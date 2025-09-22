#!/usr/bin/env python3
"""
Script pour convertir un CSV existant avec images en CSV avec images base64
Usage: python convert_existing_csv.py <dossier_scraping>
"""

import sys
import os
from pathlib import Path
from image_converter import convert_csv_images

def main():
    if len(sys.argv) != 2:
        print("Usage: python convert_existing_csv.py <dossier_scraping>")
        print("Exemple: python convert_existing_csv.py downloads/adfrontiere.com_1758539331")
        sys.exit(1)
    
    scrape_folder = Path(sys.argv[1])
    
    if not scrape_folder.exists():
        print(f"Dossier non trouvé: {scrape_folder}")
        sys.exit(1)
    
    csv_path = scrape_folder / 'products.csv'
    
    if not csv_path.exists():
        print(f"Fichier products.csv non trouvé dans: {scrape_folder}")
        sys.exit(1)
    
    print(f"Conversion du CSV: {csv_path}")
    output_path = convert_csv_images(str(csv_path))
    
    if output_path:
        print("Conversion terminee!")
        print(f"Fichier cree: {output_path}")
        print("Vous pouvez maintenant importer ce fichier dans WordPress")
    else:
        print("Erreur lors de la conversion")

if __name__ == "__main__":
    main()