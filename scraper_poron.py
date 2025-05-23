import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from urllib.parse import urljoin, urlparse
import os

# Versione con Selenium per siti con JavaScript
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Selenium non installato. Usa: pip install selenium")

class PoronScraperSelenium:
    def __init__(self, use_selenium=True):
        self.base_url = "https://gruppoporon.com"
        self.products_url = "https://gruppoporon.com/prodotti/"
        self.products_data = []
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        
        if self.use_selenium:
            self.setup_selenium()
        else:
            self.setup_requests()
    
    def setup_selenium(self):
        """Configura Selenium WebDriver"""
        print("Configurazione Selenium...")
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Decommentare la riga sotto per modalità headless (senza interfaccia grafica)
        # chrome_options.add_argument("--headless")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("Selenium configurato con successo!")
        except Exception as e:
            print(f"Errore configurazione Selenium: {e}")
            print("Assicurati di aver installato ChromeDriver")
            self.use_selenium = False
            self.setup_requests()
    
    def setup_requests(self):
        """Fallback con requests"""
        print("Usando requests come fallback...")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def get_page_selenium(self, url):
        """Carica pagina con Selenium"""
        try:
            print(f"Caricamento con Selenium: {url}")
            self.driver.get(url)
            
            # Aspetta che la pagina si carichi completamente
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Scroll per attivare lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            return self.driver.page_source
        except Exception as e:
            print(f"Errore Selenium: {e}")
            return None
    
    def get_page_requests(self, url, retries=3):
        """Fallback con requests"""
        for attempt in range(retries):
            try:
                print(f"Tentativo {attempt + 1} con requests: {url}")
                response = self.session.get(url, timeout=15, verify=True, allow_redirects=True)
                response.raise_for_status()
                print(f"Successo! Status code: {response.status_code}")
                return response.text
            except Exception as e:
                print(f"Errore requests: {e}")
                if attempt < retries - 1:
                    time.sleep(3)
        return None
    
    def extract_product_links(self):
        """Estrae tutti i link dei prodotti"""
        print("=== ESTRAZIONE LINK PRODOTTI ===")
        
        if self.use_selenium:
            html_content = self.get_page_selenium(self.products_url)
        else:
            html_content = self.get_page_requests(self.products_url)
        
        if not html_content:
            print("❌ Impossibile caricare la pagina dei prodotti")
            # Lista di link noti - AGGIORNA QUESTA LISTA
            known_products = [
                "https://gruppoporon.com/product/austrotherm-xps-top-30-sf/",
                # Aggiungi qui altri link di prodotti che conosci
            ]
            print(f"🔄 Usando {len(known_products)} link noti")
            return known_products
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Salva HTML per debug
        with open('debug_products_page.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("💾 HTML salvato in debug_products_page.html")
        
        product_links = []
        
        # Selettori basati sul tuo HTML
        selectors_to_try = [
            'a.x-cell.e448-e17.mcg-11',
            'a[class*="x-cell"][class*="e448-e17"]',
            'a[class*="mcg-11"]',
            'a[href*="/product/"]',
            '.x-cell a',
            'a[href*="gruppoporon.com/product/"]'
        ]
        
        print("🔍 Ricerca link prodotti...")
        for i, selector in enumerate(selectors_to_try):
            links = soup.select(selector)
            print(f"   Selettore {i+1}: '{selector}' -> {len(links)} link")
            
            if links:
                for link in links:
                    href = link.get('href')
                    if href:
                        if href.startswith('/'):
                            full_url = self.base_url + href
                        elif not href.startswith('http'):
                            full_url = urljoin(self.base_url, href)
                        else:
                            full_url = href
                        
                        if '/product/' in full_url and full_url not in product_links:
                            product_links.append(full_url)
                
                if product_links:
                    break
        
        # Se non trova nulla, cerca tutti i link della pagina
        if not product_links:
            print("🔍 Ricerca in tutti i link della pagina...")
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href')
                if href and '/product/' in href:
                    if href.startswith('/'):
                        full_url = self.base_url + href
                    elif not href.startswith('http'):
                        full_url = urljoin(self.base_url, href)
                    else:
                        full_url = href
                    
                    if full_url not in product_links:
                        product_links.append(full_url)
        
        print(f"✅ Trovati {len(product_links)} link di prodotti")
        
        # Mostra i primi 5 link
        for i, link in enumerate(product_links[:5]):
            print(f"   {i+1}. {link}")
        
        if len(product_links) > 5:
            print(f"   ... e altri {len(product_links) - 5}")
        
        return product_links
    
    def extract_product_data(self, product_url):
        """Estrae dati di un singolo prodotto"""
        print(f"\n📦 Elaborazione: {product_url}")
        
        if self.use_selenium:
            html_content = self.get_page_selenium(product_url)
        else:
            html_content = self.get_page_requests(product_url)
        
        if not html_content:
            print("❌ Impossibile caricare la pagina del prodotto")
            return None
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Salva HTML per debug
        filename = f"debug_product_{len(self.products_data) + 1}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        
        # Estrazione nome prodotto
        nome_prodotto = ""
        nome_selectors = [
            'h1.x-text-content-text-primary',
            'h2.x-text-content-text-primary',
            '.x-text-content-text-primary',
            'h1',
            'h2',
            '.entry-title',
            '.product-title'
        ]
        
        for selector in nome_selectors:
            element = soup.select_one(selector)
            if element:
                nome_prodotto = element.get_text(strip=True)
                print(f"✅ Nome trovato: {nome_prodotto}")
                break
        
        if not nome_prodotto:
            print("❌ Nome prodotto non trovato")
        
        # Estrazione descrizione
        descrizione = ""
        desc_selectors = [
            'div.x-text.x-content.e119-e11.m3b-1j',
            'div.x-text.x-content.e448-e20.mcg-12',
            'div.x-text.x-content',
            '.x-text.x-content',
            '.product-description',
            '.entry-content'
        ]
        
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                descrizione = element.get_text(separator=' ', strip=True)
                descrizione = re.sub(r'\s+', ' ', descrizione)
                print(f"✅ Descrizione trovata: {descrizione[:80]}...")
                break
        
        if not descrizione:
            print("❌ Descrizione non trovata")
        
        # Estrazione immagine
        immagine_url = ""
        
        # Cerca background-image
        bg_elements = soup.select('[style*="background-image"]')
        for element in bg_elements:
            style = element.get('style', '')
            match = re.search(r'background-image:\s*url\(["\']?(.*?)["\']?\)', style)
            if match:
                immagine_url = match.group(1)
                if not immagine_url.startswith('http'):
                    immagine_url = urljoin(self.base_url, immagine_url)
                print(f"✅ Immagine background trovata: {immagine_url}")
                break
        
        # Se non trova background, cerca tag img
        if not immagine_url:
            img_selectors = [
                '.x-image img',
                'span.x-image img',
                'img[src*=".jpg"], img[src*=".png"], img[src*=".jpeg"]',
                'img'
            ]
            
            for selector in img_selectors:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    immagine_url = img.get('src')
                    if not immagine_url.startswith('http'):
                        immagine_url = urljoin(self.base_url, immagine_url)
                    print(f"✅ Immagine img trovata: {immagine_url}")
                    break
        
        if not immagine_url:
            print("❌ Immagine non trovata")
        
        product_data = {
            'nome_prodotto': nome_prodotto,
            'marca': 'Poron',
            'descrizione': descrizione,
            'immagine_url': immagine_url,
            'url_prodotto': product_url
        }
        
        return product_data
    
    def scrape_all_products(self):
        """Scraping di tutti i prodotti"""
        print("🚀 INIZIO SCRAPING GRUPPO PORON")
        print("=" * 50)
        
        # Ottieni link prodotti
        product_links = self.extract_product_links()
        
        if not product_links:
            print("❌ Nessun link di prodotto trovato!")
            return
        
        print(f"\n📋 Elaborazione di {len(product_links)} prodotti...")
        
        # Elabora ogni prodotto
        for i, link in enumerate(product_links, 1):
            print(f"\n--- PRODOTTO {i}/{len(product_links)} ---")
            
            product_data = self.extract_product_data(link)
            if product_data and product_data['nome_prodotto']:
                self.products_data.append(product_data)
                print(f"✅ Salvato: {product_data['nome_prodotto']}")
            else:
                print("❌ Dati insufficienti, prodotto saltato")
            
            # Pausa tra richieste
            if self.use_selenium:
                time.sleep(2)
            else:
                time.sleep(3)
        
        print(f"\n🎉 SCRAPING COMPLETATO!")
        print(f"✅ Trovati {len(self.products_data)} prodotti validi")
    
    def save_to_csv(self, filename='prodotti_poron.csv'):
        """Salva i dati in CSV"""
        if not self.products_data:
            print("❌ Nessun dato da salvare!")
            return
        
        print(f"💾 Salvataggio in {filename}...")
        
        fieldnames = ['nome_prodotto', 'marca', 'descrizione', 'immagine_url', 'url_prodotto']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.products_data)
        
        print(f"✅ File CSV salvato: {filename}")
        print(f"📊 Prodotti salvati: {len(self.products_data)}")
    
    def print_summary(self):
        """Stampa riassunto"""
        if not self.products_data:
            print("❌ Nessun dato trovato!")
            return
        
        print("\n" + "="*60)
        print("📋 RIASSUNTO PRODOTTI ESTRATTI")
        print("="*60)
        
        for i, product in enumerate(self.products_data, 1):
            print(f"\n{i}. 📦 {product['nome_prodotto']}")
            print(f"   🏷️  Marca: {product['marca']}")
            print(f"   📝 Descrizione: {product['descrizione'][:100]}...")
            print(f"   🖼️  Immagine: {product['immagine_url']}")
            print(f"   🔗 URL: {product['url_prodotto']}")
    
    def close(self):
        """Chiude il browser Selenium"""
        if self.use_selenium and hasattr(self, 'driver'):
            self.driver.quit()
            print("🔒 Browser chiuso")

def main():
    print("🔧 WEBSCRAPER GRUPPO PORON")
    print("="*50)
    
    # Scegli se usare Selenium
    use_selenium = SELENIUM_AVAILABLE
    if use_selenium:
        print("✅ Selenium disponibile - usando browser automatizzato")
    else:
        print("⚠️  Selenium non disponibile - usando requests")
        print("   Per migliori risultati installa: pip install selenium")
    
    scraper = PoronScraperSelenium(use_selenium=use_selenium)
    
    try:
        # Esegui scraping
        scraper.scrape_all_products()
        
        # Salva risultati
        scraper.save_to_csv()
        
        # Mostra riassunto
        scraper.print_summary()
        
    except KeyboardInterrupt:
        print("\n⏹️  Scraping interrotto dall'utente")
    except Exception as e:
        print(f"❌ Errore durante lo scraping: {e}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()