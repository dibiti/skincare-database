import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import re
import json

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


if __name__ == "__main__":
    fetch_page(NEW_URL)