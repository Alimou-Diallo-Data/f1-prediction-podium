"""SHAP par permutation sur les variables d'origine et la probabilité positive."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import sklearn
from threadpoolctl import threadpool_limits
from ml.features import FEATURES,CATEGORICAL
from ml.train import score

LABELS={'round':'Manche','driver_id':'Identité du pilote','constructor_id':'Écurie','circuit_id':'Circuit',
 'driver_history_n':'Historique pilote disponible (max. 5)', 'driver_pos5':'Position moyenne pilote — 5 GP précédents',
 'driver_points5':'Points moyens pilote — 5 GP précédents','driver_win5':'Fréquence de victoire — 5 GP précédents',
 'driver_podium5':'Fréquence de podium — 5 GP précédents','team_history_n':'Historique écurie disponible (max. 5)',
 'team_points5':'Points moyens écurie — 5 GP précédents','team_pos5':'Position moyenne écurie — 5 GP précédents'}

class CodedInputs:
    """Codes numériques réservés au masque ; catégories décodées avant le modèle.

    Le masquage remplace des valeurs complètes, sans interpolation des codes.
    """
    def __init__(self,background,row):
        self.categories={c:sorted(set(background[c].dropna().astype(str))|set(row[c].dropna().astype(str))) for c in CATEGORICAL}
    def encode(self,frame):
        out=frame[FEATURES].copy()
        for c in CATEGORICAL:
            mapping={v:i for i,v in enumerate(self.categories[c])}
            out[c]=out[c].map(lambda v:np.nan if pd.isna(v) else mapping[str(v)])
        return out.to_numpy(dtype=float)
    def decode(self,values):
        out=pd.DataFrame(values,columns=FEATURES)
        for c in CATEGORICAL:
            cats=self.categories[c]
            out[c]=out[c].map(lambda v:np.nan if pd.isna(v) else cats[int(v)])
        return out

def training_background(development,size=32):
    train=development.loc[development.season.between(2018,2022)].dropna(subset=['win','podium'])
    if train.empty: raise ValueError('Historique d’entraînement absent')
    return train.sample(n=min(size,len(train)),random_state=42)[FEATURES].reset_index(drop=True)

def explain_row(model,background,row,permutations=5):
    import shap
    if len(row)!=1: raise ValueError('Sélectionner exactement un pilote et une course')
    coded=CodedInputs(background,row)
    def predict(values):
        with threadpool_limits(limits=2):
            return model.predict_proba(coded.decode(values))[:,1]
    masker=shap.maskers.Independent(coded.encode(background),max_samples=len(background))
    explainer=shap.PermutationExplainer(predict,masker,feature_names=FEATURES,seed=42)
    budget=(2*len(FEATURES)+1)*permutations
    exp=explainer(coded.encode(row),max_evals=budget,silent=True)
    base=float(np.asarray(exp.base_values).reshape(-1)[0])
    values=np.asarray(exp.values)[0].astype(float)
    probability=float(predict(coded.encode(row))[0])
    residual=float(probability-base-values.sum())
    if not np.isfinite(values).all() or abs(residual)>1e-5:
        raise ValueError('Contrôle d’additivité SHAP non satisfait')
    return dict(probability=probability,base=base,contributions=values.tolist(),
                residual=residual,features=FEATURES,background_size=len(background),
                max_evals=budget,seed=42,shap_version=shap.__version__)

def load_local_model(folder,target):
    if target not in ('win','podium'): raise ValueError('Cible inconnue')
    meta=json.loads((Path(folder)/'manifest.json').read_text())
    if meta['sklearn']!=sklearn.__version__:
        raise ValueError(f"Version scikit-learn requise : {meta['sklearn']} ; installée : {sklearn.__version__}. Conserver la version d’entraînement.")
    return joblib.load(Path(folder)/f'{target}.joblib')

def baseline_report(development,test_predictions):
    train=development.loc[development.season.between(2018,2022)].dropna(subset=['win','podium'])
    if train.empty: raise ValueError('Entraînement vide')
    records=[]
    for target in ('win','podium'):
        prior=float(train[target].mean())
        records.append(dict(target=target,model='baseline_2018_2022',prior=prior,
                            **score(test_predictions[target],np.full(len(test_predictions),prior))))
    return pd.DataFrame(records)
