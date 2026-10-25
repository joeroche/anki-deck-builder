#!/usr/bin/env python3
"""Build/install/remove a pinned local Qt Cocoa ownership backport. No collection access."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIN = 'e55f65197f5a3c2520a65190930f5051f5d5d7b1e861821d36c1838a556b977d'
PACKAGE = 'qt_macos_ownership_guard'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def runtime_info(python):
    code = '''import json,platform,hashlib
from pathlib import Path
from PyQt6.QtCore import qVersion
import PyQt6
p=Path(PyQt6.__file__).parent/'Qt6/plugins/platforms/libqcocoa.dylib'
print(json.dumps(dict(system=platform.system(),machine=platform.machine(),qt=qVersion(),plugin_sha256=hashlib.sha256(p.read_bytes()).hexdigest())))'''
    return json.loads(subprocess.check_output([str(python), '-c', code], text=True))

def validate_runtime(info):
    if (info.get('system'), info.get('machine'), info.get('qt'), info.get('plugin_sha256')) != ('Darwin', 'arm64', '6.9.1', PIN):
        raise RuntimeError('Runtime is outside the verified pin; no installation performed. Do not bypass this check.')

def running_anki():
    lines = subprocess.check_output(['ps', '-axo', 'pid=,command='], text=True).splitlines()
    return [line.strip() for line in lines if 'AnkiProgramFiles' in line and ('aqt.run()' in line or '/bin/anki' in line.split(' ', 1)[-1]) and int(line.split()[0]) != os.getpid()]

def require_closed():
    if running_anki():
        raise RuntimeError('Quit Anki before installing or rolling back. No files changed.')

def build():
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('This backport is only verified on Apple Silicon macOS.')
    destination = ROOT / 'qt_ownership_guard.dylib'
    with tempfile.TemporaryDirectory() as temp:
        compiled = Path(temp) / destination.name
        subprocess.run(['xcrun', 'clang', '-dynamiclib', '-fno-objc-arc', '-arch', 'arm64', '-mmacosx-version-min=12.0', '-framework', 'Foundation', '-o', str(compiled), str(ROOT / 'qt_ownership_guard.m')], check=True)
        shutil.copy2(compiled, destination)
    return destination

def install(base, python):
    require_closed()
    info = runtime_info(python)
    validate_runtime(info)
    library = build()
    addons = base / 'addons21'
    addons.mkdir(parents=True, exist_ok=True)
    destination = addons / PACKAGE
    if destination.is_symlink():
        raise RuntimeError('Refusing to replace a symlinked add-on.')
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = None
    # Prepare everything before replacing the installed directory.
    with tempfile.TemporaryDirectory(dir=addons, prefix='.qt-guard-stage-') as temp:
        staged = Path(temp) / PACKAGE
        staged.mkdir()
        shutil.copy2(ROOT / 'addon.py', staged / '__init__.py')
        shutil.copy2(library, staged / library.name)
        (staged / 'manifest.json').write_text(json.dumps({'name': 'Local Qt macOS ownership guard', 'package': PACKAGE, 'author': 'Local source build', 'homepage': 'https://codereview.qt-project.org/c/qt/qtbase/+/765434', 'conflicts': []}, indent=2))
        receipt = dict(runtime=info, source_sha256=digest(ROOT / 'qt_ownership_guard.m'), library_sha256=digest(library), installed_at_utc=timestamp)
        (staged / 'install-receipt.json').write_text(json.dumps(receipt, indent=2))
        if destination.exists():
            backup = base / 'qt_guard_backups' / timestamp / PACKAGE
            backup.parent.mkdir(parents=True)
            shutil.move(str(destination), backup)
        try:
            shutil.move(str(staged), destination)
        except Exception:
            if backup is not None and not destination.exists():
                shutil.move(str(backup), destination)
            raise
    return dict(status='installed_for_next_launch', restart_required=True, addon=str(destination), backup=str(backup) if backup else None, **receipt)

def rollback(base):
    require_closed()
    source = base / 'addons21' / PACKAGE
    if source.is_symlink():
        raise RuntimeError('Refusing a symlinked add-on.')
    if not source.exists():
        return dict(status='already_absent')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = base / 'qt_guard_backups' / ('disabled-' + stamp) / PACKAGE
    destination.parent.mkdir(parents=True)
    shutil.move(str(source), destination)
    return dict(status='disabled_for_next_launch', backup=str(destination), restart_required=True)

def regression(python):
    """Compile both native libraries and test synthetic data without activation."""
    validate_runtime(runtime_info(python))
    build()
    subprocess.run(['xcrun', 'clang', '-dynamiclib', '-fno-objc-arc', '-arch', 'arm64',
                    '-mmacosx-version-min=12.0', '-framework', 'Foundation',
                    '-o', str(ROOT / 'native_probe.dylib'), str(ROOT / 'native_probe.m')], check=True)
    result = json.loads(subprocess.check_output(
        [str(python), str(ROOT / 'native_regression.py'), '--patched', '--background'], text=True))
    if result.get('patched') is not True or len(result.get('checks', [])) != 15:
        raise RuntimeError('Missing complete patched regression evidence.')
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'build', 'install', 'status', 'rollback', 'regression'])
    parser.add_argument('--anki-base', type=Path, default=Path.home() / 'Library/Application Support/Anki2')
    parser.add_argument('--anki-python', type=Path, default=Path.home() / 'Library/Application Support/AnkiProgramFiles/.venv/bin/python')
    args = parser.parse_args()
    if args.action == 'inspect':
        result = runtime_info(args.anki_python)
        try:
            validate_runtime(result)
            result['supported'] = True
        except RuntimeError:
            result['supported'] = False
    elif args.action == 'build':
        path = build()
        result = dict(library=str(path), sha256=digest(path))
    elif args.action == 'install':
        result = install(args.anki_base, args.anki_python)
    elif args.action == 'rollback':
        result = rollback(args.anki_base)
    elif args.action == 'regression':
        result = regression(args.anki_python)
    else:
        path = args.anki_base / 'addons21' / PACKAGE / 'user_files/status.json'
        result = json.loads(path.read_text()) if path.exists() else dict(status='no_runtime_receipt')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
