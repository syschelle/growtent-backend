"""Isolated production setup fixture; no database or live services."""
import json
import sys
from pathlib import Path
from test_irrigation_ui_runtime import render, extract_scripts
from render_target_editors import StaticHTML

def fixture():
    html=render('setup_page');js='\n'.join(extract_scripts(html))
    a=js.index('          function chartRangeSettings(');b=js.index('          const isEmbed',a)
    c=js.index('          function applyChartRangesI18n(');d=js.index("          document.getElementById('saveBtn').addEventListener",c)
    return {'html':''.join(StaticHTML(html).parts),'js':"const langSel=document.getElementById('langSelect');\n"+js[a:b]+js[c:d]+'\napplyChartRangesI18n();'}
if __name__=='__main__':Path(sys.argv[1]).write_text(json.dumps(fixture()),encoding='utf-8')
