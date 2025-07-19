*Note: ce projet se répartit sur plusieurs dépôts pour faciliter la maintenance.*
*Notre usage a évolué mais il s'agit toujours de générer automatiquement un fichier HTML depuis des fichiers Markdown.*  
 # Portfolio Automation
>>
>> Ce dépôt contient des scripts et workflows pour automatiser la création et la publication de contenus à partir de notre dépôt portfolio.
>>
>> ## Fonctionnalités
>>
>> 1. **Génération de Newsletter** : Crée automatiquement une newsletter hebdomadaire à partir des fichiers Markdown les plus récents de notre portfolio  
>>
>> ## Comment ça marche
>>
>> Le système génère une newsletter contenant jusqu'à 6 de vos contenus les plus récents (créés ou modifiés au cours des 7 derniers jours).  
>>
>> ## Configuration nécessaire
>>
>> 1. Créez un token d'accès personnel GitHub avec les droits `repo`
>> 2. Ajoutez-le comme secret dans le dépôt sous le nom `GH_PAT`
>> 3. Modifiez le fichier workflow pour utiliser votre nom d'utilisateur GitHub
>>
## Structure du dépôt
```
portfolio-automation/
├── .github/                    
│   └── workflows/              
│       └── generate_newsletter.yml  
├── scripts/                    
│   └── newsletter_generator.py
├── newsletters/                
└── README.md
```
## Utilisation

Les newsletters sont générées automatiquement chaque vendredi. Vous pouvez également déclencher manuellement la génération via l'onglet Actions de GitHub.
