#!/usr/bin/env python3
"""Build/check an immutable CSP hash allowlist from FIRST-PARTY source templates.

Never hash rendered responses: hashing response HTML would accidentally authorize
attacker-supplied <script> elements in case a future XSS escapes HTML encoding.
Only code literals in api/app.py and audited static templates are sources.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'api/services/csp_script_hashes.json'
PATTERN = re.compile(r'<script\b([^>]*)>(.*?)</script\s*>', re.I | re.S)


def hashes() -> list[str]:
    source = (ROOT / 'api/app.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    chunks = [node.value for node in ast.walk(tree)
              if isinstance(node, ast.Constant) and isinstance(node.value, str)
              and '<script' in node.value.lower()]
    # The Grow Guide is a trusted first-party template. Do not read imported or
    # database-supplied content to calculate CSP permissions.
    chunks.append((ROOT / 'api/static/grow-guide-page.html').read_text(encoding='utf-8'))
    results = set()
    for chunk in chunks:
        for match in PATTERN.finditer(chunk):
            if re.search(r'\bsrc\s*=', match.group(1), re.I):
                continue
            body = match.group(2)
            if body.strip():
                digest = base64.b64encode(hashlib.sha256(body.encode('utf-8')).digest()).decode('ascii')
                results.add('sha256-' + digest)
    if len(results) < 10:
        raise RuntimeError(f'Expected at least 10 trusted inline scripts, found {len(results)}')
    return sorted(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if generated manifest differs')
    args = parser.parse_args()
    content = json.dumps({'hashes': hashes()}, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding='utf-8') != content:
            print('CSP hash manifest stale: run python scripts/generate_csp_hashes.py')
            return 1
        print('CSP hash manifest matches trusted source templates')
    else:
        TARGET.write_text(content, encoding='utf-8')
        print(f'Wrote {TARGET.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
