import os
import subprocess
import shutil
import logging
from datetime import datetime
from pathlib import Path
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
        # URL du dépôt
        self.repository_url = repository_url or "https://github.com/SiaSia-dev/newsletter-portfolio.git"
        
        # Branche de déploiement
        self.branch = branch
        
        # Récupérer le token d'accès
        self.access_token = access_token or os.environ.get('GITHUB_TOKEN') or os.environ.get('DEPLOY_TOKEN')
        
        if not self.access_token:
            logger.error("Aucun token d'accès GitHub trouvé")
            raise ValueError("Token d'accès GitHub requis")
        
        # Générer un nom de dossier temporaire unique
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.temp_dir = Path(f"./gh_pages_temp_{random_suffix}")

    def _run_git_command(self, command, cwd=None, capture_output=True):
        """
        Exécute une commande Git avec gestion des erreurs.
        
        Args:
            command (list): Commande Git à exécuter
            cwd (Path, optional): Répertoire de travail
            capture_output (bool, optional): Capture la sortie standard
        
        Returns:
            subprocess.CompletedProcess: Résultat de la commande
        """
        try:
            result = subprocess.run(
                command, 
                cwd=cwd, 
                check=True, 
                capture_output=capture_output, 
                text=True
            )
            logger.info(f"Commande Git réussie : {' '.join(command)}")
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur Git : {' '.join(command)}")
            logger.error(f"Sortie d'erreur : {e.stderr}")
            raise

    def publish_newsletter(self, html_file_path, output_name=None):
        """
        Publie un fichier HTML de newsletter sur GitHub Pages.
        
        Args:
            html_file_path (str): Chemin vers le fichier HTML de la newsletter
            output_name (str, optional): Nom du fichier de sortie
        
        Returns:
            str: URL publique de la newsletter
        """
        # URL publique par défaut
        public_url = "https://SiaSia-dev.github.io/newsletter-portfolio"
        
        # Vérifier l'existence du fichier
        if not os.path.exists(html_file_path):
            logger.error(f"Fichier non trouvé : {html_file_path}")
            return public_url
        
        # Nom de sortie par défaut
        output_name = output_name or "index.html"
        
        # Créer le répertoire temporaire
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Séquence de commandes Git
            git_commands = [
                # Initialiser le dépôt
                ["git", "init"],
                
                # Configurer l'identité Git
                ["git", "config", "user.name", "Newsletter Publisher"],
                ["git", "config", "user.email", "newsletter@example.com"],
                
                # Ajouter le dépôt distant avec authentification
                ["git", "remote", "add", "origin", 
                 f"https://{self.access_token}@github.com/SiaSia-dev/newsletter-portfolio.git"],
                
                # Récupérer la branche gh-pages
                ["git", "fetch", "origin", "gh-pages"],
                ["git", "checkout", "gh-pages"]
            ]
            
            # Exécuter les commandes Git
            for cmd in git_commands:
                self._run_git_command(cmd, cwd=self.temp_dir)
            
            # Copier le fichier HTML
            dest_path = self.temp_dir / output_name
            shutil.copy2(html_file_path, dest_path)
            
            # Gérer les images
            img_src_dir = os.path.join(os.path.dirname(html_file_path), "img")
            img_dest_dir = self.temp_dir / "img"
            
            if os.path.exists(img_src_dir):
                img_dest_dir.mkdir(exist_ok=True)
                
                # Copier toutes les images
                for file in os.listdir(img_src_dir):
                    src_file = os.path.join(img_src_dir, file)
                    dest_file = img_dest_dir / file
                    if os.path.isfile(src_file):
                        shutil.copy2(src_file, dest_file)
            
            # Commandes Git finales
            final_commands = [
                ["git", "add", "."],
                ["git", "commit", "-m", f"Mise à jour de la newsletter - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"],
                ["git", "push", "-f", "origin", "gh-pages"]
            ]
            
            # Exécuter les commandes finales
            for cmd in final_commands:
                self._run_git_command(cmd, cwd=self.temp_dir)
            
            logger.info(f"Newsletter publiée avec succès sur {public_url}")
            return public_url
        
        except Exception as e:
            logger.error(f"Erreur lors de la publication : {e}")
            return public_url
        
        finally:
            # Nettoyer le dossier temporaire
            try:
                if self.temp_dir.exists():
                    shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.warning(f"Impossible de supprimer le dossier temporaire : {e}")

def main():
    """
    Fonction principale pour publier la newsletter.
    """
    try:
        # Récupérer le répertoire des newsletters
        newsletters_dir = os.environ.get('NEWSLETTERS_DIR', './newsletters')
        
        # Message de débogage
        logger.info(f"Recherche de fichiers HTML dans le répertoire: {newsletters_dir}")
        
        # Vérifier si le répertoire existe
        if not os.path.exists(newsletters_dir):
            logger.error(f"Le répertoire {newsletters_dir} n'existe pas")
            return False
        
        # Lister tous les fichiers dans le répertoire
        all_files = os.listdir(newsletters_dir)
        logger.info(f"Fichiers trouvés dans le répertoire : {all_files}")
        
        # Trouver les fichiers HTML
        html_files = [f for f in all_files if f.endswith('.html')]
        
        if not html_files:
            logger.error("Aucun fichier HTML de newsletter trouvé")
            return False
        
        # Trier par date de modification
        latest_html = sorted(
            html_files, 
            key=lambda f: os.path.getmtime(os.path.join(newsletters_dir, f)), 
            reverse=True
        )[0]
        
        # Chemin complet du fichier
        html_file_path = os.path.join(newsletters_dir, latest_html)
        logger.info(f"Fichier HTML sélectionné : {html_file_path}")
        
        # Publier la newsletter
        publisher = GithubPagesPublisher()
        public_url = publisher.publish_newsletter(html_file_path)
        
        logger.info(f"URL de la newsletter : {public_url}")
        return True
    
    except Exception as e:
        logger.error(f"Erreur lors de la publication : {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1
    exit(exit_code)