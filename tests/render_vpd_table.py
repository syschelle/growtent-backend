import json,sys
from pathlib import Path
from test_irrigation_ui_runtime import render
from render_target_editors import StaticHTML
if __name__=='__main__':Path(sys.argv[1]).write_text(json.dumps({'html':''.join(StaticHTML(render('dashboard_page')).parts),'js':(Path(__file__).parents[1]/'api/static/vpd-table.js').read_text()}),encoding='utf-8')
