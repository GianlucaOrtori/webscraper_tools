import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from datetime import datetime
import os
import random

def get_page_content(url, max_retries=3):
    """Scarica e restituisce il contenuto di una pagina web con gestione di errori e retry."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.firstcorporation.it/'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 429:  # Too Many Requests
                wait_time = (2 ** attempt) + random.random()  # Exponential backoff with jitter
                print(f"Troppi request, aspetto {wait_time:.2f} secondi prima di riprovare...")
                time.sleep(wait_time)
            else:
                print(f"Errore nel recupero della pagina {url}: {response.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Attesa prima di riprovare
        except requests.exceptions.RequestException as e:
            print(f"Errore di connessione per {url}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Attesa prima di riprovare
    
    print(f"Impossibile recuperare la pagina {url} dopo {max_retries} tentativi.")
    return None

def extract_product_links(page_content):
    """Estrae i link ai prodotti dalla pagina della categoria."""
    soup = BeautifulSoup(page_content, 'html.parser')
    
    product_links = []
    products = soup.select('div.col-md-4.mb-0 div.feature-wrap')
    
    for product in products:
        link_elem = product.select_one('a.site-button.blue-btn.has_arrow')
        if link_elem and 'href' in link_elem.attrs:
            product_links.append(link_elem['href'])
    
    # Controlla se c'è una paginazione e in caso affermativo ottiene anche i link delle pagine successive
    pagination = soup.select_one('nav.woocommerce-pagination ul.page-numbers')
    next_page = None
    if pagination:
        next_page_link = pagination.select_one('a.next.page-numbers')
        if next_page_link and 'href' in next_page_link.attrs:
            next_page = next_page_link['href']
    
    return product_links, next_page

def extract_product_info(page_content):
    """Estrae le informazioni del prodotto dalla pagina del prodotto."""
    soup = BeautifulSoup(page_content, 'html.parser')
    
    # Estrazione del nome del prodotto
    nome_prodotto_elem = soup.select_one('div.scheda_dat_title h2')
    nome_prodotto = nome_prodotto_elem.get_text(strip=True) if nome_prodotto_elem else "N/A"
    
    # Estrazione della descrizione
    descrizione_elem = soup.select_one('div.scheda_text_block')
    descrizione = ""
    if descrizione_elem:
        paragraphs = descrizione_elem.find_all('p')
        descrizione = " ".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
    
    # Estrazione del materiale
    materiale_elem = soup.select_one('div.scheda_category_block.scheda_filter_content span.cat_txt')
    materiale = materiale_elem.get_text(strip=True) if materiale_elem else "N/A"
    
    # Estrazione dei colori disponibili
    colori = []
    colori_elements = soup.select('ul.variable-items-wrapper.button-variable-items-wrapper li.variable-item')
    for colore_elem in colori_elements:
        data_title = colore_elem.get('data-title')
        if data_title:
            colori.append(data_title)
    
    # Estrazione dell'immagine - metodo ulteriormente migliorato
    immagine = "N/A"
    
    # Metodo 1: Immagine semplice in div.col-md-6
    simple_image = soup.select_one('div.col-md-6 > img')
    if simple_image and 'src' in simple_image.attrs:
        immagine = simple_image['src']
    
    # Metodo 2: Carosello principale
    if immagine == "N/A":
        slider_main = soup.select_one('div.slider.slider-single div.slick-slide.slick-current.slick-active img')
        if slider_main and 'src' in slider_main.attrs:
            immagine = slider_main['src']
    
    # Metodo 3: Miniature
    if immagine == "N/A":
        slider_thumb = soup.select_one('div.slider.slider-nav div.slick-slide.slick-current.slick-active img')
        if slider_thumb and 'src' in slider_thumb.attrs:
            immagine = slider_thumb['src']
    
    # Metodo 4: Qualsiasi immagine nel carosello
    if immagine == "N/A":
        any_slider_img = soup.select_one('div.product_owl_slider img')
        if any_slider_img and 'src' in any_slider_img.attrs:
            immagine = any_slider_img['src']
    
    # Metodo 5: Qualsiasi immagine correlata al prodotto
    if immagine == "N/A":
        any_product_img = soup.select_one('img[alt="ProductImage"]')
        if any_product_img and 'src' in any_product_img.attrs:
            immagine = any_product_img['src']
    
    # Combinazione descrizione e materiale
    descrizione_completa = descrizione
    if materiale != "N/A":
        descrizione_completa += f" Materiale: {materiale}."
    
    colori_str = ", ".join(colori) if colori else "N/A"
    
    return {
        'nome': nome_prodotto,
        'descrizione': descrizione_completa,
        'colori': colori_str,
        'immagine': immagine,
        'marca': 'First Corporation'
    }

def scrape_products(start_url):
    """Estrae le informazioni dai prodotti a partire dall'URL iniziale."""
    products_info = []
    urls_to_visit = [start_url]
    visited_urls = set()
    product_count = 0
    
    while urls_to_visit:
        current_url = urls_to_visit.pop(0)
        
        if current_url in visited_urls:
            continue
        
        visited_urls.add(current_url)
        
        # Ottieni il contenuto della pagina
        print(f"Elaborazione della pagina: {current_url}")
        page_content = get_page_content(current_url)
        if not page_content:
            continue
        
        # Se l'URL è quello di partenza o una pagina di categoria
        if "/product-category/" in current_url or "/page/" in current_url:
            product_links, next_page = extract_product_links(page_content)
            
            # Aggiungi i link dei prodotti alla lista da visitare
            for link in product_links:
                if link not in visited_urls and link not in urls_to_visit:
                    urls_to_visit.append(link)
            
            # Aggiungi la pagina successiva se esiste
            if next_page and next_page not in visited_urls and next_page not in urls_to_visit:
                urls_to_visit.append(next_page)
        
        # Se l'URL è quello di un prodotto
        elif "/product/" in current_url:
            try:
                product_info = extract_product_info(page_content)
                products_info.append(product_info)
                product_count += 1
                
                # Mostra progresso
                if product_count % 5 == 0:
                    print(f"  Prodotti estratti finora: {product_count}")
                
                # Attesa per non sovraccaricare il server
                time.sleep(0.5)
            except Exception as e:
                print(f"Errore nell'estrazione del prodotto {current_url}: {str(e)}")
    
    return products_info

def save_to_csv(products_info, filename="first_corporation_products.csv"):
    """Salva le informazioni dei prodotti in un file CSV."""
    if not products_info:
        print("Nessun prodotto trovato.")
        return
    
    # Aggiungi timestamp al nome del file per evitare sovrascritture
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"first_corporation_products_{timestamp}.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['nome', 'descrizione', 'colori', 'immagine', 'marca']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for product in products_info:
            writer.writerow(product)
    
    print(f"Informazioni salvate in {filename}")
    
    # Salva anche una copia di backup in caso di interruzioni
    backup_filename = f"first_corporation_backup_{timestamp}.csv"
    with open(backup_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['nome', 'descrizione', 'colori', 'immagine', 'marca']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for product in products_info:
            writer.writerow(product)
            
    print(f"Backup salvato in {backup_filename}")

def main():
    # Lista di URL di categoria da scrapare
    start_urls = [
        "https://www.firstcorporation.it/product-category/griglie-di-aerazione/",
        "https://www.firstcorporation.it/product-category/drenaggio-suolo/",
        "https://www.firstcorporation.it/product-category/canali-di-gronda/",
        "https://www.firstcorporation.it/product-category/idrosanitaria/",
        "https://www.firstcorporation.it/product-category/edilizia/",
        "https://www.firstcorporation.it/product-category/sistemi-di-condizionamento/",
        "https://www.firstcorporation.it/product-category/aerazione-canalizzata/",
        "https://www.firstcorporation.it/product-category/articoli-complementari/",
        "https://www.firstcorporation.it/product-category/prodotti-tecnici/",
        "https://www.firstcorporation.it/product-category/lastre-di-copertura-termoplastiche/"
    ]
    
    all_products_info = []
    
    # Crea directory per i risultati
    results_dir = "first_corporation_results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    # Per ogni URL di categoria
    for url in start_urls:
        # Estrai il nome della categoria dall'URL
        category_name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
        print(f"\nProcessando categoria: {category_name}")
        
        # Scrapa i prodotti di questa categoria
        products_info = scrape_products(url)
        print(f"Estratti {len(products_info)} prodotti dalla categoria {category_name}.")
        
        # Salva i prodotti di questa categoria in un file separato
        if products_info:
            category_file = os.path.join(results_dir, f"{category_name}.csv")
            with open(category_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['nome', 'descrizione', 'colori', 'immagine', 'marca']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for product in products_info:
                    writer.writerow(product)
            print(f"Salvati i prodotti della categoria {category_name} in {category_file}")
        
        # Aggiungi i prodotti di questa categoria all'elenco completo
        all_products_info.extend(products_info)
        
        # Salva progressivamente tutti i prodotti per sicurezza
        save_to_csv(all_products_info, os.path.join(results_dir, "all_products_progress.csv"))
        
        # Attendi un po' prima di passare alla categoria successiva
        print(f"Attesa di 3 secondi prima di passare alla categoria successiva...")
        time.sleep(3)
    
    # Salva tutti i prodotti in un unico file alla fine
    final_file = os.path.join(results_dir, "first_corporation_all_products.csv")
    with open(final_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['nome', 'descrizione', 'colori', 'immagine', 'marca']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for product in all_products_info:
            writer.writerow(product)
    
    print(f"\nTotale prodotti estratti: {len(all_products_info)}")
    print(f"Tutti i prodotti sono stati salvati in {final_file}")

if __name__ == "__main__":
    main()