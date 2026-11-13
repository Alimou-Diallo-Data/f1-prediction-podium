# S4 — Analyses et comparateurs

Ce dossier contient l'application complète S1 à S4. Le schéma PostgreSQL est inchangé et les données 2024 déjà chargées sont réutilisées.

## Lancer dans WSL

Arrêter le serveur S3 avec Ctrl+C. Extraire l'archive S4 dans Downloads/PROJET F1 puis :

```bash
cd "/mnt/c/Users/User/Downloads/PROJET F1/F1-S4-Comparateurs/F1-S4"
source "$HOME/venvs/f1-s2/bin/activate"
cp "/mnt/c/Users/User/Downloads/PROJET F1/F1-S3-Dashboard/F1-S3/.env" .env
pip install -r requirements.txt
python -m streamlit run app.py
```

Ouvrir http://localhost:8501 et l'onglet Comparateurs. Adapter le chemin cd si l'extraction a créé un dossier différent. Aucun chargement ETL supplémentaire nécessaire.

## Comparer

La saison et la manche de la barre latérale délimitent les données : aucune manche postérieure n'est incluse. Choisir Pilotes ou Écuries, puis deux sélections distinctes. Choisir Toutes leurs courses pour les statistiques de chacun ou Courses communes pour les manches où chacun possède un résultat de GP. En mode commun, les sprints et qualifications sont également limités à ces manches.

Indicateurs : nombre de courses, nombre de résultats de pilotes, victoires et podiums en GP, points GP et sprint séparés, moyenne des positions et nombre de positions connues. Pour une écurie, podiums/victoires désignent des résultats de pilotes ; une double présence sur le podium compte donc deux podiums. La moyenne des positions utilise tous les résultats avec position connue, tous statuts confondus. Une position officielle n'implique pas nécessairement que le pilote a terminé la course.

Le face-à-face pilote compare seulement les positions connues de deux pilotes dans la même manche, sans exclusion des abandons classés. Le graphique montre les points par GP, sans sprint. L'export CSV contient les indicateurs du périmètre sélectionné.

Les qualifications comparent Q1, Q2 ou Q3 dans une même manche. Écart A−B négatif : A plus rapide. Pour une écurie, on utilise le meilleur temps connu parmi ses pilotes. Les séances sans temps pour l'une des sélections sont exclues et le nombre comparable est affiché.

## Valeurs inconnues et précautions

Un point absent ne vaut pas zéro. Si un total contient une valeur inconnue, il reste vide. Aucun sprint connu laisse le total sprint vide. Les décomptes de podiums/victoires reposent sur les positions connues ; vérifier la couverture pour des données partielles. Le classement officiel reste dans Championnat : des sanctions peuvent créer un écart avec les points des résultats.

Comparer des pilotes ayant disputé un nombre différent de courses ou les seuls pilotes qualifiés pour Q3 peut introduire un biais de sélection. Les effectifs et le périmètre sont affichés pour rendre ce contexte visible. Aucun score prédictif ni définition automatique de DNF n'est ajouté à ce stade.

## Vérification

```bash
python -m unittest discover -s tests -v
```

17 tests réussis sur données synthétiques : ETL, dashboard S3, valeurs manquantes, face-à-face, qualifications, filtre temporel et navigation pilotes/écuries. La connexion réelle au PostgreSQL de l'utilisateur reste à vérifier sur sa machine.

Vérification manuelle : choisir deux pilotes, tester Courses communes, passer de Q1 à Q3, choisir Écuries, changer la manche dans la barre latérale et exporter le CSV.
