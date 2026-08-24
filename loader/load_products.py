"""Loads the scraped product JSON files (data/raw/) into PostgreSQL.

Design principles:
- Idempotent: every write is an UPSERT (INSERT ... ON CONFLICT), so running
  the loader twice leaves the database exactly the same. Re-scraping and
  re-loading is always safe.
- One common shape: each scraper names its fields slightly differently, so a
  small adapter step maps them all onto the same structure instead of
  rewriting the scrapers.
- Fail loudly: a source file with zero products aborts the run with an error.
  A scraper that silently returns nothing is a broken scraper, not a success.
"""

import json
import os
import re
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "raw"

# Which file belongs to which brand, and what currency to assume when the
# price string carries no symbol (CeraVe prints bare numbers, in USD).
SOURCES = [
    {"file": "cerave_products.json",       "brand": "CeraVe",          "default_currency": "USD"},
    {"file": "haruharu_products_full.json", "brand": "Haruharu Wonder", "default_currency": "USD"},
    {"file": "ordinary_products_full.json", "brand": "The Ordinary",    "default_currency": "EUR"},
    {"file": "vtcosmetics_products.json",   "brand": "VT Cosmetics",    "default_currency": "USD"},
]

# The Ordinary labels skin compatibility like "Dry Skin"; our reference table
# uses bare names like "Dry". Unknown labels (e.g. "All Hair Types") are skipped.
SKIN_TYPE_MAP = {
    "dry skin": "Dry",
    "oily skin": "Oily",
    "normal skin": "Normal",
    "combination skin": "Combination",
    "sensitive skin": "Sensitive",
    "all skin types": "ALL Skin Types",
}

NOT_FOUND = re.compile(r"not found", re.IGNORECASE)


# --------------------------------------------------------------------------
# Parsing helpers: scraped strings -> clean typed values
# --------------------------------------------------------------------------

def clean_or_none(value):
    """Returns the stripped string, or None for empty/placeholder values."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or NOT_FOUND.search(text):
        return None
    return text


def parse_price(raw, default_currency):
    """'$17.00' -> (17.00, 'USD'); '€11.40 EUR' -> (11.40, 'EUR')."""
    text = clean_or_none(raw)
    if not text:
        return None, None

    match = re.search(r"(\d+(?:[.,]\d{1,2})?)", text)
    if not match:
        return None, None
    amount = float(match.group(1).replace(",", "."))

    if "€" in text or "EUR" in text.upper():
        currency = "EUR"
    elif "CHF" in text.upper():
        currency = "CHF"
    elif "$" in text or "USD" in text.upper():
        currency = "USD"
    else:
        currency = default_currency
    return amount, currency


def parse_size_ml(raw):
    """'15ml' -> 15.0; '10ml, 30ml' -> 10.0 (first listed); junk -> None."""
    text = clean_or_none(raw)
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*ml", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def split_ingredients(raw):
    """Turns a raw ingredient string into an ordered list of
    (inci_name, concentration_percent) tuples.

    - Bracketed sub-product labels in sets ('[Barrier Serum] Water, ...')
      are dropped and the ingredient lists merged.
    - Names are normalized to UPPERCASE: 'Water' (Haruharu) and 'WATER'
      (CeraVe) are the same substance and must land on the same row. The
      INCI convention (and CosIng, coming in Sprint 3) is uppercase anyway.
    - 'SALICYLIC ACID 2%' -> ('SALICYLIC ACID', 2.0).
    """
    text = clean_or_none(raw)
    if not text:
        return []

    text = re.sub(r"\[[^\]]*\]", ",", text)

    # Chemical names can contain commas ('1,2-Hexanediol'), which a naive
    # comma-split breaks into '1' + '2-Hexanediol'. When a fragment is just
    # digits, it belongs to the next fragment — glue them back together.
    parts = []
    for fragment in text.split(","):
        fragment = fragment.strip()
        if parts and re.fullmatch(r"\d+", parts[-1]):
            parts[-1] = parts[-1] + "," + fragment
        else:
            parts.append(fragment)

    seen = set()
    result = []
    for part in parts:
        name = part.strip()

        concentration = None
        conc_match = re.search(r"(\d+(?:\.\d+)?)\s*%", name)
        if conc_match:
            concentration = float(conc_match.group(1))
            name = name.replace(conc_match.group(0), "").strip()

        name = re.sub(r"\s{2,}", " ", name).strip(" .*").upper()

        if len(name) < 2 or len(name) > 255:
            continue
        if name in seen:  # sets can repeat ingredients; keep the first rank
            continue
        seen.add(name)
        result.append((name, concentration))
    return result


# --------------------------------------------------------------------------
# Database helpers: one small function per table, all idempotent
# --------------------------------------------------------------------------

def get_or_create_brand(cur, brand_name):
    cur.execute(
        """INSERT INTO brands (brand_name) VALUES (%s)
           ON CONFLICT (brand_name) DO NOTHING""",
        (brand_name,),
    )
    cur.execute("SELECT brand_id FROM brands WHERE brand_name = %s", (brand_name,))
    return cur.fetchone()[0]


def upsert_product(cur, brand_id, record, default_currency):
    price, currency = parse_price(
        record.get("Price") or record.get("Price_Regular"), default_currency
    )
    cur.execute(
        """INSERT INTO products
               (product_name, brand_id, product_type, price, price_currency,
                size_ml, description)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT ON CONSTRAINT uq_products_name_brand DO UPDATE SET
               product_type   = EXCLUDED.product_type,
               price          = EXCLUDED.price,
               price_currency = EXCLUDED.price_currency,
               size_ml        = EXCLUDED.size_ml,
               description    = EXCLUDED.description
           RETURNING product_id""",
        (
            clean_or_none(record.get("Name")),
            brand_id,
            clean_or_none(record.get("Product Type")),
            price,
            currency,
            parse_size_ml(record.get("Size (ml)")),
            clean_or_none(record.get("Description")),
        ),
    )
    return cur.fetchone()[0]


def get_or_create_ingredient(cur, inci_name):
    cur.execute(
        """INSERT INTO ingredients (ingredient_name) VALUES (%s)
           ON CONFLICT (ingredient_name) DO NOTHING""",
        (inci_name,),
    )
    cur.execute(
        "SELECT ingredient_id FROM ingredients WHERE ingredient_name = %s",
        (inci_name,),
    )
    return cur.fetchone()[0]


def link_ingredient(cur, product_id, ingredient_id, concentration, rank):
    cur.execute(
        """INSERT INTO product_ingredients
               (product_id, ingredient_id, concentration_percent, ingredient_rank)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (product_id, ingredient_id) DO UPDATE SET
               concentration_percent = EXCLUDED.concentration_percent,
               ingredient_rank       = EXCLUDED.ingredient_rank""",
        (product_id, ingredient_id, concentration, rank),
    )


def link_skin_types(cur, product_id, raw_value):
    """Links The Ordinary's 'Skin Type' field to the skin_types table.
    Returns the labels it could not map, so the summary can report them."""
    text = clean_or_none(raw_value)
    if not text:
        return []

    unmapped = []
    for label in text.split(","):
        mapped = SKIN_TYPE_MAP.get(label.strip().lower())
        if not mapped:
            unmapped.append(label.strip())
            continue
        cur.execute(
            """INSERT INTO product_skin_types (product_id, skin_type_id)
               SELECT %s, skin_type_id FROM skin_types WHERE skin_type_name = %s
               ON CONFLICT DO NOTHING""",
            (product_id, mapped),
        )
    return unmapped


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    load_dotenv(REPO_ROOT / ".env")
    conn = psycopg2.connect(
        host="localhost",
        port=os.getenv("POSTGRES_HOST_PORT", "5433"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )

    try:
        for source in SOURCES:
            path = DATA_DIR / source["file"]
            if not path.exists():
                sys.exit(f"ERROR: {path} not found. Run the scraper first.")

            with open(path, encoding="utf-8") as f:
                records = json.load(f)

            # Fail loudly: an empty file means a broken scraper, not "no news".
            if not records:
                sys.exit(f"ERROR: {source['file']} contains 0 products — "
                         "the scraper is probably broken. Aborting, nothing loaded.")

            with conn.cursor() as cur:
                brand_id = get_or_create_brand(cur, source["brand"])

                loaded = 0
                links = 0
                skipped = 0
                unmapped_skin_labels = set()

                for record in records:
                    if not clean_or_none(record.get("Name")):
                        skipped += 1
                        continue

                    product_id = upsert_product(cur, brand_id, record,
                                                source["default_currency"])

                    for rank, (name, conc) in enumerate(
                            split_ingredients(record.get("Ingredients")), start=1):
                        ingredient_id = get_or_create_ingredient(cur, name)
                        link_ingredient(cur, product_id, ingredient_id, conc, rank)
                        links += 1

                    unmapped_skin_labels.update(
                        link_skin_types(cur, product_id, record.get("Skin Type")))
                    loaded += 1

            # one commit per brand: a failure in file 3 never corrupts files 1-2
            conn.commit()

            print(f"[{source['brand']}] {loaded} products upserted, "
                  f"{links} ingredient links, {skipped} skipped (no name)")
            if unmapped_skin_labels:
                print(f"   note: unmapped skin-type labels ignored: "
                      f"{sorted(unmapped_skin_labels)}")

        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM brands),
                    (SELECT COUNT(*) FROM products),
                    (SELECT COUNT(*) FROM ingredients),
                    (SELECT COUNT(*) FROM product_ingredients)
            """)
            brands, products, ingredients, product_ingredients = cur.fetchone()

        print("\n=== DATABASE TOTALS ===")
        print(f"brands: {brands} | products: {products} | "
              f"ingredients: {ingredients} | product_ingredients: {product_ingredients}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
