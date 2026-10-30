"""Scraper for Paula's Choice (paulaschoice.com).

The product page looks empty to a naive scraper: no INCI in the visible
HTML, none in any XHR. The data hides in plain sight — a single
<script id="appData-json"> tag holding a ~280 KB BASE64-ENCODED JSON blob
(85% of the page). Decode it and Paula's Choice's famous transparency
appears fully structured:

  - page.ingredientsData: ORDERED ingredient list, each with name,
    functional categories and its own description
  - page.product: variants (price/size), skin types, concerns, benefits,
    and the site's own category taxonomy (used as the skincare gate)

Product URLs come from sitemap_0.xml (slug/<masterId>.html pattern).

Output: data/raw/paulaschoice_products.json
"""

import base64
import json
import re
import sys
import time
from pathlib import Path

import requests

# Windows consoles default to cp1252; never let a progress print kill a
# healthy scrape (a COSRX lesson).
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SITEMAP_URL = "https://www.paulaschoice.com/sitemap_0.xml"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "paulaschoice_products.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
}

APPDATA_RE = re.compile(r'id="appData-json"[^>]*>([^<]+)<')


def fetch_with_retry(url, max_attempts=3, timeout=25):
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


def fetch_product_urls():
    response = fetch_with_retry(SITEMAP_URL)
    if response is None:
        return []
    urls = re.findall(r"<loc>([^<]+)</loc>", response.text)
    return sorted({u for u in urls if re.search(r"/\d+\.html$", u)})


def decode_app_data(page_html):
    """The page's data payload: base64 inside <script id="appData-json">."""
    match = APPDATA_RE.search(page_html)
    if not match:
        return None
    try:
        return json.loads(base64.b64decode(match.group(1).strip()))
    except (ValueError, json.JSONDecodeError):
        return None


def parse_size(raw):
    """Sizes come in fl. oz ('0.5 oz'); converted to ml (1 oz = 29.5735 ml)
    so the loader's ml parser can read them."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:fl\.?\s*)?oz", str(raw or ""), re.IGNORECASE)
    if match:
        return f"{float(match.group(1)) * 29.5735:.0f}ml"
    match = re.search(r"(\d+(?:\.\d+)?)\s*ml", str(raw or ""), re.IGNORECASE)
    return f"{match.group(1)}ml" if match else "Size Not Found"


def find_price(variant):
    """Price fields move around in this payload; hunt any key containing
    'price' whose value looks like money, preferring plain 'price'."""
    for key in ("price", "salePrice", "listPrice"):
        value = variant.get(key)
        if value:
            return str(value)
    for key, value in variant.items():
        if "price" in key.lower() and isinstance(value, str) and "$" in value:
            return value
    return None


def main():
    urls = fetch_product_urls()
    print(f"Catalog loaded from sitemap: {len(urls)} product URLs")
    if not urls:
        raise SystemExit("ERROR: no product URLs found — sitemap structure changed?")

    extracted_data = []
    non_skincare = []

    for i, url in enumerate(urls, start=1):
        slug = url.rsplit("/", 2)[-2]
        print(f"[{i}/{len(urls)}] {slug[:60]}")

        response = fetch_with_retry(url)
        if response is None:
            continue
        app_data = decode_app_data(response.text)
        if not app_data or "product" not in (app_data.get("page") or {}):
            print("   (no product payload, skipping)")
            continue

        page = app_data["page"]
        product = page["product"]
        variant = (product.get("variants") or [{}])[0]

        # Domain gate, exclusion-based: Paula's Choice is a skincare brand,
        # but its category spellings vary ('Skin Care Products', 'Skincare',
        # 'Shop Collections'...). Requiring a literal 'skin care' once
        # excluded a real BHA exfoliant — so instead, exclude only what we
        # KNOW is not a single skincare product: kits/gift sets and makeup.
        categories = [c.get("name", "") for c in product.get("categories", [])]
        joined = " / ".join(categories)
        if re.search(r"kit|gift|holiday|makeup|lip gloss", joined, re.IGNORECASE):
            non_skincare.append(f"{variant.get('name') or slug}  [{joined}]")
            continue

        # ordered, structured ingredient list -> the loader's preferred path
        ingredient_names = [e.get("name", "") for e in (page.get("ingredientsData") or [])]

        name = variant.get("name") or variant.get("title") or slug
        extracted_data.append({
            "Name": name,
            "Product Type": categories[-1] if categories else "Others / Unclassified",
            "Price": find_price(variant) or "Price Not Found",
            "Size (ml)": parse_size(variant.get("size")),
            "Description": variant.get("description") or product.get("whatDoesItDo") or "Description Not Found",
            "Ingredients": ", ".join(ingredient_names) if ingredient_names else "Ingredients Not Found",
            "Ingredients_List": ingredient_names,
            "Skin Type": ", ".join(product.get("goodForSkinTypes") or []) or None,
            "Source_URL": url,
        })

        # small pause between requests, out of politeness to the server
        time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {len(extracted_data)} Products Successfully Parsed")
    with_ingredients = sum(1 for p in extracted_data if p["Ingredients_List"])
    print(f"Products with a full ingredient list: {with_ingredients}/{len(extracted_data)}")
    print(f"Non-skincare excluded: {len(non_skincare)}")
    for entry in non_skincare:
        print(f"   - {entry[:80]}")
    print("=" * 60)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
    print(f"Data saved successfully to **{OUTPUT_PATH.name}**.")


if __name__ == "__main__":
    main()
