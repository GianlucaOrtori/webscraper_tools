import requests
from bs4 import BeautifulSoup
import re
import time
import pandas as pd

def get_product_details_from_page(product_page_url):
    """
    Scrapa il nome completo del prodotto (titolo + sottotitolo),
    la descrizione e l'URL dell'immagine di qualità più elevata
    da una singola pagina del prodotto Bosch Professional.

    Args:
        product_page_url (str): L'URL della pagina del prodotto.

    Returns:
        dict: Un dizionario contenente il nome del prodotto, la descrizione
              e l'URL dell'immagine, oppure None se si verifica un errore.
    """
    try:
        response = requests.get(product_page_url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il recupero della pagina {product_page_url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    product_data = {}

    # --- Estrai il nome completo del prodotto (titolo + sottotitolo) ---
    product_name_full = []
    product_title_tag = soup.find('h1', class_='product-detail-stage__title')
    if product_title_tag:
        product_name_full.append(product_title_tag.get_text(strip=True))

    product_subtitle_tag = soup.find('p', class_='product-detail-stage__subtitle')
    if product_subtitle_tag:
        product_name_full.append(product_subtitle_tag.get_text(strip=True))
    
    if product_name_full:
        product_data['nome_prodotto'] = " ".join(product_name_full)
    else:
        product_data['nome_prodotto'] = 'Nome prodotto non trovato'


    # Estrai la descrizione
    description_list = soup.find('ul', class_='product-detail-stage__list')
    if description_list:
        description_items = [li.get_text(strip=True) for li in description_list.find_all('li')]
        product_data['descrizione'] = "\n".join(description_items)
    else:
        product_data['descrizione'] = 'Descrizione non trovata'

    # --- Estrai l'URL dell'immagine di qualità più elevata ---
    high_res_image_url = 'URL Immagine non trovato'

    product_stage_slide_div = soup.find('div', class_='product-detail-stage__slide')

    if product_stage_slide_div:
        picture_tag = product_stage_slide_div.find('picture')

        if picture_tag:
            source_tags = picture_tag.find_all('source')

            best_image_url = None
            max_width = 0

            for source in source_tags:
                if 'srcset' in source.attrs:
                    srcset_value = source['srcset']
                    urls_and_widths = [part.strip().split(' ') for part in srcset_value.split(',')]

                    for item in urls_and_widths:
                        if len(item) == 2:
                            url_candidate = item[0]
                            width_str = item[1]
                            width_match = re.match(r'(\d+)w', width_str)
                            if width_match:
                                width = int(width_match.group(1))
                                if width > max_width:
                                    max_width = width
                                    best_image_url = url_candidate
            
            if best_image_url:
                high_res_image_url = best_image_url
            else:
                img_tag = picture_tag.find('img')
                if img_tag and 'src' in img_tag.attrs:
                    high_res_image_url = img_tag['src']
                elif img_tag and 'data-src' in img_tag.attrs:
                    high_res_image_url = img_tag['data-src']

    product_data['url_immagine'] = high_res_image_url
    product_data['marca'] = 'Bosch' # Aggiungiamo la marca

    return product_data



def scrape_category_pages(start_category_url):
    """
    Scrapa tutti i link ai prodotti da una pagina di categoria e poi visita
    ciascun link per estrarre i dettagli, navigando tra tutte le pagine.

    Args:
        start_category_url (str): L'URL della pagina di categoria iniziale.

    Returns:
        list: Una lista di dizionari, dove ogni dizionario contiene i dettagli
              di un prodotto.
    """
    all_products_data = []
    current_page_url = start_category_url
    page_count = 0

    while current_page_url: # Continua finché c'è un URL per la pagina successiva
        page_count += 1
        print(f"\n--- Recupero pagina di categoria {page_count}: {current_page_url} ---")
        try:
            response = requests.get(current_page_url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Errore durante il recupero della pagina di categoria {current_page_url}: {e}")
            break # Esci dal loop in caso di errore di rete

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Scraping dei prodotti dalla pagina attuale
        product_tiles = soup.find_all('div', class_='category-grid-tile', attrs={'data-sku': True})

        print(f"Trovati {len(product_tiles)} prodotti nella pagina {current_page_url}.")

        if not product_tiles:
            print("Nessun prodotto trovato in questa pagina. Controlla il selettore o la struttura della pagina.")

        for tile in product_tiles:
            product_link_tag = tile.find('a', class_='category-grid-tile__link-wrapper')
            
            if product_link_tag and 'href' in product_link_tag.attrs:
                product_url = product_link_tag['href']
                print(f"  Scraping del prodotto: {product_url}")
                
                product_details = get_product_details_from_page(product_url)
                if product_details:
                    all_products_data.append(product_details)
                
                time.sleep(0.5) # Piccolo ritardo tra le richieste ai dettagli dei prodotti

        # --- Trova il link alla pagina successiva ---
        next_page_button = soup.find('button', 
                                     class_='m-ghostblock__nav-item arrow', 
                                     attrs={'aria-label': 'avanti'})
        
        if next_page_button and 'data-href' in next_page_button.attrs:
            current_page_url = next_page_button['data-href']
            print(f"Trovata pagina successiva: {current_page_url}")
            time.sleep(1) # Ritardo più lungo tra il caricamento delle pagine di categoria
        else:
            print("Nessun bottone 'avanti' trovato. Fine dello scraping delle pagine.")
            current_page_url = None # Ferma il loop quando non ci sono più pagine

    return all_products_data



# --- Esecuzione dello scraping ---
# Lista di URL delle categorie da scrapare
category_urls = [
    "https://www.bosch-professional.com/it/it/foratura-taglio-e-levigatura-al-diamante-2848783-ocs-ac/",
    "https://www.bosch-professional.com/it/it/frese-e-lame-per-pialletti-2865191-ocs-ac/",
    "https://www.bosch-professional.com/it/it/scalpelli-2865192-ocs-ac/",
    "https://www.bosch-professional.com/it/it/accessori-per-utensili-multifunzione-2865193-ocs-ac/",
    "https://www.bosch-professional.com/it/it/lame-per-seghe-e-seghe-a-tazza-2865194-ocs-ac/",
    "https://www.bosch-professional.com/it/it/dischi-per-levigatura-nastri-abrasivi-e-carte-abrasive-2844667-ocs-ac/",
    "https://www.bosch-professional.com/it/it/bit-avvitamento-bussole-per-viti-e-bussole-2865195-ocs-ac/",
    "https://www.bosch-professional.com/it/it/mole-da-taglio-mole-da-sbavo-e-spazzole-con-filo-metallico-2865196-ocs-ac/",
    "https://www.bosch-professional.com/it/it/set-2844675-ocs-ac/",
    "https://www.bosch-professional.com/it/it/accessori-di-sistema-2844668-ocs-ac/",

]

all_scraped_products = []

for url in category_urls:
    print(f"\n***** INIZIO SCRAPING CATEGORIA: {url} *****")
    products_from_category = scrape_category_pages(url)
    all_scraped_products.extend(products_from_category)
    print(f"***** FINE SCRAPING CATEGORIA: {url} *****")
    time.sleep(2) # Breve pausa tra una categoria e l'altra

if all_scraped_products:
    print("\n--- Scraping completato per tutte le categorie. Salvataggio in CSV... ---")
    
    # Crea un DataFrame Pandas dai dati scrapati
    df = pd.DataFrame(all_scraped_products)
    
    # Ordina le colonne come richiesto
    output_columns = ['nome_prodotto', 'marca', 'descrizione', 'url_immagine']
    df = df[output_columns]
    
    # Salva il DataFrame in un file CSV
    csv_filename = 'bosch_accessori_products.csv' # Cambiato nome del file per includere tutti i prodotti
    df.to_csv(csv_filename, index=False, encoding='utf-8')
    
    print(f"Dati salvati con successo in '{csv_filename}'")
else:
    print("Nessun dato di prodotto è stato scrapato da nessuna categoria o si è verificato un errore.")