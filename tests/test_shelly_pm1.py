"""Production direct reader/parser tests without a real Shelly or database."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from services.shelly_status import parse_rpc_status

PM={'id':0,'voltage':239.9,'current':0.2,'apower':46.1,'aenergy':{'total':40.7}}

class PM1Tests(unittest.TestCase):
    def test_live_and_zero(self):
        for power in [46.1,0]:
            result=parse_rpc_status({'pm1:0':{**PM,'apower':power}})
            self.assertEqual(result,{'isOn':True,'Watt':power,'Wh':40.7,'meteringOnly':True})

    def test_invalid_never_fabricates_off(self):
        for status in [{}, {'error':{'code':404}}, {'pm1:0':{}}, {'pm1:0':{**PM,'id':1}}, {'pm1:0':{**PM,'apower':None}}, {'pm1:0':{**PM,'aenergy':[]}}, {'pm1:0':{**PM,'apower':float('nan')}}]:
            self.assertIsNone(parse_rpc_status(status))
        for on in [True,False]:
            self.assertEqual(parse_rpc_status({'switch:0':{'output':on,'apower':2,'aenergy':{'total':5}}})['isOn'],on)

    def test_actual_direct_readers(self):
        tree=ast.parse((Path(__file__).parents[1]/'api/app.py').read_text())
        names={'_get_shelly_direct_state_for_key','get_main_shelly_direct_state'}
        module=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
        sample={'pm1:0':PM};urls=[]
        class Client:
            def __init__(self,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def get(self,url,**kwargs):
                urls.append(url)
                return SimpleNamespace(raise_for_status=lambda:None,json=lambda:sample)
        ns={'httpx':SimpleNamespace(Client=Client),'parse_rpc_status':parse_rpc_status,'_stored_shelly_main_password':lambda t:'','_shelly_auth_candidates':lambda *a:[None], '_extract_main_shelly_conn':lambda t:('http://192.0.2.1',3,None,{})}
        exec(compile(module,'production_direct_reader','exec'),ns)
        payload={'settings.shelly.heatmat.ip':'192.0.2.1','settings.shelly.heatmat.gen':3}
        direct=ns['_get_shelly_direct_state_for_key'](payload,{},'heatmat')
        self.assertTrue(direct['isOn']);self.assertEqual(direct['Watt'],46.1);self.assertEqual(direct['Wh'],40.7)
        main=ns['get_main_shelly_direct_state'](2)
        self.assertEqual(main['Watt'],46.1);self.assertTrue(main['isOn'])
        self.assertTrue(all(url.endswith('/rpc/Shelly.GetStatus') for url in urls))
        sample={};self.assertIsNone(ns['_get_shelly_direct_state_for_key'](payload,{},'heatmat'))
        sample={'relays':[{'ison':False}],'meters':[{'power':0,'total':5}]}
        payload['settings.shelly.heatmat.gen']=1
        self.assertFalse(ns['_get_shelly_direct_state_for_key'](payload,{},'heatmat')['isOn'])

if __name__=='__main__':unittest.main()
