import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from bs4 import BeautifulSoup
from urllib.parse import urljoin # Utile per costruire URL completi

# Impostazioni iniziali
# URL della pagina di elenco prodotti Weber
WEBER_LISTING_URL = "https://www.it.weber/search-content/content_type/product/activities/isolamento-termico-e-acustico-79/activities/sottofondi-colle-sigillanti-29"
OUTPUT_CSV_FILE = "weber_prodotti_selenium.csv" # Nuovo nome file per distinguerlo

# URL base del sito per costruire URL completi
BASE_URL = "https://www.it.weber"

# --- Selettori per la pagina di LISTA ---
# Selettore per ogni singolo blocco prodotto nella lista (il div con classe col-lg-6 che contiene thumbnail)
PRODUCT_CONTAINER_SELECTOR_LIST = "div.col-lg-6 div.thumbnail.thumbnail-inline"
# Selettore per il link al dettaglio prodotto nella lista (all'interno del contenitore)
PRODUCT_LINK_SELECTOR_LIST = "a.thumbnail-image" # O a.thumbnail-infos, sono gli stessi link

# Selettore comune per elementi che potrebbero indicare un CAPTCHA o blocco (potrebbe richiedere aggiustamenti)
# Cerchiamo elementi comuni in pagine di blocco, come un form, un div specifico, o testo che menziona verifiche.
# Questo è un tentativo, potrebbe essere necessario ispezionare la pagina di CAPTCHA per un selettore più preciso.
CAPTCHA_INDICATOR_SELECTORS = [
    "div#recaptcha", # Esempio per Google reCAPTCHA
    "div.cf-browser-verification", # Esempio per Cloudflare
    "form#challenge-form", # Altro esempio per Cloudflare
    "div:contains('Verifica di non essere un robot')", # Cerca div con testo specifico (meno robusto)
    "div:contains('Please verify you are human')"
]


# --- Selettori per la pagina di DETTAGLIO PRODOTTO ---
# Selettore per il titolo del prodotto nella pagina di dettaglio
PRODUCT_TITLE_SELECTOR_DETAIL = "h1.product-title"
# Selettore per il blocco contenente la descrizione e altre info
DESCRIPTION_BLOCK_SELECTOR_DETAIL = "div.col-sm-6.col-lg-7"
# Selettore per i paragrafi all'interno del contenitore descrizione (usato per trovare tutti i p)
DESCRIPTION_PARAGRAPH_SELECTOR_DETAIL = f"{DESCRIPTION_BLOCK_SELECTOR_DETAIL} p"


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


def scrape_weber_listing(driver, url):
    """
    Naviga alla pagina di elenco usando il driver Selenium,
    gestisce l'eventuale CAPTCHA manualmente, e raccoglie gli URL
    delle pagine di dettaglio prodotto.
    """
    print(f"Navigazione alla pagina di elenco: {url}")
    driver.get(url)

    # Attesa iniziale per il caricamento della pagina
    time.sleep(5) # Breve pausa per permettere al contenuto iniziale o al CAPTCHA di apparire

    # --- Gestione CAPTCHA ---
    print("Controllo per potenziale CAPTCHA o blocco...")
    captcha_present = False
    for selector in CAPTCHA_INDICATOR_SELECTORS:
        try:
            # Cerca l'elemento indicatore del CAPTCHA
            captcha_element = driver.find_element(By.CSS_SELECTOR, selector)
            if captcha_element.is_displayed():
                captcha_present = True
                print(f"Potenziale CAPTCHA o blocco rilevato usando selettore: {selector}")
                break # Esci dal ciclo selettori se ne trovi uno
        except NoSuchElementException:
            # L'elemento non è presente, continua a controllare gli altri selettori
            pass
        except Exception as e:
            print(f"Errore durante il controllo CAPTCHA con selettore {selector}: {e}")
            # Continua con gli altri selettori anche in caso di errore

    if captcha_present:
        print("\n=========================================================")
        print("!!! CAPTCHA RILEVATO O PAGINA BLOCCATA !!!")
        print("Per favore, risolvi manualmente il CAPTCHA nella finestra del browser.")
        print("Una volta che la pagina dei prodotti si è caricata correttamente,")
        print("torna qui e premi INVIO per continuare lo scraping.")
        print("=========================================================\n")

        # Attendi che l'utente risolva il CAPTCHA
        input("Premi INVIO dopo aver risolto il CAPTCHA e caricato la pagina dei prodotti...")

        # Dopo che l'utente ha premuto INVIO, attendi che i prodotti siano visibili
        try:
            wait = WebDriverWait(driver, 60) # Attesa più lunga dopo il CAPTCHA
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST)))
            print("Pagina dei prodotti caricata dopo la risoluzione del CAPTCHA.")
        except TimeoutException:
            print("Timeout nell'attesa dei prodotti dopo la risoluzione del CAPTCHA. La pagina potrebbe non essersi caricata correttamente.")
            # Prova comunque a ottenere la soup con l'HTML attuale
            soup_after_captcha = get_soup_from_selenium(driver)
            if soup_after_captcha and soup_after_captcha.select(PRODUCT_CONTAINER_SELECTOR_LIST):
                 print("Trovati prodotti nell'HTML attuale nonostante il timeout. Procedo.")
                 soup_listing = soup_after_captcha # Usa questa soup
            else:
                 print("Ancora nessun prodotto trovato. Uscita.")
                 return [] # Esci se non trovi prodotti anche dopo l'attesa

    else:
        # Se nessun CAPTCHA sembra presente, attendi semplicemente che i prodotti appaiano
        print("Nessun potenziale CAPTCHA rilevato. Attendo il caricamento dei prodotti...")
        try:
            wait = WebDriverWait(driver, 20) # Attesa normale per i prodotti
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR_LIST)))
            print("Primi prodotti visibili nella lista.")
        except TimeoutException:
            print("Timeout nell'attesa dei primi prodotti nella lista. Potrebbe non esserci nulla da scrapare o il selettore non è corretto.")
            # Se i primi prodotti non appaiono, non ha senso continuare
            # Possibile che la pagina non abbia prodotti o il selettore sia sbagliato
            print("Nessun prodotto iniziale trovato. Controlla l'URL o il selettore.")
            # Ottieni l'HTML anche in caso di timeout iniziale per vedere se c'è qualcosa
            soup_on_timeout = get_soup_from_selenium(driver)
            if soup_on_timeout and soup_on_timeout.select(PRODUCT_CONTAINER_SELECTOR_LIST):
                 print(f"Trovati {len(soup_on_timeout.select(PRODUCT_CONTAINER_SELECTOR_LIST))} prodotti nell'HTML iniziale nonostante il timeout. Procedo con l'estrazione.")
                 soup_listing = soup_on_timeout # Usa questa soup
            else:
                 print("Nessun prodotto trovato nemmeno nell'HTML iniziale. Uscita.")
                 return [] # Nessun prodotto trovato nemmeno nell'HTML iniziale


    # --- Fine Gestione CAPTCHA ---


    # Ottieni l'HTML completo della pagina dopo il caricamento (e l'eventuale risoluzione CAPTCHA)
    # Se la soup è già stata ottenuta in caso di timeout, usiamo quella.
    if 'soup_listing' not in locals():
        soup_listing = get_soup_from_selenium(driver)
        if not soup_listing:
            print("Impossibile ottenere la soup dalla pagina di elenco dopo l'attesa.")
            return []


    product_urls = []

    # Trova tutti i contenitori prodotto nell'HTML
    product_containers = soup_listing.select(PRODUCT_CONTAINER_SELECTOR_LIST)

    print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR_LIST}') per la raccolta URL.")

    if not product_containers:
        print(f"Nessun contenitore prodotto trovato. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR_LIST}'.")
        # Stampa una parte dell'HTML per aiutarti a debuggare se non trova i contenitori
        print("Primi 2000 caratteri dell'HTML della pagina di elenco per debug:")
        print(soup_listing.prettify()[:2000])
        return []


    for i, container in enumerate(product_containers):
        try:
            # Estrai l'URL della pagina di dettaglio dal link nella card
            link_tag = container.select_one(PRODUCT_LINK_SELECTOR_LIST)
            if link_tag and link_tag.has_attr('href'):
                relative_url = link_tag['href']
                # Costruisci l'URL completo se è relativo
                full_url = urljoin(BASE_URL, relative_url)
                product_urls.append(full_url)
            else:
                print(f"Link al dettaglio prodotto ({PRODUCT_LINK_SELECTOR_LIST}) non trovato nel contenitore {i+1}.")

        except Exception as e:
            print(f"Errore durante l'elaborazione del contenitore prodotto {i+1} nella lista: {e}")
            continue # Continua con il prossimo contenitore anche in caso di errore su uno

    print(f"Raccolti {len(product_urls)} URL di pagine di dettaglio.")

    return product_urls


def scrape_weber_product_detail(driver, detail_url):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium
    ed estrae nome e descrizione con la logica specificata.
    """
    print(f"Scraping pagina di dettaglio: {detail_url}")
    product_data = {
        "name": "N/A",
        "brand": "Weber", # Marca fissa
        "description": "N/A",
        "price": "N/A", # Non richiesto/visibile nella card/dettaglio forniti
        "image_url": "N/A", # Non richiesto/visibile nella card/dettaglio forniti
        "product_page_url": detail_url # L'URL della pagina di dettaglio stessa
    }

    try:
        # Usa il driver Selenium per navigare e ottenere l'HTML dopo JS execution
        driver.get(detail_url)
        # Attendi che il titolo del prodotto sia presente (segno che la pagina è caricata)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_TITLE_SELECTOR_DETAIL)))
        print("  Pagina di dettaglio caricata (titolo trovato).")

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Estrai il Nome del prodotto
        name_tag = soup.select_one(PRODUCT_TITLE_SELECTOR_DETAIL)
        if name_tag:
            product_data["name"] = name_tag.get_text(strip=True)
            print(f"  Trovato Nome: {product_data['name']}")
        else:
            print(f"  Nome prodotto ({PRODUCT_TITLE_SELECTOR_DETAIL}) non trovato nella pagina {detail_url}.")


        # --- Estrazione e composizione della Descrizione ---
        description_block = soup.select_one(DESCRIPTION_BLOCK_SELECTOR_DETAIL)
        description_parts = []

        if description_block:
            print(f"  Trovato blocco descrizione ({DESCRIPTION_BLOCK_SELECTOR_DETAIL}).")

            # Cerca tutti i tag <p> all'interno del contenitore
            description_paragraphs = description_block.select("p")

            if description_paragraphs:
                # Se ci sono paragrafi, estrai il testo da ciascuno e unisci
                print("  Trovati paragrafi nella descrizione.")
                for p_tag in description_paragraphs:
                    # Crea una copia del tag per non modificare la soup originale
                    p_copy = p_tag.copy()
                    # Rimuovi tutti i tag <def> dalla copia
                    for def_tag in p_copy.select("def"):
                        def_tag.decompose()
                    # Estrai il testo pulito
                    paragraph_text = p_copy.get_text(strip=True)
                    if paragraph_text:
                        description_parts.append(paragraph_text)
                        # print(f"   Estratto testo da <p> (snippet): {paragraph_text[:70]}...") # DEBUG
                # Unisci i testi dei paragrafi con un doppio newline per mantenere la separazione
                description_text = "\n\n".join(description_parts).strip()

            else:
                # Se non ci sono paragrafi, estrai il testo diretto dal contenitore
                print("  Nessun paragrafo trovato, estraggo testo diretto dal contenitore descrizione.")
                # Ottieni il testo completo del div, usando un separatore per i tag interni se necessario
                # Rimuovi prima i tag <def> anche dal testo diretto se presenti
                description_block_copy = description_block.copy()
                for def_tag in description_block_copy.select("def"):
                     def_tag.decompose()
                description_text = description_block_copy.get_text(separator=' ', strip=True)

                # Potrebbe essere necessario un ulteriore controllo o pulizia se il testo diretto
                # contiene elementi indesiderati o spazi extra.

            # Aggiungi il testo dell'h2 "Supporto" e del p successivo se presenti
            supporto_h2 = description_block.find("h2", string="Supporto")
            if supporto_h2:
                 print("  Trovato tag <h2>Supporto</h2>.")
                 h2_text = supporto_h2.get_text(strip=True)
                 if h2_text:
                      # Aggiungi con doppio newline prima dell'intestazione "Supporto"
                      description_text += f"\n\n{h2_text}"
                      print(f"   Aggiunto testo da <h2>: {h2_text}")

                 next_p_after_h2 = supporto_h2.find_next_sibling("p")
                 if next_p_after_h2:
                      print("  Trovato tag <p> successivo a <h2>Supporto</h2>.")
                      # Rimuovi tag <def> anche da questo paragrafo
                      next_p_copy = next_p_after_h2.copy()
                      for def_tag in next_p_copy.select("def"):
                           def_tag.decompose()
                      p_after_h2_text = next_p_copy.get_text(strip=True)
                      if p_after_h2_text:
                           # Aggiungi con singolo newline dopo l'intestazione "Supporto"
                           description_text += f"\n{p_after_h2_text}"
                           # print(f"   Aggiunto testo dal <p> dopo <h2> (snippet): {p_after_h2_text[:70]}...") # DEBUG
                      else:
                           print("   Testo estratto dal <p> dopo <h2> è vuoto.")
                 else:
                      print("   Tag <p> successivo a <h2>Supporto</h2> non trovato.")


            if description_text:
                 product_data["description"] = description_text
                 print(f"  Trovata Descrizione completa (snippet): {product_data['description'][:100]}...")
            else:
                 print("  Descrizione trovata nel contenitore ma vuota dopo l'estrazione e composizione.")


        else:
            print(f"  Blocco descrizione ({DESCRIPTION_BLOCK_SELECTOR_DETAIL}) non trovato nella pagina {detail_url}.")
        # --- Fine Estrazione e composizione della Descrizione ---


        # Non estraiamo immagine e prezzo per ora, rimangono N/A come da richiesta implicita.

        # Restituisci i dati solo se il nome è stato trovato
        if product_data.get("name") != "N/A":
            return product_data
        else:
            print(f"Saltato scraping dettaglio per {detail_url} perché il nome prodotto non è stato trovato.")
            return None


    # Cattura eccezioni specifiche di Selenium durante la navigazione della pagina di dettaglio
    except (TimeoutException, NoSuchElementException) as e:
        print(f"Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina di dettaglio {detail_url}: {e}")
    except Exception as e:
        print(f"Errore generico durante lo scraping della pagina di dettaglio {detail_url}: {e}")

    return product_data # Restituisce dati parziali in caso di errore


def save_to_csv(data, filename):
    """Salva una lista di dizionari in un file CSV."""
    if not data:
        print("Nessun dato da salvare nel file CSV.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_dir, filename)

    try:
        # Ottieni le chiavi dal primo dizionario per le intestazioni
        # Assicurati che ci siano dati prima di provare a ottenere le chiavi
        if not data:
             print("Nessun dato valido per determinare le intestazioni CSV.")
             return

        keys = data[0].keys()
        # Usa 'w' per scrivere (sovrascrive il file se esiste)
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
        # Esegui in modalità visibile per debuggare inizialmente
        driver = webdriver.Chrome() # O webdriver.Firefox(), webdriver.Edge(), ecc.

        # Fase 1: Usa Selenium per ottenere tutti gli URL dalla pagina di elenco
        # Questa funzione ora include la gestione manuale del CAPTCHA
        product_detail_urls = scrape_weber_listing(driver, WEBER_LISTING_URL)

        # Fase 2: Visita ogni URL di dettaglio e scrape i dati
        all_scraped_products = []
        if product_detail_urls:
            print(f"\nInizio scraping dei dettagli per {len(product_detail_urls)} prodotti...")
            # Ottieni l'handle della finestra corrente prima di aprire nuove schede
            # Questo handle dovrebbe essere quello della pagina di elenco DOPO l'eventuale CAPTCHA
            original_window = driver.current_window_handle

            for i, detail_url in enumerate(product_detail_urls):
                print(f"\nScraping prodotto {i+1}/{len(product_detail_urls)}: {detail_url}")
                # Passa l'istanza del driver alla funzione di scraping dettaglio
                product_data = scrape_weber_product_detail(driver, detail_url)
                if product_data and product_data.get("name") != "N/A": # Aggiungi solo se lo scraping del dettaglio ha avuto successo (nome trovato)
                    all_scraped_products.append(product_data)

                # Non chiudiamo la scheda qui perché scrape_weber_product_detail naviga direttamente.
                # Se avessimo aperto in una nuova scheda, la chiuderemmo qui.
                # time.sleep(1) # Breve pausa tra le richieste di dettaglio (non strettamente necessaria con get)

        # Fase 3: Salva tutti i dati raccolti in un file CSV
        print("\nCompletato lo scraping.")
        print(f"Totale prodotti con dettagli estratti: {len(all_scraped_products)}")
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
