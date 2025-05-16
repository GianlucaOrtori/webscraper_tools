import requests
from bs4 import BeautifulSoup
import csv
import os
import time
from urllib.parse import urljoin, urlparse # Importa urljoin e urlparse per debug

# Impostazioni iniziali
# Lista per contenere gli URL delle pagine di catalogo da cui iniziare lo scraping.
# Ho inserito qui tutti i link che hai fornito.
MAURER_URLS = [
    "https://www.maurer.ferritalia.it/catalogo/settore/2/desc/Accessori-per-utensili-elettrici",
    "https://www.maurer.ferritalia.it/catalogo/settore/4/desc/Pinze---Martelli",
    "https://www.maurer.ferritalia.it/catalogo/settore/3/desc/Chiavi-e-cacciaviti",
    "https://www.maurer.ferritalia.it/catalogo/settore/5/desc/Utensili-da-taglio-e-assemblaggio",
    "https://www.maurer.ferritalia.it/catalogo/settore/6/desc/Attrezzature---Edilizia",
    "https://www.maurer.ferritalia.it/catalogo/settore/14/desc/Pittura",
    "https://www.maurer.ferritalia.it/catalogo/settore/7/desc/Strumenti-di-misura",
    "https://www.maurer.ferritalia.it/catalogo/settore/8/desc/Sollevamento-e-trasporto",
    "https://www.maurer.ferritalia.it/catalogo/settore/9/desc/Materiale-elettrico",
    "https://www.maurer.ferritalia.it/catalogo/settore/10/desc/Fissaggio---Sigillanti",
    "https://www.maurer.ferritalia.it/catalogo/settore/11/desc/Articoli-di-protezione",
    "https://www.maurer.ferritalia.it/catalogo/settore/12/desc/Ferramenta",
    "https://www.maurer.ferritalia.it/catalogo/settore/15/desc/Reti-e-coperture",
    "https://www.maurer.ferritalia.it/catalogo/settore/16/desc/Idraulica---Arredo-bagno",
    "https://www.maurer.ferritalia.it/catalogo/settore/13/desc/Casalinghi",
    "https://www.maurer.ferritalia.it/catalogo/settore/31/desc/Prodotti-di-manutenzione",
    "https://www.maurer.ferritalia.it/catalogo/settore/33/desc/Zanzariere"
]
OUTPUT_CSV_FILE = "maurer_prodotti_paginato.csv" # File di output

# Intestazioni per simulare una richiesta da browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Selettori CSS per gli elementi sulla pagina di elenco Maurer ---
# Basati sull'HTML che hai fornito

# Selettore per ogni singolo contenitore prodotto (la card completa)
PRODUCT_CONTAINER_SELECTOR = "div.card"

# Selettore per il nome del prodotto (all'interno di h5.card-title.title-modello)
PRODUCT_NAME_SELECTOR = "h5.card-title.title-modello"

# Selettore per il tag immagine del prodotto (all'interno di div.card-img-bottom.catalogue-image img)
PRODUCT_IMAGE_SELECTOR = "div.card-img-bottom.catalogue-image img"

# Selettore per il link "Successivo" nella paginazione
# Usiamo l'attributo aria-label per specificare il link "Next"
NEXT_PAGE_SELECTOR = "a.page-link[aria-label='Next']"

# URL base del sito per costruire URL completi (per le immagini relative)
BASE_URL = "https://www.maurer.ferritalia.it"


def get_soup(url):
    """Invia una richiesta GET all'URL e restituisce un oggetto BeautifulSoup."""
    try:
        print(f"Fetching URL: {url}")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status() # Solleva un'eccezione per stati di errore (4xx, 5xx)
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup
    except requests.exceptions.Timeout:
        print(f"Timeout durante la richiesta a {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Errore durante la richiesta a {url}: {e}")
        return None

def scrape_maurer_page(url):
    """
    Scarica una singola pagina di elenco prodotti Maurer, estrae nome e immagine,
    e trova l'URL della pagina successiva (se esiste).
    """
    soup = get_soup(url)
    if not soup:
        # get_soup ha già stampato un messaggio di errore
        return [], None # Restituisce lista vuota di prodotti e nessun URL successivo

    products_on_page = []

    # Trova tutti i contenitori prodotto nella pagina corrente
    product_containers = soup.select(PRODUCT_CONTAINER_SELECTOR)

    print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR}') su {url}.")

    if not product_containers:
        print(f"Nessun contenitore prodotto trovato su {url}. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR}'.")
        # Stampa una parte dell'HTML per debuggare se non trova contenitori
        print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
        print(soup.prettify()[:2000])
        # Anche se non trova prodotti, controlla se c'è un link alla pagina successiva
        pass # Continua per cercare il link di paginazione


    for i, container in enumerate(product_containers):
        # print(f"Elaborazione prodotto {i+1}/{len(product_containers)} su {url}...") # Messo a commento
        try:
            product_data = {
                "name": "N/A",
                "brand": "Maurer", # Marca fissa
                "description": "N/A", # La descrizione non è nella card
                "price": "N/A", # Il prezzo non è nella card
                "image_url": "N/A",
                "product_page_url": "N/A" # L'URL della pagina di dettaglio (non lo estraiamo per ora)
            }

            # Estrai il Nome del prodotto
            name_tag = container.select_one(PRODUCT_NAME_SELECTOR)
            if name_tag:
                product_data["name"] = name_tag.get_text(strip=True)
                # print(f"Trovato Nome: {product_data['name']}") # Messo a commento
            # else: name rimane N/A


            # --- Estrai l'URL dell'immagine usando urljoin ---
            img_tag = container.select_one(PRODUCT_IMAGE_SELECTOR)
            if img_tag:
                # print(f"DEBUG IMMAGINE: Trovato tag immagine per prodotto {i+1}.") # DEBUG
                if img_tag.has_attr('src'):
                    image_src = img_tag['src']
                    # print(f"DEBUG IMMAGINE: Valore attributo src trovato: '{image_src}'") # DEBUG
                    # Usa urljoin per costruire l'URL completo, gestisce la codifica
                    if image_src and not image_src.startswith('data:image'): # Ignora placeholder data:image
                        try:
                            # Costruisci l'URL completo usando urljoin
                            full_image_url = urljoin(BASE_URL, image_src)
                            product_data["image_url"] = full_image_url
                            # print(f"DEBUG IMMAGINE: URL immagine costruito con urljoin: '{product_data['image_url']}'") # DEBUG

                            # Ulteriore controllo: provare a fare una richiesta HEAD per vedere se l'URL funziona
                            # Rimosso debug HEAD per ridurre output, riattivare se necessario
                            # try:
                            #     head_response = requests.head(product_data["image_url"], headers=HEADERS, timeout=5)
                            #     if head_response.status_code == 200:
                            #         print("DEBUG IMMAGINE: Richiesta HEAD all'URL immagine completata con successo (Status 200).")
                            #     else:
                            #         print(f"DEBUG IMMAGINE: Richiesta HEAD all'URL immagine fallita (Status {head_response.status_code}). L'URL potrebbe non essere valido.")
                            # except requests.exceptions.RequestException as req_err:
                            #     print(f"DEBUG IMMAGINE: Errore nella richiesta HEAD all'URL immagine: {req_err}")


                        except Exception as urljoin_err:
                            print(f"DEBUG IMMAGINE: Errore durante la costruzione dell'URL con urljoin: {urljoin_err}")
                            product_data["image_url"] = "N/A" # Imposta a N/A in caso di errore urljoin

                    else:
                        # print("DEBUG IMMAGINE: L'attributo src è vuoto o un placeholder data:image. URL immagine impostato a N/A.") # DEBUG
                        product_data["image_url"] = "N/A" # Assicurati che sia N/A
                else:
                    # print("DEBUG IMMAGINE: Tag immagine trovato ma senza attributo src. URL immagine impostato a N/A.") # DEBUG
                    product_data["image_url"] = "N/A" # Assicurati che sia N/A
            else:
                # print(f"DEBUG IMMAGINE: Tag immagine ({PRODUCT_IMAGE_SELECTOR}) non trovato nel contenitore prodotto {i+1}. URL immagine impostato a N/A.") # DEBUG
                product_data["image_url"] = "N/A" # Assicurati che sia N/A
            # --- FINE MODIFICA ---


            # Aggiungi i dati estratti alla lista dei prodotti di questa pagina
            # Aggiungiamo solo se abbiamo trovato almeno il nome
            if product_data.get("name") != "N/A":
                products_on_page.append(product_data)
            # else: Saltato prodotto senza nome


        except Exception as e:
            print(f"Errore durante l'elaborazione del contenitore prodotto {i+1} su {url}: {e}")
            continue # Continua con il prossimo prodotto anche in caso di errore su uno

    # Cerca il link per la pagina successiva
    # Il link della paginazione potrebbe trovarsi all'interno di una lista (ul)
    # Cerchiamo un link con la classe page-link e l'attributo aria-label='Next'
    next_page_link = soup.select_one(NEXT_PAGE_SELECTOR)

    next_listing_url = None
    if next_page_link and next_page_link.has_attr('href'):
        relative_next_url = next_page_link['href']
        # Gli URL di paginazione sembrano relativi, costruiamo l'URL completo
        # Usiamo urljoin anche qui per coerenza, anche se per gli URL di paginazione
        # potrebbe non essere strettamente necessario se non contengono caratteri speciali
        next_listing_url = urljoin(BASE_URL, relative_next_url)


    return products_on_page, next_listing_url


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
        # Usa 'w' per scrivere (sovrascrive il file se esiste), 'a' per appendere
        # Visto che scrapiamo pagine multiple e vogliamo tutto in un file, usiamo 'w'
        # perché raccogliamo tutti i dati prima di salvare.
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
    all_scraped_products = []

    # Itera su ogni URL iniziale fornito
    for start_listing_url in MAURER_URLS:
        current_listing_url = start_listing_url

        # Loop per gestire la paginazione delle pagine di elenco per questa categoria
        while current_listing_url:
            print(f"\n--- Scraping Pagina di Elenco: {current_listing_url} ---")

            # Scrape la pagina corrente ed ottieni l'URL della pagina successiva
            products_on_page, next_listing_url = scrape_maurer_page(current_listing_url)

            # Aggiungi i prodotti trovati sulla pagina corrente alla lista totale
            all_scraped_products.extend(products_on_page)

            # Passa all'URL della pagina di elenco successiva per la prossima iterazione del ciclo while
            current_listing_url = next_listing_url
            if current_listing_url:
                print(f"Passando alla pagina di elenco successiva: {current_listing_url}")
                time.sleep(2) # Pausa tra le pagine di elenco
            else:
                print("\nNessuna pagina di elenco successiva trovata per questa categoria.")

        print(f"\nCompletato lo scraping per l'URL iniziale {start_listing_url}.")


    # Salva tutti i dati raccolti da tutte le pagine in un unico file CSV
    print(f"\nCompletato lo scraping di {len(MAURER_URLS)} URL iniziali.")
    print(f"Totale prodotti raccolti: {len(all_scraped_products)}")
    save_to_csv(all_scraped_products, OUTPUT_CSV_FILE)
