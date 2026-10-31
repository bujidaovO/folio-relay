"""Native desktop window around the shared local application."""
import argparse
import json
from pathlib import Path
import sys
import threading

from app_paths import application_directory, default_data_directory, resource_directory, settings_path
from local_server import make_server, running_url
from platform_support import open_path, set_window_theme
from storage import Repository, atomic_write, encode, MAX_BYTES


_settings_lock = threading.Lock()


def _read_settings():
    try:
        value = json.loads(settings_path().read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _update_settings(changes):
    with _settings_lock:
        settings = _read_settings()
        settings.update(changes)
        atomic_write(settings_path(), encode(settings))


class LocalSession:
    def __init__(self, directory, port=4173):
        self.repository = Repository(directory)
        self.server = None
        self.thread = None
        self.url = running_url(self.repository, port) if port else None
        if self.url:
            return
        for candidate in range(port, port + 10) if port else [0]:
            try:
                self.server = make_server(self.repository, candidate)
                break
            except OSError:
                continue
        if self.server is None:
            raise OSError('本地端口被占用，请关闭之前的服务后重试。')
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            self.server = None


class DesktopBridge:
    def __init__(self, session):
        self._session = session
        self._window = None

    def get_theme(self):
        theme = _read_settings().get('theme')
        return theme if theme in ('dark', 'light') else 'dark'

    def set_theme(self, theme):
        if theme not in ('dark', 'light'):
            raise ValueError('请选择日间或夜间模式')
        _update_settings({'theme': theme})
        set_window_theme(theme)
        return True

    def _page_url(self, session):
        return session.url + '/?theme=' + self.get_theme()

    def copy_text(self, value):
        if not isinstance(value, str) or len(value.encode('utf-8')) > MAX_BYTES:
            raise ValueError('复制内容过长')
        import pyperclip
        pyperclip.copy(value)
        return True

    def save_json(self, name, value):
        import webview
        if not isinstance(name, str) or Path(name).name != name or not name.endswith('.json'):
            raise ValueError('导出文件名应为 JSON')
        raw = encode(value)
        selected = self._window.create_file_dialog(webview.FileDialog.SAVE,
                    save_filename=name, file_types=('JSON 文件 (*.json)',))
        if not selected:
            return {'saved': False}
        destination = Path(selected[0] if isinstance(selected, (tuple, list)) else selected)
        atomic_write(destination, raw)
        return {'saved': True, 'path': str(destination)}

    def open_data_directory(self):
        open_path(self._session.repository.directory)

    def choose_data_directory(self):
        import webview
        selected = self._window.create_file_dialog(webview.FileDialog.FOLDER,
                    directory=str(self._session.repository.directory))
        if not selected:
            return
        directory = Path(selected[0] if isinstance(selected, (tuple, list)) else selected).resolve()
        if directory == self._session.repository.directory:
            return
        # The chosen folder is the data root containing projects/, not one project.
        if (directory / '正在使用文件').is_dir():
            raise ValueError('请选择包含 projects 文件夹的资料根目录。')
        replacement = LocalSession(directory)
        try:
            replacement.repository.bundle()
            _update_settings({'dataDirectory': str(directory),
                              'applicationDirectory': str(application_directory())})
            self._window.load_url(self._page_url(replacement))
        except Exception:
            replacement.close()
            raise
        previous, self._session = self._session, replacement
        previous.close()

    def close(self):
        self._session.close()

    def _choose_from_menu(self):
        try:
            self.choose_data_directory()
        except (OSError, ValueError) as error:
            self._window.run_js('toast(' + json.dumps('无法切换资料目录：' + str(error)) + ')')


def main():
    parser = argparse.ArgumentParser(description='项目札记 · 桌面应用')
    parser.add_argument('--data-dir', type=Path, default=default_data_directory())
    parser.add_argument('--check', action='store_true', help='只校验资料和打包资源，不打开窗口')
    args = parser.parse_args()
    if args.check:
        root = resource_directory()
        for name in ('dist/index.html', 'dist/app.js', 'dist/style.css', 'dist/reading-plan.js', 'dist/help.js', 'dist/theme.js', 'dist/brand.svg', '记录读写说明.md'):
            if not (root / name).is_file():
                raise FileNotFoundError('缺少应用资源：' + name)
        projects = Repository(args.data_dir).bundle()[0]['projects']
        print(f'应用资源及 JSON 校验通过：{len(projects)} 个项目。')
        return

    import webview
    from webview.menu import Menu, MenuAction
    session = LocalSession(args.data_dir)
    bridge = DesktopBridge(session)
    try:
        window = webview.create_window('项目札记', bridge._page_url(session), js_api=bridge,
                    width=1200, height=820, min_size=(820, 600), text_select=True,
                    background_color='#05070b' if bridge.get_theme() == 'dark' else '#f4f8fc')
        bridge._window = window
        window.events.shown += lambda: set_window_theme(bridge.get_theme())
        menu = [Menu('资料', [MenuAction('打开资料文件夹', bridge.open_data_directory),
                             MenuAction('选择资料目录…', bridge._choose_from_menu),
                             MenuAction('退出项目札记', window.destroy)])]
        webview.start(menu=menu, private_mode=True,
                      gui='edgechromium' if sys.platform == 'win32' else None,
                      localization={'global.quit': '退出项目札记', 'global.cancel': '取消',
                                    'global.ok': '确定', 'global.saveFile': '保存 JSON'})
    finally:
        bridge.close()


if __name__ == '__main__':
    main()
