import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup

# Impostazioni iniziali
# Lista per contenere gli URL delle pagine di elenco da cui iniziare lo scraping.
SAIT_LISTING_URLS = [
    "https://www.sait-abr.com/it/65-catalogo-prodotti"
    # Aggiungi qui altri URL di pagine di elenco prodotti Sait da scrapare, se necessario
    # Esempio: "https://www.sait-abr.com/it/altra-categoria"
]
OUTPUT_CSV_FILE = "sait_prodotti.csv"

# --- Selettori CSS per gli elementi sulla pagina di ELENCO ---
# Basati sull'HTML che hai fornito e l'ispezione di una pagina di elenco

# Selettore per ogni singolo blocco prodotto nella lista
PRODUCT_CONTAINER_SELECTOR_LISTING = "article.product-miniature"

# Selettore per il link alla pagina di dettaglio prodotto all'interno del blocco nella lista
PRODUCT_DETAIL_LINK_SELECTOR_LISTING = "a.product-thumbnail"

# Selettore per il link "Successivo" nella paginazione (trovato ispezionando il sito)
NEXT_PAGE_SELECTOR = "a.next.js-search-link"


# --- Selettori CSS per gli elementi sulla pagina di DETTAGLIO Prodotto ---
# Basati sull'HTML che hai fornito

# Selettore per il titolo del prodotto nella pagina di dettaglio
PRODUCT_TITLE_SELECTOR_DETAIL = "h1.titolo-prodotto"

# Selettore per la descrizione del prodotto nella pagina di dettaglio
# Trova il div contenitore della descrizione per itemprop e poi i paragrafi all'interno
PRODUCT_DESCRIPTION_CONTAINER_SELECTOR_DETAIL = "div[itemprop='description']"
PRODUCT_DESCRIPTION_PARAGRAPH_SELECTOR_DETAIL = "p"


# Selettore per l'immagine principale del prodotto nella pagina di dettaglio
# Si trova nell'img con classe js-qv-product-cover dentro il div product-cover
PRODUCT_IMAGE_SELECTOR_DETAIL = "div.product-cover img.js-qv-product-cover"


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


def scrape_sait_detail_page(driver, detail_url):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium
    ed estrae nome, descrizione e URL immagine.
    """
    print(f"  Navigazione pagina dettaglio: {detail_url}")
    product_detail_data = {
        "name": "N/A",
        "brand": "SAIT", # Marca fissa
        "description": "N/A",
        "price": "N/A", # Non sembra esserci un prezzo visibile
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
        description_container = soup.select_one(PRODUCT_DESCRIPTION_CONTAINER_SELECTOR_DETAIL)
        if description_container:
            # Concatena il testo di tutti i paragrafi all'interno del contenitore descrizione
            paragraphs = description_container.select(PRODUCT_DESCRIPTION_PARAGRAPH_SELECTOR_DETAIL)
            description_text = "\n".join([p.get_text(strip=True) for p in paragraphs])
            if description_text:
                product_detail_data["description"] = description_text
                # print(f"   Trovata Descrizione (snippet): {product_detail_data['description'][:70]}...") # DEBUG
            # else: Nessun paragrafo trovato, description rimane N/A


        # Estrai l'URL dell'immagine
        img_tag = soup.select_one(PRODUCT_IMAGE_SELECTOR_DETAIL)
        if img_tag and img_tag.has_attr('src'):
             image_src = img_tag['src']
             # Gli URL delle immagini sembrano già assoluti
             if image_src and not image_src.startswith('data:'): # Ignora placeholder data:image
                 product_detail_data["image_url"] = image_src
                 # print(f"   Trovata Immagine: {product_detail_data['image_url']}") # DEBUG
             # else: image_url rimane N/A se placeholder o vuoto
        # else: img_tag non trovato o senza src, image_url rimane N/A


    # Cattura eccezioni specifiche di Selenium durante la navigazione della pagina di dettaglio
    except (TimeoutException, NoSuchElementException) as e:
        print(f"  Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina di dettaglio {detail_url}: {e}")
    except Exception as e:
        print(f"  Errore generico durante lo scraping della pagina di dettaglio {detail_url}: {e}")

    return product_detail_data


def scrape_sait_listing_page(driver, listing_url):
    """
    Naviga a una pagina di elenco, raccoglie gli URL dei prodotti,
    e trova l'URL della pagina successiva (se esiste).
    """
    print(f"Navigazione alla pagina di elenco: {listing_url}")
    driver.get(listing_url)

    # Attendi che la pagina carichi e che almeno un contenitore prodotto sia presente
    try:
        wait = WebDriverWait(driver, 20) # Attesa iniziale più lunga
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LISTING)))
        print("Pagina di elenco caricata (primo prodotto trovato).")
    except TimeoutException:
        print("Timeout nell'attesa dei prodotti nella lista. Potrebbe non esserci nulla da scrapare su questa pagina.")
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
                # Gli URL sembrano già assoluti su questo sito
                # if detail_url.startswith('/'):
                #      detail_url = "https://www.sait-abr.com" + detail_url # Aggiungi URL base se necessario
                product_detail_urls_on_page.append(detail_url)
                # print(f"  Raccolto URL dettaglio: {detail_url}") # DEBUG
            # else: link dettaglio non trovato per questo contenitore, salta
        except Exception as e:
            print(f"Errore nel raccogliere l'URL dettaglio dal contenitore prodotto {i+1} su {listing_url}: {e}. Salto.")
            continue

    print(f"Raccolti {len(product_detail_urls_on_page)} URL di pagine di dettaglio su {listing_url}.")

    # Cerca il link per la pagina successiva
    next_page_link = soup_listing.select_one(NEXT_PAGE_SELECTOR)
    next_listing_url = None
    if next_page_link and next_page_link.has_attr('href'):
        next_listing_url = next_page_link['href']
        # Gli URL di paginazione sembrano già assoluti

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
        PRODUCT_LIMIT = 511 # Imposta il limite di prodotti da scrapare


        print(f"Scraping limitato ai primi {PRODUCT_LIMIT} prodotti.")

        # Processa ogni URL di elenco fornito
        for start_listing_url in SAIT_LISTING_URLS:
            current_listing_url = start_listing_url

            # Loop per gestire la paginazione delle pagine di elenco
            while current_listing_url:
                if len(all_scraped_products) >= PRODUCT_LIMIT:
                    print(f"Limite di {PRODUCT_LIMIT} prodotti raggiunto. Interruzione scraping.")
                    break # Esci dal ciclo di paginazione se il limite è raggiunto

                print(f"\n--- Scraping Pagina di Elenco: {current_listing_url} ---")

                # Scrape la pagina di elenco per ottenere gli URL di dettaglio e l'URL della pagina successiva
                detail_urls_on_page, next_listing_url = scrape_sait_listing_page(driver, current_listing_url)

                # Scrape i dettagli per ogni URL di prodotto trovato su questa pagina di elenco
                if detail_urls_on_page:
                    print(f"\nScraping dei dettagli per {len(detail_urls_on_page)} prodotti su {current_listing_url}...")
                    for k, detail_url in enumerate(detail_urls_on_page):
                        if len(all_scraped_products) >= PRODUCT_LIMIT:
                            print(f"Limite di {PRODUCT_LIMIT} prodotti raggiunto. Interruzione scraping dei dettagli.")
                            break # Esci dal loop dei dettagli se il limite è raggiunto

                        product_detail = scrape_sait_detail_page(driver, detail_url)
                        # Aggiungi i dati estratti alla lista principale solo se il nome è stato trovato
                        if product_detail and product_detail.get("name") != "N/A":
                            all_scraped_products.append(product_detail)
                            print(f"  Aggiunto prodotto {len(all_scraped_products)}: {product_detail.get('name')}") # DEBUG
                        # else: Prodotto saltato (nome N/A)

                        time.sleep(1) # Breve pausa tra lo scraping di pagine di dettaglio

                else:
                    print(f"Nessun URL di dettaglio prodotto trovato sulla pagina di elenco {current_listing_url}.")


                # Passa all'URL della pagina di elenco successiva per la prossima iterazione del ciclo while
                # Controlla di nuovo il limite prima di passare alla pagina successiva
                if len(all_scraped_products) < PRODUCT_LIMIT:
                    current_listing_url = next_listing_url
                    if current_listing_url:
                        print(f"\nPassando alla pagina di elenco successiva: {current_listing_url}")
                        time.sleep(3) # Pausa tra le pagine di elenco
                    else:
                        print("\nNessuna pagina di elenco successiva trovata per questa categoria.")
                else:
                    current_listing_url = None # Imposta a None per uscire dal ciclo di paginazione


            # Esci dal loop delle URL iniziali se il limite è stato raggiunto
            if len(all_scraped_products) >= PRODUCT_LIMIT:
                break


        print(f"\nCompletato lo scraping per {len(SAIT_LISTING_URLS)} URL iniziali (o fino al limite di {PRODUCT_LIMIT} prodotti).")
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
