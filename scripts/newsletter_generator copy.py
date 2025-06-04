import os
import yaml
import markdown
import re
import math
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

def calculate_freshness(create_time, mod_time, is_new, has_frontmatter, in_recent_rotation):
    """
    Calcule un score de fraîcheur qui change avec le temps pour prioriser les fichiers.
    
    Paramètres:
    - create_time: Date de création du fichier
    - mod_time: Date de dernière modification du fichier
    - is_new: Si le fichier n'a jamais été inclus dans une newsletter
    - has_frontmatter: Si le fichier a un frontmatter YAML valide
    - in_recent_rotation: Si le fichier a été utilisé récemment
    
    Retourne:
    Score de fraîcheur (plus élevé = plus prioritaire)
    """
    now = datetime.now()
    
    # Pénalité pour les fichiers récemment utilisés
    rotation_penalty = 500 if in_recent_rotation else 0
    
    # Base du score: priorité absolue aux nouveaux fichiers
    base_score = 1000 if is_new else 0
    
    # Facteurs de récence
    days_since_creation = max(1, (now - create_time).days)
    days_since_modification = max(1, (now - mod_time).days)
    
    # Scores de récence (décroissance logarithmique pour réduire l'impact du temps)
    # Plus le fichier est ancien, plus son score diminue, mais de moins en moins vite
    creation_score = 100 / (1 + math.log10(days_since_creation))
    modification_score = 50 / (1 + math.log10(days_since_modification))
    
    # Bonus pour les fichiers avec frontmatter
    frontmatter_bonus = 25 if has_frontmatter else 0
    
    # Composante aléatoire pour introduire de la variété (valeur entre 0 et 15)
    import random
    random_factor = random.uniform(0, 15)
    
    # Score final
    return base_score + creation_score + modification_score + frontmatter_bonus + random_factor - rotation_penalty

def get_recent_md_files(docs_directory, processed_files_path, max_count=6, days_ago=30, 
                        force_rotation=False, rotation_count=2, rotation_memory=10):
    """
    Récupère les fichiers Markdown récemment ajoutés, modifiés ou non encore traités,
    avec option de rotation forcée pour garantir la diversité des contenus.
    
    Paramètres:
    - docs_directory: Chemin vers le répertoire contenant les fichiers Markdown
    - processed_files_path: Chemin vers le fichier listant les fichiers déjà traités
    - max_count: Nombre maximum de fichiers à sélectionner
    - days_ago: Période de recherche pour les fichiers récents (en jours)
    - force_rotation: Activer la rotation forcée de contenus
    - rotation_count: Nombre de fichiers à remplacer lors d'une rotation forcée
    - rotation_memory: Taille de l'historique des fichiers récemment sélectionnés
    
    Retourne:
    Liste des fichiers sélectionnés
    """
    try:
        if not os.path.exists(docs_directory):
            logger.error(f"Le répertoire {docs_directory} n'existe pas")
            return []

        now = datetime.now()
        cutoff_date = now - timedelta(days=days_ago)
        
        # Chargement des fichiers déjà traités
        processed_files = set()
        if os.path.exists(processed_files_path):
            with open(processed_files_path, 'r', encoding='utf-8') as f:
                processed_files = set(f.read().splitlines())
        
        # Historique des fichiers récemment sélectionnés (pour la rotation)
        rotation_history_path = os.path.join(os.path.dirname(processed_files_path), 'rotation_history.txt')
        recent_selections = []
        
        if os.path.exists(rotation_history_path):
            with open(rotation_history_path, 'r', encoding='utf-8') as f:
                recent_selections = [line.strip() for line in f.readlines()]
                # Limiter l'historique à rotation_memory entrées
                recent_selections = recent_selections[-rotation_memory:]
        
        # Liste pour stocker tous les fichiers candidats
        all_candidate_files = []
        
        # Analyser tous les fichiers
        for filename in os.listdir(docs_directory):
            if filename.endswith('.md'):
                file_path = os.path.join(docs_directory, filename)
                file_stats = os.stat(file_path)
                mod_time = datetime.fromtimestamp(file_stats.st_mtime)
                create_time = datetime.fromtimestamp(file_stats.st_ctime)
                
                # Marquer les attributs importants
                is_new = file_path not in processed_files
                is_recently_created = create_time >= cutoff_date
                is_recently_modified = mod_time >= cutoff_date
                has_frontmatter = has_valid_frontmatter(file_path)
                in_recent_rotation = file_path in recent_selections
                
                # Ajouter à la liste des candidats
                all_candidate_files.append({
                    'path': file_path,
                    'filename': filename,
                    'modified_at': mod_time,
                    'created_at': create_time,
                    'is_new': is_new,
                    'recently_created': is_recently_created,
                    'recently_modified': is_recently_modified,
                    'has_frontmatter': has_frontmatter,
                    'in_recent_rotation': in_recent_rotation,
                    'freshness_score': calculate_freshness(create_time, mod_time, is_new, has_frontmatter, in_recent_rotation)
                })
        
        # Tri basé sur le score de fraîcheur
        sorted_files = sorted(all_candidate_files, key=lambda x: x['freshness_score'], reverse=True)
        
        # Sélection de base - les fichiers les mieux notés
        selected_files = sorted_files[:max_count]
        
        # Si la rotation forcée est activée, remplacer certains fichiers
        if force_rotation and len(sorted_files) > max_count:
            # Identifier les chemins de fichiers déjà sélectionnés
            selected_paths = [file['path'] for file in selected_files]
            
            # Trouver des candidats éligibles pour la rotation qui ne sont pas déjà sélectionnés
            rotation_candidates = [
                file for file in sorted_files[max_count:] 
                if file['path'] not in recent_selections and file['path'] not in selected_paths
            ]
            
            # Effectuer la rotation si nous avons des candidats
            if rotation_candidates:
                # Tri des fichiers sélectionnés par score croissant (les moins intéressants d'abord)
                selected_files.sort(key=lambda x: x['freshness_score'])
                
                # Déterminer combien de fichiers remplacer (minimum entre rotation_count et candidats disponibles)
                replacements = min(rotation_count, len(rotation_candidates))
                
                logger.info(f"Rotation forcée: Remplacement de {replacements} fichiers")
                
                # Remplacer les fichiers les moins bien notés par de nouveaux candidats
                for i in range(replacements):
                    # Retirer le fichier le moins intéressant (maintenant à l'index 0 après tri)
                    removed_file = selected_files.pop(0)
                    logger.info(f"Rotation: Retrait de '{removed_file['filename']}'")
                    
                    # Ajouter un nouveau candidat à la place
                    new_file = rotation_candidates[i]
                    selected_files.append(new_file)
                    logger.info(f"Rotation: Ajout de '{new_file['filename']}'")
                
                # Re-trier la liste finale par score
                selected_files.sort(key=lambda x: x['freshness_score'], reverse=True)
        
        # Mettre à jour l'historique de rotation
        new_rotation_history = recent_selections + [file['path'] for file in selected_files]
        # Limiter l'historique à rotation_memory entrées
        new_rotation_history = new_rotation_history[-rotation_memory:]
        
        with open(rotation_history_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_rotation_history))
        
        # Mettre à jour les fichiers traités
        for file in selected_files:
            processed_files.add(file['path'])
        
        # Sauvegarder la liste mise à jour des fichiers traités
        with open(processed_files_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(processed_files))
        
        # Log détaillé des fichiers sélectionnés
        for file in selected_files:
            logger.info(f"Fichier sélectionné: {file['filename']}")
            logger.info(f"  - Nouveau: {file['is_new']}")
            logger.info(f"  - Créé récemment: {file['recently_created']}")
            logger.info(f"  - Modifié récemment: {file['recently_modified']}")
            logger.info(f"  - Avec frontmatter: {file['has_frontmatter']}")
            logger.info(f"  - Score de fraîcheur: {file['freshness_score']}")
        
        # Formater les résultats comme avant
        result_files = []
        for file in selected_files:
            result_files.append({
                'path': file['path'],
                'filename': file['filename'],
                'modified_at': file['modified_at'],
                'created_at': file['created_at'],
                'newly_added': file['is_new'],
                'recently_created': file['recently_created'],
                'recently_modified': file['recently_modified'],
                'has_frontmatter': file['has_frontmatter']
            })
        
        return result_files
    
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
    
    # Paramètres de rotation forcée
    force_rotation = os.environ.get('FORCE_ROTATION', 'false').lower() == 'true'
    rotation_count = int(os.environ.get('ROTATION_COUNT', '2'))
    rotation_memory = int(os.environ.get('ROTATION_MEMORY', '10'))
    
    # Logs de débogage
    logger.info(f"Répertoire portfolio: {portfolio_directory}")
    logger.info(f"Répertoire docs: {docs_directory}")
    logger.info(f"Répertoire de sortie: {output_directory}")
    logger.info(f"Rotation forcée: {force_rotation}")
    if force_rotation:
        logger.info(f"Nombre de fichiers à remplacer: {rotation_count}")
        logger.info(f"Taille de l'historique de rotation: {rotation_memory}")
    
    # Copie des images
    header_image_exists = copy_images_to_newsletter(portfolio_directory, output_directory)
    
    # Récupération des fichiers Markdown récents avec gestion de la rotation
    recent_files = get_recent_md_files(
        docs_directory, 
        processed_files_path,
        max_count=int(os.environ.get('MAX_COUNT', '6')),
        days_ago=int(os.environ.get('DAYS_AGO', '30')),
        force_rotation=force_rotation,
        rotation_count=rotation_count,
        rotation_memory=rotation_memory
    )
    
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
    avec conservation des liens hypertextes
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
            
            for elem in project_elem.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'ol', 'a']):
                if elem.name in ['h1', 'h2', 'h3']:
                    current_section = elem.text.strip()
                    sections[current_section] = []
                elif current_section and elem.name in ['p', 'ul', 'ol', 'a']:
                    # Pour les paragraphes, listes et liens
                    if elem.name == 'p':
                        # Traiter les liens dans les paragraphes
                        paragraph_text = elem.decode_contents()
                        for link in elem.find_all('a'):
                            paragraph_text = paragraph_text.replace(
                                str(link), 
                                f"[{link.text}]({link.get('href', '')})"
                            )
                        sections[current_section].append(('paragraph', paragraph_text.strip()))
                    elif elem.name == 'ul':
                        list_items = [('bullet', li.text.strip()) for li in elem.find_all('li')]
                        sections[current_section].extend(list_items)
                    elif elem.name == 'ol':
                        list_items = [('numbered', li.text.strip()) for li in elem.find_all('li')]
                        sections[current_section].extend(list_items)
                    elif elem.name == 'a':
                        # Liens directs
                        sections[current_section].append(('link', f"[{elem.text}]({elem.get('href', '')})"))
            
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
                    elif item_type == 'link':
                        markdown += f"{item}\n\n"
                
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