import os
import json
import requests
import logging
from datetime import datetime, timedelta
import base64

# Configuration du logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('linkedin_publisher')

# Configuration des chemins
TOKENS_FILE = "linkedin_tokens.json"
NEWSLETTER_DIR = "./newsletters"

def get_latest_newsletter():
    """Récupère le chemin du fichier de newsletter le plus récent"""
    try:
        files = [f for f in os.listdir(NEWSLETTER_DIR) if f.endswith('.md')]
        if not files:
            logger.warning(f"Aucun fichier de newsletter trouvé dans {NEWSLETTER_DIR}")
            return None
        
        # Trier par date de modification (plus récent d'abord)
        latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(NEWSLETTER_DIR, f)))
        return os.path.join(NEWSLETTER_DIR, latest_file)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de la newsletter: {str(e)}")
        return None

def refresh_access_token():
    """Rafraîchit le token d'accès LinkedIn en utilisant le refresh token"""
    try:
        client_id = os.environ.get('LINKEDIN_CLIENT_ID')
        client_secret = os.environ.get('LINKEDIN_CLIENT_SECRET')
        refresh_token = os.environ.get('LINKEDIN_REFRESH_TOKEN')
        
        if not (client_id and client_secret and refresh_token):
            logger.error("Variables d'environnement manquantes (LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_REFRESH_TOKEN)")
            return None
        
        # Créer l'authentification Basic pour l'en-tête
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        
        headers = {
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        response = requests.post('https://www.linkedin.com/oauth/v2/accessToken', 
                                headers=headers, 
                                data=data)
        
        if response.status_code == 200:
            tokens = response.json()
            logger.info("Token d'accès LinkedIn rafraîchi avec succès")
            return tokens['access_token']
        else:
            logger.error(f"Échec du rafraîchissement du token: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors du rafraîchissement du token: {str(e)}")
        return None

def publish_to_linkedin(content):
    # ...code existant...
    
    # ID de personne LinkedIn (au lieu de l'ID d'entreprise)
    person_id = os.environ.get('LINKEDIN_PERSON_ID')
    if not person_id:
        logger.error("Variable d'environnement LINKEDIN_PERSON_ID manquante")
        return False
    
    url = "https://api.linkedin.com/v2/ugcPosts"
    
    # Formater la requête pour LinkedIn avec le profil personnel comme auteur
    payload = {
        "author": f"urn:li:person:{LINKEDIN_PERSON_ID}",  # Utiliser l'ID personnel au lieu de l'organisation
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": content
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    

def prepare_linkedin_content(newsletter_path):
    """Prépare le contenu pour LinkedIn à partir de la newsletter"""
    try:
        if not newsletter_path or not os.path.exists(newsletter_path):
            logger.error(f"Fichier de newsletter non trouvé: {newsletter_path}")
            return None
        
        with open(newsletter_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extraire le titre et les premières lignes
        lines = content.split('\n')
        title = lines[0].replace('# ', '') if lines and lines[0].startswith('# ') else "Newsletter Portfolio"
        
        # Préparer un contenu attrayant pour LinkedIn
        linkedin_content = f"🔥 {title} 🔥\n\n"
        linkedin_content += "Découvrez mes derniers projets et réalisations cette semaine !\n\n"
        
        # Ajouter un aperçu des projets (extraire les titres de second niveau)
        projects = []
        for line in lines:
            if line.startswith('## '):
                projects.append(line.replace('## ', ''))
        
        if projects:
            linkedin_content += "Projets inclus dans cette édition:\n"
            for i, project in enumerate(projects[:3], 1):
                linkedin_content += f"{i}. {project}\n"
            
            if len(projects) > 3:
                linkedin_content += f"...et {len(projects) - 3} autres projets\n"
        
        # Ajouter un lien vers la page LinkedIn
        linkedin_content += "\nRetrouvez toutes mes newsletters sur LinkedIn: https://www.linkedin.com/company/www-linkedin-com-in-alexiafontaine"
        
        # Limiter à la limite de caractères de LinkedIn
        max_length = 3000
        if len(linkedin_content) > max_length:
            linkedin_content = linkedin_content[:max_length-3] + "..."
        
        return linkedin_content
    except Exception as e:
        logger.error(f"Erreur lors de la préparation du contenu: {str(e)}")
        return None

def main():
    """Fonction principale"""
    try:
        # Récupérer le chemin de la dernière newsletter
        newsletter_path = get_latest_newsletter()
        if not newsletter_path:
            logger.error("Aucune newsletter trouvée pour publication")
            return 1
        
        # Préparer le contenu pour LinkedIn
        linkedin_content = prepare_linkedin_content(newsletter_path)
        if not linkedin_content:
            logger.error("Impossible de préparer le contenu pour LinkedIn")
            return 1
        
        # Publier sur LinkedIn
        success = publish_to_linkedin(linkedin_content)
        if success:
            logger.info("Publication LinkedIn réussie")
            return 0
        else:
            logger.error("Échec de la publication sur LinkedIn")
            return 1
    except Exception as e:
        logger.error(f"Erreur dans la fonction principale: {str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)