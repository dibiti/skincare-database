import requests
from bs4 import BeautifulSoup
import time
import re
import json

# NOTE (2026-08): CeraVe redesigned their site. The old category page with the
# 'load-more-results__cta-btn' button and 'results__card-front' cards is gone,
# so the Selenium-based catalog crawl stopped finding products (0 results).
# The new approach reads the sitemap.xml instead: it lists every page on the
# site, we keep the /skincare/ and /sunscreen/ ones, and parse_content() itself
# tells us which are real product pages (only those have the 'pdp-heading' h1).
# Bonus: no Selenium needed anymore — plain requests is enough.

SITEMAP_URL = "https://www.cerave.com/sitemap.xml"
BASE_URL = "https://www.cerave.com"

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
            return response.text
        except requests.RequestException as e:
            if attempt < max_attempts:
                time.sleep(2 * attempt)
            else:
                print(f"ERROR: Could not fetch URL {url} after {max_attempts} attempts: {e}")
    return None

def extract_product_links():
    """Collects candidate product URLs from the sitemap.

    The root sitemap.xml may just point to other sitemap files (a 'sitemap
    index'), so we follow those first, then keep every URL under /skincare/
    or /sunscreen/. Category pages slip through here — they are filtered out
    later because they have no 'pdp-heading' when parsed.
    """
    xml = fetch_with_retry(SITEMAP_URL)
    if not xml:
        return []

    # if this is a sitemap index, follow the child sitemaps (skip video/image ones)
    child_sitemaps = [
        loc for loc in re.findall(r'<loc>([^<]+)</loc>', xml)
        if loc.endswith('sitemap.xml')
    ]
    if child_sitemaps:
        xml = "".join(filter(None, (fetch_with_retry(u) for u in child_sitemaps)))

    urls = re.findall(r'<loc>([^<]+)</loc>', xml)
    product_links = [
        u for u in urls
        if re.search(r'https://www\.cerave\.com/(skincare|sunscreen)/', u)
    ]

    return sorted(set(product_links))

def clean_text(text):
    """Removes excess whitespace, newlines, and replaces them with a single space."""
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', text)
    return cleaned.strip()

def scrape_product_details(url):
    """Fetches the HTML content for a single product URL using requests."""
    return fetch_with_retry(url)

def parse_content(html_content):
    """Parses the HTML and extracts the product data."""
    if not html_content:
        return

    soup = BeautifulSoup(html_content, 'html.parser')
    product_data = {}

    # Extracting the Product Name 
    try:
        name_tag = soup.find('h1', class_='pdp-heading') 
        if name_tag:
            product_data['Name'] = clean_text(name_tag.text)
        else:
            product_data['Name'] = "Product Name Not Found"
            
    except Exception as e:
        product_data['Name'] = f"Error extracting Name: {e}"
    
    # Extracting the Product Type
    try:
        active_counter = soup.find(class_='productHowTo-when-steps-step__counter--active')
        product_type = "Type Not Found"

        if active_counter:
            list_item = active_counter.find_parent('li')
            if list_item:
                title_tag = list_item.find(class_='productHowTo-when-steps-step__title')
                if title_tag:
                    product_type = clean_text(title_tag.text)
                
        product_data['Product Type'] = product_type
            
    except Exception as e:
        product_data['Product Type'] = f"Error extracting Product Type: {e}"

    # Extracting the Price
    try:
        price_tag = soup.find('p', class_='product-details__price')
        if price_tag:
            raw_price = clean_text(price_tag.text)
            product_data['Price'] = raw_price.replace('$', '').strip() 
        else:
            product_data['Price'] = "Price Not Found"
            
    except Exception as e:
        product_data['Price'] = f"Error extracting Price: {e}"

    # Extracting the Available Sizes
    # Since the website don't have this informations
    product_data['Size (ml)'] = "Size Not Found"

    # Extracting the Product Description
    try:
        description_tag = soup.find('p', class_='product-details__description') 
        if description_tag:
            product_data['Description'] = clean_text(description_tag.text)
        else:
            product_data['Description'] = "Description Not Found"
            
    except Exception as e:
        product_data['Description'] = f"Error extracting Description: {e}"

    # Extracting the Ingredients
    try:
        ingredients_div = soup.find('div', class_='richtext keyIngredients-details__content')
        if ingredients_div:
            
            for a_tag in ingredients_div.find_all('a'):
                a_tag.unwrap() 

            for unwanted_tag in ingredients_div.find_all(lambda tag: tag.name in ['p', 'em'] and ('refilled products in the store' in tag.text or 'Please be aware that ingredient lists' in tag.text or 'Code F.I.L.' in tag.text)):
                unwanted_tag.decompose()
            
            raw_text = ingredients_div.get_text(separator=' ').strip()
            cleaned_text = raw_text
            cleaned_text = re.sub(r'^\s*(INGREDIENTS?:?\s*)+\s*[\d\s-]*\s*(INGREDIENTS?:?\s*)*', '', cleaned_text, flags=re.IGNORECASE).strip()
            cleaned_text = re.sub(r'\s*\(Code\s*F\.I\.L\..*?\)', '', cleaned_text).strip()
            cleaned_text = re.sub(r'(ACTIVE|INACTIVE)\s*INGREDIENTS?:?\s*', '', cleaned_text, flags=re.IGNORECASE).strip()

            cleaned_text = re.sub(
                r'\s*\([^)]*\d+\.\d*\%[^)]*\)\s*', 
                '', cleaned_text, flags=re.IGNORECASE).strip() 
                
            cleaned_text = re.sub(r'\s*\([^)]*\)\s*', ', ', cleaned_text).strip()
            cleaned_text = re.sub(r'(Sunscreen|SUNSCREEN|\.\.+)', '', cleaned_text, flags=re.IGNORECASE).strip()
            cleaned_text = re.sub(r'(\d\%|[a-z])\s+([A-Z])', r'\1, \2', cleaned_text)
            cleaned_text = re.sub(r'[\s\n]*•[\s\n]*', ', ', cleaned_text)
            cleaned_text = re.sub(r'\s{2,}', ' ', cleaned_text)
            cleaned_text = re.sub(r'\n', ', ', cleaned_text)
            cleaned_text = re.sub(r'\s*,\s*', ', ', cleaned_text)
            cleaned_text = cleaned_text.strip(', ')
            
            product_data['Ingredients'] = clean_text(cleaned_text)
            
        else:
            product_data['Ingredients'] = "Ingredients Div Not Found"
            
    except Exception as e:
        product_data['Ingredients'] = f"Error extracting Ingredients: {e}"

    return product_data

if __name__ == "__main__":

    product_urls = extract_product_links()

    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {len(product_urls)} Candidate URLs to be Processed")
    print("=" * 60)

    extracted_data = []

    if product_urls:
        for i, url in enumerate(product_urls):
            print(f" -> Processing {i+1}/{len(product_urls)}: {url}")
            product_html = scrape_product_details(url)

            if product_html:
                product_data = parse_content(product_html)

                # category/landing pages have no 'pdp-heading', so parse_content
                # returns no name for them — that is how we skip non-products
                if product_data.get('Name') == "Product Name Not Found":
                    print("    (not a product page, skipping)")
                    continue

                product_data['Source_URL'] = url
                extracted_data.append(product_data)

            # small pause between requests, out of politeness to the server
            time.sleep(0.5)

    else:
        print(" No products were scraped. Check if the website structure or the initial fetching was correct.")

    if extracted_data:
        print(f"Successfully scraped data for {len(extracted_data)} products.")

        filename = 'cerave_products.json'
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, ensure_ascii=False, indent=4)
            print(f"Data saved successfully to **{filename}**.")
        except Exception as e:
            print(f"ERROR: Could not save data to JSON. Details: {e}")
    else:
        print("No data available to save.")

    print("=" * 60)
    print("\nScript finished.")