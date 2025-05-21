import time
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup

# Impostazioni iniziali
# URL della singola pagina prodotto da scrapare
WEBER_PRODUCT_URL = "https://www.it.weber/sottofondi-colle-sigillanti/sottofondo-da-riempimento/sottofondo-da-riempimento/weberplan-isolight250"
OUTPUT_CSV_FILE = "weber_singolo_prodotto.csv"

# --- Selettori CSS per gli elementi sulla pagina di DETTAGLIO Prodotto ---
# Basati sull'HTML che hai fornito

# Selettore per il titolo del prodotto nella pagina di dettaglio
PRODUCT_TITLE_SELECTOR_DETAIL = "h1.product-title"
# Selettore per il blocco contenente la descrizione e altre info
DESCRIPTION_BLOCK_SELECTOR_DETAIL = "div.col-sm-6.col-lg-7"

# Selettore comune per elementi che potrebbero indicare un CAPTCHA o blocco (potrebbe richiedere aggiustamenti)
# Cerchiamo elementi comuni in pagine di blocco, come un form, un div specifico, o testo che menziona verifiche.
# Usiamo selettori CSS standard o XPath per cercare testo.
CAPTCHA_INDICATOR_SELECTORS = [
    ("css", "div#recaptcha"), # Esempio per Google reCAPTCHA (CSS)
    ("css", "div.cf-browser-verification"), # Esempio per Cloudflare (CSS)
    ("css", "form#challenge-form"), # Altro esempio per Cloudflare (CSS)
    ("xpath", "//div[contains(text(), 'Verifica di non essere un robot')]"), # Cerca div con testo specifico (XPath)
    ("xpath", "//div[contains(text(), 'Please verify you are human')]"), # Cerca div con testo specifico (XPath)
    ("xpath", "//iframe[contains(@title, 'challenge')]"), # Cerca iframe comuni nei CAPTCHA (XPath)
    ("xpath", "//div[contains(@class, 'captcha')]"), # Cerca div con classe che contiene 'captcha' (XPath)
]


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


def scrape_weber_single_product(driver, product_url):
    """
    Visita una singola pagina di dettaglio prodotto usando il driver Selenium,
    gestisce l'eventuale CAPTCHA manualmente, ed estrae nome e descrizione
    con la logica specificata.
    """
    print(f"Navigazione alla pagina prodotto: {product_url}")

    product_data = {
        "name": "N/A",
        "brand": "Weber", # Marca fissa
        "description": "N/A",
        "price": "N/A", # Non richiesto/visibile nella card/dettaglio forniti
        "image_url": "N/A", # Non richiesto/visibile nella card/dettaglio forniti
        "product_page_url": product_url # L'URL della pagina di dettaglio stessa
    }

    try:
        driver.get(product_url)

        # --- Gestione CAPTCHA ---
        print("Controllo per potenziale CAPTCHA o blocco...")
        captcha_present = False
        # Diamo un po' di tempo alla pagina per caricarsi e mostrare il CAPTCHA
        time.sleep(5)
        for selector_type, selector_value in CAPTCHA_INDICATOR_SELECTORS:
            try:
                if selector_type == "css":
                    # Usa By.CSS_SELECTOR per i selettori CSS
                    captcha_element = driver.find_element(By.CSS_SELECTOR, selector_value)
                elif selector_type == "xpath":
                    # Usa By.XPATH per i selettori XPath
                    captcha_element = driver.find_element(By.XPATH, selector_value)
                else:
                    print(f"Tipo di selettore sconosciuto: {selector_type}. Salto.")
                    continue # Salta questo selettore se il tipo non è riconosciuto

                if captcha_element.is_displayed():
                    captcha_present = True
                    print(f"Potenziale CAPTCHA o blocco rilevato usando selettore ({selector_type}): {selector_value}")
                    break # Esci dal ciclo selettori se ne trovi uno
            except NoSuchElementException:
                # L'elemento non è presente, continua a controllare gli altri selettori
                pass
            except Exception as e:
                # Stampa l'errore ma continua con gli altri selettori
                print(f"Errore durante il controllo CAPTCHA con selettore ({selector_type}) {selector_value}: {e}")


        if captcha_present:
            print("\n=========================================================")
            print("!!! CAPTCHA RILEVATO O PAGINA BLOCCATA !!!")
            print("Per favore, risolvi manualmente il CAPTCHA nella finestra del browser.")
            print("Una volta che la pagina del prodotto si è caricata correttamente,")
            print("torna qui e premi INVIO per continuare lo scraping.")
            print("=========================================================\n")

            # Attendi che l'utente risolva il CAPTCHA
            input("Premi INVIO dopo aver risolto il CAPTCHA e caricato la pagina del prodotto...")

            # Dopo che l'utente ha premuto INVIO, attendi che il titolo del prodotto sia visibile
            try:
                wait = WebDriverWait(driver, 60) # Attesa più lunga dopo il CAPTCHA per il contenuto reale
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_TITLE_SELECTOR_DETAIL)))
                print("Pagina prodotto caricata dopo la risoluzione del CAPTCHA.")
            except TimeoutException:
                print("Timeout nell'attesa del titolo prodotto dopo la risoluzione del CAPTCHA. La pagina potrebbe non essersi caricata correttamente.")
                # Se il titolo non appare, probabilmente lo scraping fallirà
                print("Impossibile trovare il titolo del prodotto. Uscita.")
                return product_data # Restituisce dati parziali (Nome sarà N/A)

        else:
            # Se nessun CAPTCHA sembra presente, attendi semplicemente che il titolo del prodotto appaia
            print("Nessun potenziale CAPTCHA rilevato. Attendo il caricamento del titolo prodotto...")
            try:
                wait = WebDriverWait(driver, 15) # Attesa normale per il titolo
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_TITLE_SELECTOR_DETAIL)))
                print("Pagina prodotto caricata (titolo trovato).")
            except TimeoutException:
                print("Timeout nell'attesa del titolo prodotto. Potrebbe non esserci nulla da scrapare o il selettore non è corretto.")
                print("Impossibile trovare il titolo del prodotto. Uscita.")
                return product_data # Restituisce dati parziali (Nome sarà N/A)

        # --- Fine Gestione CAPTCHA ---


        # Ottieni l'HTML dopo il caricamento completo (e l'eventuale risoluzione CAPTCHA)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Estrai il Nome del prodotto (anche se l'abbiamo già atteso, lo ri-estraiamo dalla soup)
        name_tag = soup.select_one(PRODUCT_TITLE_SELECTOR_DETAIL)
        if name_tag:
            product_data["name"] = name_tag.get_text(strip=True)
            print(f"  Trovato Nome: {product_data['name']}")
        else:
            print(f"  Nome prodotto ({PRODUCT_TITLE_SELECTOR_DETAIL}) non trovato nella pagina {product_url}.")


        # --- Estrazione e composizione della Descrizione ---
        description_block = soup.select_one(DESCRIPTION_BLOCK_SELECTOR_DETAIL)
        description_text = "" # Inizializza la descrizione come stringa vuota

        if description_block:
            print(f"  Trovato blocco descrizione ({DESCRIPTION_BLOCK_SELECTOR_DETAIL}).")

            # Cerca tutti i tag <p> all'interno del contenitore
            description_paragraphs = description_block.select("p")

            description_parts = [] # Lista temporanea per le parti della descrizione

            if description_paragraphs:
                # Se ci sono paragrafi, estrai il testo da ciascuno e unisci
                print(f"  Trovati {len(description_paragraphs)} paragrafi nella descrizione.")
                for p_tag in description_paragraphs:
                    # Crea una copia del tag per non modificare la soup originale
                    p_copy = p_tag.copy()
                    # Rimuovi tutti i tag <def> dalla copia
                    for def_tag in p_copy.select("def"):
                        def_tag.decompose()
                    # Estrai il testo pulito
                    paragraph_text = p_copy.get_text(separator=' ', strip=True)
                    if paragraph_text:
                        description_parts.append(paragraph_text)
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
                # Rimuovi spazi extra multipli che potrebbero derivare dal separator=' '
                description_text = ' '.join(description_text.split())


            # Aggiungi il testo dell'h2 "Supporto" e del p successivo se presenti
            supporto_h2 = description_block.find("h2", string="Supporto")
            if supporto_h2:
                 print("  Trovato tag <h2>Supporto</h2>.")
                 h2_text = supporto_h2.get_text(strip=True)
                 if h2_text:
                      # Aggiungi con doppio newline prima dell'intestazione "Supporto"
                      # Aggiungi solo se c'era già del testo nella descrizione
                      if description_text:
                          description_text += f"\n\n{h2_text}"
                      else:
                          description_text = h2_text
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
                           # Aggiungi solo se c'era già del testo nella descrizione
                           if description_text:
                               description_text += f"\n{p_after_h2_text}"
                           else:
                               description_text = p_after_h2_text
                       # print(f"   Estratto testo dal <p> dopo <h2> (snippet): {p_after_h2_text[:70]}...") # DEBUG
                      else:
                           print("   Testo estratto dal <p> dopo <h2> è vuoto.")
                 else:
                      print("   Tag <p> successivo a <h2>Supporto</h2> non trovato.")

            # Rimuovi eventuali spazi bianchi all'inizio o alla fine della descrizione finale
            description_text = description_text.strip()

            if description_text:
                 product_data["description"] = description_text
                 print(f"  Trovata Descrizione completa (snippet): {product_data['description'][:100]}...")
            else:
                 print("  Descrizione trovata nel contenitore ma vuota dopo l'estrazione e composizione.")


        else:
            print(f"  Blocco descrizione ({DESCRIPTION_BLOCK_SELECTOR_DETAIL}) non trovato nella pagina {product_url}.")
        # --- Fine Estrazione e composizione della Descrizione ---


        # Non estraiamo immagine e prezzo per ora, rimangono N/A come da richiesta implicita.

        # Return the data only if the name was found
        if product_data.get("name") != "N/A":
            return product_data
        else:
            print(f"Saltato scraping dettaglio per {product_url} perché il nome prodotto non è stato trovato.")
            return product_data # Return partial data even if name is N/A


    # Catch Selenium specific exceptions during navigation
    except (TimeoutException, NoSuchElementException) as e:
        print(f"Errore Selenium (Timeout o Elemento non trovato) durante lo scraping della pagina {product_url}: {e}")
    except Exception as e:
        print(f"Errore generico durante lo scraping della pagina {product_url}: {e}")
        return product_data # Return partial data in case of error


def save_to_csv(data, filename):
    """Salva una lista di dizionari in un file CSV."""
    # Incapsula il singolo dizionario in una lista per la funzione DictWriter
    data_list = [data] if data else []

    if not data_list:
        print("Nessun dato da salvare nel file CSV.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_dir, filename)

    try:
        # Ottieni le chiavi dal primo (e unico) dizionario per le intestazioni
        keys = data_list[0].keys()
        # Usa 'w' per scrivere (sovrascrive il file se esiste)
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader() # Scrive l'intestazione (nomi colonne)
            dict_writer.writerows(data_list) # Scrive i dati
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

        # Scrape la singola pagina prodotto
        # Questa funzione ora include la gestione manuale del CAPTCHA
        product_data = scrape_weber_single_product(driver, WEBER_PRODUCT_URL)

        # Salva i dati estratti in un file CSV
        if product_data and product_data.get("name") != "N/A":
            save_to_csv(product_data, OUTPUT_CSV_FILE)
        else:
            print("Nessun dato prodotto valido estratto per salvare.")

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
