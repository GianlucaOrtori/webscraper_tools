import requests
from bs4 import BeautifulSoup
import csv
import time
import re
import random
import os

class UnishopScraper:
    def __init__(self, start_url, output_file='unishop_products.csv'):
        self.start_url = start_url
        self.output_file = output_file
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.visited_urls = set()
        self.products = []
    
    def get_soup(self, url):
        """Makes a request to the URL and returns a BeautifulSoup object"""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def extract_product_info(self, product_card, base_url):
        """Extract product information from a product card"""
        product_info = {}
        
        # Find product name and URL
        product_link = product_card.select_one('div.product-info a.product-name')
        if product_link:
            product_info['name'] = product_link.get_text(strip=True)
            product_info['url'] = product_link.get('href')
            if not product_info['url'].startswith('http'):
                product_info['url'] = base_url.rstrip('/') + product_info['url']
        
        # Try to find product description directly in the card
        description = product_card.select_one('div.product-info div.product-description')
        if description:
            product_info['description'] = description.get_text(strip=True)
        else:
            product_info['description'] = None
        
        # Get image URL if present
        img_element = product_card.select_one('img.product-image')
        if img_element:
            product_info['image_url'] = img_element.get('src')
        
        return product_info
    
    def fetch_product_details(self, product_url):
        """Fetch additional details from the product page if needed"""
        if product_url in self.visited_urls:
            return None
            
        self.visited_urls.add(product_url)
        
        # Add a random delay to avoid being blocked
        time.sleep(random.uniform(1, 3))
        
        soup = self.get_soup(product_url)
        if not soup:
            return None
        
        # Try to extract a more detailed description from the product page
        description = None
        desc_element = soup.select_one('div.product-description')
        if desc_element:
            description = desc_element.get_text(strip=True)
        
        return description
    
    def process_category_page(self, category_url, base_url):
        """Process all products in a category page"""
        soup = self.get_soup(category_url)
        if not soup:
            return
        
        print(f"Processing category: {category_url}")
        
        # Find all product cards
        product_cards = soup.select('div.cms-listing-col div.product-box')
        
        for product_card in product_cards:
            product_info = self.extract_product_info(product_card, base_url)
            
            if not product_info.get('description') and product_info.get('url'):
                # If no description in card, try to get it from the product page
                detailed_description = self.fetch_product_details(product_info['url'])
                if detailed_description:
                    product_info['description'] = detailed_description
            
            if product_info.get('name'):
                self.products.append(product_info)
                print(f"Found product: {product_info['name']}")
        
        # Check for pagination and process next pages
        next_page = soup.select_one('a.pagination-next')
        if next_page and next_page.get('href'):
            next_url = next_page.get('href')
            if not next_url.startswith('http'):
                next_url = base_url.rstrip('/') + next_url
            
            if next_url not in self.visited_urls:
                self.visited_urls.add(next_url)
                time.sleep(random.uniform(1, 3))  # Add delay between pagination requests
                self.process_category_page(next_url, base_url)
    
    def extract_categories(self):
        """Extract all categories from the main page"""
        soup = self.get_soup(self.start_url)
        if not soup:
            return []
        
        categories = []
        
        # Find all category cards based on the provided HTML structure
        category_cards = soup.select('div.cms-listing-col div.product-box')
        
        for card in category_cards:
            category_link = card.select_one('div.product-info a.product-name')
            if category_link:
                category_name = category_link.get_text(strip=True)
                category_url = category_link.get('href')
                
                # Make sure URL is absolute
                if not category_url.startswith('http'):
                    base_url = '/'.join(self.start_url.split('/')[:3])
                    category_url = base_url + category_url
                
                categories.append({
                    'name': category_name,
                    'url': category_url
                })
                print(f"Found category: {category_name}")
        
        return categories
    
    def save_to_csv(self):
        """Save extracted products to a CSV file"""
        if not self.products:
            print("No products to save.")
            return
        
        with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['name', 'description', 'url', 'image_url']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for product in self.products:
                writer.writerow({
                    'name': product.get('name', ''),
                    'description': product.get('description', ''),
                    'url': product.get('url', ''),
                    'image_url': product.get('image_url', '')
                })
            
        print(f"Saved {len(self.products)} products to {self.output_file}")
    
    def run(self):
        """Main method to run the scraper"""
        print(f"Starting scraper for {self.start_url}")
        
        # Extract all categories
        categories = self.extract_categories()
        print(f"Found {len(categories)} categories")
        
        base_url = '/'.join(self.start_url.split('/')[:3])
        
        # Process each category
        for category in categories:
            time.sleep(random.uniform(2, 5))  # Add delay between category requests
            self.process_category_page(category['url'], base_url)
        
        # Save results
        self.save_to_csv()
        print("Scraping completed!")


if __name__ == "__main__":
    # URL of the viteria section
    start_url = "https://www.unishop.it/viteria/"
    
    # Create and run the scraper
    scraper = UnishopScraper(start_url)
    scraper.run()