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
# Il singolo URL di partenza per la lista di prodotti.
START_URL = "https://www.edilportale.com/aziende/saint-gobain-weber_1892/prodotti"

# Nome del file CSV di output
OUTPUT_CSV_FILE = "edilportale_prodotti_weber.csv"

# URL base del sito per costruire URL completi
BASE_URL = "https://www.edilportale.com"

# --- Selettori CSS per gli elementi sulla pagina di ELENCO (pagina brand/categoria) ---
# Basati sugli snippet HTML che hai fornito per Edilportale.

# Selettore per ogni singolo contenitore prodotto nella lista (il blocco div)
PRODUCT_CONTAINER_SELECTOR_LISTING = "div.cell.item-cell"

# Selettore per il link alla pagina di dettaglio prodotto all'interno del blocco nella lista
PRODUCT_DETAIL_LINK_SELECTOR_LISTING = "div.cell.item-cell > a"

# Selettore per il produttore/brand nella lista (dentro il container prodotto)
PRODUCT_BRAND_SELECTOR_LISTING = "span.product-manufacturer"


# Selettore per il link "Avanti" (Next) nella paginazione.
NEXT_BUTTON_SELECTOR = "li.pagination-next.pagination-direction a"

# Selettore per il banner dei cookie (il contenitore)
COOKIE_WALL_SELECTOR = "div#cookie-wall.cookie-wall-container"
# Selettore per il bottone che accetta o chiude il banner dei cookie.
# Questo è un tentativo basato su selettori comuni; potrebbe richiedere aggiustamenti.
# Cerchiamo un bottone o link all'interno del cookie wall che contenga il testo "Accetto" o "OK".
COOKIE_ACCEPT_BUTTON_SELECTOR = f'{COOKIE_WALL_SELECTOR} button, {COOKIE_WALL_SELECTOR} a' # Iniziamo cercando bottoni o link generici all'interno del wall


# --- Selettori CSS per gli elementi sulla pagina di DETTAGLIO Prodotto ---
# Basati sugli snippet HTML che hai fornito per Edilportale.

# Selettore per il nome del prodotto nella pagina di dettaglio
PRODUCT_NAME_SELECTOR_DETAIL = "span.product-name"

# Selettore per la descrizione del prodotto
PRODUCT_DESCRIPTION_SELECTOR_DETAIL = "div.accordion-content p"

# Selettore per l'immagine principale del prodotto nella pagina di dettaglio
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

def dismiss_cookie_wall(driver):
    """
    Tenta di chiudere il banner dei cookie se presente.
    """
    try:
        # Attendi brevemente la potenziale presenza del cookie wall
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, COOKIE_WALL_SELECTOR))
        )
        print("Banner cookie rilevato.")

        # Prova a trovare e cliccare il bottone di accettazione.
        # Iteriamo su possibili selettori o elementi per trovare il giusto bottone.
        accept_button = None
        try:
            # Cerca un bottone o link all'interno del cookie wall
            possible_buttons = driver.find_elements(By.CSS_SELECTOR, COOKIE_ACCEPT_BUTTON_SELECTOR)
            for button in possible_buttons:
                # Controlla il testo del bottone (case-insensitive e trimming)
                if button.text.strip().lower() in ['accetto', 'ok', 'chiudi', 'accetta i cookie']:
                    accept_button = button
                    break # Trovato il bottone, esci dal loop

            if accept_button and accept_button.is_displayed():
                 print(f"Trovato bottone di accettazione cookie con testo: '{accept_button.text.strip()}'. Tentativo di click.")
                 # Usa JavaScript per il click per superare possibili intercettazioni minori
                 driver.execute_script("arguments[0].click();", accept_button)
                 # Attendi che il banner scompaia
                 WebDriverWait(driver, 5).until(
                     EC.invisibility_of_element_located((By.CSS_SELECTOR, COOKIE_WALL_SELECTOR))
                 )
                 print("Banner cookie chiuso con successo.")
            else:
                 print("Bottone di accettazione cookie non trovato o non visibile all'interno del banner.")
                 # Potresti voler provare a cliccare l'overlay o fare qualcos'altro qui se il bottone specifico non funziona.
                 # Per ora, logghiamo e proseguiamo, potrebbe non essere sempre bloccante.

        except NoSuchElementException:
            print("Bottone di accettazione cookie non trovato con i selettori specificati.")
            # Potrebbe non esserci un bottone standard o il selettore è sbagliato.

        except Exception as e:
            print(f"Errore durante la gestione del banner cookie: {e}")
            # Continua anche in caso di errore nella gestione del cookie, non vogliamo bloccare tutto.

    except TimeoutException:
        # Il banner dei cookie non è apparso entro il timeout, prosegui.
        # print("Banner cookie non rilevato (Timeout).") # DEBUG
        pass
    except Exception as e:
         print(f"Errore generico nel controllo presenza cookie wall: {e}")
         pass


def scrape_edilportale_detail_page(driver, product_data):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium
    ed estrae nome, descrizione e URL immagine, aggiornando il dizionario product_data.
    """
    detail_url = product_data["product url"]
    # print(f"  Navigazione pagina dettaglio: {detail_url}") # DEBUG

    try:
        # Selenium è già sulla pagina di dettaglio (ci navighiamo cliccando il link in una nuova scheda)
        # Quindi non serve driver.get(detail_url) di nuovo qui.

        # Attendi che un elemento chiave sulla pagina di dettaglio sia presente (es. il nome)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_NAME_SELECTOR_DETAIL)))
        # print("   Pagina di dettaglio caricata (nome trovato).") # DEBUG

        # Gestisci il banner cookie anche sulla pagina di dettaglio, potrebbe riapparire
        dismiss_cookie_wall(driver)


        soup = get_soup_from_selenium(driver)
        if not soup:
             print("   Impossibile ottenere la soup dalla pagina di dettaglio.")
             return # Esci se non si ottiene la soup

        # Estrai il Nome del prodotto
        name_tag = soup.select_one(PRODUCT_NAME_SELECTOR_DETAIL)
        if name_tag:
            product_data["nome"] = name_tag.get_text(strip=True)


        # Estrai la Descrizione
        # MODIFICA INIZIA QUI
        description_paragraphs = soup.select(PRODUCT_DESCRIPTION_SELECTOR_DETAIL) # Usa select per prendere TUTTI i <p>
        description_text = ""
        if description_paragraphs:
            # Unisci il testo di tutti i paragrafi, separandoli con un ritorno a capo
            # Usa get_text(strip=True) su ogni paragrafo per pulire spazi bianchi inutili
            description_text = "\n".join([p.get_text(strip=True) for p in description_paragraphs if p.get_text(strip=True)]) # Filtra paragrafi vuoti

        if description_text: # Controlla se il testo unito non è vuoto
             product_data["descrizione"] = description_text
        else:
             product_data["descrizione"] = "N/A" # Imposta a N/A se non è stato trovato alcun testo nei paragrafi
        # MODIFICA FINISCE QUI


        # Estrai l'URL dell'immagine
        img_tag = soup.select_one(PRODUCT_IMAGE_SELECTOR_DETAIL)
        if img_tag and img_tag.has_attr('src'):
             image_src = img_tag['src']
             if image_src and not image_src.startswith('data:'):
                 image_url = img_tag.get('content') or img_tag.get('src')
                 if image_url:
                     product_data["image url"] = urljoin(BASE_URL, image_url)


    except (TimeoutException, NoSuchElementException) as e:
        print(f"  Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina di dettaglio {detail_url}: {e}")
    except Exception as e:
        print(f"  Errore generico durante lo scraping della pagina di dettaglio {detail_url}: {e}")


def scrape_edilportale_listing_page(driver):
     """
     Raccoglie i dati base dei prodotti (URL e Brand) dalla pagina di elenco corrente.
     Il driver Selenium DEVE già essere sulla pagina.
     """
     # Non facciamo driver.get(listing_url) qui, perché il driver è già sulla pagina

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
         return [] # Restituisce lista vuota di dati

     products_data_on_page = []

     # Ottieni l'HTML corrente della pagina
     soup_listing = get_soup_from_selenium(driver)
     if not soup_listing:
         print("Impossibile ottenere la soup dalla pagina di elenco corrente.")
         return [] # Restituisce lista vuota

     # Trova tutti i contenitori prodotto nell'HTML corrente
     product_containers = soup_listing.select(PRODUCT_CONTAINER_SELECTOR_LISTING)
     print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR_LISTING}') sulla pagina corrente.")

     if not product_containers:
         print(f"Nessun contenitore prodotto trovato sulla pagina corrente. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR_LISTING}'.")
         print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
         print(soup_listing.prettify()[:2000])
         return [] # Restituisce lista vuota

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

             if detail_url != "N/A": # Aggiungiamo solo prodotti per cui abbiamo l'URL
                 products_data_on_page.append({
                     "marca": brand_name,
                     "nome": "N/A",
                     "descrizione": "N/A",
                     "image url": "N/A",
                     "product url": detail_url
                 })

         except Exception as e:
             print(f"Errore nel raccogliere dati base dal contenitore prodotto {i+1}: {e}. Salto.")
             continue

     print(f"Raccolti {len(products_data_on_page)} set di dati base (URL e Brand) dalla pagina corrente.")

     return products_data_on_page


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

        keys = ["marca", "nome", "descrizione", "image url", "product url"]

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


        all_products_base_data = []
        seen_product_urls = set()

        print(f"\n--- Fase 1: Raccogli URL e Brand dalle Pagine di Elenco (cliccando 'Avanti') ---")

        current_listing_url = START_URL
        page_count = 0

        while True: # Loop infinito che verrà interrotto manualmente
            page_count += 1
            print(f"\n--- Elaborazione Pagina Lista Prodotti (cliccando Avanti) Pagina {page_count}: {current_listing_url} ---")

            # Naviga alla pagina corrente (solo per la prima iterazione e dopo il click di "Avanti")
            driver.get(current_listing_url)

            # --- Gestisci il banner dei cookie ---
            dismiss_cookie_wall(driver)
            # --- Fine gestione cookie ---

            # Chiama la funzione per scrapare i dati base dalla pagina corrente
            products_data_on_page = scrape_edilportale_listing_page(driver)

            # Aggiungi i dati base trovati alla lista complessiva, evitando duplicati basati sull'URL
            for product_data in products_data_on_page:
                if product_data["product url"] != "N/A" and product_data["product url"] not in seen_product_urls:
                    all_products_base_data.append(product_data)
                    seen_product_urls.add(product_data["product url"])


            # --- Gestione Clic Paginazione "Avanti" ---
            next_button = None
            try:
                # Attendi che il bottone "Avanti" sia presente e cliccabile
                # Aumentiamo un po' l'attesa per il bottone "Avanti" dopo il caricamento
                wait = WebDriverWait(driver, 15)
                next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, NEXT_BUTTON_SELECTOR)))
                print("Trovato bottone 'Avanti'.")
            except (NoSuchElementException, TimeoutException):
                print("Bottone 'Avanti' non trovato o non cliccabile. Fine paginazione.")
                next_button = None # Assicurati che sia None se non trovato

            if next_button:
                try:
                    # Ottieni l'URL attuale prima del click
                    old_url = driver.current_url
                    print(f"Clicco su 'Avanti'...")
                    # Usa JavaScript per il click, a volte più affidabile con elementi coperti o scroll non perfetti
                    driver.execute_script("arguments[0].click();", next_button)

                    # Attendi che l'URL cambi, indicando che la nuova pagina è stata caricata
                    # Aumentiamo l'attesa per il cambio URL
                    wait.until(EC.url_changes(old_url))
                    # Aggiorna l'URL corrente con l'URL della nuova pagina
                    current_listing_url = driver.current_url
                    print(f"Navigato alla pagina successiva: {current_listing_url}")

                    time.sleep(3) # Aumenta la pausa per sicurezza dopo il caricamento della nuova pagina e prima della prossima iterazione

                except Exception as e:
                    print(f"Errore cliccando il bottone Avanti o caricando la pagina successiva: {e}. Interruzione paginazione.")
                    break # Interrompi il loop se il click o il caricamento falliscono
            else:
                break # Esci dal loop se il bottone "Avanti" non è stato trovato


        print(f"\n--- Fine Fase 1. Raccolti {len(all_products_base_data)} set di dati base unici (URL e Brand) da tutte le pagine processate. ---")


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
                print(f"Errore durante lo scraping della pagina di dettaglio {detail_url}: {e}. Salto e continuo.")
                # Assicurati di tornare alla finestra originale anche in caso di errore
                try:
                     if len(driver.window_handles) > 1:
                         driver.close()
                     driver.switch_to.window(original_window)
                except:
                     pass
                # Non facciamo continue qui, l'errore è gestito internamente al try/except

        print(f"\n--- Fine Fase 2. Scraping dettagli completato. ---")
        print(f"Totale prodotti con dati base e dettaglio raccolti: {len(all_products_base_data)}")
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