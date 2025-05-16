import requests
from bs4 import BeautifulSoup
import csv
import os
import time

# Impostazioni iniziali
# L'URL iniziale della prima pagina
MAPEI_START_URL = "https://www.fvledilizia.it/brand/19-mapei?srsltid=AfmBOop-i97Z14X4AtNB5dm9vH7XEzHKv_RLAcQlrwapb9pj99L18AyG"
OUTPUT_CSV_FILE = "mapei_prodotti_paginato.csv" # Nuovo nome file per distinguere

# Intestazioni per simulare una richiesta da browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- MODIFICA QUI: Selettore corretto per ogni singolo contenitore prodotto ---
# Basato sull'HTML fornito, il contenitore è un tag <article> con classe product-miniature
PRODUCT_CONTAINER_SELECTOR = "article.product-miniature"
# --- FINE MODIFICA ---

# Selettore per il link "Successivo" nella paginazione
NEXT_PAGE_SELECTOR = "a.page-link.next.js-search-link"


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

def scrape_mapei_products_paginated(start_url):
    """
    Scarica le pagine di elenco prodotti Mapei con paginazione e estrae i dati.
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

        print(f"DEBUG: Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR}') su {current_url}.") # DEBUG PRINT

        if not product_containers:
            print(f"Nessun contenitore prodotto trovato su {current_url}. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR}'.")
            # Se non troviamo prodotti ma c'era un URL successivo, potremmo voler continuare.
            # Ma se non ci sono prodotti e nessun link successivo, il ciclo finirà comunque.


        for i, container in enumerate(product_containers):
            # print(f"Elaborazione prodotto {i+1} su {len(product_containers)}...") # Messo a commento
            try:
                product_data = {
                    "name": "N/A",
                    "brand": "Mapei", # Marca fissa
                    "description": "N/A", # Non estraiamo la descrizione breve dalla lista per ora
                    "price": "N/A", # Non estraiamo il prezzo per ora
                    "image_url": "N/A",
                    "product_page_url": "N/A" # L'URL della pagina di dettaglio, se presente
                }

                # Estrai il Nome del prodotto e l'URL della pagina di dettaglio
                # Cerca l'h2 con classe product-title e il suo link <a>
                title_link_tag = container.select_one("h2.product-title a")
                if title_link_tag:
                    product_data["name"] = title_link_tag.get_text(strip=True)
                    product_data["product_page_url"] = title_link_tag.get('href', 'N/A')
                    # print(f"Trovato Nome: {product_data['name']}, URL: {product_data['product_page_url']}") # Messo a commento
                else:
                    print("Nome prodotto (h2.product-title a) non trovato nel contenitore.")


                # Estrai l'URL dell'immagine
                # Cerca il tag img e prendi l'attributo data-full-size-image-url
                img_tag = container.select_one("img") # Cerca qualsiasi tag img nel contenitore
                if img_tag:
                    # Priorità a data-full-size-image-url, poi data-src, poi src
                    image_url = img_tag.get('data-full-size-image-url')
                    if not image_url:
                        image_url = img_tag.get('data-src')
                    if not image_url:
                        image_url = img_tag.get('src')

                    # Assicurati che l'URL non sia un placeholder data:image
                    if image_url and not image_url.startswith('data:image'):
                        # Gli URL sembrano già assoluti, ma aggiungiamo un controllo base
                        if image_url.startswith('//'):
                            product_data["image_url"] = "https:" + image_url
                        else:
                            product_data["image_url"] = image_url
                        # print(f"Trovata Immagine: {product_data['image_url']}") # Messo a commento
                    else:
                        print("Tag immagine trovato ma l'URL è un placeholder data:image o vuoto.")
                else:
                    print("Tag immagine trovato ma senza attributi URL utili (data-full-size-image-url, data-src, src).")


                # Aggiungi i dati estratti alla lista principale
                all_products_data.append(product_data)

            except Exception as e:
                print(f"Errore durante l'elaborazione del contenitore prodotto {i+1}: {e}")
                continue # Continua con il prossimo prodotto anche in caso di errore su uno

        time.sleep(0.5) # Breve pausa tra l'elaborazione dei prodotti (opzionale)


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
    # Esegui lo scraping della pagina Mapei con paginazione
    mapei_products = scrape_mapei_products_paginated(MAPEI_START_URL)

    # Salva i dati estratti in un file CSV
    save_to_csv(mapei_products, OUTPUT_CSV_FILE)
