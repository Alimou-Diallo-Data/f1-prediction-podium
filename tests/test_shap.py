import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from streamlit.testing.v1 import AppTest
from test_ml import data
from ml.features import FEATURES
from ml.train import dataset,digest,pipeline
from ml.explain import CodedInputs,training_background,explain_row,baseline_report,load_local_model

class ShapTests(unittest.TestCase):
    def tearDown(self):
        import streamlit as st
        st.cache_data.clear()
    def test_category_roundtrip_and_missing(self):
        dev=dataset(data(),2023)
        bg=training_background(dev,8)
        row=bg.iloc[[0]].copy();row['driver_id']='nouveau';row['driver_pos5']=np.nan
        codec=CodedInputs(bg,row)
        back=codec.decode(codec.encode(row))
        self.assertEqual(back.iloc[0].driver_id,'nouveau')
        self.assertTrue(pd.isna(back.iloc[0].driver_pos5))
    def test_background_training_only(self):
        dev=dataset(data(),2023)
        # Une valeur de validation identifiable ne doit jamais entrer dans le fond.
        dev.loc[dev.season==2023,'driver_id']='validation_only'
        bg=training_background(dev)
        self.assertNotIn('validation_only',bg.driver_id.tolist())
        self.assertEqual(len(bg),32)
    def test_additivity_for_all_selected_model_families(self):
        frame=dataset(data(),2024)
        train=frame.loc[frame.season<=2022]
        bg=training_background(frame,8)
        row=frame.loc[frame.season==2024,FEATURES].iloc[[0]]
        for estimator in [LogisticRegression(max_iter=1000),RandomForestClassifier(n_estimators=8,random_state=42),
                          HistGradientBoostingClassifier(max_iter=5,early_stopping=False,random_state=42)]:
            from threadpoolctl import threadpool_limits
            with threadpool_limits(limits=2):
                model=pipeline(estimator).fit(train[FEATURES],train.win)
            explanation=explain_row(model,bg,row,permutations=1)
            self.assertLess(abs(explanation['residual']),1e-5)
            self.assertAlmostEqual(explanation['base']+sum(explanation['contributions']),explanation['probability'])
    def test_version_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'manifest.json').write_text(json.dumps({'sklearn':'different'}))
            with self.assertRaises(ValueError):load_local_model(tmp,'win')
    def test_baseline_uses_training_prior(self):
        frame=dataset(data(),2024)
        report=baseline_report(frame,frame.loc[frame.season==2024,['win','podium']])
        self.assertAlmostEqual(report.iloc[0]['prior'],0.25)
        self.assertAlmostEqual(report.iloc[1]['prior'],0.75)
    def test_ui_explanation_and_changed_selection(self):
        source=data()
        source['races']['name']='GP synthétique'
        source['results']['driver']=source['results'].driver_id
        development=dataset(source,2023)
        full=dataset(source,2024)
        model=pipeline(DummyClassifier(strategy='prior')).fit(development[FEATURES],development.win)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'models'/'run';folder.mkdir(parents=True)
            development.to_csv(folder/'features_development.csv',index=False)
            meta={'sklearn':sklearn.__version__,'feature_sha256':digest(development),'selected':{'win':'baseline','podium':'baseline'}}
            (folder/'manifest.json').write_text(json.dumps(meta))
            joblib.dump(model,folder/'win.joblib')
            test=full.loc[full.season==2024,['season','round','driver_id','win','podium']].copy()
            test['p_win']=0.25;test['p_podium']=0.75
            test.to_csv(folder/'test_predictions.csv',index=False)
            with patch('dashboard.shap_ui.ROOT',Path(tmp)):
                # Source injectée dans le script via un module de fixture, sans DB.
                with patch('test_ml.data',return_value=source):
                    app=AppTest.from_string('from test_ml import data\nfrom dashboard.shap_ui import render_shap\nrender_shap(data())',default_timeout=30).run()
                    self.assertFalse(app.exception)
                    app.button(key='explain_button').click().run(timeout=30)
                    self.assertFalse(app.exception)
                    self.assertEqual(app.metric[0].value,'25.00 %')
                    app.selectbox(key='shap_driver').select('d1').run()
                    self.assertFalse(app.exception)
                    self.assertEqual(len(app.metric),0)
