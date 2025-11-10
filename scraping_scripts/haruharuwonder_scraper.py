import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup

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

def parse_content(html_content: str, url: str) -> dict:
    """Parses the HTML and extracts the product data."""

    if not html_content:
        return

    soup = BeautifulSoup(html_content, 'html.parser')
    product_data = {'URL': url}

    # Extracting the Product Name
    try:
        name_tag = soup.find('h1', class_='product__title')
        if name_tag:
            product_data['Name'] = name_tag.text.strip()
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
                product_data['Price'] = price_span.text.strip()
            else:
                product_data['Price'] = "Product Price Not Found"
        else:
            product_data['Price'] = "Price Not Found (Main Div)"
    except Exception:
        product_data['Price'] = "Price Not Found"

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
        else:
            print("[FAIL] Could not fetch product HTML.")

    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {len(final_products_data)} Products Successfully Parsed")
    print("=" * 60)

    print("Script finished.")