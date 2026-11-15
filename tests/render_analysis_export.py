"""Production analysis-export dialog fixture without live backend/device access."""
import json,sys
from pathlib import Path
from test_irrigation_ui_runtime import render,extract_scripts
from render_target_editors import StaticHTML

def fixture():
    html=render('dashboard_page');js='\n'.join(extract_scripts(html))
    a=js.index('          // Compact analysis export;');b=js.index('          function applyGuestModeUi',a)
    return {'html':''.join(StaticHTML(html).parts),'js':"let currentTentId=2,currentLang='de';\n"+js[a:b]}
if __name__=='__main__':Path(sys.argv[1]).write_text(json.dumps(fixture()),encoding='utf-8')
