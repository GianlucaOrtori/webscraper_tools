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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

class LecaScraper:
    def __init__(self, headless=True):
        self.base_url = "https://www.leca.it/prodotti/"
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
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.post"))
            )
        except TimeoutException:
            print("Timeout durante l'attesa del caricamento dei prodotti")
            return []
        
        # Ottieni il contenuto HTML aggiornato
        html_content = self.driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Trova tutti gli articoli di prodotto
        product_articles = soup.find_all("article", class_="post")
        print(f"Trovati {len(product_articles)} prodotti nella pagina corrente")
        
        new_products = []
        for article in product_articles:
            try:
                product_link = article.find("a")["href"] if article.find("a") else None
                product_name = article.find("p", class_="entry-title").text.strip() if article.find("p", class_="entry-title") else None
                product_description = article.find("p", class_="entry-content").text.strip() if article.find("p", class_="entry-content") else None
                product_image = article.find("img", class_="entry-thumb")["src"] if article.find("img", class_="entry-thumb") else None
                
                product = {
                    "nome": product_name,
                    "Marca": "Leca",
                    "descrizione": product_description,
                    "immagine": product_image,
                    "link": product_link
                }
                
                # Verifica che il prodotto non sia già nella lista
                if product not in self.products and all(product.get(key) for key in ["nome", "immagine"]):
                    new_products.append(product)
            except Exception as e:
                print(f"Errore nell'estrazione di un prodotto: {e}")
        
        return new_products
    
    def click_load_more(self):
        """Clicca sul pulsante 'Carica altri' se disponibile"""
        try:
            # Verifica se il pulsante esiste
            load_more_button = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.button.full.loadMore"))
            )
            
            # Verifica se il pulsante è visibile e cliccabile
            if load_more_button.is_displayed():
                # Scrolla fino al pulsante
                self.driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(1)  # Piccola pausa per assicurarsi che il pulsante sia visibile
                
                # Clicca sul pulsante
                load_more_button.click()
                print("Pulsante 'Carica altri' cliccato con successo")
                
                # Attendi che i nuovi prodotti siano caricati
                time.sleep(2)
                return True
            else:
                print("Pulsante 'Carica altri' non visibile")
                return False
                
        except TimeoutException:
            print("Pulsante 'Carica altri' non trovato - probabilmente non ci sono più prodotti da caricare")
            return False
        except ElementClickInterceptedException:
            print("Impossibile cliccare sul pulsante - potrebbe essere coperto da un altro elemento")
            # Tenta di cliccare con JavaScript
            try:
                self.driver.execute_script("arguments[0].click();", load_more_button)
                time.sleep(2)
                return True
            except Exception as e:
                print(f"Errore anche con JavaScript: {e}")
                return False
        except Exception as e:
            print(f"Errore durante il click sul pulsante 'Carica altri': {e}")
            return False
    
    def scrape_all_products(self):
        """Scrapa tutti i prodotti dal sito Leca"""
        try:
            # Apri la pagina dei prodotti
            print(f"Navigando verso {self.base_url}...")
            self.driver.get(self.base_url)
            time.sleep(3)  # Attendi il caricamento iniziale
            
            # Estrai i prodotti dalla prima pagina
            initial_products = self.extract_products_from_page()
            self.products.extend(initial_products)
            print(f"Estratti {len(initial_products)} prodotti dalla pagina iniziale")
            
            # Clicca sul pulsante "Carica altri" fino a quando non è più disponibile
            click_count = 0
            max_clicks = 20  # Limite di sicurezza
            
            while click_count < max_clicks:
                if self.click_load_more():
                    # Estrai i prodotti dalla pagina aggiornata
                    new_products = self.extract_products_from_page()
                    
                    # Aggiungi solo i nuovi prodotti non già presenti nella lista
                    new_count = 0
                    for product in new_products:
                        if product not in self.products:
                            self.products.append(product)
                            new_count += 1
                    
                    print(f"Aggiunti {new_count} nuovi prodotti dopo il click #{click_count+1}")
                    
                    if new_count == 0 and click_count > 2:
                        print("Nessun nuovo prodotto trovato dopo più tentativi, terminando...")
                        break
                    
                    click_count += 1
                else:
                    print("Impossibile caricare altri prodotti, terminando...")
                    break
                
                # Pausa breve per evitare di sovraccaricare il server
                time.sleep(2)
            
            print(f"Scraping completato. Trovati in totale {len(self.products)} prodotti.")
        except Exception as e:
            print(f"Errore durante lo scraping: {e}")
        finally:
            # Chiudi il browser
            self.driver.quit()
            print("Browser chiuso")
            
        return self.products
    
    def save_to_csv(self, filename="prodotti_leca.csv"):
        """Salva i prodotti in un file CSV"""
        if not self.products:
            print("Nessun prodotto da salvare")
            return
            
        try:
            with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["nome","Marca", "descrizione", "immagine", "link"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for product in self.products:
                    writer.writerow(product)
                
            print(f"Prodotti salvati in {filename}")
        except Exception as e:
            print(f"Errore nel salvataggio del file CSV: {e}")
    
    def save_to_json(self, filename="prodotti_leca.json"):
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
    # Imposta headless=False per vedere il browser in azione (utile per debug)
    scraper = LecaScraper(headless=True)
    prodotti = scraper.scrape_all_products()
    
    print(f"\nEsempio di dati estratti (primi 3 prodotti):")
    for i, prodotto in enumerate(prodotti[:3], 1):
        print(f"\nProdotto {i}:")
        print(f"Marca: {prodotto['Marca']}")
        print(f"Nome: {prodotto['nome']}")
        print(f"Descrizione: {prodotto['descrizione']}")
        print(f"Immagine: {prodotto['immagine']}")
        print(f"Link: {prodotto['link']}")
    
    # Salva i dati nei formati CSV e JSON
    scraper.save_to_csv()
    scraper.save_to_json()