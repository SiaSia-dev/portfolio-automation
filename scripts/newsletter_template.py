import os
import re
import markdown
from bs4 import BeautifulSoup
from datetime import datetime
import shutil
from pathlib import Path
import logging

# Configurer le logging
logger = logging.getLogger(__name__)

def load_html_template(template_path):
    """
    Charge un template HTML depuis un fichier.
    """
    try:
        logger.info(f"Chargement du template depuis: {template_path}")
        if not os.path.exists(template_path):
            logger.warning(f"Le fichier template n'existe pas: {template_path}")
            return ""
            
        with open(template_path, 'r', encoding='utf-8') as file:
            content = file.read()
            logger.info(f"Template chargé avec succès: {len(content)} caractères")
            return content
    except Exception as e:
        logger.error(f"Erreur lors du chargement du template HTML {template_path}: {e}")
        return ""

def generate_project_html(project):
    """
    Génère le HTML pour un projet individuel.
    """
    # Générer les tags
    tags_html = ""
    if project['tags']:
        tags_html = '<div class="tags">'
        for tag in project['tags']:
            tags_html += f'<span class="tag">{tag}</span>'
        tags_html += '</div>'
    
    # Convertir le contenu markdown en HTML
    html_content = markdown.markdown(project['content'])
    
    # Nettoyer le HTML pour un résumé
    soup = BeautifulSoup(html_content, 'html.parser')
    clean_text = soup.get_text(separator=' ', strip=True)
    
    # Limiter le contenu pour l'aperçu
    summary = clean_text[:250] + "..." if len(clean_text) > 250 else clean_text
    
    # Générer le HTML pour le projet
    project_html = f"""
    <div id="{project['id']}" class="project-full-content">
        <h2>{project['title']}</h2>
        
        <img class="hero-image" src="{project['image']}" alt="{project['title']}" loading="lazy">
        
        {html_content}
        
        {tags_html}
        
        <a href="#" class="btn back-to-top">Retour en haut</a>
    </div>
    """
    
    return project_html, summary

def generate_newsletter_template(projects, display_date, header_image_exists=False):
    """
    Génère le template HTML complet pour la newsletter en utilisant le fichier template.
    """
    # Chemin vers le template - ajustez selon votre structure de projet
    template_path = os.path.join(os.getcwd(), 'newsletter_template.html')
    
    # Charger le template
    template_html = load_html_template(template_path)
    if not template_html:
        logger.error("Impossible de charger le template HTML, génération abandonnée")
        return ""
    
    # Générer le contenu HTML pour chaque projet
    projects_detail_html = ""
    projects_grid_html = ""
    toc_items = ""
    
    for project in projects:
        # Générer le HTML pour le projet détaillé
        project_detail_html, summary = generate_project_html(project)
        projects_detail_html += project_detail_html
        
        # Générer la carte du projet pour la grille
        tags_html = ""
        if project['tags']:
            tags_html = '<div class="tags">'
            for tag in project['tags']:
                tags_html += f'<span class="tag">{tag}</span>'
            tags_html += '</div>'
        
        projects_grid_html += f"""
        <div class="project-card">
            <div class="project-image-container">
                <img class="project-image" src="{project['image']}" alt="{project['title']}" loading="lazy">
            </div>
            <div class="project-content">
                <h2 class="project-title">{project['title']}</h2>
                <div class="project-description">{project['description']}</div>
                <div class="project-summary">{summary}</div>
                {tags_html}
                <a href="#{project['id']}" class="btn">En savoir plus</a>
            </div>
        </div>
        """
        
        # Générer les items de la table des matières
        toc_items += f'<li class="toc-item"><a href="#{project["id"]}">{project["title"]}</a></li>'
    
    # Générer l'en-tête
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
    
    # Préparer le contenu complet de la newsletter
    newsletter_content = f"""
        {header_html}
        
        <div class="grid">
            {projects_grid_html}
        </div>
        
        {projects_detail_html}
    """
    
    # Remplacer les variables dans le template
    html_content = template_html.replace("{display_date}", display_date)
    html_content = html_content.replace("{newsletter_content}", newsletter_content)
    html_content = html_content.replace("{toc_items}", toc_items)
    html_content = html_content.replace("{current_year}", str(datetime.now().year))
    
    return html_content

def generate_index_template(latest_newsletter):
    """
    Génère le contenu du fichier index.html qui redirige vers la dernière newsletter.
    """
    template_path = os.path.join(os.getcwd(), 'index_template.html')
    
    # Essayer de charger le template personnalisé
    template_html = load_html_template(template_path)
    
    # Si le template personnalisé n'existe pas, utiliser un template par défaut
    if not template_html:
        template_html = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0;url={latest_newsletter}">
    <title>Newsletter Portfolio</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            text-align: center; 
            padding: 50px; 
            background-color: #f4f4f4; 
        }
        p { 
            color: #333; 
            font-size: 18px; 
        }
        a { 
            color: #4a6d8c; 
            text-decoration: none; 
        }
        a:hover { 
            text-decoration: underline; 
        }
    </style>
</head>
<body>
    <p>Redirection vers la dernière newsletter...</p>
    <p>Si la redirection automatique ne fonctionne pas, 
    <a href="{latest_newsletter}">cliquez ici</a>.</p>
</body>
</html>"""
    
    # Remplacer la variable
    return template_html.replace("{latest_newsletter}", latest_newsletter)

def generate_latest_template(latest_newsletter_path):
    """
    Copie du fichier de la dernière newsletter vers latest.html
    Retourne le contenu du fichier.
    """
    try:
        with open(latest_newsletter_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Erreur lors de la lecture de la dernière newsletter : {e}")
        return ""

def generate_archives_template(output_directory):
    """
    Génère le template HTML pour la page des archives.
    """
    # Chemin vers le template des archives
    template_path = os.path.join(os.getcwd(), 'archive_template.html')  # Changé de archives_template.html à archive_template.html
    
    # Essayer de charger le template personnalisé
    template_html = load_html_template(template_path)
    
    # Si aucun template personnalisé n'est trouvé, utiliser un template par défaut
    if not template_html:
        logger.warning("Template d'archives non trouvé, utilisation du template par défaut")
        # Gardez votre template par défaut mais assurez-vous qu'il contient un footer
        template_html = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archives - Récits visuels, horizons numériques</title>
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
        }
        
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 40px 20px;
            background-color: white;
            box-shadow: var(--shadow);
            border-radius: var(--radius);
        }
        
        h1 { 
            color: var(--secondary);
            margin-bottom: 30px;
            font-size: 2rem;
        }
        
        .tabs {
            display: flex;
            border-bottom: 2px solid var(--accent);
            margin-bottom: 30px;
        }
        
        .tab {
            padding: 15px 25px;
            cursor: pointer;
            font-weight: 500;
            color: var(--primary);
            transition: all 0.3s ease;
            border-bottom: 3px solid transparent;
        }
        
        .tab:hover {
            color: var(--secondary);
        }
        
        .tab.active {
            color: var(--secondary);
            border-bottom-color: var(--secondary);
        }
        
        ul { 
            list-style-type: none; 
            padding: 0; 
        }
        
        li { 
            margin-bottom: 15px; 
            padding: 15px; 
            background-color: var(--light);
            border-radius: var(--radius);
            transition: background-color 0.3s ease;
        }
        
        li:hover { 
            background-color: #e6edf3; 
        }
        
        a { 
            text-decoration: none; 
            color: var(--primary); 
            font-weight: 500;
            transition: color 0.3s ease;
        }
        
        a:hover { 
            color: var(--secondary); 
            text-decoration: underline; 
        }
        
        .back-link {
            display: inline-block;
            margin-top: 30px;
            padding: 10px 20px;
            background-color: var(--primary);
            color: white;
            border-radius: 25px;
            font-weight: 500;
            transition: all 0.3s ease;
            text-decoration: none;
        }
        
        .back-link:hover {
            background-color: var(--secondary);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
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
    </style>
</head>
<body>
    <div class="container">
        <div class="tabs">
            <div class="tab" onclick="window.location.href='latest.html'">Newsletter</div>
            <div class="tab active">Archives</div>
        </div>
        
        <h1>Archives des newsletters</h1>
        <ul>
            {archives_items}
        </ul>
        
        <a href="latest.html" class="back-link">Retour à la dernière newsletter</a>
        
        <div class="footer">
            <h2>Restons connectés !</h2>
            <p>N'hésitez pas à me contacter pour discuter de projets ou simplement échanger sur nos domaines d'intérêt communs.</p>
            
            <div class="social-links">
                <a href="https://portfolio-af-v2.netlify.app/" class="social-link" target="_blank" rel="noopener">Portfolio</a>
                <a href="https://www.linkedin.com/in/alexiafontaine" class="social-link" target="_blank" rel="noopener">LinkedIn</a>
            </div>
            
            <div class="copyright">
                <p>© {current_year} - Newsletter générée automatiquement depuis mon portfolio GitHub - Alexia Fontaine tous drois réservés</p>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    # Trouver tous les fichiers HTML de newsletter
    html_files = [f for f in os.listdir(output_directory) if f.startswith('newsletter_') and f.endswith('.html')]
    
    # Trier les fichiers par date (du plus récent au plus ancien)
    sorted_files = sorted(html_files, key=lambda f: os.path.getmtime(os.path.join(output_directory, f)), reverse=True)
    
    # Générer la liste des archives
    archives_items = ""
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
            
            archives_items += f'        <li><a href="{file}">Newsletter du {formatted_date}</a></li>\n'
    
    # Remplacer les variables dans le template
    html_content = template_html.replace("{archives_items}", archives_items)
    html_content = html_content.replace("{current_year}", str(datetime.now().year))
    
    logger.info(f"Archives générées avec {len(sorted_files)} newsletters")
    
    return html_content

def create_index_and_archives(output_directory, file_date, display_date):
    """
    Crée les fichiers index.html, latest.html et archives.html.
    Ajoute la génération d'une copie datée de latest.html.
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
            
            # NOUVEAU : Créer une copie datée de latest.html
            dated_file = f"newsletter_{file_date}.html"
            dated_path = os.path.join(output_directory, dated_file)
            
            # Copier latest.html vers le fichier daté
            import shutil
            shutil.copy(latest_path, dated_path)
            logger.info(f"Création du fichier daté : {dated_path}")
            
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