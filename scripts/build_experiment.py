"""Build a version-pinned ARM64 offline voice experiment from a local APK.

Original resources and native libraries are preserved. Compatibility metadata is
passed only to the input core initialization, without changing Android signing.
No upstream binaries, models, private keys or machine-specific paths belong in Git.
"""
from pathlib import Path
import argparse
import hashlib
import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import commercial_cleanup

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'audit/build'
BUILD.mkdir(parents=True, exist_ok=True)
LOGS = BUILD / 'logs'
LOGS.mkdir(exist_ok=True)
ORIGINAL = ROOT / 'inputs/baiduinput_AndroidPhone_1000e.apk'
EXPECTED = 'e83a5a0f48e147e1717fd54de8f56087a628bc28643a56286bf0c3e9a01af033'
DECODED = ROOT / 'audit/decoded'
SDK = Path(os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME') or
           (Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk' if os.name == 'nt' else Path.home() / 'Android/Sdk'))
JDK = Path(os.environ['JAVA_HOME']) / 'bin'
BT = SDK / 'build-tools/36.1.0'
ANDROID = SDK / 'platforms/android-36/android.jar'
JADX = Path(os.environ.get('JADX_JAR', ROOT / 'tools/jadx-1.5.6-all.jar'))
EXT = '.exe' if os.name == 'nt' else ''
PATCHES = []
DEBUG = False


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(name, args):
    print(name, flush=True)
    with (LOGS / (name + '.log')).open('w', encoding='utf-8') as log:
        result = subprocess.run([str(v) for v in args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print((LOGS / (name + '.log')).read_text(encoding='utf-8', errors='replace')[-6000:])
        raise SystemExit(f'{name} failed ({result.returncode})')


def resources():
    manifest = json.loads((ROOT / 'resource-manifest.json').read_text(encoding='utf-8'))
    archive = ROOT / 'audit/offline-voice/offline_voice_release_64.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        partial = archive.with_suffix('.partial')
        with urllib.request.urlopen(manifest['source_url'], timeout=45) as stream, partial.open('wb') as output:
            shutil.copyfileobj(stream, output)
        if partial.stat().st_size != manifest['archive_bytes'] or digest(partial) != manifest['archive_sha256']:
            raise SystemExit('Downloaded resource verification failed')
        partial.replace(archive)
    assert archive.stat().st_size == manifest['archive_bytes'] and digest(archive) == manifest['archive_sha256']
    selected = {}
    with zipfile.ZipFile(archive) as bundle:
        for name, expected in manifest['files'].items():
            payload = bundle.read(name)
            assert len(payload) == expected['bytes'] and hashlib.sha256(payload).hexdigest() == expected['sha256'], name
            selected[name] = payload
    return manifest, selected


def patch_sources():
    texts = {}
    def source(cls):
        if cls not in texts:
            files = list(DECODED.glob('smali*/' + cls + '.smali'))
            assert len(files) == 1, cls
            texts[cls] = files[0].read_text(encoding='utf-8')
        return texts[cls]

    def replace(cls, signature, body):
        text = source(cls)
        pattern = r'(?m)^\.method ([^\n]* ' + re.escape(signature) + r')\n[\s\S]*?^\.end method'
        matches = list(re.finditer(pattern, text))
        assert len(matches) == 1, (cls, signature)
        match = matches[0]
        texts[cls] = text[:match.start()] + '.method ' + match[1] + '\n' + body + '\n.end method' + text[match.end():]
        PATCHES.append({'class': cls, 'method': signature})

    cls = 'com/baidu/input/NewImeApplication'
    text = source(cls)
    anchor = '    invoke-super {p0, p1}, Landroidx/multidex/MultiDexApplication;->attachBaseContext(Landroid/content/Context;)V'
    assert text.count(anchor) == 1
    texts[cls] = text.replace(anchor, anchor + '\n\n    invoke-static {p0}, Llocal/baiduoffline/OfflineAssets;->attach(Landroid/content/Context;)V')
    PATCHES.append({'class': cls, 'method': 'attachBaseContext', 'purpose': 'Attach local resource context'})

    if DEBUG:
        cls = 'com/baidu/flywheel/crash/CrashCollector'
        text = source(cls)
        anchor = '    iget-object v1, p2, Lcom/baidu/flywheel/crash/CrashEvent;->a:Ljava/lang/String;'
        assert text.count(anchor) == 1
        texts[cls] = text.replace(anchor, anchor + '\n\n    invoke-static {v1}, Llocal/baiduoffline/OfflineAssets;->recordCrash(Ljava/lang/String;)V')
        PATCHES.append({'class': cls, 'method': 'dispatchEvent', 'purpose': 'Record experimental crash locally'})

    replace('okhttp3/RealCall', 'getResponseWithInterceptorChain()Lokhttp3/Response;',
            '    .locals 2\n    new-instance v0, Ljava/io/IOException;\n    const-string v1, "Network disabled in offline build"\n    invoke-direct {v0, v1}, Ljava/io/IOException;-><init>(Ljava/lang/String;)V\n    throw v0')
    replace('com/baidu/helios/ids/oid/cert/c$1', 'run()V',
            '    .locals 0\n    return-void')

    cls = 'com/baidu/iptcore/IptCoreInterface'
    text = source(cls)
    anchor = '.method public openCore(Landroid/content/Context;Ljava/lang/String;Landroid/content/pm/PackageInfo;I)Z\n    .locals 9'
    assert text.count(anchor) == 1
    texts[cls] = text.replace(anchor, anchor + '\n\n    invoke-static {p1, p3}, Llocal/baiduoffline/CoreCompatibility;->forCore(Landroid/content/Context;Landroid/content/pm/PackageInfo;)Landroid/content/pm/PackageInfo;\n    move-result-object p3')
    PATCHES.append({'class': cls, 'method': 'openCore', 'purpose': 'Pass isolated consistent compatibility metadata to unmodified native core'})

    manager = 'com/baidu/input/ime/voicerecognize/offline/OfflineVoiceManager'
    for method, helper in [('f', 'modelPath'), ('g', 'libraryPath')]:
        replace(manager, method + '()Ljava/lang/String;',
                '    .locals 1\n    invoke-static {}, Llocal/baiduoffline/OfflineAssets;->' + helper + '()Ljava/lang/String;\n    move-result-object v0\n    return-object v0')
    replace(manager, 'i()Z', '    .locals 1\n    invoke-static {}, Llocal/baiduoffline/OfflineAssets;->ready()Z\n    move-result v0\n    return v0')
    replace('com/baidu/input/ime/voicerecognize/controller/BasicVoiceLogicController', 'v(I)I',
            '    .locals 1\n    const/4 v0, 0x1\n    return v0')

    sdk = 'com/baidu/speech/SpeechEventManager'
    text = source(sdk)
    for method in ['startAsr', 'startAsrStream', 'loadKws', 'loadKwsStream']:
        sig = method + '(Landroid/content/Context;Lorg/json/JSONObject;Lcom/baidu/speech/IEventListener;)V'
        pattern = r'(?m)(^\.method [^\n]* ' + re.escape(sig) + r'\n    \.locals \d+\n)'
        text, count = re.subn(pattern, lambda m: m[1] + '\n    invoke-static/range {p1 .. p1}, Llocal/baiduoffline/OfflineAssets;->forceOffline(Lorg/json/JSONObject;)V\n', text)
        assert count == 1, method
        PATCHES.append({'class': sdk, 'method': sig, 'purpose': 'Force offline decoder and bundled resources'})
    texts[sdk] = text
    commercial_cleanup.patch(source, replace, texts, PATCHES)
    output = BUILD / 'patched-smali'
    for cls, text in texts.items():
        path = output / (cls + '.smali')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    return output


def manifest():
    ns = 'http://schemas.android.com/apk/res/android'
    ET.register_namespace('android', ns)
    a = '{' + ns + '}'
    root = ET.parse(DECODED / 'AndroidManifest.xml').getroot()
    removed = []
    for permission in list(root.findall('uses-permission')):
        if permission.get(a + 'name') not in commercial_cleanup.LOCAL_PERMISSIONS:
            removed.append(permission.get(a + 'name')); root.remove(permission)
    assert 'android.permission.INTERNET' in removed
    for queries in list(root.findall('queries')): root.remove(queries)
    app = root.find('application')
    app.set(a + 'label', '百度离线输入')
    app.set(a + 'debuggable', str(DEBUG).lower())
    app.set(a + 'allowBackup', 'false')
    app.set(a + 'extractNativeLibs', 'true')
    disabled = []
    prefixes = commercial_cleanup.DISABLED_PREFIXES
    redirects = {'com.baidu.input.ImeAppMainActivity', 'com.baidu.input.ImeLauncherActivity'}
    for component in list(app):
        name = component.get(a + 'name', '')
        if component.tag == 'activity' and name in redirects:
            app.remove(component)
            continue
        if component.tag in ('activity', 'service', 'receiver', 'provider') and name.startswith(prefixes):
            component.set(a + 'enabled', 'false'); component.set(a + 'exported', 'false'); disabled.append(name)
        if component.tag in ('activity', 'activity-alias'):
            component.set(a + 'exported', 'false')
        if name == 'com.baidu.input.ImeMainConfigActivity':
            component.set(a + 'exported', 'true')
        for intent_filter in list(component.findall('intent-filter')):
            if any(c.get(a + 'name') == 'android.intent.category.LAUNCHER' for c in intent_filter.findall('category')):
                component.remove(intent_filter)
    activity = ET.SubElement(app, 'activity', {
        a + 'name': 'local.baiduoffline.SetupActivity', a + 'exported': 'true',
        a + 'theme': '@android:style/Theme.Material.Light.NoActionBar',
        a + 'windowSoftInputMode': 'adjustResize'})
    launcher = ET.SubElement(activity, 'intent-filter')
    ET.SubElement(launcher, 'action', {a + 'name': 'android.intent.action.MAIN'})
    ET.SubElement(launcher, 'category', {a + 'name': 'android.intent.category.LAUNCHER'})
    for name in sorted(redirects):
        ET.SubElement(app, 'activity-alias', {
            a + 'name': name, a + 'targetActivity': 'local.baiduoffline.SetupActivity',
            a + 'exported': 'true' if name.endswith('ImeMainConfigActivity') else 'false'})
    public = ET.parse(DECODED / 'res/values/public.xml').getroot()
    identifiers = {'@' + el.get('type') + '/' + el.get('name'):
                   '@com.baidu.input:' + el.get('type') + '/' + el.get('name') for el in public}
    for node in root.iter():
        for key, value in list(node.attrib.items()):
            if value.startswith('@') and not value.startswith('@android:') and not value.startswith('@0x'):
                assert value in identifiers, value
                node.set(key, identifiers[value])
    path = BUILD / 'AndroidManifest.xml'
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
    run('compile-manifest', [BT / ('aapt2' + EXT), 'link', '--manifest', path, '-I', ANDROID, '-I', ORIGINAL,
         '--min-sdk-version', '23', '--target-sdk-version', '34', '--version-code', '1177',
         '--version-name', '13.3.16.2', '-o', BUILD / 'manifest.apk'])
    (BUILD / 'removed-permissions.json').write_text(json.dumps(removed, indent=2), encoding='utf-8')
    return disabled


def signing():
    directory = ROOT / '.local/signing'
    directory.mkdir(parents=True, exist_ok=True)
    password = directory / 'keystore.pass'
    key = directory / 'baidu-offline.p12'
    if not key.exists():
        assert not password.exists(), 'Orphan signing password exists'
        password.write_text(secrets.token_urlsafe(32), encoding='ascii')
        run('create-signing-key', [JDK / ('keytool' + EXT), '-genkeypair', '-keystore', key,
            '-storetype', 'PKCS12', '-storepass:file', password, '-keypass:file', password,
            '-alias', 'baidu-offline', '-keyalg', 'RSA', '-keysize', '3072', '-validity', '10000',
            '-dname', 'CN=Offline IME Local Build'])
    assert password.exists()
    run('public-certificate', [JDK / ('keytool' + EXT), '-exportcert', '-keystore', key,
        '-storepass:file', password, '-alias', 'baidu-offline', '-file', directory / 'signer.der'])
    return key, password


def core_public_certificate():
    result = subprocess.run([str(JDK / ('keytool' + EXT)), '-printcert', '-rfc', '-jarfile', str(ORIGINAL)], capture_output=True)
    assert result.returncode == 0, 'Original public certificate extraction failed'
    match = re.search(rb'-----BEGIN CERTIFICATE-----([\s\S]+?)-----END CERTIFICATE-----', result.stdout)
    assert match, 'Original public certificate missing'
    certificate = base64.b64decode(match[1])
    assert hashlib.sha256(certificate).hexdigest() == 'a6ef817bfd6c083442a149856e51036f6912c2db6b6009db8127cdd641e295a9'
    return certificate


def main():
    global DEBUG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debug', action='store_true', help='Enable local crash diagnostics and Android debugging')
    DEBUG = parser.parse_args().debug
    assert digest(ORIGINAL) == EXPECTED, 'Unexpected original APK'
    # Only discard reproducible compiler output within this build directory.
    # Otherwise a removed patch can survive in the next APK as a stale class.
    for name in ('patched-smali', 'helper-classes', 'helper-dex', 'patch-tool', 'original-dex', 'patched-dex'):
        path = BUILD / name
        assert path.resolve().parent == BUILD.resolve(), 'Unsafe generated output path'
        if path.exists(): shutil.rmtree(path)
    resource_info, resource_files = resources()
    patched = patch_sources()
    disabled = manifest()
    helper_classes = BUILD / 'helper-classes'
    helper_dex = BUILD / 'helper-dex'
    patch_tool = BUILD / 'patch-tool'
    original_dex = BUILD / 'original-dex'
    dex_output = BUILD / 'patched-dex'
    for path in (helper_classes, helper_dex, patch_tool, original_dex, dex_output): path.mkdir(exist_ok=True)
    run('compile-java', [JDK / ('javac' + EXT), '-encoding', 'UTF-8', '-source', '8', '-target', '8',
        '-g:none', '-classpath', ANDROID, '-d', helper_classes, *sorted((ROOT / 'java').rglob('*.java'))])
    run('helper-dex', [JDK / ('java' + EXT), '-cp', BT / 'lib/d8.jar', 'com.android.tools.r8.D8',
        '--release', '--min-api', '23', '--lib', ANDROID, '--output', helper_dex,
        *sorted(helper_classes.rglob('*.class'))])
    run('compile-dex-tool', [JDK / ('javac' + EXT), '-encoding', 'UTF-8', '-g:none', '-cp', JADX,
        '-d', patch_tool, ROOT / 'scripts/DexPatch.java'])
    with zipfile.ZipFile(ORIGINAL) as apk:
        for name in apk.namelist():
            if re.fullmatch(r'classes\d*\.dex', name): (original_dex / name).write_bytes(apk.read(name))
    run('patch-dex', [JDK / ('java' + EXT), '-Xmx4g', '-cp', str(JADX) + os.pathsep + str(patch_tool),
        'DexPatch', original_dex, patched, dex_output])
    key, password = signing()
    unsigned = BUILD / 'unsigned.apk'
    with zipfile.ZipFile(BUILD / 'manifest.apk') as container:
        manifest_bytes = container.read('AndroidManifest.xml')
    with zipfile.ZipFile(ORIGINAL) as original, zipfile.ZipFile(unsigned, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        def put(name, data, compression=zipfile.ZIP_DEFLATED):
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = compression
            output.writestr(info, data)
        for info in original.infolist():
            name = info.filename
            signature_entry = name.startswith('META-INF/') and (
                name.upper() == 'META-INF/MANIFEST.MF' or name.upper().endswith(('.SF', '.RSA', '.DSA', '.EC')))
            if signature_entry or name.startswith('lib/armeabi-v7a/') or name.endswith('/'): continue
            if name == 'AndroidManifest.xml': data = manifest_bytes
            elif re.fullmatch(r'classes\d*\.dex', name) and (dex_output / name).exists(): data = (dex_output / name).read_bytes()
            else: data = original.read(name)
            put(name, data, info.compress_type)
        assert 'classes9.dex' not in original.namelist()
        assert 'classes10.dex' not in original.namelist()
        put('classes9.dex', (helper_dex / 'classes.dex').read_bytes())
        put('classes10.dex', (dex_output / 'patches.dex').read_bytes())
        put('assets/offline-voice/s_14', resource_files['s_14'])
        put('assets/offline-voice/resource-manifest.json', (ROOT / 'resource-manifest.json').read_bytes())
        put('assets/offline-voice/core-original-public-certificate.der', core_public_certificate())
        put('lib/arm64-v8a/libbdTinyEasrAndroid_arm64_12.so', resource_files['libbdTinyEasrAndroid_arm64_12.so'])
    aligned = BUILD / 'aligned.apk'
    run('align', [BT / ('zipalign' + EXT), '-f', '-P', '16', '4', unsigned, aligned])
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    apk = dist / ('BaiduOffline-0.2-debug-arm64.apk' if DEBUG else 'BaiduOffline-0.2-arm64.apk')
    signer = BT / 'lib/apksigner.jar'
    run('sign', [JDK / ('java' + EXT), '-jar', signer, 'sign', '--ks', key,
        '--ks-key-alias', 'baidu-offline', '--ks-pass', 'file:' + str(password),
        '--v1-signing-enabled', 'true', '--v2-signing-enabled', 'true', '--v3-signing-enabled', 'true',
        '--v4-signing-enabled', 'false', '--out', apk, aligned])
    run('verify-signature', [JDK / ('java' + EXT), '-jar', signer, 'verify', '--verbose', '--print-certs', apk])
    run('verify-alignment', [BT / ('zipalign' + EXT), '-c', '-P', '16', '4', apk])
    run('verify-permissions', [BT / ('aapt2' + EXT), 'dump', 'permissions', apk])
    permissions = (LOGS / 'verify-permissions.log').read_text(encoding='utf-8')
    assert "name='android.permission.INTERNET'" not in permissions
    assert "name='android.permission.RECORD_AUDIO'" in permissions
    with zipfile.ZipFile(ORIGINAL) as src, zipfile.ZipFile(apk) as dst:
        preserved = [n for n in src.namelist() if not n.endswith('/') and (n.startswith(('res/', 'assets/', 'lib/arm64-v8a/')) or n == 'resources.arsc')]
        assert all(src.read(n) == dst.read(n) for n in preserved), 'Original resource or native library changed'
        for name, payload in resource_files.items():
            entry = ('assets/offline-voice/' if name == 's_14' else 'lib/arm64-v8a/') + name
            assert dst.read(entry) == payload
        assert not any('__MACOSX' in name for name in dst.namelist())
    report = {'apk': apk.name, 'bytes': apk.stat().st_size, 'sha256': digest(apk),
        'original_sha256': EXPECTED, 'resource_sha256': resource_info['archive_sha256'],
        'internet_permission': False, 'debuggable': DEBUG, 'signature_verified': True,
        'alignment_verified': True, 'runtime_tested': False, 'commercial_cleanup_complete': False,
        'original_resources_and_arm64_libraries_preserved': len(preserved),
        'disabled_components': disabled, 'patches': PATCHES,
        'removed_permissions': json.loads((BUILD / 'removed-permissions.json').read_text(encoding='utf-8')),
        'signer_sha256': digest(ROOT / '.local/signing/signer.der')}
    (dist / 'build-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (dist / 'SHA256SUMS.txt').write_text(report['sha256'] + '  ' + apk.name + '\n', encoding='ascii')
    print(json.dumps({k: v for k, v in report.items() if k not in ('patches', 'disabled_components', 'removed_permissions')}, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
