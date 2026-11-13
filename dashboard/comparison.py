"""Comparaisons descriptives ; aucune reconstitution du classement officiel."""
import pandas as pd


def subset(frame,entity,ident,rd):
    return frame.loc[(frame[entity]==ident)&(frame['round']<=rd)].copy()


def summary(results,sprints):
    positions=pd.to_numeric(results['position'],errors='coerce')
    def points(frame):
        values=pd.to_numeric(frame['points'],errors='coerce')
        return float(values.sum()) if len(values) and values.notna().all() else None
    return {'Courses avec résultat':int(results['round'].nunique()),
            'Résultats de pilotes':len(results),
            'Victoires en GP':int((positions==1).sum()),
            'Podiums en GP':int(positions.isin([1,2,3]).sum()),
            'Points en GP':points(results),
            'Points en sprint':points(sprints),
            'Position moyenne en GP':float(positions.mean()) if positions.notna().any() else None,
            'Positions connues':int(positions.notna().sum())}


def race_duel(left,right):
    # Pilotes uniquement ; comparer les seules manches avec deux positions connues.
    pair=left[['round','position']].merge(right[['round','position']],on='round',suffixes=('_a','_b'))
    for col in ('position_a','position_b'):
        pair[col]=pd.to_numeric(pair[col],errors='coerce')
    pair=pair.dropna()
    return dict(a=int((pair.position_a<pair.position_b).sum()),
                b=int((pair.position_b<pair.position_a).sum()),
                ties=int((pair.position_a==pair.position_b).sum()),total=len(pair))


def qualifying_duel(left,right,session):
    # Pour une écurie, meilleur temps connu parmi ses pilotes dans la même séance.
    col=session.lower()+'_seconds'
    def best(frame):
        frame=frame[['round',col]].copy()
        frame[col]=pd.to_numeric(frame[col],errors='coerce')
        return frame.groupby('round',as_index=False)[col].min()
    paired=best(left).merge(best(right),on='round',suffixes=('_a','_b')).dropna()
    paired['delta_seconds']=paired[col+'_a']-paired[col+'_b']
    return paired


def points_by_round(left,right,label_a,label_b):
    rows=[]
    for frame,label in ((left,label_a),(right,label_b)):
        frame=frame.copy(); frame['points']=pd.to_numeric(frame['points'],errors='coerce')
        for rd,group in frame.groupby('round'):
            rows.append({'Manche':rd,'Entité':label,
                         'Points GP':group.points.sum() if group.points.notna().all() else None})
    return pd.DataFrame(rows,columns=['Manche','Entité','Points GP'])
