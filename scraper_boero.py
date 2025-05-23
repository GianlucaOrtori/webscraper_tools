import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from urllib.parse import urljoin # Utile per costruire URL completi

# Impostazioni iniziali
# URL base del sito
BASE_URL = "https://shop.boero.it"
# Percorso della pagina di elenco prodotti
LISTING_PATH = "/prodotti"
# Numero di pagine da scrapare
NUM_PAGES_TO_SCRAPE = 4
# File di output
OUTPUT_CSV_FILE = "boero_prodotti.csv"

# --- Selettori CSS per gli elementi sulla pagina di ELENCO ---
# Basati sull'HTML che hai fornito

# Selettore per ogni singolo contenitore prodotto nella lista (la card)
# Usiamo il div esterno con le classi di colonna
PRODUCT_CONTAINER_SELECTOR_LISTING = "div.col-6.col-md-3"

# Selettore per il link alla pagina di dettaglio prodotto (dentro il contenitore)
# È il tag <a> che avvolge il div.thumb
PRODUCT_LINK_SELECTOR_LISTING = "div.listing--pad > a"

# Selettore per il div che contiene nome e descrizione breve
PRODUCT_TOP_INFO_SELECTOR_LISTING = "div.text div.top"

# Selettore per il nome del prodotto (all'interno del div.top)
PRODUCT_NAME_SELECTOR_LISTING = "h3.name"

# Selettore per l'immagine del prodotto (all'interno del div.thumb)
PRODUCT_IMAGE_SELECTOR_LISTING = "div.thumb img"

# --- Selettori CSS per gli elementi sulla pagina di DETTAGLIO prodotto ---
# Basati sull'esempio fornito per https://shop.boero.it/prodotti/litron-2

# Selettore per il div "infocard" che contiene le specifiche tecniche
PRODUCT_INFOCARD_SELECTOR = "div.infocard"

# Selettore per ogni riga di specifiche all'interno di infocard
PRODUCT_INFOLINE_SELECTOR = "div.line"

# Selettore per la descrizione estesa del prodotto
PRODUCT_DESCRIPTION_EXTENDED_SELECTOR = "div.tab--content"

# Configurazione di Selenium WebDriver
driver = None


def get_soup_from_selenium(driver):
    """Ottiene l'HTML corrente dal driver Selenium e lo parsa con BeautifulSoup."""
    try:
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        return soup
    except Exception as e:
        print(f"Errore nell'ottenere la page_source o nel parsing con BeautifulSoup: {e}")
        return None


def scrape_product_detail_page(driver, detail_url):
    """
    Scrape la pagina di dettaglio del prodotto per estrarre informazioni aggiuntive.
    """
    if not detail_url or detail_url == "N/A":
        return {
            "adatto_per": "N/A",
            "supporto_consigliato": "N/A",
            "base": "N/A",
            "extended_description": "N/A"
        }
    
    try:
        print(f"  Navigazione alla pagina di dettaglio: {detail_url}")
        driver.get(detail_url)
        
        # Attendi che gli elementi chiave siano caricati
        try:
            wait = WebDriverWait(driver, 10)
            # Attendiamo o l'infocard o la descrizione estesa (uno dei due elementi principali)
            wait.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    f"{PRODUCT_INFOCARD_SELECTOR}, {PRODUCT_DESCRIPTION_EXTENDED_SELECTOR}"
                ))
            )
            print("  Pagina di dettaglio caricata.")
        except TimeoutException:
            print(f"  Timeout nell'attesa dei dati sulla pagina di dettaglio {detail_url}.")
            return {
                "adatto_per": "N/A",
                "supporto_consigliato": "N/A",
                "base": "N/A",
                "extended_description": "N/A"
            }
        
        # Ottieni l'HTML corrente della pagina di dettaglio
        soup = get_soup_from_selenium(driver)
        if not soup:
            print("  Impossibile ottenere la soup dalla pagina di dettaglio.")
            return {
                "adatto_per": "N/A", 
                "supporto_consigliato": "N/A", 
                "base": "N/A",
                "extended_description": "N/A"
            }
        
        detail_data = {
            "adatto_per": "N/A",
            "supporto_consigliato": "N/A",
            "base": "N/A",
            "extended_description": "N/A"
        }
        
        # --- Estrazione delle specifiche tecniche dall'infocard ---
        infocard = soup.select_one(PRODUCT_INFOCARD_SELECTOR)
        if infocard:
            print("  Trovata sezione infocard.")
            # Estrai tutte le righe di informazioni
            info_lines = infocard.select(PRODUCT_INFOLINE_SELECTOR)
            
            for line in info_lines:
                # Ottieni il testo completo della riga
                line_text = line.get_text(strip=True)
                
                # Esegui il parsing in base alla chiave
                if "Adatto per:" in line_text:
                    # Estrai il valore diretto dal tag 'b' con classe 'value'
                    value_tag = line.select_one('b.value')
                    if value_tag:
                        detail_data["adatto_per"] = value_tag.get_text(strip=True)
                
                elif "Supporto consigliato:" in line_text:
                    value_tag = line.select_one('b.value')
                    if value_tag:
                        detail_data["supporto_consigliato"] = value_tag.get_text(strip=True)
                
                elif "Base:" in line_text:
                    value_tag = line.select_one('b.value')
                    if value_tag:
                        detail_data["base"] = value_tag.get_text(strip=True)
        else:
            print(f"  Sezione infocard non trovata su {detail_url}.")
        
        # --- Estrazione della descrizione estesa ---
        description_extended = soup.select_one(PRODUCT_DESCRIPTION_EXTENDED_SELECTOR)
        if description_extended:
            print("  Trovata descrizione estesa.")
            detail_data["extended_description"] = description_extended.get_text(strip=True)
        else:
            print(f"  Descrizione estesa non trovata su {detail_url}.")
        
        return detail_data
        
    except Exception as e:
        print(f"  Errore durante lo scraping della pagina di dettaglio {detail_url}: {e}")
        return {
            "adatto_per": "N/A", 
            "supporto_consigliato": "N/A", 
            "base": "N/A",
            "extended_description": "N/A"
        }


def scrape_boero_page(driver, page_url):
    """
    Naviga a una pagina specifica di elenco prodotti Boero ed estrae i dati dei prodotti.
    """
    print(f"Navigazione alla pagina: {page_url}")
    driver.get(page_url)

    # Attendi che i contenitori prodotto siano presenti
    try:
        wait = WebDriverWait(driver, 15) # Attesa per il caricamento dei prodotti
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LISTING)))
        print("Pagina caricata (primo blocco prodotto trovato).")
    except TimeoutException:
        print(f"Timeout nell'attesa dei prodotti sulla pagina {page_url}. Potrebbe non esserci nulla o il selettore non è corretto.")
        # Stampa una parte dell'HTML per debuggare se non trova contenitori
        soup_debug = get_soup_from_selenium(driver)
        if soup_debug:
             print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
             print(soup_debug.prettify()[:2000])
        return [] # Restituisce lista vuota se non trova prodotti


    # Ottieni l'HTML corrente della pagina dopo il caricamento
    soup = get_soup_from_selenium(driver)
    if not soup:
        print("Impossibile ottenere la soup dalla pagina.")
        return [] # Restituisce lista vuota

    # Trova tutti i contenitori prodotto nell'HTML corrente
    product_containers = soup.select(PRODUCT_CONTAINER_SELECTOR_LISTING)
    print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR_LISTING}') su {page_url}.")

    if not product_containers:
        print(f"Nessun contenitore prodotto trovato su {page_url}. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR_LISTING}'.")
        # Stampa una parte dell'HTML per debuggare se non trova contenitori
        print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
        print(soup.prettify()[:2000])
        return [] # Restituisce lista vuota


    products_on_page = []

    for i, container in enumerate(product_containers):
        # print(f"  Elaborazione prodotto {i+1}/{len(product_containers)}...") # DEBUG
        product_data = {
            "name": "N/A",
            "brand": "Boero", # Marca fissa
            "description": "N/A",
            "price": "N/A", # Il prezzo non sembra essere nella card di lista
            "image_url": "N/A",
            "product_page_url": "N/A",
            "adatto_per": "N/A",
            "supporto_consigliato": "N/A",
            "base": "N/A",
            "extended_description": "N/A"
        }

        try:
            # Trova il div.top che contiene nome e descrizione breve
            top_info_div = container.select_one(PRODUCT_TOP_INFO_SELECTOR_LISTING)

            if top_info_div:
                # Estrai il Nome del prodotto dal div.top
                name_tag = top_info_div.select_one(PRODUCT_NAME_SELECTOR_LISTING)
                if name_tag:
                    product_data["name"] = name_tag.get_text(strip=True)
                    # print(f"   Trovato Nome: {product_data['name']}") # DEBUG

                # --- Estrai la Descrizione breve dal div.top ---
                # La descrizione è il testo diretto nel div.top dopo l'h3.name
                description_text = ""
                if name_tag:
                    # Itera sui contenuti del div.top dopo l'h3
                    for sibling in name_tag.next_siblings:
                        if isinstance(sibling, str): # Se è un nodo di testo
                            description_text += sibling.strip() + " "
                        # Puoi aggiungere qui altri controlli se la descrizione è avvolta in altri tag
                        # elif sibling.name == 'span':
                        #     description_text += sibling.get_text(strip=True) + " "

                product_data["description"] = description_text.strip()
                # print(f"   Trovata Descrizione: {product_data['description']}") # DEBUG
                # --- Fine Estrazione Descrizione ---

            else:
                 print("   Div top info (div.text div.top) non trovato nel contenitore.")


            # Estrai l'URL dell'immagine
            img_tag = container.select_one(PRODUCT_IMAGE_SELECTOR_LISTING)
            if img_tag and img_tag.has_attr('src'):
                 image_src = img_tag['src']
                 # Usa urljoin per costruire l'URL completo, gestisce la codifica
                 if image_src and not image_src.startswith('data:'): # Ignora placeholder data:image
                     product_data["image_url"] = urljoin(BASE_URL, image_src)
                     # print(f"   Trovata Immagine: {product_data['image_url']}") # DEBUG
                 # else: image_url rimane N/A se placeholder o vuoto
            # else: img_tag non trovato o senza src, image_url rimane N/A


            # Estrai l'URL della pagina di dettaglio
            link_tag = container.select_one(PRODUCT_LINK_SELECTOR_LISTING)
            if link_tag and link_tag.has_attr('href'):
                 relative_url = link_tag['href']
                 product_data["product_page_url"] = urljoin(BASE_URL, relative_url)
                 # print(f"   Trovato URL prodotto: {product_data['product_page_url']}") # DEBUG
            # else: product_page_url rimane N/A

            # --- NUOVO: Visita la pagina di dettaglio per informazioni aggiuntive ---
            if product_data["product_page_url"] != "N/A":
                print(f"  Estrazione dettagli aggiuntivi per il prodotto: {product_data.get('name', 'N/A')}")
                detail_data = scrape_product_detail_page(driver, product_data["product_page_url"])
                
                # Aggiungi i dati di dettaglio al prodotto
                product_data["adatto_per"] = detail_data["adatto_per"]
                product_data["supporto_consigliato"] = detail_data["supporto_consigliato"]
                product_data["base"] = detail_data["base"]
                product_data["extended_description"] = detail_data["extended_description"]
                
                # Aggiungiamo una breve pausa tra le visite di dettaglio per non sovraccaricare
                time.sleep(1)
            # --- Fine NUOVO ---


            # Aggiungi i dati estratti alla lista dei prodotti di questa pagina
            # Aggiungiamo solo se abbiamo trovato almeno il nome o l'URL
            if product_data.get("name") != "N/A" or product_data.get("product_page_url") != "N/A":
                products_on_page.append(product_data)
                # print(f"  Aggiunto prodotto alla lista della pagina: {product_data.get('name')}") # DEBUG
            # else: Blocco saltato (nessun nome o URL)


        except Exception as e:
            print(f"Errore durante l'elaborazione del contenitore prodotto {i+1} su {page_url}: {e}. Salto.")
            continue # Continua con la prossima card

    print(f"Scraping completato per la pagina {page_url}. Trovati {len(products_on_page)} prodotti.")
    return products_on_page


def save_to_csv(data, filename):
    """Salva una lista di dizionari in un file CSV."""
    if not data:
        print("Nessun dato da salvare nel file CSV.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_dir, filename)

    try:
        # Ottieni le chiavi dal primo dizionario per le intestazioni
        if not data:
             print("Nessun dato valido per determinare le intestazioni CSV.")
             return

        keys = data[0].keys()
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader() # Scrive l'intestazione (nomi colonne)
            dict_writer.writerows(data) # Scrive i dati
        print(f"Dati salvati in {csv_file_path}")
    except IndexError:
        print("Nessun dato prodotto valido estratto per determinare le intestazioni CSV.")
    except Exception as e:
        print(f"Errore durante il salvataggio del file CSV: {e}")


if __name__ == "__main__":
    try:
        # Inizializza il driver Selenium
        # ASSICURATI DI AVER SCARICATO IL DRIVER DEL BROWSER E CHE SIA NEL TUO PATH DI SISTEMA
        # O SPECIFICA IL PERCORSO COMPLETO AL DRIVER QUI.
        # driver = webdriver.Chrome() # O webdriver.Firefox(), webdriver.Edge(), ecc.
        # driver = webdriver.Firefox()

        # Esegui in modalità visibile per debuggare inizialmente, poi puoi passare a headless
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument("--headless") # Rimuovi il commento per eseguire senza finestra
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)


        all_scraped_products = []

        print(f"Inizio scraping per {NUM_PAGES_TO_SCRAPE} pagine a partire da {BASE_URL}{LISTING_PATH}")

        # Loop attraverso le pagine da 1 al numero specificato
        for page_num in range(1, NUM_PAGES_TO_SCRAPE + 1):
            if page_num == 1:
                # La prima pagina non ha il parametro ?page=1
                page_url = f"{BASE_URL}{LISTING_PATH}"
            else:
                # Costruisci l'URL per le pagine successive
                page_url = f"{BASE_URL}{LISTING_PATH}?page={page_num}"

            print(f"\n--- Scraping Pagina {page_num}/{NUM_PAGES_TO_SCRAPE} ---")

            # Scrape la pagina corrente
            products_from_page = scrape_boero_page(driver, page_url)

            # Aggiungi i prodotti trovati sulla pagina corrente alla lista totale
            all_scraped_products.extend(products_from_page)

            print(f"Totale prodotti raccolti finora: {len(all_scraped_products)}")

            # Pausa tra le pagine per evitare di sovraccaricare il server
            if page_num < NUM_PAGES_TO_SCRAPE:
                 time.sleep(2)


        print(f"\n--- Scraping completato per {NUM_PAGES_TO_SCRAPE} pagine. ---")
        print(f"Totale prodotti raccolti: {len(all_scraped_products)}")
        save_to_csv(all_scraped_products, OUTPUT_CSV_FILE)

    except Exception as e:
        print(f"Errore critico durante l'esecuzione principale: {e}")

    finally:
        # Assicurati che il driver venga chiuso anche in caso di errori
        if driver:
            try:
                driver.quit()
                print("Browser Selenium chiuso.")
            except Exception as e:
                print(f"Errore durante la chiusura del browser: {e}")