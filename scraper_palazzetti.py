import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from bs4 import BeautifulSoup
from urllib.parse import urljoin # Utile per costruire URL completi

# Impostazioni iniziali
# URL della pagina iniziale con le macro-categorie
PALAZZETTI_INITIAL_URL = "https://palazzetti.it/prodotti/"
OUTPUT_CSV_FILE = "palazzetti_prodotti.csv"

# --- Selettori CSS per gli elementi ---

# Selettore per ogni contenitore di macro-categoria, categoria o prodotto nelle liste
# Sembra essere lo stesso per i primi due livelli
LISTING_ITEM_CONTAINER_SELECTOR = "div.col-12.col-sm-6.col-md-4.col-lg-3"
# Selettore per il link all'interno del contenitore di lista (macro, categoria, o prodotto)
LISTING_ITEM_LINK_SELECTOR = "a[href]" # Cerca qualsiasi link con href all'interno del container

# --- Pagine di Dettaglio Prodotto ---
# Selettore per il titolo del prodotto nella pagina di dettaglio
PRODUCT_NAME_SELECTOR_DETAIL = "h1.entry-title.product__title"
# Selettore per il div contenitore della descrizione generale
PRODUCT_DESCRIPTION_CONTAINER_SELECTOR_DETAIL = "div.tab-pane.fade#approfondimento"
# Selettore per l'immagine principale nella pagina di dettaglio
PRODUCT_IMAGE_SELECTOR_DETAIL = "div.carousel-inner img"
# Selettore per il div contenitore delle dimensioni
PRODUCT_DIMENSIONS_SELECTOR_DETAIL = "div.product__dim.mt-4"
# Selettore per lo span contenente il valore della classe energetica
PRODUCT_ENERGY_CLASS_SELECTOR_DETAIL = "div.classe_energetica_container span.classe_energetica_value"
# Selettore per il corpo della tabella delle specifiche tecniche
PRODUCT_TECH_SPECS_TABLE_BODY_SELECTOR_DETAIL = "div#dettagli-tecnici table.table tbody"


# URL base del sito per costruire URL completi
BASE_URL = "https://palazzetti.it"


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


def collect_links_from_listing(driver, url, item_container_selector, item_link_selector):
    """
    Naviga a una pagina di elenco, raccoglie gli URL dai link all'interno dei contenitori specificati.
    """
    print(f"Navigazione a: {url} per raccogliere link...")
    driver.get(url)

    # Attendi che i contenitori degli elementi siano presenti
    try:
        wait = WebDriverWait(driver, 20) # Attesa per il caricamento degli elementi
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, item_container_selector)))
        print("Pagina caricata (primo contenitore trovato).")
    except TimeoutException:
        print(f"Timeout nell'attesa dei contenitori ('{item_container_selector}') su {url}. Potrebbe non esserci nulla o il selettore non è corretto.")
        # Stampa una parte dell'HTML per debuggare se non trova contenitori
        soup_debug = get_soup_from_selenium(driver)
        if soup_debug:
             print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
             print(soup_debug.prettify()[:2000])
        return [] # Restituisce lista vuota se non trova contenitori


    # Ottieni l'HTML corrente della pagina dopo il caricamento
    soup = get_soup_from_selenium(driver)
    if not soup:
        print("Impossibile ottenere la soup dalla pagina.")
        return [] # Restituisce lista vuota

    # Trova tutti i contenitori degli elementi
    item_containers = soup.select(item_container_selector)
    print(f"Trovati {len(item_containers)} contenitori ('{item_container_selector}') su {url}.")

    if not item_containers:
        print(f"Nessun contenitore trovato su {url}. Controlla il selettore '{item_container_selector}'.")
        # Stampa una parte dell'HTML per debuggare se non trova contenitori
        print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
        print(soup.prettify()[:2000])
        return [] # Restituisce lista vuota

    collected_urls = []
    seen_urls = set() # Per evitare duplicati

    for i, container in enumerate(item_containers):
        try:
            # Trova il link all'interno del contenitore
            link_tag = container.select_one(item_link_selector)
            if link_tag and link_tag.has_attr('href'):
                relative_url = link_tag['href']
                full_url = urljoin(BASE_URL, relative_url)
                # Aggiungi l'URL alla lista solo se non l'abbiamo già visto
                if full_url not in seen_urls:
                    collected_urls.append(full_url)
                    seen_urls.add(full_url) # Aggiungi al set dei visti
                    # print(f"  Raccolto URL: {full_url}") # DEBUG
            # else: print(f"  Link non trovato nel contenitore {i+1}.") # DEBUG

        except Exception as e:
            print(f"Errore nel raccogliere l'URL dal contenitore {i+1} su {url}: {e}. Salto.")
            continue # Continua con il prossimo contenitore

    print(f"Raccolti {len(collected_urls)} URL unici da {url}.")
    return collected_urls


def scrape_palazzetti_product_detail(driver, detail_url):
    """
    Visita una singola pagina di dettaglio prodotto ed estrae nome, descrizione combinata
    (descrizione generale, specifiche tecniche, dimensioni, classe energetica) e URL immagine.
    """
    print(f"  Navigazione pagina dettaglio prodotto: {detail_url}")
    product_data = {
        "name": "N/A",
        "brand": "Palazzetti", # Marca fissa
        "description": "N/A", # Questo campo conterrà la descrizione combinata
        "price": "N/A", # Il prezzo non sembra essere sulla pagina di dettaglio
        "image_url": "N/A",
        "product_page_url": detail_url, # L'URL della pagina di dettaglio stessa
        # Rimosso campi separati per dimensioni, classe energetica, specifiche tecniche
    }

    try:
        # Usa il driver Selenium per navigare alla pagina di dettaglio
        driver.get(detail_url)
        # Attendi che un elemento chiave sulla pagina di dettaglio sia presente (es. il titolo)
        wait = WebDriverWait(driver, 15) # Attesa per il caricamento della pagina di dettaglio
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_NAME_SELECTOR_DETAIL)))
        print("   Pagina di dettaglio caricata (titolo trovato).")

        # Ottieni l'HTML dopo il caricamento completo
        soup_detail = get_soup_from_selenium(driver)
        if not soup_detail:
             print("   Impossibile ottenere la soup dalla pagina di dettaglio.")
             return product_data # Restituisce dati parziali se non si ottiene la soup


        # Estrai il Nome del prodotto
        name_tag = soup_detail.select_one(PRODUCT_NAME_SELECTOR_DETAIL)
        if name_tag:
            product_data["name"] = name_tag.get_text(strip=True)
            print(f"   Trovato Nome: {product_data['name']}")
        else:
            print(f"   Nome prodotto ({PRODUCT_NAME_SELECTOR_DETAIL}) non trovato nella pagina di dettaglio.")


        # --- Raccogli tutte le parti della descrizione ---
        combined_description_parts = []

        # Estrai la Descrizione generale dal div specifico
        description_container = soup_detail.select_one(PRODUCT_DESCRIPTION_CONTAINER_SELECTOR_DETAIL)
        if description_container:
            general_description = description_container.get_text(separator="\n", strip=True)
            if general_description:
                combined_description_parts.append("Descrizione:\n" + general_description)
                print(f"   Trovata Descrizione generale (snippet): {general_description[:70]}...")
            else:
                 print("   Contenitore descrizione generale trovato ma vuoto.")
        else:
            print(f"   Contenitore descrizione generale ({PRODUCT_DESCRIPTION_CONTAINER_SELECTOR_DETAIL}) non trovato nella pagina di dettaglio.")


        # Estrai Specifiche Tecniche
        tech_specs_tbody = soup_detail.select_one(PRODUCT_TECH_SPECS_TABLE_BODY_SELECTOR_DETAIL)
        technical_specifications_list = []
        if tech_specs_tbody:
            rows = tech_specs_tbody.select("tr")
            for row in rows:
                header = row.select_one("th")
                data = row.select_one("td")
                if header and data:
                    key = header.get_text(strip=True)
                    value = data.get_text(strip=True)
                    if key and value:
                        technical_specifications_list.append(f"{key}: {value}")
                elif header and not data:
                     section_header = header.get_text(strip=True)
                     if section_header:
                          technical_specifications_list.append(f"-- {section_header} --")

        if technical_specifications_list:
            formatted_tech_specs = "\n".join(technical_specifications_list)
            combined_description_parts.append("Specifiche Tecniche:\n" + formatted_tech_specs)
            print(f"   Trovate Specifiche Tecniche ({len(technical_specifications_list)} righe).")
        else:
            print(f"   Specifiche Tecniche ({PRODUCT_TECH_SPECS_TABLE_BODY_SELECTOR_DETAIL}) non trovate nella pagina di dettaglio.")


        # Estrai Dimensioni
        dimensions_tag = soup_detail.select_one(PRODUCT_DIMENSIONS_SELECTOR_DETAIL)
        if dimensions_tag:
            dimensions_text = dimensions_tag.get_text(strip=True)
            if dimensions_text:
                combined_description_parts.append("Dimensioni:\n" + dimensions_text)
                print(f"   Trovate Dimensioni: {dimensions_text}")
            else:
                 print("   Dimensioni trovate ma vuote.")
        else:
            print(f"   Dimensioni ({PRODUCT_DIMENSIONS_SELECTOR_DETAIL}) non trovate nella pagina di dettaglio.")


        # Estrai Classe Energetica
        energy_class_tag = soup_detail.select_one(PRODUCT_ENERGY_CLASS_SELECTOR_DETAIL)
        if energy_class_tag:
            energy_class_text = energy_class_tag.get_text(strip=True)
            if energy_class_text:
                combined_description_parts.append("Classe Energetica:\n" + energy_class_text)
                print(f"   Trovata Classe Energetica: {energy_class_text}")
            else:
                 print("   Classe Energetica trovata ma vuota.")
        else:
            print(f"   Classe Energetica ({PRODUCT_ENERGY_CLASS_SELECTOR_DETAIL}) non trovata nella pagina di dettaglio.")

        # Unisci tutte le parti nella colonna description
        if combined_description_parts:
            product_data["description"] = "\n\n".join(combined_description_parts)
        # Se nessuna parte è stata trovata, la descrizione rimane "N/A" come inizializzato


        # Estrai l'URL dell'immagine
        img_tag = soup_detail.select_one(PRODUCT_IMAGE_SELECTOR_DETAIL)
        if img_tag and img_tag.has_attr('src'):
             image_src = img_tag['src']
             # Usa urljoin per costruire l'URL completo, gestisce la codifica
             if image_src and not image_src.startswith('data:'): # Ignora placeholder data:image
                 product_data["image_url"] = urljoin(BASE_URL, image_src)
                 print(f"   Trovata Immagine: {product_data['image_url']}")
             else:
                 print("   URL immagine vuoto o placeholder data:image.")
        else:
            print(f"   Immagine ({PRODUCT_IMAGE_SELECTOR_DETAIL}) non trovata o senza attributo src nella pagina di dettaglio.")


    # Cattura eccezioni specifiche di Selenium durante la navigazione della pagina di dettaglio
    except (TimeoutException, NoSuchElementException) as e:
        print(f"  Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina di dettaglio {detail_url}: {e}")
    except Exception as e:
        print(f"  Errore generico durante lo scraping della pagina di dettaglio {detail_url}: {e}")

    return product_data


def save_to_csv(data, filename):
    """Salva una lista di dizionari in un file CSV."""
    if not data:
        print("Nessun dato da salvare nel file CSV.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_dir, filename)

    try:
        # Ottieni le chiavi da tutti i dizionari per assicurare che l'intestazione sia completa
        # Anche se ora c'è solo una colonna descrizione, è buona pratica per robustezza
        all_keys = set()
        for d in data:
            all_keys.update(d.keys())
        keys = list(all_keys) # Converti in lista

        # Definisci l'ordine delle colonne se desiderato, altrimenti saranno in ordine casuale dal set
        # Esempio di ordine desiderato:
        # ordered_keys = ["name", "brand", "description", "price", "image_url", "product_page_url"]
        # keys = [k for k in ordered_keys if k in all_keys] + [k for k in all_keys if k not in ordered_keys]


        with open(csv_file_path, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader() # Scrive l'intestazione (nomi colonne)
            dict_writer.writerows(data) # Scrive i dati
        print(f"Dati salvati in {csv_file_path}")
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
        macro_category_urls = []
        category_urls = []
        product_detail_urls = []

        # Rimosso: PRODUCT_TOTAL_LIMIT = 5 # Imposta il limite totale di prodotti da scrapare per il test


        # Rimosso: print(f"Scraping limitato ai primi {PRODUCT_TOTAL_LIMIT} prodotti totali.") # Messaggio rimosso

        # --- Fase 1: Raccogliere gli URL delle Macro-Categorie ---
        print("\n--- Fase 1: Raccolta URL Macro-Categorie ---")
        macro_category_urls = collect_links_from_listing(driver, PALAZZETTI_INITIAL_URL, LISTING_ITEM_CONTAINER_SELECTOR, LISTING_ITEM_LINK_SELECTOR)
        print(f"\n--- Fine Fase 1. Raccolti {len(macro_category_urls)} URL di macro-categorie. ---")
        # print(f"Lista URL macro-categorie: {macro_category_urls}") # DEBUG lista URL


        # --- Fase 2: Raccogliere gli URL delle Categorie da ogni Macro-Categoria ---
        print("\n--- Fase 2: Raccolta URL Categorie ---")
        for i, macro_url in enumerate(macro_category_urls):
            print(f"\nElaborazione Macro-Categoria {i+1}/{len(macro_category_urls)}: {macro_url}")
            current_category_urls = collect_links_from_listing(driver, macro_url, LISTING_ITEM_CONTAINER_SELECTOR, LISTING_ITEM_LINK_SELECTOR)
            category_urls.extend(current_category_urls)
            print(f"Totale URL categorie raccolti finora: {len(category_urls)}")
            time.sleep(1) # Pausa tra le macro-categorie

        # Rimuovi duplicati dalle URL delle categorie (potrebbero esserci categorie presenti in più macro)
        category_urls = list(set(category_urls))
        print(f"\n--- Fine Fase 2. Raccolti {len(category_urls)} URL di categorie uniche. ---")
        # print(f"Lista URL categorie: {category_urls}") # DEBUG lista URL


        # --- Fase 3: Raccogliere gli URL dei Prodotti da ogni Categoria ---
        print("\n--- Fase 3: Raccolta URL Prodotti ---")
        for i, category_url in enumerate(category_urls):
            # Rimosso: Non raccogliere URL se stiamo per superare di molto il limite totale
            # Rimosso: if len(product_detail_urls) >= PRODUCT_TOTAL_LIMIT * 2: # Raccogli il doppio del limite per sicurezza
            # Rimosso: print(f"Avvicinamento al limite totale di {PRODUCT_TOTAL_LIMIT} prodotti. Interruzione raccolta URL per questa categoria.")
            # Rimosso: break # Interrompi la raccolta URL se stiamo per superare il limite

            print(f"\nElaborazione Categoria {i+1}/{len(category_urls)}: {category_url}")
            current_product_urls = collect_links_from_listing(driver, category_url, LISTING_ITEM_CONTAINER_SELECTOR, LISTING_ITEM_LINK_SELECTOR)
            product_detail_urls.extend(current_product_urls)
            print(f"Totale URL prodotti raccolti finora: {len(product_detail_urls)}")
            time.sleep(1) # Pausa tra le categorie

        # Rimuovi duplicati dalle URL dei prodotti
        product_detail_urls = list(set(product_detail_urls))
        print(f"\n--- Fine Fase 3. Raccolti {len(product_detail_urls)} URL di prodotti unici. ---")
        # print(f"Lista URL prodotti: {product_detail_urls}") # DEBUG lista URL


        # --- Fase 4: Scraping dei Dettagli per ogni Prodotto ---
        print("\n--- Fase 4: Scraping Dettagli Prodotti ---")
        # Ottieni l'handle della finestra corrente prima di aprire nuove schede
        original_window = driver.current_window_handle

        # Limita l'iterazione agli URL raccolti, fino al limite di prodotti
        # Non è necessario tagliare la lista qui se i controlli sono all'interno del loop
        # product_detail_urls_to_scrape = product_detail_urls[:PRODUCT_TOTAL_LIMIT] # Rimosso taglio lista

        for i, product_url in enumerate(product_detail_urls):
            # Rimosso: if len(all_scraped_products) >= PRODUCT_TOTAL_LIMIT:
            # Rimosso: print(f"Limite totale di {PRODUCT_TOTAL_LIMIT} prodotti raggiunto. Interruzione scraping dei dettagli.")
            # Rimosso: break # Esci dal loop dei dettagli se il limite è raggiunto

            print(f"\nScraping Prodotto {len(all_scraped_products) + 1} (URL {i+1}/{len(product_detail_urls)}): {product_url}")

            try:
                # Apri l'URL di dettaglio in una nuova scheda
                driver.execute_script("window.open(arguments[0]);", product_url)
                time.sleep(1) # Breve pausa per permettere alla nuova scheda di aprirsi

                # Passa alla nuova scheda
                driver.switch_to.window(driver.window_handles[-1])
                # print(f"  Passato alla nuova scheda per {product_url}") # DEBUG

                # Scrape i dati dalla pagina di dettaglio
                product_data = scrape_palazzetti_product_detail(driver, product_url)

                # Aggiungi i dati estratti alla lista principale solo se il nome è stato trovato
                if product_data and product_data.get("name") != "N/A":
                    all_scraped_products.append(product_data)
                    print(f"  Aggiunto prodotto {len(all_scraped_products)} (Totale): {product_data.get('name')}")
                # else: Prodotto saltato (nome N/A)


                # Chiudi la scheda corrente
                driver.close()
                # print("  Scheda chiusa.") # DEBUG

                # Torna alla scheda originale (la pagina da cui è stata aperta l'ultima scheda)
                driver.switch_to.window(original_window)
                # print("  Tornato alla scheda originale.") # DEBUG

                time.sleep(1) # Breve pausa tra lo scraping di pagine di dettaglio

            except Exception as e:
                print(f"Errore durante lo scraping della pagina di dettaglio {product_url}: {e}. Salto.")
                # Assicurati di tornare alla finestra originale anche in caso di errore
                try:
                     # Prova a chiudere la scheda corrente se è ancora aperta
                     if len(driver.window_handles) > 1 and driver.current_window_handle != original_window:
                         driver.close()
                     # Torna alla finestra originale se non ci siamo già
                     if driver.current_window_handle != original_window:
                          driver.switch_to.window(original_window)
                except:
                     pass # Ignora errori nella gestione delle finestre in caso di errore critico
                continue # Continua con il prossimo URL di dettaglio


        print(f"\n--- Scraping completato. ---")
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
