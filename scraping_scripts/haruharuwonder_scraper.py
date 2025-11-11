import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import re

BASE_URL = "https://haruharuwonder.com"
NEW_URL = BASE_URL + "/collections/all"

def fetch_page(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")      # Keep headless mode for a fast and discreet connection
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    driver = None 
    html_content = None
    
    print(f"Initializing Chrome Driver to access: {url}")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        print("Waiting for the page to fully load ...")
        time.sleep(7) 
        
        page_title = driver.title
        html_content = driver.page_source

        print("-" * 50)
        print(f"Connection successful!")
        print("-" * 50)

    except WebDriverException as e:
        print("-" * 70)
        print(" WEB DRIVER ERROR ")
        print("Error initializing or controlling the Chrome Driver.")
        print(f"Error details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if driver:
            driver.quit()

    return html_content

def fetch_static_html(url: str) -> str | None:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5) 
        response.raise_for_status() 
        return response.text
    except requests.exceptions.RequestException as e:
        # print(f"Failed to fetch static content for {url}. Details: {e}")
        return None

def extract_product_links(html_content: str) -> list[str]:
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    product_links = []
    
    EXCLUSION_KEYWORDS = ["bundle", "kit", "collection"]

    link_tags = soup.find_all('a', class_='product-card__link') 
    
    for tag in link_tags:
        relative_link = tag.get('href')
        
        if relative_link and relative_link.startswith('/products/'): 

            clean_link = relative_link.split('?')[0]
            lower_link = clean_link.lower()
            should_exclude = any(keyword in lower_link for keyword in EXCLUSION_KEYWORDS)
            
            if should_exclude: 
                #print(f"   -> SKIPPING (Excluded): {relative_link}")
                continue
                
            full_url = BASE_URL + relative_link
            product_links.append(full_url)
            
    return list(set(product_links))

def clean_text(text):
    """Removes excess whitespace, newlines, and replaces them with a single space."""
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', text)
    return cleaned.strip()


def parse_content(html_content: str, url: str) -> dict:
    """Parses the HTML and extracts the product data."""

    if not html_content:
        return

    soup = BeautifulSoup(html_content, 'html.parser')
    product_data = {'URL': url}

    # Extracting the Product Name
    product_prefix = ""
    try:
        prefix_tag = soup.find('p', class_='product__text--link')
        if prefix_tag:
            product_prefix = clean_text(prefix_tag.text)
            if product_prefix:
                product_prefix += " "
                
    except Exception as e:
        print(f"Error extracting Product Prefix: {e}")

    try:
        name_tag = soup.find('h1', class_='product__title')
        if name_tag:
            main_name = clean_text(name_tag.text)
            product_data['Name'] = product_prefix + main_name
        else:
            product_data['Name'] = "Name Not Found"
            
    except Exception as e:
        product_data['Name'] = f"Error extracting Name: {e}"
    
    # Extracting the Price
    try:
        price_tag = soup.find('div', class_='price__regular')
        if price_tag:
            all_spans = price_tag.find_all('span')
            price_span = all_spans[-1]
            if price_span:
                product_data['Price'] = clean_text(price_span.text)
            else:
                product_data['Price'] = "Product Price Not Found"
        else:
            product_data['Price'] = "Price Not Found (Main Div)"
    except Exception:
        product_data['Price'] = "Price Not Found"

    # Extracting the Available Sizes
    try:
        size_swatches = soup.find_all('label', class_='product__swatch')
        available_sizes = []

        for swatch in size_swatches:
            size = swatch.get('title') 
        
            if not size:
                span_tag = swatch.find('span')
                if span_tag:
                    size = span_tag.text.strip()
        
            if size:
                available_sizes.append(size)
            
            if available_sizes:
                product_data['Sizes'] =", ".join(sorted(list(set(available_sizes))))
            else:
                product_data['Sizes'] = "Single Size / Not Found"

    except Exception as e:
        product_data['Sizes'] = f"Error extracting Sizes: {e}"

    try:
        ingredients_tag = soup.find('span', class_='metafield-multi_line_text_field')
        
        if ingredients_tag:
            ingredients_list = clean_text(ingredients_tag.text)
            product_data['Ingredients'] = ingredients_list
        else:
            product_data['Ingredients'] = "Ingredients Not Found"
            
    except Exception as e:
        product_data['Ingredients'] = f"Error extracting Ingredients: {e}"

    return product_data

if __name__ == "__main__":
    all_extracted_links = set()  
    page_num = 1
    
    while True:
        current_url = f"{NEW_URL}?page={page_num}"
        print(f"\n Scraping PAGE {page_num}: {current_url}")

        raw_html = fetch_page(current_url)

        if raw_html:
            new_links = extract_product_links(raw_html)
            if not new_links:
                print(f"!!! Page {page_num} returned 0 new links. Assuming END OF COLLECTION.")
                break 

            initial_count = len(all_extracted_links)
            all_extracted_links.update(new_links)
            added_count = len(all_extracted_links) - initial_count

            page_num += 1
            
        else:
            print("!!! Failed to fetch HTML content. Stopping the process.")
            break
            
    final_products_data = []

    sorted_urls = sorted(list(all_extracted_links)) 
    
    for i, url in enumerate(sorted_urls):
        print(f"[{i + 1}/{len(sorted_urls)}] Processing: {url}")
        
        product_html = fetch_static_html(url) 
        
        if product_html:
            product_details = parse_content(product_html, url)
            final_products_data.append(product_details)
            print(f" Name: {product_details.get('Name')}")
            print(f" Price: {product_details.get('Price')}")
            print(f" Sizes: {product_details.get('Sizes')}")
            print(f" Ingredients: {product_details.get('Ingredients')}")

        else:
            print("[FAIL] Could not fetch product HTML.")

    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {len(final_products_data)} Products Successfully Parsed")
    print("=" * 60)

    print("Script finished.")