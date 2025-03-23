# Configuration de l'intégration LinkedIn

Ce document explique comment configurer l'intégration avec LinkedIn pour publier automatiquement vos newsletters.

## 1. Créer une application LinkedIn Developer

1. Rendez-vous sur [LinkedIn Developer Portal](https://www.linkedin.com/developers/)
2. Connectez-vous à votre compte LinkedIn
3. Cliquez sur "Create app" (Créer une application)
4. Remplissez les informations requises:
   - Nom de l'application: "Portfolio Newsletter Publisher"
   - URL de votre site web/GitHub: URL de votre portfolio
   - Logo de l'application (optionnel)
   - Description: "Application pour publier automatiquement les mises à jour de mon portfolio"
5. Acceptez les conditions d'utilisation
6. Soumettez la demande de création d'application

## 2. Configurer les permissions de l'application

Une fois votre application créée:
1. Allez dans l'onglet "Auth" (Authentification)
2. Ajoutez les permissions (scopes) suivantes:
   - `r_liteprofile` - pour accéder à votre profil
   - `r_emailaddress` - pour accéder à votre email
   - `w_member_social` - pour publier du contenu
3. Dans "OAuth 2.0 settings", ajoutez l'URL de redirection:
   - `http://localhost:8000/callback`

## 3. Obtenir le token initial et le refresh token

Pour obtenir les tokens initiaux, suivez ces étapes:

### 3.1 Créer un script d'authentification

Créez un fichier `get_linkedin_token.py` avec le contenu suivant:

```python
import requests
import webbrowser
import http.server
import socketserver
import urllib.parse
import json
import os
from datetime import datetime, timedelta

# Configuration
CLIENT_ID = "votre_client_id"
CLIENT_SECRET = "votre_client_secret"
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "r_liteprofile r_emailaddress w_member_social"
AUTH_URL = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={SCOPES}"

# Classe pour gérer la redirection
class CallbackHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/callback'):
            # Extraire le code d'autorisation
            query = urllib.parse.urlparse(self.path).query
            params = dict(urllib.parse.parse_qsl(query))
            auth_code = params.get('code', '')
            
            if auth_code:
                # Échanger le code contre un token d'accès
                token_data = exchange_code_for_token(auth_code)
                if token_data:
                    # Envoyer une réponse HTML
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><body><h1>Autorisation réussie!</h1><p>Vous pouvez fermer cette fenêtre.</p></body></html>")
                    
                    # Sauvegarder les tokens
                    save_tokens(token_data)
                    
                    # Arrêter le serveur
                    self.server.shutdown()
                else:
                    self.send_response(500)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><body><h1>Erreur!</h1><p>Impossible d'obtenir le token d'accès.</p></body></html>")
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Erreur!</h1><p>Code d'autorisation manquant.</p></body></html>")
        else:
            super().do_GET()

def exchange_code_for_token(auth_code):
    """Échange le code d'autorisation contre un token d'accès"""
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    response = requests.post(token_url, data=data, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Erreur: {response.status_code} - {response.text}")
        return None

def save_tokens(token_data):
    """Sauvegarde les tokens dans un fichier JSON"""
    # Ajouter la date d'expiration
    expires_in = token_data.get('expires_in', 0)
    expire_date = datetime.now() + timedelta(seconds=expires_in)
    token_data['expire_date'] = expire_date.isoformat()
    
    with open('linkedin_tokens.json', 'w') as f:
        json.dump(token_data, f, indent=2)
    
    print("\n===== TOKENS LINKEDIN OBTENUS =====")
    print(f"Access Token: {token_data['access_token']}")
    print(f"Refresh Token: {token_data['refresh_token']}")
    print(f"Expire dans: {expires_in} secondes ({expire_date})")
    print("====================================")
    print("\nAjoutez ces tokens comme secrets GitHub:")
    print("LINKEDIN_ACCESS_TOKEN")
    print("LINKEDIN_REFRESH_TOKEN")

def main():
    # Ouvrir le navigateur pour l'autorisation
    print(f"Ouverture du navigateur pour l'autorisation LinkedIn...")
    webbrowser.open(AUTH_URL)
    
    # Démarrer un serveur local pour recevoir la redirection
    port = 8000
    with socketserver.TCPServer(("", port), CallbackHandler) as httpd:
        print(f"Serveur démarré sur le port {port}...")
        httpd.serve_forever()

if __name__ == "__main__":
    main()
```

### 3.2 Exécuter le script

1. Remplacez `votre_client_id` et `votre_client_secret` par les valeurs de votre application LinkedIn
2. Exécutez le script: `python get_linkedin_token.py`
3. Suivez les instructions pour autoriser l'application
4. Le script affichera les tokens obtenus

## 4. Obtenir votre ID de personne LinkedIn

Pour publier du contenu, vous avez besoin de votre ID de personne LinkedIn:

1. Connectez-vous à LinkedIn
2. Allez sur votre profil
3. Dans l'URL de votre profil, vous verrez quelque chose comme `linkedin.com/in/votre-nom/`
4. Utilisez l'API pour récupérer votre ID numérique avec ce script:

```python
import requests
import json

def get_person_id(access_token):
    url = "https://api.linkedin.com/v2/me"
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(f"ID de personne LinkedIn: {data['id']}")
        return data['id']
    else:
        print(f"Erreur: {response.status_code} - {response.text}")
        return None

# Remplacez par votre token d'accès
access_token = "votre_access_token"
person_id = get_person_id(access_token)
print(f"Ajoutez cet ID comme secret GitHub: LINKEDIN_PERSON_ID = {person_id}")
```

## 5. Configurer les secrets GitHub

Ajoutez ces informations comme secrets dans votre dépôt GitHub:

1. LINKEDIN_CLIENT_ID - votre Client ID
2. LINKEDIN_CLIENT_SECRET - votre Client Secret
3. LINKEDIN_ACCESS_TOKEN - le token d'accès 
4. LINKEDIN_REFRESH_TOKEN - le token de rafraîchissement
5. LINKEDIN_PERSON_ID - votre ID de personne LinkedIn

## Notes importantes

1. Le token d'accès LinkedIn expire généralement après 60 jours
2. Le script `linkedin_publisher.py` tente de rafraîchir automatiquement le token
3. Cependant, GitHub Actions ne peut pas mettre à jour ses propres secrets
4. Une solution est de stocker les tokens dans un service externe sécurisé ou une base de données
5. Alternativement, renouvelez manuellement le token tous les 45-50 jours pour éviter l'expiration

## Solutions alternatives

Si cette configuration est trop complexe, vous pouvez envisager:

1. [Zapier](https://zapier.com/) pour connecter GitHub à LinkedIn
2. [IFTTT](https://ifttt.com/) pour des automatisations simples
3. [Integromat/Make](https://www.make.com/) pour des workflows plus avancés
