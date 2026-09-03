"""Scraper for Beauty of Joseon (beautyofjoseon.com).

This brand's store runs on Shopify, which exposes a public JSON catalog at
/products.json — no HTML parsing, no Selenium, no 'Load More' buttons. One
request returns every product with title, handle, price and description.

The full INCI ingredient list is not in the catalog JSON, though: it lives on
each product's page, server-rendered inside a <dialog> element (the "Full
Ingredient List" popup). So the strategy is:

  1. /products.json (paginated)  -> catalog skeleton
  2. each product page           -> ingredient list from the dialog

Output: data/raw/beautyofjoseon_products.json, with the same field names as
the other scrapers so the loader ingests it unchanged.
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE_URL = "https://beautyofjoseon.com"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "beautyofjoseon_products.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
}


def fetch_with_retry(url, max_attempts=3, timeout=15):
    """Fetches a URL, retrying on transient failures so one slow response
    does not cost us a product."""
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
    """Reads the whole catalog from Shopify's public /products.json,
    following pagination until a page comes back empty."""
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
    """Removes excess whitespace, newlines, and replaces them with a single space."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def looks_like_inci_list(text):
    """An INCI list is long and comma-heavy, made of short chemical-looking
    names. (An earlier version also required the text to START with water —
    which silently rejected cleansing oils and sunscreens, whose lists open
    with esters and UV filters. Content checks beat position checks.)"""
    if len(text) < 120 or text.count(",") < 8:
        return False
    if re.search(r"Notify Me|@|http", text):
        return False
    tokens = [t.strip() for t in text.split(",") if t.strip()]
    inci_like = sum(
        1 for t in tokens
        if len(t) < 60 and re.fullmatch(r"[A-Za-z0-9\s\-()/.%&+*']+", t)
    )
    return inci_like / len(tokens) > 0.7


def extract_ingredients(product_html):
    """Finds the full INCI list on a product page: it is server-rendered
    inside one of the page's <dialog> popups."""
    soup = BeautifulSoup(product_html, "html.parser")

    for dialog in soup.find_all("dialog"):
        text = clean_text(dialog.get_text(separator=" "))
        if looks_like_inci_list(text):
            return text

    return "Ingredients Not Found"


_driver = None
_driver_uses = 0

# One fresh browser per page: empirically, the app script that injects the
# ingredient dialog runs reliably on a browser's FIRST page load and only
# erratically on later ones. Combined with the polling wait below (which
# absorbs the cold-cache slowness) and the accumulation cache (which makes
# re-runs cheap), this is the configuration that converges.
MAX_DRIVER_USES = 1


def reset_driver():
    global _driver, _driver_uses
    if _driver is not None:
        _driver.quit()
    _driver = None
    _driver_uses = 0


def get_driver():
    """Creates the headless Chrome driver on first use only — most products
    never need it, so most runs never pay the browser start-up cost."""
    global _driver, _driver_uses
    if _driver is not None and _driver_uses >= MAX_DRIVER_USES:
        reset_driver()
    _driver_uses += 1
    if _driver is None:
        options = Options()
        # '--headless=new' + a realistic user agent: the old headless mode
        # announces itself ('HeadlessChrome') and this site's app scripts
        # stay silent for it — no scripts, no injected ingredient dialog
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument(f"user-agent={HEADERS['User-Agent']}")
        _driver = webdriver.Chrome(options=options)
    return _driver


def extract_ingredients_with_js(url):
    """Fallback for newer product pages: their full INCI list is injected
    into a <dialog> by an app script AFTER page load, so plain requests
    never sees it. A headless browser lets that script run, then the same
    dialog extractor works on the rendered DOM."""
    try:
        driver = get_driver()
        driver.get(url)
        # Poll instead of a fixed sleep: the dialog appears whenever the app
        # script finishes (2s on a warm cache, much later on a cold one).
        # A fixed 6s sleep was both too slow for easy pages and too
        # impatient for slow ones.
        deadline = time.time() + 25
        while time.time() < deadline:
            time.sleep(2)
            ingredients = extract_ingredients(driver.page_source)
            if ingredients != "Ingredients Not Found":
                return ingredients
        return "Ingredients Not Found"
    except Exception as e:
        print(f"   Selenium fallback failed for {url}: {e}")
        return "Ingredients Not Found"


def extract_size_ml(page_text, variant_title):
    """Sizes show up either in the variant name ('30ml') or in the page
    text ('1.01 fl. oz.(30ml)')."""
    for candidate in (variant_title or "", page_text or ""):
        match = re.search(r"(\d+(?:\.\d+)?)\s*ml", candidate, re.IGNORECASE)
        if match:
            return f"{match.group(1)}ml"
    return "Size Not Found"


def guess_product_type(title):
    """The catalog JSON leaves product_type empty, so it is inferred from
    the title. Unknown titles stay unclassified rather than guessed wrong."""
    keywords = [
        ("sunscreen", "Sunscreen"), ("sun stick", "Sunscreen"), ("spf", "Sunscreen"),
        ("cleanser", "Cleanser"), ("cleansing", "Cleanser"),
        ("serum", "Serum"), ("ampoule", "Serum"),
        ("cream", "Cream"), ("moisturizer", "Cream"),
        ("toner", "Toner"), ("mask", "Mask"), ("eye", "Eye Care"),
        ("lip", "Lip Care"), ("balm", "Balm"), ("mist", "Mist"),
        ("set", "Set"), ("kit", "Set"), ("duo", "Set"),
    ]
    lowered = title.lower()
    for needle, product_type in keywords:
        if needle in lowered:
            return product_type
    return "Others / Unclassified"


def load_previous_ingredients():
    """Ingredient lists found by earlier runs, keyed by product URL.

    The site's app scripts fail randomly for a fraction of pages on any
    given run, so results accumulate across runs instead of starting from
    zero: whatever a previous run managed to extract is kept, and only the
    still-missing products are attempted again. (Same principle as the
    CosIng cache: never re-ask what you already know.)"""
    if not OUTPUT_PATH.exists():
        return {}
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        previous = json.load(f)
    return {
        p["Source_URL"]: p["Ingredients"]
        for p in previous
        if p.get("Ingredients") and p["Ingredients"] != "Ingredients Not Found"
    }


def main():
    catalog = fetch_catalog()
    print(f"Catalog loaded from /products.json: {len(catalog)} products")

    known_ingredients = load_previous_ingredients()
    if known_ingredients:
        print(f"Reusing {len(known_ingredients)} ingredient lists from previous runs")

    extracted_data = []
    for i, product in enumerate(catalog, start=1):
        url = f"{BASE_URL}/products/{product['handle']}"
        print(f"[{i}/{len(catalog)}] {product['title'][:60]}")

        if url in known_ingredients:
            ingredients = known_ingredients[url]
            page_html = ""   # no page fetch needed; size comes from the variant
        elif known_ingredients:
            # Re-run for a product that already failed the static path once:
            # skip the requests hit entirely. Two near-simultaneous hits on
            # the same URL — one with a Python TLS fingerprint, one from a
            # browser — is a classic bot pattern, and the page's app scripts
            # (which inject the ingredient dialog) tend to stay silent after
            # it. One clean browser visit looks like a normal customer.
            page_html = ""
            ingredients = "Ingredients Not Found"
        else:
            response = fetch_with_retry(url)
            page_html = response.text if response else ""
            ingredients = extract_ingredients(page_html) if page_html else "Ingredients Not Found"

        # newer templates only render the list via JavaScript — fall back to
        # a real browser for those. Sets and merch never publish a list
        # (verified empirically), so they skip the expensive fallback.
        merch_words = ("set", "kit", "duo", "trio", "pouch", "charm", "bundle",
                       "routine", "collection", "gift", "tumbler", "headband",
                       "towel", "case", "gwalsa", "bojagi", "scrunchie", "soap saver")
        is_merch = any(w in product["title"].lower() for w in merch_words)
        if ingredients == "Ingredients Not Found" and not is_merch:
            ingredients = extract_ingredients_with_js(url)

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
    print("=" * 60)

    with_ingredients = sum(
        1 for p in extracted_data if p["Ingredients"] != "Ingredients Not Found"
    )
    print(f"Products with a full ingredient list: {with_ingredients}/{len(extracted_data)}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
    print(f"Data saved successfully to **{OUTPUT_PATH.name}**.")

    reset_driver()


if __name__ == "__main__":
    main()
