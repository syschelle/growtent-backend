"""Parse the actual rendered setup/dashboard JavaScript, including irrigation changes."""
import ast
import json
from html.parser import HTMLParser
import pytest
import subprocess
from pathlib import Path
from types import SimpleNamespace
from fastapi import Request,HTTPException
from fastapi.responses import RedirectResponse


class ScriptCollector(HTMLParser):
    """Collect script raw text using HTML's tag parsing, not a filtering regexp."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.chunks = None

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.chunks = []

    def handle_data(self, data):
        if self.chunks is not None:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.chunks is not None:
            self.scripts.append(''.join(self.chunks))
            self.chunks = None


def extract_scripts(html):
    collector = ScriptCollector()
    collector.feed(html)
    collector.close()
    return collector.scripts


@pytest.mark.parametrize('opening,closing', [
    ('<script>', '</script>'),
    ('<SCRIPT>', '</SCRIPT>'),
    ('<ScRiPt>', '</sCrIpT >'),
    ('<script type="text/javascript">', '</script\n>'),
    ('<script data-example=">">', '</script >'),
])
def test_script_collector_handles_html_tag_variants(opening, closing):
    payload = 'const result = 1 < 2 && 3 > 2;\n'
    assert extract_scripts(opening + payload + closing) == [payload]


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
        extracted=extract_scripts(html)
        assert extracted, 'Rendered page must contain scripts to validate'
        scripts+=extracted
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

def test_sync_message_converts_utc_to_berlin_and_keeps_event_errors_distinct():
    html=render('dashboard_page')
    start=html.index('          function irrigationSyncMessage(')
    end=html.index('          async function openDashboardIrPlanModal(',start)
    code=html[start:end]
    js='''const vm=require('node:vm'),assert=require('node:assert/strict');
const code=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const context=vm.createContext({localStorage:{getItem:()=> 'de'},document:{documentElement:{lang:'de'}},Date,irrigationStatusText:()=> 'ESP',irrigationMessage:code=>'Error '+code});
vm.runInContext(code,context);
context.summary={stale:true,last_success_at:'2026-11-13T16:21:03.916222+00:00',error:'controller_unreachable'};
let text=vm.runInContext('irrigationSyncMessage(summary)',context);
assert.ok(text.includes('17:21:03'));assert.ok(!text.includes('T16:21'));
assert.ok(text.includes('[controller_unreachable]'));
context.summary={stale:false,last_success_at:'2026-11-13T16:21:03.916222+00:00',status:{queued_events:0}};
text=vm.runInContext('irrigationSyncMessage(summary)',context);
assert.ok(text.startsWith('Letztes Update: '));
assert.ok(!text.includes('Ereignispuffer')&&!text.includes('ESP'));
assert.ok(!text.includes('MEZ')&&!text.includes('CET')&&!text.includes('GMT'));

context.summary={stale:false,event_sync_error:'event_sequence_gap',status:{}};
text=vm.runInContext('irrigationSyncMessage(summary)',context);
assert.ok(text.includes('event_sequence_gap'));assert.ok(!text.includes('Stand veraltet'));
'''
    subprocess.run(['node','-e',js],input=json.dumps(code),text=True,check=True)
