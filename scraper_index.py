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
# Lista di URL iniziali delle pagine di elenco prodotti da cui iniziare lo scraping.
# Puoi aggiungere qui più URL se necessario.
START_URLS_FOR_LISTINGS = [
    "https://www.edilportale.com/aziende/index_836/prodotti/costruzione-consolidamento-e-rinforzo-s71877",
       "https://www.edilportale.com/aziende/index_836/prodotti/deumidificazione-s71876",
       "https://www.edilportale.com/aziende/index_836/prodotti/impermeabilizzazione-s71886",
       "https://www.edilportale.com/aziende/index_836/prodotti/isolamento-termico-s71991",
       "https://www.edilportale.com/aziende/index_836/prodotti/isolanti-acustici-s72130",
       "https://www.edilportale.com/aziende/index_836/prodotti/miglioramento-di-malte-e-cls-s71989",
       "https://www.edilportale.com/aziende/index_836/prodotti/posa-del-legno-s72127",
       "https://www.edilportale.com/aziende/index_836/prodotti/posa-di-ceramiche-pietre-naturali-e-composite-s71994",
       "https://www.edilportale.com/aziende/index_836/prodotti/preparazione-dei-fondi-di-posa-s72128",
       "https://www.edilportale.com/aziende/index_836/prodotti/primer-e-promotori-di-adesione-s71988",
       "https://www.edilportale.com/aziende/index_836/prodotti/protezione-e-decorazione-s71879",
       "https://www.edilportale.com/aziende/index_836/prodotti/regolarizzazione-e-finitura-delle-superfici-s71992",
       "https://www.edilportale.com/aziende/index_836/prodotti/ripristino-del-calcestruzzo-s71889",
       "https://www.edilportale.com/aziende/index_836/prodotti/sigillatura-s71990",
       "https://www.edilportale.com/aziende/index_836/prodotti/stuccatura-di-fughe-s72126"
    # Aggiungi altri URL di pagine di elenco qui se necessario
]
# Nome del file CSV di output
OUTPUT_CSV_FILE = "edilportale_prodotti.csv"

# URL base del sito per costruire URL completi
BASE_URL = "https://www.edilportale.com"

# --- Selettori CSS per gli elementi sulla pagina di ELENCO (pagina brand/categoria) ---
# Basati sugli snippet HTML che hai fornito per Edilportale.

# Selettore per ogni singolo contenitore prodotto nella lista (il blocco div)
# CONFERMATO dal tuo snippet.
PRODUCT_CONTAINER_SELECTOR_LISTING = "div.cell.item-cell"

# Selettore per il link alla pagina di dettaglio prodotto all'interno del blocco nella lista
# CONFERMATO dal tuo snippet (il link diretto figlio del container).
PRODUCT_DETAIL_LINK_SELECTOR_LISTING = "div.cell.item-cell > a"

# Selettore per il produttore/brand nella lista (dentro il container prodotto)
# CONFERMATO dal tuo snippet.
PRODUCT_BRAND_SELECTOR_LISTING = "span.product-manufacturer"


# Selettore per il link "Successiva" nella paginazione.
# Basato sull'ispezione della pagina fornita.
NEXT_PAGE_SELECTOR = "a.paginazione__link.paginazione__link--successiva[rel='next']"


# --- Selettori CSS per gli elementi sulla pagina di DETTAGLIO Prodotto ---
# Basati sugli snippet HTML che hai fornito per Edilportale.

# Selettore per il nome del prodotto nella pagina di dettaglio
# CONFERMATO dal tuo snippet.
PRODUCT_NAME_SELECTOR_DETAIL = "span.product-name"

# Selettore per la descrizione del prodotto
# CONFERMATO dal tuo snippet. Seleziona il paragrafo all'interno del div accordion-content.
PRODUCT_DESCRIPTION_SELECTOR_DETAIL = "div.accordion-content p"

# Selettore per l'immagine principale del prodotto nella pagina di dettaglio
# Seleziona l'img all'interno del div con id "product-image".
PRODUCT_IMAGE_SELECTOR_DETAIL = "div#product-image img"


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


def scrape_edilportale_detail_page(driver, product_data):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium
    ed estrae nome, descrizione e URL immagine, aggiornando il dizionario product_data.
    """
    detail_url = product_data["product url"]
    # print(f"  Navigazione pagina dettaglio: {detail_url}") # DEBUG

    try:
        driver.get(detail_url)
        # Attendi che un elemento chiave sulla pagina di dettaglio sia presente (es. il nome)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_NAME_SELECTOR_DETAIL)))
        # print("   Pagina di dettaglio caricata (nome trovato).") # DEBUG

        soup = get_soup_from_selenium(driver)
        if not soup:
             print("   Impossibile ottenere la soup dalla pagina di dettaglio.")
             return # Esci se non si ottiene la soup

        # Estrai il Nome del prodotto
        name_tag = soup.select_one(PRODUCT_NAME_SELECTOR_DETAIL)
        if name_tag:
            product_data["nome"] = name_tag.get_text(strip=True)
            # print(f"   Trovato Nome: {product_data['nome']}") # DEBUG


        # Estrai la Descrizione
        description_tag = soup.select_one(PRODUCT_DESCRIPTION_SELECTOR_DETAIL)
        if description_tag:
            # Estrai il testo mantenendo la formattazione base dei paragrafi se presenti
            description_text = description_tag.get_text(separator='\n', strip=True)
            if description_text:
                product_data["descrizione"] = description_text
                # print(f"   Trovata Descrizione (snippet): {product_detail_data['description'][:70]}...") # DEBUG


        # Estrai l'URL dell'immagine
        img_tag = soup.select_one(PRODUCT_IMAGE_SELECTOR_DETAIL)
        if img_tag and img_tag.has_attr('src'):
             image_src = img_tag['src']
             # Usa urljoin per costruire l'URL completo, gestisce la codifica
             if image_src and not image_src.startswith('data:'): # Ignora placeholder data:image
                 # Edilportale usa srcset, potresti voler prendere l'URL migliore da lì,
                 # ma src è una buona fallback e spesso sufficiente.
                 # Prendiamo l'attributo src o content se presente (come visto in altri snippet).
                 image_url = img_tag.get('content') or img_tag.get('src')
                 if image_url:
                     product_data["image url"] = urljoin(BASE_URL, image_url)
                     # print(f"   Trovata Immagine: {product_detail_data['image_url']}") # DEBUG


    # Cattura eccezioni specifiche di Selenium durante la navigazione della pagina di dettaglio
    except (TimeoutException, NoSuchElementException) as e:
        print(f"  Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina di dettaglio {detail_url}: {e}")
    except Exception as e:
        print(f"  Errore generico durante lo scraping della pagina di dettaglio {detail_url}: {e}")

    # Il dizionario product_data viene modificato direttamente (passato per riferimento)


def scrape_edilportale_listing_page(driver, listing_url):
     """
     Naviga a una pagina di elenco, raccoglie i dati base dei prodotti (URL e Brand),
     e trova l'URL della pagina successiva (se esiste tramite paginazione).
     """
     print(f"Navigazione Pagina Lista Prodotti per raccogliere URL e Brand: {listing_url}")
     driver.get(listing_url)

     # Attendi che la pagina carichi e che almeno un contenitore prodotto sia presente
     try:
         wait = WebDriverWait(driver, 20) # Attesa iniziale
         wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LISTING)))
         print("Pagina lista prodotti caricata (primo prodotto trovato).")
     except TimeoutException:
         print("Timeout nell'attesa dei prodotti nella lista. Potrebbe non esserci nulla su questa pagina o il selettore del contenitore prodotto è errato.")
         soup_listing_debug = get_soup_from_selenium(driver)
         if soup_listing_debug:
             print("Primi 2000 caratteri dell'HTML della pagina per debug (Timeout o nessun contenitore trovato):")
             print(soup_listing_debug.prettify()[:2000])
         return [], None # Restituisce lista vuota di dati e nessun URL successivo


     products_data_on_page = []

     # Ottieni l'HTML corrente della pagina
     soup_listing = get_soup_from_selenium(driver)
     if not soup_listing:
         print("Impossibile ottenere la soup dalla pagina di elenco.")
         return [], None # Restituisce lista vuota e nessun URL successivo

     # Trova tutti i contenitori prodotto nell'HTML corrente
     product_containers = soup_listing.select(PRODUCT_CONTAINER_SELECTOR_LISTING)
     print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR_LISTING}') su {listing_url}.")

     if not product_containers:
         print(f"Nessun contenitore prodotto trovato su {listing_url}. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR_LISTING}'.")
         print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
         print(soup_listing.prettify()[:2000])
         pass # Continua per cercare il link di paginazione

     for i, container in enumerate(product_containers):
         try:
             detail_link_tag = container.select_one(PRODUCT_DETAIL_LINK_SELECTOR_LISTING)
             brand_tag = container.select_one(PRODUCT_BRAND_SELECTOR_LISTING)

             detail_url = "N/A"
             brand_name = "N/A"

             if detail_link_tag and detail_link_tag.has_attr('href'):
                 detail_url = urljoin(BASE_URL, detail_link_tag['href'])

             if brand_tag:
                 brand_name = brand_tag.get_text(strip=True)

             # Aggiungi i dati base del prodotto
             if detail_url != "N/A": # Aggiungiamo solo prodotti per cui abbiamo l'URL
                 products_data_on_page.append({
                     "marca": brand_name,
                     "nome": "N/A", # Il nome verrà estratto dalla pagina di dettaglio
                     "descrizione": "N/A", # La descrizione verrà estratta dalla pagina di dettaglio
                     "image url": "N/A", # L'immagine verrà estratta dalla pagina di dettaglio
                     "product url": detail_url # L'URL del prodotto
                 })
             # else: Prodotto saltato perché manca l'URL

         except Exception as e:
             print(f"Errore nel raccogliere dati base dal contenitore prodotto {i+1} su {listing_url}: {e}. Salto.")
             continue

     print(f"Raccolti {len(products_data_on_page)} set di dati base (URL e Brand) su {listing_url}.")

     # Cerca il link per la pagina successiva
     next_page_link = soup_listing.select_one(NEXT_PAGE_SELECTOR)
     next_listing_url = None
     if next_page_link and next_page_link.has_attr('href'):
         relative_next_url = next_page_link['href']
         next_listing_url = urljoin(BASE_URL, relative_next_url)
         print(f"Trovato link pagina successiva: {next_listing_url}")
     else:
         print("Nessun link pagina successiva trovato.")

     return products_data_on_page, next_listing_url


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

        # Definisci l'ordine delle colonne come richiesto dall'utente
        keys = ["marca", "nome", "descrizione", "image url", "product url"]

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
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument("--headless") # Rimuovi il commento per eseguire senza finestra
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)


        # Lista per raccogliere TUTTI i dati base dei prodotti dalle pagine di elenco
        all_products_base_data = []
        seen_product_urls = set() # Usiamo un set per tenere traccia degli URL visti ed evitare duplicati

        print("\n--- Fase 1: Raccogli URL e Brand dalle Pagine di Elenco (con paginazione) ---")
        # Utilizziamo gli URL di partenza forniti
        listing_urls_to_process = list(START_URLS_FOR_LISTINGS) # Copia la lista iniziale
        processed_listing_urls = set() # Per evitare loop se la paginazione è mal configurata

        while listing_urls_to_process:
            current_listing_url = listing_urls_to_process.pop(0) # Prendi il primo URL dalla lista

            if current_listing_url in processed_listing_urls:
                 print(f"URL di elenco già processato: {current_listing_url}. Salto.")
                 continue
            processed_listing_urls.add(current_listing_url)


            print(f"\n--- Elaborazione Pagina Lista Prodotti: {current_listing_url} ---")

            # Chiama la funzione per scrapare i dati base dalla pagina corrente e trovare il link alla pagina successiva
            products_data_on_page, next_listing_url = scrape_edilportale_listing_page(driver, current_listing_url)

            # Aggiungi i dati base trovati alla lista complessiva, evitando duplicati basati sull'URL
            for product_data in products_data_on_page:
                if product_data["product url"] != "N/A" and product_data["product url"] not in seen_product_urls:
                    all_products_base_data.append(product_data)
                    seen_product_urls.add(product_data["product url"])
                # else: Prodotto saltato perché manca l'URL o è già stato visto

            # Aggiungi la pagina successiva alla lista da processare se esiste e non è già stata visitata
            if next_listing_url and next_listing_url not in processed_listing_urls and next_listing_url not in listing_urls_to_process:
                 listing_urls_to_process.append(next_listing_url)
                 print(f"Aggiunto link pagina successiva alla coda: {next_listing_url}")
            elif next_listing_url:
                 print(f"Link pagina successiva {next_listing_url} già in coda o processato. Salto.")


            if listing_urls_to_process: # Solo se ci sono altri URL da processare in coda (inclusa la prossima pagina)
                 time.sleep(2) # Pausa tra la navigazione delle pagine di elenco


        print(f"\n--- Fine Fase 1. Raccolti {len(all_products_base_data)} set di dati base unici (URL e Brand). ---")


        # --- Fase 2: Scraping dei dettagli da ogni pagina prodotto ---
        print("\n--- Fase 2: Scraping Dettagli Prodotti ---")

        # Ottieni l'handle della finestra corrente (dopo l'ultima pagina di elenco visitata)
        original_window = driver.current_window_handle

        for i, product_data in enumerate(all_products_base_data): # Iteriamo sui dati base raccolti
            detail_url = product_data["product url"]
            print(f"Scraping dettaglio prodotto {i+1}/{len(all_products_base_data)}: {detail_url}")

            try:
                # Apri l'URL di dettaglio in una nuova scheda
                driver.execute_script("window.open(arguments[0]);", detail_url)
                time.sleep(1) # Breve pausa

                # Passa alla nuova scheda
                driver.switch_to.window(driver.window_handles[-1])

                # Scrape i dati dalla pagina di dettaglio e aggiorna il dizionario product_data
                scrape_edilportale_detail_page(driver, product_data)

                # Il dizionario product_data in all_products_base_data è stato aggiornato direttamente

                # Chiudi la scheda corrente
                driver.close()

                # Torna alla scheda originale
                driver.switch_to.window(original_window)

                time.sleep(1) # Breve pausa tra lo scraping di pagine di dettaglio

            except Exception as e:
                print(f"Errore durante lo scraping della pagina di dettaglio {detail_url}: {e}. Salto.")
                # Assicurati di tornare alla finestra originale anche in caso di errore
                try:
                     if len(driver.window_handles) > 1:
                         driver.close()
                     driver.switch_to.window(original_window)
                except:
                     pass
                # Non facciamo continue qui, perché l'errore non interrompe il loop,
                # semplicemente i dati di dettaglio per questo prodotto potrebbero rimanere N/A.


        print(f"\n--- Fine Fase 2. Scraping dettagli completato. ---")
        print(f"Totale prodotti con dati base raccolti: {len(all_products_base_data)}")
        # Salviamo tutti i dati raccolti, inclusi quelli di dettaglio
        save_to_csv(all_products_base_data, OUTPUT_CSV_FILE)

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