from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
import requests
from bs4 import BeautifulSoup
import csv
import re
import os
from urllib.parse import urljoin, urlparse
import time
import uuid
import threading
import json
import zipfile
import shutil

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Stockage des jobs en cours
jobs = {}

def save_jobs():
    """Sauvegarde les jobs sur disque"""
    try:
        with open('jobs.json', 'w') as f:
            json.dump(jobs, f)
    except:
        pass

def load_jobs():
    """Charge les jobs depuis le disque"""
    global jobs
    try:
        with open('jobs.json', 'r') as f:
            jobs = json.load(f)
        # Nettoyer les anciens jobs (plus de 24h)
        current_time = time.time()
        jobs_to_remove = []
        for job_id, job_data in jobs.items():
            if current_time - job_data.get('created', current_time) > 86400:  # 24h
                jobs_to_remove.append(job_id)
        for job_id in jobs_to_remove:
            del jobs[job_id]
        if jobs_to_remove:
            save_jobs()
    except:
        jobs = {}

# Charger les jobs au démarrage
load_jobs()

class WooCommerceScraper:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_product_urls(self):
        """Récupère toutes les URLs des produits uniques"""
        product_urls = set()
        
        # Essayer différentes URLs de shop
        shop_patterns = [
            '/shop/',
            '/products/',
            '/boutique/',
            '/store/',
            '/catalog/',
            '/'
        ]
        
        for pattern in shop_patterns:
            page = 1
            found_products = False
            
            while page <= 20:  # Augmenter à 20 pages par pattern
                shop_urls = [
                    f"{self.base_url}{pattern}page/{page}/",
                    f"{self.base_url}{pattern}?page={page}",
                    f"{self.base_url}{pattern}?paged={page}"
                ]
                
                for shop_url in shop_urls:
                    try:
                        response = self.session.get(shop_url, timeout=10)
                        if response.status_code != 200:
                            continue
                            
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Patterns de recherche plus larges
                        product_selectors = [
                            'a[href*="/product/"]',
                            'a[href*="/produit/"]',
                            '.woocommerce-loop-product__link',
                            '.product-item a',
                            '.product a',
                            '[class*="product"] a',
                            'a[class*="product"]',
                            '.wc-block-grid__product a',
                            'h2 a',
                            'h3 a',
                            '.entry-title a',
                            '.post-title a'
                        ]
                        
                        page_products = set()
                        
                        for selector in product_selectors:
                            links = soup.select(selector)
                            for link in links:
                                href = link.get('href')
                                if href:
                                    full_url = urljoin(self.base_url, href)
                                    # Vérifier que c'est bien un produit
                                    if any(x in href.lower() for x in ['/product/', '/produit/', '?add-to-cart=']):
                                        page_products.add(full_url)
                        
                        if page_products:
                            product_urls.update(page_products)
                            found_products = True
                            break
                            
                    except Exception as e:
                        continue
                
                if not found_products and page > 1:
                    break
                    
                page += 1
                time.sleep(0.3)
            
            if product_urls:
                break
        
        return list(product_urls)
    
    def scrape_product(self, product_url, product_index=0, scrape_folder=''):
        """Scrape les données d'un produit"""
        try:
            response = self.session.get(product_url, timeout=10)
            if response.status_code != 200:
                return None
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Nom du produit avec sélecteurs plus larges
            title_selectors = [
                'h1.product_title',
                'h1.entry-title',
                'h1[class*="product"]',
                '.product-title h1',
                '.single-product h1',
                'h1'
            ]
            
            name = ''
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    name = self.extract_text(title_elem)
                    if name:
                        break
            
            if not name:
                name = self.extract_text(soup.find('title'))
            
            # Description courte avec sélecteurs élargis
            short_desc_selectors = [
                '.woocommerce-product-details__short-description',
                '.product-short-description',
                '.short-description',
                '.product-excerpt',
                '.excerpt',
                '.summary .entry-summary',
                'meta[name="description"]'
            ]
            
            short_desc = ''
            for selector in short_desc_selectors:
                if 'meta' in selector:
                    elem = soup.select_one(selector)
                    if elem and elem.get('content'):
                        short_desc = elem['content']
                        break
                else:
                    elem = soup.select_one(selector)
                    if elem:
                        short_desc = self.extract_html(elem)
                        break
            
            # Description longue
            long_desc_elem = soup.find('div', class_=re.compile(r'woocommerce-Tabs-panel--description'))
            if not long_desc_elem:
                long_desc_elem = soup.find('div', id='tab-description')
            long_desc = self.extract_html(long_desc_elem)
            
            # Prix
            price = self.extract_price(soup)
            
            # Catégories
            categories = self.extract_categories(soup)
            
            # Tags/Étiquettes
            tags = self.extract_tags(soup)
            
            # Marque
            brand = self.extract_brand(soup)
            
            # Images
            main_image, gallery_images = self.extract_images(soup, product_url, self.generate_slug(name), product_index, scrape_folder)
            
            return {
                'title': name or '',
                'slug': self.generate_slug(name),
                'sku': '',
                'price': price or '0',
                'regular_price': price or '0',
                'sale_price': '',
                'sale_start_date': '',
                'sale_end_date': '',
                'stock_status': 'instock',
                'manage_stock': 'no',
                'stock_quantity': '',
                'allow_backorders': 'no',
                'sold_individually': 'no',
                'weight': '',
                'length': '',
                'width': '',
                'height': '',
                'tax_status': 'taxable',
                'tax_class': '',
                'status': 'publish',
                'catalog_visibility': 'visible',
                'featured_product': 'no',
                'description': long_desc or '',
                'short_description': short_desc or '',
                'purchase_note': '',
                'virtual_product': 'no',
                'downloadable_product': 'no',
                'downloadable_files': '',
                'download_limit': '',
                'download_expiry': '',
                'categories': categories,
                'tags': tags,
                'attributes': '',
                'default_attributes': '',
                'upsell_products': '',
                'cross_sell_products': '',
                'parent_product_id': '',
                'main_image': main_image or '',
                'gallery_images': gallery_images,
                'variations': '',
                'brands': brand or '',
                'color': '',
                'size': '',
                'material': ''
            }
            
        except Exception as e:
            print(f"Erreur scraping {product_url}: {e}")
            return None
    
    def extract_text(self, element):
        """Extrait le texte d'un élément"""
        if element:
            return element.get_text(strip=True)
        return ''
    
    def extract_html(self, element):
        """Extrait le HTML d'un élément en gardant la structure"""
        if element:
            html = str(element)
            html = html.replace('"', "'")
            return html
        return ''
    
    def extract_price(self, soup):
        """Extrait le prix"""
        price_selectors = [
            '.woocommerce-Price-amount',
            '.price .amount',
            '.price',
            '[class*="price"]'
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                if price_match:
                    return price_match.group()
        return ''
    
    def extract_categories(self, soup):
        """Extrait les catégories spécifiques au produit"""
        categories = []
        
        # Breadcrumb
        breadcrumb = soup.find('nav', class_=re.compile(r'breadcrumb'))
        if breadcrumb:
            links = breadcrumb.find_all('a')
            for link in links[1:-1][-3:]:
                cat = link.get_text(strip=True)
                if cat and cat.lower() not in ['home', 'shop'] and cat not in categories:
                    categories.append(cat)
        
        # Catégories dans les métadonnées du produit
        cat_meta = soup.find('span', class_=re.compile(r'posted_in|category'))
        if cat_meta:
            cat_links = cat_meta.find_all('a')
            for link in cat_links:
                cat = link.get_text(strip=True)
                if cat and cat not in categories:
                    categories.append(cat)
        
        return ', '.join(categories)
    
    def get_site_categories(self):
        """Récupère toutes les catégories du site"""
        categories = []
        
        try:
            cat_urls = [
                f"{self.base_url}/product-category/",
                f"{self.base_url}/shop/"
            ]
            
            for cat_url in cat_urls:
                try:
                    response = self.session.get(cat_url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        cat_links = soup.find_all('a', href=re.compile(r'/product-category/'))
                        
                        for link in cat_links:
                            cat_name = link.get_text(strip=True)
                            cat_href = link.get('href')
                            
                            if cat_name and cat_href:
                                cat_slug = cat_href.split('/product-category/')[-1].rstrip('/')
                                parts = cat_slug.split('/')
                                parent = parts[-2] if len(parts) > 1 else ''
                                
                                category_data = {
                                    'name': cat_name,
                                    'slug': parts[-1],
                                    'parent': parent,
                                    'url': cat_href
                                }
                                
                                if not any(c['slug'] == category_data['slug'] for c in categories):
                                    categories.append(category_data)
                        
                        break
                        
                except:
                    continue
                    
        except Exception as e:
            print(f"Erreur extraction catégories: {e}")
        
        return categories
    
    def extract_tags(self, soup):
        """Extrait les tags"""
        tags = []
        
        # Sélecteurs de tags plus larges
        tag_selectors = [
            'a[href*="/product-tag/"]',
            'a[href*="/tag/"]',
            '.product-tags a',
            '.tags a',
            '[class*="tag"] a',
            'meta[name="keywords"]',
            '.product-categories a',
            '.breadcrumb a'
        ]
        
        for selector in tag_selectors:
            if 'meta' in selector:
                meta_elem = soup.select_one(selector)
                if meta_elem and meta_elem.get('content'):
                    meta_tags = [t.strip() for t in meta_elem['content'].split(',')]
                    for tag in meta_tags:
                        if tag and tag not in tags and len(tag) > 1:
                            tags.append(tag)
            else:
                tag_links = soup.select(selector)
                for link in tag_links:
                    tag = link.get_text(strip=True)
                    if tag and tag not in tags and len(tag) > 1 and tag.lower() not in ['home', 'accueil']:
                        tags.append(tag)
        
        # Si pas de tags, utiliser les catégories comme tags
        if not tags:
            categories = self.extract_categories(soup)
            if categories:
                tags = [cat.strip() for cat in categories.split(',')]
        
        return ', '.join(tags[:5])  # Limiter à 5 tags
    
    def extract_brand(self, soup):
        """Extrait la marque"""
        brand_selectors = [
            '[class*="brand"]',
            '[data-attribute*="brand"]',
            '.woocommerce-product-attributes-item__value',
            '.product-brand',
            '.brand-name',
            '[class*="manufacturer"]',
            'meta[property="product:brand"]',
            'meta[name="author"]',
            '.site-title',
            '.logo img'
        ]
        
        for selector in brand_selectors:
            if 'meta' in selector:
                brand_elem = soup.select_one(selector)
                if brand_elem and brand_elem.get('content'):
                    return brand_elem['content'].strip()
            elif '.logo img' in selector:
                brand_elem = soup.select_one(selector)
                if brand_elem and brand_elem.get('alt'):
                    return brand_elem['alt'].strip()
            else:
                brand_elem = soup.select_one(selector)
                if brand_elem:
                    brand_text = brand_elem.get_text(strip=True)
                    if brand_text and len(brand_text) < 50:
                        brand_text = re.sub(r'^brands?:\s*', '', brand_text, flags=re.IGNORECASE)
                        return brand_text
        
        # Si pas de marque, utiliser le nom du site
        site_name = soup.select_one('title')
        if site_name:
            title_text = site_name.get_text().strip()
            # Extraire le nom du site du titre
            if '|' in title_text:
                return title_text.split('|')[-1].strip()
            elif '-' in title_text:
                return title_text.split('-')[-1].strip()
        
        return ''
    
    def generate_slug(self, name):
        """Génère un slug à partir du nom"""
        if not name:
            return ''
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'\s+', '-', slug)
        slug = slug.strip('-')
        return slug
    
    def download_image(self, image_url, product_slug, image_type='main', product_index=0, scrape_folder=''):
        """Télécharge une image et retourne le chemin local"""
        try:
            response = self.session.get(image_url, timeout=10)
            if response.status_code == 200:
                # Créer le dossier images dans le dossier de scraping
                images_dir = os.path.join(scrape_folder, 'images')
                os.makedirs(images_dir, exist_ok=True)
                
                # Nom du fichier avec index pour éviter les doublons
                ext = image_url.split('.')[-1].split('?')[0]
                if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                    ext = 'jpg'
                
                filename = f"{product_slug}_{product_index}_{image_type}.{ext}"
                filepath = os.path.join(images_dir, filename)
                
                # Sauvegarder l'image
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                return filename
        except:
            pass
        return ''
    
    def extract_images(self, soup, base_url, product_slug, product_index=0, scrape_folder=''):
        """Extrait et télécharge les images"""
        main_image_url = ''
        gallery_image_urls = []
        
        # Sélecteurs d'images spécifiques aux produits
        image_selectors = [
            'img.wp-post-image',
            'img.attachment-shop_single',
            '.woocommerce-product-gallery img',
            '.product-image img',
            '.product-gallery img'
        ]
        
        # Image principale
        for selector in image_selectors:
            main_img = soup.select_one(selector)
            if main_img and main_img.get('src'):
                main_image_url = urljoin(base_url, main_img['src'])
                break
        
        # Galerie
        gallery_selectors = [
            'img.attachment-shop_thumbnail',
            '.woocommerce-product-gallery img',
            '.product-thumbnails img'
        ]
        
        for selector in gallery_selectors:
            gallery_imgs = soup.select(selector)
            for img in gallery_imgs:
                if img.get('src'):
                    img_url = urljoin(base_url, img['src'])
                    if img_url != main_image_url:
                        gallery_image_urls.append(img_url)
        
        # Télécharger les images
        main_image_file = ''
        gallery_image_files = []
        
        if main_image_url:
            main_image_file = self.download_image(main_image_url, product_slug, 'main', product_index, scrape_folder)
        
        for i, gallery_url in enumerate(gallery_image_urls):
            gallery_file = self.download_image(gallery_url, product_slug, f'gallery_{i+1}', product_index, scrape_folder)
            if gallery_file:
                gallery_image_files.append(gallery_file)
        
        return main_image_file, ';'.join(gallery_image_files)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_scrape', methods=['POST'])
def start_scrape():
    data = request.get_json()
    url = data.get('url', '').strip()
    max_products = data.get('maxProducts', '')
    
    if not url:
        return jsonify({'error': 'URL invalide'}), 400
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'progress': 0,
        'status': 'Démarrage...',
        'url': url,
        'filepath': None,
        'created': time.time()
    }
    save_jobs()
    
    # Démarrer le scraping en arrière-plan
    thread = threading.Thread(target=scrape_background, args=(job_id, url, max_products))
    thread.start()
    
    return jsonify({'job_id': job_id})

@app.route('/progress/<job_id>')
def get_progress(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job non trouvé'}), 404
    
    return jsonify({
        'progress': jobs[job_id]['progress'],
        'status': jobs[job_id]['status']
    })

@app.route('/download/<job_id>')
def download_file(job_id):
    if job_id not in jobs:
        return 'Job non trouvé', 404
    
    if not jobs[job_id].get('filepath') or not os.path.exists(jobs[job_id]['filepath']):
        return 'Dossier non trouvé', 404
    
    folder_path = jobs[job_id]['filepath']
    folder_name = os.path.basename(folder_path)
    
    # Créer le fichier ZIP
    zip_filename = f'{folder_name}.zip'
    zip_filepath = os.path.join('downloads', zip_filename)
    
    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)
    
    # Supprimer le job après création du ZIP
    del jobs[job_id]
    
    # Nettoyer tous les jobs terminés avec erreur ou sans fichier
    jobs_to_remove = []
    for jid, job_data in jobs.items():
        if job_data['progress'] == 100 and not job_data.get('filepath'):
            jobs_to_remove.append(jid)
    
    for jid in jobs_to_remove:
        del jobs[jid]
    
    save_jobs()
    
    return send_file(zip_filepath, as_attachment=True, download_name=zip_filename)

def scrape_background(job_id, url, max_products=None):
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = 'https://' + url
        
        jobs[job_id]['status'] = 'Recherche des produits...'
        jobs[job_id]['progress'] = 10
        save_jobs()
        
        scraper = WooCommerceScraper(url)
        product_urls = scraper.get_product_urls()
        
        if not product_urls:
            jobs[job_id]['status'] = 'Aucun produit trouvé'
            return
        
        jobs[job_id]['status'] = f'{len(product_urls)} produits trouvés'
        jobs[job_id]['progress'] = 20
        save_jobs()
        
        # Création du dossier de scraping unique
        domain = urlparse(url).netloc.replace('www.', '')
        timestamp = int(time.time())
        scrape_folder = os.path.join('downloads', f'{domain}_{timestamp}')
        os.makedirs(scrape_folder, exist_ok=True)
        
        products_data = []
        # Utilise la limite utilisateur ou tous les produits
        if max_products and str(max_products).isdigit():
            limit = int(max_products)
        else:
            limit = len(product_urls)
        
        total_products = min(len(product_urls), limit)
        
        # Supprimer les doublons et filtrer les pages non-produits
        seen_products = set()
        unique_products = []
        invalid_titles = ['boutique', 'shop', 'store', 'accueil', 'home', 'contact', 'about', 'panier', 'cart', 'checkout', 'mon-compte', 'account']
        
        for i, product_url in enumerate(product_urls):
            if len(unique_products) >= limit:
                break
                
            product_data = scraper.scrape_product(product_url, i, scrape_folder)
            if product_data:
                product_key = product_data['title'].lower().strip()
                # Filtrer les pages non-produits (moins strict)
                if product_key not in invalid_titles and len(product_key) > 2:
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        unique_products.append(product_data)
            
            # Mise à jour du progrès
            progress = 20 + len(unique_products) / limit * 70
            jobs[job_id]['progress'] = int(progress)
            jobs[job_id]['status'] = f'Trouvé {len(unique_products)}/{limit} produits'
            if i % 5 == 0:  # Sauvegarder tous les 5 produits
                save_jobs()
        
        products_data = unique_products
        
        if not products_data:
            jobs[job_id]['status'] = 'Aucune donnée récupérée'
            return
        
        jobs[job_id]['status'] = 'Génération du CSV...'
        jobs[job_id]['progress'] = 95
        
        # Récupération des catégories du site
        site_categories = scraper.get_site_categories()
        
        # Création des fichiers CSV dans le dossier de scraping
        products_filename = 'products.csv'
        products_filepath = os.path.join(scrape_folder, products_filename)
        
        categories_filename = 'categories.csv'
        categories_filepath = os.path.join(scrape_folder, categories_filename)
        
        # Sauvegarde du CSV des produits
        with open(products_filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['title', 'slug', 'sku', 'price', 'regular_price', 'sale_price', 'sale_start_date', 'sale_end_date', 'stock_status', 'manage_stock', 'stock_quantity', 'allow_backorders', 'sold_individually', 'weight', 'length', 'width', 'height', 'tax_status', 'tax_class', 'status', 'catalog_visibility', 'featured_product', 'description', 'short_description', 'purchase_note', 'virtual_product', 'downloadable_product', 'downloadable_files', 'download_limit', 'download_expiry', 'categories', 'tags', 'attributes', 'default_attributes', 'upsell_products', 'cross_sell_products', 'parent_product_id', 'main_image', 'gallery_images', 'variations', 'brands', 'color', 'size', 'material']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(products_data)
        
        # Sauvegarde du CSV des catégories (toujours créer le fichier)
        with open(categories_filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['name', 'slug', 'parent', 'url']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            if site_categories:
                writer.writerows(site_categories)
            else:
                # Créer des catégories à partir des produits
                product_categories = set()
                for product in products_data:
                    if product['categories']:
                        cats = [cat.strip() for cat in product['categories'].split(',')]
                        for cat in cats:
                            if cat:
                                product_categories.add(cat)
                
                for cat in product_categories:
                    writer.writerow({
                        'name': cat,
                        'slug': cat.lower().replace(' ', '-').replace('&', 'and'),
                        'parent': '',
                        'url': ''
                    })
        
        jobs[job_id]['filepath'] = scrape_folder
        jobs[job_id]['products_filepath'] = products_filepath
        jobs[job_id]['categories_filepath'] = categories_filepath if site_categories else None
        jobs[job_id]['progress'] = 100
        jobs[job_id]['status'] = f'Terminé! {len(products_data)} produits, {len(site_categories)} catégories'
        save_jobs()
        
    except Exception as e:
        jobs[job_id]['status'] = f'Erreur: {str(e)}'
        jobs[job_id]['progress'] = 100
        save_jobs()

if __name__ == '__main__':
    app.run(debug=True)