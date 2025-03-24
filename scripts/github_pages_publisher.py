import os
import subprocess
import shutil
import logging
from datetime import datetime
from pathlib import Path
import time
import random
import string

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('github_pages_publisher')

class GithubPagesPublisher:
    def __init__(self, repository_url=None, branch="gh-pages", access_token=None):
    """
    Initialise le publisher pour GitHub Pages.
    
    Args:
        repository_url (str, optional): URL du dépôt à utiliser
        branch (str, optional): Branche à utiliser pour GitHub Pages
        access_token (str, optional): Token d'accès GitHub
    """
    # Utiliser explicitement l'URL du dépôt newsletter-portfolio
    self.repository_url = repository_url or "https://github.com/SiaSia-dev/newsletter-portfolio.git"
    
    self.branch = branch
    
    # Récupérer le token d'accès
    self.access_token = access_token or os.environ.get('GITHUB_TOKEN') or os.environ.get('DEPLOY_TOKEN')
    
    if not self.access_token:
        logger.error("Aucun token d'accès GitHub trouvé")
        raise ValueError("Token d'accès GitHub requis")

    # Générer un nom de dossier temporaire unique pour éviter les conflits
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    self.temp_dir = Path(f"./gh_pages_temp_{random_suffix}")
        
    def _run_command(self, command, cwd=None, ignore_errors=False):
        """Exécute une commande shell et retourne le résultat."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=not ignore_errors,
                capture_output=True,
                text=True,
                cwd=cwd
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if ignore_errors:
                logger.warning(f"Commande échouée (ignorée): {e}")
                logger.warning(f"Sortie d'erreur: {e.stderr}")
                return None
            else:
                logger.error(f"Erreur lors de l'exécution de la commande: {e}")
                logger.error(f"Sortie d'erreur: {e.stderr}")
                raise
            
    def publish_newsletter(self, html_file_path, output_name=None):
        """
        Publie un fichier HTML de newsletter sur GitHub Pages.
        
        Args:
            html_file_path (str): Chemin vers le fichier HTML de la newsletter
            output_name (str, optional): Nom du fichier de sortie (index.html par défaut)
            
        Returns:
            str: URL publique de la newsletter publiée
        """
        # URL publique par défaut
        public_url = "https://SiaSia-dev.github.io/newsletter-portfolio"
        
        # Vérifier l'existence du fichier
        if not os.path.exists(html_file_path):
            logger.error(f"Le fichier {html_file_path} n'existe pas")
            return public_url
        
        # Nom de sortie par défaut
        output_name = output_name or "index.html"
        
        # Créer un répertoire temporaire unique
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_dir = Path(f"./gh_pages_temp_{timestamp}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Configuration des commandes Git
            git_commands = [
                # Initialisation du dépôt
                ["git", "init"],
                
                # Configuration de l'identité Git
                ["git", "config", "user.name", "Newsletter Publisher"],
                ["git", "config", "user.email", "newsletter@example.com"],
                
                # Ajout du dépôt distant avec authentification
                ["git", "remote", "add", "origin", 
                f"https://{self.access_token}@github.com/SiaSia-dev/newsletter-portfolio.git"],
                
                # Récupération de la branche gh-pages
                ["git", "fetch", "origin", "gh-pages"],
                ["git", "checkout", "gh-pages"]
            ]
            
            # Exécution des commandes Git
            for cmd in git_commands:
                try:
                    subprocess.run(cmd, cwd=temp_dir, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Erreur Git: {cmd[0]} - {e.stderr}")
                    raise
            
            # Copie du fichier HTML
            dest_path = temp_dir / output_name
            shutil.copy2(html_file_path, dest_path)
            
            # Gestion des images
            img_src_dir = os.path.join(os.path.dirname(html_file_path), "img")
            img_dest_dir = temp_dir / "img"
            
            if os.path.exists(img_src_dir):
                img_dest_dir.mkdir(exist_ok=True)
                
                # Copier toutes les images
                for file in os.listdir(img_src_dir):
                    src_file = os.path.join(img_src_dir, file)
                    dest_file = img_dest_dir / file
                    if os.path.isfile(src_file):
                        shutil.copy2(src_file, dest_file)
            
            # Ajout, commit et push
            additional_commands = [
                ["git", "add", "."],
                ["git", "commit", "-m", f"Mise à jour de la newsletter - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"],
                ["git", "push", "-f", "origin", "gh-pages"]
            ]
            
            for cmd in additional_commands:
                try:
                    result = subprocess.run(cmd, cwd=temp_dir, check=True, capture_output=True, text=True)
                    logger.info(f"Commande réussie: {' '.join(cmd)}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Erreur lors de l'exécution de {' '.join(cmd)}: {e.stderr}")
                    raise
            
            logger.info(f"Newsletter publiée avec succès sur {public_url}")
            return public_url
        
        except Exception as e:
            logger.error(f"Erreur lors de la publication : {e}")
            return public_url
        
        finally:
            # Nettoyage du dossier temporaire
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Impossible de supprimer le dossier temporaire: {e}")

def main():
    try:
        # Récupérer le dernier fichier de newsletter
        newsletters_dir = os.environ.get('NEWSLETTERS_DIR', './newsletters')
        
        # Recherche du fichier HTML le plus récent
        html_files = [f for f in os.listdir(newsletters_dir) if f.endswith('.html')]
        
        if not html_files:
            logger.error("Aucun fichier HTML de newsletter trouvé")
            return False
        
        # Trier par date de modification (le plus récent en premier)
        html_files.sort(key=lambda f: os.path.getmtime(os.path.join(newsletters_dir, f)), reverse=True)
        latest_html = html_files[0]
        
        logger.info(f"Dernier fichier de newsletter trouvé: {latest_html}")
        
        # Chemin complet vers le fichier HTML
        html_file_path = os.path.join(newsletters_dir, latest_html)
        
        # Publier sur GitHub Pages
        publisher = GithubPagesPublisher()
        public_url = publisher.publish_newsletter(html_file_path)
        
        if public_url:
            logger.info(f"URL de la newsletter: {public_url}")
            
            # Créer un fichier avec l'URL pour utilisation par d'autres scripts
            url_file_path = os.path.join(newsletters_dir, "latest_url.txt")
            with open(url_file_path, "w") as f:
                f.write(public_url)
            
            return True
        else:
            logger.error("Échec de la publication sur GitHub Pages")
            return False
    
    except Exception as e:
        logger.error(f"Erreur lors de la publication sur GitHub Pages: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        logger.error("Le script s'est terminé avec des erreurs")
    else:
        logger.info("Publication GitHub Pages terminée avec succès")