import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

YC_BASE_URL = "https://www.ycombinator.com"
ua = UserAgent()


def find_best_website_from_yc_page(detail_soup, company_name, yc_slug):
    excluded_domains = [
        'ycombinator.com', 'startupschool.org', 'linkedin.com',
        'twitter.com', 'facebook.com', 'instagram.com'
    ]
    name_norm = re.sub(r'[^a-zA-Z0-9]', '', company_name).lower()
    slug_norm = re.sub(r'[^a-zA-Z0-9]', '', yc_slug).lower()
    for a in detail_soup.find_all('a', href=True):
        href = a['href']
        if any(domain in href for domain in excluded_domains):
            continue
        href_norm = re.sub(r'[^a-zA-Z0-9]', '', href).lower()
        if name_norm in href_norm or slug_norm in href_norm:
            if href.startswith('http'):
                return href
            elif href.startswith('www.'):
                return 'https://' + href
    return None


def extract_real_url(raw_url):
    if not raw_url:
        return None
    if '/r/goto?' in raw_url:
        try:
            from urllib.parse import urlparse, parse_qs
            if raw_url.startswith('/'):
                raw_url = 'https://www.ycombinator.com' + raw_url
            parsed = urlparse(raw_url)
            if parsed.query:
                query_params = parse_qs(parsed.query)
                if 'url' in query_params:
                    target_url = query_params['url'][0]
                    if target_url.startswith(('http://', 'https://')):
                        return target_url
        except Exception:
            return None
    elif raw_url.startswith(('http://', 'https://')):
        excluded_domains = [
            'ycombinator.com', 'startupschool.org', 'linkedin.com',
            'twitter.com', 'facebook.com', 'instagram.com'
        ]
        if not any(domain in raw_url for domain in excluded_domains):
            return raw_url
    elif '.' in raw_url and not raw_url.startswith('/'):
        return 'https://' + raw_url
    return None


def get_company_details(name, yc_link):
    headers = {"User-Agent": ua.random}
    try:
        detail_resp = requests.get(yc_link, headers=headers, timeout=10)
        detail_soup = BeautifulSoup(detail_resp.text, "lxml")
        website = None
        website_tag = detail_soup.find('a', string="Website")
        if website_tag and website_tag.get('href'):
            website = extract_real_url(website_tag.get('href'))
            excluded_domains = [
                'ycombinator.com', 'startupschool.org', 'linkedin.com',
                'twitter.com', 'facebook.com', 'instagram.com'
            ]
            if website and any(domain in website for domain in excluded_domains):
                website = None
        if not website:
            yc_slug = yc_link.rstrip('/').split('/')[-1]
            website = find_best_website_from_yc_page(detail_soup, name, yc_slug)
            if website:
                print(f"Fallback website found for {name}: {website}")
            else:
                print(f"No website found for {name} on YC page.")
        linkedin_url = None
        linkedin_tag = detail_soup.find('a', href=lambda x: x and 'linkedin.com/company' in x)
        if linkedin_tag:
            linkedin_url = linkedin_tag.get('href')
        return website, linkedin_url
    except Exception as e:
        print(f"Error fetching details for {name}: {e}")
        return None, None


def get_linkedin_description(linkedin_url):
    if not linkedin_url:
        return None, False
    headers = {"User-Agent": ua.random}
    try:
        resp = requests.get(linkedin_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None, False
        soup = BeautifulSoup(resp.text, "lxml")
        desc_tag = soup.find('meta', {'name': 'description'})
        desc = desc_tag['content'] if desc_tag else ''
        has_yc_s25 = 'YC S25' in desc or 'YCS25' in desc
        return desc, has_yc_s25
    except Exception:
        return None, False


def process_single_company(card, csv_filename, company_count):
    name_tag = card.find('span', class_=lambda x: x and '_coName_' in x)
    name = name_tag.text.strip() if name_tag else None
    if not name:
        return False
    print(f"Processing company {company_count}: {name}")
    desc_tag = card.find('div', class_=lambda x: x and 'text-sm' in x)
    description = desc_tag.text.strip() if desc_tag else None
    batch_tag = None
    for span in card.find_all('span', class_=lambda x: x and 'pill' in x):
        if any(batch in span.text for batch in ['Summer 2025', 'Spring 2025', 'Winter 2025']):
            batch_tag = span.text.strip()
            break
    if not batch_tag:
        print(f"Skipping {name} - no valid batch tag")
        return False
    yc_link = YC_BASE_URL + card.get('href')
    website, linkedin_url = get_company_details(name, yc_link)
    linkedin_description = None
    yc_s25_on_linkedin = False
    if linkedin_url:
        print(f"Getting LinkedIn data: {name}")
        linkedin_description, yc_s25_on_linkedin = get_linkedin_description(linkedin_url)
    company_data = {
        'name': name,
        'website': website,
        'description': description,
        'yc_link': yc_link,
        'linkedin_url': linkedin_url,
        'linkedin_description': linkedin_description,
        'yc_s25_on_linkedin': yc_s25_on_linkedin,
        'batch': batch_tag
    }
    append_to_csv(company_data, csv_filename)
    time.sleep(2)
    return True


def append_to_csv(company_data, filename):
    df = pd.DataFrame([company_data])
    file_exists = os.path.isfile(filename)
    df.to_csv(filename, mode='a', header=not file_exists, index=False)
    print(f"Saved to CSV: {company_data['name']}")


def get_available_driver():
    driver = None
    # Try Firefox first
    try:
        print("Attempting to use Firefox...")
        firefox_options = FirefoxOptions()
        firefox_options.headless = True
        firefox_options.add_argument('--width=1920')
        firefox_options.add_argument('--height=1080')
        service = FirefoxService(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=firefox_options)
        print("Firefox driver initialized successfully")
        return driver, "Firefox"
    except Exception as e:
        print(f"Firefox not available: {e}")
        # Try Chrome as backup
        try:
            print("Attempting to use Chrome...")
            chrome_options = ChromeOptions()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Chrome driver initialized successfully")
            return driver, "Chrome"
        except Exception as e:
            print(f"Chrome not available: {e}")
            raise Exception("No compatible browser found! Please install Firefox or Chrome.")


def get_yc_s25_companies():
    csv_filename = "yc_s25_companies.csv"
    if os.path.exists(csv_filename):
        os.remove(csv_filename)
        print(f"Cleared existing {csv_filename}")
    url = "https://www.ycombinator.com/companies?batch=Summer%202025"
    driver, browser_name = get_available_driver()
    print(f"Using {browser_name} browser for scraping")
    try:
        driver.get(url)
        print("Page loaded, waiting for companies to appear...")
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[class*="_company_"]')))
        time.sleep(3)
        print("Scrolling to load all companies...")
        previous_count = 0
        max_attempts = 20
        attempt = 0
        while attempt < max_attempts:
            current_cards = driver.find_elements(By.CSS_SELECTOR, 'a[class*="_company_"]')
            current_count = len(current_cards)
            print(f"Found {current_count} companies (attempt {attempt + 1})")
            if current_count == previous_count:
                if attempt >= 3:
                    print("No more companies loading, finishing...")
                    break
            else:
                attempt = 0
                previous_count = current_count
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
            time.sleep(2)
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(3)
            attempt += 1
        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")
        cards = soup.find_all('a', class_=lambda x: x and '_company_' in x)
        cards = [card for card in cards if card.get('href')]
        unique_cards = {}
        for card in cards:
            href = card.get('href')
            if href not in unique_cards:
                unique_cards[href] = card
        cards = list(unique_cards.values())
        print(f"Found {len(cards)} unique company cards to process")
        processed_count = 0
        for i, card in enumerate(cards, 1):
            if process_single_company(card, csv_filename, i):
                processed_count += 1
                print(f"Progress: {processed_count}/{len(cards)} companies processed")
            if processed_count > 0 and processed_count % 10 == 0:
                print(f"Processed {processed_count} companies so far!")
                print("You can stop the script anytime and check the CSV file.")
        print(f"Completed! Processed {processed_count} companies total.")
        return processed_count
    finally:
        driver.quit()


def main():
    print("Starting YC S25 companies scraper...")
    print("Companies will be saved to CSV as they're processed.")
    print("You can stop the script anytime and check yc_s25_companies.csv and run the streamlit app\n")
    try:
        processed_count = get_yc_s25_companies()
        print(f"Scraping completed! {processed_count} companies saved to yc_s25_companies.csv")
    except KeyboardInterrupt:
        print("Scraping interrupted by user. Check yc_s25_companies.csv for partial results.")
    except Exception as e:
        print(f"Error occurred: {e}")
        print("Check yc_s25_companies.csv for any partial results.")


if __name__ == "__main__":
    main()