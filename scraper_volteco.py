import time
import csv
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Impostazioni iniziali
VOLTECO_INITIAL_URL = "https://volteco.com/it/prodotti/"
OUTPUT_CSV_FILE = "volteco_prodotti2.csv"
BASE_URL = "https://volteco.com"

# --- Selettori CSS per gli elementi ---
# Selettori per la pagina di listing
PRODUCT_CARD_SELECTOR = "div.card.product-card"
PRODUCT_LINK_SELECTOR = "div.card.product-card > a"
PAGINATION_NEXT_SELECTOR = "a.next.page-numbers"

# Selettori per la pagina di dettaglio prodotto
PRODUCT_NAME_SELECTOR = "h2.element-title.mb-2"
PRODUCT_SHORT_DESCRIPTION_SELECTOR = "span.d-block.light-title.mb-3"
PRODUCT_ADVANTAGES_SELECTOR = "div#i-vantaggi ul.items-list li"
PRODUCT_IMAGE_SELECTOR = "span#product-image"


def get_soup_from_selenium(driver):
    """Ottiene l'HTML corrente dal driver Selenium e lo parsa con BeautifulSoup."""
    try:
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        return soup
    except Exception as e:
        print(f"Errore nell'ottenere la page_source o nel parsing con BeautifulSoup: {e}")
        return None


def extract_image_url_from_style(style_attribute):
    """Estrae l'URL dall'attributo style 'background-image: url(...)'. """
    if style_attribute:
        match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style_attribute)
        if match:
            return match.group(1)
    return None


def scrape_product_detail_page(driver, product_url):
    """
    Scrape della pagina di dettaglio di un prodotto Volteco.
    Estrae nome, descrizione completa e URL immagine.
    """
    print(f"\n--- Navigazione Pagina Dettaglio Prodotto: {product_url} ---")
    driver.get(product_url)
    
    # Attendi che la pagina carichi completamente
    try:
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_NAME_SELECTOR)))
        print(f"Pagina dettaglio prodotto caricata.")
    except TimeoutException:
        print(f"Timeout nell'attesa del caricamento della pagina dettaglio. Selettore non trovato: '{PRODUCT_NAME_SELECTOR}'.")
        return None
    
    # Ottieni l'HTML corrente della pagina dopo il caricamento
    soup_detail = get_soup_from_selenium(driver)
    if not soup_detail:
        print("Impossibile ottenere l'HTML dalla pagina di dettaglio.")
        return None
    
    product_data = {
        "name": "N/A",
        "brand": "Volteco",
        "description": "N/A",
        "image_url": "N/A",
        "product_page_url": product_url
    }
    
    # Estrai il Nome del prodotto
    name_tag = soup_detail.select_one(PRODUCT_NAME_SELECTOR)
    if name_tag:
        product_data["name"] = name_tag.get_text(strip=True)
        print(f"Nome prodotto: {product_data['name']}")
    else:
        print(f"Nome prodotto non trovato con selettore: '{PRODUCT_NAME_SELECTOR}'")
    
    # Estrai la Descrizione breve
    short_description = ""
    short_desc_tag = soup_detail.select_one(PRODUCT_SHORT_DESCRIPTION_SELECTOR)
    if short_desc_tag:
        short_description = short_desc_tag.get_text(strip=True)
        print(f"Descrizione breve trovata: {short_description[:70]}...")
    else:
        print(f"Descrizione breve non trovata con selettore: '{PRODUCT_SHORT_DESCRIPTION_SELECTOR}'")
    
    # Estrai i Vantaggi (lista elementi)
    advantages = []
    advantage_items = soup_detail.select(PRODUCT_ADVANTAGES_SELECTOR)
    if advantage_items:
        for item in advantage_items:
            advantages.append(item.get_text(strip=True))
        print(f"Trovati {len(advantages)} punti di vantaggio.")
    else:
        print(f"Nessun vantaggio trovato con selettore: '{PRODUCT_ADVANTAGES_SELECTOR}'")
    
    # Combina descrizione breve e vantaggi in un'unica descrizione completa
    full_description = short_description
    if advantages:
        if full_description:
            full_description += "\n\nVantaggi:\n"
        else:
            full_description = "Vantaggi:\n"
        for i, adv in enumerate(advantages, 1):
            full_description += f"{i}. {adv}\n"
    
    product_data["description"] = full_description.strip()
    
    # Estrai l'URL dell'immagine
    image_tag = soup_detail.select_one(PRODUCT_IMAGE_SELECTOR)
    if image_tag and image_tag.has_attr('style'):
        style_attribute = image_tag['style']
        image_url = extract_image_url_from_style(style_attribute)
        if image_url:
            product_data["image_url"] = urljoin(BASE_URL, image_url)
            print(f"URL immagine prodotto: {product_data['image_url']}")
        else:
            print("URL immagine non trovato nell'attributo style.")
    else:
        print(f"Elemento immagine non trovato con selettore: '{PRODUCT_IMAGE_SELECTOR}'")
    
    return product_data


def collect_product_links(driver, listing_url):
    """
    Navigazione di tutte le pagine di listing dei prodotti per raccogliere
    gli URL dei prodotti da visitare individualmente.
    """
    all_product_links = []
    current_page_url = listing_url
    
    while current_page_url:
        print(f"\n--- Raccolta link prodotti dalla pagina: {current_page_url} ---")
        driver.get(current_page_url)
        
        # Attendi che la pagina carichi e che almeno un contenitore prodotto sia presente
        try:
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CARD_SELECTOR)))
            print(f"Pagina di listing caricata.")
        except TimeoutException:
            print(f"Timeout nell'attesa dei prodotti nella lista. Verifica il selettore: '{PRODUCT_CARD_SELECTOR}'.")
            break
        
        # Ottieni l'HTML corrente della pagina
        soup_listing = get_soup_from_selenium(driver)
        if not soup_listing:
            print("Impossibile ottenere l'HTML dalla pagina di listing.")
            break
        
        # Trova tutti i link ai prodotti
        product_links = soup_listing.select(PRODUCT_LINK_SELECTOR)
        page_links = []
        
        for link in product_links:
            if link.has_attr('href'):
                relative_url = link['href']
                # Pulisci l'URL da eventuali parametri di query
                clean_url = relative_url.split('?')[0]
                full_url = urljoin(BASE_URL, clean_url)
                page_links.append(full_url)
        
        print(f"Trovati {len(page_links)} link a prodotti su questa pagina.")
        all_product_links.extend(page_links)
        
        # Cerca il link per la pagina successiva
        next_page_link_tag = soup_listing.select_one(PAGINATION_NEXT_SELECTOR)
        next_listing_url = None
        if next_page_link_tag and next_page_link_tag.has_attr('href'):
            relative_next_url = next_page_link_tag['href']
            clean_next_url = relative_next_url.split('?')[0]
            next_listing_url = urljoin(BASE_URL, clean_next_url)
            print(f"Trovato link pagina successiva: {next_listing_url}")
        else:
            print("Nessun link pagina successiva trovato. Fine navigazione.")
        
        # Passa alla pagina successiva per la prossima iterazione
        current_page_url = next_listing_url
        
        if current_page_url:
            time.sleep(3)  # Pausa tra le pagine di paginazione
    
    print(f"\nTotale link a prodotti raccolti: {len(all_product_links)}")
    return all_product_links


def save_to_csv(data, filename):
    """Salva una lista di dizionari in un file CSV."""
    if not data:
        print("Nessun dato da salvare nel file CSV.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_dir, filename)

    try:
        # Ottieni le chiavi dal primo dizionario per le intestazioni
        keys = data[0].keys()
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(data)
        print(f"Dati salvati in {csv_file_path}")
    except IndexError:
        print("Nessun dato prodotto valido estratto per determinare le intestazioni CSV.")
    except Exception as e:
        print(f"Errore durante il salvataggio del file CSV: {e}")


if __name__ == "__main__":
    # Configura le opzioni di Chrome
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")  # Rimuovi il commento per eseguire senza finestra
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = None
    all_scraped_products = []

    try:
        print("Inizializzazione driver Selenium...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(5)  # Attesa implicita per trovare gli elementi

        # Fase 1: Raccogliere tutti gli URL dei prodotti
        product_links = collect_product_links(driver, VOLTECO_INITIAL_URL)
        
        # Fase 2: Visitare ogni pagina di dettaglio prodotto e raccogliere i dati
        print("\n--- Inizio scraping dettaglio prodotti ---")
        for i, product_url in enumerate(product_links, 1):
            print(f"\nProdotto {i}/{len(product_links)}")
            product_data = scrape_product_detail_page(driver, product_url)
            
            if product_data:
                all_scraped_products.append(product_data)
                print(f"Aggiunto prodotto alla lista: {product_data.get('name')}")
            
            # Pausa tra le richieste per evitare di sovraccaricare il server
            time.sleep(2)

        print(f"\n--- Scraping Volteco completato. ---")
        print(f"Totale prodotti raccolti: {len(all_scraped_products)}")
        save_to_csv(all_scraped_products, OUTPUT_CSV_FILE)

    except Exception as e:
        print(f"\nErrore critico durante l'esecuzione principale: {e}")
        # Stampa traceback completo per debugging
        import traceback
        traceback.print_exc()

    finally:
        # Assicurati che il driver venga chiuso anche in caso di errori
        if driver:
            try:
                driver.quit()
                print("Browser Selenium chiuso.")
            except Exception as e:
                print(f"Errore durante la chiusura del browser: {e}")