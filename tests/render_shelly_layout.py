"""Isolated production dashboard markup and Shelly renderer for browser tests."""
import json
import re
import sys
from pathlib import Path
from test_irrigation_ui_runtime import render, extract_scripts
from render_target_editors import StaticHTML


def fixture():
    html = render('dashboard_page')
    script = '\n'.join(extract_scripts(html))
    names = ('finiteNumber', 'normalizeShellyDeviceFromPayload', 'shellyIcon',
             'shellyName', 'formatShellyChangeTime', 'renderShellyDevices')
    functions = []
    for name in names:
        # All these functions are top-level dashboard functions with the same indentation.
        match = re.search(r'^          function ' + name + r'\(.*?^          }', script, re.M | re.S)
        assert match, name
        functions.append(match.group())
    i18n = script[script.index('          const I18N = {'):script.index('          let currentLang')]
    return {'html': ''.join(StaticHTML(html).parts), 'js': i18n + '\n' + '\n'.join(functions)}


if __name__ == '__main__':
    Path(sys.argv[1]).write_text(json.dumps(fixture()), encoding='utf-8')
