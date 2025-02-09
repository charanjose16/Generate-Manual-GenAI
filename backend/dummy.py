import requests
from bs4 import BeautifulSoup
import json
import logging
import os
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://www.regalrexnord.com/products"
FILENAME = "all_products.json"

def load_existing_products(filename):
    """Loads existing products from the JSON file (if it exists)."""
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("Existing JSON file is corrupt. Overwriting with new data.")
            return []
    return []

def scrape_product_categories(url):
    """Scrapes top-level product categories from the given URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, verify=False)  # Disable SSL verification
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        categories = []
        category_tiles = soup.find_all("article", class_="product-tiles__tile")
        if not category_tiles:
            logger.warning("No category tiles found. The website structure might have changed.")
        for tile in category_tiles:
            category_name_tag = tile.find("h3")
            category_link_tag = tile.find("a")
            if not category_name_tag or not category_link_tag:
                logger.warning("Skipping a category due to missing data.")
                continue
            category_name = category_name_tag.get_text(strip=True)
            category_link = category_link_tag.get("href", "")
            full_link = f"https://www.regalrexnord.com{category_link}" if category_link else "N/A"
            categories.append({"name": category_name, "url": full_link})
        return categories
    except Exception as e:
        logger.error(f"Error scraping categories from {url}: {str(e)}")
        return []

def scrape_subcategories(url):
    """Scrapes subcategory links from a given category URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, verify=False)  # Disable SSL verification
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        subcategories = []
        subcategory_links = soup.find_all("a", href=True)
        for link in subcategory_links:
            href = link.get("href", "")
            if "/products/" in href and href.startswith("/") and "product" in href.lower():
                full_link = f"https://www.regalrexnord.com{href}"
                subcategories.append(full_link)
        return list(set(subcategories))  # Remove duplicates
    except Exception as e:
        logger.error(f"Error scraping subcategories from {url}: {str(e)}")
        return []

def scrape_products_from_subcategory(url):
    """Scrapes product details from a subcategory URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, verify=False)  # Disable SSL verification
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        product_tiles = soup.find_all("article", class_="product-tiles__tile")
        for tile in product_tiles:
            product_name_tag = tile.find("h3")
            product_link_tag = tile.find("a")
            if not product_name_tag or not product_link_tag:
                logger.warning("Skipping a product due to missing data.")
                continue
            product_name = product_name_tag.get_text(strip=True)
            product_link = product_link_tag.get("href", "")
            full_link = f"https://www.regalrexnord.com{product_link}" if product_link else "N/A"
            products.append({"name": product_name, "url": full_link})
        return products
    except Exception as e:
        logger.error(f"Error scraping products from subcategory {url}: {str(e)}")
        return []

def scrape_all_products(base_url, max_depth=3):
    """Scrapes all products from subcategories of the given base URL."""
    all_products = []
    visited_urls = set()  # Track visited URLs to avoid duplicates

    def scrape_recursive(url, current_depth):
        if current_depth > max_depth:
            logger.info(f"Reached max depth ({max_depth}). Stopping further scraping.")
            return
        if url in visited_urls:
            logger.info(f"Skipping already visited URL: {url}")
            return
        visited_urls.add(url)  # Mark as visited
        logger.info(f"Processing URL (depth {current_depth}): {url}")
        products = scrape_products_from_subcategory(url)
        all_products.extend(products)
        subcategories = scrape_subcategories(url)
        for subcategory_url in subcategories:
            scrape_recursive(subcategory_url, current_depth + 1)

    # Start scraping from top-level categories
    top_level_categories = scrape_product_categories(base_url)
    for category in top_level_categories:
        logger.info(f"Scraping subcategories for {category['name']} ({category['url']})")
        scrape_recursive(category["url"], current_depth=1)
    return all_products

def save_products_to_json(products, filename=FILENAME):
    """Saves products to a JSON file only if there are new products."""
    existing_products = load_existing_products(filename)
    existing_set = {json.dumps(p, sort_keys=True) for p in existing_products}
    new_set = {json.dumps(p, sort_keys=True) for p in products}
    new_products = new_set - existing_set  # Find new products
    if not new_products:
        logger.info("No new products found. Skipping file update.")
        return
    updated_products = existing_products + [json.loads(p) for p in new_products]
    try:
        with open(filename, "w") as f:
            json.dump(updated_products, f, indent=4)
        logger.info(f"Added {len(new_products)} new products. Updated {filename}.")
    except Exception as e:
        logger.error(f"Failed to save products to JSON: {e}")

def main():
    logger.info("Starting product scraping...")
    all_products = scrape_all_products(BASE_URL)
    if all_products:
        save_products_to_json(all_products)
    else:
        logger.info("No products found.")

if __name__ == "__main__":
    main()