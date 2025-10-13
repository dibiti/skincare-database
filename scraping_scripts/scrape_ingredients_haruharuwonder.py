import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException

def save_to_csv(data, filename="ingredientes_haruharu.csv"):
    if not data:
        print("No data to save.")
        return

    # define the fields/columns based on the dictionary keys
    fieldnames = ['Name', 'Category/Benefit', 'Source', 'Description']

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=',')
            
            writer.writeheader() # write header row
            writer.writerows(data) # write data
        
        print(f"\n Data successfully saved to {filename}")
        
    except IOError as e:
        print(f"Error writing to CSV file: {e}")


def extract_and_save_ingredients(url):

    chrome_options = Options()
    chrome_options.add_argument("--headless")     # not opening the chrome page
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = None 
    results = [] # list to store all extracted dictionaries
    
    try:
        #print("Launching Chrome (Headless mode)")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        time.sleep(5) 
        page_source = driver.page_source
        
        driver.quit()
        driver = None
        #print("page loaded successfully and browser closed")

        soup = BeautifulSoup(page_source, 'html.parser')

        # find all ingredient blocks
        ingredient_blocks = soup.find_all(
            'div',
            class_=lambda c: c and 'tw-relative' in c and 'cb' in c
        )

        print(f" Found {len(ingredient_blocks)} ingredient blocks to process")

        for block in ingredient_blocks:
            
            # extract the Name
            name_tag = block.find(
                'div',
                class_='tw-font-light tw-capitalize',
                style='font-size: 1.2rem;'
            )
            name = name_tag.text.strip() if name_tag else "NAME NOT FOUND"

            # extract the Description
            description_tag = block.find('div', class_='tw-mt-4 sm:tw-mt-0')
            description = description_tag.text.strip() if description_tag else "DESCRIPTION NOT FOUND"
            
            # extract the Category/Benefit
            category_tag = block.find(
                'div',
                class_='tw-font-bold tw-capitalize',
                style='font-size: 1.2rem;'
            )
            category = category_tag.text.strip() if category_tag else "CATEGORY NOT FOUND"

            # extract the Source
            source = "SOURCE NOT FOUND"
            source_container = block.find('div', class_='tw-flex tw-mt-4 sm:tw-mt-0 sm:tw-flex-col tw-gap-2')
            if source_container:
                active_source_tag = source_container.find('div', class_=lambda c: c and 'tw-text-black' in c)
                if active_source_tag:
                    source = active_source_tag.text.strip()
          
            results.append({
                "Name": name,
                "Category/Benefit": category,
                "Source": source,
                "Description": description,
            })
            
        save_to_csv(results)

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

URL_SITE = "https://haruharuwonder.com/pages/ingredients"

extract_and_save_ingredients(URL_SITE)