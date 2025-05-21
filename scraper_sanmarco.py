import requests
from bs4 import BeautifulSoup
import time
import json
import csv
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class ProductScraper:
    def __init__(self, base_urls, headless=True):
        self.base_urls = base_urls if isinstance(base_urls, list) else [base_urls]
        self.products = []
        
        # Configurazione Selenium
        self.headless = headless
        self.setup_selenium()
        
    def setup_selenium(self):
        """Configura il driver Selenium"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            print("Browser Chrome avviato con successo")
        except Exception as e:
            print(f"Errore nell'avvio di Chrome: {e}")
            print("Tentativo di avvio con Firefox...")
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            firefox_options = FirefoxOptions()
            if self.headless:
                firefox_options.add_argument("--headless")
            self.driver = webdriver.Firefox(options=firefox_options)
            print("Browser Firefox avviato con successo")
            
    def extract_products_from_page(self):
        """Estrae i prodotti dalla pagina attuale"""
        # Attendi che i prodotti siano caricati
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "p.product_preview_title"))
            )
        except TimeoutException:
            print("Timeout durante l'attesa del caricamento dei prodotti")
            return []
        
        # Ottieni il contenuto HTML aggiornato
        html_content = self.driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Trova tutti i container di prodotti
        product_containers = soup.find_all("div", class_="product_preview")
        
        if not product_containers:
            print("Nessun prodotto trovato con il selettore specificato")
            # Tenta un approccio alternativo cercando le informazioni direttamente
            titles = soup.find_all("p", class_="product_preview_title")
            print(f"Trovati {len(titles)} titoli di prodotti")
            
            # Stampa alcuni elementi della pagina per debug
            print("Esempio di struttura della pagina:")
            sample_elements = soup.find_all(class_=lambda value: value and "product" in value.lower())[:5]
            for elem in sample_elements:
                print(f"Elemento trovato: {elem.name} con classe {elem.get('class')}")
        
        print(f"Trovati {len(product_containers)} container di prodotti nella pagina")
        
        new_products = []
        for container in product_containers:
            try:
                # Estrazione del nome del prodotto
                title_elem = container.find("p", class_="product_preview_title")
                if title_elem and title_elem.strong:
                    product_name = title_elem.strong.text.strip()
                else:
                    product_name = title_elem.text.strip() if title_elem else "Nome non disponibile"
                
                # Estrazione della descrizione
                description_elem = container.find("p", class_="product_preview_description")
                product_description = description_elem.text.strip() if description_elem else "Descrizione non disponibile"
                
                # Estrazione dell'immagine
                img_container = container.find("div", class_="product_preview_img")
                if img_container and img_container.img:
                    product_image = img_container.img.get("src")
                else:
                    product_image = "Immagine non disponibile"
                
                # Estrazione del link al prodotto (se presente)
                link_elem = container.find("a")
                product_link = link_elem.get("href") if link_elem else None
                
                product = {
                    "nome": product_name,
                    "marca": "San Marco",  # Aggiungiamo sempre San Marco come marca
                    "descrizione": product_description,
                    "immagine": product_image,
                    "link": product_link
                }
                
                # Verifica che il prodotto non sia già nella lista e abbia almeno nome e immagine
                if self.is_unique_product(product) and product["nome"] != "Nome non disponibile":
                    new_products.append(product)
                    
            except Exception as e:
                print(f"Errore nell'estrazione di un prodotto: {e}")
        
        return new_products
    
    def is_unique_product(self, product):
        """Verifica se un prodotto è già presente nella lista dei prodotti"""
        for existing_product in self.products:
            if existing_product["nome"] == product["nome"]:
                return False
        return True
    
    def extract_individual_product_info(self):
        """
        Metodo alternativo per estrarre prodotti quando i container non sono facilmente identificabili.
        Cerca elementi individuali relativi ai prodotti e li combina.
        """
        html_content = self.driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Cerca tutti i titoli di prodotto
        title_elements = soup.find_all("p", class_="product_preview_title")
        print(f"Trovati {len(title_elements)} titoli di prodotti")
        
        new_products = []
        for title_elem in title_elements:
            try:
                # Troviamo il contenitore padre che probabilmente contiene tutti gli elementi del prodotto
                parent_container = self.find_parent_container(title_elem)
                
                # Estrai nome
                product_name = title_elem.strong.text.strip() if title_elem.strong else title_elem.text.strip()
                
                # Cerca la descrizione nel container padre
                description_elem = parent_container.find("p", class_="product_preview_description") if parent_container else None
                product_description = description_elem.text.strip() if description_elem else "Descrizione non disponibile"
                
                # Cerca l'immagine nel container padre
                img_container = parent_container.find("div", class_="product_preview_img") if parent_container else None
                img_elem = img_container.find("img") if img_container else None
                product_image = img_elem.get("src") if img_elem else "Immagine non disponibile"
                
                # Cerca il link nel container padre o nel titolo stesso
                link_elem = parent_container.find("a") if parent_container else None
                if not link_elem and title_elem.parent.name == "a":
                    link_elem = title_elem.parent
                product_link = link_elem.get("href") if link_elem else None
                
                product = {
                    "nome": product_name,
                    "marca": "San Marco",  # Aggiungiamo sempre San Marco come marca
                    "descrizione": product_description,
                    "immagine": product_image,
                    "link": product_link
                }
                
                # Verifica che il prodotto non sia già nella lista
                if self.is_unique_product(product):
                    new_products.append(product)
                    
            except Exception as e:
                print(f"Errore nell'estrazione di un prodotto: {e}")
        
        return new_products
    
    def find_parent_container(self, element, max_levels=5):
        """
        Risale nell'albero DOM per trovare un contenitore che probabilmente contiene tutti i dettagli del prodotto.
        max_levels: numero massimo di livelli da risalire nell'albero DOM.
        """
        current = element
        levels = 0
        
        # Risali nell'albero DOM fino a trovare un div che potrebbe essere il container
        while current and levels < max_levels:
            current = current.parent
            levels += 1
            
            # Controlla se questo elemento ha i componenti principali di un prodotto
            if current and current.name == "div" and (
                (current.find("p", class_="product_preview_title") and 
                 current.find("div", class_="product_preview_img")) or
                "product_preview" in current.get("class", [])
            ):
                return current
                
        # Se non troviamo un container adatto, restituiamo il parent più diretto
        return element.parent
    
    def get_pagination_links(self):
        """
        Estrae i link per la paginazione, se presenti
        Ritorna una lista di URL per le pagine successive
        """
        html_content = self.driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Cerca elementi di paginazione (adatta il selettore in base al sito specifico)
        pagination = soup.find("div", class_="pagination")
        
        if not pagination:
            # Prova alternative comuni per paginazione
            pagination = soup.find("ul", class_="pagination")
            if not pagination:
                pagination = soup.find("nav", class_="pagination")
            if not pagination:
                # Cerca qualsiasi elemento che potrebbe contenere paginazione
                pagination = soup.find(lambda tag: tag.name and "pagination" in tag.get("class", []))
        
        if not pagination:
            print("Nessun elemento di paginazione trovato")
            return []
        
        # Estrai i link alle pagine
        page_links = []
        links = pagination.find_all("a")
        
        for link in links:
            href = link.get("href")
            if href and "javascript:" not in href and "#" not in href:
                # Normalizza URL relativi
                if href.startswith("/"):
                    base_url = self.driver.current_url.split("/")[0] + "//" + self.driver.current_url.split("/")[2]
                    href = base_url + href
                elif not href.startswith(("http://", "https://")):
                    base_url = self.driver.current_url.rstrip("/")
                    href = base_url + "/" + href
                
                # Aggiungi solo se non già presente
                if href not in page_links:
                    page_links.append(href)
        
        return page_links
    
    def scrape_all_products(self):
        """Scrapa tutti i prodotti da tutti gli URL specificati"""
        try:
            for url_index, base_url in enumerate(self.base_urls):
                print(f"\n[{url_index+1}/{len(self.base_urls)}] Iniziando scraping per: {base_url}")
                
                # Apri la pagina dei prodotti
                print(f"Navigando verso {base_url}...")
                self.driver.get(base_url)
                time.sleep(3)  # Attendi il caricamento iniziale
                
                # Estrai i prodotti dalla prima pagina
                initial_products = self.extract_products_from_page()
                
                # Se non abbiamo trovato prodotti con il metodo standard, proviamo con il metodo alternativo
                if not initial_products:
                    print("Tentativo con metodo alternativo di estrazione...")
                    initial_products = self.extract_individual_product_info()
                
                self.products.extend(initial_products)
                print(f"Estratti {len(initial_products)} prodotti dalla pagina iniziale")
                
                # Controlla se ci sono pagine aggiuntive
                pagination_links = self.get_pagination_links()
                print(f"Trovate {len(pagination_links)} pagine aggiuntive")
                
                # Visita ogni pagina di paginazione e estrai i prodotti
                for i, page_url in enumerate(pagination_links):
                    print(f"Navigando verso la pagina {i+2}: {page_url}")
                    self.driver.get(page_url)
                    time.sleep(2)  # Attendi il caricamento della pagina
                    
                    page_products = self.extract_products_from_page()
                    
                    # Se non troviamo prodotti con il metodo standard, proviamo con quello alternativo
                    if not page_products:
                        page_products = self.extract_individual_product_info()
                    
                    # Aggiungi solo prodotti non duplicati
                    new_count = 0
                    for product in page_products:
                        if self.is_unique_product(product):
                            self.products.append(product)
                            new_count += 1
                    
                    print(f"Aggiunti {new_count} nuovi prodotti dalla pagina {i+2}")
            
            print(f"\nScraping completato. Trovati in totale {len(self.products)} prodotti unici.")
            
        except Exception as e:
            print(f"Errore durante lo scraping: {e}")
        finally:
            # Chiudi il browser
            self.driver.quit()
            print("Browser chiuso")
            
        return self.products
    
    def save_to_csv(self, filename="prodotti.csv"):
        """Salva i prodotti in un file CSV"""
        if not self.products:
            print("Nessun prodotto da salvare")
            return
            
        try:
            with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["nome", "marca", "descrizione", "immagine", "link"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for product in self.products:
                    writer.writerow(product)
                
            print(f"Prodotti salvati in {filename}")
        except Exception as e:
            print(f"Errore nel salvataggio del file CSV: {e}")
    
    def save_to_json(self, filename="prodotti.json"):
        """Salva i prodotti in un file JSON"""
        if not self.products:
            print("Nessun prodotto da salvare")
            return
            
        try:
            with open(filename, "w", encoding="utf-8") as jsonfile:
                json.dump(self.products, jsonfile, ensure_ascii=False, indent=4)
                
            print(f"Prodotti salvati in {filename}")
        except Exception as e:
            print(f"Errore nel salvataggio del file JSON: {e}")

# Esempio di utilizzo
if __name__ == "__main__":
    # Specifica gli URL del sito da cui vuoi estrarre i prodotti
    urls = [
        "https://san-marco.com/prodotti-acquistabili-online-san-marco#smalti",
        "https://san-marco.com/pitture-decorative-acquistabili-online-san-marco"
    ]
    
    # Imposta headless=False per vedere il browser in azione (utile per debug)
    scraper = ProductScraper(urls, headless=True)
    prodotti = scraper.scrape_all_products()
    
    print(f"\nEsempio di dati estratti (primi 3 prodotti):")
    for i, prodotto in enumerate(prodotti[:3], 1):
        print(f"\nProdotto {i}:")
        print(f"Nome: {prodotto['nome']}")
        print(f"Marca: {prodotto['marca']}")
        print(f"Descrizione: {prodotto['descrizione']}")
        print(f"Immagine: {prodotto['immagine']}")
        print(f"Link: {prodotto['link']}")
    
    # Salva i dati nei formati CSV e JSON
    scraper.save_to_csv("prodotti_sanmarco.csv")
    scraper.save_to_json("prodotti_sanmarco.json")