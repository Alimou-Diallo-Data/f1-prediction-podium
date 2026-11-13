import unittest
from unittest.mock import patch
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from dashboard.comparison import summary,race_duel,qualifying_duel,subset
from test_dashboard import fixture

class ComparisonTests(unittest.TestCase):
    def tearDown(self):
        import streamlit as st
        st.cache_data.clear()
    def test_partial_points_not_zero(self):
        frame=pd.DataFrame({'round':[1,2],'position':[1,None],'points':[0.5,None]})
        s=summary(frame,frame.iloc[:0])
        self.assertIsNone(s['Points en GP']); self.assertIsNone(s['Points en sprint'])
        self.assertEqual(s['Podiums en GP'],1)
        self.assertEqual(s['Positions connues'],1)
    def test_common_known_positions(self):
        a=pd.DataFrame({'round':[1,2,3],'position':[1,4,None]})
        b=pd.DataFrame({'round':[1,3,4],'position':[2,1,1]})
        self.assertEqual(race_duel(a,b),dict(a=1,b=0,ties=0,total=1))
    def test_team_best_same_session(self):
        a=pd.DataFrame({'round':[1,1,2],'q2_seconds':[81,80,None]})
        b=pd.DataFrame({'round':[1,2],'q2_seconds':[80.5,79]})
        self.assertEqual(qualifying_duel(a,b,'Q2')['delta_seconds'].tolist(),[-0.5])
    def test_scope(self):
        frame=pd.DataFrame({'driver_id':['a','a','b'],'round':[1,2,1]})
        self.assertEqual(len(subset(frame,'driver_id','a',1)),1)
    def test_ui_driver_and_constructor(self):
        data=fixture()
        for name in ['results','sprint_results','qualifying','driver_standings','constructor_standings']:
            first=data[name]
            if first.empty: continue
            second=first.copy()
            for col,val in [('driver_id','e'),('driver','Second Pilote'),('constructor_id','other'),('constructor','Seconde Écurie')]:
                if col in second: second[col]=val
            if name=='qualifying':
                first=first.assign(constructor_id='c');second=second.assign(constructor_id='other')
            second['position']=2
            data[name]=pd.concat([first,second],ignore_index=True)
        with patch('dashboard.repository.load_snapshot',return_value=data):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=20)
            self.assertFalse(app.exception)
            app.radio(key='comparison_scope').set_value('Courses communes').run()
            self.assertFalse(app.exception)
            app.radio(key='comparison_kind').set_value('Écuries').run()
            self.assertFalse(app.exception)
            app.radio(key='duel_session').set_value('Q3').run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Aucun temps connu' in i.value for i in app.info))
