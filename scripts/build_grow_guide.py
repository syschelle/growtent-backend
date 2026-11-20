"""Build static, escaped Grow-Guide HTML fragments from the bilingual Markdown sources.

Dev-only dependency: `python -m pip install 'mistune>=3,<4'`.
No Markdown renderer is needed at runtime in the API container.
"""
from pathlib import Path
import re

try:
    import mistune
except ImportError as exc:
    raise SystemExit("Install dev-only renderer with: python -m pip install 'mistune>=3,<4'") from exc

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs"
DEST = ROOT / "api" / "static"
md = mistune.create_markdown(renderer="html", plugins=["table"], escape=True)

for lang in ("de", "en"):
    text = (SRC / f"grow-guide-{lang}.md").read_text(encoding="utf-8")
    rendered = md(text)
    parts = re.split(r"(?=<h2>)", rendered)
    if len(parts) != 21:
        raise SystemExit(f"Expected 20 chapters for {lang}, got {len(parts)-1}")
    sections = [parts[0]]
    for n, part in enumerate(parts[1:], 1):
        if not part.startswith("<h2>"):
            raise SystemExit(f"Invalid heading in {lang} chapter {n}")
        sections.append(f'<section class="guide-section" id="guide-{lang}-{n}">\n{part}</section>')
    output = "\n".join(sections)
    # All hyperlinks are from the checked-in Markdown sources.
    output = output.replace('<a href="https://', '<a target="_blank" rel="noopener noreferrer" href="https://')
    (DEST / f"grow-guide-{lang}.html").write_text(output, encoding="utf-8")
    print(f"{lang}: 20 chapters, {len(output)} characters")
