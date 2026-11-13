"""ETL Jolpica vers le schéma PostgreSQL f1 de S1."""
import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time
from uuid import uuid4
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
KEYS = {
 'circuits': ('circuit_id',), 'drivers': ('driver_id',),
 'constructors': ('constructor_id',), 'races': ('season','round'),
 'results': ('season','round','driver_id'),
 'sprint_results': ('season','round','driver_id'),
 'qualifying': ('season','round','driver_id'),
 'driver_standings': ('season','round','driver_id'),
 'constructor_standings': ('season','round','constructor_id'),
}

def number(value, converter=int):
    return None if value in (None, '', '\\N') else converter(value)

def seconds(value):
    if not value:
        return None
    parts = value.split(':')
    if len(parts) > 2:
        raise ValueError('Temps de qualification invalide')
    result = sum(Decimal(p) * (60 ** i) for i,p in enumerate(reversed(parts)))
    if not result.is_finite() or result <= 0:
        raise ValueError('Temps de qualification invalide')
    return result

class Client:
    def __init__(self, archive, session=None):
        self.archive = Path(archive)
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent':'UQAM-F1-session-project/1.0'})
        self.last = 0.0

    def page(self, endpoint, offset):
        url = f'https://api.jolpi.ca/ergast/f1/{endpoint}/'
        for attempt in range(5):
            # Marge sous la limite horaire publique ; les pages sont archivées.
            time.sleep(max(0, 7.5 - (time.monotonic()-self.last)))
            self.last = time.monotonic()
            try:
                response = self.session.get(url, params={'limit':100,'offset':offset}, timeout=30)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 4:
                        response.raise_for_status()
                    try:
                        delay = float(response.headers.get('Retry-After', 2**attempt))
                    except ValueError:
                        delay = 2**attempt
                    if delay > 60:
                        raise RuntimeError('Quota API atteint : réessayer ultérieurement')
                    time.sleep(max(0,delay))
                    continue
                response.raise_for_status()
                payload = response.json()
                target = self.archive / endpoint / f'{offset}.json'
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
                return payload['MRData']
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 4:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError('Extraction interrompue')

    def rows(self, endpoint, table, group, nested=None):
        offset = 0
        total_expected = None
        while True:
            data = self.page(endpoint,offset)
            total = int(data['total'])
            if total_expected is not None and total != total_expected:
                raise ValueError('Source modifiée pendant la pagination : relancer')
            total_expected = total
            groups = data[table][group]
            count = 0
            for parent in groups:
                if nested:
                    for child in parent[nested]:
                        count += 1
                        yield parent,child
                else:
                    count += 1
                    yield parent
            if offset + count >= total:
                return
            if count == 0:
                raise ValueError('Pagination incomplète : page vide avant total')
            offset += count

class Dataset:
    def __init__(self):
        self.tables = {name:{} for name in KEYS}
    def add(self, table, **row):
        key = tuple(row[k] for k in KEYS[table])
        if any(k is None or k == '' for k in key):
            raise ValueError(f'Clé absente : {table}')
        previous = self.tables[table].get(key)
        if previous is not None and previous != row:
            raise ValueError(f'Doublon contradictoire : {table} {key}')
        self.tables[table][key] = row
    def driver(self,d):
        self.add('drivers',driver_id=d['driverId'],given_name=d['givenName'],
                 family_name=d['familyName'],birth_date=d.get('dateOfBirth'),nationality=d.get('nationality'))
    def constructor(self,c):
        self.add('constructors',constructor_id=c['constructorId'],name=c['name'],nationality=c.get('nationality'))
    def race(self,r):
        c = r['Circuit']; loc = c['Location']
        self.add('circuits',circuit_id=c['circuitId'],name=c['circuitName'],country=loc.get('country'),
                 locality=loc.get('locality'),latitude=number(loc.get('lat'),float),longitude=number(loc.get('long'),float))
        date.fromisoformat(r['date'])
        self.add('races',season=int(r['season']),round=int(r['round']),circuit_id=c['circuitId'],
                 name=r['raceName'],race_date=r['date'],
                 starts_at=f"{r['date']}T{r['time']}" if r.get('time') else None)
    @property
    def count(self):
        return sum(len(rows) for rows in self.tables.values())

def extract(client,season):
    ds = Dataset()
    for r in client.rows(str(season),'RaceTable','Races'):
        ds.race(r)
    if not ds.tables['races']:
        raise ValueError('Aucune course : vérifier la saison')
    for endpoint,nested,table in [('results','Results','results'),('qualifying','QualifyingResults','qualifying'),
                                   ('sprint','SprintResults','sprint_results')]:
        for r,item in client.rows(f'{season}/{endpoint}','RaceTable','Races',nested):
            if (int(r['season']),int(r['round'])) not in ds.tables['races']:
                raise ValueError('Résultat sans course dans le calendrier')
            ds.driver(item['Driver']); ds.constructor(item['Constructor'])
            row = dict(season=int(r['season']),round=int(r['round']),driver_id=item['Driver']['driverId'],
                       constructor_id=item['Constructor']['constructorId'],position=number(item.get('position')))
            if table == 'qualifying':
                row.update({f'q{i}_seconds':seconds(item.get(f'Q{i}')) for i in (1,2,3)})
            else:
                row.update(grid=number(item.get('grid')),points=number(item.get('points'),Decimal),
                           laps=number(item.get('laps')),status=item.get('status'))
            ds.add(table,**row)
    # Les endpoints sans round ne fournissent que le dernier classement.
    completed = sorted({key[1] for key in ds.tables['results']})
    for rd in completed:
        for endpoint,nested,table,entity in [
            ('driverstandings','DriverStandings','driver_standings','Driver'),
            ('constructorstandings','ConstructorStandings','constructor_standings','Constructor')]:
            for parent,item in client.rows(f'{season}/{rd}/{endpoint}','StandingsTable','StandingsLists',nested):
                if int(parent['season']) != season or int(parent['round']) != rd:
                    raise ValueError('Classement retourné pour une autre manche')
                if entity == 'Driver':
                    ds.driver(item[entity]); foreign = {'driver_id':item[entity]['driverId']}
                else:
                    ds.constructor(item[entity]); foreign = {'constructor_id':item[entity]['constructorId']}
                ds.add(table,season=season,round=rd,position=number(item.get('position')),
                       points=number(item.get('points'),Decimal),wins=number(item.get('wins')),**foreign)
    return ds

def load(conn,ds):
    from psycopg import sql
    # Un seul commit pour l'ensemble de la saison ; aucune suppression.
    with conn.transaction():
        with conn.cursor() as cur:
            for table,rows in ds.tables.items():
                for row in rows.values():
                    columns = list(row)
                    updates = [c for c in columns if c not in KEYS[table]]
                    query = sql.SQL('INSERT INTO f1.{} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}').format(
                        sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,columns)),
                        sql.SQL(',').join(sql.Placeholder() for _ in columns),
                        sql.SQL(',').join(map(sql.Identifier,KEYS[table])),
                        sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c),sql.Identifier(c)) for c in updates))
                    cur.execute(query,list(row.values()))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season',type=int,required=True)
    parser.add_argument('--dry-run',action='store_true',help='Extraction et transformation sans PostgreSQL')
    args = parser.parse_args()
    if not 1950 <= args.season <= date.today().year+1:
        parser.error('Saison hors plage')
    load_dotenv(ROOT/'.env')
    run_id = uuid4().hex
    archive = ROOT/'data'/'raw'/str(args.season)/run_id
    conn = None
    try:
        if not args.dry_run:
            import psycopg
            url = os.getenv('DATABASE_URL')
            if not url:
                raise ValueError('DATABASE_URL absente')
            conn = psycopg.connect(url,autocommit=True)
            conn.execute("INSERT INTO f1.etl_runs(run_id,season,started_at,status) VALUES(%s,%s,%s,'running')",
                         (run_id,args.season,datetime.now(timezone.utc)))
        ds = extract(Client(archive),args.season)
        if conn:
            with conn.transaction():
                load(conn,ds)
                conn.execute("UPDATE f1.etl_runs SET finished_at=%s,status='success',records_count=%s WHERE run_id=%s",
                         (datetime.now(timezone.utc),ds.count,run_id))
        summary = {t:len(rows) for t,rows in ds.tables.items()}
        archive.mkdir(parents=True,exist_ok=True)
        (archive/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print('Extraction validée' if args.dry_run else 'Chargement terminé')
        print(json.dumps(summary,indent=2)); print(f'Archives : {archive}')
    except Exception as exc:
        # Ni URL de connexion ni message serveur potentiellement sensible à l'écran.
        if conn:
            try:
                conn.execute("UPDATE f1.etl_runs SET finished_at=%s,status='failed',error_summary=%s WHERE run_id=%s",
                             (datetime.now(timezone.utc),type(exc).__name__,run_id))
            except Exception:
                pass
        raise SystemExit(f'Échec ({type(exc).__name__}). Exécution : {run_id}. Vérifier API, schéma et configuration.') from None
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
