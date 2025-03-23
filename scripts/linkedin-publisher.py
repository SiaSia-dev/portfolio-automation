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
            
            # Mettre à jour les tokens dans l'environnement GitHub
            if os.environ.get('GITHUB_ACTIONS') == 'true':
                # Dans GitHub Actions, nous mettons à jour les secrets
                # Cette partie nécessite une configuration supplémentaire (voir README)
                update_github_secrets(tokens)
            
            # Renvoyer le nouveau token d'accès
            logger.info("Token d'accès LinkedIn rafraîchi avec succès")
            return tokens['access_token']
        else:
            logger.error(f"Échec du rafraîchissement du token: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors du rafraîchissement du token: {str(e)}")
        return None

def update_github_secrets(tokens):
    """
    Met à jour les secrets GitHub pour les tokens LinkedIn
    
    Note: Cette fonction nécessite une configuration supplémentaire.
    Options alternatives:
    1. Utiliser une action GitHub qui peut mettre à jour les secrets
    2. Stocker les tokens dans un stockage externe sécurisé
    """
    # Exemple avec l'API GitHub
    try:
        import base64
        from nacl import encoding, public
        
        github_token = os.environ.get('GH_PAT')
        github_repo = os.environ.get('GITHUB_REPOSITORY')
        
        if not (github_token and github_repo):
            logger.error("Variables GitHub manquantes")
            return
        
        # Cette approche nécessite un token GitHub avec les droits appropriés
        # Code pour mettre à jour les secrets ici...
        logger.info("Les secrets GitHub doivent être mis à jour manuellement")
    except ImportError:
        logger.warning("Bibliothèques pour chiffrement manquantes")
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des secrets: {str(e)}")

def publish_to_linkedin(content):
    """Publie un contenu sur LinkedIn"""
    try:
        # Obtenir ou rafraîchir le token d'accès
        access_token = os.environ.get('LINKEDIN_ACCESS_TOKEN')
        if not access_token:
            logger.info("Token d'accès LinkedIn non trouvé, tentative de rafraîchissement")
            access_token = refresh_access_token()
            
        if not access_token:
            logger.error("Impossible d'obtenir un token d'accès LinkedIn valide")
            return False
        
        # ID de personne LinkedIn (à configurer)
        person_id = os.environ.get('LINKEDIN_PERSON_ID')
        if not person_id:
            logger.error("Variable d'environnement LINKEDIN_PERSON_ID manquante")
            return False
        
        url = "https://api.linkedin.com/v2/ugcPosts"
        
        # Formater la requête pour LinkedIn
        payload = {
            "author": f"urn:li:person:{person_id}",
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
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code in (200, 201):
            logger.info("Publication LinkedIn réussie")
            return True
        elif response.status_code == 401:
            # Token expiré, tenter de rafraîchir et réessayer
            logger.info("Token expiré, tentative de rafraîchissement")
            new_token = refresh_access_token()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                retry_response = requests.post(url, json=payload, headers=headers)
                if retry_response.status_code in (200, 201):
                    logger.info("Publication LinkedIn réussie après rafraîchissement du token")
                    return True
            
            logger.error("Échec de la publication après rafraîchissement du token")
            return False
        else:
            logger.error(f"Échec de la publication LinkedIn: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Erreur lors de la publication sur LinkedIn: {str(e)}")
        return False

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
        
        # Ajouter un lien vers la version complète (à adapter selon votre setup)
        linkedin_content += "\nConsultez la version complète sur mon portfolio: https://votre-portfolio.com/newsletters"
        
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
