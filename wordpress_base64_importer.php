<?php
/**
 * Plugin Name: Base64 Image Importer
 * Description: Importe les produits avec images base64
 */

function import_base64_image($base64_data, $filename = '') {
    if (empty($base64_data) || strpos($base64_data, 'data:') !== 0) {
        return false;
    }
    
    // Extraire le type MIME et les données
    list($type, $data) = explode(';', $base64_data);
    list(, $data) = explode(',', $data);
    
    $mime_type = str_replace('data:', '', $type);
    $extension = '';
    
    switch ($mime_type) {
        case 'image/jpeg':
            $extension = '.jpg';
            break;
        case 'image/png':
            $extension = '.png';
            break;
        case 'image/webp':
            $extension = '.webp';
            break;
        case 'image/gif':
            $extension = '.gif';
            break;
        default:
            $extension = '.jpg';
    }
    
    // Décoder les données
    $image_data = base64_decode($data);
    
    if (!$image_data) {
        return false;
    }
    
    // Générer un nom de fichier unique
    if (empty($filename)) {
        $filename = 'imported_image_' . time() . '_' . wp_generate_password(8, false);
    }
    $filename = sanitize_file_name($filename . $extension);
    
    // Uploader l'image
    $upload_dir = wp_upload_dir();
    $file_path = $upload_dir['path'] . '/' . $filename;
    $file_url = $upload_dir['url'] . '/' . $filename;
    
    // Sauvegarder le fichier
    if (file_put_contents($file_path, $image_data) === false) {
        return false;
    }
    
    // Créer l'attachment
    $attachment = array(
        'guid' => $file_url,
        'post_mime_type' => $mime_type,
        'post_title' => preg_replace('/\.[^.]+$/', '', $filename),
        'post_content' => '',
        'post_status' => 'inherit'
    );
    
    $attachment_id = wp_insert_attachment($attachment, $file_path);
    
    if (!is_wp_error($attachment_id)) {
        require_once(ABSPATH . 'wp-admin/includes/image.php');
        $attachment_data = wp_generate_attachment_metadata($attachment_id, $file_path);
        wp_update_attachment_metadata($attachment_id, $attachment_data);
        return $attachment_id;
    }
    
    return false;
}

function process_product_with_base64_images($product_data) {
    // Traiter l'image principale
    if (!empty($product_data['main_image']) && strpos($product_data['main_image'], 'data:') === 0) {
        $main_image_id = import_base64_image($product_data['main_image'], $product_data['slug'] . '_main');
        if ($main_image_id) {
            $product_data['main_image'] = $main_image_id;
        }
    }
    
    // Traiter la galerie
    if (!empty($product_data['gallery_images'])) {
        $gallery_images = explode(';', $product_data['gallery_images']);
        $gallery_ids = array();
        
        foreach ($gallery_images as $index => $base64_image) {
            if (!empty($base64_image) && strpos($base64_image, 'data:') === 0) {
                $gallery_id = import_base64_image($base64_image, $product_data['slug'] . '_gallery_' . $index);
                if ($gallery_id) {
                    $gallery_ids[] = $gallery_id;
                }
            }
        }
        
        $product_data['gallery_images'] = implode(',', $gallery_ids);
    }
    
    return $product_data;
}

// Exemple d'utilisation avec WooCommerce
function import_products_from_base64_csv($csv_file) {
    if (!file_exists($csv_file)) {
        return false;
    }
    
    $handle = fopen($csv_file, 'r');
    if (!$handle) {
        return false;
    }
    
    // Lire l'en-tête
    $headers = fgetcsv($handle);
    $imported = 0;
    
    while (($data = fgetcsv($handle)) !== FALSE) {
        $product_data = array_combine($headers, $data);
        
        // Traiter les images base64
        $product_data = process_product_with_base64_images($product_data);
        
        // Créer le produit WooCommerce
        $product = new WC_Product_Simple();
        $product->set_name($product_data['title']);
        $product->set_slug($product_data['slug']);
        $product->set_regular_price($product_data['regular_price']);
        $product->set_description($product_data['description']);
        $product->set_short_description($product_data['short_description']);
        
        // Définir l'image principale
        if (is_numeric($product_data['main_image'])) {
            $product->set_image_id($product_data['main_image']);
        }
        
        // Définir la galerie
        if (!empty($product_data['gallery_images'])) {
            $gallery_ids = explode(',', $product_data['gallery_images']);
            $gallery_ids = array_filter($gallery_ids, 'is_numeric');
            $product->set_gallery_image_ids($gallery_ids);
        }
        
        // Catégories
        if (!empty($product_data['categories'])) {
            $categories = explode(',', $product_data['categories']);
            $category_ids = array();
            foreach ($categories as $cat_name) {
                $cat_name = trim($cat_name);
                $term = get_term_by('name', $cat_name, 'product_cat');
                if (!$term) {
                    $term = wp_insert_term($cat_name, 'product_cat');
                    if (!is_wp_error($term)) {
                        $category_ids[] = $term['term_id'];
                    }
                } else {
                    $category_ids[] = $term->term_id;
                }
            }
            $product->set_category_ids($category_ids);
        }
        
        $product->save();
        $imported++;
    }
    
    fclose($handle);
    return $imported;
}

// Hook pour ajouter un menu d'administration
add_action('admin_menu', function() {
    add_submenu_page(
        'tools.php',
        'Import Base64 Products',
        'Import Base64 Products',
        'manage_options',
        'import-base64-products',
        'base64_import_page'
    );
});

function base64_import_page() {
    if (isset($_POST['import_csv']) && isset($_FILES['csv_file'])) {
        $uploaded_file = $_FILES['csv_file'];
        if ($uploaded_file['error'] === UPLOAD_ERR_OK) {
            $imported = import_products_from_base64_csv($uploaded_file['tmp_name']);
            echo '<div class="notice notice-success"><p>' . $imported . ' produits importés avec succès!</p></div>';
        }
    }
    ?>
    <div class="wrap">
        <h1>Import Base64 Products</h1>
        <form method="post" enctype="multipart/form-data">
            <table class="form-table">
                <tr>
                    <th scope="row">Fichier CSV</th>
                    <td>
                        <input type="file" name="csv_file" accept=".csv" required>
                        <p class="description">Sélectionnez le fichier products_base64.csv</p>
                    </td>
                </tr>
            </table>
            <?php submit_button('Importer les produits', 'primary', 'import_csv'); ?>
        </form>
    </div>
    <?php
}
?>