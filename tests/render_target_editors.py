"""Render isolated admin/guest fixtures without importing the database application."""
import json
import sys
from pathlib import Path
from test_grow_profile_modal_runtime import _render_functions, _request
from html.parser import HTMLParser

class InlineScripts(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.scripts=[]; self.inside=False; self.parts=[]; self.feed(html)
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='script': self.inside=True; self.parts=[]
    def handle_data(self, data):
        if self.inside: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=='script' and self.inside:
            self.scripts.append(''.join(self.parts)); self.inside=False

class StaticHTML(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=False); self.parts=[]; self.script=False; self.feed(html)
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='script': self.script=True
        elif not self.script:self.parts.append(self.get_starttag_text())
    def handle_endtag(self, tag):
        if tag.lower()=='script':self.script=False
        elif not self.script:self.parts.append('</'+tag+'>')
    def handle_startendtag(self, tag, attrs):
        if not self.script:self.parts.append(self.get_starttag_text())
    def handle_data(self, data):
        if not self.script:self.parts.append(data)
    def handle_entityref(self, name):
        if not self.script:self.parts.append('&'+name+';')
    def handle_charref(self, name):
        if not self.script:self.parts.append('&#'+name+';')

def fixtures():
    admin=_render_functions('admin');guest=_render_functions('guest')
    dashboard=admin['dashboard_page'](_request());scripts='\n'.join(InlineScripts(dashboard).scripts)
    start=scripts.index('          // Native target dialogs:')
    end=scripts.index('          function applyI18n(){', start)
    bindings_start=scripts.index("          const growProfileBtnEl = document.getElementById('openGrowProfileBtn');")
    bindings_end=scripts.index('          // Diagnostic export:',bindings_start)
    guest_html=guest['dashboard_page'](_request())
    label_start=scripts.index("            txt('editTemperatureTargetBtn',")
    label_end=scripts.index("            const closeGrowProfileBtn",label_start)
    i18n_start=scripts.index('          const I18N = {')
    i18n_end=scripts.index('          let currentLang',i18n_start)
    return dict(i18n_js=scripts[i18n_start:i18n_end],labels_js=scripts[label_start:label_end],dashboard=dashboard,dashboard_static=''.join(StaticHTML(dashboard).parts),guest_static=''.join(StaticHTML(guest_html).parts),guest=guest_html,editor=admin['grow_profile_page'](_request()),modal_js=scripts[start:end],bindings_js=scripts[bindings_start:bindings_end])

if __name__=='__main__':Path(sys.argv[1]).write_text(json.dumps(fixtures()),encoding='utf-8')
