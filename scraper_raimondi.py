import logging
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException
)
import csv
import os

# --- Configurazione ---
# Usiamo ?limit=all per caricare tutti i prodotti su un'unica pagina
BASE_URL = "https://www.prontocantiere.it/marchi/raimondi.html?limit=all"
CSV_FILENAME = "prodotti_prontocantiere_raimondi.csv"
WAIT_TIMEOUT = 15  # Timeout per le attese esplicite in secondi
IMPLICIT_WAIT_TIME = 5 # Attesa implicita (può essere utile in alcuni casi, ma WebDriverWait è preferito)

# Selettori CSS/XPath per la PAGINA DI LISTING (basati sul tuo HTML)
# Contenitore principale del prodotto
PRODUCT_CONTAINER_SELECTOR = 'li.item div.item-area'
# Selettore per il link alla pagina di dettaglio DENTRO il container prodotto
PRODUCT_LINK_SELECTOR = 'h2.product-name a'
# Selettore per l'immagine principale nella listing
PRODUCT_LISTING_IMAGE_SELECTOR = 'a.product-image img'
# Selettore per il prezzo nella listing (reso più generale per prendere .price dentro .price-box)
# Questo cercherà sia il prezzo normale che lo special price se usa la classe 'price'
PRODUCT_LISTING_PRICE_SELECTOR = 'div.price-box .price'
# Selettore per il pulsante "Pagina successiva" (rilevante se non usi ?limit=all)
PAGINATION_NEXT_SELECTOR = 'a[rel="next"].js-search-link'


# Selettori per i dati sulla PAGINA DI DETTAGLIO del prodotto (basati sul tuo HTML)
DETAIL_PAGE_TITLE_SELECTOR = 'div.product-name h1' # Titolo principale
DETAIL_PAGE_DESCRIPTION_SHORT_SELECTOR = 'div.short-description div.std' # Breve descrizione (possono essere più di uno)
# Selettore per la descrizione completa dentro la tab
DETAIL_PAGE_DESCRIPTION_FULL_SELECTOR = 'div.tab-content#tab_description_tabbed_contents div.txt_9_00'

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

# --- Funzione Principale di Scraping ---
def scrape_products(url):
    """
    Naviga la pagina di listing, raccoglie i link e immagini dei prodotti,
    visita ogni link per scrapare i dettagli, torna indietro e gestisce la paginazione.
    """
    driver = None
    all_product_data = []
    current_page_url = url # Partiamo dall'URL iniziale
    original_window_handle = None # Per gestire potenziali nuove tab/finestre

    try:
        # --- Inizializzazione Driver ---
        logging.info("Inizializzazione driver Selenium...")
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless') # Esegui in background (commenta per vedere il browser)
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        # Opzionale: Ignora i warning SSL (come quello di urllib3)
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')

        # service = Service('/path/to/chromedriver') # Decommenta e modifica se chromedriver non è nel PATH
        driver = webdriver.Chrome(options=options) # , service=service)
        # driver.implicitly_wait(IMPLICIT_WAIT_TIME) # Attiva se vuoi attesa implicita globale

        logging.info(f"--- Inizio scraping da: {current_page_url} ---")
        original_window_handle = driver.current_window_handle # Memorizza l'handle della finestra principale

        # Loop di paginazione (con ?limit=all, questo loop eseguirà una sola volta)
        while current_page_url:
            logging.info(f"Navigando pagina di listing: {current_page_url}")
            driver.get(current_page_url)

            try:
                # Attendi che i contenitori prodotto siano visibili/presenti
                WebDriverWait(driver, WAIT_TIMEOUT).until(
                    ec.presence_of_all_elements_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR))
                )
                logging.info(f"Pagina di listing caricata. Contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR}') trovati.")
            except TimeoutException:
                logging.warning(f"Nessun contenitore prodotto trovato su {current_page_url} entro il timeout. Fine paginazione o problema nel selettore del contenitore.")
                break # Non ci sono prodotti o la pagina non è caricata correttamente, esci dal loop di paginazione

            # Raccogli i link, URL delle immagini e prezzi dalla pagina di listing corrente
            # È cruciale raccogliere questi dati ORA, prima di navigare via per ogni prodotto
            product_listing_items = driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR)
            product_details_from_listing = [] # Lista per salvare URL, immagine e prezzo dalla listing

            if not product_listing_items:
                 logging.info("Nessun prodotto trovato in questa pagina. Fine o problema nel selettore.")
                 break # Esci se non ci sono elementi prodotto

            logging.info(f"Trovati {len(product_listing_items)} contenitori prodotto. Raccogliendo link, immagini e prezzi...")

            for i, product_elem in enumerate(product_listing_items):
                product_url = None # Inizializza a None
                image_url = 'N/A'
                price_listing = 'N/A'

                # Estrai il link alla pagina di dettaglio (Gestione errori specifica)
                try:
                    link_elem = product_elem.find_element(By.CSS_SELECTOR, PRODUCT_LINK_SELECTOR)
                    product_url = link_elem.get_attribute('href')
                except NoSuchElementException:
                    logging.warning(f"  Link prodotto ('{PRODUCT_LINK_SELECTOR}') non trovato nella card {i+1}. Skippato per URL/Dettaglio.")
                except Exception as e:
                    logging.error(f"  Errore imprevisto nell'estrarre link dalla card {i+1}: {e}")

                # Estrai l'URL dell'immagine dalla listing (Gestione errori specifica)
                try:
                    image_elem = product_elem.find_element(By.CSS_SELECTOR, PRODUCT_LISTING_IMAGE_SELECTOR)
                    image_url = image_elem.get_attribute('src')
                except NoSuchElementException:
                    logging.warning(f"  Immagine ('{PRODUCT_LISTING_IMAGE_SELECTOR}') non trovata nella card {i+1}. Userà N/A.")
                except Exception as e:
                    logging.error(f"  Errore imprevisto nell'estrarre immagine dalla card {i+1}: {e}")

                # Estrai il prezzo dalla listing (Gestione errori specifica, selettore più generale)
                try:
                    price_elem = product_elem.find_element(By.CSS_SELECTOR, PRODUCT_LISTING_PRICE_SELECTOR)
                    price_listing = price_elem.text.strip()
                except NoSuchElementException:
                    logging.warning(f"  Prezzo ('{PRODUCT_LISTING_PRICE_SELECTOR}') non trovato nella card {i+1}. Userà N/A.")
                except Exception as e:
                    logging.error(f"  Errore imprevisto nell'estrarre prezzo dalla card {i+1}: {e}")


                # Aggiungi alla lista SOLO se il link principale è stato trovato
                if product_url:
                     product_details_from_listing.append({
                         'detail_url': product_url,
                         'listing_image_url': image_url, # Immagine dalla listing (potrebbe essere N/A)
                         'listing_price': price_listing, # Prezzo dalla listing (potrebbe essere N/A)
                         'listing_index': i + 1
                     })
                # else: il warning specifico per il link non trovato è già stato loggato

            logging.info(f"Raccolti {len(product_details_from_listing)} URL di prodotti validi (su {len(product_listing_items)} contenitori trovati) da questa pagina di listing.")

            # Ora visita ogni URL raccolto per scrapare i dettagli
            logging.info("Inizio scraping pagine di dettaglio per i prodotti validi...")
            for i, product_info in enumerate(product_details_from_listing):
                 product_url = product_info['detail_url']
                 listing_image_url = product_info['listing_image_url']
                 listing_price = product_info['listing_price']
                 listing_index = product_info['listing_index']

                 logging.info(f"Processing product {i + 1}/{len(product_details_from_listing)} (Card {listing_index} from listing): {product_url}")

                 product_data = {
                     'listing_url': current_page_url,
                     'detail_url': product_url,
                     'image_url': listing_image_url, # Aggiungi l'URL immagine dalla listing
                     'price_listing': listing_price # Aggiungi il prezzo dalla listing
                 } # Inizializza con URL e Immagine/Prezzo dalla listing

                 try:
                     # Naviga alla pagina di dettaglio
                     driver.get(product_url)

                     # Attendi che un elemento chiave della pagina di dettaglio sia visibile
                     WebDriverWait(driver, WAIT_TIMEOUT).until(
                         ec.presence_of_element_located((By.CSS_SELECTOR, DETAIL_PAGE_TITLE_SELECTOR))
                     )
                     logging.info(f"  Pagina dettaglio caricata per {product_url}")

                     # --- Estrazione dati dalla PAGINA DI DETTAGLIO ---
                     # Titolo
                     try:
                         title_elem = driver.find_element(By.CSS_SELECTOR, DETAIL_PAGE_TITLE_SELECTOR)
                         product_data['title'] = title_elem.text.strip() if title_elem and title_elem.text else 'N/A'
                     except NoSuchElementException:
                         product_data['title'] = 'N/A'
                         logging.warning(f"  Titolo ('{DETAIL_PAGE_TITLE_SELECTOR}') non trovato su {product_url}")
                     except Exception as e:
                         logging.error(f"  Errore imprevisto nell'estrarre titolo su {product_url}: {e}")
                         product_data['title'] = 'N/A (extraction error)'


                     # Descrizione breve (cattura tutte le parti e uniscile)
                     short_desc_parts_text = []
                     try:
                         short_desc_elements = driver.find_elements(By.CSS_SELECTOR, DETAIL_PAGE_DESCRIPTION_SHORT_SELECTOR)
                         if short_desc_elements:
                             for part_elem in short_desc_elements:
                                 part_text = part_elem.text.strip()
                                 if part_text: # Aggiungi solo se non è vuoto
                                    short_desc_parts_text.append(part_text)
                             product_data['short_description'] = " ".join(short_desc_parts_text) if short_desc_parts_text else 'N/A'
                         else:
                              product_data['short_description'] = 'N/A'
                              logging.warning(f"  Nessuna descrizione breve trovata con selettore '{DETAIL_PAGE_DESCRIPTION_SHORT_SELECTOR}' su {product_url}")
                     except Exception as e:
                          logging.error(f"  Errore imprevisto nell'estrarre descrizione breve su {product_url}: {e}")
                          product_data['short_description'] = 'N/A (extraction error)'


                     # Descrizione completa
                     full_desc_text = 'N/A'
                     try:
                         full_desc_elem = driver.find_element(By.CSS_SELECTOR, DETAIL_PAGE_DESCRIPTION_FULL_SELECTOR)
                         full_desc_text = full_desc_elem.text.strip() if full_desc_elem and full_desc_elem.text else 'N/A'
                         # Potresti voler pulire ulteriormente il testo se contiene caratteri strani o troppi spazi/newline
                     except NoSuchElementException:
                         logging.warning(f"  Descrizione completa ('{DETAIL_PAGE_DESCRIPTION_FULL_SELECTOR}') non trovata su {product_url}")
                         full_desc_text = 'N/A'
                     except Exception as e:
                         logging.error(f"  Errore imprevisto nell'estrarre descrizione completa su {product_url}: {e}")
                         full_desc_text = 'N/A (extraction error)'

                     # Combina le descrizioni
                     combined_description_parts = []
                     if product_data['short_description'] != 'N/A':
                          combined_description_parts.append(f"Breve: {product_data['short_description']}")
                     if full_desc_text != 'N/A':
                          combined_description_parts.append(f"Completa: {full_desc_text}")

                     product_data['combined_description'] = " --- ".join(combined_description_parts) if combined_description_parts else 'N/A'

                     # Estrai prezzo dalla pagina dettaglio se necessario (usando un selettore corretto per la DETAIL PAGE)
                     # try:
                     #      price_detail_elem = driver.find_element(By.CSS_SELECTOR, 'SELETTORE_PREZZO_DETTAGLIO_REALE') # Sostituisci con il selettore corretto
                     #      product_data['price_detail'] = price_detail_elem.text.strip() if price_detail_elem and price_detail_elem.text else 'N/A'
                     # except NoSuchElementException:
                     #       product_data['price_detail'] = 'N/A'
                     #       logging.warning(f"  Prezzo dettaglio ('SELETTORE_PREZZO_DETTAGLIO_REALE') non trovato su {product_url}")
                     # except Exception as e:
                     #        logging.error(f"  Errore imprevisto nell'estrarre prezzo dettaglio su {product_url}: {e}")
                     #        product_data['price_detail'] = 'N/A (extraction error)'


                     all_product_data.append(product_data)
                     logging.info(f"  Dati estratti per '{product_data.get('title', product_url)}'")

                     # Torna alla pagina di listing
                     driver.back()
                     logging.info(f"  Tornato alla pagina di listing: {current_page_url}")

                     # Potrebbe essere utile una breve attesa dopo il back per stabilizzazione DOM
                     time.sleep(1) # Attesa breve e fissa, usala con cautela

                 except TimeoutException:
                     logging.error(f"  Timeout in caricamento o ricerca elementi critici su pagina dettaglio: {product_url}. Skippato.")
                     # Torna alla pagina di listing anche in caso di errore sulla pagina dettaglio
                     try: driver.back()
                     except: logging.warning("  Fallito tentativo di tornare indietro dopo errore dettaglio.")
                     time.sleep(1) # Breve attesa
                 except NoSuchElementException as e:
                     # Cattura specificamente NoSuchElementException per gli elementi critici della pagina dettaglio
                     logging.error(f"  Elemento critico non trovato (es. Titolo '{DETAIL_PAGE_TITLE_SELECTOR}') su pagina dettaglio: {product_url}. Dettagli: {e}. Skippato.")
                     # Torna alla pagina di listing anche in caso di errore sulla pagina dettaglio
                     try: driver.back()
                     except: logging.warning("  Fallito tentativo di tornare indietro dopo errore dettaglio.")
                     time.sleep(1) # Breve attesa
                 except Exception as e:
                     logging.error(f"  Errore generico nello scraping della pagina dettaglio {product_url}: {e}. Skippato.", exc_info=True)
                      # Torna alla pagina di listing anche in caso di errore sulla pagina dettaglio
                     try: driver.back()
                     except: logging.warning("  Fallito tentativo di tornare indietro dopo errore dettaglio.")
                     time.sleep(1) # Breve attesa


            logging.info(f"Completato elaborazione pagine di dettaglio per i link raccolti dalla pagina {current_page_url}.")

            # --- Gestione Paginazione ---
            # Questo blocco verrà eseguito solo una volta se usi ?limit=all
            # e uscirà dal loop perché non troverà il link "Successivo"
            next_page_link = None
            try:
                logging.info("Cercando il link di paginazione 'Pagina successiva'...")
                # Assicurati di essere nella finestra principale prima di cercare il link
                driver.switch_to.window(original_window_handle)
                # Attendi che il link "next" sia presente
                next_button = WebDriverWait(driver, WAIT_TIMEOUT).until(
                    ec.presence_of_element_located((By.CSS_SELECTOR, PAGINATION_NEXT_SELECTOR))
                )
                next_page_url = next_button.get_attribute('href')

                if next_page_url and next_page_url != current_page_url: # Evita loop infiniti
                     current_page_url = next_page_url
                     logging.info(f"Link 'Pagina successiva' trovato: {current_page_url}")
                     # Il loop while(current_page_url) gestirà la navigazione alla prossima pagina
                else:
                    logging.info("'Pagina successiva' link non trovato o è lo stesso della pagina attuale. Fine paginazione.")
                    current_page_url = None # Termina il loop

            except TimeoutException:
                logging.info("Nessun link 'Pagina successiva' trovato entro il timeout. Fine paginazione.")
                current_page_url = None # Termina il loop
            except NoSuchElementException:
                 logging.info("Selettore link 'Pagina successiva' non trovato. Fine paginazione.")
                 current_page_url = None # Termina il loop
            except Exception as e:
                 logging.error(f"Errore generico nel cercare il link di paginazione: {e}")
                 current_page_url = None # Termina il loop


    except WebDriverException as e: # Cattura gli errori generali di Selenium, inclusa la disconnessione dal driver
        logging.critical(f"ERRORE GRAVE: Si è verificato un errore Selenium (WebDriverException), probabilmente il driver è crashato o è diventato instabile. Dettagli: {e}", exc_info=True)
    except Exception as e:
        logging.critical(f"ERRORE GRAVE: Si è verificato un errore imprevisto durante lo scraping. Dettagli: {e}", exc_info=True)
    finally:
        # --- Pulizia ---
        if driver:
            logging.info("Chiusura browser Selenium.")
            driver.quit() # Chiude il browser e termina il driver
        else:
            logging.warning("Il driver non è stato inizializzato correttamente.")

        # --- Salvataggio dati ---
        logging.info(f"Totale prodotti raccolti: {len(all_product_data)}")
        if all_product_data:
            logging.info(f"--- Salvataggio dati in CSV: {CSV_FILENAME} ---")
            try:
                # Usa i nomi delle chiavi del primo dict come header CSV
                headers = all_product_data[0].keys() if all_product_data else []
                if headers:
                    with open(CSV_FILENAME, mode='w', newline='', encoding='utf-8') as file:
                        writer = csv.DictWriter(file, fieldnames=headers)
                        writer.writeheader()
                        writer.writerows(all_product_data)
                    logging.info("Dati salvati con successo.")
                else:
                     logging.warning("Nessun dato raccolto, CSV non creato.")

            except Exception as e:
                logging.error(f"Errore durante il salvataggio del file CSV: {e}")
        else:
            logging.warning("Nessun dato da salvare nel file CSV.")

        logging.info("--- Script completato. ---")

# --- Esecuzione ---
if __name__ == "__main__":
    scrape_products(BASE_URL)