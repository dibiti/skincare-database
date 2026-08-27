"""Enriches the ingredients table with official data from CosIng.

CosIng is the European Commission's database of cosmetic ingredients. This
script uses the same public search API that the CosIng website itself calls
(endpoint and API key come from the site's own env-json-config.json — they
are public by design, shipped to every browser that visits the site).

Design principles:
- The database IS the cache: each ingredient is queried once and the result
  (including "not found") is stored. Re-running the script only processes
  ingredients that were never checked, so it is cheap and resumable.
- Politeness: one request at a time, with a small pause between calls. We
  are guests on a public service.
- Nothing is destroyed: CosIng data fills empty fields and updates official
  ones (function, classification, CAS/EC numbers), but a manually written
  description is never overwritten with nothing.

Usage:
    python loader/enrich_ingredients.py         # process all pending
    python loader/enrich_ingredients.py 20      # process only 20 (test run)
"""

import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[1]

# Public endpoint + key used by the CosIng website itself
# (source: https://ec.europa.eu/growth/tools-databases/cosing/assets/env-json-config.json)
COSING_SEARCH_URL = "https://webgate.ec.europa.eu/es/search-api/rest/search"
COSING_API_KEY = "285a77fd-1257-4271-8507-f0c6b2961203"

PAUSE_BETWEEN_CALLS = 0.4   # seconds; be a polite guest
COMMIT_EVERY = 25           # ingredients per transaction

# CosIng annex -> human-readable regulatory classification
ANNEX_CLASSIFICATION = {
    "II": "Prohibited (Annex II)",
    "III": "Restricted (Annex III)",
    "IV": "Colorant (Annex IV)",
    "V": "Preservative (Annex V)",
    "VI": "UV filter (Annex VI)",
}


def query_cosing(session, text, max_attempts=3):
    """Runs one search against the CosIng API. Pass the text already quoted
    ('"NAME"') for an exact-phrase search, or bare for a fuzzy search.
    Returns the list of result metadata dicts (possibly empty)."""
    params = {
        "apiKey": COSING_API_KEY,
        "text": text,
        "pageSize": 50,
        "pageNumber": 1,
    }
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.post(COSING_SEARCH_URL, params=params, timeout=20)
            response.raise_for_status()
            return [r.get("metadata", {}) for r in response.json().get("results", [])]
        except (requests.RequestException, ValueError) as e:
            if attempt < max_attempts:
                time.sleep(2 * attempt)
            else:
                print(f"   API error for '{name}' after {max_attempts} attempts: {e}")
    return []


def first(metadata, field):
    """CosIng metadata wraps every value in a list; returns the first item
    (stripped) or None. '-' means 'no value' in CosIng."""
    values = metadata.get(field) or []
    if not values:
        return None
    value = str(values[0]).strip()
    # '-' means 'no value'; multi-part entries can be all-empty too ('- / - / -')
    if not value or re.fullmatch(r"[\s/-]*", value):
        return None
    return value[:255]


def pick_match(results, name):
    """Finds the result whose INCI name equals ours (case-insensitive).
    Active entries win over historical ('Not active') ones."""
    candidates = [
        m for m in results
        if (first(m, "inciName") or "").upper() == name.upper()
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda m: 0 if first(m, "status") == "Active" else 1)
    return candidates[0]


def find_annex_entry(session, name, ingredient_entry):
    """Looks up the REGULATORY entry for a matched ingredient.

    CosIng keeps two separate records: the inventory entry (rich description,
    functions — what pick_match returns) and, for regulated ingredients, a
    substance entry holding the annex number and the legal maximum
    concentration. The substance entry is indexed under its chemical name,
    so the exact-phrase search never returns it; a fuzzy search does, and
    the two records are linked by id: substance.identifiedIngredient ==
    ingredient.substanceId. That id link is what makes this safe — a fuzzy
    search returns loosely related entries, and we must never take an annex
    from a record that merely resembles our name."""
    substance_id = first(ingredient_entry, "substanceId")
    if not substance_id:
        return None, None

    for m in query_cosing(session, name):   # unquoted = fuzzy search
        if (m.get("itemType") or [""])[0] == "substance" \
                and first(m, "identifiedIngredient") == substance_id:
            return first(m, "annexNo"), first(m, "maximumConcentration")
    return None, None


def name_variants(name):
    """Fallback spellings for names CosIng doesn't know verbatim.
    'AQUA (WATER)' is tried as 'AQUA' and then 'WATER'."""
    variants = []
    if "(" in name:
        outside = re.sub(r"\s*\([^)]*\)", "", name).strip()
        inside = ", ".join(re.findall(r"\(([^)]*)\)", name)).strip()
        variants = [v for v in (outside, inside) if len(v) >= 2]
    return variants


def classification_for(annex):
    if annex:
        return ANNEX_CLASSIFICATION.get(annex, f"Annex {annex}")[:50]
    return "Inventory"


def enrich_one(session, name):
    """Queries CosIng for one ingredient, trying fallback spellings if the
    exact name doesn't match. Returns (metadata, annex, max_concentration),
    all None when nothing matched."""
    for candidate in [name] + name_variants(name):
        match = pick_match(query_cosing(session, f'"{candidate}"'), candidate)
        time.sleep(PAUSE_BETWEEN_CALLS)
        if match:
            annex, max_conc = find_annex_entry(session, candidate, match)
            time.sleep(PAUSE_BETWEEN_CALLS)
            return match, annex, max_conc
    return None, None, None


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    load_dotenv(REPO_ROOT / ".env")
    conn = psycopg2.connect(
        host="localhost",
        port=os.getenv("POSTGRES_HOST_PORT", "5433"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    session = requests.Session()

    with conn.cursor() as cur:
        cur.execute(
            """SELECT ingredient_id, ingredient_name FROM ingredients
               WHERE cosing_status IS NULL
               ORDER BY ingredient_id""" + (f" LIMIT {limit}" if limit else "")
        )
        pending = cur.fetchall()

    print(f"{len(pending)} ingredients to enrich...")
    matched = 0
    not_found = 0

    try:
        with conn.cursor() as cur:
            for i, (ingredient_id, name) in enumerate(pending, start=1):
                metadata, annex, max_conc = enrich_one(session, name)

                if metadata:
                    functions = ", ".join(metadata.get("functionName") or []) or None
                    cur.execute(
                        """UPDATE ingredients SET
                               ingredient_description  = COALESCE(%s, ingredient_description),
                               ingredient_function     = COALESCE(%s, ingredient_function),
                               cosmetic_classification = %s,
                               annex_max_concentration = %s,
                               cas_no                  = %s,
                               ec_no                   = %s,
                               cosing_status           = 'matched',
                               cosing_checked_at       = NOW()
                           WHERE ingredient_id = %s""",
                        (
                            first(metadata, "chemicalDescription"),
                            functions[:255] if functions else None,
                            classification_for(annex),
                            max_conc[:100] if max_conc else None,
                            first(metadata, "casNo"),
                            first(metadata, "ecNo"),
                            ingredient_id,
                        ),
                    )
                    matched += 1
                else:
                    cur.execute(
                        """UPDATE ingredients SET
                               cosing_status = 'not_found',
                               cosing_checked_at = NOW()
                           WHERE ingredient_id = %s""",
                        (ingredient_id,),
                    )
                    not_found += 1

                if i % COMMIT_EVERY == 0:
                    conn.commit()
                    print(f"   [{i}/{len(pending)}] matched: {matched}, "
                          f"not found: {not_found}")

        conn.commit()
    finally:
        conn.close()

    print("\n=== ENRICHMENT SUMMARY ===")
    print(f"processed: {len(pending)} | matched: {matched} | not found: {not_found}")
    if pending:
        print(f"match rate: {matched / len(pending):.1%}")


if __name__ == "__main__":
    main()
