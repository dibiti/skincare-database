import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import re
import json
from typing import List, Set

BASE_URL = "https://globalvt-cosmetics.com"
NEW_URL = BASE_URL + "/collections/all"

def fetch_page(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")      # Keep headless mode for a fast and discreet connection
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    driver = None 
    html_content = None
    
    #print(f"Initializing Chrome Driver to access: {url}")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        #print("Waiting for the page to fully load ...")
        time.sleep(7) 
        
        page_title = driver.title
        html_content = driver.page_source

        #print("-" * 50)
        #print(f"Connection successful!")
        #print("-" * 50)

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

def clean_text(text):
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', text)
    return cleaned.strip()

def extract_product_links(html_content: str | None) -> List[str]:
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    product_links: List[str] = [] #Using Type Hinting
    
    EXCLUSION_KEYWORDS = ["bundle", "kit", "collection", "set", "duo"]
    link_tags = soup.find_all('a', class_='prgrid-name-style') 

    for tag in link_tags:
        relative_link = tag.get('href') 
        
        if relative_link and relative_link.startswith('/products/'): 
            clean_link = relative_link.split('?')[0]
            lower_link = clean_link.lower()
            should_exclude = any(keyword in lower_link for keyword in EXCLUSION_KEYWORDS)
            
            if should_exclude: 
                # print(f"   -> SKIPPING (Excluded): {relative_link}")
                continue
                
            full_url = BASE_URL + clean_link
            product_links.append(full_url)
            
    return list(set(product_links))

def parse_content(html_content: str, url: str) -> dict:
    if not html_content:
        return {'Source_URL': url, 'Name': 'HTML Content Missing'}

    soup = BeautifulSoup(html_content, 'html.parser')
    product_data = {'Source_URL': url}

    # Extracting the Product Name
    try:
        name_tag = soup.find('h2', class_='h1')
        
        if name_tag:
            product_data['Name'] = clean_text(name_tag.text)
        else:
            product_data['Name'] = "Name Not Found"
            
    except Exception as e:
        product_data['Name'] = f"Error extracting Name: {e}"

    try:
        modal_container = soup.find('div', id='ingreModal')
        
        if modal_container:
            ingredients_content_div = modal_container.find('div', class_='metafield-rich_text_field')
            
            if ingredients_content_div:
                ingredients_text = ingredients_content_div.get_text(strip=True)
                product_data['Ingredients'] = ingredients_text
            else:
                product_data['Ingredients'] = 'Ingredients Not Found (metafield-rich_text_field missing inside modal)'
        
    except Exception as e:
        product_data['Ingredients'] = f"Error extracting Ingredients: {e}"

    # Extracting the Product Description
    try:
        description_tag = soup.find('div', class_='metafield-rich_text_field')
        
        if description_tag:
            description_list = clean_text(description_tag.text)
            product_data['Description'] = description_list
        else:
            product_data['Description'] = "Description Not Found"
            
    except Exception as e:
        product_data['Description'] = f"Error extracting Description: {e}"

    return product_data

if __name__ == "__main__":
    all_extracted_links: Set[str] = set() 
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
            
            #print(f" -> Found {len(new_links)} links on this page. Added {added_count} unique links.")

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
            print(f" Ingredients: {product_details.get('Ingredients')}")
            print(f" Description: {product_details.get('Description')}")
        else:
            print("[FAIL] Could not fetch product HTML.")

    final_count = len(all_extracted_links)
    print("\n" + "=" * 60)
    print(f"LINK EXTRACTION COMPLETE: Found a total of {final_count} UNIQUE Product URLs.")
    print("=" * 60)
            
    print("\nScript finished.")