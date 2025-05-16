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
KNAUF_URL = "https://knauf.com/it-IT/p/prodotti"
OUTPUT_CSV_FILE = "knauf_prodotti.csv"

# --- Selettori CSS per gli elementi sulla pagina Knauf ---
# Basati sull'HTML che hai fornito

# Selettore per ogni singolo blocco prodotto (usa data-cy per maggiore robustezza contro classi casuali)
PRODUCT_CONTAINER_SELECTOR = "div[data-cy^='ProductCard-']"

# Selettore per il titolo del prodotto (usa data-cy)
PRODUCT_TITLE_SELECTOR = "span[data-cy$='-title']"

# Selettore per la descrizione del prodotto (usa data-cy)
PRODUCT_DESCRIPTION_SELECTOR = "p[data-cy$='-description']"

# Selettore per l'URL della pagina di dettaglio del prodotto (il link che avvolge la card)
PRODUCT_LINK_SELECTOR = "a.MuiCardActionArea-root"

# Selettore per il tag immagine dentro il blocco immagine del prodotto
# L'immagine è dentro un div con classe MuiCardMedia-root
PRODUCT_IMAGE_SELECTOR = "div.MuiCardMedia-root img"


# Selettore per il pulsante "Mostra di più" (usa data-cy)
LOAD_MORE_BUTTON_SELECTOR = "button[data-cy='ProductHits-showMore']"

# Configurazione di Selenium WebDriver
# ASSICURATI DI AVER SCARICATO IL DRIVER DEL BROWSER E CHE SIA NEL TUO PATH DI SISTEMA
# O SPECIFICA IL PERCORSO COMPLETO AL DRIVER QUI.
try:
    # Esegui in modalità visibile per debuggare inizialmente, poi puoi passare a headless
    # chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless") # Rimuovi il commento per eseguire senza finestra
    # chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument("--disable-dev-shm-usage")
    # driver = webdriver.Chrome(options=chrome_options)

    driver = webdriver.Chrome() # O webdriver.Firefox(), webdriver.Edge(), ecc.

except Exception as e:
    print(f"Errore nell'inizializzazione del WebDriver: {e}")
    print("Assicurati di aver installato il browser driver corretto (es. ChromeDriver) e che sia nel tuo PATH di sistema.")
    exit()


def scrape_knauf_products(url):
    """
    Naviga alla pagina Knauf, clicca su "Mostra di più" finché possibile,
    e poi estrae i dati dei prodotti.
    """
    print(f"Navigazione alla pagina: {url}")
    driver.get(url)

    # Attendi che la pagina iniziale carichi e che i primi prodotti siano visibili
    try:
        wait = WebDriverWait(driver, 20) # Attesa iniziale più lunga
        # Attendi che almeno un contenitore prodotto sia presente
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR)))
        print("Primi prodotti visibili.")
    except TimeoutException:
        print("Timeout nell'attesa dei primi prodotti. Procedo con l'HTML disponibile.")
        # Se i primi prodotti non appaiono, non ha senso continuare
        # Possibile che la pagina non abbia prodotti o il selettore sia sbagliato
        print("Nessun prodotto iniziale trovato. Controlla l'URL o il selettore.")
        # Ottieni l'HTML anche in caso di timeout iniziale per vedere se c'è qualcosa
        page_source = driver.page_source
        driver.quit()
        soup = BeautifulSoup(page_source, 'html.parser')
        product_containers_on_timeout = soup.select(PRODUCT_CONTAINER_SELECTOR)
        if not product_containers_on_timeout:
             return [] # Nessun prodotto trovato nemmeno nell'HTML iniziale
        else:
             print(f"Trovati {len(product_containers_on_timeout)} prodotti nell'HTML iniziale nonostante il timeout. Procedo con l'estrazione.")
             # Continua l'esecuzione con l'HTML parziale se sono stati trovati prodotti
             pass # Continua al codice di estrazione sotto


    # Cicla per cliccare sul pulsante "Mostra di più"
    while True:
        try:
            print("Ricerca del pulsante 'Mostra di più'...")
            # Cerca il pulsante "Mostra di più" e attendi che sia visibile e cliccabile
            wait = WebDriverWait(driver, 10) # Attesa per il pulsante
            load_more_button = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, LOAD_MORE_BUTTON_SELECTOR))
            )
            # Attendi anche che sia cliccabile
            load_more_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, LOAD_MORE_BUTTON_SELECTOR))
            )
            print("Pulsante 'Mostra di più' trovato e cliccabile.")

            # Scrolla il pulsante nella vista (a volte necessario)
            # Usa 'center' per posizionare il pulsante al centro della vista prima del click
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
            time.sleep(1) # Breve pausa dopo lo scrolllo

            # Ottieni il numero di prodotti PRIMA di cliccare
            initial_product_count = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR))
            print(f"Trovati {initial_product_count} prodotti prima di cliccare.")

            # Clicca sul pulsante
            # Prova prima il click diretto, se fallisce usa execute_script
            try:
                load_more_button.click()
                print("Cliccato su 'Mostra di più' (click diretto).")
            except ElementClickInterceptedException:
                print("Click diretto intercettato. Tentativo con execute_script.")
                driver.execute_script("arguments[0].click();", load_more_button)
                print("Cliccato su 'Mostra di più' (execute_script).")

            # Attendi che il numero di prodotti AUMENTI DOPO il click
            try:
                print("Attendere il caricamento di nuovi prodotti...")
                wait.until(
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR)) > initial_product_count
                )
                print(f"Nuovi prodotti caricati. Totale attuale: {len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR))}")
            except TimeoutException:
                print("Timeout nell'attesa di nuovi prodotti. Potrebbero non essercene altri o il caricamento è molto lento.")
                break # Esci dal ciclo se non appaiono nuovi prodotti


        except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
            # Il pulsante non è più presente, non è cliccabile, o c'è un errore di riferimento obsoleto
            print("Pulsante 'Mostra di più' non più presente o non cliccabile. Tutti i prodotti dovrebbero essere caricati.")
            break # Esci dal ciclo while True

    # Ora che tutti i prodotti sono caricati (o non ci sono più pulsanti), ottieni l'HTML
    # Se il timeout iniziale è scattato e siamo arrivati qui, l'HTML è già stato ottenuto
    # altrimenti lo otteniamo ora.
    try:
        page_source = driver.page_source
        print("Ottenuto l'HTML finale della pagina.")
    except Exception as e:
        print(f"Errore nell'ottenere la page_source dopo il caricamento: {e}")
        # Se non riusciamo a ottenere la page_source qui, usiamo quella ottenuta in caso di timeout iniziale se esiste
        if 'page_source' not in locals() and 'page_source' in globals():
             print("Utilizzo page_source ottenuta durante il timeout iniziale.")
        else:
             print("Impossibile ottenere la page_source. Uscita.")
             return [] # Esci se non hai l'HTML


    # Chiudi il browser Selenium
    driver.quit()
    print("Browser chiuso.")

    # Usa BeautifulSoup per analizzare l'HTML
    soup = BeautifulSoup(page_source, 'html.parser')

    all_products_data = []

    # Trova tutti i contenitori dei prodotti utilizzando il selettore corretto
    product_containers = soup.select(PRODUCT_CONTAINER_SELECTOR)
    print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR}') nell'HTML finale per l'estrazione dati.")

    if not product_containers:
        print("Nessun contenitore prodotto trovato nell'HTML finale. Controlla il selettore.")
        return []

    for i, container in enumerate(product_containers):
        # print(f"Elaborazione prodotto {i+1}/{len(product_containers)}...") # Messo a commento per ridurre output
        try:
            product_data = {
                "name": "N/A",
                "brand": "Knauf", # Marca fissa
                "description": "N/A",
                "price": "N/A", # Non sembra esserci un prezzo visibile
                "image_url": "N/A",
                "product_page_url": "N/A"
            }

            # Estrai il Nome del prodotto
            name_tag = container.select_one(PRODUCT_TITLE_SELECTOR)
            if name_tag:
                product_data["name"] = name_tag.get_text(strip=True)

            # Estrai la Descrizione del prodotto
            description_tag = container.select_one(PRODUCT_DESCRIPTION_SELECTOR)
            if description_tag:
                product_data["description"] = description_tag.get_text(strip=True)

            # Estrai l'URL della pagina di dettaglio del prodotto
            link_tag = container.select_one(PRODUCT_LINK_SELECTOR)
            if link_tag and link_tag.has_attr('href'):
                # Gli URL sembrano già assoluti su questo sito, ma controlliamo
                product_data["product_page_url"] = link_tag['href']

            # --- Estrazione Immagine di massima qualità da srcset ---
            img_tag = container.select_one(PRODUCT_IMAGE_SELECTOR)
            if img_tag:
                image_url = "N/A"
                # Priorità a srcset per l'immagine di massima qualità
                srcset_value = img_tag.get('srcset')
                if srcset_value:
                    best_url = None
                    max_descriptor_value = 0 # Usiamo questo per confrontare sia 'w' che 'x'

                    sources = srcset_value.split(',')
                    for source in sources:
                        parts = source.strip().split()
                        if len(parts) >= 1:
                            url = parts[0]
                            descriptor_value = 0
                            if len(parts) > 1:
                                descriptor = parts[1]
                                try:
                                    if descriptor.endswith('w'):
                                        descriptor_value = int(descriptor[:-1]) # Larghezza in pixel
                                    elif descriptor.endswith('x'):
                                        # Convertiamo la densità in un valore numerico per il confronto
                                        # Moltiplichiamo per 1000 per dare priorità alle larghezze reali se presenti
                                        descriptor_value = int(float(descriptor[:-1]) * 1000)
                                    else:
                                         print(f"Attenzione: Descrittore srcset sconosciuto: {descriptor}") # DEBUG

                                    if descriptor_value > max_descriptor_value:
                                        max_descriptor_value = descriptor_value
                                        best_url = url
                                except ValueError:
                                    print(f"Attenzione: Impossibile convertire descrittore srcset '{descriptor}' in numero.") # DEBUG


                    if best_url:
                        image_url = best_url
                        # print(f"DEBUG: Immagine selezionata da srcset: {image_url}") # DEBUG

                # Se srcset non ha fornito un URL valido, usa src come fallback (potrebbe essere di qualità inferiore)
                if image_url == "N/A" and img_tag.has_attr('src'):
                     src_url = img_tag['src']
                     if src_url and not src_url.startswith('data:'):
                         image_url = src_url
                         # print(f"DEBUG: Immagine selezionata da src (srcset non valido): {image_url}") # DEBUG
                     else:
                         # print("DEBUG: src è un placeholder data: URL.") # DEBUG
                         pass # src è un placeholder, image_url rimane N/A

                # Assicurati che l'URL immagine finale non sia un placeholder data:image
                if image_url and not image_url.startswith('data:image'):
                     # Gli URL delle immagini sembrano già assoluti, ma aggiungiamo un controllo base
                     if image_url.startswith('//'):
                         product_data["image_url"] = "https:" + image_url
                     else:
                         product_data["image_url"] = image_url
                else:
                    product_data["image_url"] = "N/A" # Assicurati che sia N/A se è un placeholder o None


            else:
                print("Tag immagine non trovato nel contenitore prodotto.") # DEBUG


            # --- Aggiungi i dati solo se il nome non è N/A ---
            if product_data.get("name") != "N/A":
                 all_products_data.append(product_data)
            else:
                 print(f"DEBUG: Saltato prodotto senza nome nel contenitore {i+1}.") # DEBUG


        except Exception as e:
            print(f"Errore durante l'elaborazione del contenitore prodotto {i+1}: {e}")
            continue # Continua con il prossimo prodotto anche in caso di errore su uno

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
        # Assicurati che ci siano dati prima di provare a ottenere le chiavi
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
    # Configurazione di Selenium WebDriver (spostata qui per usarla in entrambe le fasi)
    # ASSICURATI DI AVER SCARICATO IL DRIVER DEL BROWSER E CHE SIA NEL TUO PATH DI SISTEMA
    # O SPECIFICA IL PERCORSO COMPLETO AL DRIVER QUI.
    try:
        # Esegui in modalità visibile per debuggare inizialmente, poi puoi passare a headless
        # chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument("--headless") # Rimuovi il commento per eseguire senza finestra
        # chrome_options.add_argument("--no-sandbox")
        # chrome_options.add_argument("--disable-dev-shm-usage")
        # driver = webdriver.Chrome(options=chrome_options)

        driver = webdriver.Chrome() # O webdriver.Firefox(), webdriver.Edge(), ecc.

    except Exception as e:
        print(f"Errore nell'inizializzazione del WebDriver: {e}")
        print("Assicurati di aver installato il browser driver corretto (es. ChromeDriver) e che sia nel tuo PATH di sistema.")
        exit()


    # Esegui lo scraping della pagina Knauf per ottenere tutti i prodotti
    knauf_products = scrape_knauf_products(KNAUF_URL)

    # Salva i dati estratti (limitati per il test) in un file CSV
    # Usa la lista limitata per il salvataggio
    save_to_csv(knauf_products, OUTPUT_CSV_FILE)

    # Chiudi il browser Selenium UNA SOLA VOLTA alla fine
    try:
        driver.quit()
        print("Browser Selenium chiuso.")
    except Exception as e:
        print(f"Errore durante la chiusura del browser: {e}")
