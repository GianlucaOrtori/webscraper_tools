import requests
from bs4 import BeautifulSoup
import time
import csv
import os

# Impostazioni iniziali
BASE_URL = "https://products.kerakoll.com"
DEFAULT_LISTING_PAGE_URL = "https://products.kerakoll.com/it-IT/c/preparazione-fondi-di-posa"
OUTPUT_CSV_FILE = "kerakoll_prodotti.csv"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_soup(url):
    try:
        print(f"Fetching URL: {url}")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup
    except requests.exceptions.Timeout:
        print(f"Timeout durante la richiesta a {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Errore durante la richiesta a {url}: {e}")
        return None

def scrape_product_details(product_url):
    return None

def main_scraper(listing_urls):
    all_products_data = []

    if not isinstance(listing_urls, list):
        print("Errore: La funzione main_scraper richiede una lista di URL.")
        return

    for listing_url in listing_urls:
        print(f"\nAvvio scraping da: {listing_url}")
        listing_soup = get_soup(listing_url)
        if not listing_soup:
            print(f"Impossibile recuperare la pagina di elenco: {listing_url}. Salto questa URL.")
            continue

        product_containers = listing_soup.find_all("div", class_="card")
        print(f"Trovati {len(product_containers)} contenitori prodotto ('div.card') su {listing_url}.")

        if not product_containers:
            print(f"Nessun contenitore prodotto trovato su {listing_url}. Controlla il selettore 'div.card'.")
            print("Primi 2000 caratteri dell'HTML della pagina di elenco per debug:")
            print(listing_soup.prettify()[:2000])
            continue

        for i, container in enumerate(product_containers):
            try:
                product_data = {
                    "name": "N/A",
                    "brand": "Kerakoll",
                    "description": "N/A",
                    "price": "N/A",
                    "image_url": "N/A",
                    "product_page_url": "N/A"
                }

                link_tag = container.find("a", class_="card__link")
                if link_tag and link_tag.has_attr('href'):
                    relative_url = link_tag['href']
                    if not relative_url.startswith('http'):
                        product_data["product_page_url"] = BASE_URL + relative_url
                    else:
                        product_data["product_page_url"] = relative_url

                name_tag = container.find("h4", class_="card__title")
                if name_tag:
                    product_data["name"] = name_tag.get_text(strip=True)
                    print(f"Trovato Nome: {product_data['name']}")
                else:
                    print("Nome prodotto (h4.card__title) non trovato nel contenitore.")

                description_tag = None
                name_tag_found = container.find("h4", class_="card__title")
                if name_tag_found:
                    description_tag = name_tag_found.find_next_sibling('div')

                if description_tag:
                    product_data["description"] = description_tag.get_text(separator="\n", strip=True)
                    print(f"Trovata Descrizione: {product_data['description'][:70]}...")
                else:
                    content_div = container.find("div", class_="card__content")
                    if content_div:
                        fallback_desc_tag = content_div.find('div', recursive=False)
                        if not fallback_desc_tag:
                            fallback_desc_tags = content_div.find_all('div')
                            fallback_desc_tag = fallback_desc_tags[-1] if fallback_desc_tags else None
                        if fallback_desc_tag:
                            product_data["description"] = fallback_desc_tag.get_text(separator="\n", strip=True)
                            print(f"Trovata Descrizione (fallback): {product_data['description'][:70]}...")
                        else:
                            print("Descrizione prodotto non trovata nel contenitore (vari tentativi).")
                    else:
                        print("Contenuto card (div.card__content) non trovato.")

                img_url = "N/A"
                figure_tag = container.find("figure", class_="card__img")

                if figure_tag:
                    img_tag = figure_tag.find("img", class_="lazy")
                    if img_tag:
                        srcset_value = img_tag.get('srcset')
                        data_srcset_value = img_tag.get('data-srcset')
                        source_set_to_parse = srcset_value if srcset_value else data_srcset_value

                        if source_set_to_parse:
                            sources = source_set_to_parse.split(',')
                            best_url = None
                            max_width = 0

                            for source in sources:
                                parts = source.strip().split()
                                if len(parts) == 2:
                                    url = parts[0]
                                    width_str = parts[1].replace('w', '')
                                    try:
                                        width = int(width_str)
                                        if width > max_width:
                                            max_width = width
                                            best_url = url
                                    except ValueError:
                                        print(f"Attenzione: Impossibile convertire la larghezza '{width_str}' in intero per {product_data['name']}.")
                                else:
                                    print(f"Attenzione: Formato srcset inatteso: '{source.strip()}' per {product_data['name']}.")

                            if best_url:
                                if best_url.startswith('//'):
                                    img_url = "https:" + best_url
                                elif best_url.startswith('/'):
                                    img_url = BASE_URL + best_url
                                elif not best_url.startswith('http'):
                                    img_url = BASE_URL + "/" + best_url.lstrip("/")
                                else:
                                    img_url = best_url
                            else:
                                print("Source set trovato ma impossibile estrarre URL valido.")
                        else:
                            image_src = img_tag.get('data-src') or img_tag.get('src')
                            if image_src:
                                if image_src.startswith('//'):
                                    img_url = "https:" + image_src
                                elif image_src.startswith('/'):
                                    img_url = BASE_URL + image_src
                                elif not image_src.startswith('http'):
                                    img_url = BASE_URL + "/" + image_src.lstrip("/")
                                else:
                                    img_url = image_src
                            else:
                                print("Tag immagine trovato ma senza attributi 'srcset', 'data-srcset', 'data-src' o 'src'.")
                    else:
                        print("Tag immagine (img.lazy) non trovato dentro figure.card__img.")
                else:
                    print("Figure immagine (figure.card__img) non trovata nel contenitore.")

                product_data["image_url"] = img_url
                all_products_data.append(product_data)
                time.sleep(1.5)

            except Exception as e:
                print(f"Errore durante l'elaborazione del contenitore prodotto {i+1}: {e}")
                continue

    if all_products_data:
        print(f"\nScraping completato. Estratti dati per {len(all_products_data)} prodotti totali.")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_file_path = os.path.join(script_dir, OUTPUT_CSV_FILE)

        try:
            keys = all_products_data[0].keys()
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(all_products_data)
            print(f"Dati salvati in {csv_file_path}")
        except IndexError:
            print("Nessun dato prodotto valido estratto per determinare le intestazioni CSV.")
        except Exception as e:
            print(f"Errore durante il salvataggio del file CSV: {e}")
    else:
        print("Nessun dato prodotto estratto da nessuna delle URLs fornite.")

if __name__ == "__main__":
    urls_to_scrape = [
        DEFAULT_LISTING_PAGE_URL,
        "https://products.kerakoll.com/it-IT/c/impermeabilizzazione",
				"https://products.kerakoll.com/it-IT/c/posa-ceramica-e-pietre-naturali",
        "https://products.kerakoll.com/it-IT/c/posa-parquet-resilienti-e-resine-industriali",
        "https://products.kerakoll.com/it-IT/c/ripristino-e-rinforzo-strutturale-antisismico",
        "https://products.kerakoll.com/it-IT/c/costruzione-e-finitura",
        "https://products.kerakoll.com/it-IT/c/decorazione-pitture-rivestimenti-e-smalti",
        "https://products.kerakoll.com/it-IT/c/isolamento-termico",
        "https://products.kerakoll.com/it-IT/c/sistemi-naturali",
                
    ]
    main_scraper(urls_to_scrape)
