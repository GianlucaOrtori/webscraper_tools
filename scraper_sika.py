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
SIKA_URL = "https://ita.sika.com/it/edilizia/prodotti-edilizia.html"
OUTPUT_CSV_FILE = "sika_prodotti.csv"

# Selettori CSS per gli elementi sulla pagina Sika
# Questi sono basati sull'HTML che hai fornito
PRODUCT_CONTAINER_SELECTOR = "div[data-list-item].cell" # Selettore per ogni singolo blocco prodotto
PRODUCT_LINK_SELECTOR = "a.cmp-teaser_productContainer" # Selettore per il link all'interno del blocco prodotto
PRODUCT_TITLE_SELECTOR = "h5.cmp-teaser_productContent__title" # Selettore per il titolo del prodotto
PRODUCT_DESCRIPTION_SELECTOR = "p.cmp-teaser_productContent__text" # Selettore per la descrizione del prodotto
# Selettore per l'immagine - basato sull'HTML della card che hai mostrato in precedenza
# Potrebbe essere necessario renderlo più specifico se ci sono altre immagini
PRODUCT_IMAGE_SELECTOR = "figure.cmp-teaser_productImage img" # Cerca l'img dentro figure.cmp-teaser_productImage

# Selettore corretto per il pulsante "Più Risultati"
LOAD_MORE_BUTTON_SELECTOR = ".load-more-results button" # Selettore per il pulsante "Più Risultati"

# Configurazione di Selenium WebDriver
# ASSICURATI DI AVER SCARICATO IL DRIVER DEL BROWSER E CHE SIA NEL TUO PATH DI SISTEMA
# O SPECIFICA IL PERCORSO COMPLETO AL DRIVER QUI.
# Esempio per ChromeDriver (assicurati che la versione corrisponda al tuo Chrome):
# driver_path = "/percorso/al/tuo/chromedriver"
# driver = webdriver.Chrome(executable_path=driver_path)
# Per un setup più semplice, se il driver è nel PATH:
try:
  # Opzioni per eseguire Chrome in modalità headless (senza aprire la finestra del browser)
  # Utile per lo scraping su server o per non avere la finestra che si apre
  # chrome_options = webdriver.ChromeOptions()
  # chrome_options.add_argument("--headless")
  # chrome_options.add_argument("--no-sandbox") # Utile in alcuni ambienti Linux
  # chrome_options.add_argument("--disable-dev-shm-usage") # Utile in alcuni ambienti Linux
  # driver = webdriver.Chrome(options=chrome_options)

  # Esegui in modalità visibile per debuggare e vedere cosa succede
  driver = webdriver.Chrome() # O webdriver.Firefox(), webdriver.Edge(), ecc.

except Exception as e:
  print(f"Errore nell'inizializzazione del WebDriver: {e}")
  print("Assicurati di aver installato il browser driver corretto (es. ChromeDriver) e che sia nel tuo PATH di sistema.")
  exit() # Esci se non riesci a inizializzare il driver


def scrape_sika_products(url):
  """
  Naviga alla pagina Sika, clicca su "Visualizza di più" finché possibile,
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
    return []


  # Cicla per cliccare sul pulsante "Visualizza di più"
  while True:
    try:
      print("Ricerca del pulsante 'Visualizza di più'...")
      # Cerca il pulsante "Visualizza di più" e attendi che sia visibile e cliccabile
      wait = WebDriverWait(driver, 15) # Aumentata leggermente l'attesa per il pulsante
      load_more_button = wait.until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, LOAD_MORE_BUTTON_SELECTOR))
      )
      # Attendi anche che sia cliccabile
      load_more_button = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, LOAD_MORE_BUTTON_SELECTOR))
      )
      print("Pulsante 'Visualizza di più' trovato e cliccabile.")

      # Scrolla il pulsante nella vista (a volte necessario)
      driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
      time.sleep(0.5) # Breve pausa dopo lo scroll

      # Ottieni il numero di prodotti PRIMA di cliccare
      initial_product_count = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_CONTAINER_SELECTOR))
      print(f"Trovati {initial_product_count} prodotti prima di cliccare.")

      # Clicca sul pulsante
      # Prova prima il click diretto, se fallisce usa execute_script
      try:
        load_more_button.click()
        print("Cliccato su 'Visualizza di più' (click diretto).")
      except ElementClickInterceptedException:
        print("Click diretto intercettato. Tentativo con execute_script.")
        driver.execute_script("arguments[0].click();", load_more_button)
        print("Cliccato su 'Visualizza di più' (execute_script).")

      # Attendi che il numero di prodotti AUMENTI DOPO il click
      # Questa è una strategia di attesa più robusta di un sleep fisso
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
      print("Pulsante 'Visualizza di più' non più presente o non cliccabile. Tutti i prodotti dovrebbero essere caricati.")
      break # Esci dal ciclo while True

  # Ora che tutti i prodotti sono caricati (o non ci sono più pulsanti), ottieni l'HTML
  print("Ottenere l'HTML finale della pagina...")
  page_source = driver.page_source

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
        "brand": "Sika", # Marca fissa per questo sito
        "description": "N/A",
        "price": "N/A", # Non sembra esserci un prezzo visibile
        "image_url": "N/A",
        "product_page_url": "N/A"
      }

      # Estrai il link e l'URL della pagina di dettaglio
      link_tag = container.select_one(PRODUCT_LINK_SELECTOR)
      if link_tag and link_tag.has_attr('href'):
        relative_url = link_tag['href']
        # Assicurati che l'URL sia assoluto se necessario (Sika sembra usare percorsi relativi che partono dalla root)
        if relative_url.startswith('/'):
          # Costruisci l'URL completo basato sulla struttura del sito Sika
          product_data["product_page_url"] = "https://ita.sika.com" + relative_url
        else:
          product_data["product_page_url"] = relative_url # Già assoluto o altro formato inatteso

      # Estrai il Nome del prodotto
      name_tag = container.select_one(PRODUCT_TITLE_SELECTOR)
      if name_tag:
        product_data["name"] = name_tag.get_text(strip=True)

      # Estrai la Descrizione del prodotto
      description_tag = container.select_one(PRODUCT_DESCRIPTION_SELECTOR)
      if description_tag:
        product_data["description"] = description_tag.get_text(strip=True)

      # Estrai l'URL dell'immagine
      # Cerca il tag img all'interno del selettore più specifico
      img_tag = container.select_one(PRODUCT_IMAGE_SELECTOR)
      if img_tag and img_tag.has_attr('src'):
        image_src = img_tag['src']
        # Costruisci l'URL completo dell'immagine se è relativo
        if image_src.startswith('//'):
          product_data["image_url"] = "https:" + image_src
        elif image_src.startswith('/'):
          # Assumi che le immagini relative partano dalla root del sito Sika
          product_data["image_url"] = "https://ita.sika.com" + image_src
        elif not image_src.startswith('http'):
          # Gestisci altri casi di URL relativo se necessario
          product_data["image_url"] = "https://ita.sika.com/" + image_src.lstrip("/")
        else:
          product_data["image_url"] = image_src # Già URL assoluto


      # Aggiungi i dati estratti alla lista principale
      all_products_data.append(product_data)

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
  # Esegui lo scraping della pagina Sika
  sika_products = scrape_sika_products(SIKA_URL)

  # Salva i dati estratti in un file CSV
  save_to_csv(sika_products, OUTPUT_CSV_FILE)
