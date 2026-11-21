"""Production analysis-export dialog fixture without live backend/device access."""
import json,sys,base64,io,zipfile
from pathlib import Path
from test_irrigation_ui_runtime import render,extract_scripts
from render_target_editors import StaticHTML

def fixture():
    html=render('dashboard_page');js='\n'.join(extract_scripts(html))
    a=js.index('          // Compact analysis export;');b=js.index('          function applyGuestModeUi',a)
    with io.BytesIO() as stream:
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('growtent-2_2026-11-15_1200Z_24h.json', json.dumps({'schema':'growtent.analysis.v1', 'points':[], 'camera_snapshot':{'status':'included','filename':'camera.jpg'}}))
            archive.writestr('camera.jpg', b'\xff\xd8samplejpeg\xff\xd9')
        zip_b64=base64.b64encode(stream.getvalue()).decode('ascii')
    return {'html':''.join(StaticHTML(html).parts), 'js':"let currentTentId=2,currentLang='de';\n"+js[a:b], 'zip_b64':zip_b64}
if __name__=='__main__':Path(sys.argv[1]).write_text(json.dumps(fixture()),encoding='utf-8')
