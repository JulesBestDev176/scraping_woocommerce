# Scraper E-commerce WooCommerce

Application Flask pour scraper automatiquement les produits d'un site e-commerce WooCommerce et les exporter en CSV.

## Installation

1. Installer les dépendances :
```bash
pip install -r requirements.txt
```

2. Lancer l'application :
```bash
python app.py
```

3. Ouvrir le navigateur sur : http://localhost:5000

## Utilisation

1. Coller l'URL d'un site e-commerce dans le champ
2. Cliquer sur "Télécharger les produits CSV"
3. Le fichier CSV sera automatiquement téléchargé

## Format CSV généré

Le CSV contient les colonnes suivantes :
- Nom
- Description courte  
- Description
- Catégories
- Étiquettes
- Marques
- Prix
- Image
- Gallery

## Fonctionnalités

- Détection automatique des produits WooCommerce
- Extraction des données produits (nom, prix, descriptions, images)
- Export CSV conforme au format fourni
- Interface web simple et intuitive
- Gestion des erreurs et feedback utilisateur