import requests
from bs4 import BeautifulSoup
import csv
import os
import time

# Impostazioni iniziali
# L'URL iniziale della prima pagina dei prodotti BigMat
BIGMAT_START_URL = "https://www.bigmat.it/brand/314-bigmat?resultsPerPage=48"
OUTPUT_CSV_FILE = "bigmat_prodotti_paginato.csv" # File di output

# Intestazioni per simulare una richiesta da browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Selettori CSS per gli elementi sulla pagina di elenco BigMat ---
# Basati sull'HTML che hai fornito

# Selettore per ogni singolo contenitore prodotto (la card completa)
PRODUCT_CONTAINER_SELECTOR = "article.product-miniature"

# Selettore per il nome del prodotto (all'interno di h2.product-title a)
PRODUCT_NAME_SELECTOR = "h2.product-title a"

# Selettore per la descrizione breve del prodotto (all'interno di div.short-desc p)
PRODUCT_DESCRIPTION_SELECTOR = "div.short-desc p"

# Selettore per il tag immagine del prodotto (all'interno di picture.cover-image img)
PRODUCT_IMAGE_SELECTOR = "picture.cover-image img"

# --- MODIFICA QUI: Selettore corretto per il link "Successivo" nella paginazione ---
# Basato sull'HTML fornito, usiamo le classi 'next' e 'js-search-link'
NEXT_PAGE_SELECTOR = "a.next.js-search-link"
# --- FINE MODIFICA ---

# URL base del sito per costruire URL completi se necessario
BASE_URL = "https://www.bigmat.it"


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

def scrape_bigmat_products_paginated(start_url):
    """
    Scarica le pagine di elenco prodotti BigMat con paginazione e estrae i dati.
    """
    all_products_data = []
    current_url = start_url

    while current_url:
        soup = get_soup(current_url)
        if not soup:
            print(f"Impossibile recuperare la pagina: {current_url}. Interruzione scraping.")
            break # Esci dal ciclo se non riesci a scaricare una pagina

        # Trova tutti i contenitori prodotto nella pagina corrente
        product_containers = soup.select(PRODUCT_CONTAINER_SELECTOR)

        print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR}') su {current_url}.")

        if not product_containers:
            print(f"Nessun contenitore prodotto trovato su {current_url}. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR}'.")
            # Stampa una parte dell'HTML per debuggare se non trova contenitori
            print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
            print(soup.prettify()[:2000])
            # Se non ci sono prodotti, controlla comunque se c'è un link alla pagina successiva
            # per evitare di bloccare lo scraping se una pagina è vuota per qualche motivo.
            pass


        for i, container in enumerate(product_containers):
            # print(f"Elaborazione prodotto {i+1}/{len(product_containers)} su {current_url}...") # Messo a commento
            try:
                product_data = {
                    "name": "N/A",
                    "brand": "BigMat", # Marca fissa
                    "description": "N/A",
                    "price": "N/A", # Il prezzo è presente ma non richiesto, impostato a N/A
                    "image_url": "N/A",
                    "product_page_url": "N/A" # L'URL della pagina di dettaglio
                }

                # Estrai il Nome del prodotto e l'URL della pagina di dettaglio
                title_link_tag = container.select_one(PRODUCT_NAME_SELECTOR)
                if title_link_tag:
                    product_data["name"] = title_link_tag.get_text(strip=True)
                    product_data["product_page_url"] = title_link_tag.get('href', 'N/A')
                    # Gli URL sembrano già assoluti su questo sito, ma aggiungiamo un controllo base
                    if product_data["product_page_url"] != 'N/A' and product_data["product_page_url"].startswith('/'):
                         product_data["product_page_url"] = BASE_URL + product_data["product_page_url"]

                    # print(f"Trovato Nome: {product_data['name']}, URL: {product_data['product_page_url']}") # Messo a commento
                # else: name e product_page_url rimangono N/A


                # Estrai la Descrizione breve
                description_tag = container.select_one(PRODUCT_DESCRIPTION_SELECTOR)
                if description_tag:
                    product_data["description"] = description_tag.get_text(strip=True)
                    # print(f"Trovata Descrizione: {product_data['description'][:50]}...") # Messo a commento
                # else: la descrizione potrebbe non essere sempre presente, N/A è il default


                # Estrai l'URL dell'immagine (priorità data-image-large-src, poi data-image-medium-src, poi src)
                img_tag = container.select_one(PRODUCT_IMAGE_SELECTOR)
                if img_tag:
                    # Priorità a data-image-large-src per l'immagine di massima qualità
                    image_url = img_tag.get('data-image-large-src')
                    if not image_url:
                        image_url = img_tag.get('data-image-medium-src') # Fallback a data-image-medium-src
                    if not image_url:
                        image_url = img_tag.get('src') # Ultimo fallback a src

                    # Assicurati che l'URL non sia un placeholder data:image
                    if image_url and not image_url.startswith('data:image'):
                         # Gli URL delle immagini sembrano già assoluti, ma aggiungiamo un controllo base
                         if image_url.startswith('//'):
                             product_data["image_url"] = "https:" + image_url
                         else:
                             product_data["image_url"] = image_url # Già assoluto

                         # print(f"Trovata Immagine: {product_data['image_url']}") # Messo a commento
                    # else: image_url rimane N/A se placeholder o vuoto
                # else: img_tag non trovato, image_url rimane N/A


                # Aggiungi i dati estratti alla lista principale
                # Aggiungiamo solo se abbiamo trovato almeno il nome
                if product_data.get("name") != "N/A":
                    all_products_data.append(product_data)
                # else: Saltato prodotto senza nome, non stampare per non intasare l'output


            except Exception as e:
                print(f"Errore durante l'elaborazione del contenitore prodotto {i+1} su {current_url}: {e}")
                continue # Continua con il prossimo prodotto anche in caso di errore su uno

        time.sleep(1) # Breve pausa tra l'elaborazione dei prodotti (opzionale)


        # --- Gestione Paginazione ---
        # Cerca il link "Successivo"
        next_page_link = soup.select_one(NEXT_PAGE_SELECTOR)

        if next_page_link and next_page_link.has_attr('href'):
            next_url = next_page_link['href']
            print(f"\nTrovato link pagina successiva: {next_url}")
            current_url = next_url # Imposta l'URL corrente alla pagina successiva
            time.sleep(2) # Pausa più lunga tra le pagine per non sovraccaricare il server
        else:
            print("\nNessun link pagina successiva trovato. Fine della paginazione.")
            current_url = None # Imposta a None per uscire dal ciclo while

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
    # Esegui lo scraping della pagina BigMat con paginazione
    bigmat_products = scrape_bigmat_products_paginated(BIGMAT_START_URL)

    # Salva i dati estratti in un file CSV
    save_to_csv(bigmat_products, OUTPUT_CSV_FILE)
