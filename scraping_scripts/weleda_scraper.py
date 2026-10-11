"""Scraper for Weleda Switzerland (weleda.ch, French storefront).

No HTML parsing at all: the site is a Nuxt app fed by a public JSON API
(Access-Control-Allow-Origin: *), discovered via DevTools' Network tab:

    https://www.weleda.ch/api/cms/che-fr/produit/<slug>

Product slugs come from the French product sitemap
(https://www.weleda.ch/ch-fr/product-sitemap.xml, found via robots.txt).
The API returns the ingredient list as a STRUCTURED, ORDERED array of INCI
names, so this scraper emits an 'Ingredients_List' field that the loader
uses directly — no comma-splitting, no parsing bugs possible.

Output: data/raw/weleda_products.json
"""

import json
import re
import time
from pathlib import Path

import requests

SITEMAP_URL = "https://www.weleda.ch/ch-fr/product-sitemap.xml"
API_URL = "https://www.weleda.ch/api/cms/che-fr/produit/{slug}"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "weleda_products.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
}


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
    return sorted({u.rsplit("/produit/", 1)[1] for u in urls if "/produit/" in u})


def find_product_model(api_payload):
    """The page's components are keyed by GUIDs, so the product model is
    located by shape, not by name."""
    for component in (api_payload.get("page") or {}).values():
        if isinstance(component, dict):
            models = component.get("models") or {}
            if "product" in models:
                return models["product"]
    return None


def main():
    slugs = fetch_product_slugs()
    print(f"Catalog loaded from the French product sitemap: {len(slugs)} products")
    if not slugs:
        raise SystemExit("ERROR: no product slugs found — sitemap structure changed?")

    extracted_data = []
    pharma_skipped = 0

    for i, slug in enumerate(slugs, start=1):
        print(f"[{i}/{len(slugs)}] {slug[:60]}")
        response = fetch_with_retry(API_URL.format(slug=slug))
        if response is None:
            continue

        product = find_product_model(response.json())
        if product is None:
            print("   (no product model in payload, skipping)")
            continue

        # Weleda also sells registered medicines; those are not skincare
        # and carry pharma regulatory data instead of INCI lists.
        if product.get("pharmaceutical"):
            pharma_skipped += 1
            continue

        variant = (product.get("variants") or [{}])[0]
        price_cents = ((variant.get("price") or {}).get("price"))
        currency = (variant.get("price") or {}).get("currencyCode") or "CHF"
        category_path = product.get("categoryPath") or []

        ingredient_names = [
            entry.get("ingredientName", "")
            for entry in ((product.get("ingredients") or {}).get("ingredients") or [])
        ]

        extracted_data.append({
            "Name": product.get("name"),
            "Product Type": category_path[-1] if category_path else "Others / Unclassified",
            # API prices are in minor units (3420 = 34.20 CHF)
            "Price": f"{price_cents / 100:.2f} {currency}" if price_cents else "Price Not Found",
            "Size (ml)": variant.get("size") or "Size Not Found",
            "Description": product.get("summary") or product.get("description") or "Description Not Found",
            "Ingredients": ", ".join(ingredient_names) if ingredient_names else "Ingredients Not Found",
            "Ingredients_List": ingredient_names,   # structured: the loader prefers this
            "Source_URL": product.get("productUrl") or f"https://www.weleda.ch/ch-fr/produit/{slug}",
        })

        # small pause between requests, out of politeness to the server
        time.sleep(0.4)

    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {len(extracted_data)} Products Successfully Parsed")
    print(f"(pharmaceutical products skipped: {pharma_skipped})")
    with_ingredients = sum(1 for p in extracted_data if p["Ingredients_List"])
    print(f"Products with a full ingredient list: {with_ingredients}/{len(extracted_data)}")
    print("=" * 60)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
    print(f"Data saved successfully to **{OUTPUT_PATH.name}**.")


if __name__ == "__main__":
    main()
