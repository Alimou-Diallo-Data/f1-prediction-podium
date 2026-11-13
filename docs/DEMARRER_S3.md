# S3 — Dashboard MVP PostgreSQL

Ce dossier comprend S1, S2 et le dashboard. Il utilise le schéma f1 déjà alimenté ; aucune réinitialisation de la base n'est nécessaire.

## WSL : démarrage

Extraire F1-S3 sur la machine. Dans son dossier, activer l'environnement Linux existant :

```bash
source "$HOME/venvs/f1-s2/bin/activate"
pip install -r requirements.txt
```

Copier le fichier .env de F1-S2 dans F1-S3. Il contient la configuration de la même base PostgreSQL. Ne pas publier ce fichier.

```bash
python scripts/check_database.py
python -m streamlit run app.py
```

Ouvrir http://localhost:8501 dans le navigateur Windows. Garder le terminal ouvert ; Ctrl+C arrête l'application. Le port reste local par défaut : ne pas le publier sur Internet avec le rôle PostgreSQL actuel.

## Fonctions

- Filtres saison et Grand Prix ; sélection initiale de la dernière course avec résultats.
- Indicateurs de saison, podium selon les positions 1/2/3 réellement présentes.
- Résultats de course filtrables par écurie et export CSV ; sprint séparé.
- Classements officiels pilotes et écuries à la manche sélectionnée, avec repli explicitement indiqué vers la dernière manche antérieure disponible.
- Top 10 et évolution des points jusqu'à la manche sélectionnée.
- Qualifications Q1/Q2/Q3, temps en secondes et écarts calculés dans la même séance.
- Calendrier et disponibilité des résultats.
- Actualisation manuelle du cache (5 minutes), sans déclenchement de l'ETL.

Les lectures SQL utilisent une transaction en lecture seule et un instantané cohérent. Le rôle utilisé peut être celui de S2 pour le développement ; créer un rôle limité à SELECT pour le déploiement. L'application n'entraîne aucun modèle et n'invente aucune prédiction.

## Validation

```bash
python -m unittest discover -s tests -v
```

Tests : ETL hors ligne et dashboard sur données synthétiques (temps, absence de données, connexion en erreur, navigation et classements sans information future). Ces tests ne remplacent pas une vérification sur votre PostgreSQL. Aucune connexion à votre machine n'est possible depuis l'environnement de préparation.

Vérifier dans le navigateur : saison 2024, 24 courses avec résultats, changement de Grand Prix, classements, qualifications et export CSV. Si la connexion échoue, contrôler le fichier .env et le serveur PostgreSQL. Les messages serveur susceptibles de contenir des secrets ne sont pas affichés.

Limites : lecture de toutes les saisons au chargement (à paginer côté SQL si le volume augmente), pas d'authentification applicative, pas de prédictions avant S5/S6. Les données absentes restent vides. Les victoires affichées proviennent des classements officiels, pas de sommes recalculées. Les points décimaux sont conservés.

Documentation Streamlit consultée : https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data
