import requests
from bs4 import BeautifulSoup
import csv
import os
import time

# Impostazioni iniziali
# Lista per contenere gli URL delle pagine da scrapare.
# Ho inserito qui tutti i link che hai fornito.
HILTI_URLS = [
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_ROTARY_HAMMERS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_DEMOLITION_HAMMER_BREAKER_SUB_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_DRILL_DRIVERS_SCREW_DRIVERS__7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_IMPACT_DRIVERS_WRENCHES_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_CONCRETE_SAWS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_DIAMOND_CORING_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_DIAMOND_WIRE_WALL_SAWS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_SAWS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_GRINDERS_SANDERS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_DIRECT_FASTENING_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_SPECIALTY_POWER_TOOLS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_PIPE_PRESS_CUTTERS_CRIMPERS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_DISPENSERS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_BATT_CHARGERS_POWER_STATIONS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_JOBSITE_ESSENTIALS_7125",
    "https://www.hilti.it/c/CLS_POWER_TOOLS_7125/CLS_TOOLS_7125",
    "https://www.hilti.it/c/CLS_DUST_WATER_MANAGEMENT/CLS_CONSTRUCTION_VACUUMS_DUST_EXTRACTORS",
    "https://www.hilti.it/c/CLS_DUST_WATER_MANAGEMENT/CLS_DUST_EXTRACTION_ATTACHMENTS",
    "https://www.hilti.it/c/CLS_DUST_WATER_MANAGEMENT/CLS_ON_BOARD_DUST_REMOVAL_SYS",
    "https://www.hilti.it/c/CLS_DUST_WATER_MANAGEMENT/CLS_WATER_MANAGE_SYS_WATER_TANKS",
    "https://www.hilti.it/c/CLS_DUST_WATER_MANAGEMENT/CLS_DRILL_STAND_MOUNTED_WATER_COLLECTORS",
    "https://www.hilti.it/c/CLS_DUST_WATER_MANAGEMENT/CLS_SELF_ATTACH_WATER_COLLECTORS",
    "https://www.hilti.it/c/CLS_DUST_WATER_MANAGEMENT/CLS_AIR_CLEANERS",
    "https://www.hilti.it/c/CLS_DUST_WATER_MANAGEMENT/CLS_PRESSURE_CLEANERS",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_CONCRETE_MASONRY_DRILL_BITS_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_METAL_N_WOOD_DRILL_BIT_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_CHISELS_ROD_DRIVERS_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_DIAMOND_CORE_BIT_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_DIAMOND_BLADES_CUP_WHEELS",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_DIAMOND_SAW_BLADES_WIRES_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_SAW_BLADES_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_ABRASIVES_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_BITS_SOCKETS_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_INSERTS_PRESSING_CC_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_KNOCKOUT_DIES_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_MULTI_TOOL_INSERTS_7126",
    "https://www.hilti.it/c/CLS_POWER_TOOL_INSERT_7126/CLS_ACCESSORIES_TOOLS_INSERTS_7126",
    "https://www.hilti.it/c/CLS_MEA_TOOL_INSERT_7127/CLS_LASER_METERS_7127",
    "https://www.hilti.it/c/CLS_MEA_TOOL_INSERT_7127/CLS_MEA_LASER_LAYOUT_TOOLS_7127",
    "https://www.hilti.it/c/CLS_MEA_TOOL_INSERT_7127/CLS_MEA_DIGITAL_LAYOUT_TOOLS_7127",
    "https://www.hilti.it/c/CLS_MEA_TOOL_INSERT_7127/CLS_CONCRETE_SCANNERS_SENSORS_7127",
    "https://www.hilti.it/c/CLS_MEA_TOOL_INSERT_7127/CLS_TABLETS_CONTROLLERS_7127",
    "https://www.hilti.it/c/CLS_MEA_TOOL_INSERT_7127/CLS_POWER_SUPPLIES_7127",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_MECHANICAL_ANCHORS_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_CHEMICAL_ANCHORS_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_ANCHOR_RODS_ELEMENTS_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_TOOLS_FOR_FASTENERS_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_CASTIN_ANCHOR_CHANNELS_2_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_BOLTS_WASHERS_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_SCREWS_2_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_NAILS_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_STUDS_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_FASTENING_ELEMENTS_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_ACCESSORIES_FOR_TOOLS_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_FASTENERS_ACCESSORIES_7135",
    "https://www.hilti.it/c/CLS_FASTENER_7135/CLS_INSERTS_7135",
    "https://www.hilti.it/c/CLS_FIRESTOP_PROTECTION_7131/CLS_FIRESTOP_DEVICES_SLEEVES_7131",
    "https://www.hilti.it/c/CLS_FIRESTOP_PROTECTION_7131/CLS_CABLE_TRANSIT_SYSTEMS_7131",
    "https://www.hilti.it/c/CLS_FIRESTOP_PROTECTION_7131/CLS_FIRESTOP_BLOCKS_PLUGS_7131",
    "https://www.hilti.it/c/CLS_FIRESTOP_PROTECTION_7131/CLS_FIRESTOP_BOARDS_7131",
    "https://www.hilti.it/c/CLS_FIRESTOP_PROTECTION_7131/CLS_FIRESTOP_COLLARS_WRAPS_BANDAGES_7131",
    "https://www.hilti.it/c/CLS_FIRESTOP_PROTECTION_7131/CLS_PREFABRICATED_JOINT_7131",
    "https://www.hilti.it/c/CLS_FIRESTOP_PROTECTION_7131/CLS_FIRESTOP_PUTTIES_7131",
    "https://www.hilti.it/c/CLS_FIRESTOP_PROTECTION_7131/CLS_FIRESTOP_SEALANTS_SPRAY_7131",
    "https://www.hilti.it/c/CLS_FIRESTOP_PROTECTION_7131/CLS_ACCESSORIES_FIRESTOP_7131",
    "https://www.hilti.it/c/CLS_MODULAR_SUPPORT_SYSTEM/CLS_MODULAR_SUPPORT_PRO",
    "https://www.hilti.it/c/CLS_MODULAR_SUPPORT_SYSTEM/CLS_SYS_CONNECTORS_INT",
    "https://www.hilti.it/c/CLS_MODULAR_SUPPORT_SYSTEM/CLS_BRACKETS_MSS",
    "https://www.hilti.it/c/CLS_MODULAR_SUPPORT_SYSTEM/CLS_PIPE_SUPPORTS",
    "https://www.hilti.it/c/CLS_MODULAR_SUPPORT_SYSTEM/CLS_STD_FIX_SUPPORT_SYS",
    "https://www.hilti.it/c/CLS_MODULAR_SUPPORT_SYSTEM/CLS_FIXED_POINT_SLIDERS",
    "https://www.hilti.it/c/CLS_MODULAR_SUPPORT_SYSTEM/CLS_WIRE_SUSPENSION_SYS",
    "https://www.hilti.it/c/CLS_MODULAR_SUPPORT_SYSTEM/CLS_WIRE_SUSPENSION_SYS", # Questo URL è duplicato, ma lo script lo processerà due volte se presente
    "https://www.hilti.it/c/CLS_FACADE_MOUNTING_SYSTEMS/CLS_PROFILES",
    "https://www.hilti.it/c/CLS_FACADE_MOUNTING_SYSTEMS/CLS_ACCESSORIES6966",
    "https://www.hilti.it/c/CLS_CONSTRCUT_CHEM_7132/CLS_FOAMS_7132",
    "https://www.hilti.it/c/CLS_CONSTRCUT_CHEM_7132/CLS_FOAM_GUNS_7133",
    "https://www.hilti.it/c/CLS_CONSTRCUT_CHEM_7132/CLS_ACC_FOR_CONSTRUCTION_CHEMICALS_7133/CLS_DISPENSING_ACCESSORIES_7133",
    "https://www.hilti.it/c/CLS_HEALTH_SAFETY/CLS_CONSTRUCTION_EXOSKELETONS",
    "https://www.hilti.it/c/CLS_HEALTH_SAFETY/CLS_SAFETY_GEAR",
    "https://www.hilti.it/c/CLS_HEALTH_SAFETY/CLS_ACC_EXOSKELETONS",
    "https://www.hilti.it/c/CLS_TOOL_STORAGE_TRANSPORT/CLS_TOOL_CASE",
    "https://www.hilti.it/c/CLS_TOOL_STORAGE_TRANSPORT/CLS_ORGANISERS_CONSUMABLE",
    "https://www.hilti.it/c/CLS_TOOL_STORAGE_TRANSPORT/CLS_SOFTBAGS_BACKPACKS",
    "https://www.hilti.it/c/CLS_TOOL_STORAGE_TRANSPORT/CLS_ROLLING_TOOL_STORAGE"
]
OUTPUT_CSV_FILE = "hilti_prodotti.csv"

# Intestazioni per simulare una richiesta da browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Selettori CSS per gli elementi sulla scheda prodotto Hilti ---
# Basati sull'HTML prototipo che hai fornito

# Selettore per ogni singolo contenitore prodotto (la card completa)
# Usiamo shrd-uic-card che sembra racchiudere la scheda prodotto
PRODUCT_CONTAINER_SELECTOR = "shrd-uic-card"

# Selettore per il link e il titolo del prodotto
# Il link (<a>) è dentro un h3 con classe heading-sm
PRODUCT_TITLE_LINK_SELECTOR = "h3.heading-sm a"

# Selettore per la descrizione del prodotto
# È un tag <dd> con classe product-description-definition
PRODUCT_DESCRIPTION_SELECTOR = "dd.product-description-definition"

# Selettore per il tag immagine del prodotto
# È un tag <img> dentro shrd-uic-image
PRODUCT_IMAGE_SELECTOR = "shrd-uic-image img"


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
        return [] # Restituisce una lista vuota in caso di timeout per non bloccare lo script
    except requests.exceptions.RequestException as e:
        print(f"Errore durante la richiesta a {url}: {e}")
        return [] # Restituisce una lista vuota in caso di errore di richiesta


def scrape_hilti_page(url):
    """
    Scarica una singola pagina di elenco prodotti Hilti e estrae i dati
    di nome, descrizione e immagine per ogni prodotto.
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
                "brand": "Hilti", # Marca fissa
                "description": "N/A",
                "price": "N/A", # Non sembra esserci un prezzo visibile nella card
                "image_url": "N/A",
                "product_page_url": "N/A"
            }

            # Estrai il Nome del prodotto e l'URL della pagina di dettaglio
            title_link_tag = container.select_one(PRODUCT_TITLE_LINK_SELECTOR)
            if title_link_tag:
                product_data["name"] = title_link_tag.get_text(strip=True)
                product_data["product_page_url"] = title_link_tag.get('href', 'N/A')
                # Gli URL Hilti sembrano relativi, costruiamo l'URL completo se necessario
                # Usiamo l'URL base corretto per Hilti
                if product_data["product_page_url"] != 'N/A' and product_data["product_page_url"].startswith('/'):
                     product_data["product_page_url"] = "https://www.hilti.it" + product_data["product_page_url"]

                # print(f"Trovato Nome: {product_data['name']}, URL: {product_data['product_page_url']}") # Messo a commento
            else:
                # Questo caso è gestito dal filtro alla fine del loop
                pass


            # Estrai la Descrizione del prodotto
            description_tag = container.select_one(PRODUCT_DESCRIPTION_SELECTOR)
            if description_tag:
                product_data["description"] = description_tag.get_text(strip=True)
                # print(f"Trovata Descrizione: {product_data['description'][:50]}...") # Messo a commento
            else:
                 # La descrizione potrebbe non essere sempre presente, non è un errore critico
                 # print(f"Descrizione prodotto ({PRODUCT_DESCRIPTION_SELECTOR}) non trovata nel contenitore su {url}.")
                 pass


            # Estrai l'URL dell'immagine
            img_tag = container.select_one(PRODUCT_IMAGE_SELECTOR)
            if img_tag and img_tag.has_attr('src'):
                image_src = img_tag['src']
                # Gli URL delle immagini sembrano già assoluti
                if image_src and not image_src.startswith('data:image'): # Ignora placeholder data:image
                    product_data["image_url"] = image_src
                    # print(f"Trovata Immagine: {product_data['image_url']}") # Messo a commento
                else:
                    # print(f"Tag immagine trovato ma l'URL è un placeholder data:image o vuoto su {url}.")
                    pass # image_url rimane N/A
            else:
                # print(f"Tag immagine ({PRODUCT_IMAGE_SELECTOR}) non trovato o senza src nel contenitore su {url}.")
                pass # image_url rimane N/A


            # Aggiungi i dati estratti alla lista dei prodotti di questa pagina
            # Aggiungiamo solo se abbiamo trovato almeno il nome
            if product_data.get("name") != "N/A":
                products_on_page.append(product_data)
            else:
                # print(f"Saltato prodotto senza nome nel contenitore {i+1} su {url}.") # Messo a commento
                pass


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

    # Itera su ogni URL nella lista HILTI_URLS
    for url in HILTI_URLS:
        print(f"\n--- Scraping URL: {url} ---")
        products_from_current_page = scrape_hilti_page(url)
        all_scraped_products.extend(products_from_current_page) # Aggiunge i prodotti trovati alla lista totale
        time.sleep(2) # Breve pausa tra le richieste a URL diversi


    # Salva tutti i dati raccolti da tutti gli URL in un unico file CSV
    print(f"\nCompletato lo scraping di {len(HILTI_URLS)} URL.")
    print(f"Totale prodotti raccolti: {len(all_scraped_products)}")
    save_to_csv(all_scraped_products, OUTPUT_CSV_FILE)
