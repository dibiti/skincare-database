import requests
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

if __name__ == "__main__":
    
    category_html = scrape_all_products_with_selenium(CATEGORY_URL)
    
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