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

def get_recent_md_files(docs_directory, max_count=6, days_ago=7):
    """
    Récupère les fichiers Markdown les plus récents du répertoire docs.
    """
    try:
        if not os.path.exists(docs_directory):
            logger.error(f"Le répertoire {docs_directory} n'existe pas")
            return []

        now = datetime.now()
        cutoff_date = now - timedelta(days=days_ago)
        
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
        
        # Trier par date de modification décroissante
        sorted_files = sorted(md_files, key=lambda x: x['modified_at'], reverse=True)
        
        # Limiter au nombre maximum spécifié
        return sorted_files[:max_count]
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des fichiers récents: {e}")
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
            logger.warning("Image d'en-tête 'Carneti.jpg' non trouvée dans le dossier img")
    else:
        logger.warning(f"Dossier d'images non trouvé: {portfolio_img_dir}")
    
    return header_image_exists

def save_newsletter(content, output_directory):
    """
    Sauvegarde la newsletter dans un fichier avec un nom horodaté.
    """
    try:
        # Créer le répertoire de sortie s'il n'existe pas
        Path(output_directory).mkdir(parents=True, exist_ok=True)
        
        # Générer un nom de fichier avec la date
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"newsletter_{timestamp}.md"
        
        file_path = os.path.join(output_directory, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Newsletter sauvegardée: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de la newsletter: {e}")
        return None

def generate_newsletter_content(md_files, portfolio_directory, output_directory):
    """
    Génère le contenu de la newsletter à partir des fichiers Markdown.
    """
    if not md_files:
        logger.warning("Aucun fichier Markdown récent trouvé")
        return "Aucun contenu récent disponible pour cette newsletter.", []

    newsletter_date = datetime.now().strftime("%d/%m/%Y")
    
    newsletter_content = f"""# Newsletter Portfolio - {newsletter_date}

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

- [Portfolio](https://votre-portfolio.com)
- [LinkedIn](https://www.linkedin.com/in/alexiafontaine)
"""
    
    return newsletter_content, projects

def generate_single_file_html(projects, newsletter_date, output_directory, header_image_exists=False):
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
        
        # Formater la date pour le nom de fichier
        formatted_date = newsletter_date.replace('/', '')
        
        # Générer le HTML de l'en-tête en fonction de l'existence de l'image d'en-tête
        if header_image_exists:
            header_html = f"""
            <div class="header">
                <div class="header-content">
                    <h1>Newsletter Portfolio</h1>
                    <p>{newsletter_date}</p>
                    <p>Découvrez mes derniers projets et réalisations dans cette newsletter hebdomadaire.</p>
                </div>
            </div>
            """
        else:
            header_html = f"""
            <div class="header">
                <h1>Newsletter Portfolio</h1>
                <p>{newsletter_date}</p>
                <p>Découvrez mes derniers projets et réalisations dans cette newsletter hebdomadaire.</p>
            </div>
            """
        
        # Assembler le HTML complet
        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newsletter Portfolio - {newsletter_date}</title>
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
                <a href="https://votre-portfolio.com" class="social-link" target="_blank" rel="noopener">Portfolio</a>
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
        html_filename = f"newsletter_{formatted_date}.html"
        html_path = os.path.join(output_directory, html_filename)
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Newsletter HTML (fichier unique) sauvegardée: {html_path}")
        return html_path
    except Exception as e:
        logger.error(f"Erreur lors de la génération HTML: {e}")
        return None

def main():
    """
    Fonction principale du générateur de newsletter.
    """
    # Chemins des répertoires (à ajuster selon votre configuration)
    portfolio_directory = os.environ.get('PORTFOLIO_DIR', '../portfolio')
    docs_directory = os.path.join(portfolio_directory, 'docs')
    output_directory = os.environ.get('OUTPUT_DIR', './newsletters')
    
    logger.info(f"Recherche de fichiers Markdown récents dans {docs_directory}")
    logger.info(f"Répertoire de sortie: {output_directory}")
    
    # Copier toutes les images du dossier img du PORTFOLIO vers le dossier img de la newsletter
    # et vérifier si l'image d'en-tête existe
    header_image_exists = copy_images_to_newsletter(portfolio_directory, output_directory)
    
    # Récupérer les fichiers Markdown récents
    recent_files = get_recent_md_files(docs_directory)
    
    if recent_files:
        logger.info(f"Nombre de fichiers récents trouvés: {len(recent_files)}")
        for file in recent_files:
            logger.info(f"  - {file['filename']} (modifié le {file['modified_at']})")
    else:
        logger.warning("Aucun fichier récent trouvé")
    
    # Générer le contenu de la newsletter
    newsletter_content, projects = generate_newsletter_content(recent_files, portfolio_directory, output_directory)
    
    # Sauvegarder la newsletter au format Markdown
    md_path = save_newsletter(newsletter_content, output_directory)

    if md_path:
        # Générer une version HTML avec tout le contenu intégré dans un seul fichier
        newsletter_date = datetime.now().strftime("%d/%m/%Y")
        html_path = generate_single_file_html(projects, newsletter_date, output_directory, header_image_exists)
        
        if html_path:
            logger.info("Newsletter générée avec succès.")
            logger.info(f"Ouvrez {html_path} dans votre navigateur pour voir le résultat.")
        else:
            logger.error("Erreur lors de la génération de la version HTML.")
    
    logger.info("Génération de la newsletter terminée")

if __name__ == "__main__":
    main()