"""Transformations pures utilisées par le dashboard."""
import pandas as pd

def season_data(data,season):
    return {name:df.loc[df['season']==season].copy() for name,df in data.items()}

def standings_at(df,rd):
    available=df.loc[df['round']<=rd]
    if available.empty:
        return available, None
    actual=int(available['round'].max())
    return available.loc[available['round']==actual].sort_values('position',na_position='last'),actual

def qualifying_gap(df):
    out=df.copy()
    # Comparer uniquement les pilotes de la même séance.
    for col in ('q1_seconds','q2_seconds','q3_seconds'):
        values=pd.to_numeric(out[col],errors='coerce')
        out[col.replace('_seconds','_gap')]=values-values.min()
    return out
