"""Scraper for Typology Paris (typology.com).

Everything is server-rendered in static HTML — no Shopify endpoint, no
JavaScript, no Selenium:
  - product slugs from sitemap.xml (CeraVe technique)
  - name / description / price from the Open Graph meta tags
  - the product's own category from the BreadcrumbList JSON-LD
  - the full INCI list as a text run in the page body

Typology also sells MAKEUP (mascaras, tinted serums, brow products...).
This is a skincare database, so makeup is excluded — loudly, with a count
and the category that triggered the exclusion, never silently.

Output: data/raw/typology_products.json
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Windows consoles default to cp1252; French accents and typographic marks
# in titles must not crash a healthy scrape (a COSRX lesson).
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SITEMAP_URL = "https://www.typology.com/sitemap.xml"
BASE_URL = "https://www.typology.com"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "typology_products.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
}

# Category or slug markers that identify makeup. 'Soins lèvres' (lip CARE)
# stays; tinted/colour products ('teinté', mascara, brows...) go.
# CAREFUL: 'teinte' (tinted; slugs drop the accent) is makeup, but bare
# 'teint' (complexion — as in the 'Teint terne' skin-concern category) is
# skincare. A '\bteint\b' marker once excluded an antioxidant cream.
MAKEUP_MARKERS = re.compile(
    r"maquillage|teinte|mascara|sourcils|\bcils\b|blush|gloss|"
    r"highlighter|anti-?cernes|concealer|crayon|rouge-",
    re.IGNORECASE,
)


def fetch_with_retry(url, max_attempts=3, timeout=20):
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if attempt < max_attempts:
                time.sleep(2 * attempt)
            else:
                print(f"ERROR: Could not fetch {url} after {max_attempts} attempts: {e}")
    return None


def fetch_product_slugs():
    response = fetch_with_retry(SITEMAP_URL)
    if response is None:
        return []
    urls = re.findall(r"<loc>([^<]+)</loc>", response.text)
    slugs = {u.rsplit("/products/", 1)[1] for u in urls if "/products/" in u}
    return sorted(slugs)


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def meta_content(soup, prop):
    tag = soup.find("meta", attrs={"property": prop})
    return clean_text(tag["content"]) if tag and tag.has_attr("content") else None


def breadcrumb_category(soup):
    """The site's own taxonomy, from the BreadcrumbList JSON-LD: the last
    collection-level entry ('Sérums visage', 'Coffrets', ...)."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if data.get("@type") == "BreadcrumbList":
            names = [e.get("name", "") for e in data.get("itemListElement", [])]
            # [Accueil, <collection>, <product>] -> the collection
            if len(names) >= 3:
                return names[-2]
    return None


def looks_like_inci_list(text):
    """Long, comma-heavy, chemical-looking content — with the hard lessons
    baked in: '$' disqualifies (shipping tables), and a positive chemistry
    marker is required."""
    if len(text) < 100 or text.count(",") < 6:
        return False
    if re.search(r"Notify Me|@|http|\$", text):
        return False
    if not re.search(r"[()\d]|(?i:acid|extract|oil|water|aqua|glycer|ate\b|yl\b)", text):
        return False
    tokens = [t.strip() for t in text.split(",") if t.strip()]
    inci_like = sum(
        1 for t in tokens
        if len(t) < 60 and re.fullmatch(r"[A-Za-zÀ-ÿ0-9\s\-()/.%&+*']+", t)
    )
    return inci_like / len(tokens) > 0.7


def extract_ingredients(soup):
    candidates = []
    for tag in soup.find_all(["p", "div", "li", "span", "td"]):
        if not tag.find(["p", "div", "li"]):
            text = clean_text(tag.get_text(separator=" "))
            if looks_like_inci_list(text):
                candidates.append(text)
            continue
        direct = clean_text(" ".join(tag.find_all(string=True, recursive=False)))
        if looks_like_inci_list(direct):
            candidates.append(direct)
    return max(candidates, key=len) if candidates else "Ingredients Not Found"


def extract_size_ml(page_text):
    match = re.search(r"(\d+(?:\.\d+)?)\s*ml\b", page_text or "", re.IGNORECASE)
    return f"{match.group(1)}ml" if match else "Size Not Found"


def main():
    slugs = fetch_product_slugs()
    print(f"Catalog loaded from sitemap: {len(slugs)} unique products")
    if not slugs:
        raise SystemExit("ERROR: no product slugs found — sitemap structure changed?")

    extracted_data = []
    makeup_excluded = []

    for i, slug in enumerate(slugs, start=1):
        url = f"{BASE_URL}/products/{slug}"
        print(f"[{i}/{len(slugs)}] {slug[:60]}")

        response = fetch_with_retry(url)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, "html.parser")

        name = meta_content(soup, "og:title") or slug
        name = re.sub(r"\s*—\s*Typology\s*$", "", name)
        category = breadcrumb_category(soup) or "Others / Unclassified"

        # the skincare-only gate: judged on the site's own category AND the
        # slug, excluded loudly at the end of the run
        if MAKEUP_MARKERS.search(category) or MAKEUP_MARKERS.search(slug):
            makeup_excluded.append(f"{name}  [{category}]")
            continue

        price = meta_content(soup, "product:price:amount")
        currency = meta_content(soup, "product:price:currency") or "EUR"

        extracted_data.append({
            "Name": name,
            "Product Type": category,
            "Price": f"{price} {currency}" if price else "Price Not Found",
            "Size (ml)": extract_size_ml(soup.get_text(" ")),
            "Description": meta_content(soup, "og:description") or "Description Not Found",
            "Ingredients": extract_ingredients(soup),
            "Source_URL": url,
        })

        # small pause between requests, out of politeness to the server
        time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {len(extracted_data)} Products Successfully Parsed")
    with_ingredients = sum(
        1 for p in extracted_data if p["Ingredients"] != "Ingredients Not Found"
    )
    print(f"Products with a full ingredient list: {with_ingredients}/{len(extracted_data)}")
    print(f"Makeup products excluded (skincare database): {len(makeup_excluded)}")
    for entry in makeup_excluded:
        print(f"   - {entry[:80]}")
    print("=" * 60)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
    print(f"Data saved successfully to **{OUTPUT_PATH.name}**.")


if __name__ == "__main__":
    main()
