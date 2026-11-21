"""Pot labels in a single-tent analysis JSON/ZIP originate from config only."""
import ast
from contextlib import contextmanager
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from datetime import timezone
from fastapi.responses import Response
from services.analysis_archive import make_analysis_zip
from test_analysis_export import END, exporter, reading
from test_vpd_source import Database

ROOT = Path(__file__).parents[1]


def _function(name):
    node = next(n for n in ast.parse((ROOT/'api/app.py').read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list=[]
    return compile(ast.Module(body=[node],type_ignores=[]),'api/app.py','exec')


class TentDatabase:
    def __init__(self):
        self.sql=[]
    @contextmanager
    def connection(self):
        yield self
    @contextmanager
    def cursor(self):
        yield self
    def execute(self,sql,args):
        self.sql.append((sql,args))
    def fetchone(self):
        # Deliberately include a password and RTSP credentials to ensure they
        # never escape the backend in a snapshot.
        return (2, 'Zelt Süd', 'http://device/api/state',
                'rtsp://cam:secret@camera/live', 'shelly_user', 'shelly_password',
                '{"pot1":"Oreoz", "pot2":"Blue Dream", "pot3":""}')


def test_tent_lookup_loads_only_requested_tent_and_returns_three_assignments():
    db=TentDatabase()
    ns={'get_conn':db.connection, 'json':json,
        'POT_STRAIN_KEYS':('pot1','pot2','pot3')}
    for name in ('_normalise_pot_strains','get_tent_by_id'):
        exec(_function(name),ns)
    result=ns['get_tent_by_id'](2)
    assert db.sql[0][1]==(2,)
    assert 'WHERE id=%s' in db.sql[0][0]
    assert 'pot_strains_json' in db.sql[0][0]
    assert result['pot_strains']=={'pot1':'Oreoz','pot2':'Blue Dream','pot3':''}
    assert result['name']=='Zelt Süd'
    assert result['_shelly_main_password']=='shelly_password'


def test_analysis_json_and_zip_keep_tent_assignments_not_historical_guesses():
    # The export is scoped to the selected tent; no other tent data is copied.
    old=(END.replace(tzinfo=timezone.utc))
    db=Database([(old.replace(hour=old.hour-1),reading(**{
        'settings.grow.currentPhase':2,
        'settings.grow.currentPhaseWeek':6,
    }))])
    response=exporter(db)(2,'24h')
    original=json.loads(response.body)
    assert original['pot_strains']=={'pot1':'Oreoz','pot2':'White Widow','pot3':''}
    assert original['pot_strains_source']=='current_tent_configuration'
    assert all('pot_strains' not in p for p in original['points'])
    assert 'pot_strains' not in (original['context_last'] or {})
    archive=make_analysis_zip(response.body,'growtent-2_24h.json',None)
    with ZipFile(BytesIO(archive)) as z:
        wrapped=json.loads(z.read('growtent-2_24h.json'))
        assert wrapped['pot_strains']==original['pot_strains']
        assert wrapped['tent_name']==original['tent_name']
        assert wrapped['pot_strains_source']==original['pot_strains_source']


def test_empty_assignments_are_not_inferred_from_measurements():
    db=Database([(END.replace(minute=0),reading())])
    # The exported metadata is always config state; it never derives a value
    # from a measured climate record or a strain catalog match.
    output=exporter(db)(2,'1h')
    assert json.loads(output.body)['pot_strains']['pot3']==''
