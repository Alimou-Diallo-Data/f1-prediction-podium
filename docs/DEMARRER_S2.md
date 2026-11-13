# S2 — Charger une première saison

Ce dossier comprend S1 et le nouvel ETL. Il utilise exactement le schéma f1 déjà installé. Il ne contient aucun mot de passe ni données réelles préchargées.

## Sur ta machine, dans le dossier extrait F1-S2

Activer l'environnement Python existant ou en créer un, puis :

```bash
pip install -r requirements.txt
```

Copier ton fichier `.env` du dossier F1-S1 vers F1-S2 (ne pas l'envoyer ni le publier). Ne pas remplacer sa valeur DATABASE_URL par l'exemple.

```bash
python scripts/check_database.py
python -m unittest discover -s tests -v
python -m etl.pipeline --season 2024
```

Commencer par 2024, saison terminée. L'extraction est volontairement espacée ; elle peut prendre une dizaine de minutes. Elle affiche les compteurs à la fin. En cas d'échec, le message donne un identifiant d'exécution, sans exposer les identifiants PostgreSQL.

## Ce qui est chargé

Calendrier, circuits, pilotes et écuries présents dans les résultats/qualifications/classements ; résultats de course et sprint, qualifications, classements après chaque manche disputée. Une absence de sprint ou de Q2/Q3 n'est pas remplacée par zéro. Les temps de qualification sont convertis en secondes et les points en nombres décimaux.

Les pages JSON sont archivées dans data/raw/SAISON/EXECUTION. Une relance refait l'extraction et réalise des UPSERT : elle ne duplique pas les clés et n'efface aucune saison. Le chargement complet et son statut success sont transactionnels. Les données incorrectes font échouer l'exécution plutôt que d'être partiellement ignorées : aucun rejet silencieux, rejected_count reste à zéro. Les doublons identiques sont fusionnés ; les doublons contradictoires interrompent le chargement.

Attention : UPSERT ne supprime pas une ligne retirée ultérieurement par la source. Une synchronisation des suppressions et la reprise depuis les archives restent à ajouter. Les validations SQL des bornes et des relations se font au chargement ; --dry-run vérifie uniquement extraction et transformation.

## Vérification SQL après chargement

```sql
SELECT season, count(*) FROM f1.races GROUP BY season;
SELECT season, count(*) FROM f1.results GROUP BY season;
SELECT season, count(*) FROM f1.qualifying GROUP BY season;
SELECT season, max(round) FROM f1.driver_standings GROUP BY season;
SELECT run_id, status, records_count, error_summary
FROM f1.etl_runs ORDER BY started_at DESC LIMIT 5;
```

Relancer ensuite la même commande ETL : les effectifs des tables doivent rester stables si la source n'a pas changé. records_count est le nombre de lignes traitées, références comprises, et non le nombre de nouvelles lignes.

Option pour extraire sans écrire dans PostgreSQL :

```bash
python -m etl.pipeline --season 2024 --dry-run
```

## Validation et limites

Sept tests hors ligne couvrent pagination imbriquée/incomplète, changement du total, doublons, valeurs absentes, temps et transformation d'une saison synthétique. Aucun test sur le serveur PostgreSQL de l'utilisateur ni extraction réelle complète n'a été réalisé ici. Les erreurs réseau transitoires sont réessayées ; après épuisement, l'exécution échoue et peut être relancée. Les exécutions arrêtées brutalement peuvent rester running dans le journal. Ne pas lancer plusieurs chargements concurrents de la même saison.

Le dashboard précédent lit encore son stockage existant : il faudra le raccorder au schéma f1 en S3.

Documentation source : https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md et docs/rate_limits.md du même dépôt (consultées le 28 octobre 2026).
