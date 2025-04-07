#!/bin/bash
# Script pour gérer les opérations Git dans les workflows GitHub Actions

set -e  # Arrêter en cas d'erreur

# Récupérer les arguments
REPO_PATH=$1
COMMIT_MESSAGE=$2
BRANCH=$3

# Aller dans le répertoire du dépôt
cd "$REPO_PATH" || exit 1

# Configurer Git
git config user.name "GitHub Actions"
git config user.email "github-actions@github.com"

# Vérifier s'il y a des changements
if git status --porcelain | grep -q .; then
    # Il y a des changements à committer
    git add .
    git commit -m "$COMMIT_MESSAGE"
    git push origin "$BRANCH"
    echo "Changements commités et poussés vers $BRANCH"
else
    echo "Aucun changement à committer dans $REPO_PATH"
fi