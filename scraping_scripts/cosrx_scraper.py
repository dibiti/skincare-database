"""Scraper for COSRX (cosrx.com).

Same recipe as The Inkey List — the two easy patterns combined:
  1. Shopify's public /products.json catalog endpoint (200 products).
  2. Full INCI lists server-rendered in each product page's HTML.

COSRX pages are heavy (~1.5 MB) and contain comparison tables with PARTIAL
ingredient mentions ('Snail Secretion Filtrate, Betaine'); the extractor
naturally ignores those because the longest INCI-like candidate wins.

Output: data/raw/cosrx_products.json
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Windows consoles default to cp1252, which cannot print characters like
# the fullwidth '￡' COSRX uses in product titles — and a crashed progress
# print would kill a perfectly healthy scrape.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "https://www.cosrx.com"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "cosrx_products.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
}

TYPE_KEYWORDS = [
    ("sunscreen", "Sunscreen"), ("spf", "Sunscreen"), ("sun ", "Sunscreen"),
    ("cleanser", "Cleanser"), ("cleansing", "Cleanser"), ("bar", "Cleanser"),
    ("serum", "Serum"), ("essence", "Serum"), ("ampoule", "Serum"),
    ("cream", "Cream"), ("moisturizer", "Cream"), ("lotion", "Cream"),
    ("toner", "Toner"), ("mist", "Mist"), ("mask", "Mask"), ("patch", "Patch"),
    ("eye", "Eye Care"), ("lip", "Lip Care"), ("balm", "Balm"),
    ("gel", "Gel"), ("powder", "Powder"), ("oil", "Oil"),
    ("set", "Set"), ("kit", "Set"), ("duo", "Set"), ("trio", "Set"),
    ("bundle", "Set"), ("gift card", "Gift Card"),
]


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


def fetch_catalog():
    products = []
    page = 1
    while True:
        response = fetch_with_retry(f"{BASE_URL}/products.json?limit=250&page={page}")
        if response is None:
            break
        batch = response.json().get("products", [])
        if not batch:
            break
        products.extend(batch)
        page += 1
    return products


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def looks_like_inci_list(text):
    """Long, comma-heavy, chemical-looking content — with the two hard
    lessons from The Inkey List baked in: '$' disqualifies (shipping-rate
    state lists pass shape checks), and a positive chemistry marker is
    required (parens, digits or chemical suffixes)."""
    if len(text) < 120 or text.count(",") < 8:
        return False
    if re.search(r"Notify Me|@|http|\$", text):
        return False
    if not re.search(r"[()\d]|(?i:acid|extract|oil|water|aqua|glycer|ate\b|yl\b)", text):
        return False
    tokens = [t.strip() for t in text.split(",") if t.strip()]
    inci_like = sum(
        1 for t in tokens
        if len(t) < 60 and re.fullmatch(r"[A-Za-z0-9\s\-()/.%&+*']+", t)
    )
    return inci_like / len(tokens) > 0.7


def extract_ingredients(product_html):
    """Scans leaf text blocks AND bare text nodes (some themes drop the INCI
    list outside any leaf element — an Inkey List lesson)."""
    soup = BeautifulSoup(product_html, "html.parser")
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


def extract_size_ml(page_text, variant_title):
    for candidate in (variant_title or "", page_text or ""):
        match = re.search(r"(\d+(?:\.\d+)?)\s*ml", candidate, re.IGNORECASE)
        if match:
            return f"{match.group(1)}ml"
    return "Size Not Found"


def guess_product_type(title):
    lowered = title.lower()
    for needle, product_type in TYPE_KEYWORDS:
        if needle in lowered:
            return product_type
    return "Others / Unclassified"


def main():
    catalog = fetch_catalog()
    print(f"Catalog loaded from /products.json: {len(catalog)} products")
    if not catalog:
        raise SystemExit("ERROR: empty catalog — endpoint structure changed?")

    extracted_data = []
    for i, product in enumerate(catalog, start=1):
        url = f"{BASE_URL}/products/{product['handle']}"
        print(f"[{i}/{len(catalog)}] {product['title'][:60]}")

        response = fetch_with_retry(url)
        page_html = response.text if response else ""
        ingredients = extract_ingredients(page_html) if page_html else "Ingredients Not Found"

        variant = (product.get("variants") or [{}])[0]
        description = clean_text(
            BeautifulSoup(product.get("body_html") or "", "html.parser").get_text(separator=" ")
        )

        extracted_data.append({
            "Name": clean_text(product["title"]),
            "Product Type": guess_product_type(product["title"]),
            "Price": variant.get("price") or "Price Not Found",
            "Size (ml)": extract_size_ml(page_html, variant.get("title")),
            "Description": description or "Description Not Found",
            "Ingredients": ingredients,
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
    print("=" * 60)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
    print(f"Data saved successfully to **{OUTPUT_PATH.name}**.")


if __name__ == "__main__":
    main()
