import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from urllib.parse import urljoin, urlparse
import logging

# Configurazione logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FittScraper:
    def __init__(self):
        self.base_url = "https://www.fitt.com"
        self.products_url = "https://www.fitt.com/it/products/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.products_data = []

    def get_page(self, url, retries=3):
        """Ottiene il contenuto di una pagina con retry automatico"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Tentativo {attempt + 1} fallito per {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Backoff esponenziale
                else:
                    logger.error(f"Impossibile ottenere {url} dopo {retries} tentativi")
                    return None

    def extract_product_links(self):
        """Estrae tutti i link dei prodotti dalla pagina principale"""
        logger.info("Estrazione link prodotti dalla pagina principale...")
        
        response = self.get_page(self.products_url)
        if not response:
            logger.error("Impossibile accedere alla pagina dei prodotti")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Cerca tutti i link "Scopri di più"
        product_links = []
        
        # Cerca i bottoni con classe specifica
        cta_buttons = soup.find_all('a', class_=lambda x: x and 'ud_product-card__cta__btn' in x)
        
        for button in cta_buttons:
            href = button.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                product_links.append(full_url)
                logger.info(f"Trovato prodotto: {full_url}")

        # Cerca anche altri possibili pattern
        if not product_links:
            # Pattern alternativi per i link dei prodotti
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href')
                if href and '/product/' in href and 'scopri' in link.get_text().lower():
                    full_url = urljoin(self.base_url, href)
                    if full_url not in product_links:
                        product_links.append(full_url)

        logger.info(f"Trovati {len(product_links)} link prodotti")
        return product_links

    def clean_text(self, text):
        """Pulisce il testo da caratteri non desiderati"""
        if not text:
            return ""
        # Rimuove spazi extra e caratteri di nuova riga
        text = re.sub(r'\s+', ' ', text.strip())
        return text

    def extract_product_info(self, product_url):
        """Estrae le informazioni di un singolo prodotto"""
        logger.info(f"Estrazione informazioni da: {product_url}")
        
        response = self.get_page(product_url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        
        product_info = {
            'nome_prodotto': '',
            'marca': 'FITT',
            'descrizione': '',
            'immagine': '',
            'url': product_url
        }

        # Estrai nome prodotto
        title_selectors = [
            'h1.ud_product--intro__title',
            'h1[class*="product"][class*="title"]',
            'h1[class*="intro"][class*="title"]',
            '.product-title h1',
            'h1'
        ]
        
        for selector in title_selectors:
            title_element = soup.select_one(selector)
            if title_element:
                product_info['nome_prodotto'] = self.clean_text(title_element.get_text())
                break

        # Estrai descrizione
        desc_selectors = [
            'div.description',
            '.product-description',
            '.ud_product--intro__description',
            '[class*="description"]'
        ]
        
        for selector in desc_selectors:
            desc_element = soup.select_one(selector)
            if desc_element:
                product_info['descrizione'] = self.clean_text(desc_element.get_text())
                break

        # Estrai immagine principale
        img_selectors = [
            '.swiper-slide img',
            '.product-gallery img',
            '.ud_product img',
            'img[src*="thron.com"]',
            '.product-image img'
        ]
        
        for selector in img_selectors:
            img_element = soup.select_one(selector)
            if img_element:
                img_src = img_element.get('src')
                if img_src:
                    # Se l'URL è relativo, rendilo assoluto
                    if img_src.startswith('//'):
                        img_src = 'https:' + img_src
                    elif img_src.startswith('/'):
                        img_src = urljoin(self.base_url, img_src)
                    product_info['immagine'] = img_src
                    break

        # Verifica che abbiamo estratto almeno il nome del prodotto
        if not product_info['nome_prodotto']:
            logger.warning(f"Nome prodotto non trovato per: {product_url}")
            # Prova a estrarre dal title della pagina
            title_tag = soup.find('title')
            if title_tag:
                product_info['nome_prodotto'] = self.clean_text(title_tag.get_text())

        logger.info(f"Estratto: {product_info['nome_prodotto']}")
        return product_info

    def scrape_all_products(self):
        """Scraping completo di tutti i prodotti"""
        logger.info("Inizio scraping prodotti FITT...")
        
        # Ottieni tutti i link dei prodotti
        product_links = self.extract_product_links()
        
        if not product_links:
            logger.error("Nessun link prodotto trovato!")
            return

        # Scraping di ogni prodotto
        for i, product_url in enumerate(product_links, 1):
            logger.info(f"Processando prodotto {i}/{len(product_links)}")
            
            product_info = self.extract_product_info(product_url)
            if product_info:
                self.products_data.append(product_info)
            
            # Pausa tra le richieste per evitare di sovraccaricare il server
            time.sleep(1)

        logger.info(f"Scraping completato! Trovati {len(self.products_data)} prodotti")

    def save_to_csv(self, filename='fitt_products.csv'):
        """Salva i dati in un file CSV"""
        if not self.products_data:
            logger.error("Nessun dato da salvare!")
            return

        logger.info(f"Salvataggio dati in {filename}...")
        
        fieldnames = ['nome_prodotto', 'marca', 'descrizione', 'immagine', 'url']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in self.products_data:
                writer.writerow(product)

        logger.info(f"File {filename} salvato con successo!")
        
        # Stampa statistiche
        print(f"\n=== STATISTICHE SCRAPING ===")
        print(f"Prodotti trovati: {len(self.products_data)}")
        print(f"File salvato: {filename}")
        
        # Mostra alcuni esempi
        if self.products_data:
            print(f"\n=== ESEMPI PRODOTTI ===")
            for i, product in enumerate(self.products_data[:3], 1):
                print(f"\n{i}. {product['nome_prodotto']}")
                print(f"   Descrizione: {product['descrizione'][:100]}...")
                print(f"   Immagine: {product['immagine'][:50]}...")

def main():
    """Funzione principale"""
    scraper = FittScraper()
    
    try:
        # Esegui lo scraping
        scraper.scrape_all_products()
        
        # Salva i dati
        scraper.save_to_csv('fitt_products.csv')
        
    except KeyboardInterrupt:
        logger.info("Scraping interrotto dall'utente")
    except Exception as e:
        logger.error(f"Errore durante lo scraping: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()