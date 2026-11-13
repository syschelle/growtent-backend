"""Parse the actual rendered setup/dashboard JavaScript, including irrigation changes."""
import ast
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from fastapi import Request,HTTPException
from fastapi.responses import RedirectResponse


def render(name):
    source=(Path(__file__).parents[1]/'api/app.py').read_text()
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    node.decorator_list=[]
    ns={'Request':Request,'HTTPException':HTTPException,'RedirectResponse':RedirectResponse,'FAVICON_LINKS':'',
        'get_session':lambda token:{'role':'admin'}}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),ns)
    return ns[name](SimpleNamespace(query_params={'embed':'1','tent':'1'},cookies={'caop_session':'test'}))


def test_rendered_irrigation_scripts_parse_and_include_revision_and_manual_identity():
    scripts=[]
    for name in ('setup_page','dashboard_page'):
        html=render(name)
        scripts+=re.findall(r'<script\b[^>]*>(.*?)</script>',html,re.S)
        assert 'expected_revision:' in html and 'Stand veraltet' in html
        assert 'Transfer previous backend plan' in html
        assert 'if(saveButton) saveButton.disabled = !!j.stale' in html
        assert 'Plan loaded for review' in html
    subprocess.run(['node','-e',"const vm=require('node:vm');const fs=require('node:fs');JSON.parse(fs.readFileSync(0,'utf8')).forEach(code=>new vm.Script(code));"],input=json.dumps(scripts),text=True,check=True)
    dashboard=render('dashboard_page')
    assert 'sessionStorage.setItem(storageKey' in dashboard
    assert 'command_id:commandId' in dashboard
    assert 'crypto.getRandomValues' in dashboard
    assert 'retry_same_command' in dashboard
