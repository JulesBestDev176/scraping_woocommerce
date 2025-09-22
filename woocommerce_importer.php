<?php
/**
 * Script d'import WooCommerce avec images
 * À placer dans le dossier racine de WordPress
 */

require_once('wp-config.php');
require_once('wp-load.php');

function import_products_from_csv($csv_file, $images_folder) {
    if (!file_exists($csv_file)) {
        die("Fichier CSV non trouvé: $csv_file\n");
    }
    
    $handle = fopen($csv_file, 'r');
    $header = fgetcsv($handle); // Ignorer l'en-tête
    
    $imported = 0;
    $errors = 0;
    
    while (($data = fgetcsv($handle)) !== FALSE) {
        try {
            $product_data = array_combine($header, $data);
            
            // Créer le produit
            $product = new WC_Product_Simple();
            $product->set_name($product_data['title']);
            $product->set_slug($product_data['slug']);
            $product->set_description($product_data['description']);
            $product->set_short_description($product_data['short_description']);
            $product->set_regular_price($product_data['regular_price']);
            $product->set_price($product_data['price']);
            $product->set_status($product_data['status']);
            
            // Catégories
            if (!empty($product_data['categories'])) {
                $categories = explode(',', $product_data['categories']);
                $cat_ids = [];
                foreach ($categories as $cat_name) {
                    $cat_name = trim($cat_name);
                    $term = get_term_by('name', $cat_name, 'product_cat');
                    if (!$term) {
                        $term = wp_insert_term($cat_name, 'product_cat');
                        $cat_ids[] = $term['term_id'];
                    } else {
                        $cat_ids[] = $term->term_id;
                    }
                }
                $product->set_category_ids($cat_ids);
            }
            
            // Tags
            if (!empty($product_data['tags'])) {
                $tags = explode(',', $product_data['tags']);
                $tag_ids = [];
                foreach ($tags as $tag_name) {
                    $tag_name = trim($tag_name);
                    $term = get_term_by('name', $tag_name, 'product_tag');
                    if (!$term) {
                        $term = wp_insert_term($tag_name, 'product_tag');
                        $tag_ids[] = $term['term_id'];
                    } else {
                        $tag_ids[] = $term->term_id;
                    }
                }
                $product->set_tag_ids($tag_ids);
            }
            
            // Sauvegarder le produit
            $product_id = $product->save();
            
            // Ajouter les images
            if (!empty($product_data['main_image'])) {
                $image_id = upload_image_to_media_library($images_folder . '/' . $product_data['main_image']);
                if ($image_id) {
                    set_post_thumbnail($product_id, $image_id);
                }
            }
            
            // Galerie d'images
            if (!empty($product_data['gallery_images'])) {
                $gallery_files = explode(';', $product_data['gallery_images']);
                $gallery_ids = [];
                foreach ($gallery_files as $file) {
                    if (!empty($file)) {
                        $image_id = upload_image_to_media_library($images_folder . '/' . $file);
                        if ($image_id) {
                            $gallery_ids[] = $image_id;
                        }
                    }
                }
                if (!empty($gallery_ids)) {
                    update_post_meta($product_id, '_product_image_gallery', implode(',', $gallery_ids));
                }
            }
            
            // Marque (si vous avez un plugin de marques)
            if (!empty($product_data['brands'])) {
                $brand_term = get_term_by('name', $product_data['brands'], 'product_brand');
                if (!$brand_term) {
                    $brand_term = wp_insert_term($product_data['brands'], 'product_brand');
                    wp_set_object_terms($product_id, $brand_term['term_id'], 'product_brand');
                } else {
                    wp_set_object_terms($product_id, $brand_term->term_id, 'product_brand');
                }
            }
            
            $imported++;
            echo "Produit importé: {$product_data['title']}\n";
            
        } catch (Exception $e) {
            $errors++;
            echo "Erreur: {$e->getMessage()}\n";
        }
    }
    
    fclose($handle);
    echo "\nImport terminé: $imported produits importés, $errors erreurs\n";
}

function upload_image_to_media_library($image_path) {
    if (!file_exists($image_path)) {
        return false;
    }
    
    $filename = basename($image_path);
    $upload_dir = wp_upload_dir();
    $upload_path = $upload_dir['path'] . '/' . $filename;
    
    // Copier le fichier
    if (!copy($image_path, $upload_path)) {
        return false;
    }
    
    // Créer l'attachment
    $attachment = array(
        'guid' => $upload_dir['url'] . '/' . $filename,
        'post_mime_type' => mime_content_type($upload_path),
        'post_title' => preg_replace('/\.[^.]+$/', '', $filename),
        'post_content' => '',
        'post_status' => 'inherit'
    );
    
    $attach_id = wp_insert_attachment($attachment, $upload_path);
    
    if (!is_wp_error($attach_id)) {
        require_once(ABSPATH . 'wp-admin/includes/image.php');
        $attach_data = wp_generate_attachment_metadata($attach_id, $upload_path);
        wp_update_attachment_metadata($attach_id, $attach_data);
        return $attach_id;
    }
    
    return false;
}

// Utilisation
if ($argc < 3) {
    die("Usage: php woocommerce_importer.php <csv_file> <images_folder>\n");
}

$csv_file = $argv[1];
$images_folder = $argv[2];

import_products_from_csv($csv_file, $images_folder);
?>