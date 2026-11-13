import unittest
from decimal import Decimal
from etl.pipeline import Client, Dataset, number, seconds, extract

class Tests(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(seconds('1:23.456'),Decimal('83.456'))
        self.assertIsNone(seconds(None))
        with self.assertRaises(ValueError): seconds('0')
    def test_missing_points(self):
        self.assertIsNone(number(None,Decimal))
        self.assertEqual(number('0.5',Decimal),Decimal('0.5'))
    def test_duplicates(self):
        ds=Dataset()
        ds.add('constructors',constructor_id='a',name='A')
        ds.add('constructors',constructor_id='a',name='A')
        self.assertEqual(ds.count,1)
        with self.assertRaises(ValueError): ds.add('constructors',constructor_id='a',name='B')
    def test_nested_pagination(self):
        class Fake(Client):
            def __init__(self): self.offsets=[]
            def page(self,ep,offset):
                self.offsets.append(offset)
                return {'total':'3','RaceTable':{'Races':[{'Results':list(range(2 if offset==0 else 1))}]}}
        c=Fake()
        self.assertEqual(len(list(c.rows('x','RaceTable','Races','Results'))),3)
        self.assertEqual(c.offsets,[0,2])
    def test_incomplete(self):
        class Fake(Client):
            def __init__(self): pass
            def page(self,ep,offset): return {'total':'3','RaceTable':{'Races':[]}}
        with self.assertRaises(ValueError): list(Fake().rows('x','RaceTable','Races'))
    def test_changed_total(self):
        class Fake(Client):
            def __init__(self): pass
            def page(self,ep,offset):
                return {'total':str(3 if offset==0 else 4),'RaceTable':{'Races':[{}]}}
        with self.assertRaises(ValueError): list(Fake().rows('x','RaceTable','Races'))

class ExtractionTests(unittest.TestCase):
    def test_full_season_fixture(self):
        driver={'driverId':'d','givenName':'D','familyName':'Test'}
        constructor={'constructorId':'c','name':'C'}
        race={'season':'2024','round':'1','raceName':'Test GP','date':'2024-03-01',
              'Circuit':{'circuitId':'track','circuitName':'Track','Location':{'country':'X'}}}
        class Fake:
            def rows(self,ep,table,group,nested=None):
                if ep=='2024': return iter([race])
                if ep.endswith('/results'):
                    return iter([(race,{'Driver':driver,'Constructor':constructor,'position':'1','points':'0.5','grid':'0','status':'Finished'})])
                if ep.endswith('/qualifying'):
                    return iter([(race,{'Driver':driver,'Constructor':constructor,'position':'1','Q1':'1:20.001'})])
                if ep.endswith('/driverstandings'):
                    return iter([({'season':'2024','round':'1'},{'Driver':driver,'position':'1','points':'0.5','wins':'1'})])
                if ep.endswith('/constructorstandings'):
                    return iter([({'season':'2024','round':'1'},{'Constructor':constructor,'position':'1','points':'0.5','wins':'1'})])
                return iter([])
        ds=extract(Fake(),2024)
        self.assertEqual(len(ds.tables['races']),1)
        result=next(iter(ds.tables['results'].values()))
        self.assertEqual(result['points'],Decimal('0.5'))
        self.assertIsNone(result['laps'])
        self.assertEqual(len(ds.tables['driver_standings']),1)
        self.assertEqual(len(ds.tables['sprint_results']),0)
        self.assertEqual(ds.tables['qualifying'][(2024,1,'d')]['q1_seconds'],Decimal('80.001'))

if __name__=='__main__': unittest.main()
