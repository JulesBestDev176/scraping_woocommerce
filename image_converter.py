import csv
import base64
import os
import sys
from pathlib import Path

def image_to_base64(image_path):
    """Convertit une image en base64"""
    try:
        with open(image_path, 'rb') as image_file:
            encoded = base64.b64encode(image_file.read()).decode('utf-8')
            # Déterminer le type MIME
            ext = Path(image_path).suffix.lower()
            mime_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg', 
                '.png': 'image/png',
                '.webp': 'image/webp',
                '.gif': 'image/gif'
            }
            mime_type = mime_types.get(ext, 'image/jpeg')
            return f"data:{mime_type};base64,{encoded}"
    except Exception as e:
        print(f"Erreur conversion {image_path}: {e}")
        return ""

def convert_csv_images(csv_path):
    """Convertit les images du CSV en base64"""
    csv_dir = Path(csv_path).parent
    images_dir = csv_dir / 'images'
    
    if not images_dir.exists():
        print("Dossier images non trouvé")
        return
    
    # Lire le CSV
    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            # Convertir image principale
            if row['main_image']:
                img_path = images_dir / row['main_image']
                if img_path.exists():
                    row['main_image'] = image_to_base64(img_path)
            
            # Convertir galerie
            if row['gallery_images']:
                gallery_files = row['gallery_images'].split(';')
                gallery_base64 = []
                for img_file in gallery_files:
                    if img_file.strip():
                        img_path = images_dir / img_file.strip()
                        if img_path.exists():
                            gallery_base64.append(image_to_base64(img_path))
                row['gallery_images'] = ';'.join(gallery_base64)
            
            rows.append(row)
    
    # Sauvegarder le nouveau CSV
    output_path = csv_dir / 'products_base64.csv'
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"CSV avec images base64 créé: {output_path}")
    return output_path

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python image_converter.py <chemin_vers_products.csv>")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"Fichier non trouvé: {csv_path}")
        sys.exit(1)
    
    convert_csv_images(csv_path)