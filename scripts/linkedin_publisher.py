import requests
import json
import logging
import os
import hashlib
import pickle
from datetime import datetime
from pathlib import Path
import time

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('linkedin_publisher')

class LinkedInPublisher:
    def __init__(self, access_token=None):
        """
        Initialise la classe de publication LinkedIn.
        
        Args:
            access_token (str, optional): Token d'accès LinkedIn. 
                                          Si non fourni, tentera de le récupérer des variables d'environnement.
        """
        # Récupérer le token d'accès
        self.access_token = access_token or os.environ.get('DEPLOY_TOKEN')
        
        # Nettoyer et valider le token
        if self.access_token:
            self.access_token = self.access_token.strip()
            
        if not self.access_token:
            logger.error("Token d'accès LinkedIn non trouvé")
            raise ValueError("Token d'accès LinkedIn requis")
        
        # Récupérer l'ID de personne
        self.person_id = os.environ.get('LINKEDIN_PERSON_ID')
        
        # Nettoyer et valider l'ID de personne
        if self.person_id:
            self.person_id = self.person_id.strip()
            
        if not self.person_id:
            logger.error("ID de personne LinkedIn non trouvé")
            raise ValueError("ID de personne LinkedIn requis")
        
        # Gestion du cache des publications
        self.cache_dir = Path('./.linkedin_cache')
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / 'published_posts.pkl'
        
        # Charger les hachages des publications précédentes
        self.published_hashes = self._load_published_hashes()

    def _load_published_hashes(self):
        """
        Charge les hachages des publications précédentes depuis le fichier de cache.
        
        Returns:
            set: Ensemble des hachages de publications précédentes
        """
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"Erreur lors du chargement du cache: {e}")
                return set()
        return set()

    def _save_published_hash(self, content_hash):
        """
        Sauvegarde le hachage d'une publication dans le fichier de cache.
        
        Args:
            content_hash (str): Hachage du contenu de la publication
        """
        self.published_hashes.add(content_hash)
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.published_hashes, f)
        except Exception as e:
            logger.warning(f"Erreur lors de la sauvegarde du cache: {e}")

    def _generate_content_hash(self, text):
        """
        Génère un hachage unique pour le contenu de la publication.
        
        Args:
            text (str): Contenu textuel de la publication
        
        Returns:
            str: Hachage MD5 du contenu
        """
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def is_duplicate(self, text):
        """
        Vérifie si une publication est un doublon.
        
        Args:
            text (str): Contenu textuel de la publication
        
        Returns:
            bool: True si le contenu est un doublon, False sinon
        """
        content_hash = self._generate_content_hash(text)
        return content_hash in self.published_hashes

    def make_unique(self, text):
        """
        Rend le contenu unique en ajoutant un horodatage.
        
        Args:
            text (str): Contenu original de la publication
        
        Returns:
            str: Contenu modifié avec un horodatage
        """
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return f"{text}\n\nPublié le {timestamp}"

    def publish_text_post(self, text, public_url, force_unique=False):
        """
        Publie un post texte sur LinkedIn avec un lien vers une page web.
        
        Args:
            text (str): Le texte à publier
            public_url (str): URL publique de la newsletter
            force_unique (bool): Force l'ajout d'un horodatage pour rendre le contenu unique
        
        Returns:
            dict: Réponse de l'API LinkedIn ou None en cas d'échec
        """
        # Gestion du contenu dupliqué
        original_text = text
        
        if force_unique:
            text = self.make_unique(text)
        elif self.is_duplicate(text):
            logger.warning("Contenu en double détecté, ajout d'un horodatage")
            text = self.make_unique(text)
        
        # Configuration de l'API
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0'
        }
        
        # Préparer le corps de la requête
        post_data = {
            "author": f"urn:li:person:{self.person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "originalUrl": public_url,
                            "title": {
                                "text": "Newsletter Portfolio"
                            },
                            "description": {
                                "text": "Découvrez mes derniers projets et réalisations"
                            }
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        # Tentatives de publication avec gestion des erreurs
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                post_url = "https://api.linkedin.com/v2/ugcPosts"
                
                # Journalisation de la requête
                logger.debug(f"Envoi de la requête POST à {post_url}")
                
                # Envoi de la requête
                response = requests.post(post_url, headers=headers, json=post_data)
                
                # Gestion des différents codes de réponse
                if response.status_code == 201:
                    logger.info("Publication réussie sur LinkedIn")
                    
                    # Sauvegarder le hachage du contenu
                    content_hash = self._generate_content_hash(original_text)
                    self._save_published_hash(content_hash)
                    
                    return response.json()
                
                elif response.status_code == 429:  # Rate limit
                    retry_count += 1
                    wait_time = min(2 ** retry_count, 60)  # Exponential backoff
                    logger.warning(f"Rate limit atteint, nouvelle tentative dans {wait_time} secondes...")
                    time.sleep(wait_time)
                
                elif response.status_code == 422:  # Duplicate content
                    # Rendre le contenu unique et réessayer
                    text = self.make_unique(text + f" [{retry_count}]")
                    post_data['specificContent']['com.linkedin.ugc.ShareContent']['shareCommentary']['text'] = text
                    retry_count += 1
                    logger.warning(f"Contenu en double détecté, nouvelle tentative avec un texte modifié...")
                
                else:
                    logger.error(f"Échec de la publication LinkedIn: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"Erreur lors de la publication sur LinkedIn: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"Nouvelle tentative {retry_count}/{max_retries}...")
                    time.sleep(5)
                else:
                    return None
        
        logger.error(f"Échec après {max_retries} tentatives de publication")
        return None

def main():
    """
    Fonction principale pour générer et publier la newsletter sur LinkedIn.
    
    Returns:
        bool: True si la publication est réussie, False sinon
    """
    try:
        # Récupérer le répertoire des newsletters
        newsletters_dir = os.environ.get('NEWSLETTERS_DIR', './newsletters')
        
        # Recherche du fichier HTML le plus récent
        html_files = [f for f in os.listdir(newsletters_dir) if f.startswith('newsletter_') and f.endswith('.html')]
        
        if not html_files:
            logger.error("Aucun fichier HTML de newsletter trouvé")
            return False
        
        # Trier par date de modification (le plus récent en premier)
        latest_html = sorted(html_files, key=lambda f: os.path.getmtime(os.path.join(newsletters_dir, f)), reverse=True)[0]
        
        logger.info(f"Dernier fichier de newsletter trouvé: {latest_html}")
        
        # Vérifier s'il existe un fichier URL pour la dernière newsletter
        url_file_path = os.path.join(newsletters_dir, "latest_url.txt")
        public_url = None
        
        if os.path.exists(url_file_path):
            with open(url_file_path, "r") as f:
                public_url = f.read().strip()
                logger.info(f"URL publique trouvée: {public_url}")
        
        if not public_url:
            # Utiliser une URL par défaut si pas trouvée
            username = os.environ.get('GITHUB_USERNAME', 'SiaSia-dev')
            repo_name = os.environ.get('GITHUB_REPO', 'newsletter-portfolio')
            public_url = f"https://{username}.github.io/{repo_name}"
            logger.warning(f"Aucune URL trouvée, utilisation de l'URL par défaut: {public_url}")
        
        # Lire le contenu du fichier HTML
        try:
            from bs4 import BeautifulSoup
            
            with open(os.path.join(newsletters_dir, latest_html), 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extraire le titre et la date
            title = soup.find('h1').text.strip() if soup.find('h1') else "Newsletter Portfolio"
            date = soup.find('p', string=lambda s: '/' in s if s else False)
            date_text = date.text.strip() if date else datetime.now().strftime("%d/%m/%Y")
            
            # Extraire les titres des projets
            project_titles = (
                [h2.text.strip() for h2 in soup.find_all('h2', class_='project-title')] or
                [h2.text.strip() for h2 in soup.select('.project-card h2')] or
                [h2.text.strip() for h2 in soup.find_all('h2')][:5]  # Limiter aux 5 premiers
            )
            
            # Créer le contenu de la publication LinkedIn
            post_text = f"""🚀 {title} - {date_text} 🚀

Découvrez mes derniers projets et réalisations dans cette nouvelle édition de ma newsletter portfolio !

📌 Au sommaire:
"""
            # Ajouter les titres des projets
            for proj_title in project_titles:
                post_text += f"- {proj_title}\n"

            post_text += """
Consultez la version complète pour plus de détails sur chaque projet.

#portfolio #developpeur #tech #projets #newsletter"""
            
            # Créer l'instance LinkedIn Publisher et publier
            publisher = LinkedInPublisher()
            result = publisher.publish_text_post(post_text, public_url)
            
            if result:
                logger.info("Newsletter publiée avec succès sur LinkedIn")
                return True
            else:
                logger.error("Échec de la publication sur LinkedIn")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la préparation ou de la publication: {e}")
            return False
    
    except Exception as e:
        logger.error(f"Erreur générale: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1
    logger.info(f"Script terminé. Code de sortie: {exit_code}")
    exit(exit_code)
