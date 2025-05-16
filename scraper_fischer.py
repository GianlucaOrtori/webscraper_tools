import requests
from bs4 import BeautifulSoup
import csv
import os
import time
import re # Importa il modulo re per le espressioni regolari

# Impostazioni iniziali
# Lista per contenere gli URL delle pagine da scrapare.
# Ho inserito qui tutti i link che hai fornito.
FISCHER_URLS = [
    "https://www.fischer.it/it-it/prodotti/ancoranti-chimici",
    "https://www.fischer.it/it-it/prodotti/ancoranti-metallici",
    "https://www.fischer.it/it-it/prodotti/fissaggi-universali",
    "https://www.fischer.it/it-it/prodotti/fissaggi-prolungati",
    "https://www.fischer.it/it-it/prodotti/fissaggi-cartongesso-e-soffitti",
    "https://www.fischer.it/it-it/prodotti/schiume-e-sigillanti",
    "https://www.fischer.it/it-it/prodotti/adesivi-nastri-e-spray",
    "https://www.fischer.it/it-it/prodotti/fissaggi-di-pannelli-isolanti-e-cappotti",
    "https://www.fischer.it/it-it/prodotti/fissaggi-su-cappotti",
    "https://www.fischer.it/it-it/prodotti/fissaggi-idrotermosanitari",
    "https://www.fischer.it/it-it/prodotti/fissaggi-per-materiali-elettrici",
    "https://www.fischer.it/it-it/prodotti/fissaggi-per-ponteggi",
    "https://www.fischer.it/it-it/prodotti/viti-legno-e-connettori",
    "https://www.fischer.it/it-it/prodotti/punte-e-inserti",
    "https://www.fischer.it/it-it/prodotti/sistemi-per-impiantistica",
    "https://www.fischer.it/it-it/prodotti/sistemi-per-il-solare",
    "https://www.fischer.it/it-it/prodotti/sistemi-antintrusione",
    "https://www.fischer.it/it-it/prodotti/sistemi-di-protezione-al-fuoco",
    "https://www.fischer.it/it-it/prodotti/taglio-e-abrasione",
    "https://www.fischer.it/it-it/prodotti/linea-fai-da-te",
    "https://www.fischer.it/it-it/prodotti/binari-cast-in"
]
OUTPUT_CSV_FILE = "fischer_prodotti.csv"

# Intestazioni per simulare una richiesta da browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Selettori CSS per gli elementi sulla scheda prodotto Fischer ---
# Basati sull'HTML prototipo che hai fornito

# Selettore per ogni singolo contenitore prodotto (la card completa)
PRODUCT_CONTAINER_SELECTOR = "div.fact-finder-item"

# Selettore per il nome del prodotto
PRODUCT_NAME_SELECTOR = "div.fact-finder-item__name"

# Selettore per la descrizione del prodotto
PRODUCT_DESCRIPTION_SELECTOR = "div.fact-finder-item__description"

# Selettore per il tag picture che contiene le immagini del prodotto
PRODUCT_PICTURE_SELECTOR = "picture.fact-finder-item__image"

# Selettore per il tag img all'interno della picture (usato come fallback)
PRODUCT_IMAGE_SELECTOR_IMG_TAG = "img"

# URL base per costruire URL completi se necessario (anche se sembrano già assoluti)
FISCHER_BASE_URL = "https://www.fischer.it"


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

def scrape_fischer_page(url):
    """
    Scarica una singola pagina di elenco prodotti Fischer e estrae i dati
    di nome, descrizione e immagine di massima qualità per ogni prodotto.
    """
    soup = get_soup(url)
    if not soup:
        # get_soup ha già stampato un messaggio di errore
        return [] # Restituisce una lista vuota se la pagina non può essere recuperata

    products_on_page = []

    # Trova tutti i contenitori prodotto nella pagina corrente
    product_containers = soup.select(PRODUCT_CONTAINER_SELECTOR)

    print(f"Trovati {len(product_containers)} contenitori prodotto ('{PRODUCT_CONTAINER_SELECTOR}') su {url}.")

    if not product_containers:
        print(f"Nessun contenitore prodotto trovato su {url}. Controlla il selettore '{PRODUCT_CONTAINER_SELECTOR}'.")
        # Stampa una parte dell'HTML per aiutarti a debuggare solo se non trova contenitori
        print("Primi 2000 caratteri dell'HTML della pagina per debug (nessun contenitore trovato):")
        print(soup.prettify()[:2000])
        return []


    for i, container in enumerate(product_containers):
        # print(f"Elaborazione prodotto {i+1}/{len(product_containers)} su {url}...") # Messo a commento
        try:
            product_data = {
                "name": "N/A",
                "brand": "Fischer", # Marca fissa
                "description": "N/A",
                "price": "N/A", # Non sembra esserci un prezzo visibile nella card
                "image_url": "N/A",
                "product_page_url": "N/A" # L'URL della pagina di dettaglio, se presente
            }

            # Estrai il Nome del prodotto
            name_tag = container.select_one(PRODUCT_NAME_SELECTOR)
            if name_tag:
                product_data["name"] = name_tag.get_text(strip=True)
                # print(f"Trovato Nome: {product_data['name']}") # Messo a commento


            # Estrai la Descrizione del prodotto
            description_tag = container.select_one(PRODUCT_DESCRIPTION_SELECTOR)
            if description_tag:
                product_data["description"] = description_tag.get_text(strip=True)
                # print(f"Trovata Descrizione: {product_data['description'][:50]}...") # Messo a commento
            # else: la descrizione potrebbe non essere sempre presente, N/A è il default


            # Estrai l'URL della pagina di dettaglio del prodotto
            # Il link è l'attributo href del tag <a> che racchiude l'intera card
            link_tag = container.select_one("a.fact-finder-item__tile")
            if link_tag and link_tag.has_attr('href'):
                relative_url = link_tag['href']
                # Costruisci l'URL completo se è relativo
                if relative_url.startswith('/'):
                    product_data["product_page_url"] = FISCHER_BASE_URL + relative_url
                else:
                    product_data["product_page_url"] = relative_url # Assumi sia già assoluto
                # print(f"Trovato URL pagina prodotto: {product_data['product_page_url']}") # Messo a commento
            # else: product_page_url rimane N/A


            # --- Estrai l'URL dell'immagine di massima qualità ---
            image_url = "N/A"
            # Trova il tag <picture>
            picture_tag = container.select_one(PRODUCT_PICTURE_SELECTOR)

            if picture_tag:
                best_url = None
                max_descriptor_value = 0

                # 1. Cerca nei tag <source> all'interno della <picture>
                source_tags = picture_tag.select("source")
                for source_tag in source_tags:
                    srcset_value = source_tag.get('srcset')
                    if srcset_value:
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
                                             descriptor_value = int(float(descriptor[:-1]) * 1000) # Moltiplica per dare priorità
                                         # else: Descrittore sconosciuto, ignora
                                     except ValueError:
                                         # print(f"Attenzione: Impossibile convertire descrittore srcset '{descriptor}' in numero per {url}.") # DEBUG
                                         pass # Ignora descrittori non validi

                                 # Scegli l'URL con il descrittore maggiore
                                 if descriptor_value > max_descriptor_value:
                                     max_descriptor_value = descriptor_value
                                     best_url = url

                # 2. Se non abbiamo trovato un URL valido da srcset nei <source>, prova l'<img> tag
                if not best_url:
                     img_tag = picture_tag.select_one(PRODUCT_IMAGE_SELECTOR_IMG_TAG)
                     if img_tag:
                         # Prova srcset dell'img tag
                         srcset_value_img = img_tag.get('srcset')
                         if srcset_value_img:
                             sources_img = srcset_value_img.split(',')
                             for source_img in sources_img:
                                 parts_img = source_img.strip().split()
                                 if len(parts_img) >= 1:
                                     url_img = parts_img[0]
                                     descriptor_value_img = 0
                                     if len(parts_img) > 1:
                                         descriptor_img = parts_img[1]
                                         try:
                                             if descriptor_img.endswith('w'):
                                                 descriptor_value_img = int(descriptor_img[:-1])
                                             elif descriptor_img.endswith('x'):
                                                 descriptor_value_img = int(float(descriptor_img[:-1]) * 1000)
                                         except ValueError:
                                             pass

                                     if descriptor_value_img > max_descriptor_value:
                                          max_descriptor_value = descriptor_value_img
                                          best_url = url_img

                         # Se ancora nessun URL valido, prova src dell'img tag
                         if not best_url and img_tag.has_attr('src'):
                             src_url = img_tag['src']
                             if src_url and not src_url.startswith('data:'): # Ignora placeholder
                                 best_url = src_url


                # Assegna l'URL immagine trovato
                if best_url:
                    image_url = best_url


            # Assicurati che l'URL immagine finale non sia un placeholder data:image e sia completo
            if image_url and not image_url.startswith('data:image'):
                 # Gli URL delle immagini sembrano già assoluti, ma aggiungiamo un controllo base
                 if image_url.startswith('//'):
                     product_data["image_url"] = "https:" + image_url
                 # else: Assumi sia già assoluto
                 else:
                     product_data["image_url"] = image_url # Già assoluto
            else:
                product_data["image_url"] = "N/A" # Assicurati che sia N/A se è un placeholder o None


            # Aggiungi i dati estratti alla lista dei prodotti di questa pagina
            # Aggiungiamo solo se abbiamo trovato almeno il nome
            if product_data.get("name") != "N/A":
                products_on_page.append(product_data)
            # else: Saltato prodotto senza nome, non stampare per non intasare l'output


        except Exception as e:
            print(f"Errore durante l'elaborazione del contenitore prodotto {i+1} su {url}: {e}")
            continue # Continua con il prossimo prodotto anche in caso di errore su uno

    return products_on_page


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
        # Visto che scrapiamo URL multipli e vogliamo tutto in un file, usiamo 'w'
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

    # Itera su ogni URL nella lista FISCHER_URLS
    for url in FISCHER_URLS:
        print(f"\n--- Scraping URL: {url} ---")
        products_from_current_page = scrape_fischer_page(url)
        all_scraped_products.extend(products_from_current_page) # Aggiunge i prodotti trovati alla lista totale
        time.sleep(2) # Breve pausa tra le richieste a URL diversi


    # Salva tutti i dati raccolti da tutti gli URL in un unico file CSV
    print(f"\nCompletato lo scraping di {len(FISCHER_URLS)} URL.")
    print(f"Totale prodotti raccolti: {len(all_scraped_products)}")
    save_to_csv(all_scraped_products, OUTPUT_CSV_FILE)
