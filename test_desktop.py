import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError
from urllib.request import urlopen

from desktop import DesktopBridge, LocalSession
import app_paths
import platform_support


class DesktopTests(unittest.TestCase):
    @patch('desktop.set_window_theme')
    def test_theme_survives_restart_without_replacing_data_preferences(self, appearance):
        with tempfile.TemporaryDirectory() as directory, patch('desktop.settings_path', return_value=Path(directory)/'settings.json'):
            settings = Path(directory)/'settings.json'
            original = {'dataDirectory': '/chosen/records', 'applicationDirectory': '/chosen/app', 'futurePreference': True}
            settings.write_text(json.dumps(original), encoding='utf-8')
            bridge = DesktopBridge(None)
            self.assertEqual(bridge.get_theme(), 'dark')
            bridge.set_theme('light')
            self.assertEqual(DesktopBridge(None).get_theme(), 'light')
            self.assertEqual(json.loads(settings.read_text(encoding='utf-8')), {**original, 'theme': 'light'})
            appearance.assert_called_once_with('light')
            with self.assertRaises(ValueError):
                bridge.set_theme('unsupported')
            self.assertEqual(DesktopBridge(None).get_theme(), 'light')

    def test_selecting_another_data_folder_keeps_theme_and_initial_page_appearance(self):
        fake = SimpleNamespace(FileDialog=SimpleNamespace(FOLDER=2))
        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', webview=fake):
            root = Path(directory)
            chosen = root/'chosen'; chosen.mkdir()
            settings = root/'settings.json'
            settings.write_text(json.dumps({'theme': 'light', 'futurePreference': True}), encoding='utf-8')
            previous = Mock(repository=SimpleNamespace(directory=root))
            replacement = Mock(url='http://127.0.0.1:4274')
            bridge = DesktopBridge(previous)
            bridge._window = Mock()
            bridge._window.create_file_dialog.return_value = [str(chosen)]
            with patch('desktop.settings_path', return_value=settings), patch('desktop.LocalSession', return_value=replacement):
                bridge.choose_data_directory()
            self.assertEqual(json.loads(settings.read_text(encoding='utf-8'))['theme'], 'light')
            self.assertTrue(json.loads(settings.read_text(encoding='utf-8'))['futurePreference'])
            bridge._window.load_url.assert_called_once_with('http://127.0.0.1:4274/?theme=light')
            previous.close.assert_called_once()

    def test_desktop_service_owns_its_lifetime(self):
        with tempfile.TemporaryDirectory() as directory:
            service = LocalSession(directory, port=0)
            with urlopen(service.url + '/api/health', timeout=2) as response:
                self.assertEqual(json.load(response)['data_directory'], str(Path(directory).resolve()))
            service.close()
            with self.assertRaises((URLError, OSError)):
                urlopen(service.url + '/api/health', timeout=0.5)

    def test_closing_a_borrowed_service_does_not_stop_its_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            owner = LocalSession(directory, port=0)
            try:
                borrowed = LocalSession(directory, port=owner.server.server_address[1])
                self.assertEqual(borrowed.url, owner.url)
                borrowed.close()
                self.assertEqual(urlopen(owner.url + '/api/health', timeout=2).status, 200)
            finally:
                owner.close()

    def test_native_export_writes_selected_file_and_cancel_writes_nothing(self):
        fake = SimpleNamespace(FileDialog=SimpleNamespace(SAVE=1, FOLDER=2))
        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', webview=fake):
            bridge = DesktopBridge(None)
            bridge._window = Mock()
            bridge._window.create_file_dialog.return_value = None
            self.assertFalse(bridge.save_json('项目.json', {'内容': '你好'})['saved'])
            self.assertEqual(list(Path(directory).iterdir()), [])
            target = Path(directory) / '导出文件.json'
            bridge._window.create_file_dialog.return_value = [str(target)]
            self.assertTrue(bridge.save_json('项目.json', {'内容': '你好'})['saved'])
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'内容': '你好'})
            with self.assertRaises(ValueError):
                bridge.save_json('../bad.json', {})

    def test_app_resources_and_user_data_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('app_paths.application_directory', return_value=root), patch('app_paths.settings_path', return_value=root/'settings.json'), patch.dict('os.environ', {'PROJECT_NOTES_DATA_DIR': ''}):
                self.assertEqual(app_paths.default_data_directory(), root/'项目资料')
                custom = root/'自选资料'; custom.mkdir()
                (root/'项目资料').mkdir()
                (root/'settings.json').write_text(json.dumps({'applicationDirectory': str(root), 'dataDirectory': str(custom)}), encoding='utf-8')
                self.assertEqual(app_paths.default_data_directory(), custom.resolve())

    def test_windows_open_uses_default_application_without_shell_interpolation(self):
        with patch('platform_support.sys.platform', 'win32'), patch('platform_support.os.startfile', create=True) as launch:
            platform_support.open_path('包含空格的 资料.json')
            launch.assert_called_once_with(str(Path('包含空格的 资料.json').resolve()))

    def test_windows_build_finds_data_beside_the_program_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'项目资料').mkdir()
            with patch('app_paths.application_directory', return_value=root/'项目札记'), patch('app_paths.sys.platform', 'win32'), patch('app_paths.settings_path', return_value=root/'settings.json'), patch.dict('os.environ', {'PROJECT_NOTES_DATA_DIR': ''}):
                self.assertEqual(app_paths.default_data_directory(), root/'项目资料')

    def test_windows_lock_resets_the_position_before_unlocking(self):
        import os
        fake = SimpleNamespace(LK_LOCK=1, LK_UNLCK=2, locking=Mock())
        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', msvcrt=fake), patch('platform_support.os', SimpleNamespace(name='nt', SEEK_END=os.SEEK_END)):
            with platform_support.file_lock(Path(directory)/'lock'):
                pass
            self.assertEqual([call.args[1:] for call in fake.locking.call_args_list], [(1, 1), (2, 1)])


if __name__ == '__main__':
    unittest.main()
