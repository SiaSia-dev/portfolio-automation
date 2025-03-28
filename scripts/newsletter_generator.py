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

def get_recent_md_files(docs_directory, processed_files_path, max_count=6, days_ago=30):
    """
    Récupère les fichiers Markdown récemment ajoutés, modifiés ou non encore traités.
    
    Améliorations:
    - Détection améliorée des fichiers nouvellement ajoutés
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
        logger.info(f"Date limite pour considérer un fichier comme récent: {cutoff_date}")
        
        # Vérifier si le fichier processed_files.txt existe
        logger.info(f"Recherche du fichier de suivi: {processed_files_path}")
        if os.path.exists(processed_files_path):
            logger.info(f"Fichier de suivi trouvé: {processed_files_path}")
            try:
                # Charger la liste des fichiers déjà traités
                with open(processed_files_path, 'r') as f:
                    processed_files = set(f.read().splitlines())
                logger.info(f"Nombre de fichiers déjà traités: {len(processed_files)}")
            except Exception as e:
                logger.error(f"Erreur lors de la lecture de {processed_files_path}: {e}")
                processed_files = set()
        else:
            logger.warning(f"Fichier de suivi non trouvé: {processed_files_path}. Initialisation d'une liste vide.")
            processed_files = set()
        
        # Définir le chemin du fichier de scan précédent
        last_scan_path = os.path.join(os.path.dirname(processed_files_path), 'last_scan_files.txt')
        logger.info(f"Fichier de dernier scan: {last_scan_path}")
        
        # Obtenir la liste actuelle des fichiers et leurs timestamps
        current_files = {}
        logger.info(f"Scan du répertoire {docs_directory} pour les fichiers .md")
        
        try:
            for filename in os.listdir(docs_directory):
                if filename.endswith('.md'):
                    file_path = os.path.join(docs_directory, filename)
                    file_stats = os.stat(file_path)
                    mod_time = datetime.fromtimestamp(file_stats.st_mtime)
                    current_files[file_path] = mod_time.timestamp()
            logger.info(f"Nombre de fichiers .md trouvés: {len(current_files)}")
        except Exception as e:
            logger.error(f"Erreur lors du scan du répertoire {docs_directory}: {e}")
            return []
        
        # Charger les fichiers du dernier scan s'ils existent
        previous_files = {}
        if os.path.exists(last_scan_path):
            logger.info(f"Fichier de dernier scan trouvé: {last_scan_path}")
            try:
                with open(last_scan_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            parts = line.strip().split('|')
                            if len(parts) == 2:
                                previous_files[parts[0]] = float(parts[1])
                logger.info(f"Nombre de fichiers dans le scan précédent: {len(previous_files)}")
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du fichier last_scan_files.txt: {e}")
        else:
            logger.warning(f"Fichier de dernier scan non trouvé: {last_scan_path}")
        
        # Identifier les fichiers nouvellement ajoutés depuis le dernier scan
        newly_added_files = set(current_files.keys()) - set(previous_files.keys())
        if newly_added_files:
            logger.info(f"Fichiers nouvellement ajoutés ({len(newly_added_files)}):")
            for file_path in newly_added_files:
                logger.info(f"  - {os.path.basename(file_path)}")
        else:
            logger.info("Aucun fichier nouvellement ajouté détecté")
        
        # Enregistrer le scan actuel pour la prochaine exécution
        try:
            logger.info(f"Écriture du fichier de scan actuel: {last_scan_path}")
            with open(last_scan_path, 'w') as f:
                for file_path, timestamp in current_files.items():
                    f.write(f"{file_path}|{timestamp}\n")
            logger.info(f"Fichier de scan sauvegardé avec {len(current_files)} entrées")
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture du fichier last_scan_files.txt: {e}")
        
        # Liste pour stocker les fichiers à traiter
        md_files = []
        
        # Liste pour suivre les fichiers qui seront sélectionnés pour cette newsletter
        selected_files_paths = set()
        
        # Analyser chaque fichier Markdown pour déterminer s'il doit être inclus
        for filename in os.listdir(docs_directory):
            if filename.endswith('.md'):
                file_path = os.path.join(docs_directory, filename)
                file_stats = os.stat(file_path)
                
                # Date de dernière modification
                mod_time = datetime.fromtimestamp(file_stats.st_mtime)
                
                # Date de création/changement de métadonnées
                create_time = datetime.fromtimestamp(file_stats.st_ctime)
                
                # Vérifier différents critères de sélection
                is_new = file_path not in processed_files
                is_newly_added = file_path in newly_added_files
                is_recently_modified = mod_time >= cutoff_date
                is_recently_created = create_time >= cutoff_date
                
                # Logs détaillés pour le débogage
                logger.debug(f"Analyse de {filename}:")
                logger.debug(f"  - Chemin: {file_path}")
                logger.debug(f"  - Date de modification: {mod_time}")
                logger.debug(f"  - Date de métadonnées: {create_time}")
                logger.debug(f"  - Jamais traité: {is_new}")
                logger.debug(f"  - Nouvellement ajouté: {is_newly_added}")
                logger.debug(f"  - Récemment modifié: {is_recently_modified}")
                logger.debug(f"  - Métadonnées récentes: {is_recently_created}")
                
                # Sélectionner le fichier s'il correspond à un des critères
                if is_newly_added or is_new or is_recently_modified or is_recently_created:
                    logger.info(f"Fichier sélectionné: {filename}")
                    logger.info(f"  - Nouvellement ajouté: {is_newly_added}")
                    logger.info(f"  - Jamais traité: {is_new}")
                    logger.info(f"  - Récemment modifié: {is_recently_modified}")
                    logger.info(f"  - Métadonnées récentes: {is_recently_created}")
                    
                    md_files.append({
                        'path': file_path,
                        'modified_at': mod_time,
                        'created_at': create_time,
                        'filename': filename,
                        'newly_added': is_newly_added
                    })
                    
                    # Ajouter ce fichier à la liste des fichiers sélectionnés
                    selected_files_paths.add(file_path)
                else:
                    logger.debug(f"Fichier ignoré: {filename}")
        
        # Stratégie de tri:
        # 1. Priorité aux fichiers vraiment nouveaux
        # 2. Puis aux fichiers jamais traités
        # 3. Ensuite par date de création décroissante
        # 4. Enfin par date de modification décroissante
        sorted_files = sorted(
            md_files, 
            key=lambda x: (
                not x.get('newly_added', False),  # True avant False
                x['path'] in processed_files,     # False avant True
                -x['created_at'].timestamp(),     # Plus grand (plus récent) d'abord
                -x['modified_at'].timestamp()     # Plus grand (plus récent) d'abord
            )
        )
        
        # Limiter au nombre maximum spécifié
        recent_files = sorted_files[:max_count]
        logger.info(f"Nombre de fichiers sélectionnés pour la newsletter: {len(recent_files)}")
        
        # Si des fichiers ont été sélectionnés, les journaliser
        if recent_files:
            logger.info("Fichiers sélectionnés pour la newsletter:")
            for idx, file in enumerate(recent_files):
                logger.info(f"  {idx+1}. {file['filename']}")
                logger.info(f"     - Nouvellement ajouté: {file.get('newly_added', False)}")
                logger.info(f"     - Date de modification: {file['modified_at']}")
        
        # Mise à jour de la liste des fichiers traités - SEULEMENT ceux qui ont été sélectionnés
        processed_files.update(selected_files_paths)
        
        # Sauvegarder la liste mise à jour des fichiers traités
        try:
            logger.info(f"Écriture du fichier de suivi: {processed_files_path}")
            with open(processed_files_path, 'w') as f:
                f.write('\n'.join(processed_files))
            logger.info(f"Fichier de suivi sauvegardé avec {len(processed_files)} entrées")
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture du fichier processed_files.txt: {e}")
        
        return recent_files
    
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des fichiers récents: {e}")
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

def save_newsletter(content, output_directory, file_date):
    """
    Sauvegarde la newsletter dans un fichier avec un nom horodaté.
    """
    try:
        # Créer le répertoire de sortie s'il n'existe pas
        Path(output_directory).mkdir(parents=True, exist_ok=True)
        
        # Générer un nom de fichier avec la date au format YYYYMMDD
        filename = f"newsletter_{file_date}.md"
        
        file_path = os.path.join(output_directory, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Newsletter sauvegardée: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de la newsletter: {e}")
        return None

def generate_newsletter_content(md_files, portfolio_directory, output_directory, display_date):
    """
    Génère le contenu de la newsletter à partir des fichiers Markdown.
    """
    if not md_files:
        logger.warning("Aucun fichier Markdown récent trouvé")
        return "Aucun contenu récent disponible pour cette newsletter.", []
    
    newsletter_content = f"""# Newsletter Portfolio - {display_date}


Découvrez mes derniers projets et réalisations !

"""
    
    # Liste pour stocker les informations de projet pour le HTML
    projects = []
    
    for file_info in md_files:
        metadata, content = extract_metadata_and_content(file_info['path'])
        
        # Extraire le titre, description, tags et URL du projet
        title = metadata.get('title', os.path.splitext(file_info['filename'])[0])
        description = metadata.get('description', '')
        tags = metadata.get('tags', [])
        url = metadata.get('url', '')
        
        # Trouver une image pour le projet
        image_path = find_image_for_project(title, content, portfolio_directory)
        image_filename = os.path.basename(image_path) if image_path else ""
        
        # Si une image a été trouvée, la copier dans le dossier img de la newsletter
        if image_path and os.path.exists(image_path):
            output_img_dir = os.path.join(output_directory, "img")
            os.makedirs(output_img_dir, exist_ok=True)
            output_image_path = os.path.join(output_img_dir, image_filename)
            try:
                shutil.copy2(image_path, output_image_path)
            except Exception as e:
                logger.error(f"Erreur lors de la copie de l'image {image_path}: {e}")
        
        image_rel_path = f"img/{image_filename}" if image_filename else ""
        
        # Si aucune image n'a été trouvée, utiliser un placeholder
        if not image_rel_path:
            image_rel_path = f"https://via.placeholder.com/600x400?text={title.replace(' ', '+')}"
        
        # Convertir le contenu markdown en HTML
        html_content = markdown.markdown(content)
        
        # Nettoyer le HTML pour un résumé
        soup = BeautifulSoup(html_content, 'html.parser')
        clean_text = soup.get_text(separator=' ', strip=True)
        
        # Limiter le contenu pour l'aperçu
        summary = clean_text[:250] + "..." if len(clean_text) > 250 else clean_text
        
        # Créer une section pour ce projet dans le Markdown
        newsletter_content += f"""## {title}

{description}

{summary}

"""
        
        # Ajouter les tags s'ils existent
        if tags:
            tags_str = ', '.join([f"#{tag}" for tag in tags])
            newsletter_content += f"**Tags**: {tags_str}\n\n"
        
        # Ajouter un lien si disponible
        newsletter_content += f"[En savoir plus]({url or '#'})\n\n"
        
        newsletter_content += "---\n\n"
        
        # Stocker les informations pour le HTML
        projects.append({
            'title': title,
            'description': description,
            'content': content,
            'html_content': html_content,
            'summary': summary,
            'tags': tags,
            'url': url,
            'image': image_rel_path,
            'filename': file_info['filename'],
            'path': file_info['path'],
            'id': f"project-{os.path.splitext(file_info['filename'])[0]}"  # ID unique pour l'ancre
        })
    
    # Ajouter une signature
    newsletter_content += """
## Restons connectés !

N'hésitez pas à me contacter pour discuter de projets ou simplement échanger sur nos domaines d'intérêt communs.

- [Portfolio](https://portfolio-af-v2.netlify.app/)
- [LinkedIn](https://www.linkedin.com/in/alexiafontaine)
"""
    
    return newsletter_content, projects

def generate_single_file_html(projects, display_date, output_directory, file_date, header_image_exists=False):
    """
    Génère un fichier HTML unique contenant tous les projets avec leurs contenus détaillés.
    """
    try:
        # Style CSS pour la page
        css_style = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Poppins:wght@300;400;500&display=swap');
            
            :root {
                --primary: #4a6d8c;
                --secondary: #2a475e;
                --accent: #90afc5;
                --light: #f6f9fc;
                --dark: #333333;
                --text: #444444;
                --shadow: 0 5px 20px rgba(0, 0, 0, 0.05);
                --border: 1px solid #eaeaea;
                --radius: 8px;
            }
            
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Poppins', sans-serif;
                line-height: 1.7;
                color: var(--text);
                background-color: var(--light);
                padding: 0;
                margin: 0;
                scroll-behavior: smooth;
            }
            
            .container {
                max-width: 1100px;
                margin: 0 auto;
                padding: 40px 20px;
                background-color: white;
                box-shadow: var(--shadow);
                border-radius: var(--radius);
            }
        """
        
        # Ajouter le style de l'en-tête en fonction de l'existence de l'image d'en-tête
        if header_image_exists:
            css_style += """
            .header {
                text-align: center;
                margin-bottom: 50px;
                padding: 60px 20px;
                background-image: url('img/header-bg.jpg');
                background-size: cover;
                background-position: center;
                border-radius: var(--radius);
                position: relative;
                color: white;
            }
            
            .header::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(42, 71, 94, 0.7);
                border-radius: var(--radius);
                z-index: 1;
            }
            
            .header-content {
                position: relative;
                z-index: 2;
            }
            
            .header h1 {
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 15px;
                color: white;
                position: relative;
                display: inline-block;
            }
            
            .header h1::after {
                content: '';
                position: absolute;
                left: 50%;
                bottom: -10px;
                transform: translateX(-50%);
                width: 60px;
                height: 3px;
                background-color: var(--accent);
            }
            
            .header p {
                color: rgba(255, 255, 255, 0.9);
            }
            """
        else:
            css_style += """
            .header {
                text-align: center;
                margin-bottom: 50px;
            }
            
            .header h1 {
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 15px;
                color: var(--primary);
                position: relative;
                display: inline-block;
            }
            
            .header h1::after {
                content: '';
                position: absolute;
                left: 50%;
                bottom: -10px;
                transform: translateX(-50%);
                width: 60px;
                height: 3px;
                background-color: var(--accent);
            }
            """
        
        # Continuer avec le reste du CSS
        css_style += """
            h2 {
                font-size: 1.8rem;
                margin-bottom: 15px;
                scroll-margin-top: 50px;
            }
            
            h3 {
                font-size: 1.5rem;
                margin-top: 30px;
                margin-bottom: 15px;
            }
            
            p {
                margin-bottom: 20px;
            }
            
            img {
                max-width: 100%;
                height: auto;
                border-radius: var(--radius);
                margin: 1em 0;
            }
            
            a {
                color: var(--primary);
                text-decoration: none;
                transition: all 0.3s ease;
            }
            
            a:hover {
                color: var(--accent);
                text-decoration: underline;
            }
            
            .grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 30px;
                margin-bottom: 50px;
            }
            
            .project-card {
                border-radius: var(--radius);
                overflow: hidden;
                box-shadow: var(--shadow);
                transition: all 0.3s ease;
                background-color: white;
            }
            
            .project-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 15px 30px rgba(0, 0, 0, 0.1);
            }
            
            .project-image-container {
                overflow: hidden;
                height: 200px;
            }
            
            .project-image {
                width: 100%;
                height: 100%;
                object-fit: cover;
                transition: transform 0.5s ease;
            }
            
            .project-card:hover .project-image {
                transform: scale(1.05);
            }
            
            .project-content {
                padding: 25px;
            }
            
            .project-title {
                font-size: 1.4rem;
                margin-bottom: 10px;
                color: var(--primary);
            }
            
            .project-description {
                font-weight: 500;
                margin-bottom: 15px;
                color: var(--dark);
            }
            
            .project-summary {
                margin-bottom: 20px;
                font-size: 0.95rem;
                color: var(--text);
            }
            
            .toc {
                background-color: var(--light);
                padding: 20px;
                border-radius: var(--radius);
                margin-bottom: 30px;
                text-align: center;
                max-width: 600px;
                margin-left: auto;
                margin-right: auto;
            }
            
            .toc-title {
                font-weight: 600;
                margin-bottom: 10px;
                font-size: 1.2rem;
                color: var(--primary);
            }
            
            .toc-list {
                list-style-type: none;
                margin-left: 0;
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                text-align: center;
            }
            
            .toc-item {
                margin-bottom: 5px;
            }
            
            .toc-item a {
                display: block;
                padding: 8px;
                background-color: white;
                border-radius: var(--radius);
                transition: all 0.3s ease;
            }
            
            .toc-item a:hover {
                background-color: var(--accent);
                color: white;
                text-decoration: none;
                transform: translateY(-2px);
            }
            
            .tags {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-bottom: 20px;
                margin-top: 20px;
            }
            
            .tag {
                background-color: var(--light);
                color: var(--primary);
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            
            .tag:hover {
                background-color: var(--accent);
                color: white;
            }
            
            .btn {
                display: inline-block;
                background-color: var(--primary);
                color: white !important;
                padding: 10px 20px;
                border-radius: 25px;
                text-decoration: none;
                font-weight: 500;
                transition: all 0.3s ease;
                border: none;
                font-size: 0.9rem;
                letter-spacing: 0.5px;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
                cursor: pointer;
            }
            
            .btn:hover {
                background-color: var(--secondary);
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
                color: white !important;
                text-decoration: none !important;
            }
            
            .back-to-top {
                display: inline-block;
                margin-top: 30px;
                margin-bottom: 50px;
            }
            
            .footer {
                text-align: center;
                padding-top: 40px;
                border-top: var(--border);
                margin-top: 30px;
            }
            
            .social-links {
                display: flex;
                justify-content: center;
                gap: 30px;
                margin: 25px 0;
            }
            
            .social-link {
                color: var(--primary);
                text-decoration: none;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            
            .social-link:hover {
                color: var(--secondary);
                text-decoration: underline;
            }
            
            .copyright {
                font-size: 0.9rem;
                color: #777;
                margin-top: 30px;
            }
            
            .project-full-content {
                padding: 40px;
                margin-bottom: 60px;
                background-color: white;
                border-radius: var(--radius);
                box-shadow: var(--shadow);
            }
            
            .project-full-content img.hero-image {
                width: 100%;
                max-height: 400px;
                object-fit: cover;
                border-radius: var(--radius);
                margin-bottom: 30px;
            }
            
            blockquote {
                border-left: 4px solid var(--accent);
                padding-left: 20px;
                margin: 1em 0;
                font-style: italic;
                color: var(--text);
            }
            
            ul, ol {
                margin-left: 1.5em;
                margin-bottom: 1em;
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            
            table th, table td {
                border: 1px solid #ddd;
                padding: 8px;
            }
            
            table th {
                padding-top: 12px;
                padding-bottom: 12px;
                text-align: left;
                background-color: var(--accent);
                color: white;
            }
            
            code {
                background-color: #f0f0f0;
                padding: 2px 5px;
                border-radius: 3px;
                font-family: monospace;
            }
            
            pre {
                background-color: #f0f0f0;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
                margin: 20px 0;
            }
            
            pre code {
                padding: 0;
                background-color: transparent;
            }
            
            hr {
                border: none;
                height: 1px;
                background-color: #eaeaea;
                margin: 25px 0;
            }
            
            /* Styles responsifs */
            @media (max-width: 900px) {
                .grid {
                    grid-template-columns: 1fr;
                }
                
                .container {
                    padding: 20px;
                }
                
                h1 {
                    font-size: 2rem;
                }
                
                .project-full-content {
                    padding: 20px;
                }
                
                .toc-list {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """
        
        # Générer la table des matières
        toc_html = """
        <div class="toc">
            <div class="toc-title">Table des matières</div>
            <ul class="toc-list">
        """
        
        for project in projects:
            toc_html += f'<li class="toc-item"><a href="#{project["id"]}">{project["title"]}</a></li>'
        
        toc_html += """
            </ul>
        </div>
        """
        
        # Générer le HTML pour chaque projet dans la grille
        projects_grid_html = ""
        for project in projects:
            # Générer les tags
            tags_html = ""
            if project['tags']:
                tags_html = '<div class="tags">'
                for tag in project['tags']:
                    tags_html += f'<span class="tag">{tag}</span>'
                tags_html += '</div>'
            
            # Définir l'image du projet
            image_src = project['image']
            
            # Lien vers la section détaillée du projet
            project_link = f"#{project['id']}"
            
            # Générer le HTML pour ce projet dans la grille
            projects_grid_html += f"""
            <div class="project-card">
                <div class="project-image-container">
                    <img class="project-image" src="{image_src}" alt="{project['title']}" loading="lazy">
                </div>
                <div class="project-content">
                    <h2 class="project-title">{project['title']}</h2>
                    <div class="project-description">{project['description']}</div>
                    <div class="project-summary">{project['summary']}</div>
                    {tags_html}
                    <a href="{project_link}" class="btn">En savoir plus</a>
                </div>
            </div>
            """
        
        # Générer le HTML pour le contenu détaillé de chaque projet
        projects_detail_html = ""
        for project in projects:
            # Générer les tags
            tags_html = ""
            if project['tags']:
                tags_html = '<div class="tags">'
                for tag in project['tags']:
                    tags_html += f'<span class="tag">{tag}</span>'
                tags_html += '</div>'
            
            # Définir l'image du projet
            image_src = project['image']
            
            # Convertir le contenu markdown en HTML
            html_content = markdown.markdown(project['content'])
            
            # Générer le HTML pour le contenu détaillé de ce projet
            projects_detail_html += f"""
            <div id="{project['id']}" class="project-full-content">
                <h2>{project['title']}</h2>
                
                <img class="hero-image" src="{image_src}" alt="{project['title']}" loading="lazy">
                
                {html_content}
                
                {tags_html}
                
                <a href="#" class="btn back-to-top">Retour en haut</a>
            </div>
            """
        
        # Générer le nom du fichier HTML avec le format YYYYMMDD
        html_filename = f"newsletter_{file_date}.html"
        
        # Générer le HTML de l'en-tête en fonction de l'existence de l'image d'en-tête
        if header_image_exists:
            header_html = f"""
            <div class="header">
                <div class="header-content">
                    <h1>Newsletter Portfolio</h1>
                    <p>{display_date}</p>
                    <p>Découvrez mes derniers projets et réalisations dans cette newsletter hebdomadaire.</p>
                    <h3>Récits visuels, horizons numériques :</h3> 
                    <h3>Chaque newsletter, un voyage entre données, créativité et découvertes</h3>
                </div>
            </div>
            """
        else:
            header_html = f"""
            <div class="header">
                <h1>Newsletter Portfolio</h1>
                <p>{display_date}</p>
                <p>Découvrez mes derniers projets et réalisations dans cette newsletter hebdomadaire.</p>
            </div>
            """
        
        # Assembler le HTML complet
        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newsletter Portfolio - {display_date}</title>
    {css_style}
</head>
<body>
    <div class="container">
        {header_html}
        
        {toc_html}
        
        <div class="grid">
            {projects_grid_html}
        </div>
        
        {projects_detail_html}
        
        <div class="footer">
            <h2>Restons connectés !</h2>
            <p>N'hésitez pas à me contacter pour discuter de projets ou simplement échanger sur nos domaines d'intérêt communs.</p>
            
            <div class="social-links">
                <a href="https://portfolio-af-v2.netlify.app/" class="social-link" target="_blank" rel="noopener">Portfolio</a>
                <a href="https://www.linkedin.com/in/alexiafontaine" class="social-link" target="_blank" rel="noopener">LinkedIn</a>
            </div>
            
            <div class="copyright">
                <p>© {datetime.now().year} - Newsletter générée automatiquement depuis mon portfolio GitHub</p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        # Sauvegarder le HTML
        html_path = os.path.join(output_directory, html_filename)
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Newsletter HTML (fichier unique) sauvegardée: {html_path}")
        return html_path
    except Exception as e:
        logger.error(f"Erreur lors de la génération HTML: {e}")
        return None

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
    <meta http-equiv="refresh" content="0;url=latest.html">
    <title>Newsletter Portfolio</title>
</head>
<body>
    <p>Redirection vers la dernière newsletter...</p>
    <a href="latest.html">Cliquez ici si la redirection automatique ne fonctionne pas</a>
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
        
        # Créer le même index.html dans le dossier de sortie
        output_index_path = os.path.join(output_directory, "index.html")
        with open(output_index_path, 'w', encoding='utf-8') as f:
            f.write(index_content)
        logger.info(f"Index.html créé dans le dossier de sortie: {output_index_path}")
        
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
            if file not in ["archives.html", "latest.html", "index.html"]:
                # Extraire la date du nom de fichier
                date_match = re.search(r'newsletter_(\d{4})(\d{2})(\d{2})', file)
                if date_match:
                    year, month, day = date_match.groups()
                    formatted_date = f"{day}/{month}/{year}"
                else:
                    # Utiliser la date de modification si le format du nom ne correspond pas
                    mod_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(output_directory, file)))
                    formatted_date = mod_time.strftime("%d/%m/%Y")
                
                archives_content += f'        <li><a href="{file}">Newsletter du {formatted_date}</a></li>\n'
        
        archives_content += """    </ul>
    <p><a href="latest.html">Retour à la dernière newsletter</a></p>
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

# Ajouter à la fin du script, avant le main()
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
    # Ajouter ces appels au début de la fonction main()
    if os.environ.get('PORTFOLIO_DIR'):
        debug_log_portfolio_files(os.environ.get('PORTFOLIO_DIR'))
    
    additional_debug()
    
    # Chemins des répertoires (à ajuster selon votre configuration)
    portfolio_directory = os.environ.get('PORTFOLIO_DIR', '../portfolio')
    docs_directory = os.path.join(portfolio_directory, 'docs')
    output_directory = os.environ.get('OUTPUT_DIR', './newsletters')
    
    # Utiliser TRACKING_DIR s'il est défini, sinon utiliser le répertoire du script
    if 'TRACKING_DIR' in os.environ and os.environ['TRACKING_DIR']:
        tracking_directory = os.environ['TRACKING_DIR']
        logger.info(f"Utilisation du répertoire de suivi spécifié: {tracking_directory}")
    else:
        tracking_directory = os.path.dirname(__file__)
        logger.info(f"Utilisation du répertoire du script comme répertoire de suivi: {tracking_directory}")
    
    # Créer le répertoire de suivi s'il n'existe pas
    os.makedirs(tracking_directory, exist_ok=True)
    
    # Définir le chemin complet vers les fichiers de suivi
    processed_files_path = os.path.join(tracking_directory, 'processed_files.txt')
    logger.info(f"Chemin du fichier processed_files.txt: {processed_files_path}")
    
    # Aide au débogage - journaliser des informations sur l'environnement
    logger.info(f"Répertoire de travail: {os.getcwd()}")
    logger.info(f"Répertoire portfolio: {portfolio_directory}")
    logger.info(f"Répertoire docs: {docs_directory}")
    logger.info(f"Répertoire de sortie: {output_directory}")
    
    # Définir les formats de date
    display_date = datetime.now().strftime("%d/%m/%Y")  # Format jour/mois/année pour l'affichage (23/03/2025)
    file_date = datetime.now().strftime("%Y%m%d")       # Format année/mois/jour pour le nom de fichier (20250323)
    
    # Copier toutes les images du dossier img du PORTFOLIO vers le dossier img de la newsletter
    # et vérifier si l'image d'en-tête existe
    header_image_exists = copy_images_to_newsletter(portfolio_directory, output_directory)
    
    # Récupérer les fichiers Markdown récents
    recent_files = get_recent_md_files(docs_directory, processed_files_path)
    
    if recent_files:
        logger.info(f"Nombre de fichiers récents trouvés: {len(recent_files)}")
        for file in recent_files:
            logger.info(f"  - {file['filename']} (modifié le {file['modified_at']})")
            if file.get('newly_added', False):
                logger.info(f"    Ce fichier est nouvellement ajouté!")
    else:
        logger.warning("Aucun fichier récent trouvé")
    
    # Générer le contenu de la newsletter avec la date d'affichage
    newsletter_content, projects = generate_newsletter_content(recent_files, portfolio_directory, output_directory, display_date)
    
    # Sauvegarder la newsletter au format Markdown avec la date de fichier
    md_path = save_newsletter(newsletter_content, output_directory, file_date)

    if md_path:
        # Générer une version HTML avec tout le contenu intégré dans un seul fichier
        html_path = generate_single_file_html(projects, display_date, output_directory, file_date, header_image_exists)
        
        if html_path:
            logger.info("Newsletter générée avec succès.")
            logger.info(f"Ouvrez {html_path} dans votre navigateur pour voir le résultat.")
            
            # Créer les fichiers index.html, latest.html et archives.html si demandé
            if os.environ.get('CREATE_INDEX', 'true').lower() == 'true':
                create_index_and_archives(output_directory, file_date, display_date)
        else:
            logger.error("Erreur lors de la génération de la version HTML.")
    
    logger.info("Génération de la newsletter terminée")


if __name__ == "__main__":
    main()