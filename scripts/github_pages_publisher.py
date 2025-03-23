import os
import subprocess
import shutil
import logging
from datetime import datetime
from pathlib import Path

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('github_pages_publisher')

class GithubPagesPublisher:
    def __init__(self, repository_url=None, branch="gh-pages"):
        """
        Initialise le publisher pour GitHub Pages.
        
        Args:
            repository_url (str): URL du dépôt GitHub à utiliser (par défaut: valeur de GITHUB_PAGES_REPO)
            branch (str): Branche à utiliser pour GitHub Pages (par défaut: gh-pages)
        """
        self.repository_url = repository_url or os.environ.get('GITHUB_PAGES_REPO')
        if not self.repository_url:
            raise ValueError("URL du dépôt GitHub non spécifiée")
        
        self.branch = branch
        self.temp_dir = Path("./.gh-pages-temp")
        
    def _run_command(self, command, cwd=None):
        """Exécute une commande shell et retourne le résultat."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                cwd=cwd
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
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
        if not os.path.exists(html_file_path):
            raise FileNotFoundError(f"Le fichier {html_file_path} n'existe pas")
        
        # Créer un nom de sortie si non spécifié
        if not output_name:
            # Déterminer si le fichier doit être l'index
            basename = os.path.basename(html_file_path)
            # Si c'est la newsletter la plus récente, utiliser index.html
            output_name = "index.html"
        
        # Créer ou nettoyer le répertoire temporaire
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Cloner le dépôt GitHub Pages
            logger.info(f"Clonage du dépôt {self.repository_url} (branche {self.branch})")
            self._run_command(
                f"git clone --depth 1 --branch {self.branch} {self.repository_url} .",
                cwd=self.temp_dir
            )
        except subprocess.CalledProcessError:
            # Si la branche n'existe pas, créer une nouvelle branche
            logger.info(f"Branche {self.branch} non trouvée, initialisation d'un nouveau dépôt")
            self._run_command("git init", cwd=self.temp_dir)
            self._run_command(f"git remote add origin {self.repository_url}", cwd=self.temp_dir)
            self._run_command(f"git checkout -b {self.branch}", cwd=self.temp_dir)
        
        # Copier les fichiers nécessaires
        # 1. Copier le fichier HTML principal
        dest_path = self.temp_dir / output_name
        shutil.copy2(html_file_path, dest_path)
        
        # 2. Copier les images et autres ressources
        img_src_dir = os.path.join(os.path.dirname(html_file_path), "img")
        img_dest_dir = self.temp_dir / "img"
        
        if os.path.exists(img_src_dir):
            # Créer le dossier img s'il n'existe pas
            img_dest_dir.mkdir(exist_ok=True)
            
            # Copier toutes les images
            for file in os.listdir(img_src_dir):
                src_file = os.path.join(img_src_dir, file)
                dest_file = img_dest_dir / file
                if os.path.isfile(src_file):
                    shutil.copy2(src_file, dest_file)
        
        # Créer un fichier CNAME si nécessaire (pour personnaliser le domaine)
        cname_domain = os.environ.get('GITHUB_PAGES_DOMAIN')
        if cname_domain:
            with open(self.temp_dir / "CNAME", "w") as f:
                f.write(cname_domain)
        
        # Ajouter les fichiers au dépôt Git
        logger.info("Ajout des fichiers au dépôt Git")
        self._run_command("git add .", cwd=self.temp_dir)
        
        # Créer un commit
        commit_message = f"Mise à jour de la newsletter - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        logger.info(f"Création d'un commit: {commit_message}")
        self._run_command(f'git commit -m "{commit_message}"', cwd=self.temp_dir)
        
        # Pousser les modifications
        logger.info(f"Publication sur la branche {self.branch}")
        self._run_command(f"git push -u origin {self.branch}", cwd=self.temp_dir)
        
        # Déterminer l'URL publique
        repo_parts = self.repository_url.split(":")[-1].split("/")
        if len(repo_parts) >= 2:
            username = repo_parts[-2].split(":")[-1]
            repo_name = repo_parts[-1].replace(".git", "")
            
            # Construire l'URL GitHub Pages
            if cname_domain:
                public_url = f"https://{cname_domain}"
            else:
                public_url = f"https://{username}.github.io/{repo_name}"
            
            logger.info(f"Newsletter publiée avec succès sur {public_url}")
            return public_url
        else:
            logger.warning("Impossible de déterminer l'URL publique")
            return None

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
