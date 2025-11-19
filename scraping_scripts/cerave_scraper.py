import requests
from bs4 import BeautifulSoup
import time
import re

CATEGORY_URL = "https://www.cerave.com/skincare" 
BASE_URL = "https://www.cerave.com"

def fetch_page(url):
    print(f" Fetching URL: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        time.sleep(2) 
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Check for HTTP errors (4xx or 5xx)
        return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not fetch the page. Details: {e}")
        return None

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

if __name__ == "__main__":
    
    category_html = fetch_page(CATEGORY_URL)
    
    product_urls = [] 

    if category_html:
        product_urls = extract_product_links(category_html)
        
        print("\n" + "=" * 60)
        print(f"FINAL RESULT: {len(product_urls)} Products Successfully Parsed")
        print("=" * 60)
        
        if product_urls:
            print("Sample of extracted links:")
            for i, url in enumerate(product_urls):
                print(f"   {i+1}. {url}")
    else:
        print(" No products were scraped. Check if the website structure or the initial fetching was correct.")
        
    print("=" * 60)
    print("\nScript finished.")