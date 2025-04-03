#!/bin/bash
# Script avancé pour gérer les opérations Git dans les workflows GitHub Actions

# Options de sécurité et de débogage
set -euo pipefail  # Options de shell plus strictes
LOG_FILE="git-operations.log"

# Fonction de logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Gestion des erreurs
error_handler() {
    log "ERREUR: Une erreur est survenue à la ligne $1"
    exit 1
}

# Trap pour capturer les erreurs
trap 'error_handler $LINENO' ERR

# Vérifier le nombre d'arguments
if [ $# -lt 3 ]; then
    log "ERREUR: Utilisation: $0 <chemin_repo> <message_commit> <branche> [<dossier_specifique>]"
    exit 1
fi

# Récupérer les arguments
REPO_PATH=$(realpath "$1")  # Chemin absolu
COMMIT_MESSAGE="$2"
BRANCH="$3"
SPECIFIC_FOLDER="${4:-.}"  # Dossier spécifique ou dossier courant par défaut

# Vérification des paramètres
if [ ! -d "$REPO_PATH" ]; then
    log "ERREUR: Le chemin du dépôt $REPO_PATH n'existe pas"
    exit 1
fi

# Aller dans le répertoire du dépôt
cd "$REPO_PATH" || exit 1

# Configurer Git
git config user.name "GitHub Actions"
git config user.email "github-actions@github.com"

# Vérifier s'il y a des changements dans le dossier spécifique
cd "$SPECIFIC_FOLDER"
CHANGES=$(git status --porcelain)

if [ -n "$CHANGES" ]; then
    log "Changements détectés dans $SPECIFIC_FOLDER"
    
    # Afficher les changements
    log "Détails des changements :"
    echo "$CHANGES"
    
    # Ajouter, committer et pousser
    git add .
    git commit -m "$COMMIT_MESSAGE"
    git push origin "$BRANCH"
    
    log "Changements commités et poussés vers $BRANCH"
else
    log "Aucun changement à committer dans $SPECIFIC_FOLDER"
fi

# Confirmation finale
log "Opération Git terminée avec succès"