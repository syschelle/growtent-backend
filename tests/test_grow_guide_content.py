"""Static regression for the full, bilingual, read-only Grow-Guide."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'api' / 'static'


def test_complete_bilingual_reference():
    for lang in ('de', 'en'):
        source = (ROOT / 'docs' / f'grow-guide-{lang}.md').read_text(encoding='utf-8')
        rendered = (STATIC / f'grow-guide-{lang}.html').read_text(encoding='utf-8')
        headings = re.findall(r'^## (.+)$', source, re.M)
        assert len(headings) == 20
        assert len(re.findall(r'class="guide-section"', rendered)) == 20
        assert len(re.findall(r'<table>', rendered)) >= 5
        assert len(re.findall(r'<a target="_blank" rel="noopener noreferrer"', rendered)) == 13
        assert all(f'id="guide-{lang}-{i}"' in rendered for i in range(1, 21))
    assert 'Blüte Woche 5–7' in (ROOT / 'docs' / 'grow-guide-de.md').read_text(encoding='utf-8')
    assert 'Flowering weeks 5–7' in (ROOT / 'docs' / 'grow-guide-en.md').read_text(encoding='utf-8')


def test_template_retains_framework_without_any_esp_writes():
    html = (STATIC / 'grow-guide-page.html').read_text(encoding='utf-8')
    source = (ROOT / 'api' / 'app.py').read_text(encoding='utf-8')
    assert 'def grow_guide_page(request: Request):' in source
    assert 'url="/app?page=grow-guide"' in source
    assert 'guide_assets / "grow-guide-de.html"' in source
    assert 'guide_assets / "grow-guide-en.html"' in source
    assert 'gt_lang' in html and 'gt_theme' in html
    assert 'guideLangToggle' in html and 'guideSearch' in html
    assert 'fetch(' not in html and 'POST' not in html and 'PATCH' not in html
    assert 'Die Angaben sind Orientierungswerte' in html
