"""Lectures paramétrées du schéma f1 ; aucune modification des données."""
import os
from pathlib import Path
import pandas as pd
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

class DatabaseUnavailable(RuntimeError):
    pass

def load_snapshot():
    load_dotenv(ROOT / '.env')
    url = os.getenv('DATABASE_URL')
    if not url:
        raise DatabaseUnavailable('DATABASE_URL absente. Copier le fichier .env de S2 dans le dossier courant.')
    try:
        with psycopg.connect(url, row_factory=dict_row, connect_timeout=10) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            conn.execute("SET LOCAL statement_timeout = '20s'")
            def query(sql):
                cur = conn.execute(sql)
                return pd.DataFrame(cur.fetchall(),columns=[col.name for col in cur.description])
            data = {}
            data['races'] = query('''SELECT r.season,r.round,r.circuit_id,r.name,r.race_date,c.name AS circuit,c.country
                FROM f1.races r JOIN f1.circuits c USING(circuit_id) ORDER BY r.season,r.round''')
            for name in ('results','sprint_results','qualifying'):
                # Identifiants limités à cette liste interne, jamais à une saisie utilisateur.
                data[name] = query(f'''SELECT t.*,d.given_name || ' ' || d.family_name AS driver,
                    c.name AS constructor FROM f1.{name} t
                    JOIN f1.drivers d USING(driver_id) JOIN f1.constructors c USING(constructor_id)
                    ORDER BY t.season,t.round,t.position NULLS LAST''')
            data['driver_standings'] = query('''SELECT s.*,d.given_name || ' ' || d.family_name AS driver
                FROM f1.driver_standings s JOIN f1.drivers d USING(driver_id)
                ORDER BY season,round,position NULLS LAST''')
            data['constructor_standings'] = query('''SELECT s.*,c.name AS constructor
                FROM f1.constructor_standings s JOIN f1.constructors c USING(constructor_id)
                ORDER BY season,round,position NULLS LAST''')
            data['runs'] = query('''SELECT season,finished_at,status FROM f1.etl_runs
                WHERE status='success' ORDER BY finished_at DESC LIMIT 100''')
            return data
    except psycopg.Error:
        raise DatabaseUnavailable('Base inaccessible ou schéma incomplet. Vérifier PostgreSQL, DATABASE_URL et le schéma S1.') from None
