# ordinary_scraper.py

import requests
from bs4 import BeautifulSoup
import re
import time

# The target URL is now the category listing page
CATEGORY_URL = "https://theordinary.com/en-ch/category/skincare#product-search-results" 
# Base URL for constructing full links
BASE_URL = "https://theordinary.com"

# --- 2. Helper Functions: Fetching and Cleaning ---
def fetch_page(url):
    """Fetches the HTML content of the target URL."""
    print(f"-> Fetching URL: {url}")
    try:
        # Headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Wait a moment before requesting
        time.sleep(1) 
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Check for HTTP errors (4xx or 5xx)
        return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not fetch the page. Details: {e}")
        return None

def clean_text(text):
    """Removes excess whitespace, newlines, and replaces them with a single space."""
    if not text:
        return ""
    # 1. Replace all newlines and multiple spaces with a single space
    cleaned = re.sub(r'\s+', ' ', text)
    # 2. Strip leading/trailing spaces again just to be safe
    return cleaned.strip()

def extract_product_links(html_content):
    """
    Parses the category HTML and extracts the full URLs for individual products.
    The selector looks for: <a class="link product-link" href="...>
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    product_links = []
    
    # Find all <a> tags with the specific class for product links
    link_tags = soup.find_all('a', class_='link product-link') 
    
    for tag in link_tags:
        # Get the relative link from the 'href' attribute
        relative_link = tag.get('href')
        
        if relative_link:
            # Construct the full URL using the BASE_URL
            full_url = BASE_URL + relative_link
            product_links.append(full_url)
            
    # Use set() to ensure no duplicate links and convert back to list
    return list(set(product_links))


# --- 3. Parse and Extract Data ---
def parse_content(html_content):
    """Parses the HTML and extracts the product data."""
    if not html_content:
        return

    soup = BeautifulSoup(html_content, 'html.parser')
    product_data = {}

    # 1. Extracting the Product Name (Name)
    try:
        name_tag = soup.find('h1', class_='product-name')
        product_data['Name'] = name_tag.text.strip()
    except Exception as e:
        product_data['Name'] = "Name Not Found"
        print(f"Warning: Could not find product name. {e}")

    # 2. Extracting the Price (Price)
    try:
        price_tag = soup.find('span', class_='value')
        product_data['Price'] = price_tag.text.strip()
    except Exception as e:
        product_data['Price'] = "Price Not Found"
        print(f"Warning: Could not find product price. {e}")
    
    
    # 3. Extracting the Target
    try:
        target_tag = soup.find('p', class_='skin-concern panel-item')
        target = target_tag.text
        product_data['Target'] = clean_text(target) 
    except Exception as e:
        product_data['Target'] = "Target Not Found"
        print(f"Warning: Could not find product name. {e}")

    
    # 4. Extracting the Skin Type
    try:
        skintype_tag = soup.find('p', class_='suitedTo panel-item')
        skintype = skintype_tag.text
        product_data['Skin Type'] = clean_text(skintype) 
    except Exception as e:
        product_data['Skin Type'] = "Skin Type Not Found"
        print(f"Warning: Could not find product name. {e}")

    
    # 4. Extracting the Ingredients
    try:
        ingredients_tag = soup.find('p', class_='ingredients-flyout-content')
        ingredients = ingredients_tag.text
        product_data['Ingredients'] = clean_text(ingredients) 
    except Exception:
        product_data['Ingredients'] = "Ingredients Not Found"
        print(f"Warning: Could not find product name. {e}")
        
    return product_data

# --- 5. Main Execution Loop ---
if __name__ == "__main__":
    
    # 1. Fetch the CATEGORY Page to get the list of products
    category_html = fetch_page(CATEGORY_URL)
    
    all_product_data = [] # List to store all scraped results

    if category_html:
        # 2. Extract all individual product URLs from the category page
        product_urls = extract_product_links(category_html)
        
        print(f"\n--- Starting Scrape ---")
        print(f"-> Found {len(product_urls)} unique products to scrape.")
        
        # 3. Loop through each product URL and scrape the details
        for i, url in enumerate(product_urls):
            print(f"\n--- SCRAPING PRODUCT {i+1} of {len(product_urls)} ---")
            
            # 4. Fetch the individual product page
            product_html = fetch_page(url)
            
            # 5. Parse and extract data
            if product_html:
                results = parse_content(product_html)
                
                # Add the URL to the results for tracking
                results['Source_URL'] = url
                all_product_data.append(results)
                
                # Print results for immediate feedback
                print(f"  Name: {results.get('Name')}")
                print(f"  Price: {results.get('Price')}")
                print(f"  Target: {results.get('Target')}")
                print(f"  Suited to: {results.get('Skin Type')}")
                print(f"  Ingredients: {results.get('Ingredients')[:50]}...") # Print a snippet
                
    
    # 6. Final summary and output
    print("\n--- FINAL SUMMARY ---")
    
    if all_product_data:
        print(f"Successfully scraped data for {len(all_product_data)} products.")
        
        # OPTIONAL: Save the results to a JSON file (recommended for larger scrapes)
        # with open('ordinary_products.json', 'w', encoding='utf-8') as f:
        #     json.dump(all_product_data, f, ensure_ascii=False, indent=4)
        # print("Data saved to ordinary_products.json")
    else:
        print("No products were scraped. Check if the CATEGORY_URL is correct.")
        
    print("\nScript finished.")