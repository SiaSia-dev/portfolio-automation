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
        Publie un fichier HTML de newsletter sur GitHub Pages en utilisant le dépôt local déjà cloné.
        
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
        
        try:
            # Utiliser directement le dépôt local
            repo_dir = "./newsletter-portfolio"
            
            logger.info(f"Utilisation du dépôt local : {repo_dir}")
            
            # Vérifier l'existence du dépôt local
            if not os.path.exists(repo_dir):
                logger.error(f"Le dépôt local {repo_dir} n'existe pas")
                return public_url
                
            # Configurer l'identité Git
            self._run_git_command(["git", "config", "user.name", "Newsletter Publisher"], cwd=repo_dir)
            self._run_git_command(["git", "config", "user.email", "newsletter@example.com"], cwd=repo_dir)
            
            # S'assurer que nous sommes sur la bonne branche
            self._run_git_command(["git", "checkout", "gh-pages"], cwd=repo_dir)
            
            logger.info("Vérification des fichiers à publier...")
            
            # Lister les fichiers dans le dépôt
            newsletters_dir = os.path.join(repo_dir, "newsletters")
            if os.path.exists(newsletters_dir):
                all_files = os.listdir(newsletters_dir)
                logger.info(f"Fichiers existants dans {newsletters_dir}: {all_files}")
            else:
                logger.warning(f"Le dossier {newsletters_dir} n'existe pas dans le dépôt")
            
            # Ajouter tous les fichiers
            self._run_git_command(["git", "add", "."], cwd=repo_dir)
            
            # Vérifier s'il y a des modifications à committer
            status_result = self._run_git_command(["git", "status", "--porcelain"], cwd=repo_dir)
            
            if status_result.stdout.strip():
                # Il y a des modifications, on les commit et les push
                commit_message = f"Mise à jour de la newsletter - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                self._run_git_command(["git", "commit", "-m", commit_message], cwd=repo_dir)
                
                # Push des modifications
                push_command = ["git", "push", "origin", "gh-pages"]
                self._run_git_command(push_command, cwd=repo_dir)
                
                logger.info(f"Newsletter publiée avec succès sur {public_url}")
            else:
                logger.info("Aucune modification à publier")
            
            return public_url
            
        except Exception as e:
            logger.error(f"Erreur lors de la publication : {e}")
            return public_url

def main():
    """
    Fonction principale pour publier la newsletter.
    """
    try:
        # Récupérer le répertoire des newsletters
        # Utiliser le dossier des newsletters dans le dépôt newsletter-portfolio
        newsletters_dir = os.environ.get('NEWSLETTERS_DIR', './newsletter-portfolio/newsletters')
        
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