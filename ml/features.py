"""Variables avant qualifications : l'historique est mis à jour après chaque course."""
from collections import defaultdict,deque
import numpy as np
import pandas as pd

NUMERIC=['round','driver_history_n','driver_pos5','driver_points5','driver_win5','driver_podium5',
         'team_history_n','team_points5','team_pos5']
CATEGORICAL=['driver_id','constructor_id','circuit_id']
FEATURES=NUMERIC+CATEGORICAL

def build_features(results,races):
    keys=['season','round','driver_id']
    if results.duplicated(keys).any() or races.duplicated(['season','round']).any():
        raise ValueError('Clés dupliquées dans les données ML')
    data=results.merge(races[['season','round','circuit_id','race_date']],on=['season','round'],how='left',validate='many_to_one')
    if data['race_date'].isna().any():
        raise ValueError('Résultat sans date de course')
    data['race_date']=pd.to_datetime(data['race_date'])
    for col in ['position','points']:
        data[col]=pd.to_numeric(data[col],errors='coerce')
    drivers=defaultdict(lambda:deque(maxlen=5));teams=defaultdict(lambda:deque(maxlen=5))
    rows=[]
    def mean(values):
        known=[v for v in values if pd.notna(v)]
        return float(np.mean(known)) if known else np.nan
    # Le calendrier date les événements, jamais l'ordre des lignes de la source.
    for (_,season,rd),group in data.sort_values(['race_date','season','round','driver_id']).groupby(['race_date','season','round'],sort=False):
        # Si les labels de la course sont incomplets, ne pas fabriquer de négatifs.
        known=group['position'].notna().all() and (group.position==1).sum()==1 and group.position.isin([1,2,3]).sum()==3
        for _,r in group.iterrows():
            dh=drivers[r.driver_id];th=teams[r.constructor_id]
            row={k:r[k] for k in ['season','round','driver_id','constructor_id','circuit_id','race_date']}
            row.update(driver_history_n=len(dh),driver_pos5=mean([v[0] for v in dh]),
                       driver_points5=mean([v[1] for v in dh]),
                       driver_win5=mean([float(v[0]==1) if pd.notna(v[0]) else np.nan for v in dh]),
                       driver_podium5=mean([float(v[0] in (1,2,3)) if pd.notna(v[0]) else np.nan for v in dh]),
                       team_history_n=len(th),team_points5=mean([v[0] for v in th]),team_pos5=mean([v[1] for v in th]),
                       win=int(r.position==1) if known else None,podium=int(r.position in (1,2,3)) if known else None)
            rows.append(row)
        # Seulement après avoir produit les variables de TOUS les pilotes de la manche.
        for _,r in group.iterrows(): drivers[r.driver_id].append((r.position,r.points))
        for team,g in group.groupby('constructor_id'):
            total=float(g.points.sum()) if g.points.notna().all() else np.nan
            teams[team].append((total,mean(g.position)))
    return pd.DataFrame(rows)
