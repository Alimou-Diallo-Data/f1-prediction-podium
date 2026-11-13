# S6 — Module SHAP des modèles S5

Cette livraison ajoute les explications locales et une baseline complémentaire sur le test 2024. Elle contient l'application S1–S5 complète. Elle ne réentraîne pas les modèles, ne modifie pas les scores finaux et ne réinitialise aucune table.

## Installer et lancer dans WSL

Extraire le dossier F1-S6 à cet emplacement Windows :

C:\Users\User\Downloads\PROJET F1\F1-S6

Le fichier app.py et le dossier ml doivent être directement dans F1-S6. Si l'extraction crée un dossier supplémentaire, déplacer le dossier intérieur F1-S6 à l'emplacement ci-dessus. Arrêter le serveur S5 avec Ctrl+C. Si le terminal commence par PS, ouvrir WSL avec `wsl -u postgres`.

```bash
cd "/mnt/c/Users/User/Downloads/PROJET F1/F1-S6" &&
source "$HOME/venvs/f1-s2/bin/activate" &&
cp "/mnt/c/Users/User/Downloads/PROJET F1/F1-S5/.env" .env &&
mkdir -p models &&
cp -r "/mnt/c/Users/User/Downloads/PROJET F1/F1-S5/models/." models/ &&
python -m pip install -r requirements.txt &&
python -m streamlit run app.py
```

Le dossier models doit contenir votre exécution 20261028T062053_ba2765, ses deux fichiers joblib, manifest.json, features_development.csv, validation.csv et les rapports de test. Ne pas exécuter ml.train pour cette étape. Ne charger que les modèles créés par votre propre entraînement ; les fichiers joblib externes peuvent exécuter du code lors du chargement.

La version scikit-learn doit rester celle de l'entraînement (1.9.1 pour cette exécution). L'application bloque le chargement si elle diffère. Installer les dépendances sans --upgrade pour conserver les versions déjà compatibles.

## Utiliser le dashboard

Ouvrir http://localhost:8501 (ou l'URL locale affichée par Streamlit). Dans Explications SHAP : choisir l'exécution, l'année, la course, le pilote et la cible Victoire ou Podium, puis cliquer Expliquer cette estimation.

Le graphique affiche les contributions des 12 variables d'origine, en points de pourcentage. Une contribution positive augmente l'estimation par rapport à la référence du modèle ; une contribution négative la diminue. Exemple : référence 10 % + contribution 5 points = 15 %. Le calcul complet vérifie que la référence plus la somme des contributions correspond à la probabilité, à une tolérance de 1e-5.

Les valeurs réellement fournies au modèle, les paramètres de calcul et un export JSON sont disponibles. Un changement de sélection masque l'explication précédente jusqu'à un nouveau calcul. Les résultats sont mis en cache pour éviter les recalculs au même choix. La première explication peut prendre plus de temps en raison de l'initialisation des bibliothèques.

## Méthode

SHAP PermutationExplainer, graine 42, cinq permutations aller-retour au budget (2p+1)*5. Le fond de référence est un échantillon déterministe de 32 observations éligibles d'entraînement 2018–2022 (ou toutes s'il y en a moins). La fonction expliquée est la probabilité positive fournie par le pipeline S5 complet. Les imputations, standardisations et catégories apprises restent inchangées.

Les catégories sont codées numériquement uniquement pour le masque SHAP, puis décodées vers leurs chaînes d'origine avant chaque appel au pipeline. Elles ne sont pas traitées comme des valeurs ordinales par le modèle. Les contributions restent groupées par variable d'origine : pas de séparation artificielle entre les colonnes one-hot d'un pilote.

La référence est la moyenne des probabilités du modèle sur le fond choisi, pas nécessairement la fréquence réelle des victoires ou podiums. Les valeurs SHAP sont approximatives et dépendent du fond et du budget. Les variables sont corrélées : un masquage indépendant peut créer des combinaisons peu réalistes de pilote, écurie et historique. Ces explications décrivent le comportement du modèle, sans démontrer un lien causal ni garantir sa précision.

L'empreinte de l'historique jusqu'en 2023 est comparée à celle de S5 avant d'expliquer. Les variables 2024 sont reconstruites à partir des courses antérieures. La probabilité calculée pour 2024 est ensuite comparée à celle du test sauvegardé ; si elle diffère de plus de 1e-6, l'affichage est bloqué. Les explications sont rétrospectives ; elles ne constituent pas une prévision opérationnelle d'un prochain Grand Prix.

## Baseline complémentaire 2024

L'expander Baseline sur 2024 applique la fréquence de chaque cible dans les données d'entraînement 2018–2022 aux mêmes observations que test_predictions.csv. Il affiche log-loss, Brier, average precision et ROC-AUC. Comparer ces valeurs à l'onglet Machine Learning ; cette analyse n'entraîne aucun modèle et ne remplace pas le rapport final.

## Validation et suite

27 tests passent sur données synthétiques : ETL, dashboard, comparateurs, ML et explications. Les nouvelles vérifications couvrent décodage des catégories et valeurs manquantes, fond limité à l'entraînement, additivité avec régression logistique/forêt/boosting, garde de version, baseline et navigation après une explication. Les modèles locaux de l'utilisateur et sa connexion PostgreSQL ne sont pas accessibles depuis l'environnement de préparation.

```bash
python -m unittest discover -s tests -v
```

Cette étape de S6 livre SHAP local. DNF, calibration, cohérence des probabilités entre cibles, scénarios et projections de saison restent à développer séparément. Les probabilités S5 et leurs limites restent inchangées. Aucune écriture de prédictions en base et aucun service Azure créé.

Documentation : https://shap.readthedocs.io/en/stable/generated/shap.PermutationExplainer.html et https://shap.readthedocs.io/en/stable/generated/shap.Explainer.html (consultées le 28 octobre 2026).
