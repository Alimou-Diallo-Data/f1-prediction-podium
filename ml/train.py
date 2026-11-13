"""python -m ml.train : validation 2023 ; --evaluate-test RUN : test explicite 2024."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import platform
import uuid
import joblib
import numpy as np
import pandas as pd
import sklearn
from threadpoolctl import threadpool_limits
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import log_loss,brier_score_loss,average_precision_score,roc_auc_score
from dashboard.repository import load_snapshot,ROOT
from ml.features import build_features,FEATURES,NUMERIC,CATEGORICAL


def candidates():
    return {'baseline':DummyClassifier(strategy='prior'),
            'logistic':LogisticRegression(max_iter=2000,random_state=42),
            'random_forest':RandomForestClassifier(n_estimators=250,max_depth=7,min_samples_leaf=8,random_state=42,n_jobs=2),
            'gradient_boosting':HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=15,l2_regularization=2,
                                                              early_stopping=False,random_state=42)}

def pipeline(estimator):
    numeric=Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                      ('scale',StandardScaler())])
    categorical=Pipeline([('impute',SimpleImputer(strategy='most_frequent')),
                          ('encode',OneHotEncoder(handle_unknown='ignore',sparse_output=False))])
    return Pipeline([('prepare',ColumnTransformer([('num',numeric,NUMERIC),('cat',categorical,CATEGORICAL)])),('model',estimator)])

def score(y,p):
    return {'log_loss':float(log_loss(y,p,labels=[0,1])),
            'brier':float(brier_score_loss(y,p)),
            'average_precision':float(average_precision_score(y,p)) if y.nunique()>1 else None,
            'roc_auc':float(roc_auc_score(y,p)) if y.nunique()>1 else None}

def dataset(data,last):
    results=data['results'].loc[data['results'].season<=last]
    races=data['races'].loc[data['races'].season<=last]
    df=build_features(results,races)
    return df

def digest(frame):
    return hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()

def train(data,output):
    # Ne lit pas les résultats 2024 pour choisir ou entraîner un modèle.
    df=dataset(data,2023)
    missing=set(range(2018,2024))-set(df.season)
    if missing: raise ValueError(f'Saisons absentes : {sorted(missing)}')
    train=df.loc[df.season.between(2018,2022)].dropna(subset=['win','podium'])
    val=df.loc[df.season==2023].dropna(subset=['win','podium'])
    if train.empty or val.empty: raise ValueError('Entraînement ou validation vide')
    output.mkdir(parents=True,exist_ok=False)
    records=[]; selected={}
    for target in ['win','podium']:
        if train[target].nunique()!=2: raise ValueError('Cible sans deux classes')
        fitted={}
        for name,estimator in candidates().items():
            model=pipeline(estimator)
            with threadpool_limits(limits=2):
                model.fit(train[FEATURES],train[target].astype(int))
                p=model.predict_proba(val[FEATURES])[:,1]
            metrics=score(val[target],p)
            records.append(dict(target=target,model=name,**metrics))
            fitted[name]=model
            print(f'{target} · {name} · log-loss {metrics["log_loss"]:.4f}',flush=True)
        winner=min((r for r in records if r['target']==target),key=lambda r:(r['log_loss'],r['model']))['model']
        selected[target]=winner
        joblib.dump(fitted[winner],output/f'{target}.joblib')
    pd.DataFrame(records).to_csv(output/'validation.csv',index=False)
    # Instantané auditable des données préparées, sans la saison de test.
    df.to_csv(output/'features_development.csv',index=False)
    manifest=dict(created_at=datetime.now(timezone.utc).isoformat(),selected=selected,
                  train_seasons=list(range(2018,2023)),validation_season=2023,test_season=2024,
                  training_rows=len(train),validation_rows=len(val),excluded_label_rows=int(df.win.isna().sum()),
                  feature_columns=FEATURES,feature_sha256=digest(df),sklearn=sklearn.__version__,python=platform.python_version(),
                  protocol='before_qualifying; rolling previous 5 events; retrospective entrants; frozen model',
                  targets=['win','podium'])
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Rapport et modèles : {output}',flush=True)
    return manifest

def evaluate(data,output):
    if (output/'test.json').exists(): raise ValueError('Test déjà effectué pour cette exécution ; consulter test.json')
    meta=json.loads((output/'manifest.json').read_text())
    if meta['sklearn']!=sklearn.__version__: raise ValueError('Version scikit-learn différente de l’entraînement')
    development=dataset(data,2023)
    if digest(development)!=meta['feature_sha256']: raise ValueError('Données de développement modifiées : réentraîner avant le test')
    frame=dataset(data,2024)
    test=frame.loc[frame.season==2024].dropna(subset=['win','podium'])
    if test.empty: raise ValueError('Aucune donnée test 2024')
    report={'season':2024,'rows':len(test),'metrics':{},'evaluated_at':datetime.now(timezone.utc).isoformat()}
    predictions=test[['season','round','driver_id','win','podium']].copy()
    for target in ['win','podium']:
        # Charger UNIQUEMENT les modèles locaux créés par cette commande.
        model=joblib.load(output/f'{target}.joblib')
        with threadpool_limits(limits=2):
            p=model.predict_proba(test[FEATURES])[:,1]
        report['metrics'][target]=score(test[target],p)
        predictions[f'p_{target}']=p
    predictions.to_csv(output/'test_predictions.csv',index=False)
    (output/'test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluate-test',metavar='RUN',help='Nom du dossier local affiché après entraînement')
    args=parser.parse_args()
    try:
        data=load_snapshot()
        if args.evaluate_test:
            if Path(args.evaluate_test).name!=args.evaluate_test: raise ValueError('Utiliser le nom du dossier dans models, sans chemin')
            evaluate(data,ROOT/'models'/args.evaluate_test)
        else:
            name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6]
            train(data,ROOT/'models'/name)
            print(f'Test final séparé : python -m ml.train --evaluate-test {name}')
    except Exception as exc:
        raise SystemExit(f'Échec ML ({type(exc).__name__}) : {str(exc)}') from None

if __name__=='__main__': main()
