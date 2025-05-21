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
import time # Importa time per le pause

# Impostazioni iniziali
# URL della pagina del brand Kapriol su Adipietro Commerciale.
# Questa è la pagina che contiene (tramite lazy loading) tutti i prodotti del brand.
START_URLS_FOR_LISTINGS = [
    "https://adipietro.it/brand/3-kapriol"
    # Se ci fossero altre pagine del brand Kapriol (es. con sottocategorie che richiedono scrolling),
    # potresti aggiungerle qui.
]
# Nome del file CSV di output
OUTPUT_CSV_FILE = "kapriol_prodotti.csv"

# URL base del sito per costruire URL completi
BASE_URL = "https://adipietro.it"

# --- Limite Prodotti ---
# Imposta il numero massimo di prodotti da raccogliere e scrapare i dettagli.
# Impostato a 30 per il test come richiesto. Rimuovi o aumenta per scrapare di più.
PRODUCT_LIMIT = 334

# --- Selettori CSS per gli elementi sulla pagina di ELENCO (la pagina del brand) ---
# Basati sulla struttura comune di siti e-commerce e confermati dai tuoi snippet precedenti.
# VERIFICA questi selettori sulla pagina https://adipietro.it/brand/3-kapriol
# se riscontri problemi nel trovare i prodotti.

# Selettore per ogni singolo contenitore prodotto nella lista (la card o blocco)
PRODUCT_CONTAINER_SELECTOR_LISTING = "article.product-miniature"

# Selettore per il link alla pagina di dettaglio prodotto all'interno del blocco nella lista
PRODUCT_DETAIL_LINK_SELECTOR_LISTING = "div.thumbnail-container a"

# Selettore per il link "Successivo" nella paginazione
# Sulla pagina del brand con lazy loading esteso, la paginazione tradizionale
# potrebbe non essere presente o rilevante, ma manteniamo il selettore per sicurezza.
# VERIFICA questo selettore sulla pagina https://adipietro.it/brand/3-kapriol.
NEXT_PAGE_SELECTOR = "a.next.js-search-link" # Potrebbe essere anche a[rel="next"] o simile


# --- Selettori CSS per gli elementi sulla pagina di DETTAGLIO Prodotto ---
# Basati sugli snippet HTML che hai fornito (dalle pagine di dettaglio).

# Selettore per il titolo del prodotto nella pagina di dettaglio
PRODUCT_TITLE_SELECTOR_DETAIL = "h1.product_name"

# Selettore per gli elementi della descrizione (div che contiene la descrizione breve)
PRODUCT_DESCRIPTION_SELECTOR_DETAIL = "div.product_desc"

# Selettore per l'immagine principale del prodotto nella pagina di dettaglio
# Seleziona l'img all'interno di picture all'interno del div image-container
PRODUCT_IMAGE_SELECTOR_DETAIL = "div.images-container picture img"


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


def scrape_kapriol_detail_page(driver, detail_url):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium
    ed estrae nome, descrizione e URL immagine.
    """
    # print(f"  Navigazione pagina dettaglio: {detail_url}") # DEBUG
    product_detail_data = {
        "name": "N/A",
        "brand": "Kapriol", # Marca fissa
        "description": "N/A",
        "price": "N/A", # Il prezzo potrebbe non essere sempre visibile o con un selettore standard
        "image_url": "N/A",
        "product_page_url": detail_url # L'URL della pagina di dettaglio stessa
    }

    try:
        # Usa il driver Selenium per navigare alla pagina di dettaglio
        driver.get(detail_url)
        # Attendi che un elemento chiave sulla pagina di dettaglio sia presente (es. il titolo)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_TITLE_SELECTOR_DETAIL)))
        # print("   Pagina di dettaglio caricata (titolo trovato).") # DEBUG

        # Ottieni l'HTML dopo il caricamento completo
        soup = get_soup_from_selenium(driver)
        if not soup:
             print("   Impossibile ottenere la soup dalla pagina di dettaglio.")
             return product_detail_data # Restituisce dati parziali se non si ottiene la soup


        # Estrai il Nome del prodotto
        name_tag = soup.select_one(PRODUCT_TITLE_SELECTOR_DETAIL)
        if name_tag:
            product_detail_data["name"] = name_tag.get_text(strip=True)
            # print(f"   Trovato Nome: {product_detail_data['name']}") # DEBUG


        # Estrai la Descrizione
        description_tag = soup.select_one(PRODUCT_DESCRIPTION_SELECTOR_DETAIL)
        if description_tag:
            # Estrai il testo mantenendo la formattazione base dei paragrafi se presenti
            description_text = description_tag.get_text(separator='\n', strip=True)
            if description_text:
                product_detail_data["description"] = description_text
                # print(f"   Trovata Descrizione (snippet): {product_detail_data['description'][:70]}...") # DEBUG
            # else: Nessun testo nella descrizione, rimane N/A
        # else: Elementi descrizione non trovati, rimane N/A


        # Estrai l'URL dell'immagine
        # Usiamo il selettore più specifico che hai fornito
        img_tag = soup.select_one(PRODUCT_IMAGE_SELECTOR_DETAIL)
        if img_tag and img_tag.has_attr('src'):
             image_src = img_tag['src']
             # Usa urljoin per costruire l'URL completo, gestisce la codifica
             if image_src and not image_src.startswith('data:'): # Ignora placeholder data:image
                 # Preferiamo l'attributo data-full-size-image-url se presente, altrimenti usiamo src.
                 full_size_image_src = img_tag.get('data-full-size-image-url')
                 if full_size_image_src:
                     product_detail_data["image_url"] = urljoin(BASE_URL, full_size_image_src)
                 else:
                     product_detail_data["image_url"] = urljoin(BASE_URL, image_src)

                 # print(f"   Trovata Immagine: {product_detail_data['image_url']}") # DEBUG
             # else: image_url rimane N/A se placeholder o vuoto
        # else: img_tag non trovato o senza src, image_url rimane N/A


    # Cattura eccezioni specifiche di Selenium durante la navigazione della pagina di dettaglio
    except (TimeoutException, NoSuchElementException) as e:
        print(f"  Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina di dettaglio {detail_url}: {e}")
    except Exception as e:
        print(f"  Errore generico durante lo scraping della pagina di dettaglio {detail_url}: {e}")

    return product_detail_data


def scrape_kapriol_listing_page_for_product_urls(driver, listing_url, product_limit):
     """
     Naviga a una pagina di elenco (o brand), scorre per caricare i prodotti fino al limite
     o finché non ce ne sono più, raccoglie gli URL e trova l'URL pagina successiva.
     """
     print(f"Navigazione Pagina Lista Prodotti e scrolling per caricare (limite: {product_limit} prodotti): {listing_url}")
     driver.get(listing_url)

     # Attendi che la pagina carichi e che almeno un contenitore prodotto sia presente
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
         return [], None # Restituisce lista vuota di URL e nessun URL successivo

     # --- Implementazione dello scrolling per il lazy loading ---
     last_product_count = 0
     consecutive_no_growth = 0 # Contatore per scroll senza nuovi prodotti
     max_consecutive_no_growth = 5 # Numero di scroll senza crescita per fermarsi
     scroll_attempts = 0
     max_scroll_attempts = 100 # Limite massimo di tentativi di scroll assoluto
     scroll_pause_time = 2 # Secondi da attendere dopo ogni scroll

     print("Inizio scrolling per caricare prodotti...")

     # Raccogli URL progressivamente durante lo scrolling per controllare il limite
     product_detail_urls_on_page = []
     seen_urls_on_page = set()

     while True:
         driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
         time.sleep(scroll_pause_time) # Attendi che i nuovi prodotti si carichino

         scroll_attempts += 1

         # Ottieni tutti i contenitori prodotto attuali
         product_containers = driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LISTING)
         current_product_count = len(product_containers)
         print(f"  Dopo scroll {scroll_attempts}: prodotti trovati finora: {current_product_count}")

         # Raccogli i nuovi URL aggiunti durante questo scroll
         newly_added_urls = []
         for container in product_containers:
             try:
                 detail_link_tag = container.find_element(By.CSS_SELECTOR, PRODUCT_DETAIL_LINK_SELECTOR_LISTING)
                 detail_url = detail_link_tag.get_attribute('href')
                 if detail_url:
                      full_detail_url = urljoin(BASE_URL, detail_url)
                      if full_detail_url not in seen_urls_on_page:
                           newly_added_urls.append(full_detail_url)
                           seen_urls_on_page.add(full_detail_url)
             except NoSuchElementException:
                  continue # Salta se il link non si trova nel container (non dovrebbe succedere con selettori corretti)
             except Exception as e:
                  print(f"Errore durante la raccolta URL in scrolling: {e}. Salto.")
                  continue

         product_detail_urls_on_page.extend(newly_added_urls)

         # Controlla se abbiamo raggiunto il limite di prodotti
         if product_limit is not None and len(product_detail_urls_on_page) >= product_limit:
              print(f"Limite di {product_limit} prodotti raggiunto. Interruzione scrolling.")
              break # Esci dal loop di scrolling

         # Logica per fermare lo scrolling se non vengono caricati nuovi prodotti
         if current_product_count == last_product_count:
             consecutive_no_growth += 1
             print(f"  Nessun nuovo prodotto caricato. Conteggio consecutivo senza crescita: {consecutive_no_growth}")
         else:
             consecutive_no_growth = 0 # Reimposta il contatore se nuovi prodotti sono stati trovati

         last_product_count = current_product_count # Aggiorna il conteggio per il prossimo ciclo

         # Condizioni di uscita dal loop di scrolling
         if consecutive_no_growth >= max_consecutive_no_growth or scroll_attempts >= max_scroll_attempts:
              print("Criterio di interruzione scrolling raggiunto (nessuna nuova crescita o max tentativi).")
              break


     print(f"Scrolling completato. Totale URL raccolti durante scrolling: {len(product_detail_urls_on_page)}")
     # --- Fine implementazione scrolling ---

     # Cerca il link per la pagina successiva dopo lo scrolling (potrebbe non esserci)
     soup_listing = get_soup_from_selenium(driver)
     next_listing_url = None
     if soup_listing:
         next_page_link = soup_listing.select_one(NEXT_PAGE_SELECTOR)
         if next_page_link and next_page_link.has_attr('href') and urljoin(BASE_URL, next_page_link['href']) != listing_url: # Evita loop se il link punta alla stessa pagina
              relative_next_url = next_page_link['href']
              next_listing_url = urljoin(BASE_URL, relative_next_url)
              print(f"Potenziale link pagina successiva trovato: {next_listing_url} (verificare se necessario seguirlo)")

     # Restituisce gli URL raccolti durante lo scrolling.
     # La paginazione tradizionale non viene seguita in questo scenario per concentrarsi sulla pagina brand.
     return product_detail_urls_on_page, None # next_listing_url è None perché non seguiamo paginazione esplicita qui


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
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument("--headless") # Rimuovi il commento per eseguire senza finestra
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)


        all_scraped_products = []
        # Lista per raccogliere TUTTI gli URL dei prodotti dalla pagina brand
        all_product_detail_urls_collected = []

        print(f"\n--- Fase 1: Raccogli URL Prodotti dalla Pagina Brand (con scrolling, limite {PRODUCT_LIMIT}) ---") # Messaggio aggiornato
        # Utilizziamo direttamente l'URL della pagina brand fornito
        listing_urls_to_scrape = list(START_URLS_FOR_LISTINGS) # Copia la lista iniziale

        # Processa la pagina brand, gestendo lo scrolling e il limite prodotti
        while listing_urls_to_scrape and (PRODUCT_LIMIT is None or len(all_product_detail_urls_collected) < PRODUCT_LIMIT):
            current_listing_url = listing_urls_to_scrape.pop(0) # Prendi il primo URL dalla lista

            print(f"\n--- Elaborazione Pagina Lista Prodotti: {current_listing_url} ---")

            # Chiama la funzione modificata che include lo scrolling e il limite
            # Passiamo il limite rimanente per la raccolta URL su questa pagina
            remaining_limit = PRODUCT_LIMIT - len(all_product_detail_urls_collected) if PRODUCT_LIMIT is not None else None
            detail_urls_on_page, next_listing_url = scrape_kapriol_listing_page_for_product_urls(driver, current_listing_url, remaining_limit)

            # Aggiungi gli URL trovati nella pagina corrente alla lista complessiva
            all_product_detail_urls_collected.extend(detail_urls_on_page)

            # Non seguiamo next_listing_url in questo scenario per concentrarci sulla singola pagina brand,
            # a meno che tu non aggiunga esplicitamente altri URL a START_URLS_FOR_LISTINGS.


        print(f"\n--- Fine Fase 1. Raccolti {len(all_product_detail_urls_collected)} URL di prodotti (potrebbero esserci duplicati). ---")
        # Rimuovi eventuali duplicati dalla lista finale di URL di dettaglio
        all_product_detail_urls_unique = list(set(all_product_detail_urls_collected))
        # Applica il limite finale nel caso in cui la raccolta durante lo scrolling abbia superato leggermente il limite
        if PRODUCT_LIMIT is not None:
             all_product_detail_urls_unique = all_product_detail_urls_unique[:PRODUCT_LIMIT]

        print(f"Dopo rimozione duplicati e applicazione limite: {len(all_product_detail_urls_unique)} URL unici da scrapare.")


        # --- Fase 2: Scraping di ogni pagina di dettaglio prodotto ---
        print("\n--- Fase 2: Scraping Dettagli Prodotti ---")

        # Ottieni l'handle della finestra corrente
        original_window = driver.current_window_handle

        # Iteriamo solo sugli URL unici (e limitati) raccolti nella Fase 1
        for i, detail_url in enumerate(all_product_detail_urls_unique):
            print(f"Scraping dettaglio prodotto {i+1}/{len(all_product_detail_urls_unique)}: {detail_url}")

            try:
                # Apri l'URL di dettaglio in una nuova scheda
                driver.execute_script("window.open(arguments[0]);", detail_url)
                time.sleep(1) # Breve pausa

                # Passa alla nuova scheda
                driver.switch_to.window(driver.window_handles[-1])

                # Scrape i dati dalla pagina di dettaglio
                product_detail = scrape_kapriol_detail_page(driver, detail_url)

                # Aggiungi i dati estratti alla lista principale solo se il nome è stato trovato
                if product_detail and product_detail.get("name") != "N/A":
                    all_scraped_products.append(product_detail)
                    # Non controlliamo più il limite qui, è gestito dalla lista di URL in input a questo loop

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
                continue


        print(f"\n--- Fine Fase 2. Scraping dettagli completato. ---")
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