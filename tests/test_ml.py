import tempfile
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import unittest
import pandas as pd
from ml.features import build_features,FEATURES
from ml.train import train,evaluate


def data():
    races=[];results=[]
    for year in range(2018,2025):
        for rd in (1,2):
            races.append(dict(season=year,round=rd,circuit_id='c',race_date=f'{year}-0{rd}-01'))
            for i in range(4):
                pos=(i+rd)%4+1
                results.append(dict(season=year,round=rd,driver_id=f'd{i}',constructor_id=f't{i//2}',
                                    position=pos,points=float(5-pos)))
    return {'races':pd.DataFrame(races),'results':pd.DataFrame(results)}

class MLTests(unittest.TestCase):
    def test_no_current_or_future_leak(self):
        source=data();base=build_features(**source)
        changed=source['results'].copy()
        changed.loc[(changed.season==2020)&(changed['round']==2),'points']=900
        after=build_features(changed,source['races'])
        cutoff=(base.season<2020)|((base.season==2020)&(base['round']<=2))
        pd.testing.assert_frame_equal(base.loc[cutoff,FEATURES],after.loc[cutoff,FEATURES])
        self.assertFalse(base.loc[~cutoff,'driver_points5'].equals(after.loc[~cutoff,'driver_points5']))
    def test_same_race_team_no_leak_and_new_driver(self):
        source=data();out=build_features(**source)
        first=out.loc[(out.season==2018)&(out['round']==1)]
        self.assertTrue(first.driver_pos5.isna().all())
        self.assertTrue(first.team_points5.isna().all())
        self.assertTrue((first.team_history_n==0).all())
        second=out.loc[(out.season==2018)&(out['round']==2)]
        self.assertTrue((second.team_history_n==1).all())
    def test_unknown_labels_excluded(self):
        source=data();source['results'].loc[0,'position']=None
        out=build_features(**source)
        self.assertTrue(out.loc[(out.season==2018)&(out['round']==1),'win'].isna().all())
    def test_train_and_separate_test(self):
        source=data()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'models'/'run'
            meta=train(source,folder)
            self.assertFalse((folder/'test.json').exists())
            self.assertEqual(meta['training_rows'],40)
            self.assertEqual(meta['validation_rows'],8)
            self.assertEqual(len(pd.read_csv(folder/'validation.csv')),8)
            self.assertNotIn(2024,pd.read_csv(folder/'features_development.csv').season.tolist())
            with patch('dashboard.ml_ui.ROOT',Path(tmp)):
                ui=AppTest.from_string('from dashboard.ml_ui import render_ml\nrender_ml()').run()
                self.assertFalse(ui.exception)
            evaluate(source,folder)
            self.assertTrue((folder/'test.json').exists())
            with patch('dashboard.ml_ui.ROOT',Path(tmp)):
                ui=AppTest.from_string('from dashboard.ml_ui import render_ml\nrender_ml()').run()
                self.assertFalse(ui.exception)
                self.assertEqual(len(ui.dataframe),2)
            probabilities=pd.read_csv(folder/'test_predictions.csv')
            self.assertTrue(probabilities.p_win.between(0,1).all())
            with self.assertRaises(ValueError): evaluate(source,folder)
