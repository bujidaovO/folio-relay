#!/usr/bin/env python3
"""Local-only JSON project journal. Python standard library, no login."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from storage import Repository, MAX_BYTES
from app_paths import default_data_directory, resource_directory
from platform_support import open_path

ROOT = resource_directory()
APP_ID = 'project-notes-local-v2'
FILE_API = re.compile(r'^/api/projects/([a-z][a-z0-9-]{0,63})/files/(.+)$')
WEEK_API = re.compile(r'^/api/projects/([a-z][a-z0-9-]{0,63})/next-week$')
LOCATIONS_API = re.compile(r'^/api/projects/([a-z][a-z0-9-]{0,63})/locations$')
OPEN_LOCATION_API = re.compile(r'^/api/projects/([a-z][a-z0-9-]{0,63})/open-location$')


def open_location(repository, project_id, key):
    locations = repository.locations(project_id)
    if key == 'project-directory':
        item = dict(path=locations['project_directory'], exists=True, kind='directory')
    else:
        item = next((item for item in locations['reading_files'] + locations['other_locations'] if item['key'] == key), None)
    if item is None:
        raise ValueError('请选择文件位置列表中的文件或目录')
    target = Path(item['path'])
    if not item['exists'] or not target.exists():
        raise FileNotFoundError('文件或目录已不存在，请刷新文件位置')
    try:
        open_path(target)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError('系统未能打开，请检查该文件的默认应用设置后重试') from error
    return dict(opened=True, kind=item['kind'])


def make_server(repository, port=4173):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / 'dist'), **kwargs)

        def log_message(self, fmt, *args):
            if sys.stderr is not None and len(args) > 1 and str(args[1]) not in {'200', '201', '204', '304'}:
                super().log_message(fmt, *args)

        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            super().end_headers()

        def respond(self, status, data=None, revision=None):
            raw = json.dumps(data, ensure_ascii=False).encode('utf-8') if data is not None else b''
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            if revision:
                self.send_header('ETag', revision)
            self.end_headers()
            if raw:
                self.wfile.write(raw)

        def local_request(self):
            port = self.server.server_address[1]
            hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            origin = self.headers.get('Origin')
            if self.headers.get('Host') not in hosts or (origin and origin not in {'http://' + host for host in hosts}):
                self.respond(403, {'error': '仅接受本机页面或本地工具的访问'})
                return False
            return True

        def body(self):
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('请使用 application/json 提交资料')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BYTES:
                raise ValueError('提交资料应为 1 字节至 5 MB')
            return json.loads(self.rfile.read(length))

        def handle_error(self, error):
            if isinstance(error, PermissionError):
                code = 403
            elif isinstance(error, FileExistsError):
                code = 409
            elif isinstance(error, FileNotFoundError):
                code = 404
            elif isinstance(error, (ValueError, TypeError, KeyError)):
                code = 400
            else:
                code = 500
            self.respond(code, {'error': str(error) if code != 500 else '本地文件操作失败，请检查目录权限与磁盘空间'})

        def do_GET(self):
            if not self.local_request():
                return
            path = unquote(urlsplit(self.path).path)
            try:
                if path == '/api/health':
                    self.respond(200, {'app': APP_ID, 'data_directory': str(repository.directory)})
                elif path == '/api/workspace':
                    data, revision = repository.bundle()
                    if self.headers.get('If-None-Match') == revision:
                        self.respond(304, revision=revision)
                    else:
                        self.respond(200, data, revision)
                elif (match := LOCATIONS_API.fullmatch(path)):
                    self.respond(200, repository.locations(match[1]))
                elif (match := FILE_API.fullmatch(path)):
                    with repository.locked():
                        data, revision = repository.read(match[1], match[2])
                    self.respond(200, data, revision)
                elif path in {'/', '/index.html', '/app.js', '/reading-plan.js', '/help.js', '/brand.svg', '/style.css'}:
                    super().do_GET()
                elif path == '/favicon.ico':
                    self.respond(204)
                else:
                    self.respond(404, {'error': '页面不存在'})
            except (OSError, ValueError, TypeError, KeyError) as error:
                self.handle_error(error)

        def do_PUT(self):
            if not self.local_request():
                return
            try:
                match = FILE_API.fullmatch(unquote(urlsplit(self.path).path))
                if not match:
                    return self.respond(404, {'error': '请写入明确的项目 JSON 文件'})
                if not self.headers.get('If-Match'):
                    return self.respond(428, {'error': '请先读取 JSON，并提交对应的 If-Match'})
                revision = repository.save(match[1], match[2], self.body(), self.headers['If-Match'])
                self.respond(200, {'saved': True}, revision)
            except (OSError, ValueError, TypeError, KeyError) as error:
                self.handle_error(error)

        def do_POST(self):
            if not self.local_request():
                return
            try:
                data = self.body()
                path = unquote(urlsplit(self.path).path)
                if path == '/api/stop':
                    self.respond(200, {'stopped': True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                elif path == '/api/projects':
                    self.respond(201, {'id': repository.create(data.get('name', ''))})
                elif path == '/api/import':
                    if data.get('schemaVersion') != 2:
                        raise ValueError('仅支持版本 2 的项目 JSON 导出包；旧数据仍保留在原文件中')
                    self.respond(201, {'id': repository.install(data.get('files'))})
                elif (match := OPEN_LOCATION_API.fullmatch(path)):
                    self.respond(200, open_location(repository, match[1], data.get('key')))
                elif (match := WEEK_API.fullmatch(path)):
                    self.respond(200, {'week': repository.next_week(match[1])})
                else:
                    self.respond(404, {'error': '接口不存在'})
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
                self.handle_error(error)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def running_url(repository, start_port):
    for port in range(start_port, start_port + 10):
        url = f'http://127.0.0.1:{port}'
        try:
            with urlopen(url + '/api/health', timeout=0.2) as response:
                info = json.load(response)
            if info.get('app') == APP_ID and info.get('data_directory') == str(repository.directory):
                return url
        except (URLError, OSError, ValueError):
            pass
    return None


def main():
    parser = argparse.ArgumentParser(description='项目札记 · 本地 JSON 交接')
    parser.add_argument('--data-dir', type=Path, default=default_data_directory())
    parser.add_argument('--port', type=int, default=4173)
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--check', action='store_true', help='检查所有项目 JSON 的结构')
    args = parser.parse_args()
    repository = Repository(args.data_dir)
    if args.check:
        data, _ = repository.bundle()
        print(f"JSON 校验通过：{len(data['projects'])} 个项目。")
        return
    existing = running_url(repository, args.port)
    if args.stop:
        if existing:
            with urlopen(Request(existing + '/api/stop', data=b'{}', headers={'Content-Type': 'application/json'}), timeout=3):
                pass
            print('项目札记已停止，资料文件保留。')
        else:
            print('当前没有运行中的项目札记。')
        return
    if existing:
        print('已在运行：' + existing)
        if args.open:
            webbrowser.open(existing)
        return
    for port in range(args.port, args.port + 10):
        try:
            server = make_server(repository, port)
            break
        except OSError:
            continue
    else:
        raise SystemExit('本地端口被占用，请关闭之前的服务后重试。')
    url = f'http://127.0.0.1:{server.server_address[1]}'
    print('项目札记已启动：' + url, flush=True)
    print('资料位置：' + str(repository.projects_dir), flush=True)
    print('无需登录；按 Control+C 或双击停止脚本可停止。', flush=True)
    if args.open:
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit('无法启动：' + str(error))
