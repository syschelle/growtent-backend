"""Enforce the current-only, versioned release-notes policy (standard library only)."""
import argparse
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--tag', default='')
args = parser.parse_args()
source = root / "api/app.py"
pattern = r'^APP_VERSION\s*=\s*"([^"]+)"'
match = re.search(pattern, source.read_text(encoding='utf-8'), re.MULTILINE)
if not match:
    sys.exit(f'Cannot read version from {source.relative_to(root)}')
version = match.group(1)
expected = f'RELEASE_NOTES_{version}.md'
actual = sorted(p.name for p in root.glob('RELEASE_NOTES*.md') if p.is_file())
if actual != [expected]:
    sys.exit(f'Keep only {expected}; found: {actual}')
notes = (root / expected).read_text(encoding='utf-8').strip()
if not notes or version not in notes.splitlines()[0]:
    sys.exit(f'{expected} must have a versioned title and nonempty release notes')
if args.tag and args.tag != version:
    sys.exit(f'Release tag {args.tag} does not match source version {version}')
print(f'Release notes OK: {expected}')
