import time
import csv
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
import os
from urllib.parse import urljoin

class SikaScraper:
    def __init__(self, output_folder="sika_products"):
        """Inizializza lo scraper con le configurazioni necessarie."""
        self.base_url = "https://ita.sika.com"
        self.start_url = "https://ita.sika.com/it/edilizia/prodotti-edilizia.html"
        self.output_folder = output_folder
        self.images_folder = os.path.join(output_folder, "images")
        self.products_data = []
        
        # Crea cartelle di output se non esistono
        os.makedirs(self.output_folder, exist_ok=True)
        os.makedirs(self.images_folder, exist_ok=True)
        
        # Configura Selenium
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Esegui in modalità headless (senza GUI)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Inizializza il webdriver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.driver.implicitly_wait(10)
    
    def load_all_products(self):
        """Carica tutti i prodotti cliccando sul pulsante 'Più Risultati' finché è presente."""
        print("Caricamento della pagina principale...")
        self.driver.get(self.start_url)
        time.sleep(3)  # Attendi caricamento iniziale
        
        # Accetta i cookie se presente il banner
        try:
            cookie_button = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.onetrust-accept-btn-handler"))
            )
            cookie_button.click()
            print("Banner cookie accettato")
            time.sleep(1)
        except TimeoutException:
            print("Nessun banner cookie trovato o già accettato")
        
        # Clicca sul pulsante "Più Risultati" finché esiste
        load_more_count = 0
        while True:
            try:
                load_more_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "div.load-more-results button.cmp-button"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(1)
                load_more_button.click()
                load_more_count += 1
                print(f"Cliccato 'Più Risultati' ({load_more_count} volte)")
                time.sleep(2)  # Attendi caricamento nuovi prodotti
            except (TimeoutException, NoSuchElementException):
                print("Nessun altro pulsante 'Più Risultati' trovato. Tutti i prodotti sono stati caricati.")
                break
        
        print(f"Completato il caricamento di tutti i prodotti (pulsante 'Più Risultati' cliccato {load_more_count} volte)")
    
    def get_product_links(self):
        """Estrae i link di tutti i prodotti dalla pagina principale."""
        print("Estraendo i link di tutti i prodotti...")
        
        # Trova tutti gli elementi dei prodotti
        product_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-list-item] div.cmp-teaser_product a")
        
        # Estrai gli URL
        product_links = []
        for element in product_elements:
            href = element.get_attribute("href")
            if href:
                product_links.append(href)
        
        print(f"Trovati {len(product_links)} prodotti")
        return product_links
    
    def extract_highest_quality_image_url(self, img_element):
        """Estrae l'URL dell'immagine con la qualità più alta dal tag picture."""
        try:
            # Estrai il codice HTML completo dell'elemento picture
            picture_html = img_element.get_attribute('outerHTML')
            
            # Trova tutti gli URL delle immagini usando regex
            image_urls = re.findall(r'https://sika\.scene7\.com/is/image/[^?"\']+', picture_html)
            
            # Se non ci sono URL, prova a estrarre direttamente dall'attributo src dell'immagine
            if not image_urls:
                img_src = img_element.find_element(By.TAG_NAME, "img").get_attribute("src")
                if img_src:
                    image_urls = [img_src]
            
            # Seleziona la versione con la risoluzione più alta
            # Le immagini di qualità superiore in genere hanno parametri come wid=1620 o wid=2440
            highest_quality_url = None
            highest_width = 0
            
            for url in image_urls:
                # Aggiungi parametri per massima qualità se l'URL base è stato trovato
                base_url = url.split('?')[0] if '?' in url else url
                quality_url = f"{base_url}?wid=2440&fit=crop%2C1&fmt=png-alpha"
                
                # Registra l'URL di qualità più alta
                current_width = 2440  # Impostiamo la larghezza massima
                if current_width > highest_width:
                    highest_width = current_width
                    highest_quality_url = quality_url
            
            return highest_quality_url
        
        except Exception as e:
            print(f"Errore nell'estrazione dell'URL dell'immagine: {e}")
            return None
    
    def download_image(self, url, product_name):
        """Scarica l'immagine e salva il file."""
        if not url:
            return None
        
        try:
            # Crea un nome file sicuro per l'immagine
            safe_filename = "".join([c if c.isalnum() or c in ['-', '_'] else '_' for c in product_name])
            filename = f"{safe_filename}.png"
            filepath = os.path.join(self.images_folder, filename)
            
            # Scarica l'immagine
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                print(f"Immagine salvata: {filepath}")
                return filename
            else:
                print(f"Errore nel download dell'immagine: HTTP {response.status_code}")
                return None
        
        except Exception as e:
            print(f"Errore nel download dell'immagine: {e}")
            return None
    
    def scrape_product_details(self, url):
        """Estrae i dettagli del prodotto dalla sua pagina."""
        print(f"Elaborazione prodotto: {url}")
        self.driver.get(url)
        time.sleep(2)  # Attendi il caricamento della pagina
        
        try:
            # Estrai il nome del prodotto
            product_name_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.cmp-product__title h1.cmp-title__text"))
            )
            product_name = product_name_element.text.strip()
            
            # Estrai la descrizione del prodotto
            try:
                product_desc_element = self.driver.find_element(By.CSS_SELECTOR, "p[itemprop='description']")
                product_description = product_desc_element.text.strip()
            except NoSuchElementException:
                product_description = "Descrizione non disponibile"
            
            # Estrai l'URL dell'immagine di alta qualità
            try:
                picture_element = self.driver.find_element(By.CSS_SELECTOR, "picture")
                image_url = self.extract_highest_quality_image_url(picture_element)
                image_filename = self.download_image(image_url, product_name) if image_url else None
            except NoSuchElementException:
                image_url = None
                image_filename = None
            
            # Crea il record del prodotto
            product_data = {
                "nome": product_name,
                "descrizione": product_description,
                "url": url,
                "immagine_url": image_url,
                "immagine_filename": image_filename
            }
            
            print(f"Prodotto elaborato: {product_name}")
            return product_data
            
        except Exception as e:
            print(f"Errore nell'elaborazione del prodotto {url}: {e}")
            return None
    
    def save_to_csv(self):
        """Salva i dati dei prodotti in un file CSV."""
        csv_file = os.path.join(self.output_folder, "sika_products.csv")
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as file:
            fieldnames = ["nome", "descrizione", "url", "immagine_url", "immagine_filename"]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            
            writer.writeheader()
            for product in self.products_data:
                if product:  # Skip None values
                    writer.writerow(product)
        
        print(f"Dati salvati in {csv_file}")
    
    def run(self):
        """Esegui lo scraping completo."""
        try:
            print("Avvio dello scraping...")
            
            # Carica tutti i prodotti
            self.load_all_products()
            
            # Ottieni i link ai prodotti
            product_links = self.get_product_links()
            
            # Estrai i dettagli per ogni prodotto
            for i, link in enumerate(product_links, 1):
                print(f"Elaborazione prodotto {i}/{len(product_links)}")
                product_data = self.scrape_product_details(link)
                if product_data:
                    self.products_data.append(product_data)
                
                # Pausa breve per evitare di sovraccaricare il server
                time.sleep(1)
            
            # Salva i dati in CSV
            self.save_to_csv()
            
            print(f"Scraping completato! Elaborati {len(self.products_data)} prodotti.")
            
        except Exception as e:
            print(f"Errore durante lo scraping: {e}")
        
        finally:
            # Chiudi il browser
            self.driver.quit()


if __name__ == "__main__":
    scraper = SikaScraper()
    scraper.run()