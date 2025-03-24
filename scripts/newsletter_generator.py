import os
import yaml
import markdown
import re
from datetime import datetime, timedelta
from pathlib import Path
import logging
import shutil
from bs4 import BeautifulSoup

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('newsletter_generator')

def create_default_metadata(title, content):
    """
    Crée des métadonnées par défaut en extrayant des informations du contenu Markdown.
    """
    # Extraire les premiers 150 caractères comme description
    plain_text = BeautifulSoup(markdown.markdown(content), 'html.parser').get_text()
    description = plain_text[:150] + '...' if len(plain_text) > 150 else plain_text
    
    # Essayer d'extraire un meilleur titre du contenu (premier titre H1/H2)
    title_match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
    if title_match:
        extracted_title = title_match.group(1).strip()
        if extracted_title:
            title = extracted_title
    
    # Essayer d'extraire des tags potentiels du contenu
    tags = []
    hashtag_matches = re.findall(r'#([a-zA-Z0-9_]+)', content)
    if hashtag_matches:
        tags = list(set(hashtag_matches))  # Éliminer les doublons
    
    # Ajouter un tag par défaut si aucun n'a été trouvé
    if not tags:
        tags = ['portfolio']
    
    return {
        'title': title,
        'description': description,
        'tags': tags
    }

def extract_metadata_and_content(md_file_path):
    """
    Extrait les métadonnées et le contenu d'un fichier Markdown.
    Gère les cas avec ou sans frontmatter YAML.
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # Extraire le nom du fichier pour l'utiliser comme titre par défaut
        filename = os.path.basename(md_file_path)
        default_title = os.path.splitext(filename)[0].replace('-', ' ').title()

        # Vérifier la présence du format frontmatter YAML
        if content.startswith('---'):
            # Trouver les délimiteurs du frontmatter
            parts = content.split('---', 2)
            if len(parts) >= 3:
                # Extraire et parser les métadonnées
                metadata_yaml = parts[1].strip()
                try:
                    metadata = yaml.safe_load(metadata_yaml)
                    if metadata is None:  # Si le YAML est vide ou invalide
                        metadata = {}
                    main_content = parts[2].strip()
                    
                    # Ajouter les métadonnées par défaut si elles sont manquantes
                    if 'title' not in metadata:
                        metadata['title'] = default_title
                    if 'description' not in metadata:
                        # Extraire les premiers 150 caractères comme description
                        plain_text = BeautifulSoup(markdown.markdown(main_content), 'html.parser').get_text()
                        metadata['description'] = plain_text[:150] + '...' if len(plain_text) > 150 else plain_text
                    if 'tags' not in metadata:
                        metadata['tags'] = ['portfolio']
                        
                    return metadata, main_content
                except yaml.YAMLError as e:
                    logger.error(f"Erreur lors du parsing YAML dans {md_file_path}: {e}")
                    # En cas d'erreur, créer des métadonnées par défaut
                    metadata = create_default_metadata(default_title, content)
                    return metadata, content
            else:
                logger.warning(f"Format de frontmatter incorrect dans {md_file_path}")
                metadata = create_default_metadata(default_title, content)
                return metadata, content
        else:
            logger.warning(f"Pas de frontmatter trouvé dans {md_file_path}, création de métadonnées par défaut")
            metadata = create_default_metadata(default_title, content)
            return metadata, content
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du fichier {md_file_path}: {e}")
        return {'title': os.path.basename(md_file_path), 'description': '', 'tags': []}, ""

def get_recent_md_files(docs_directory, max_count=6, days_ago=30):
    """
    Récupère les fichiers Markdown les plus récents du répertoire docs.
    """
    try:
        if not os.path.exists(docs_directory):
            logger.error(f"Le répertoire {docs_directory} n'existe pas")
            return []

        now = datetime.now()
        cutoff_date = now - timedelta(days=days_ago)
        
        logger.info(f"Recherche de fichiers modifiés depuis le {cutoff_date.strftime('%Y-%m-%d')}")
        
        md_files = []
        for filename in os.listdir(docs_directory):
            if filename.endswith('.md'):
                file_path = os.path.join(docs_directory, filename)
                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # Vérifier si le fichier a été modifié dans les X derniers jours
                if mod_time >= cutoff_date:
                    md_files.append({
                        'path': file_path,
                        'modified_at': mod_time,
                        'filename': filename
                    })
        
        # Si aucun fichier récent n'est trouvé, prendre tous les fichiers
        if not md_files:
            logger.warning(f"Aucun fichier modifié depuis {days_ago} jours, utilisation de tous les fichiers disponibles")
            for filename in os.listdir(docs_directory):
                if filename.endswith('.md'):
                    file_path = os.path.join(docs_directory, filename)
                    mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    md_files.append({
                        'path': file_path,
                        'modified_at': mod_time,
                        'filename': filename
                    })
        
        # Trier par date de modification décroissante
        sorted_files = sorted(md_files, key=lambda x: x['modified_at'], reverse=True)
        
        # Limiter au nombre maximum spécifié
        return sorted_files[:max_count]
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des fichiers récents: {e}")
        return []

# [Toutes les autres fonctions précédentes restent identiques]

def create_index_and_archives(output_directory, file_date, display_date):
    """
    Crée les fichiers index.html, latest.html et archives.html.
    """
    try:
        # Créer le dossier de sortie s'il n'existe pas
        Path(output_directory).mkdir(parents=True, exist_ok=True)
        
        # Trouver tous les fichiers HTML de newsletter
        html_files = [f for f in os.listdir(output_directory) if f.startswith('newsletter_') and f.endswith('.html')]
        
        # Récupérer le répertoire parent
        parent_dir = os.path.dirname(output_directory)
        
        # Créer l'index.html à la racine
        index_path = os.path.join(parent_dir, "index.html")
        index_content = """<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0;url=./newsletters/latest.html">
    <title>Newsletter Portfolio</title>
</head>
<body>
    <p>Redirection vers la dernière newsletter...</p>
    <a href="./newsletters/latest.html">Cliquez ici si la redirection automatique ne fonctionne pas</a>
</body>
</html>"""

        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_content)
        logger.info(f"Index.html créé: {index_path}")
        
        # Créer le fichier .nojekyll
        nojekyll_path = os.path.join(parent_dir, ".nojekyll")
        with open(nojekyll_path, 'w') as f:
            f.write("")
        logger.info(f"Fichier .nojekyll créé: {nojekyll_path}")
        
        # Créer archives.html
        archives_path = os.path.join(output_directory, "archives.html")
        
        archives_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archives - Récits visuels, horizons numériques</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 40px; }
        h1 { color: #333; }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; padding: 10px; border-bottom: 1px solid #eee; }
        a { text-decoration: none; color: #0366d6; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Archives des newsletters</h1>
    <ul>
"""
        
        # Trier les fichiers par date (du plus récent au plus ancien)
        sorted_files = sorted(html_files, key=lambda f: os.path.getmtime(os.path.join(output_directory, f)), reverse=True)
        
        for file in sorted_files:
            if file not in ["archives.html", "latest.html"]:
                # Extraire la date du nom de fichier
                date_match = re.search(r'newsletter_(\d{4})(\d{2})(\d{2})', file)
                if date_match:
                    year, month, day = date_match.groups()
                    formatted_date = f"{day}/{month}/{year}"
                else:
                    # Utiliser la date de modification si le format du nom ne correspond pas
                    mod_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(output_directory, file)))
                    formatted_date = mod_time.strftime("%d/%m/%Y")
                
                archives_content += f'        <li><a href="./{file}">Newsletter du {formatted_date}</a></li>\n'
        
        archives_content += """    </ul>
    <p><a href="./latest.html">Retour à la dernière newsletter</a></p>
</body>
</html>
"""
        
        with open(archives_path, 'w', encoding='utf-8') as f:
            f.write(archives_content)
        logger.info(f"Fichier archives.html créé: {archives_path}")
        
        # Créer le fichier latest.html
        latest_file = sorted_files[0] if sorted_files else None
        if latest_file:
            latest_path = os.path.join(output_directory, "latest.html")
            shutil.copy2(os.path.join(output_directory, latest_file), latest_path)
            logger.info(f"Fichier latest.html créé pointant vers {latest_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la création des fichiers index et archives: {e}")
        return False

def copy_images_to_newsletter(portfolio_directory, output_directory):
    """
    Copie toutes les images du dossier img du PORTFOLIO vers le dossier img de la newsletter.
    Retourne True si l'image d'en-tête existe, False sinon.
    """
    # Chemin vers le dossier img dans le dépôt PORTFOLIO
    portfolio_img_dir = os.path.join(portfolio_directory, "img")
    
    # Chemin vers le dossier img dans le répertoire de sortie
    output_img_dir = os.path.join(output_directory, "img")
    
    # Variable pour suivre si l'image d'en-tête existe
    header_image_exists = False
    
    # Créer le dossier img s'il n'existe pas
    if not os.path.exists(output_img_dir):
        os.makedirs(output_img_dir)
        logger.info(f"Dossier créé: {output_img_dir}")
    
    # Copier toutes les images
    if os.path.exists(portfolio_img_dir):
        copied_count = 0
        for filename in os.listdir(portfolio_img_dir):
            if any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']):
                src_path = os.path.join(portfolio_img_dir, filename)
                dest_path = os.path.join(output_img_dir, filename)
                try:
                    shutil.copy2(src_path, dest_path)
                    copied_count += 1
                    
                    # Vérifier si c'est l'image d'en-tête
                    if filename == "header-bg.jpg":
                        header_image_exists = True
                        
                except Exception as e:
                    logger.error(f"Erreur lors de la copie de l'image {src_path}: {e}")
        
        logger.info(f"{copied_count} images copiées du dépôt PORTFOLIO vers le dossier newsletter/img")
        
        # Copier l'image d'en-tête si elle existe
        header_image_path = os.path.join(portfolio_img_dir, "Slowsia.jpg")
        if os.path.exists(header_image_path):
            header_dest_path = os.path.join(output_img_dir, "header-bg.jpg")
            try:
                shutil.copy2(header_image_path, header_dest_path)
                logger.info(f"Image d'en-tête copiée: {header_dest_path}")
                header_image_exists = True
            except Exception as e:
                logger.error(f"Erreur lors de la copie de l'image d'en-tête: {e}")
        else:
            logger.warning("Image d'en-tête 'Slowsia.jpg' non trouvée dans le dossier img")
    else:
        logger.warning(f"Dossier d'images non trouvé: {portfolio_img_dir}")
    
    return header_image_exists


def main():
    """
    Fonction principale du générateur de newsletter.
    """
    # Chemins des répertoires (à ajuster selon votre configuration)
    portfolio_directory = os.environ.get('PORTFOLIO_DIR', '../PORTFOLIO')
    docs_directory = os.path.join(portfolio_directory, 'docs')
    output_directory = os.environ.get('OUTPUT_DIR', './newsletters')
    
    # Variables de contrôle pour la création des fichiers supplémentaires
    create_index = os.environ.get('CREATE_INDEX', 'true').lower() == 'true'
    create_latest = os.environ.get('CREATE_LATEST', 'true').lower() == 'true'
    create_archives = os.environ.get('CREATE_ARCHIVES', 'true').lower() == 'true'
    
    logger.info(f"Recherche de fichiers Markdown récents dans {docs_directory}")
    logger.info(f"Répertoire de sortie: {output_directory}")
    
    # Définir les formats de date
    display_date = datetime.now().strftime("%d/%m/%Y")  # Format jour/mois/année pour l'affichage (23/03/2025)
    file_date = datetime.now().strftime("%Y%m%d")       # Format année/mois/jour pour le nom de fichier (20250323)
    
    # Copier toutes les images du dossier img du PORTFOLIO vers le dossier img de la newsletter
    # et vérifier si l'image d'en-tête existe
    header_image_exists = copy_images_to_newsletter(portfolio_directory, output_directory)
    
    # Récupérer les fichiers Markdown récents
    max_count = int(os.environ.get('CONTENT_COUNT', '6'))
    require_yaml = os.environ.get('REQUIRE_YAML', 'false').lower() == 'true'
    
    # Ajuster la fonction get_recent_md_files si nécessaire pour prendre en compte REQUIRE_YAML
    recent_files = get_recent_md_files(docs_directory, max_count=max_count)
    
    if recent_files:
        logger.info(f"Nombre de fichiers récents trouvés: {len(recent_files)}")
        for file in recent_files:
            logger.info(f"  - {file['filename']} (modifié le {file['modified_at']})")
    else:
        logger.warning("Aucun fichier récent trouvé")
    
    # Générer le contenu de la newsletter avec la date d'affichage
    newsletter_content, projects = generate_newsletter_content(recent_files, portfolio_directory, output_directory, display_date)
    
    # Sauvegarder la newsletter au format Markdown avec la date de fichier
    md_path = save_newsletter(newsletter_content, output_directory, file_date)

    success = False
    if md_path:
        # Générer une version HTML avec tout le contenu intégré dans un seul fichier
        html_path = generate_single_file_html(projects, display_date, output_directory, file_date, header_image_exists)
        
        if html_path:
            logger.info("Newsletter générée avec succès.")
            logger.info(f"Ouvrez {html_path} dans votre navigateur pour voir le résultat.")
            success = True
        else:
            logger.error("Erreur lors de la génération de la version HTML.")
    
    # Créer les fichiers index.html, latest.html et archives.html si demandé
    if success and (create_index or create_latest or create_archives):
        logger.info("Création des fichiers index, latest et archives...")
        create_index_and_archives(output_directory, file_date, display_date)
    
    logger.info("Génération de la newsletter terminée")
    return success

if __name__ == "__main__":
    main()