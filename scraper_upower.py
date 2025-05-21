import time
import csv
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup
from urllib.parse import urljoin # Utile per costruire URL completi

# Impostazioni iniziali
# URL della pagina di elenco prodotti U-Power
UPOWER_LISTING_URL = "https://www.u-power.it/it/calzature"
OUTPUT_CSV_FILE = "upower_prodotti.csv"

# --- Selettori per la pagina di LISTA ---
# Selettore per ogni singolo blocco prodotto nella lista
PRODUCT_CONTAINER_SELECTOR_LIST = "div.prod-box.flex.flex-col.border.border-grey-100.cursor-pointer"
# Selettore per il link al dettaglio prodotto nella lista (all'interno del contenitore)
PRODUCT_LINK_SELECTOR_LIST = "a[href]" # Cerca qualsiasi link con href all'interno del container

# Selettore per il pulsante "CARICA ALTRI"
# Usiamo un selettore XPath più robusto che cerca un tag button con il testo "CARICA ALTRI"
LOAD_MORE_BUTTON_SELECTOR_XPATH = "//button[contains(text(), 'CARICA ALTRI')]"
# Selettore CSS per il contenitore del pulsante "CARICA ALTRI" (utile per verificarne la presenza)
LOAD_MORE_SECTION_SELECTOR_CSS = "div.load-more-section"


# --- Selettori per la pagina di DETTAGLIO PRODOTTO ---
# Basati sull'HTML che hai fornito
PRODUCT_TITLE_SELECTOR_DETAIL = "h1.text-3xl.font-bold" # Selettore per il titolo nella pagina di dettaglio
# Selettore per il contenitore della descrizione
DESCRIPTION_CONTAINER_SELECTOR_DETAIL = "div.description-content"
# Selettore per i paragrafi all'interno del contenitore descrizione (usato per trovare tutti i p)
DESCRIPTION_PARAGRAPH_SELECTOR_DETAIL = f"{DESCRIPTION_CONTAINER_SELECTOR_DETAIL} p"
# Selettore per l'immagine principale
PRODUCT_IMAGE_SELECTOR_DETAIL = "img#main-image" # Selettore per l'immagine principale


# URL base del sito per costruire URL completi
BASE_URL = "https://www.u-power.it"


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


def get_product_urls_from_listing(driver, url):
    """
    Naviga alla pagina di elenco usando il driver Selenium,
    clicca su "CARICA ALTRI" finché possibile (carica tutti i prodotti),
    e restituisce una lista di URL delle pagine di dettaglio prodotto.
    """
    print(f"Navigazione alla pagina di elenco: {url}")
    driver.get(url)

    # Accetta i cookie se presente un banner (comune su molti siti UE)
    # Devi ispezionare la pagina per trovare il selettore corretto per il pulsante "Accetta"
    # Esempio (potrebbe non funzionare, adattalo ispezionando la pagina reale):
    # try:
    #     # Attesa breve per il cookie banner
    #     cookie_accept_button = WebDriverWait(driver, 5).until(
    #         EC.element_to_be_clickable((By.CSS_SELECTOR, "button#onetrust-accept-btn-handler")) # Esempio comune
    #     )
    #     cookie_accept_button.click()
    #     print("Banner cookie accettato.")
    #     time.sleep(2) # Breve pausa dopo aver cliccato
    # except (TimeoutException, NoSuchElementException):
    #     # print("Banner cookie non trovato o già gestito.") # Meno verboso
    #     pass # Continua se il banner non compare


    # Attendi che la pagina iniziale carichi e che i primi prodotti siano visibili
    try:
        wait = WebDriverWait(driver, 40) # Attesa iniziale più lunga per il caricamento della pagina e dei primi prodotti
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST)))
        print("Primi prodotti visibili nella lista.")
    except TimeoutException:
        print(f"Timeout nell'attesa dei primi prodotti nella lista con selettore '{PRODUCT_CONTAINER_SELECTOR_LIST}'. Potrebbe non esserci nulla da scrapare o il selettore non è corretto.")
        return [] # Restituisce lista vuota se non trova i primi prodotti


    # Cicla per cliccare sul pulsante "CARICA ALTRI" finché non è più presente
    while True:
        try:
            # Ottieni il numero di prodotti attuali visibili PRIMA di cercare il pulsante
            initial_product_count = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST))
            print(f"Prodotti visibili prima di cercare il pulsante: {initial_product_count}.")

            # Attendi che il pulsante "CARICA ALTRI" sia presente nel DOM e visibile
            # Usiamo una attesa più lunga qui, poiché potrebbe apparire dopo un po' o dopo scroll
            wait_for_button = WebDriverWait(driver, 30) # Attesa aumentata per il pulsante
            load_more_button = wait_for_button.until(
                EC.visibility_of_element_located((By.XPATH, LOAD_MORE_BUTTON_SELECTOR_XPATH))
            )

            # Attendi che il pulsante diventi cliccabile
            load_more_button = wait_for_button.until(
                EC.element_to_be_clickable((By.XPATH, LOAD_MORE_BUTTON_SELECTOR_XPATH))
            )
            print("Pulsante 'CARICA ALTRI' trovato e cliccabile.")

            # Scrolla il pulsante nella vista per assicurare che sia interagibile
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
            time.sleep(2) # Pausa per permettere lo scroll e la stabilizzazione

            # Ulteriori controlli prima di cliccare
            if not load_more_button.is_displayed():
                print("Pulsante 'CARICA ALTRI' trovato ma non visualizzato (dopo scroll). Fine del caricamento.")
                break
            if not load_more_button.is_enabled():
                 print("Pulsante 'CARICA ALTRI' trovato ma non abilitato. Fine del caricamento.")
                 break


            # Clicca sul pulsante con un ciclo di retry più robusto
            click_successful = False
            retry_count = 0
            max_retries = 5 # Manteniamo un numero ragionevole di tentativi di click
            while not click_successful and retry_count < max_retries:
                try:
                    print(f"Tentativo di click su 'CARICA ALTRI' (Retry {retry_count + 1}/{max_retries})...")
                    load_more_button.click()
                    print("Click riuscito.")
                    click_successful = True
                    # Breve pausa subito dopo il click per dare tempo alla richiesta di partire
                    time.sleep(1.5)
                except ElementClickInterceptedException:
                    retry_count += 1
                    print(f"Click intercettato. Riprovo a cliccare...")
                    time.sleep(3) # Pausa aumentata prima di riprovare
                    # Dopo un'intercettazione, prova a ritrovare l'elemento per gestire StaleElement o overlay
                    try:
                         load_more_button = WebDriverWait(driver, 10).until(
                              EC.element_to_be_clickable((By.XPATH, LOAD_MORE_BUTTON_SELECTOR_XPATH))
                         )
                         driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                         time.sleep(1)
                    except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
                         print("Pulsante non trovato o non cliccabile dopo intercettazione. Uscita dal ciclo di click.")
                         break # Esci dal ciclo retry se non riesci a ritrovare il pulsante

                except StaleElementReferenceException:
                     retry_count += 1
                     print(f"Elemento obsoleto. Riprovo a trovare e cliccare il pulsante...")
                     # Riprova a trovare l'elemento prima del prossimo click
                     try:
                          load_more_button = WebDriverWait(driver, 10).until(
                               EC.element_to_be_clickable((By.XPATH, LOAD_MORE_BUTTON_SELECTOR_XPATH))
                          )
                          driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                          time.sleep(1)
                     except (NoSuchElementException, TimeoutException):
                          print("Pulsante non trovato dopo errore obsoleto. Uscita dal ciclo di click.")
                          break # Esci dal ciclo retry se non riesci a ritrovare il pulsante

                except Exception as e:
                     retry_count += 1
                     print(f"Errore generico durante il click: {e}. Riprovo...")
                     time.sleep(3)


            if not click_successful:
                print(f"Impossibile cliccare sul pulsante 'CARICA ALTRI' dopo {max_retries} tentativi. Potrebbe essere l'ultima pagina o un problema persistente.")
                # Non rompere qui il loop principale, lascia che l'attesa dei prodotti decida
                pass # Continua per vedere se il numero di prodotti cambia comunque

            # Attendi che il numero di prodotti AUMENTI DOPO il click
            # Questo è l'indicatore chiave che il caricamento è avvenuto
            try:
                print(f"Attendere il caricamento di nuovi prodotti dopo il click. Prodotti iniziali: {initial_product_count}")
                # Aumenta significativamente il timeout per l'attesa del caricamento dinamico
                wait_for_products = WebDriverWait(driver, 90) # Attesa lunga (es. 90 secondi)
                wait_for_products.until(
                    # Aspetta che il numero di elementi 'PRODUCT_CONTAINER_SELECTOR_LIST' sia strettamente maggiore
                    # rispetto al conteggio prima del click.
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST)) > initial_product_count
                )
                current_product_count_after_click = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST))
                print(f"Nuovi prodotti caricati. Totale attuale: {current_product_count_after_click}")

                # Aggiungi una piccola pausa extra dopo il caricamento per stabilizzare la pagina
                time.sleep(4) # Pausa aggiuntiva


            except TimeoutException:
                # Se il timeout scade e il numero di prodotti non è aumentato,
                # significa che probabilmente non ci sono altri prodotti da caricare.
                current_product_count_after_timeout = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST))
                print(f"Timeout nell'attesa di nuovi prodotti dopo il click. Conteggio attuale: {current_product_count_after_timeout}. Potrebbero non essercene altri.")

                # Controlla se il pulsante è scomparso o è diventato non cliccabile come ulteriore conferma
                try:
                     # Breve attesa per vedere se lo stato del pulsante cambia
                     WebDriverWait(driver, 5).until(
                          EC.invisibility_of_element_located((By.XPATH, LOAD_MORE_BUTTON_SELECTOR_XPATH))
                     )
                     print("Pulsante 'CARICA ALTRI' scomparso o diventato invisibile. Fine del caricamento.")
                except TimeoutException:
                     print("Pulsante 'CARICA ALTRI' ancora presente/visibile ma non ha caricato altri prodotti.")
                     # In questo caso, esci comunque perché non sono stati caricati nuovi prodotti
                     pass # Continua per uscire dal loop principale


                break # Esci dal ciclo while True perché non sono stati caricati nuovi prodotti

            # Se il numero di prodotti è aumentato, il loop continua per cercare il pulsante nuovamente

        except (NoSuchElementException, TimeoutException, StaleElementReferenceException) as e:
            # Il pulsante "CARICA ALTRI" non è stato trovato entro il timeout
            # o è diventato non cliccabile, o si è verificato un errore di riferimento obsoleto.
            # Questo è il segnale che non ci sono altri prodotti da caricare.
            print(f"Pulsante 'CARICA ALTRI' non più trovato o non interagibile ({type(e).__name__}). Tutti i prodotti dovrebbero essere caricati.")
            break # Esci dal ciclo while True


    # Ora che tutti i prodotti sono caricati (il loop while True è terminato), raccogli gli URL
    print(f"Fine del caricamento dinamico. Inizio raccolta URL da {len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST))} prodotti totali visibili.")
    product_urls = []
    # Ottieni l'HTML completo dopo tutti i caricamenti
    soup_listing = get_soup_from_selenium(driver)
    if not soup_listing:
        print("Impossibile ottenere la soup dopo il caricamento dinamico. Non posso raccogliere URL.")
        return []

    # Raccogli i contenitori prodotto dall'HTML completo
    product_containers = soup_listing.select(PRODUCT_CONTAINER_SELECTOR_LIST)
    print(f"Trovati {len(product_containers)} contenitori prodotto totali per la raccolta URL.")

    for container in product_containers:
        try:
            # Trova il link all'interno del contenitore
            link_tag = container.select_one(PRODUCT_LINK_SELECTOR_LIST)
            if link_tag and link_tag.has_attr('href'):
                relative_url = link_tag['href']
                # Usa urljoin per costruire l'URL completo, gestisce la codifica
                full_url = urljoin(BASE_URL, relative_url)
                product_urls.append(full_url)
        except Exception as e:
            print(f"Errore nel raccogliere l'URL da un contenitore prodotto nella lista: {e}")
            continue

    # Rimuovi eventuali URL duplicati che potrebbero essersi insinuati
    product_urls = list(set(product_urls))
    print(f"Raccolti {len(product_urls)} URL di pagine di dettaglio unici.")

    return product_urls


def scrape_upower_product_detail(driver, detail_url):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium
    ed estrae nome, descrizione (gestendo paragrafi multipli o testo diretto) e URL immagine.
    """
    print(f"Scraping pagina di dettaglio: {detail_url}")
    product_data = {
        "name": "N/A",
        "brand": "U-Power", # Marca fissa
        "description": "N/A",
        "price": "N/A", # Non sembra esserci un prezzo visibile
        "image_url": "N/A",
        "product_page_url": detail_url # L'URL della pagina di dettaglio stessa
    }

    try:
        # Usa il driver Selenium per navigare e ottenere l'HTML dopo JS execution
        driver.get(detail_url)
        # Attendi che il titolo del prodotto sia presente (segno che la pagina è caricata)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_TITLE_SELECTOR_DETAIL)))
        print("  Pagina di dettaglio caricata (titolo trovato).")

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Estrai il Nome del prodotto
        name_tag = soup.select_one(PRODUCT_TITLE_SELECTOR_DETAIL)
        if name_tag:
            product_data["name"] = name_tag.get_text(strip=True)
            print(f"  Trovato Nome: {product_data['name']}")
        else:
             print(f"  Nome prodotto ({PRODUCT_TITLE_SELECTOR_DETAIL}) non trovato.")


        # --- Estrai la Descrizione (gestendo paragrafi multipli o testo diretto) ---
        description_container_tag = soup.select_one(DESCRIPTION_CONTAINER_SELECTOR_DETAIL)

        if description_container_tag:
            # Cerca tutti i tag <p> all'interno del contenitore
            description_paragraphs = description_container_tag.select(DESCRIPTION_PARAGRAPH_SELECTOR_DETAIL)

            description_text_parts = []

            if description_paragraphs:
                # Se ci sono paragrafi, estrai il testo da ciascuno e unisci
                # print("  Trovati paragrafi nella descrizione.") # DEBUG
                for p_tag in description_paragraphs:
                    # Usa get_text(separator=' ') per preservare gli spazi all'interno dei paragrafi
                    paragraph_text = p_tag.get_text(separator=' ', strip=True)
                    if paragraph_text:
                        description_text_parts.append(paragraph_text)
                # Unisci i testi dei paragrafi con un doppio newline per mantenere la separazione
                description_text = "\n\n".join(description_text_parts).strip()

            else:
                # Se non ci sono paragrafi, estrai il testo diretto dal contenitore
                # print("  Nessun paragrafo trovato, estraggo testo diretto dal contenitore descrizione.") # DEBUG
                # Ottieni il testo completo del div, usando un separatore per i tag interni se necessario
                description_text = description_container_tag.get_text(separator=' ', strip=True)

                # Potrebbe essere necessario un ulteriore controllo o pulizia se il testo diretto
                # contiene elementi indesiderati o spazi extra.

            if description_text:
                 product_data["description"] = description_text
                 print(f"  Trovata Descrizione (snippet): {product_data['description'][:70]}...")
            else:
                 print("  Descrizione trovata nel contenitore ma vuota dopo l'estrazione.")
        else:
            print(f"  Contenitore descrizione ({DESCRIPTION_CONTAINER_SELECTOR_DETAIL}) non trovato.")
        # --- Fine Estrazione Descrizione ---


        # Estrai l'URL dell'immagine
        img_tag = soup.select_one(PRODUCT_IMAGE_SELECTOR_DETAIL)
        if img_tag and img_tag.has_attr('src'):
             image_src = img_tag['src']
             # Usa urljoin per costruire l'URL completo, gestisce la codifica
             if image_src and not image_src.startswith('data:'): # Ignora placeholder data:image
                 product_data["image_url"] = urljoin(BASE_URL, image_src)
                 print(f"  Trovata Immagine: {product_data['image_url']}")
             else:
                 print("  URL immagine vuoto o placeholder data:image.")
        else:
            print(f"  Immagine ({PRODUCT_IMAGE_SELECTOR_DETAIL}) non trovata o senza attributo src.")


    # Cattura eccezioni specifiche di Selenium durante la navigazione della pagina di dettaglio
    except (TimeoutException, NoSuchElementException) as e:
        print(f"Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina di dettaglio {detail_url}: {e}")
    except Exception as e:
        print(f"Errore generico durante lo scraping della pagina di dettaglio {detail_url}: {e}")

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
        all_keys = set()
        for d in data:
            all_keys.update(d.keys())
        keys = list(all_keys) # Converti in lista

        # Definisci l'ordine delle colonne se desiderato
        ordered_keys = ["name", "brand", "description", "price", "image_url", "product_page_url"]
        # Mantieni solo le chiavi che sono effettivamente presenti nei dati
        keys = [k for k in ordered_keys if k in all_keys] + [k for k in all_keys if k not in ordered_keys]


        with open(csv_file_path, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader() # Scrive l'intestazione (nomi colonne)
            dict_writer.writerows(data) # Scrive i dati
        print(f"Dati salvati in {csv_file_path}")
    except Exception as e:
        print(f"Errore durante il salvataggio del file CSV: {e}")


if __name__ == "__main__":
    # Configurazione di Selenium WebDriver (spostata qui per usarla in entrambe le fasi)
    # ASSICURATI DI AVER SCARICATO IL DRIVER DEL BROWSER E CHE SIA NEL TUO PATH DI SISTEMA
    # O SPECIFICA IL PERCORSO COMPLETO AL DRIVER QUI.
    try:
        # Esegui in modalità visibile per debuggare inizialmente, poi puoi passare a headless
        chrome_options = webdriver.ChromeOptions()
        # Rimosso: chrome_options.add_argument("--headless") # Rimuovi il commento per eseguire senza finestra
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu") # Spesso necessario con headless
        chrome_options.add_argument("--window-size=1920,1080") # Imposta dimensioni finestra, utile con headless
        # Aggiungi un user-agent per apparire come un browser reale
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        print("Inizializzazione driver Selenium...")
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(5) # Attesa implicita per trovare gli elementi

    except Exception as e:
        print(f"Errore nell'inizializzazione del WebDriver: {e}")
        print("Assicurati di aver installato il browser driver corretto (es. ChromeDriver) e che sia nel tuo PATH di sistema.")
        exit()

    # Passo 1: Usa Selenium per ottenere tutti gli URL dalla pagina di elenco (gestendo il caricamento dinamico)
    # Questa funzione ora caricherà TUTTI i prodotti prima di raccogliere gli URL
    print("\n--- Fase 1: Caricamento dinamico e raccolta URL dalla pagina di elenco ---")
    all_product_urls = get_product_urls_from_listing(driver, UPOWER_LISTING_URL)
    print(f"\n--- Fine Fase 1. Raccolti {len(all_product_urls)} URL di prodotti totali. ---")

    # Passo 2: Scrape i dettagli per ogni URL raccolto usando la stessa istanza del driver Selenium
    all_scraped_products = []
    if not all_product_urls:
        print("\nNessun URL prodotto raccolto nella Fase 1. Impossibile procedere con lo scraping dei dettagli.")
    else:
        print(f"\n--- Fase 2: Scraping delle {len(all_product_urls)} pagine di dettaglio prodotto ---")

        # Ottieni l'handle della finestra corrente (la pagina di elenco) prima di aprire nuove schede
        original_window = driver.current_window_handle

        for i, product_url in enumerate(all_product_urls):
            print(f"\nScraping Prodotto {i+1}/{len(all_product_urls)}: {product_url}")

            try:
                # Apri l'URL di dettaglio in una nuova scheda
                driver.execute_script("window.open(arguments[0]);", product_url)
                time.sleep(1.5) # Pausa aumentata per permettere alla nuova scheda di aprirsi e iniziare a caricare

                # Passa alla nuova scheda (sarà l'ultima nella lista delle window_handles)
                driver.switch_to.window(driver.window_handles[-1])
                # print(f"  Passato alla nuova scheda per {product_url}") # DEBUG

                # Scrape i dati dalla pagina di dettaglio
                product_data = scrape_upower_product_detail(driver, product_url)

                # Aggiungi i dati estratti alla lista principale solo se il nome è stato trovato
                if product_data and product_data.get("name") != "N/A":
                    all_scraped_products.append(product_data)
                    print(f"  Aggiunto prodotto {len(all_scraped_products)} (Totale): {product_data.get('name')}")
                else:
                    print("  Dati prodotto incompleti (Nome N/A). Questo prodotto non sarà aggiunto alla lista finale.")


                # Chiudi la scheda corrente
                driver.close()
                # print("  Scheda chiusa.") # DEBUG

                # Torna alla scheda originale (la pagina di elenco)
                driver.switch_to.window(original_window)
                # print("  Tornato alla scheda originale.") # DEBUG

                time.sleep(1.5) # Pausa aumentata tra lo scraping di pagine di dettaglio


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

        print(f"\n--- Fine Fase 2. Scraping delle pagine di dettaglio completato. ---")


    # Chiudi il browser Selenium UNA SOLA VOLTA alla fine
    # Questo blocco finally ora si trova solo all'interno del main try
    # per garantire che il driver sia chiuso dopo entrambe le fasi.
    try:
        driver.quit()
        print("Browser Selenium chiuso.")
    except Exception as e:
        print(f"Errore durante la chiusura del browser: {e}")


    # Passo 3: Salva tutti i dati estratti in un file CSV
    print("\n--- Fase 3: Salvataggio dati in CSV ---")
    save_to_csv(all_scraped_products, OUTPUT_CSV_FILE)
    print("\n--- Script completato. ---")