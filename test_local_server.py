import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from local_server import make_server, running_url
from storage import Repository


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(self.temp.name)
        self.id = self.repo.create('接口测试')
        self.server = make_server(self.repo, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        self.file = f'/api/projects/{self.id}/files/current/week01.json'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path, method='GET', data=None, headers=None):
        h = dict(headers or {})
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            h['Content-Type'] = 'application/json'
        try:
            with urlopen(Request(self.url + path, data=body, headers=h, method=method), timeout=3) as r:
                return r.status, dict(r.headers), r.read()
        except HTTPError as r:
            return r.code, dict(r.headers), r.read()

    def test_no_login_and_standalone_week_json(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/help.js')[0], 200)
        self.assertEqual(self.request('/theme.js')[0], 200)
        self.assertEqual(self.request('/brand.svg')[0], 200)
        status, _, raw = self.request(self.file)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['kind'], 'week')
        self.assertEqual(self.request(self.file.replace('.json', '-handoff.json'))[0], 200)

    def test_conditional_read_and_conflicting_write(self):
        _, headers, _ = self.request('/api/workspace')
        self.assertEqual(self.request('/api/workspace', headers={'If-None-Match': headers['ETag']})[0], 304)
        _, headers, raw = self.request(self.file)
        data = json.loads(raw)
        data['days'][0]['summary'] = '已保存'
        self.assertEqual(self.request(self.file, 'PUT', data, {'If-Match': headers['ETag']})[0], 200)
        self.assertEqual(self.request(self.file, 'PUT', data, {'If-Match': headers['ETag']})[0], 409)
        self.assertEqual(self.request(self.file, 'PUT', data)[0], 428)

    def test_locations_are_local_readonly_metadata(self):
        _, before, _ = self.request('/api/workspace')
        path = f'/api/projects/{self.id}/locations'
        status, _, raw = self.request(path)
        self.assertEqual(status, 200)
        locations = json.loads(raw)
        self.assertEqual(locations['project_directory'], str(self.repo.project_directory(self.id).resolve()))
        self.assertEqual(locations['active_directory'], str(self.repo.path(self.id, 'project.json').parent.resolve()))
        self.assertEqual(locations['current'], {'week': 1, 'day': 1})
        self.assertEqual(locations['reading_files'][0]['key'], 'agent-guide')
        self.assertEqual(Path(locations['reading_files'][0]['path']).name, '记录读写说明.md')
        self.assertEqual(self.request('/api/workspace')[1]['ETag'], before['ETag'])
        self.assertEqual(self.request(path, headers={'Origin': 'https://example.com'})[0], 403)

    @patch('local_server.open_path')
    def test_open_location_launches_the_selected_file_or_directory_without_writes(self, run):
        path = f'/api/projects/{self.id}/open-location'
        _, before, _ = self.request('/api/workspace')
        self.assertEqual(self.request(path, 'POST', {'key': 'current-week'})[0], 200)
        self.assertEqual(run.call_args.args[0], self.repo.path(self.id, 'current/week01.json'))
        status, _, raw = self.request(path, 'POST', {'key': 'project-directory'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['kind'], 'directory')
        self.assertEqual(run.call_args.args[0], self.repo.project_directory(self.id))
        self.assertEqual(self.request(path, 'POST', {'key': 'backup-directory'})[0], 200)
        self.assertEqual(run.call_args.args[0], self.repo.project_directory(self.id) / '备份资料')
        self.assertEqual(self.request(path, 'POST', {'key': 'active-directory'})[0], 200)
        self.assertEqual(run.call_args.args[0], self.repo.path(self.id, 'project.json').parent)
        self.assertEqual(self.request(path, 'POST', {'key': 'agent-guide'})[0], 200)
        self.assertEqual(run.call_args.args[0], Path(__file__).resolve().parent / '记录读写说明.md')
        self.assertEqual(self.request('/api/workspace')[1]['ETag'], before['ETag'])

    @patch('local_server.open_path')
    def test_open_location_rejects_unknown_paths_foreign_origins_and_missing_files(self, run):
        path = f'/api/projects/{self.id}/open-location'
        self.assertEqual(self.request(path, 'POST', {'key': '/tmp/anything.command', 'path': '/tmp/anything.command'})[0], 400)
        self.assertEqual(self.request(path, 'POST', {'key': 'project'}, {'Origin': 'https://example.com'})[0], 403)
        missing = {'project_directory': self.temp.name, 'reading_files': [{'key': 'current-week', 'path': str(Path(self.temp.name) / 'missing.json'), 'exists': False, 'kind': 'file'}], 'other_locations': []}
        with patch.object(self.repo, 'locations', return_value=missing):
            self.assertEqual(self.request(path, 'POST', {'key': 'current-week'})[0], 404)
        run.assert_not_called()

    @patch('local_server.open_path', side_effect=subprocess.CalledProcessError(1, 'open'))
    def test_open_location_reports_default_application_failure(self, run):
        status, _, raw = self.request(f'/api/projects/{self.id}/open-location', 'POST', {'key': 'project'})
        self.assertEqual(status, 400)
        self.assertIn('默认应用', json.loads(raw)['error'])

    def test_loopback_origin_and_source_directory_boundary(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        self.assertEqual(self.request('/api/workspace', headers={'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('/api/workspace', headers={'Host': 'example.com'})[0], 403)
        self.assertEqual(self.request(f'/api/projects/{self.id}/files/source-backups/source.md')[0], 400)
        self.assertEqual(self.request('/data/workspace.json')[0], 404)
        self.assertEqual(self.request('/storage.py')[0], 404)
        self.assertEqual(running_url(self.repo, self.server.server_address[1]), self.url)

    def test_application_and_records_work_after_directory_relocation(self):
        source = Path(__file__).resolve().parent
        moved = Path(self.temp.name) / '迁移后的目录 有空格' / 'trial'
        moved.mkdir(parents=True)
        for name in ('local_server.py', 'storage.py', 'app_paths.py', 'platform_support.py', '记录读写说明.md'):
            shutil.copy2(source / name, moved / name)
        shutil.copytree(source / 'dist', moved / 'dist')
        files = {name: file['data'] for name, file in self.repo.files(self.id).items()}
        relocated = Repository(moved.parent / '项目资料')
        relocated.install(files)
        process = subprocess.Popen([sys.executable, '-u', str(moved / 'local_server.py'), '--port', '0'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            line = process.stdout.readline().strip()
            self.assertTrue(line.startswith('项目札记已启动：http://127.0.0.1:'), line)
            url = line.split('：', 1)[1]
            with urlopen(url + f'/api/projects/{self.id}/locations', timeout=3) as response:
                locations = json.load(response)
            self.assertEqual(Path(locations['project_directory']), relocated.project_directory(self.id))
            guide = next(item for item in locations['reading_files'] if item['key'] == 'agent-guide')
            self.assertEqual(Path(guide['path']), (moved / '记录读写说明.md').resolve())
            self.assertFalse((moved.parent / 'AGENTS.md').exists())
            with urlopen(url + '/reading-plan.js', timeout=3) as response:
                self.assertEqual(response.status, 200)
            file_url = url + f'/api/projects/{self.id}/files/current/week01.json'
            with urlopen(file_url, timeout=3) as response:
                week, revision = json.load(response), response.headers['ETag']
            week['days'][0]['summary'] = '迁移后继续写入'
            request = Request(file_url, data=json.dumps(week).encode(), method='PUT', headers={'Content-Type': 'application/json', 'If-Match': revision})
            with urlopen(request, timeout=3) as response:
                self.assertEqual(response.status, 200)
            self.assertEqual(relocated.read(self.id, 'current/week01.json')[0]['days'][0]['summary'], '迁移后继续写入')
            self.assertEqual(self.repo.read(self.id, 'current/week01.json')[0]['days'][0]['summary'], '')
        finally:
            process.terminate()
            process.communicate(timeout=3)


if __name__ == '__main__':
    unittest.main()
