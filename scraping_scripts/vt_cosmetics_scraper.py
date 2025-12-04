import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import re
import json
from typing import List

BASE_URL = "https://globalvt-cosmetics.com"
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

def extract_product_links(html_content: str | None) -> List[str]:
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    product_links: List[str] = [] #Using Type Hinting
    
    EXCLUSION_KEYWORDS = ["bundle", "kit", "collection"]
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

if __name__ == "__main__":
    html_source = fetch_page(NEW_URL)
    
    if html_source:
        all_product_urls = extract_product_links(html_source)
        if all_product_urls:
            print("\n Example of Extracted Links:")
            for url in all_product_urls:
                print(f" - {url}")
        else:
            print("\nNo product links were extracted. Check the HTML structure.")    