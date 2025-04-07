import os
import yaml
import markdown
import re
from datetime import datetime, timedelta
from pathlib import Path
import logging
import shutil
from bs4 import BeautifulSoup
from newsletter_template import (
    generate_newsletter_template, 
    generate_archives_template, 
    generate_index_template, 
    generate_latest_template
)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('newsletter_generator')

def has_valid_frontmatter(file_path):
    """
    Vérifie si un fichier Markdown a un frontmatter YAML valide.
    
    Retourne :
    - True si un frontmatter valide existe
    - False sinon
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        # Vérifier la présence du frontmatter YAML
        if content.startswith('---'):
            # Trouver les délimiteurs du frontmatter
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    # Essayer de parser le frontmatter
                    metadata_yaml = parts[1].strip()
                    yaml.safe_load(metadata_yaml)
                    return True
                except yaml.YAMLError:
                    return False
        return False
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du frontmatter pour {file_path}: {e}")
        return False

def get_recent_md_files(docs_directory, processed_files_path, max_count=6, days_ago=30):

    try:
        if not os.path.exists(docs_directory):
            logger.error(f"Le répertoire {docs_directory} n'existe pas")
            return []

        now = datetime.now()
        cutoff_date = now - timedelta(days=days_ago)
        logger.info(f"Date limite pour considérer un fichier comme récent: {cutoff_date}")
        
        # Charger la liste des fichiers déjà traités s'il existe
        processed_files = set()
        if os.path.exists(processed_files_path):
            with open(processed_files_path, 'r') as f:
                processed_files = set(f.read().splitlines())
        logger.info(f"Nombre de fichiers déjà traités: {len(processed_files)}")
        
        # Dictionnaire pour stocker les fichiers sélectionnés, avec leur chemin comme clé
        selected_files = {}
        
        for filename in os.listdir(docs_directory):
            if filename.endswith('.md'):
                file_path = os.path.join(docs_directory, filename)
                file_stats = os.stat(file_path)
                
                # Date de dernière modification
                mod_time = datetime.fromtimestamp(file_stats.st_mtime)
                
                # Date de création (dernière metadata change time)
                create_time = datetime.fromtimestamp(file_stats.st_ctime)
                
                # Vérifier les différents critères
                is_new = file_path not in processed_files
                is_recently_created = create_time >= cutoff_date
                is_recently_modified = mod_time >= cutoff_date
                has_frontmatter = has_valid_frontmatter(file_path)
                
                # Critères de sélection
                is_selected = (
                    is_new or 
                    is_recently_created or 
                    is_recently_modified or 
                    has_frontmatter
                )
                
                if is_selected:
                    # Ajouter ou mettre à jour l'entrée
                    if file_path not in selected_files:
                        selected_files[file_path] = {
                            'path': file_path,
                            'modified_at': mod_time,
                            'created_at': create_time,
                            'filename': filename,
                            'newly_added': is_new,
                            'recently_created': is_recently_created,
                            'recently_modified': is_recently_modified,
                            'has_frontmatter': has_frontmatter
                        }
        
        # Tri selon les priorités spécifiées
        sorted_files = sorted(
            selected_files.values(), 
            key=lambda x: (
                # 1. Priorité absolue aux fichiers jamais traités
                not x['path'] in processed_files,
                
                # 2. Puis fichiers créés récemment
                not x['recently_created'],
                
                # 3. Puis fichiers modifiés récemment
                not x['recently_modified'],
                
                # 4. Puis fichiers avec frontmatter
                not x['has_frontmatter'],
                
                # 5. Par date de création décroissante
                -x['created_at'].timestamp(),
                
                # 6. Par date de modification décroissante
                -x['modified_at'].timestamp()
            ), 
            reverse=True
        )
        
        # Limiter le nombre de fichiers
        recent_files = sorted_files[:max_count]
        logger.info(f"Nombre de fichiers sélectionnés: {len(recent_files)}")
        
        # Mettre à jour la liste des fichiers traités
        processed_files.update(file['path'] for file in recent_files)
        
        # Sauvegarder la liste des fichiers traités
        with open(processed_files_path, 'w') as f:
            f.write('\n'.join(processed_files))
        logger.info(f"Liste des fichiers traités sauvegardée dans {processed_files_path}")
        
        # Log détaillé des fichiers sélectionnés
        for file in recent_files:
            logger.info(f"Fichier sélectionné: {file['filename']}")
            logger.info(f"  - Nouveau: {file['newly_added']}")
            logger.info(f"  - Créé récemment: {file['recently_created']}")
            logger.info(f"  - Modifié récemment: {file['recently_modified']}")
            logger.info(f"  - Avec frontmatter: {file['has_frontmatter']}")
        
        return recent_files
    
    except Exception as e:
        logger.exception(f"Erreur lors de la sélection des fichiers récents: {str(e)}")
        return []

def extract_metadata_and_content(md_file_path):
    """
    Extrait les métadonnées et le contenu d'un fichier Markdown.
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # Vérifier la présence du format frontmatter YAML
        if content.startswith('---'):
            # Trouver les délimiteurs du frontmatter
            parts = content.split('---', 2)
            if len(parts) >= 3:
                # Extraire et parser les métadonnées
                metadata_yaml = parts[1].strip()
                try:
                    metadata = yaml.safe_load(metadata_yaml)
                    main_content = parts[2].strip()
                    return metadata, main_content
                except yaml.YAMLError as e:
                    logger.error(f"Erreur lors du parsing YAML dans {md_file_path}: {e}")
                    return {}, content
            else:
                logger.warning(f"Format de frontmatter incorrect dans {md_file_path}")
                return {}, content
        else:
            logger.warning(f"Pas de frontmatter trouvé dans {md_file_path}")
            return {}, content
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du fichier {md_file_path}: {e}")
        return {}, ""

    """
    Récupère les fichiers Markdown récemment ajoutés, modifiés ou non encore traités.
    
    Améliorations:
    - Ne sauvegarde que les fichiers réellement sélectionnés dans processed_files.txt
    - Période de vérification réduite à 30 jours par défaut
    - Meilleure logique pour déterminer quels fichiers inclure
    """
    try:
        if not os.path.exists(docs_directory):
            logger.error(f"Le répertoire {docs_directory} n'existe pas")
            return []

        now = datetime.now()
        cutoff_date = now - timedelta(days=days_ago)
        logger.info(f"Date limite : {cutoff_date}")
        
        # Charger la liste des fichiers déjà traités s'il existe
        processed_files = set()
        if os.path.exists(processed_files_path):
            with open(processed_files_path, 'r') as f:
                processed_files = set(f.read().splitlines())
        logger.info(f"Nombre de fichiers déjà traités : {len(processed_files)}")
        
        # Liste pour stocker les nouveaux fichiers à traiter
        md_files = []
        
        # Liste pour suivre les fichiers qui seront sélectionnés pour cette newsletter
        selected_files_paths = set()
        
        for filename in os.listdir(docs_directory):
            if filename.endswith('.md'):
                file_path = os.path.join(docs_directory, filename)
                file_stats = os.stat(file_path)
                
                logger.debug(f"Traitement du fichier : {file_path}")
                
                # Date de dernière modification
                mod_time = datetime.fromtimestamp(file_stats.st_mtime)
                
                # Date de création (dernière metadata change time)
                create_time = datetime.fromtimestamp(file_stats.st_ctime)
                
                # Vérifier si le fichier est:
                # 1. Jamais traité OU
                # 2. Récemment modifié OU
                # 3. Récemment créé
                is_new = file_path not in processed_files
                is_recently_modified = mod_time >= cutoff_date
                is_recently_created = create_time >= cutoff_date
                
                if is_new or is_recently_modified or is_recently_created:
                    logger.info(f"Fichier sélectionné: {filename} - Nouveau: {is_new}, Modifié récemment: {is_recently_modified}, Créé récemment: {is_recently_created}")
                    
                    md_files.append({
                        'path': file_path,
                        'modified_at': mod_time,
                        'created_at': create_time,
                        'filename': filename
                    })
                    
                    # Ajouter ce fichier à la liste des fichiers sélectionnés
                    selected_files_paths.add(file_path)
                else:
                    logger.debug(f"Fichier ignoré : {file_path}")
        
        # Stratégie de tri modifiée:
        # 1. Priorité aux fichiers jamais traités
        # 2. Ensuite par date de création décroissante
        # 3. Puis par date de modification décroissante
        sorted_files = sorted(
            md_files, 
            key=lambda x: (
                x['path'] in processed_files,  # False (nouveaux) avant True (déjà traités)
                -x['created_at'].timestamp(),  # Tri inversé par timestamp (plus récent d'abord)
                -x['modified_at'].timestamp()
            )
        )
        
        # Limiter au nombre maximum spécifié
        recent_files = sorted_files[:max_count]
        
        # Mise à jour de la liste des fichiers traités - SEULEMENT ceux qui ont été sélectionnés
        processed_files.update(selected_files_paths)
        
        # Sauvegarder la liste mise à jour des fichiers traités
        with open(processed_files_path, 'w') as f:
            f.write('\n'.join(processed_files))
        
        return recent_files
    
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des fichiers récents : {e}")
        return []

def extract_image_from_content(content):
    """
    Tente d'extraire une URL d'image du contenu Markdown.
    """
    # Chercher les images dans le format markdown ![alt](url)
    image_matches = re.findall(r'!\[(.*?)\]\((.*?)\)', content)
    if image_matches:
        # Prendre la première image trouvée
        return image_matches[0][1]
    
    # Chercher les images en HTML <img src="url">
    html_image_matches = re.findall(r'<img.*?src=[\'"]([^\'"]*)[\'"]', content)
    if html_image_matches:
        return html_image_matches[0]
    
    return None

def find_image_for_project(project_name, content, portfolio_directory):
    """
    Recherche une image pour le projet, en cherchant d'abord dans le contenu puis dans le dossier img.
    """
    # 1. D'abord, chercher dans le contenu du fichier markdown
    image_from_content = extract_image_from_content(content)
    if image_from_content:
        # Si c'est un chemin relatif, le convertir en chemin absolu
        if not image_from_content.startswith(('http://', 'https://')):
            # Supposer que les chemins sont relatifs au dossier img
            image_path = os.path.join(portfolio_directory, "img", os.path.basename(image_from_content))
            if os.path.exists(image_path):
                return image_path
        else:
            # Si c'est une URL, la retourner directement
            return image_from_content
    
    # 2. Ensuite, chercher dans le dossier img par nom de projet
    img_dir = os.path.join(portfolio_directory, "img")
    if os.path.exists(img_dir):
        # Normaliser le nom du projet pour la recherche
        normalized_name = project_name.lower().replace(' ', '-').replace('_', '-')
        
        # Extensions d'image courantes
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']
        
        # Rechercher par nom exact ou partiel
        for filename in os.listdir(img_dir):
            if any(filename.lower().endswith(ext) for ext in image_extensions):
                name_part = os.path.splitext(filename.lower())[0]
                if normalized_name in name_part or name_part in normalized_name:
                    return os.path.join(img_dir, filename)
        
        # Si aucune correspondance, prendre la première image
        for filename in os.listdir(img_dir):
            if any(filename.lower().endswith(ext) for ext in image_extensions):
                return os.path.join(img_dir, filename)
    
    # 3. Si aucune image n'est trouvée, renvoyer None
    return None

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
        
        # Trier les fichiers par date (du plus récent au plus ancien)
        sorted_files = sorted(html_files, key=lambda f: os.path.getmtime(os.path.join(output_directory, f)), reverse=True)
        
        # La dernière newsletter
        latest_file = sorted_files[0] if sorted_files else None
        
        if latest_file:
            # Générer et sauvegarder index.html à la racine
            index_content = generate_index_template(latest_file)
            index_path = os.path.join(parent_dir, "index.html")
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(index_content)
            logger.info(f"Index.html créé: {index_path}")
            
            # Créer le fichier .nojekyll
            nojekyll_path = os.path.join(parent_dir, ".nojekyll")
            open(nojekyll_path, 'a').close()
            logger.info(f"Fichier .nojekyll créé: {nojekyll_path}")
            
            # Copier index.html dans le dossier de sortie
            output_index_path = os.path.join(output_directory, "index.html")
            with open(output_index_path, 'w', encoding='utf-8') as f:
                f.write(index_content)
            
            # Générer latest.html
            latest_path = os.path.join(output_directory, "latest.html")
            latest_content = generate_latest_template(os.path.join(output_directory, latest_file))
            with open(latest_path, 'w', encoding='utf-8') as f:
                f.write(latest_content)
            logger.info(f"Latest.html créé: {latest_path}")
            
            # Générer archives.html
            archives_path = os.path.join(output_directory, "archives.html")
            archives_content = generate_archives_template(output_directory)
            with open(archives_path, 'w', encoding='utf-8') as f:
                f.write(archives_content)
            logger.info(f"Archives.html créé: {archives_path}")
            
            return True
        else:
            logger.warning("Aucune newsletter trouvée pour générer les fichiers")
            return False
        
    except Exception as e:
        logger.error(f"Erreur lors de la création des fichiers index et archives: {e}")
        return False
def debug_log_portfolio_files(portfolio_directory):
    """
    Fonction de débogage pour logger les détails des fichiers du portfolio.
    """
    docs_directory = os.path.join(portfolio_directory, 'docs')
    
    logger.info("=== DÉBOGAGE : CONTENU DU RÉPERTOIRE DOCS ===")
    logger.info(f"Chemin absolu du répertoire docs: {os.path.abspath(docs_directory)}")
    
    try:
        # Lister tous les fichiers
        all_files = os.listdir(docs_directory)
        logger.info(f"Tous les fichiers dans docs: {all_files}")
        
        # Détails des fichiers Markdown
        md_files = [f for f in all_files if f.endswith('.md')]
        logger.info(f"Fichiers Markdown trouvés: {md_files}")
        
        # Informations détaillées sur chaque fichier Markdown
        for filename in md_files:
            file_path = os.path.join(docs_directory, filename)
            file_stats = os.stat(file_path)
            
            logger.info(f"Fichier: {filename}")
            logger.info(f"  Chemin complet: {file_path}")
            logger.info(f"  Taille: {file_stats.st_size} octets")
            logger.info(f"  Dernière modification: {datetime.fromtimestamp(file_stats.st_mtime)}")
    
    except Exception as e:
        logger.error(f"Erreur lors du débogage : {e}")
        
def additional_debug():
    """
    Fonction pour des logs de débogage supplémentaires.
    """
    logger.info("=== DÉBOGAGE : INFORMATIONS SUPPLÉMENTAIRES ===")
    logger.info(f"Répertoire de travail courant: {os.getcwd()}")
    logger.info(f"Environnement PORTFOLIO_DIR: {os.environ.get('PORTFOLIO_DIR', 'Non défini')}")
    logger.info(f"Environnement OUTPUT_DIR: {os.environ.get('OUTPUT_DIR', 'Non défini')}")

def main():
    """
    Fonction principale du générateur de newsletter.
    """
    logger.info("=== DÉBUT DE LA GÉNÉRATION DE LA NEWSLETTER ===")
    
    # Configuration des chemins
    portfolio_directory = os.environ.get('PORTFOLIO_DIR', '../portfolio')
    docs_directory = os.path.join(portfolio_directory, 'docs')
    output_directory = os.environ.get('OUTPUT_DIR', './newsletters')
    tracking_directory = os.environ.get('TRACKING_DIR', os.path.dirname(__file__))
    
    # Préparation des répertoires
    os.makedirs(tracking_directory, exist_ok=True)
    processed_files_path = os.path.join(tracking_directory, 'processed_files.txt')
    
    # Configuration des dates
    display_date = datetime.now().strftime("%d/%m/%Y")
    file_date = datetime.now().strftime("%Y%m%d")
    
    # Logs de débogage
    logger.info(f"Répertoire portfolio: {portfolio_directory}")
    logger.info(f"Répertoire docs: {docs_directory}")
    logger.info(f"Répertoire de sortie: {output_directory}")
    
    # Copie des images
    header_image_exists = copy_images_to_newsletter(portfolio_directory, output_directory)
    
    # Récupération des fichiers Markdown récents
    recent_files = get_recent_md_files(docs_directory, processed_files_path)
    
    if not recent_files:
        logger.warning("Aucun fichier récent trouvé")
        return False
    
    # Préparation des projets
    projects = []
    for file_info in recent_files:
        try:
            metadata, content = extract_metadata_and_content(file_info['path'])
            
            # Extraction des métadonnées
            title = metadata.get('title', os.path.splitext(file_info['filename'])[0])
            description = metadata.get('description', '')
            tags = metadata.get('tags', [])
            url = metadata.get('url', '')
            
            # Recherche et copie de l'image
            image_path = find_image_for_project(title, content, portfolio_directory)
            image_filename = os.path.basename(image_path) if image_path else ""
            
            if image_path and os.path.exists(image_path):
                output_img_dir = os.path.join(output_directory, "img")
                os.makedirs(output_img_dir, exist_ok=True)
                output_image_path = os.path.join(output_img_dir, image_filename)
                shutil.copy2(image_path, output_image_path)
            
            # Chemin de l'image
            image_rel_path = f"img/{image_filename}" if image_filename else \
                f"https://via.placeholder.com/600x400?text={title.replace(' ', '+')}"
            
            # Ajout du projet
            projects.append({
                'title': title,
                'description': description,
                'content': content,
                'tags': tags,
                'url': url,
                'image': image_rel_path,
                'filename': file_info['filename'],
                'path': file_info['path'],
                'id': f"project-{os.path.splitext(file_info['filename'])[0]}"
            })
        
        except Exception as e:
            logger.error(f"Erreur lors du traitement du fichier {file_info['filename']}: {e}")
    
    # Génération de la newsletter
    if not projects:
        logger.warning("Aucun projet trouvé pour générer la newsletter")
        return False
    
    try:
        # Génération du contenu HTML
        html_content = generate_newsletter_template(projects, display_date, header_image_exists)
        
        # Nom et chemin des fichiers
        html_filename = f"newsletter_{file_date}.html"
        html_path = os.path.join(output_directory, html_filename)
        
        # Sauvegarde du HTML
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Newsletter HTML générée : {html_path}")
        
        
        # Conversion et sauvegarde du Markdown LinkedIn
        markdown_linkedin_content = convert_html_to_linkedin_markdown(html_content)
        if markdown_linkedin_content:
            markdown_linkedin_filename = f"newsletter_{file_date}_linkedin.md"
            markdown_linkedin_path = os.path.join(output_directory, markdown_linkedin_filename)
            
            with open(markdown_linkedin_path, 'w', encoding='utf-8') as f:
                f.write(markdown_linkedin_content)
            logger.info(f"Newsletter LinkedIn Markdown générée : {markdown_linkedin_path}")
        
        # Création des fichiers d'index
        if os.environ.get('CREATE_INDEX', 'true').lower() == 'true':
            create_index_and_archives(output_directory, file_date, display_date)
        
        logger.info("Génération de la newsletter terminée avec succès")
        return True
    
    except Exception as e:
        logger.error(f"Erreur lors de la génération de la newsletter : {e}")
        return False

def convert_html_to_markdown(html_content):
    """
    Convertit un contenu HTML en Markdown.
    """
    import html2text
    
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0  # Ne pas couper les lignes
    
    markdown_text = h.handle(html_content)
    return markdown_text

def convert_html_to_linkedin_markdown(html_content):
    """
    Convertit le contenu HTML en Markdown optimisé pour LinkedIn
    avec une mise en page structurée et des tirets
    """
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        projects = []
        
        # Emojis correspondant aux types de projets courants
        project_emojis = {
            "data": "📊", "approche": "🎨", "patrimoine": "🏛️", 
            "avatar": "🤖", "ecriture": "✍️", "fleur": "🌸", 
            "creation": "🎨", "visualisation": "📊", "analyse": "📈", 
            "culture": "🎭", "documentation": "📝", "intelligence": "🧠"
        }
        
        # Trouver tous les projets détaillés
        project_elements = soup.select('.project-full-content')
        
        for project_elem in project_elements:
            # Extraire titre et sous-titres
            title = project_elem.h2.text.strip() if project_elem.h2 else ""
            
            # Trouver les différentes sections
            sections = {}
            current_section = None
            
            for elem in project_elem.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'ol']):
                if elem.name in ['h1', 'h2', 'h3']:
                    current_section = elem.text.strip()
                    sections[current_section] = []
                elif current_section and elem.name in ['p', 'ul', 'ol']:
                    # Pour les paragraphes et listes
                    if elem.name == 'p':
                        sections[current_section].append(('paragraph', elem.text.strip()))
                    elif elem.name == 'ul':
                        list_items = [('bullet', li.text.strip()) for li in elem.find_all('li')]
                        sections[current_section].extend(list_items)
                    elif elem.name == 'ol':
                        list_items = [('numbered', li.text.strip()) for li in elem.find_all('li')]
                        sections[current_section].extend(list_items)
            
            # Image du projet
            img_elem = project_elem.select_one('.hero-image')
            image = img_elem.get('src', '') if img_elem else ''
            
            # Déterminer emoji
            emoji = next((emoji for keyword, emoji in project_emojis.items() 
                          if keyword.lower() in title.lower()), "📌")
            
            projects.append({
                'title': title,
                'image': image,
                'sections': sections,
                'emoji': emoji
            })
        
        # Générer le markdown
        markdown = f"# 📰 Newsletter Portfolio - {datetime.now().strftime('%d/%m/%Y')}\n\n"
        markdown += "## Récits visuels, horizons numériques : Un voyage entre créativité et innovation 🚀\n\n"
        markdown += "---\n\n"
        
        for project in projects:
            # Titre du projet avec emoji
            markdown += f"### {project['emoji']} {project['title']}\n\n"
            
            # Image si disponible
            if project['image']:
                markdown += f"![{project['title']}]({project['image']})\n\n"
            
            # Parcourir les sections
            for section, content in project['sections'].items():
                # Titre de section
                markdown += f"#### {section}\n\n"
                
                # Contenu de la section
                for item_type, item in content:
                    if item_type == 'paragraph':
                        markdown += f"{item}\n\n"
                    elif item_type == 'bullet':
                        markdown += f"- {item}\n"
                    elif item_type == 'numbered':
                        markdown += f"1. {item}\n"
                
                # Ajouter un saut de ligne après chaque section
                markdown += "\n"
            
            # Séparateur entre les projets
            markdown += "---\n\n"
        
        # Philosophie et conclusion
        markdown += "## 💡 Philosophie de l'Innovation\n\n"
        markdown += "> \"L'innovation naît à l'intersection des disciplines, là où la créativité rencontre la technologie.\"\n\n"
        
        # Section de contact
        markdown += "## 📱 Restons connectés !\n\n"
        markdown += "**Envie d'explorer de nouveaux horizons numériques ?**\n\n"
        markdown += "— [Portfolio Complet](https://portfolio-af-v2.netlify.app/)  \n"
        markdown += "— [Me Contacter sur LinkedIn](https://www.linkedin.com/in/alexiafontaine)\n\n"
        
        # Hashtags
        markdown += "#Innovation #TechCreative #DataScience #DigitalTransformation #CreativeTech\n\n"
        
        markdown += f"© {datetime.now().year} Alexia Fontaine - Tous droits réservés"
        
        return markdown
    
    except Exception as e:
        logger.error(f"Erreur lors de la conversion LinkedIn Markdown: {e}")
        return None

if __name__ == "__main__":
    main()