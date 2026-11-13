# S5 — Premiers modèles : victoire et podium

L'application complète S1–S5 réutilise le schéma f1 et les saisons déjà chargées. Aucun effacement ni migration de base. La cible abandon/DNF n'est pas encore implémentée : elle nécessitera une règle explicite sur les statuts, ainsi qu'un traitement des non-départs, disqualifications et pilotes classés sans terminer.

## Installation dans WSL

Arrêter Streamlit avec Ctrl+C. Extraire l'archive dans Downloads/PROJET F1. Si le terminal commence par PS, ouvrir d'abord WSL avec `wsl -u postgres`.

```bash
cd "/mnt/c/Users/User/Downloads/PROJET F1/F1-S5-Machine-Learning/F1-S5"
source "$HOME/venvs/f1-s2/bin/activate"
cp "/mnt/c/Users/User/Downloads/PROJET F1/F1-S4-Comparateurs/F1-S4/.env" .env
python -m pip install -r requirements.txt
python scripts/check_database.py
python -m ml.train
```

Les saisons 2018 à 2023 sont obligatoires. La saison 2024 sera nécessaire au test séparé. La commande affiche les scores de chaque modèle, le dossier models/EXECUTION et une commande pour le test final. Un échec ne remplace jamais une exécution antérieure ; un dossier incomplet peut subsister mais n'apparaît pas dans le dashboard sans manifest.json.

Après l'entraînement :

```bash
python -m streamlit run app.py
```

Ouvrir http://localhost:8501, onglet Machine Learning. Recharger la page après un entraînement terminé. Un Streamlit déjà ouvert peut utiliser un autre port ; lire son URL affichée.

## Protocole

| Période | Usage |
|---|---|
| 2018–2022 | Ajustement des modèles et du prétraitement |
| 2023 | Comparaison des modèles et sélection par log-loss minimale |
| 2024 | Test final explicite du modèle sélectionné, sans réentraînement |

Deux cibles binaires : victoire = position officielle 1 ; podium = position officielle 1, 2 ou 3. Si une course contient des positions inconnues, n'a pas exactement un vainqueur ou trois positions de podium, tous ses labels sont exclus de l'entraînement/évaluation. Son historique connu reste utilisable pour les courses suivantes. Les exclusions sont comptées dans le rapport.

Quatre modèles par cible : fréquence de la cible dans l'entraînement (baseline), régression logistique, forêt aléatoire, HistGradientBoosting. Paramètres fixes et graine 42. Pas de recherche aléatoire ni de validation qui mélange les dates. Le boosting désactive l'arrêt anticipé fondé sur une séparation aléatoire. La baseline peut être sélectionnée si elle obtient le meilleur score ; ne pas masquer ce résultat.

Numériques : médiane et indicateurs de valeurs manquantes, puis standardisation. Catégorielles : imputation et encodage one-hot avec catégories inconnues ignorées. Tout le prétraitement est appris seulement sur l'entraînement. Les variables numériques entièrement absentes sont conservées par l'imputation. Les identités pilotes/écuries et les circuits sont des catégories, pas des valeurs ordinales.

## Variables avant qualifications

- Manche, pilote, écurie et circuit.
- Historique des cinq dernières courses connues du pilote : nombre disponible, moyenne des positions et points, fréquence de victoire et podium.
- Historique des cinq dernières courses connues de l'écurie : nombre disponible, moyenne des points GP par événement et des positions de ses pilotes.

Toutes les variables d'une course sont produites AVANT la mise à jour des historiques de tous ses pilotes. Aucun résultat, point, statut, temps de qualification ou grille de la course cible n'est une entrée. Les historiques continuent entre saisons et sont vides pour un débutant sans historique. Ils ne sont pas artificiellement remplis par zéro avant le prétraitement.

Le protocole représente une estimation avant qualifications. L'évaluation est rétrospective : les participants et leur écurie sont identifiés à partir des résultats de la course. Ce n'est donc pas encore un service opérationnel pour un Grand Prix futur. Les données historiques peuvent intégrer des corrections/sanctions publiées ultérieurement : leurs dates de publication ne sont pas disponibles dans cet ETL. Les tests empêchent la fuite du résultat cible, sans pouvoir reconstituer exactement les informations connues à une date historique.

## Scores et fichiers

Log-loss et Brier : plus petits = meilleurs. Average precision et ROC-AUC : plus grands = meilleurs. Aucun seuil à 0,5 ni accuracy globale n'est utilisé pour choisir le modèle, compte tenu de la rareté des victoires. Une bonne évaluation ne garantit pas la calibration des probabilités.

Chaque dossier models/EXECUTION contient :

- validation.csv : scores des quatre modèles pour chaque cible ;
- win.joblib et podium.joblib : modèles sélectionnés avec prétraitement ;
- features_development.csv : instantané des variables et labels jusqu'en 2023 ;
- manifest.json : années, effectifs, versions et empreinte des données préparées.

Les fichiers joblib ne doivent provenir que de vos propres entraînements de confiance. Le dashboard lit uniquement les rapports CSV/JSON ; il ne désérialise pas les modèles.

## Test final séparé

Figer le protocole et les paramètres avant de consulter 2024. Exécuter la commande exacte imprimée après l'entraînement, par exemple (remplacer NOM_EXECUTION par le nom réel) :

```bash
python -m ml.train --evaluate-test NOM_EXECUTION
```

La commande vérifie la version scikit-learn et l'empreinte des données de développement. Elle garde les modèles figés, mais utilise les résultats des GP 2024 précédents pour construire l'historique de chaque manche suivante : c'est une évaluation séquentielle, pas une prévision de toute la saison en janvier.

Elle crée test.json et test_predictions.csv avec les vrais labels et probabilités. Une seconde exécution du test dans le même dossier est refusée pour éviter les remplacements accidentels ; ce garde-fou n'empêche pas de créer un nouvel entraînement et ne doit pas servir à sélectionner un modèle à partir des scores 2024.

Les probabilités binaires sont indépendantes par pilote. Elles ne sont pas normalisées pour sommer à 1 (victoire) ou 3 (podium). Elles ne garantissent pas non plus p(victoire) ≤ p(podium), les cibles étant apprises séparément. L'affichage est limité aux rapports et à un export rétrospectif à ce stade. Pas d'écriture dans f1.predictions, pas d'alertes ni de prédictions futures en S5. Calibration, cohérence des cibles, SHAP, autres cibles et simulations relèvent de S6.

## Vérifications

```bash
python -m unittest discover -s tests -v
```

21 tests hors ligne passent sur des données synthétiques, dont entraînement, test séparé et affichage des rapports. Les tests ML vérifient notamment qu'une modification du résultat d'une course n'altère pas les variables de cette course ou des précédentes, que les coéquipiers n'utilisent pas les résultats courants, et que le test final est séparé de l'entraînement. Les données utilisées dans ces tests sont synthétiques ; les métriques affichées pendant ces tests ne sont pas des performances sur la F1 réelle.

Sources techniques : https://scikit-learn.org/stable/modules/model_evaluation.html et https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html (consultées le 28 octobre 2026).
