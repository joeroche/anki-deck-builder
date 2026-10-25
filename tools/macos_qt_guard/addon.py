"""Narrow local Qt 6.9.1 Cocoa accessibility ownership backport."""
import ctypes
import hashlib
import json
import platform
from pathlib import Path
from aqt.qt import QTimer, qVersion
import PyQt6

ROOT = Path(__file__).resolve().parent
EXPECTED_PLUGIN_SHA256 = 'e55f65197f5a3c2520a65190930f5051f5d5d7b1e861821d36c1838a556b977d'
status = {'status': 'not_installed', 'qt': qVersion(), 'machine': platform.machine()}
(ROOT / 'user_files').mkdir(exist_ok=True)
def save():
    (ROOT / 'user_files' / 'status.json').write_text(json.dumps(status, indent=2))
try:
    if platform.system() != 'Darwin' or platform.machine() != 'arm64' or qVersion() != '6.9.1':
        raise RuntimeError('Unsupported platform/runtime; no patch applied')
    plugin = Path(PyQt6.__file__).parent / 'Qt6/plugins/platforms/libqcocoa.dylib'
    status['plugin_sha256'] = hashlib.sha256(plugin.read_bytes()).hexdigest()
    if status['plugin_sha256'] != EXPECTED_PLUGIN_SHA256:
        raise RuntimeError('Unrecognized Cocoa plugin; no patch applied')
    lib = ctypes.CDLL(str(ROOT / 'qt_ownership_guard.dylib'))
    lib.qt_guard_target_image.restype = ctypes.c_char_p
    target_image = lib.qt_guard_target_image()
    if not target_image or hashlib.sha256(Path(target_image.decode()).read_bytes()).hexdigest() != EXPECTED_PLUGIN_SHA256:
        raise RuntimeError('Loaded accessibility class does not match the verified plugin; no patch applied')
    lib.install_qt_ownership_guard.restype = ctypes.c_int
    result = lib.install_qt_ownership_guard()
    if result not in (0, 1):
        raise RuntimeError(f'Runtime ownership guard refused installation: {result}')
    status.update(status='installed', install_result=result)
    for name in ['qt_guard_filtered_count', 'qt_guard_dealloc_count']:
        getattr(lib, name).restype = ctypes.c_ulong
    def record_counts():
        status.update(filtered_parent_elements=lib.qt_guard_filtered_count(), guarded_destructors=lib.qt_guard_dealloc_count())
        save()
    timer = QTimer()
    timer.timeout.connect(record_counts)
    timer.start(5000)
    record_counts()
except Exception as exc:
    status.update(status='installed' if status['status'] == 'installed' else 'refused', error=str(exc))
    save()
