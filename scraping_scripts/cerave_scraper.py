import requests
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import json

CATEGORY_URL = "https://www.cerave.com/skincare" 
BASE_URL = "https://www.cerave.com"

def scrape_all_products_with_selenium(url):
    #print("Starting Selenium Scraper...")
    print(f"Opening URL: {url}")
    
    service = Service() 
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)

        while True:
            try:
                load_more_button = wait.until(
                    EC.element_to_be_clickable((By.CLASS_NAME, 'load-more-results__cta-btn'))
                )
                
                #print("   -> Found 'View 12 More' button. Clicking...")
                driver.execute_script("arguments[0].click();", load_more_button)
                time.sleep(3) 
                
            except Exception:
                #print("   -> 'View 12 More' button not found or disappeared. All products loaded.")
                break

        final_html = driver.page_source
        return final_html
        
    except Exception as e:
        print(f"AN ERROR OCCURRED during Selenium process: {e}")
        return None
        
    finally:
        if 'driver' in locals() and driver:
            driver.quit()

def extract_product_links(html_content):
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    product_links = []
    
    link_tags = soup.find_all('a', class_='results__card-front') 
    
    for tag in link_tags:
        relative_link = tag.get('href')
        
        if relative_link:
            if relative_link.startswith('/'):
                full_url = BASE_URL + relative_link
            else:
                full_url = relative_link
                
            product_links.append(full_url)

    return list(set(product_links))

def clean_text(text):
    """Removes excess whitespace, newlines, and replaces them with a single space."""
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', text)
    return cleaned.strip()

def scrape_product_details(url):
    """Fetches the HTML content for a single product URL using requests."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 
        return response.text
    except requests.RequestException as e:
        print(f"ERROR: Could not fetch URL {url}: {e}")
        return None

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
    
    category_html = scrape_all_products_with_selenium(CATEGORY_URL)
    product_urls = [] 

    if category_html:
        product_urls = extract_product_links(category_html)
        
        print("\n" + "=" * 60)
        print(f"FINAL RESULT: {len(product_urls)} Products to be Processed")
        print("=" * 60)
        
        extracted_data = []
        
        if product_urls:
            for i, url in enumerate(product_urls):
                #print(f" -> Processing Product {i+1}/{len(product_urls)}: {url}")
                product_html = scrape_product_details(url) 
                
                if product_html:
                    product_data = parse_content(product_html)
                    extracted_data.append(product_data)
                    product_data['Source_URL'] = url    
                    #print(f" Name: {product_data.get('Name')}")
                    #print(f" Product Type: {product_data.get('Product Type')}")
                    #print(f" Price: {product_data.get('Price')}")
                    #print(f" Ingredients: {product_data.get('Ingredients')}")
                    #print(f" Description: {product_data.get('Description')}")
                    
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