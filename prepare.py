"""Verify the pinned local inputs, then decode the APK into ignored audit output."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parent
APK_HASH = 'e83a5a0f48e147e1717fd54de8f56087a628bc28643a56286bf0c3e9a01af033'
APKTOOL_HASH = 'dbf930b076c6b9be08d57c449cacefc3bdd6b71ebd59b3066fc0e1f5b14f9423'
JADX_HASH = 'fe3e12c45acf75f92369685fd02d1d7a7323385dc725680a9b98a0dac0ea554b'


def verify(path, expected, label):
    if not path.is_file():
        raise SystemExit('Missing local input: ' + label)
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected:
        raise SystemExit('Checksum mismatch: ' + label)
    print('Verified: ' + label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Only verify input and tool checksums')
    args = parser.parse_args()
    if 'JAVA_HOME' not in os.environ:
        raise SystemExit('Set JAVA_HOME to a JDK 21 installation')
    java = Path(os.environ['JAVA_HOME']) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')
    apk = ROOT / 'inputs/baiduinput_AndroidPhone_1000e.apk'
    apktool = Path(os.environ.get('APKTOOL_JAR', ROOT / 'tools/apktool_3.0.3.jar'))
    jadx = Path(os.environ.get('JADX_JAR', ROOT / 'tools/jadx-1.5.6-all.jar'))
    verify(apk, APK_HASH, 'original APK')
    verify(apktool, APKTOOL_HASH, 'Apktool 3.0.3 JAR')
    verify(jadx, JADX_HASH, 'JADX 1.5.6 all JAR')
    if args.check:
        return
    audit = ROOT / 'audit'
    audit.mkdir(exist_ok=True)
    output = audit / 'decoded'
    marker = audit / 'decoded-input.json'
    expected = {'apk_sha256': APK_HASH, 'apktool_sha256': APKTOOL_HASH}
    if output.exists():
        if marker.is_file() and json.loads(marker.read_text(encoding='utf-8')) == expected:
            print('Pinned decode already prepared')
            return
        raise SystemExit('Unverified audit/decoded exists; move it aside before preparing again')
    log = audit / 'apktool-decode.log'
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run([str(java), '-jar', str(apktool), 'd', str(apk),
                                 '-o', str(output), '-p', str(audit / 'apktool-framework')],
                                cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit('Decode failed; inspect the private audit/apktool-decode.log')
    marker.write_text(json.dumps(expected, indent=2) + '\n', encoding='utf-8')
    print('Prepared audit/decoded. Build with python scripts/build_experiment.py')


if __name__ == '__main__':
    main()
