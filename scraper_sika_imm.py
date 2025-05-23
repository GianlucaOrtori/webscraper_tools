import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup
# Non usiamo più requests per le pagine di dettaglio

# Impostazioni iniziali
SIKA_BASE_URL = "https://ita.sika.com"  # URL base per costruire URL completi
SIKA_LISTING_URL = "https://ita.sika.com/it/edilizia/prodotti-edilizia.html"
OUTPUT_CSV_FILE = "sika_prodotti_completo.csv"  # Nuovo nome file per distinguere

# Intestazioni (non più usate da requests, ma mantenute per riferimento se servissero)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Selettori per la pagina di LISTA ---
PRODUCT_CONTAINER_SELECTOR_LIST = "div[data-list-item].cell"
PRODUCT_LINK_SELECTOR_LIST = "a.cmp-teaser_productContainer"
LOAD_MORE_BUTTON_SELECTOR = ".load-more-results button"

# --- Selettori per la pagina di DETTAGLIO PRODOTTO ---
PRODUCT_TITLE_SELECTOR_DETAIL = "h1.cmp-title__text"
PRODUCT_DESCRIPTION_SELECTOR_DETAIL = "p.cmp-text__paragraph[itemprop='description']"
PRODUCT_PICTURE_SELECTOR_DETAIL = "div.cmp-product__media picture"


def get_product_urls_from_listing(driver, url):
    print(f"Navigazione alla pagina di elenco: {url}")
    driver.get(url)

    try:
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST)))
        print("Primi prodotti visibili nella lista.")
    except TimeoutException:
        print("Timeout nell'attesa dei primi prodotti nella lista. Potrebbe non esserci nulla da scrapare.")
        return []

    while True:
        try:
            print("Ricerca del pulsante 'Più Risultati'...")
            wait = WebDriverWait(driver, 15)
            load_more_button = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, LOAD_MORE_BUTTON_SELECTOR)))
            load_more_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, LOAD_MORE_BUTTON_SELECTOR)))
            print("Pulsante 'Più Risultati' trovato e cliccabile.")

            driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
            time.sleep(0.5)

            initial_product_count = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST))
            print(f"Trovati {initial_product_count} prodotti prima di cliccare.")

            try:
                load_more_button.click()
                print("Cliccato su 'Più Risultati' (click diretto).")
            except ElementClickInterceptedException:
                print("Click diretto intercettato. Tentativo con execute_script.")
                driver.execute_script("arguments[0].click();", load_more_button)
                print("Cliccato su 'Più Risultati' (execute_script).")

            try:
                print("Attendere il caricamento di nuovi prodotti...")
                wait.until(
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST)) > initial_product_count
                )
                print(f"Nuovi prodotti caricati. Totale attuale: {len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST))}")
            except TimeoutException:
                print("Timeout nell'attesa di nuovi prodotti. Potrebbero non essercene altri o il caricamento è molto lento.")
                break

        except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
            print("Pulsante 'Più Risultati' non più presente o non cliccabile. Tutti i prodotti dovrebbero essere caricati.")
            break

    print("Raccogliere gli URL delle pagine di dettaglio...")
    product_urls = []
    product_containers = driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST)
    for container in product_containers:
        try:
            link_tag = container.find_element(By.CSS_SELECTOR, PRODUCT_LINK_SELECTOR_LIST)
            if link_tag and link_tag.get_attribute('href'):
                relative_url = link_tag.get_attribute('href')
                if relative_url.startswith('/'):
                    full_url = SIKA_BASE_URL + relative_url
                else:
                    full_url = relative_url
                product_urls.append(full_url)
        except Exception as e:
            print(f"Errore nel raccogliere l'URL da un contenitore prodotto nella lista: {e}")
            continue

    print(f"Raccolti {len(product_urls)} URL di pagine di dettaglio.")
    return product_urls


def get_highest_quality_image(soup, product_url):
    """
    Funzione dedicata per estrarre l'immagine di qualità più elevata da diverse fonti
    nella pagina del prodotto, controllando anche dimensioni e risoluzioni specificate.
    """
    img_url = "N/A"
    product_picture_tag = soup.select_one(PRODUCT_PICTURE_SELECTOR_DETAIL)
    
    if not product_picture_tag:
        print("  Nessun tag <picture> trovato per il prodotto.")
        return img_url
        
    print("  Trovato tag <picture> usando il selettore specifico del prodotto.")
    
    # 1. Prima cerchiamo immagini di alta qualità da fonti specifiche
    picture_sources = {}
    
    # Controlliamo prima qualsiasi tag <img> con attributo data-high-resolution-src
    highres_img = product_picture_tag.select_one("img[data-high-resolution-src]")
    if highres_img and highres_img.has_attr('data-high-resolution-src'):
        url = highres_img['data-high-resolution-src']
        if url and not url.startswith('data:'):
            print(f"  Trovata immagine ad alta risoluzione con data-high-resolution-src: {url[:100]}...")
            img_url = url
            return normalize_image_url(img_url, SIKA_BASE_URL)
    
    # 2. Controlliamo per tag <img> all'interno di <picture>
    img_tag = product_picture_tag.select_one("img")
    if img_tag:
        # Cercare attributi per immagini ad alta qualità
        potential_attrs = ['src', 'data-src', 'data-srcset', 'data-original', 'data-original-set']
        
        for attr in potential_attrs:
            if img_tag.has_attr(attr):
                value = img_tag[attr]
                if value and not value.startswith('data:'):
                    print(f"  Trovato attributo {attr} nel tag <img>: {value[:100]}...")
                    picture_sources[attr] = value
    
    # 3. Procediamo con l'analisi dei tag <source> nel <picture> per srcset
    source_tags = product_picture_tag.select("source")
    best_url_from_srcset = None
    max_width = 0
    max_density = 0
    
    print(f"  Trovati {len(source_tags)} tag <source> nella picture del prodotto.")
    for source_tag in source_tags:
        srcset_value = source_tag.get('srcset')
        if not srcset_value:
            continue
            
        print(f"    Analisi srcset in <source>: {srcset_value[:100]}...")
        sources = srcset_value.split(',')
        
        for source in sources:
            parts = source.strip().split()
            if len(parts) < 1:
                continue
                
            url = parts[0]
            
            # Gestione dimensioni (width) o densità (2x, 3x)
            width = 0
            density = 0
            
            if len(parts) > 1:
                dimension = parts[1]
                
                # Controlla se è una dimensione (width) o una densità (x)
                if 'w' in dimension:
                    try:
                        width = int(dimension.replace('w', ''))
                        print(f"      Trovata larghezza: {width}px per URL: {url[:50]}...")
                    except ValueError:
                        print(f"      Impossibile convertire la larghezza '{dimension}' in intero.")
                elif 'x' in dimension:
                    try:
                        density = float(dimension.replace('x', ''))
                        print(f"      Trovata densità: {density}x per URL: {url[:50]}...")
                    except ValueError:
                        print(f"      Impossibile convertire la densità '{dimension}' in float.")
            
            # Priorità alla densità più alta (retina), quindi alla larghezza più grande
            if density > max_density:
                max_density = density
                best_url_from_srcset = url
                print(f"      Nuovo miglior URL da srcset per densità {density}x: {url[:50]}...")
            elif density == max_density and width > max_width:
                max_width = width
                best_url_from_srcset = url
                print(f"      Nuovo miglior URL da srcset per larghezza {width}px: {url[:50]}...")
            elif max_density == 0 and width > max_width:
                max_width = width
                best_url_from_srcset = url
                print(f"      Nuovo miglior URL da srcset per larghezza {width}px: {url[:50]}...")
    
    # 4. Selezionare l'immagine migliore in base alle priorità:
    # Priorità 1: Immagini ad alta risoluzione esplicite
    if best_url_from_srcset:
        img_url = best_url_from_srcset
        print(f"  URL immagine selezionato da srcset: {img_url[:100]}...")
    # Priorità 2: Qualsiasi URL trovato nei tag <img>
    elif picture_sources:
        # Preferire nella sequenza: data-src (lazy loading) -> src -> altri attributi
        if 'data-src' in picture_sources:
            img_url = picture_sources['data-src']
        elif 'src' in picture_sources:
            img_url = picture_sources['src']
        else:
            # Prendi il primo disponibile se non ci sono src/data-src
            img_url = next(iter(picture_sources.values()))
        print(f"  URL immagine selezionato dagli attributi <img>: {img_url[:100]}...")
    
    # Normalizzazione URL finale
    return normalize_image_url(img_url, SIKA_BASE_URL)


def normalize_image_url(img_url, base_url):
    """
    Normalizza l'URL dell'immagine, assicurandosi che sia completo.
    """
    if img_url == "N/A":
        return img_url
        
    if img_url.startswith('//'):
        img_url = "https:" + img_url
    elif img_url.startswith('/'):
        img_url = base_url + img_url
    
    print(f"  URL immagine finale normalizzato: {img_url}")
    return img_url


def scrape_product_detail(driver, product_url):
    print(f"Scraping pagina di dettaglio: {product_url}")
    product_data = {
        "name": "N/A",
        "brand": "Sika",
        "description": "N/A",
        "price": "N/A",
        "image_url": "N/A",
        "product_page_url": product_url
    }

    try:
        driver.get(product_url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_TITLE_SELECTOR_DETAIL)))
        print("  Pagina di dettaglio caricata (titolo trovato).")

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        name_tag = soup.select_one(PRODUCT_TITLE_SELECTOR_DETAIL)
        if name_tag:
            product_data["name"] = name_tag.get_text(strip=True)
            print(f"  Trovato Nome: {product_data['name']}")

        description_tag = soup.select_one(PRODUCT_DESCRIPTION_SELECTOR_DETAIL)
        if description_tag:
            product_data["description"] = description_tag.get_text(strip=True)
            print(f"  Trovata Descrizione (snippet): {product_data['description'][:70]}...")

        # Utilizzo della nuova funzione per ottenere l'immagine della massima qualità
        product_data["image_url"] = get_highest_quality_image(soup, product_url)

    except (TimeoutException, NoSuchElementException) as e:
        print(f"Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina di dettaglio {product_url}: {e}")
    except Exception as e:
        print(f"Errore generico durante lo scraping della pagina di dettaglio {product_url}: {e}")

    return product_data


def save_to_csv(data, filename):
    if not data:
        print("Nessun dato da salvare nel file CSV.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_dir, filename)

    try:
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
        driver = webdriver.Chrome()
    except Exception as e:
        print(f"Errore nell'inizializzazione del WebDriver: {e}")
        print("Assicurati di aver installato il browser driver corretto (es. ChromeDriver) e che sia nel tuo PATH di sistema.")
        exit()

    all_product_urls = get_product_urls_from_listing(driver, SIKA_LISTING_URL)

    urls_to_process = all_product_urls

    all_products_data = []
    print(f"\nInizio scraping delle {len(urls_to_process)} pagine di dettaglio prodotto (limitate per test) usando Selenium...")
    for j, product_url in enumerate(urls_to_process):
        product_detail = scrape_product_detail(driver, product_url)
        print(f"DEBUG: Dati prodotto prima di append: {product_detail}")
        if product_detail and product_detail.get("name") != "N/A":
            all_products_data.append(product_detail)
        time.sleep(1)

    try:
        driver.quit()
        print("Browser Selenium chiuso.")
    except Exception as e:
        print(f"Errore durante la chiusura del browser: {e}")

    print("\nCompletato lo scraping delle pagine di dettaglio.")
    save_to_csv(all_products_data, OUTPUT_CSV_FILE)