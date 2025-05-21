import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import re
from urllib.parse import urljoin

class DeWaltScraper:
    def __init__(self):
        self.base_url = "https://www.dewalt.it"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.products = []
        self.csv_filename = "dewalt_products2.csv"

    def make_request(self, url):
        """Make a request to the specified URL with retries."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Error accessing {url}: {e}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Failed to access {url} after {max_retries} attempts: {e}")
                    return None

    def parse_product_page(self, url):
        """Extract product details from a product page."""
        response = self.make_request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract product name
        product_name_elem = soup.select_one("h1.coh-heading.title.coh-style-h3---default")
        product_name = product_name_elem.text.strip() if product_name_elem else "N/A"
        
        # Extract product description
        product_description_elem = soup.select_one("div.coh-inline-element.description")
        product_description = product_description_elem.text.strip() if product_description_elem else ""
        
        # Combine product name and description for the full description
        full_description = f"{product_name}\n\n{product_description}"
        
        # Extract product image
        image_elem = soup.select_one("div.coh-container.main-slider-image img")
        image_url = ""
        if image_elem and image_elem.has_attr("src"):
            image_url = urljoin(self.base_url, image_elem["src"])
        
        # Extract product SKU from URL
        sku = "N/A"
        sku_match = re.search(r"/([^/]+)/[^/]+$", url)
        if sku_match:
            sku = sku_match.group(1)
        
        # Extract category from URL
        category = "N/A"
        category_match = re.search(r"dewalt\.it/prodotti/([^/]+)", url)
        if category_match:
            category = category_match.group(1)
        
        return {
            "name": product_name,
            "description": full_description,
            "image_url": image_url,
            "product_url": url,
            "sku": sku,
            "category": category
        }

    def scrape_product_listings(self, url):
        """Scrape product listings from a page and extract links to product pages."""
        print(f"Scraping product listings from: {url}")
        response = self.make_request(url)
        if not response:
            return False

        soup = BeautifulSoup(response.text, "html.parser")
        product_articles = soup.select("article[about]")
        
        if not product_articles:
            print("No products found on this page")
            return False
            
        print(f"Found {len(product_articles)} products on this page")
        
        for article in product_articles:
            product_link_elem = article.select_one("a.coh-link.subtitle.card-link.product-title")
            if product_link_elem and product_link_elem.has_attr("href"):
                product_url = urljoin(self.base_url, product_link_elem["href"])
                
                # Check if we've already scraped this product
                if any(p.get("product_url") == product_url for p in self.products):
                    print(f"Skipping already scraped product: {product_url}")
                    continue
                
                # Extract product data from the product page
                print(f"Scraping product details from: {product_url}")
                product_data = self.parse_product_page(product_url)
                
                if product_data:
                    self.products.append(product_data)
                    print(f"Successfully scraped: {product_data['name']} - {product_data['sku']} - {product_data['category']}")
                
                # Add a small delay to avoid overloading the server
                time.sleep(1)
        
        return True

    def get_next_page_url(self, current_url):
        """Extract the URL for the next page of products."""
        response = self.make_request(current_url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        next_page_elem = soup.select_one("li.pager__item.pager__item--next a")
        
        if next_page_elem and next_page_elem.has_attr("href"):
            next_page_href = next_page_elem["href"]
            # Handle both absolute and relative URLs
            if next_page_href.startswith("http"):
                return next_page_href
            else:
                # If it's a relative URL like "?page=1"
                if "?" in current_url:
                    # Replace existing query parameters
                    base_url = current_url.split("?")[0]
                    return f"{base_url}{next_page_href}"
                else:
                    # Append query parameters
                    return f"{current_url}{next_page_href}"
        
        return None

    def save_to_csv(self):
        """Save scraped product data to a CSV file."""
        if not self.products:
            print("No products to save")
            return
            
        with open(self.csv_filename, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["name", "sku", "description", "image_url", "product_url", "category"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for product in self.products:
                writer.writerow(product)
                
        print(f"Saved {len(self.products)} products to {self.csv_filename}")

    def scrape_url(self, start_url, max_pages=None):
        """Scrape a specific URL and its pagination."""
        current_url = start_url
        page_count = 1
        
        while current_url:
            print(f"\nProcessing page {page_count} for {start_url}: {current_url}")
            success = self.scrape_product_listings(current_url)
            
            if not success:
                print(f"Failed to scrape products from page {page_count}")
                break
                
            if max_pages and page_count >= max_pages:
                print(f"Reached maximum number of pages ({max_pages}) for {start_url}")
                break
                
            # Get the URL for the next page
            current_url = self.get_next_page_url(current_url)
            if not current_url:
                print(f"No more pages to scrape for {start_url}")
                break
                
            page_count += 1
            
        return page_count - 1  # Return the number of pages processed

    def run(self, urls, max_pages=None):
        """Run the scraper for multiple URLs."""
        total_pages = 0
        
        for url in urls:
            print(f"\n{'='*50}\nStarting to scrape: {url}\n{'='*50}")
            pages_scraped = self.scrape_url(url, max_pages)
            total_pages += pages_scraped
            
        # Save the scraped products to CSV
        self.save_to_csv()
        print(f"\nScraping completed. Scraped {len(self.products)} products from {total_pages} pages across {len(urls)} categories.")


if __name__ == "__main__":
    scraper = DeWaltScraper()
    
    # List of category URLs to scrape
    urls_to_scrape = [
        "https://www.dewalt.it/prodotti/utensili-manuali",
        "https://www.dewalt.it/prodotti/giardino",
        "https://www.dewalt.it/prodotti/portautensili",
        "https://www.dewalt.it/prodotti/organizza-il-tuo-spazio"
    ]
    
    # You can limit the number of pages to scrape per URL
    # Leave as None to scrape all available pages
    max_pages = None  # Change to a number like 3 to limit to 3 pages per URL
    
    scraper.run(urls_to_scrape, max_pages=max_pages)