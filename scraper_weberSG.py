import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Impostazioni iniziali
# URL della pagina del brand Weber su Gruppo Edico.
# Lo scraper navigherà le pagine di elenco tramite paginazione da qui.
START_URLS_FOR_LISTINGS = [
    "https://www.gruppoedico.it/brands/weber_saint_gobain"
]
# Nome del file CSV di output
OUTPUT_CSV_FILE = "weber_prodotti.csv"

# URL base del sito per costruire URL completi
BASE_URL = "https://www.gruppoedico.it"

# --- Limite Pagine ---
# Imposta il numero massimo di pagine di elenco da scrapare.
PAGE_LIMIT = 11

# --- Selettori CSS per gli elementi sulla pagina di ELENCO (pagina brand/categoria) ---
# Basati sugli snippet HTML che hai fornito per Gruppo Edico.

# Selettore per ogni singolo contenitore prodotto nella lista (la card o blocco)
PRODUCT_CONTAINER_SELECTOR_LISTING = "li.item.product.product-item"

# Selettore per il link alla pagina di dettaglio prodotto all'interno del blocco nella lista
PRODUCT_DETAIL_LINK_SELECTOR_LISTING = "a.product-item-link"

# Selettore per il link "Successivo" nella paginazione
NEXT_PAGE_SELECTOR = "li.item.pages-item-next a.action.next"


# --- Selettori CSS per gli elementi sulla pagina di DETTAGLIO Prodotto ---
# Basati sugli snippet HTML che hai fornito per Gruppo Edico.

# Selettore per il titolo del prodotto nella pagina di dettaglio
PRODUCT_TITLE_SELECTOR_DETAIL = "h2.page-title span.base"

# Selettore per gli elementi della descrizione
PRODUCT_DESCRIPTION_SELECTOR_DETAIL = "div.product.attribute.overview div.value"

# Selettore per l'immagine principale del prodotto nella pagina di dettaglio
PRODUCT_IMAGE_SELECTOR_DETAIL = "div.fotorama__stage__frame.fotorama__active img"


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


def scrape_weber_detail_page(driver, detail_url):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium
    ed estrae nome, descrizione e URL immagine.
    """
    product_detail_data = {
        "name": "N/A",
        "brand": "Weber", # Marca fissa
        "description": "N/A",
        "price": "N/A",
        "image_url": "N/A",
        "product_page_url": detail_url
    }

    try:
        driver.get(detail_url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_TITLE_SELECTOR_DETAIL)))

        soup = get_soup_from_selenium(driver)
        if not soup:
             print("   Impossibile ottenere la soup dalla pagina di dettaglio.")
             return product_detail_data

        name_tag = soup.select_one(PRODUCT_TITLE_SELECTOR_DETAIL)
        if name_tag:
            product_detail_data["name"] = name_tag.get_text(strip=True)

        description_tag = soup.select_one(PRODUCT_DESCRIPTION_SELECTOR_DETAIL)
        if description_tag:
            description_text = description_tag.get_text(separator='\n', strip=True)
            if description_text:
                product_detail_data["description"] = description_text

        img_tag = soup.select_one(PRODUCT_IMAGE_SELECTOR_DETAIL)
        if img_tag and img_tag.has_attr('src'):
             image_src = img_tag['src']
             if image_src and not image_src.startswith('data:'):
                 product_detail_data["image_url"] = urljoin(BASE_URL, image_src)


    except (TimeoutException, NoSuchElementException) as e:
        print(f"  Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina di dettaglio {detail_url}: {e}")
    except Exception as e:
        print(f"  Errore generico durante lo scraping della pagina di dettaglio {detail_url}: {e}")

    return product_detail_data


def scrape_weber_listing_page_for_product_urls(driver, listing_url):
     """
     Naviga a una pagina di elenco, raccoglie gli URL dei prodotti su quella pagina,
     e trova l'URL della pagina successiva (se esiste tramite paginazione).
     Non include lo scrolling per lazy loading in questo caso.
     """
     print(f"Navigazione Pagina Lista Prodotti per raccogliere URL prodotti: {listing_url}")
     driver.get(listing_url)

     try:
         wait = WebDriverWait(driver, 20)
         wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LISTING)))
         print("Pagina lista prodotti caricata (primo prodotto trovato).")
     except TimeoutException:
         print("Timeout nell'attesa dei prodotti nella lista. Potrebbe non esserci nulla su questa pagina o il selettore del contenitore prodotto è errato.")
         soup_listing_debug = get_soup_from_selenium(driver)
         if soup_listing_debug:
             print("Primi 2000 caratteri dell'HTML della pagina per debug (Timeout o nessun contenitore trovato):")
             print(soup_listing_debug.prettify()[:2000])
         return [], None

     product_detail_urls_on_page = []

     soup_listing = get_soup_from_selenium(driver)
     if not soup_listing:
         print("Impossibile ottenere la soup dalla pagina di elenco.")
         return [], None

     product_containers = soup_listing.select(PRODUCT_CONTAINER_SELECTOR_LISTING)
     print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR_LISTING}') su {listing_url}.")

     if not product_containers:
         print(f"Nessun contenitore prodotto trovato su {listing_url}. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR_LISTING}'.")
         print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
         print(soup_listing.prettify()[:2000])
         pass

     for i, container in enumerate(product_containers):
         try:
             detail_link_tag = container.select_one(PRODUCT_DETAIL_LINK_SELECTOR_LISTING)
             if detail_link_tag and detail_link_tag.has_attr('href'):
                 detail_url = detail_link_tag['href']
                 full_detail_url = urljoin(BASE_URL, detail_url)
                 product_detail_urls_on_page.append(full_detail_url)
         except Exception as e:
             print(f"Errore nel raccogliere l'URL dettaglio dal contenitore prodotto {i+1} su {listing_url}: {e}. Salto.")
             continue

     print(f"Raccolti {len(product_detail_urls_on_page)} URL di pagine di dettaglio su {listing_url}.")

     next_page_link = soup_listing.select_one(NEXT_PAGE_SELECTOR)
     next_listing_url = None
     if next_page_link and next_page_link.has_attr('href'):
         relative_next_url = next_page_link['href']
         next_listing_url = urljoin(BASE_URL, relative_next_url)
         print(f"Trovato link pagina successiva: {next_listing_url}")
     else:
         print("Nessun link pagina successiva trovato.")

     return product_detail_urls_on_page, next_listing_url


def save_to_csv(data, filename):
    """Salva una lista di dizionari in un file CSV."""
    if not data:
        print("Nessun dato da salvare nel file CSV.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_dir, filename)

    try:
        if not data:
             print("Nessun dato valido per determinare le intestazioni CSV.")
             return

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
    try:
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument("--headless") # Rimuovi il commento per eseguire senza finestra
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)

        all_scraped_products = []
        all_product_detail_urls_collected = []
        seen_product_detail_urls = set()

        print(f"\n--- Fase 1: Raccogli URL Prodotti dalle Pagine di Elenco (con paginazione, limite {PAGE_LIMIT} pagine) ---") # Messaggio aggiornato
        current_listing_url = START_URLS_FOR_LISTINGS[0]
        page_count = 0 # <--- Inizializza il contatore pagine

        # Processa le pagine di elenco, seguendo la paginazione fino al limite di pagine
        while current_listing_url and page_count < PAGE_LIMIT: # <--- Aggiungi la condizione di limite pagine
            page_count += 1 # <--- Incrementa il contatore pagine
            print(f"\n--- Elaborazione Pagina Lista Prodotti {page_count}/{PAGE_LIMIT}: {current_listing_url} ---") # Messaggio aggiornato

            detail_urls_on_page, next_listing_url = scrape_weber_listing_page_for_product_urls(driver, current_listing_url)

            for detail_url in detail_urls_on_page:
                if detail_url not in seen_product_detail_urls:
                    all_product_detail_urls_collected.append(detail_url)
                    seen_product_detail_urls.add(detail_url)

            # Passa alla pagina successiva
            current_listing_url = next_listing_url

            if current_listing_url and page_count < PAGE_LIMIT: # <--- Aggiungi controllo sul limite pagine prima della pausa
                 time.sleep(2)

        if page_count >= PAGE_LIMIT:
             print(f"\nLimite di {PAGE_LIMIT} pagine raggiunto. Interruzione raccolta URL.")
        else:
             print("\nFine della paginazione. Tutte le pagine disponibili sono state processate.")


        print(f"\n--- Fine Fase 1. Raccolti {len(all_product_detail_urls_collected)} URL di prodotti unici. ---")


        # --- Fase 2: Scraping di ogni pagina di dettaglio prodotto ---
        print("\n--- Fase 2: Scraping Dettagli Prodotti ---")

        original_window = driver.current_window_handle

        for i, detail_url in enumerate(all_product_detail_urls_collected):
            print(f"Scraping dettaglio prodotto {i+1}/{len(all_product_detail_urls_collected)}: {detail_url}")

            try:
                driver.execute_script("window.open(arguments[0]);", detail_url)
                time.sleep(1)

                driver.switch_to.window(driver.window_handles[-1])

                product_detail = scrape_weber_detail_page(driver, detail_url)

                if product_detail and product_detail.get("name") != "N/A":
                    all_scraped_products.append(product_detail)

                driver.close()
                driver.switch_to.window(original_window)

                time.sleep(1)

            except Exception as e:
                print(f"Errore durante lo scraping della pagina di dettaglio {detail_url}: {e}. Salto.")
                try:
                     if len(driver.window_handles) > 1:
                         driver.close()
                     driver.switch_to.window(original_window)
                except:
                     pass
                continue


        print(f"\n--- Fine Fase 2. Scraping dettagli completato. ---")
        print(f"Totale prodotti raccolti: {len(all_scraped_products)}")
        save_to_csv(all_scraped_products, OUTPUT_CSV_FILE)

    except Exception as e:
        print(f"Errore critico durante l'esecuzione principale: {e}")

    finally:
        if driver:
            try:
                driver.quit()
                print("Browser Selenium chiuso.")
            except Exception as e:
                print(f"Errore durante la chiusura del browser: {e}")