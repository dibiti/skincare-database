import requests
from bs4 import BeautifulSoup
import re
import time
import json

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By 
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# The target URL is now the category listing page
CATEGORY_URL = "https://theordinary.com/en-ch/category/skincare#product-search-results" 
# Base URL for constructing full links
BASE_URL = "https://theordinary.com"

def fetch_page(url):
    """Fetches the HTML content of the target URL."""
    print(f"-> Fetching URL: {url}")
    try:
        # Headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Wait a moment before requesting
        time.sleep(0.5) 
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Check for HTTP errors (4xx or 5xx)
        return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not fetch the page. Details: {e}")
        return None

def fetch_page_with_js(url):
    """Fetches the HTML content of the target URL after JavaScript execution (Fallback)."""
    print(f"-> Fetching URL (JS mode): {url}")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run the browser in the background
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        driver.get(url)
        
        time.sleep(2) # Simple wait (2 seconds) to ensure all JS is executed
        
        html_content = driver.page_source
        print("-> JS Page content successfully loaded.")
        return html_content
    
    except TimeoutException:
        print(f"ERROR: Selenium timed out loading the page.")
        return None
    except Exception as e:
        print(f"ERROR: Could not fetch the page with JS. Details: {e}")
        return None
    finally:
        if driver:
            driver.quit() # Important to always close the browser instance

def get_full_category_html_with_js(url):
    """
    Usa Selenium para carregar a página de categoria e clica em 'Load More' 
    até que todos os produtos sejam exibidos.
    """
    print(f"\n--- Loading Full Category (JS) ---")
    print(f"-> Initiating Selenium on: {url}")
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        driver.get(url)

        # Esperar que o primeiro botão Load More apareça (após o carregamento inicial de 12 produtos)
        wait = WebDriverWait(driver, 15)
        
        while True:
            try:
                # Localizar o botão "Load More"
                # Usando o seletor 'button.btn-load.more' que é o mais específico
                load_more_button = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'button.btn-load.more'))
                )

                if load_more_button.is_displayed() and load_more_button.is_enabled():
                    print("-> Clicking 'Load More'...")
                    driver.execute_script("arguments[0].click();", load_more_button)
                    
                    # Aguardar um pouco para que os novos produtos e o botão Load More reapareçam
                    # 1.5s é um bom balanço entre velocidade e estabilidade
                    time.sleep(1.5) 
                else:
                    print("-> 'Load More' button not visible or enabled. All products loaded.")
                    break # Sai do loop se não estiver visível
                    
            except TimeoutException:
                print("-> Timeout: 'Load More' button not found after waiting. Assuming all products loaded.")
                break # Sai do loop se o botão não aparecer mais
            except NoSuchElementException:
                print("-> 'Load More' element not present. Assuming all products loaded.")
                break
            except ElementClickInterceptedException:
                print("-> Click intercepted, scrolling to button.")
                # Tentar rolar para o elemento e clicar novamente (útil para banners/popups)
                driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(0.5)
                try:
                    load_more_button.click()
                    time.sleep(1.5)
                except:
                    print("-> Failed to click after scroll. Exiting loop.")
                    break


        print("-> Full category page content successfully loaded.")
        return driver.page_source
        
    except Exception as e:
        print(f"ERROR: Failed to load full category page. Details: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def clean_text(text):
    """Removes excess whitespace, newlines, and replaces them with a single space."""
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', text)
    return cleaned.strip()

def extract_product_links(html_content):
    """
    Parses the category HTML and extracts the full URLs for individual products.
    The selector looks for: <a class="link product-link" href="...> and ignore links with the word "set"
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    product_links = []
    
    EXCLUSION_KEYWORDS = ["set", "collection"]

    # Find all <a> tags with the specific class for product links
    link_tags = soup.find_all('a', class_='link product-link') 
    
    for tag in link_tags:
        relative_link = tag.get('href')
        if relative_link:
            lower_link = relative_link.lower() # To ensure that it works
            should_exclude = any(keyword in lower_link for keyword in EXCLUSION_KEYWORDS)
            if should_exclude: 
                print(f"-> Skipping set/collection link: {relative_link}")
                continue
            full_url = BASE_URL + relative_link
            product_links.append(full_url)
            
    return list(set(product_links))


def parse_content(html_content):
    """Parses the HTML and extracts the product data."""
    if not html_content:
        return

    soup = BeautifulSoup(html_content, 'html.parser')
    product_data = {}

    # Extracting the Product Name (Name)
    try:
        name_tag = soup.find('h1', class_='product-name')
        full_text = name_tag.text.strip()
        span_tag = name_tag.find('span', class_='sr-only')
        if span_tag:
            span_text = span_tag.text.strip()
            product_data['Name'] = full_text.replace(span_text, '', 1).strip()
        else:
            product_data['Name'] = full_text
    except Exception as e:
        product_data['Name'] = "Name Not Found"
        print(f"Warning: Could not find product name. {e}")

    # Extracting the Product Type 
    try:
        format_tag = soup.find('p', class_='format panel-item')
    
        if format_tag:
            full_text = format_tag.text.strip()
            span_title_tag = format_tag.find('span', class_='title')
        
            if span_title_tag:
                title_text = span_title_tag.text.strip()

                format_value = full_text.replace(title_text, '', 1).strip()
            else:
                format_value = full_text.replace('Format', '', 1).strip()
            
            product_data['Product Type'] = clean_text(format_value)
        else:
            product_data['Product Type'] = "Product Type Not Found"
            
    except Exception as e:
        product_data['Product Type'] = "Product Type Not Found"
        print(f"Warning: Could not find product type. Details: {e}")

    # Extracting the Price 
    try:
        price_tag = soup.find('span', class_='value')
        product_data['Price'] = price_tag.text.strip()
    except Exception as e:
        product_data['Price'] = "Price Not Found"
        print(f"Warning: Could not find product price. {e}")
    
    # Extracting the Available Sizes (ml)
    try:
        size_tags = soup.find_all('span', class_='size-value')
        raw_sizes = [tag.text.strip() for tag in size_tags if tag.text.strip()]
        available_sizes = list(set(raw_sizes))
        
        if available_sizes:
            product_data['Size (ml)'] = ", ".join(sorted(available_sizes))
        else:
            product_data['Size (ml)'] = "Size Not Found"
            
    except Exception as e:
        product_data['Size (ml)'] = "Size Not Found"
        print(f"Warning: Could not find product size options. Details: {e}")
    
    # Extracting the Product Description
    try:
        description_div = soup.find('div', class_='overview-description-substring')
        
        if description_div:
            raw_description = description_div.get_text(separator=' ', strip=True)
            product_data['Description'] = clean_text(raw_description)
        else:
            product_data['Description'] = "Description Not Found"
            
    except Exception as e:
        product_data['Description'] = "Description Not Found"
        print(f"Warning: Could not find product description. Details: {e}")

    # Extracting the Target
    try:
        target_tag = soup.find('p', class_='skin-concern panel-item')
        if target_tag:
            full_text = target_tag.text.strip()
            span_title_tag = target_tag.find('span', class_='title')
        
            if span_title_tag:
                title_text = span_title_tag.text.strip()
                target = full_text.replace(title_text, '', 1).strip()
            else:
                target = full_text # Pode ser necessário um tratamento manual aqui se for o caso
            product_data['Target'] = clean_text(target) 
        else:
            product_data['Target'] = "Target Not Found"
    except Exception as e:
        product_data['Target'] = "Target Not Found"
        print(f"Warning: Could not find product name. {e}")
    
    # Extracting the Skin Type
    try:
        skintype_tag = soup.find('p', class_='suitedTo panel-item')
        if skintype_tag:
            full_text = skintype_tag.text.strip()
            span_title_tag = skintype_tag.find('span', class_='title')
        
            if span_title_tag:
                title_text = span_title_tag.text.strip()
                skintype = full_text.replace(title_text, '', 1).strip()
            else:
                skintype = full_text
            product_data['Skin Type'] = clean_text(skintype) 
        else:
            product_data['Skin Type'] = "Skin Type Not Found"
    except Exception as e:
        product_data['Skin Type'] = "Skin Type Not Found"
        print(f"Warning: Could not find product name. {e}")

    
    # Extracting the Ingredients
    try:
        ingredients_tag = soup.find('p', class_='ingredients-flyout-content')
        ingredients = ingredients_tag.text
        product_data['Ingredients'] = clean_text(ingredients) 
    except Exception:
        product_data['Ingredients'] = "Ingredients Not Found"
        print(f"Warning: Could not find product name. {e}")
        
    return product_data

# --- Main Execution Loop ---
if __name__ == "__main__":
    
    # Fetch the CATEGORY Page to get the list of products
    category_html = get_full_category_html_with_js(CATEGORY_URL)
    
    all_product_data = [] # List to store all scraped results

    if category_html:
        product_urls = extract_product_links(category_html)
        
        print(f"\n--- Starting Scrape ---")
        print(f"-> Found {len(product_urls)} unique products to scrape.")
        
        for i, url in enumerate(product_urls):
            print(f"\n--- SCRAPING PRODUCT {i+1} of {len(product_urls)} ---")

            product_html = fetch_page(url)
            results = {} 
            
            if product_html:
                results = parse_content(product_html)
                results['Source_URL'] = url
                
                # --- FALLBACK LOGIC: Check Description and Use Selenium if needed, check if Description is empty or failed ---
                is_description_empty = not results.get('Description') or \
                                       results.get('Description') == "" or \
                                       results.get('Description') == "Description Not Found"
                
                if is_description_empty:
                    print("-> Description empty or not found. Activating JS Fallback (Selenium)...")
                    js_html = fetch_page_with_js(url)
                    
                    if js_html:
                        js_soup = BeautifulSoup(js_html, 'html.parser')
                        try:
                            description_div = js_soup.find('div', class_='overview-description-substring')
                            if description_div:
                                raw_description = description_div.text 
                                results['Description'] = clean_text(raw_description)
                            else:
                                results['Description'] = "Description Not Found (JS Fallback Failed)"
                        except Exception:
                            results['Description'] = "Description Error (JS Fallback)"
                            
                    else:
                        print("-> ERROR: Failed to load with Selenium.")
                # --- END OF FALLBACK LOGIC ---

                all_product_data.append(results)
                
                # Print results for immediate feedback
                """print(f"   Name: {results.get('Name')}")
                print(f"   Product Type: {results.get('Product Type')}")
                print(f"   Price: {results.get('Price')}")
                print(f"   Size (ml): {results.get('Size (ml)')}")
                description_snippet = results.get('Description')
                if description_snippet and len(description_snippet) > 180:
                     description_snippet = description_snippet[:180] + "..."
                print(f"   Description: {description_snippet}")
                print(f"   Ingredients: {results.get('Ingredients')[:80]}...") 
                print(f"   Target: {results.get('Target')}")
                print(f"   Suited to: {results.get('Skin Type')}")"""
                
    print("\n--- FINAL SUMMARY ---")
    
    if all_product_data:
        print(f"Successfully scraped data for {len(all_product_data)} products.")
        
        filename = 'ordinary_products_full.json'
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(all_product_data, f, ensure_ascii=False, indent=4)
            print(f"Data saved successfully to **{filename}**.")
        except Exception as e:
            print(f"ERROR: Could not save data to JSON. Details: {e}")
    else:
        print("No products were scraped. Check if the CATEGORY_URL is correct.")
        
    print("\nScript finished.")