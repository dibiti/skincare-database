import time
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

def extract_product_links(html_content: str) -> list[str]:
    if not html_content:
        return []

    #print(" Starting data extraction ...")
    soup = BeautifulSoup(html_content, 'html.parser')
    product_links = []
    
    EXCLUSION_KEYWORDS = ["bunble", "kit", "collection"]

    link_tags = soup.find_all('a', class_='product-card__link') 
    
    print(f"   -> Found {len(link_tags)} potential link tags.")
    
    for tag in link_tags:
        relative_link = tag.get('href')

        #print(f" CHECKING LINK: {relative_link}")
        
        if relative_link and relative_link.startswith('/products/'): 

            clean_link = relative_link.split('?')[0]
            
            lower_link = clean_link.lower()
            should_exclude = any(keyword in lower_link for keyword in EXCLUSION_KEYWORDS)
            
            if should_exclude: 
                print(f"   -> SKIPPING (Excluded): {relative_link}")
                continue
                
            full_url = BASE_URL + relative_link
            
            product_links.append(full_url)
            
    unique_links = list(set(product_links))
    return unique_links

if __name__ == "__main__":
    raw_html = fetch_page(NEW_URL)
    
    extracted_links = []
    
    if raw_html:
        extracted_links = extract_product_links(raw_html)
    else:
        print(" Skipping extraction because no HTML content was fetched.")

    print("\n" + "=" * 50)
    print(f"FINAL RESULT: {len(extracted_links)} Unique Product Links Extracted:")
    print("=" * 50)

    for link in extracted_links:
        print(f"-> {link}")

    print("=" * 50)