import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup
from urllib.parse import urljoin # Utile per costruire URL completi

# Impostazioni iniziali
# Lista di URL iniziali per trovare il menu delle categorie.
# Lo scraper troverà automaticamente le altre categorie da queste pagine.
# Abbiamo cambiato l'URL di partenza per quello di Yamato.
YAMATO_START_URLS_FOR_CATEGORIES = [
    "https://www.yamato.ferritalia.it/catalogo/settore/1.05/desc/Utensili-a-batteria"
    # Puoi aggiungere qui altre URL di pagine del catalogo Yamato che sai contengono il menu completo delle categorie, se necessario.
]
# Nome del file CSV di output
OUTPUT_CSV_FILE = "yamato_prodotti.csv"

# --- Selettori CSS per gli elementi sulla pagina di ELENCO (Categoria) ---
# Basati sull'HTML del sito Papillon fornito e ASSUMENDO che la struttura sia simile per Yamato.
# VERIFICA questi selettori se lo script non funziona come previsto.

# Selettore per ogni singolo contenitore prodotto nella lista (la card)
PRODUCT_CONTAINER_SELECTOR_LISTING = "div.card"

# Selettore per il link alla pagina di dettaglio prodotto all'interno del blocco nella lista
# Questo link si trova dentro il div con classe 'catalogue-overlay'
PRODUCT_DETAIL_LINK_SELECTOR_LISTING = "div.catalogue-overlay a"

# Selettore per il link "Successivo" nella paginazione
# Basato sull'HTML fornito (simile a Maurer/Papillon)
NEXT_PAGE_SELECTOR = "a.page-link[aria-label='Next']"

# --- Selettore CSS per i link delle CATEGORIE nel menu laterale ---
# Cerca tutti i link (a) che sono figli diretti (>) degli elementi lista (li)
# che sono figli diretti (>) del ul con classi fa-ul e ul-settore, e che hanno un attributo href.
# VERIFICA questo selettore.
CATEGORY_LINK_SELECTOR = "ul.fa-ul.ul-settore > li > a[href]"


# --- Selettori CSS per gli elementi sulla pagina di DETTAGLIO Prodotto ---
# Basati sull'HTML del sito Papillon fornito e ASSUMENDO che la struttura sia simile per Yamato.
# VERIFICA questi selettori se lo script non funziona come previsto.

# Selettore per il titolo del prodotto nella pagina di dettaglio
PRODUCT_TITLE_SELECTOR_DETAIL = "h1.proddetails-title-white"

# Selettore per gli elementi della descrizione (lista di <li>)
PRODUCT_DESCRIPTION_SELECTOR_DETAIL = "ul.my-4.ml-4.proddetails-vals-white li"

# Selettore per l'immagine principale del prodotto nella pagina di dettaglio
PRODUCT_IMAGE_SELECTOR_DETAIL = "img.img-fluid"


# URL base del sito per costruire URL completi
# Modificato per il sito Yamato
BASE_URL = "https://www.yamato.ferritalia.it"


# Configurazione di Selenium WebDriver
# Inizializza il driver una volta sola nel blocco main
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


def scrape_yamato_detail_page(driver, detail_url):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium
    ed estrae nome, descrizione e URL immagine.
    """
    # print(f"  Navigazione pagina dettaglio: {detail_url}") # DEBUG
    product_detail_data = {
        "name": "N/A",
        "brand": "Yamato", # Marca fissa
        "description": "N/A",
        "price": "N/A", # Non sembra esserci un prezzo visibile sul sito pubblico
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


        # Estrai la Descrizione (concatena gli elementi della lista)
        description_items = soup.select(PRODUCT_DESCRIPTION_SELECTOR_DETAIL)
        if description_items:
            description_text = "\n".join([item.get_text(strip=True) for item in description_items])
            if description_text:
                product_detail_data["description"] = description_text
                # print(f"   Trovata Descrizione (snippet): {product_detail_data['description'][:70]}...") # DEBUG
            # else: Nessun testo nella descrizione, rimane N/A
        # else: Elementi descrizione non trovati, rimane N/A


        # Estrai l'URL dell'immagine
        img_tag = soup.select_one(PRODUCT_IMAGE_SELECTOR_DETAIL)
        if img_tag and img_tag.has_attr('src'):
             image_src = img_tag['src']
             # Usa urljoin per costruire l'URL completo, gestisce la codifica
             if image_src and not image_src.startswith('data:'): # Ignora placeholder data:image
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


def scrape_yamato_category_page_for_product_urls(driver, listing_url):
     """
     Naviga a una pagina di elenco, raccoglie gli URL dei prodotti su quella pagina,
     e trova l'URL della pagina successiva (se esiste).
     Non scrape i dettagli qui.
     """
     print(f"Navigazione Pagina di Elenco per raccogliere URL prodotti: {listing_url}")
     driver.get(listing_url)

     # Attendi che la pagina carichi e che almeno un contenitore prodotto sia presente
     try:
         wait = WebDriverWait(driver, 20) # Attesa iniziale più lunga
         wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LISTING)))
         print("Pagina di elenco caricata (primo prodotto trovato).")
     except TimeoutException:
         print("Timeout nell'attesa dei prodotti nella lista. Potrebbe non esserci nulla su questa pagina.")
         return [], None # Restituisce lista vuota di URL e nessun URL successivo


     # Raccogli gli URL delle pagine di dettaglio da questa pagina di elenco
     product_detail_urls_on_page = []

     # Ottieni l'HTML corrente della pagina dopo il caricamento iniziale
     soup_listing = get_soup_from_selenium(driver)
     if not soup_listing:
         print("Impossibile ottenere la soup dalla pagina di elenco.")
         return [], None # Restituisce lista vuota e nessun URL successivo

     # Trova tutti i contenitori prodotto nell'HTML corrente
     product_containers = soup_listing.select(PRODUCT_CONTAINER_SELECTOR_LISTING)
     print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR_LISTING}') su {listing_url}.")

     if not product_containers:
         print(f"Nessun contenitore prodotto trovato su {listing_url}. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR_LISTING}'.")
         # Stampa una parte dell'HTML per debuggare se non trova contenitori
         print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
         print(soup_listing.prettify()[:2000])
         # Anche se non trova prodotti, controlla se c'è un link alla pagina successiva
         pass # Continua per cercare il link di paginazione

     for i, container in enumerate(product_containers):
         try:
             detail_link_tag = container.select_one(PRODUCT_DETAIL_LINK_SELECTOR_LISTING)
             if detail_link_tag and detail_link_tag.has_attr('href'):
                 detail_url = detail_link_tag['href']
                 # Usa urljoin per costruire l'URL completo, gestisce la codifica
                 full_detail_url = urljoin(BASE_URL, detail_url)
                 product_detail_urls_on_page.append(full_detail_url)
                 # print(f"  Raccolto URL dettaglio: {full_detail_url}") # DEBUG
             # else: link dettaglio non trovato per questo contenitore, salta
         except Exception as e:
             print(f"Errore nel raccogliere l'URL dettaglio dal contenitore prodotto {i+1} su {listing_url}: {e}. Salto.")
             continue

     print(f"Raccolti {len(product_detail_urls_on_page)} URL di pagine di dettaglio su {listing_url}.")

     # Cerca il link per la pagina successiva
     next_page_link = soup_listing.select_one(NEXT_PAGE_SELECTOR)
     next_listing_url = None
     if next_page_link and next_page_link.has_attr('href'):
         relative_next_url = next_page_link['href']
         # Usa urljoin per costruire l'URL completo della prossima pagina di elenco
         next_listing_url = urljoin(BASE_URL, relative_next_url)
         # print(f"Trovato link pagina successiva: {next_listing_url}") # DEBUG
     # else: print("Nessun link pagina successiva trovato.") # DEBUG


     return product_detail_urls_on_page, next_listing_url


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
        # Rimosso: PRODUCT_TOTAL_LIMIT = 50 # Imposta il limite totale di prodotti da scrapare


        # Rimosso: print(f"Scraping limitato ai primi {PRODUCT_TOTAL_LIMIT} prodotti totali.") # Messaggio rimosso

        # --- Fase 1: Raccogliere gli URL di TUTTE le categorie nell'ordine in cui appaiono ---
        print("\n--- Fase 1: Raccolta URL Categorie ---")
        # Usiamo una lista per mantenere l'ordine
        category_urls_ordered = []
        # Usiamo un set temporaneo per evitare duplicati durante la raccolta
        seen_category_urls = set()


        # Visita le URL iniziali per trovare il menu delle categorie
        for start_url in YAMATO_START_URLS_FOR_CATEGORIES: # Modificato qui
             print(f"Visitando {start_url} per trovare link categorie...")
             driver.get(start_url)
             try:
                 # Attendi che il menu delle categorie sia visibile
                 # Aggiungiamo un'attesa più specifica per un numero minimo di link se possibile
                 wait = WebDriverWait(driver, 15)
                 wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, CATEGORY_LINK_SELECTOR)))
                 print("Menu categorie trovato.")

                 # Trova tutti i link delle categorie principali
                 category_link_elements = driver.find_elements(By.CSS_SELECTOR, CATEGORY_LINK_SELECTOR)
                 print(f"Trovati {len(category_link_elements)} link di categoria.")

                 # Raccogli gli URL nell'ordine in cui sono trovati
                 for link_element in category_link_elements:
                     relative_url = link_element.get_attribute('href')
                     if relative_url: # Verifica se l'attributo href esiste e non è vuoto
                         full_url = urljoin(BASE_URL, relative_url)
                         # Aggiungi l'URL alla lista solo se non l'abbiamo già visto
                         if full_url not in seen_category_urls:
                             category_urls_ordered.append(full_url)
                             seen_category_urls.add(full_url) # Aggiungi al set dei visti


             except TimeoutException:
                 print(f"Timeout nell'attesa del menu categorie su {start_url}. Salto questa URL iniziale.")
             except Exception as e:
                 print(f"Errore durante la raccolta dei link categorie da {start_url}: {e}")

             time.sleep(2) # Pausa tra la visita delle URL iniziali


        print(f"\n--- Fine Fase 1. Raccolti {len(category_urls_ordered)} URL di categorie uniche e ordinate. ---")
        # La lista category_urls_ordered contiene gli URL nell'ordine desiderato
        category_urls_list = category_urls_ordered
        # Rimosso: print(f"Lista categorie da scrapare: {category_urls_list}") # Rimosso debug lista categorie


        # --- Fase 2: Scraping di ogni categoria e dei suoi prodotti ---
        print("\n--- Fase 2: Scraping Prodotti per Categoria ---")
        for category_url in category_urls_list:
            # Rimosso: if len(all_scraped_products) >= PRODUCT_TOTAL_LIMIT:
            # Rimosso: print(f"Limite totale di {PRODUCT_TOTAL_LIMIT} prodotti raggiunto. Interruzione scraping delle categorie.")
            # Rimosso: break # Esci dal loop delle categorie se il limite è raggiunto

            print(f"\n--- Elaborazione Categoria: {category_url} ---")

            # Raccogli tutti gli URL dei prodotti per questa categoria (gestendo la paginazione)
            all_product_detail_urls_in_category = []
            current_listing_url = category_url

            while current_listing_url:
                 # Rimosso: Raccogli un po' di URL in più rispetto al limite totale per sicurezza prima di interrompere la raccolta URL
                 # Rimosso: if len(all_scraped_products) + len(all_product_detail_urls_in_category) >= PRODUCT_TOTAL_LIMIT + 50:
                 # Rimosso: print(f"Avvicinamento al limite totale di {PRODUCT_TOTAL_LIMIT} prodotti. Interruzione raccolta URL per questa categoria.")
                 # Rimosso: break # Interrompi la raccolta URL se stiamo per superare il limite

                 detail_urls_on_page, next_listing_url = scrape_yamato_category_page_for_product_urls(driver, current_listing_url) # Modificato qui
                 all_product_detail_urls_in_category.extend(detail_urls_on_page)

                 current_listing_url = next_listing_url
                 if current_listing_url:
                      time.sleep(2) # Pausa tra le pagine di elenco durante la raccolta URL


            print(f"Raccolti {len(all_product_detail_urls_in_category)} URL di prodotti per la categoria {category_url}.")

            # Ora visita ogni URL di dettaglio raccolto per scrapare i dati completi
            print("Inizio scraping dei dettagli dei prodotti per questa categoria...")

            # Ottieni l'handle della finestra corrente (dopo l'ultima pagina di elenco visitata)
            original_window = driver.current_window_handle

            for j, detail_url in enumerate(all_product_detail_urls_in_category):
                # Rimosso: if len(all_scraped_products) >= PRODUCT_TOTAL_LIMIT:
                # Rimosso: print(f"Limite totale di {PRODUCT_TOTAL_LIMIT} prodotti raggiunto. Interruzione scraping dei dettagli.")
                # Rimosso: break # Esci dal loop dei dettagli se il limite è raggiunto

                try:
                    # Apri l'URL di dettaglio in una nuova scheda
                    driver.execute_script("window.open(arguments[0]);", detail_url)
                    time.sleep(1) # Breve pausa per permettere alla nuova scheda di aprirsi

                    # Passa alla nuova scheda
                    driver.switch_to.window(driver.window_handles[-1])
                    # print(f"  Passato alla nuova scheda per {detail_url}") # DEBUG

                    # Scrape i dati dalla pagina di dettaglio
                    product_detail = scrape_yamato_detail_page(driver, detail_url) # Modificato qui

                    # Aggiungi i dati estratti alla lista principale solo se il nome è stato trovato
                    if product_detail and product_detail.get("name") != "N/A":
                        all_scraped_products.append(product_detail)
                        print(f"  Aggiunto prodotto {len(all_scraped_products)} (Totale): {product_detail.get('name')}") # DEBUG
                    # else: Prodotto saltato (nome N/A)


                    # Chiudi la scheda corrente
                    driver.close()
                    # print("  Scheda chiusa.") # DEBUG

                    # Torna alla scheda originale (la pagina di elenco della categoria, o l'ultima pagina visitata)
                    driver.switch_to.window(original_window)
                    # print("  Tornato alla scheda originale.") # DEBUG

                    time.sleep(1) # Breve pausa tra lo scraping di pagine di dettaglio

                except Exception as e:
                    print(f"Errore durante lo scraping della pagina di dettaglio {detail_url}: {e}. Salto.")
                    # Assicurati di tornare alla finestra originale anche in caso di errore
                    try:
                         # Prova a chiudere la scheda corrente se è ancora aperta
                         if len(driver.window_handles) > 1:
                             driver.close()
                         # Torna alla finestra originale
                         driver.switch_to.window(original_window)
                    except:
                         pass # Ignora errori nella gestione delle finestre in caso di errore critico
                    continue # Continua con il prossimo URL di dettaglio

            print(f"Completato scraping dettagli per categoria {category_url}. Totale prodotti raccolti finora: {len(all_scraped_products)}")
            # Rimosso: Controlla di nuovo il limite totale dopo aver processato una categoria
            # Rimosso: if len(all_scraped_products) >= PRODUCT_TOTAL_LIMIT:
            # Rimosso: print(f"Limite totale di {PRODUCT_TOTAL_LIMIT} prodotti raggiunto dopo la categoria {category_url}. Interruzione.")
            # Rimosso: break # Esci dal loop delle categorie


        print(f"\n--- Fine Fase 2. Scraping completato. ---") # Messaggio aggiornato
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