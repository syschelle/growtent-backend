"""Per-tent pot markers: safe persistence, display and same-frame ZIP rendering."""
import ast
from contextlib import contextmanager
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import ValidationError
from models.schemas import CameraPositionsPayload
from services.pot_markers import normalize_pot_positions, draw_marked_camera_jpeg
from services.analysis_archive import make_analysis_zip, CAMERA_MARKED_FILENAME

ROOT = Path(__file__).parents[1]
POS = {'pot1':{'x':.24,'y':.73},'pot2':{'x':.56,'y':.58},'pot3':None}
STR = {'pot1':'Oreoz','pot2':'White Widow','pot3':''}


def _jpg(width=800, height=450):
    with BytesIO() as b:
        Image.new('RGB', (width, height), (75, 100, 115)).save(b, 'JPEG', quality=92)
        return b.getvalue()


def _isolated(name, ns):
    fn=next(n for n in ast.parse((ROOT/'api/app.py').read_text()).body
            if isinstance(n,ast.FunctionDef) and n.name==name)
    fn.decorator_list=[]
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'api/app.py','exec'),ns)
    return ns[name]


def test_normalization_rejects_missing_nan_invalid_out_of_range_or_bool():
    assert normalize_pot_positions({})=={'pot1':None,'pot2':None,'pot3':None}
    assert normalize_pot_positions('{"pot1":{"x":0.25,"y":0.75}}')['pot1']=={'x':.25,'y':.75}
    assert normalize_pot_positions({'pot1':{'x':float('nan'),'y':.5},'pot2':{'x':True,'y':0},'pot3':{'x':1.2,'y':0}})=={'pot1':None,'pot2':None,'pot3':None}
    assert normalize_pot_positions('invalid')['pot1'] is None


@pytest.mark.parametrize('payload',[
    {'pot1':{'x':-0.1,'y':0.5}},
    {'pot1':{'x':0.2,'y':1.1}},
    {'pot1':{'x':float('inf'),'y':.5}},
    {'pot1':{'x':float('nan'),'y':.5}},
    {'pot1':{'x':.5,'y':.5,'z':100}},
    {'pot1':{'x':.5,'y':.5},'pot4':{'x':.5,'y':.5}},
])
def test_position_schema_rejects_outside_image_and_unknown_slots(payload):
    with pytest.raises(ValidationError):CameraPositionsPayload.model_validate(payload)


class FakeDB:
    def __init__(self):self.calls=[];self.value=POS.copy();self.result=None
    @contextmanager
    def connection(self):yield self
    @contextmanager
    def cursor(self):yield self
    def execute(self,sql,args):
        self.calls.append((sql,args))
        if sql.strip().startswith('UPDATE'):
            self.result=(2,)
            self.value=json.loads(args[0])
        else:self.result=(json.dumps(self.value),json.dumps(STR))
    def fetchone(self):return self.result


def test_get_camera_positions_only_reads_selected_tent_and_labels():
    db=FakeDB()
    fn=_isolated('get_tent_camera_positions',{'get_conn':db.connection,'JSONResponse':JSONResponse,
         'normalize_pot_positions':normalize_pot_positions,'_normalise_pot_strains':lambda s:json.loads(s)})
    response=fn(2)
    data=json.loads(response.body)
    assert data['positions']==POS and data['pot_strains']==STR and data['source']=='current_tent_configuration'
    assert 'WHERE id=%s' in db.calls[0][0] and db.calls[0][1]==(2,)
    assert response.headers['cache-control']=='no-store'


def test_save_requires_admin_and_only_updates_position_field():
    db=FakeDB()
    role={'value':'guest'}
    fn=_isolated('put_tent_camera_positions',{
        'get_conn':db.connection,'get_session':lambda cookie:{'role':role['value']} if cookie else None,
        'Request':object,'HTTPException':HTTPException,'JSONResponse':JSONResponse,
        'normalize_pot_positions':normalize_pot_positions,'json':json,
        'CameraPositionsPayload':CameraPositionsPayload,
    })
    request=SimpleNamespace(cookies={'caop_session':'token'})
    payload=CameraPositionsPayload.model_validate(POS)
    with pytest.raises(HTTPException) as e:fn(2,payload,request)
    assert e.value.status_code==403 and not db.calls
    role['value']='admin'
    saved=json.loads(fn(2,payload,request).body)
    assert saved['ok'] and saved['positions']==POS
    assert len(db.calls)==1 and db.calls[0][1][1]==2
    assert db.calls[0][0].strip().startswith('UPDATE tents SET pot_positions_json=')
    assert 'hmac' not in db.calls[0][0].lower() and 'source_url' not in db.calls[0][0]


def test_archive_labels_only_saved_coordinates_and_keeps_original_and_hdr():
    original=_jpg()
    data={'schema':'growtent.analysis.v1','tentId':2,'points':[],
          'pot_strains':STR, 'pot_positions':POS,
          'pot_positions_source':'current_tent_configuration'}
    archive=make_analysis_zip(json.dumps(data).encode(),'growtent-2_24h.json',original)
    with ZipFile(BytesIO(archive)) as z:
        names=z.namelist()
        assert CAMERA_MARKED_FILENAME in names and 'camera-hdr.jpg' in names
        assert z.read('camera.jpg')==original
        jpeg=z.read(CAMERA_MARKED_FILENAME)
        with Image.open(BytesIO(jpeg)) as annotated:
            assert annotated.format=='JPEG' and annotated.size==(800,450)
            # At least one saved marker is visibly rendered; the original is uniform.
            assert annotated.getpixel((round(.24*799),round(.73*449))) != (75,100,115)
        output=json.loads(z.read('growtent-2_24h.json'))
        assert output['pot_positions']==POS
        assert output['camera_snapshot']['marked']=={
            'status':'included','filename':CAMERA_MARKED_FILENAME,
            'width_px':800,'height_px':450,'source':'current_tent_configuration'}
    assert draw_marked_camera_jpeg(original,{'pot1':None,'pot2':None,'pot3':None},STR) is None



def test_annotated_export_contains_numbers_only_without_strain_names():
    """Marker picture must never expose the strain name; JSON still does."""
    src=_jpg(960,540)
    with_strains=draw_marked_camera_jpeg(src,POS,STR)
    renamed=draw_marked_camera_jpeg(src,POS,{'pot1':'Completely different', 'pot2':'New'})
    assert with_strains is not None and renamed is not None
    assert with_strains[0]==renamed[0], 'Strain names must not be drawn into camera-marked.jpg'
    with Image.open(BytesIO(with_strains[0])) as img:
        # Former text box sat beneath the marker; it is now camera pixels.
        x=round(.24*959); y=round(.73*539)+40
        r,g,b=img.getpixel((x,y))
        assert abs(r-75)<12 and abs(g-100)<12 and abs(b-115)<12
    with ZipFile(BytesIO(make_analysis_zip(json.dumps({'tentId':2,'pot_strains':STR,
            'pot_positions':POS}).encode(),'a.json',src))) as archive:
        assert json.loads(archive.read('a.json'))['pot_strains']==STR
        assert archive.read('camera.jpg')==src

def test_no_saved_positions_does_not_generate_false_camera_marked_file():
    analysis={'tentId':2,'pot_strains':STR,'pot_positions':{'pot1':None,'pot2':None,'pot3':None}}
    with ZipFile(BytesIO(make_analysis_zip(json.dumps(analysis).encode(),'a.json',_jpg()))) as z:
        assert CAMERA_MARKED_FILENAME not in z.namelist()
        data=json.loads(z.read('a.json'))
        assert data['camera_snapshot']['marked']['status']=='not_configured'


def test_backup_and_migration_are_referenced_by_source():
    source=(ROOT/'api/app.py').read_text()
    assert 'ALTER TABLE tents ADD COLUMN IF NOT EXISTS pot_positions_json' in source
    assert '"pot_positions": normalize_pot_positions(r[16])' in source
    assert 't.get("pot_positions") or t.get("pot_positions_json")' in source
    assert 'payload["pot_positions"] = normalize_pot_positions' in source
    assert '@app.put("/tents/{tent_id}/camera-positions")' in source
    routes=(ROOT/'api/routes/tents.py').read_text()
    assert "@router.put('/tents/{tent_id}/camera-positions', dependencies=[Depends(_admin_username)])" in routes
    assert '_admin_username(request)' in routes
