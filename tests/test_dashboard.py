import unittest
from unittest.mock import patch
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from dashboard.analytics import standings_at,qualifying_gap
from dashboard.repository import DatabaseUnavailable

APP=Path(__file__).resolve().parents[1]/'app.py'

def fixture():
    result=pd.DataFrame([dict(season=2024,round=1,driver_id='d',constructor_id='c',driver='Pilote Test',constructor='Écurie Test',
        position=1,grid=2,points=25.5,laps=50,status='Finished')])
    q=result[['season','round','driver_id','driver','constructor','position']].copy()
    q['q1_seconds']=81.0; q['q2_seconds']=80.5; q['q3_seconds']=None
    ds=result[['season','round','driver_id','driver','position','points']].copy(); ds['wins']=1
    cs=result[['season','round','constructor','position','points']].copy(); cs['wins']=1
    return {'races':pd.DataFrame([dict(season=2024,round=1,name='GP Test',race_date='2024-01-01',circuit='Test',country='Test'),
                                  dict(season=2024,round=2,name='GP Futur',race_date='2024-02-01',circuit='Test',country='Test')]),
            'results':result,'sprint_results':result.iloc[:0].copy(),'qualifying':q,
            'driver_standings':ds,'constructor_standings':cs,
            'runs':pd.DataFrame([dict(season=2024,finished_at='2024-01-02',status='success')])}

class DashboardTests(unittest.TestCase):
    def tearDown(self):
        import streamlit as st
        st.cache_data.clear()
    def test_gap_same_session(self):
        q=pd.DataFrame({'q1_seconds':[81,82],'q2_seconds':[80,None],'q3_seconds':[None,None]})
        out=qualifying_gap(q)
        self.assertEqual(out.q1_gap.tolist(),[0,1])
        self.assertTrue(out.q3_gap.isna().all())
    def test_standings_no_future(self):
        df=pd.DataFrame({'round':[1,2],'position':[2,1],'points':[1.5,30]})
        result,rd=standings_at(df,1)
        self.assertEqual(rd,1); self.assertEqual(result.points.tolist(),[1.5])
        empty,rd=standings_at(df,0)
        self.assertTrue(empty.empty); self.assertIsNone(rd)
    def test_ui_filters_and_missing_results(self):
        with patch('dashboard.repository.load_snapshot',return_value=fixture()):
            app=AppTest.from_file(str(APP)).run(timeout=20)
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value,'2')
            app.radio[0].set_value('Q3').run()
            self.assertFalse(app.exception)
            app.multiselect[0].set_value(['Écurie Test']).run()
            self.assertFalse(app.exception)
            app.selectbox[1].select(2).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Résultats indisponibles' in x.value for x in app.info))

    def test_empty_database(self):
        data=fixture(); data['races']=data['races'].iloc[:0]
        with patch('dashboard.repository.load_snapshot',return_value=data):
            app=AppTest.from_file(str(APP)).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Aucune course' in x.value for x in app.info))
    def test_connection_failure(self):
        with patch('dashboard.repository.load_snapshot',side_effect=DatabaseUnavailable('Base inaccessible')):
            app=AppTest.from_file(str(APP)).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.error[0].value,'Base inaccessible')

if __name__=='__main__': unittest.main()
