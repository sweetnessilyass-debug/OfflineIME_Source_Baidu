"""Inspect publication blobs and commit metadata without displaying secret values."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FILES = {
    '.gitignore', '.gitattributes', '.githooks/pre-commit', '.githooks/pre-push',
    'README.md', 'LICENSE', 'NOTICE.md', 'prepare.py', 'resource-manifest.json',
    'docs/BUILD.md', 'docs/CHANGES.md', 'docs/PRIVACY.md',
    'scripts/build_experiment.py', 'scripts/commercial_cleanup.py',
    'scripts/DexPatch.java', 'scripts/publish_check.py',
    'java/local/baiduoffline/SetupActivity.java',
    'java/local/baiduoffline/OfflineAssets.java',
    'java/local/baiduoffline/OfflineNetwork.java',
    'java/local/baiduoffline/OfflineMenus.java',
    'java/local/baiduoffline/OfflineSettings.java',
    'java/local/baiduoffline/CoreCompatibility.java',
}
IDENTITY = ('Contributors', 'contributors@users.invalid')
PATTERNS = {
    'absolute Windows path': re.compile(r'(?i)\b[a-z]:[\\/]'),
    'personal home path': re.compile(r'/(?:home|Users)/[^\s/]+/'),
    'private key': re.compile(r'-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----'),
    'GitHub credential': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b'),
    'access key': re.compile(r'\bAKIA[A-Z0-9]{16}\b'),
    'email address': re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
    'network address': re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])'),
    'MAC address': re.compile(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b'),
    'URL credential': re.compile(r'https?://[^\s/]+:[^\s/]+@'),
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def denied_values():
    filename = os.environ.get('PUBLISH_DENYLIST_FILE')
    if not filename:
        return []
    values = json.loads(Path(filename).read_text(encoding='utf-8'))
    if not isinstance(values, list) or any(not isinstance(v, str) or len(v) < 3 for v in values):
        raise SystemExit('Invalid private denylist')
    return [v.casefold() for v in values]


def scan(text, denied):
    failures = []
    for label, pattern in PATTERNS.items():
        matches = pattern.findall(text)
        if label == 'email address':
            matches = [value for value in matches if value != IDENTITY[1]]
        if label == 'network address':
            matches = [value for value in matches if value != '13.3.16.2']
        if matches:
            failures.append(label)
    if any(re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', text.casefold()) for value in denied):
        failures.append('private denylist match')
    return failures


def inspect(history=False):
    denied = denied_values()
    failures, seen = [], set()
    revisions = git('rev-list', '--all').decode().splitlines() if history else [None]
    if not revisions:
        raise SystemExit('No revisions found')
    for revision in revisions:
        if revision:
            raw = git('cat-file', 'commit', revision).decode('utf-8')
            metadata, message = raw.split('\n\n', 1)
            for role in ('author', 'committer'):
                match = re.search(r'^' + role + r' (.*?) <([^>]+)> \d+ [+-]\d{4}$', metadata, re.M)
                if not match or match.groups() != IDENTITY:
                    failures.append('Commit has unexpected ' + role + ' identity')
            if any(line.startswith(('gpgsig ', 'mergetag ')) for line in metadata.splitlines()):
                failures.append('Commit contains unexpected signing metadata')
            failures.extend('Commit message: ' + item for item in scan(message, denied))
        records = git('ls-tree', '-rz', revision) if revision else git('ls-files', '--stage', '-z')
        for record in records.split(b'\0'):
            if not record:
                continue
            header, name = record.split(b'\t', 1)
            name = name.decode('utf-8')
            fields = header.decode().split()
            mode, oid = (fields[0], fields[2]) if revision else (fields[0], fields[1])
            if (name, oid, mode) in seen:
                continue
            seen.add((name, oid, mode))
            if name not in PUBLIC_FILES or mode not in {'100644', '100755'}:
                failures.append('Unexpected path or file mode (value withheld)')
                continue
            if int(git('cat-file', '-s', oid)) > 262144:
                failures.append(name + ': oversized publication file')
                continue
            data = git('cat-file', 'blob', oid)
            try:
                text = data.decode('utf-8')
            except UnicodeDecodeError:
                failures.append(name + ': binary content')
                continue
            if '\0' in text:
                failures.append(name + ': binary content')
            failures.extend(name + ': ' + item for item in scan(text, denied))
    if not seen:
        failures.append('No source files found')
    if failures:
        print('\n'.join(sorted(set(failures))), file=sys.stderr)
        raise SystemExit('Publication check failed; sensitive values were withheld')
    print(f'Publication check passed: {len(seen)} source versions inspected')


if __name__ == '__main__':
    if sys.argv[1:] not in ([], ['--history']):
        raise SystemExit('Usage: python scripts/publish_check.py [--history]')
    inspect('--history' in sys.argv)
