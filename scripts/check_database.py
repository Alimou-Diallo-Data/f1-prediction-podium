"""Connexion et aller-retour transactionnel sans conserver de données fictives."""
import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
url = os.getenv('DATABASE_URL')
if not url:
    raise SystemExit('DATABASE_URL manquante : remplir le fichier .env.')
try:
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT to_regclass(%s)', ('f1.races',))
            if cur.fetchone()[0] is None:
                raise SystemExit('Schéma absent : exécuter database/001_schema.sql.')
            cur.execute('CREATE TEMP TABLE s1_probe(value INTEGER CHECK(value>0)) ON COMMIT DROP')
            cur.execute('INSERT INTO s1_probe VALUES (%s)', (1,))
            cur.execute('SELECT value FROM s1_probe')
            assert cur.fetchone() == (1,)
            cur.execute('SELECT count(*) FROM f1.races')
            print(f'Connexion et lecture/écriture OK. Courses : {cur.fetchone()[0]}')
except psycopg.Error:
    raise SystemExit('Échec PostgreSQL : vérifier le serveur, les droits et DATABASE_URL. Aucun secret affiché.')
