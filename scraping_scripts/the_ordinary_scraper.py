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

    # Extracting the Price (Price)
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
                print(f"  Product Type: {results.get('Product Type')}")
                print(f"  Price: {results.get('Price')}")
                print(f"  Size (ml): {results.get('Size (ml)')}")
                print(f"  Description: {results.get('Description')[:80]}...")
                print(f"  Ingredients: {results.get('Ingredients')}") 
                print(f"  Target: {results.get('Target')}")
                print(f"  Suited to: {results.get('Skin Type')}")
                
    
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