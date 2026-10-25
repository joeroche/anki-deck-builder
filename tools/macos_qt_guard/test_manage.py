import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('qt_guard_manage', Path(__file__).with_name('manage.py'))
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)

class GuardInstallerTests(unittest.TestCase):
    def test_runtime_pin_refuses_other_version_arch_or_hash(self):
        supported = dict(system='Darwin', machine='arm64', qt='6.9.1', plugin_sha256=manage.PIN)
        manage.validate_runtime(supported)
        for field, value in [('system', 'Linux'), ('machine', 'x86_64'), ('qt', '6.11.2'), ('plugin_sha256', 'unknown')]:
            with self.assertRaises(RuntimeError):
                manage.validate_runtime({**supported, field: value})

    def test_running_anki_refuses_before_writing(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(manage, 'running_anki', return_value=['123 Anki']):
            base = Path(temp) / 'never-created'
            with self.assertRaises(RuntimeError):
                manage.install(base, Path('/unused'))
            self.assertFalse(base.exists())

    def test_wrong_runtime_refuses_before_build(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(manage, 'running_anki', return_value=[]), patch.object(manage, 'runtime_info', return_value={}), patch.object(manage, 'build') as build:
            with self.assertRaises(RuntimeError):
                manage.install(Path(temp), Path('/unused'))
            build.assert_not_called()
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_rollback_preserves_addon_outside_load_directory(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(manage, 'running_anki', return_value=[]):
            base = Path(temp)
            source = base / 'addons21' / manage.PACKAGE
            source.mkdir(parents=True)
            (source / 'evidence').write_text('preserve')
            result = manage.rollback(base)
            self.assertFalse(source.exists())
            self.assertEqual((Path(result['backup']) / 'evidence').read_text(), 'preserve')
            self.assertEqual(manage.rollback(base)['status'], 'already_absent')

    def test_rollback_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(manage, 'running_anki', return_value=[]):
            base = Path(temp)
            (base / 'addons21').mkdir()
            target = base / 'external'
            target.mkdir()
            (base / 'addons21' / manage.PACKAGE).symlink_to(target, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                manage.rollback(base)
            self.assertTrue(target.exists())

    def test_regression_refuses_unknown_runtime_before_building(self):
        with patch.object(manage, 'runtime_info', return_value={}), patch.object(manage, 'build') as build:
            with self.assertRaises(RuntimeError):
                manage.regression(Path('/unused'))
            build.assert_not_called()

if __name__ == '__main__':
    unittest.main()
