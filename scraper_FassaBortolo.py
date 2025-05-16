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
# Lista per contenere gli URL delle pagine di categoria da scrapare.
# Ho inserito qui tutti i link che hai fornito.
FASSABORTOLO_URLS = [
    "https://www.fassabortolo.it/it/prodotti/-/p/6/1/sistema-bio-architettura",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/6/sistema-muratura",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/19/sistema-deumidificante",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/11/sistema-intonaci",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/23/sistema-ripristino-del-calcestruzzo",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/29/sistema-finiture",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/26/sistema-consolidamento-e-rinforzo-strutturale",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/33/sistema-colore",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/45/sistema-cappotto-fassatherm",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/52/sistema-gypsotech",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/58/sistema-posa-pavimenti-e-rivestimenti",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/65/sistema-underground",
    "https://www.fassabortolo.it/it/prodotti/-/p/6/94/sistema-materiali-di-cava-e-micronizzati"
]
OUTPUT_CSV_FILE = "fassabortolo_prodotti.csv"

# --- Selettori CSS per gli elementi sulla pagina di categoria ---
# Basati sull'HTML che hai fornito

# Selettore per l'intestazione dell'accordion che apre la sezione
ACCORDION_HEADER_SELECTOR = "dt a.open-accordion"

# Selettore per ogni singolo blocco prodotto all'interno di una sezione aperta
PRODUCT_CONTAINER_SELECTOR_LISTING = "div.subcontainer"

# Selettore per il link alla pagina di dettaglio prodotto all'interno del blocco prodotto
# Questo link si trova dentro il div con classe 'over'
PRODUCT_DETAIL_LINK_SELECTOR_LISTING = "div.over a"


# --- Selettori CSS per gli elementi sulla pagina di DETTAGLIO Prodotto ---
# Basati sull'HTML che hai fornito

# Selettore per il titolo del prodotto nella pagina di dettaglio
PRODUCT_TITLE_SELECTOR_DETAIL = "div.box-header h1 span"

# Selettore per la descrizione del prodotto nella pagina di dettaglio
PRODUCT_DESCRIPTION_SELECTOR_DETAIL = "div.product-descrizione span p"

# Selettore per l'immagine del prodotto nella pagina di dettaglio
PRODUCT_IMAGE_SELECTOR_DETAIL = "div.product-detail-right a.popup img"


# Configurazione di Selenium WebDriver
# ASSICURATI DI AVER SCARICATO IL DRIVER DEL BROWSER E CHE SIA NEL TUO PATH DI SISTEMA
# O SPECIFICA IL PERCORSO COMPLETO AL DRIVER QUI.
# Esegui in modalità visibile per debuggare inizialmente, poi puoi passare a headless
# chrome_options = webdriver.ChromeOptions()
# chrome_options.add_argument("--headless") # Rimuovi il commento per eseguire senza finestra
# chrome_options.add_argument("--no-sandbox")
# chrome_options.add_argument("--disable-dev-shm-usage")
# driver = webdriver.Chrome(options=chrome_options)

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


def scrape_product_detail(driver, detail_url):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium
    ed estrae nome, descrizione e URL immagine.
    """
    print(f"  Navigazione pagina dettaglio: {detail_url}")
    product_detail_data = {
        "name": "N/A",
        "brand": "Fassa Bortolo", # Marca fissa
        "description": "N/A",
        "price": "N/A", # Non sembra esserci un prezzo visibile
        "image_url": "N/A",
        "product_page_url": detail_url # L'URL della pagina di dettaglio stessa
    }

    try:
        # Usa il driver Selenium per navigare alla pagina di dettaglio
        driver.get(detail_url)
        # Attendi che il titolo del prodotto sia presente (segno che la pagina è caricata)
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


        # Estrai la Descrizione dettagliata
        description_tag = soup.select_one(PRODUCT_DESCRIPTION_SELECTOR_DETAIL)
        if description_tag:
            product_detail_data["description"] = description_tag.get_text(strip=True)
            # print(f"   Trovata Descrizione (snippet): {product_detail_data['description'][:70]}...") # DEBUG


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


def scrape_fassabortolo_category(driver, category_url):
    """
    Naviga alla pagina di categoria, apre gli accordion, raccoglie gli URL dei prodotti
    e poi visita ogni URL di dettaglio per estrarre i dati completi.
    """
    print(f"Navigazione alla pagina di categoria: {category_url}")
    driver.get(category_url)

    # Attendi che la pagina carichi e che almeno un accordion header sia presente
    try:
        wait = WebDriverWait(driver, 20) # Attesa iniziale più lunga
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ACCORDION_HEADER_SELECTOR)))
        print("Pagina di categoria caricata (accordion header trovato).")
    except TimeoutException:
        print("Timeout nell'attesa degli accordion header. Potrebbe non esserci nulla da scrapare su questa pagina.")
        return [] # Restituisce lista vuota se non trova accordion

    # Trova tutti gli accordion header
    accordion_headers = driver.find_elements(By.CSS_SELECTOR, ACCORDION_HEADER_SELECTOR)
    print(f"Trovati {len(accordion_headers)} accordion headers.")

    # Clicca su ogni accordion header per espandere le sezioni
    for i, header in enumerate(accordion_headers):
        try:
            # Scrolla l'header nella vista
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", header)
            time.sleep(0.5) # Breve pausa dopo lo scroll

            # Attendi che l'header sia cliccabile
            wait = WebDriverWait(driver, 5) # Breve attesa per il click
            clickable_header = wait.until(EC.element_to_be_clickable(header))

            # Clicca sull'header
            clickable_header.click()
            print(f"Cliccato sull'accordion header {i+1}/{len(accordion_headers)}.")

            # Attendi un breve periodo per permettere al contenuto di caricarsi dinamicamente
            time.sleep(2) # Potrebbe essere necessario aggiustare questa pausa

        except (ElementClickInterceptedException, StaleElementReferenceException, TimeoutException) as e:
            print(f"Errore nel cliccare sull'accordion header {i+1}: {e}. Continuo con i prossimi.")
            continue # Continua anche se un click fallisce
        except Exception as e:
            print(f"Errore generico nel cliccare sull'accordion header {i+1}: {e}. Continuo con i prossimi.")
            continue


    # Ora che tutti gli accordion dovrebbero essere aperti, raccogli gli URL dei prodotti
    print("\nRaccogliere gli URL delle pagine di dettaglio prodotto...")
    all_product_detail_urls = []

    # Ottieni l'HTML completo della pagina dopo aver aperto gli accordion
    soup_after_accordions = get_soup_from_selenium(driver)
    if not soup_after_accordions:
         print("Impossibile ottenere la soup dopo aver aperto gli accordion. Non posso raccogliere URL.")
         return []

    # Trova tutti i contenitori prodotto nell'HTML completo
    product_containers = soup_after_accordions.select(PRODUCT_CONTAINER_SELECTOR_LISTING)
    print(f"Trovati {len(product_containers)} contenitori prodotto nell'HTML dopo aver aperto gli accordion.")


    for i, container in enumerate(product_containers):
        try:
            detail_link_tag = container.select_one(PRODUCT_DETAIL_LINK_SELECTOR_LISTING)
            if detail_link_tag and detail_link_tag.has_attr('href'):
                detail_url = detail_link_tag['href']
                # Gli URL sembrano già assoluti su questo sito, ma aggiungiamo un controllo base
                # if detail_url.startswith('/'):
                #      detail_url = "https://www.fassabortolo.it" + detail_url # Aggiungi URL base se necessario
                all_product_detail_urls.append(detail_url)
                # print(f"  Raccolto URL dettaglio: {detail_url}") # DEBUG
            # else: link dettaglio non trovato per questo contenitore, salta
        except Exception as e:
            print(f"Errore nel raccogliere l'URL dettaglio dal contenitore prodotto {i+1}: {e}. Salto.")
            continue


    print(f"\nRaccolti {len(all_product_detail_urls)} URL di pagine di dettaglio prodotto.")

    # Ora visita ogni URL di dettaglio per scrapare i dati completi
    all_products_data = []
    print("\nInizio scraping delle pagine di dettaglio prodotto...")

    # Ottieni l'handle della finestra corrente (la pagina di categoria)
    original_window = driver.current_window_handle

    for j, detail_url in enumerate(all_product_detail_urls):
        try:
            # Apri l'URL di dettaglio in una nuova scheda
            driver.execute_script("window.open(arguments[0]);", detail_url)
            time.sleep(1) # Breve pausa per permettere alla nuova scheda di aprirsi

            # Passa alla nuova scheda
            driver.switch_to.window(driver.window_handles[-1])
            # print(f"  Passato alla nuova scheda per {detail_url}") # DEBUG

            # Scrape i dati dalla pagina di dettaglio
            product_detail = scrape_product_detail(driver, detail_url)

            # Aggiungi i dati estratti alla lista principale solo se il nome è stato trovato
            if product_detail and product_detail.get("name") != "N/A":
                all_products_data.append(product_detail)
                # print(f"  Aggiunto prodotto: {product_detail.get('name')}") # DEBUG
            # else: Prodotto saltato (nome N/A)


            # Chiudi la scheda corrente
            driver.close()
            # print("  Scheda chiusa.") # DEBUG

            # Torna alla scheda originale della pagina di categoria
            driver.switch_to.window(original_window)
            # print("  Tornato alla scheda originale.") # DEBUG

            time.sleep(1) # Breve pausa tra lo scraping di pagine di dettaglio

        except Exception as e:
            print(f"Errore durante lo scraping della pagina di dettaglio {detail_url}: {e}. Salto.")
            # Assicurati di tornare alla finestra originale anche in caso di errore
            try:
                 driver.close()
                 driver.switch_to.window(original_window)
            except:
                 pass # Ignora errori nella gestione delle finestre in caso di errore critico
            continue # Continua con il prossimo URL di dettaglio

    return all_products_data


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
        driver = webdriver.Chrome() # O webdriver.Firefox(), webdriver.Edge(), ecc.

        all_scraped_products = []

        # Itera su ogni URL di categoria nella lista
        for category_url in FASSABORTOLO_URLS:
            print(f"\n--- Elaborazione Categoria: {category_url} ---")
            products_from_category = scrape_fassabortolo_category(driver, category_url)
            all_scraped_products.extend(products_from_category) # Aggiunge i prodotti trovati alla lista totale
            time.sleep(3) # Pausa tra le categorie

        # Salva tutti i dati raccolti da tutte le categorie in un unico file CSV
        print(f"\nCompletato lo scraping di {len(FASSABORTOLO_URLS)} categorie.")
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
