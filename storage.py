"""Project goals, weekly plans and handoffs live in local JSON files."""
import contextlib
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import uuid

from app_paths import resource_directory
from platform_support import file_lock

VERSION = 2
ACTIVE_DIR = '正在使用文件'
BACKUP_DIR = '备份资料'
MAX_BYTES = 5_000_000
STATUSES = {'未完成', '进行中', '已完成', '休息'}
REPORT_FIELDS = ('completed', 'verification', 'understanding', 'issues', 'codeState', 'nextStep')
HANDOFF_FIELDS = ('summary', 'completed', 'verification', 'projectState', 'openItems', 'notes', 'nextStep')
FILE_RE = re.compile(r'^(current|history)/week(\d{2,3})(-handoff)?\.json$')
ID_RE = re.compile(r'^[a-z][a-z0-9-]{0,63}$')
RECORD_GUIDE = resource_directory() / '记录读写说明.md'


def text(value):
    return isinstance(value, str) and len(value) <= 100000


def number(value):
    return type(value) is int and 1 <= value <= 999


def strings(value):
    return isinstance(value, list) and len(value) <= 500 and all(text(v) for v in value)


def validate_condition(item):
    if 'condition' in item and not text(item['condition']):
        raise ValueError('适用条件必须为文本')


def validate_document(path, data):
    if not isinstance(data, dict) or data.get('schemaVersion') != VERSION:
        raise ValueError('JSON 必须声明 schemaVersion: 2')
    if path == 'roadmap.json':
        goal = data.get('goal')
        if data.get('kind') != 'roadmap' or not isinstance(goal, dict) or not all(text(goal.get(k)) for k in ('title', 'summary')) or not strings(goal.get('outcomes')):
            raise ValueError('长期目标需要标题、说明与成果列表')
        stages = data.get('stages')
        if not isinstance(stages, list) or len(stages) > 100:
            raise ValueError('阶段成果应为列表')
        ids = set()
        for stage in stages:
            if not isinstance(stage, dict) or not isinstance(stage.get('id'), str) or not ID_RE.fullmatch(stage['id']) or stage['id'] in ids:
                raise ValueError('阶段 ID 必须有效且不能重复')
            ids.add(stage['id'])
            validate_condition(stage)
            if stage.get('status') not in STATUSES - {'休息'} or not all(text(stage.get(k)) for k in ('title', 'outcome', 'acceptance')):
                raise ValueError('阶段须包含名称、状态、成果与验收条件')
            weeks = stage.get('plannedWeeks', [])
            if not isinstance(weeks, list) or not all(number(w) for w in weeks) or len(set(weeks)) != len(weeks):
                raise ValueError('阶段的计划周编号不能重复')
            sections = stage.get('sections', [])
            if not isinstance(sections, list) or not all(isinstance(s, dict) and text(s.get('title')) and text(s.get('body')) for s in sections):
                raise ValueError('阶段说明格式不正确')
        plans = data.get('weeklyPlans', [])
        if not isinstance(plans, list) or len(plans) > 999:
            raise ValueError('每周目标应为列表')
        weeks = set()
        for plan in plans:
            if not isinstance(plan, dict) or not number(plan.get('week')) or plan['week'] in weeks:
                raise ValueError('每周目标的周编号必须有效且不能重复')
            weeks.add(plan['week'])
            validate_condition(plan)
            if not all(text(plan.get(k)) for k in ('title', 'outcome', 'acceptance', 'scope')) or not strings(plan.get('goals')):
                raise ValueError('每周目标需要主题、目标、成果、验收与边界')
            if 'stageId' in plan and (not isinstance(plan['stageId'], str) or not ID_RE.fullmatch(plan['stageId'])):
                raise ValueError('每周目标的阶段 ID 不正确')
        return data
    if path == 'project.json':
        current = data.get('current')
        if data.get('kind') != 'project' or not ID_RE.fullmatch(data.get('id', '')) or not text(data.get('name')) or not data['name'].strip():
            raise ValueError('项目名称或 ID 格式不正确')
        if not isinstance(current, dict) or not number(current.get('week')) or not number(current.get('day')):
            raise ValueError('当前进度必须包含有效的 week 和 day')
        if not isinstance(data.get('readOnly', False), bool):
            raise ValueError('readOnly 必须为布尔值')
        if 'collaboration' in data and not strings(data['collaboration']):
            raise ValueError('协作约定应为文本列表')
        roles = data.get('agentRoles', [])
        if not isinstance(roles, list) or len(roles) > 50:
            raise ValueError('角色说明应为列表')
        role_ids = set()
        for role in roles:
            if not isinstance(role, dict) or not isinstance(role.get('id'), str) or not ID_RE.fullmatch(role['id']) or role['id'] in role_ids:
                raise ValueError('角色 ID 必须有效且不能重复')
            role_ids.add(role['id'])
            if not all(text(role.get(k)) and role[k].strip() for k in ('title', 'summary')) or not strings(role.get('reads', [])):
                raise ValueError('角色说明需要名称、职责概述和读取清单')
            sections = role.get('sections')
            if not isinstance(sections, list) or len(sections) > 50 or not all(isinstance(section, dict) and text(section.get('title')) and strings(section.get('items')) for section in sections):
                raise ValueError('角色说明的章节需要标题与规则列表')
            scenarios = role.get('scenarios', [])
            if not isinstance(scenarios, list) or len(scenarios) > 30:
                raise ValueError('接续场景应为列表')
            scenario_ids = set()
            for scenario in scenarios:
                if not isinstance(scenario, dict) or not isinstance(scenario.get('id'), str) or not ID_RE.fullmatch(scenario['id']) or scenario['id'] in scenario_ids:
                    raise ValueError('接续场景 ID 必须有效且不能重复')
                scenario_ids.add(scenario['id'])
                if not all(text(scenario.get(k)) for k in ('title', 'description')) or not strings(scenario.get('additionalReads', [])):
                    raise ValueError('场景需要名称、说明和额外必读清单')
                optional = scenario.get('optionalReads', [])
                if not isinstance(optional, list) or not all(isinstance(item, dict) and text(item.get('key')) and text(item.get('when')) for item in optional):
                    raise ValueError('按需文件需要读取标识和读取时机')
        for key in ('description', 'contextNotes', 'constraints'):
            if key in data and not text(data[key]):
                raise ValueError('项目说明格式不正确：' + key)
        if 'structure' in data and (not isinstance(data['structure'], list) or not all(isinstance(f, dict) and text(f.get('path')) and text(f.get('description')) for f in data['structure'])):
            raise ValueError('项目结构格式不正确')
        if 'runtime' in data and (not isinstance(data['runtime'], dict) or not all(text(v) for v in data['runtime'].values())):
            raise ValueError('运行说明必须使用文本字段')
        return data
    match = FILE_RE.fullmatch(path)
    if not match or data.get('week') != int(match[2]):
        raise ValueError('周编号必须与 JSON 文件名一致')
    if match[3]:
        if data.get('kind') != 'week-handoff' or data.get('status') not in STATUSES - {'休息'}:
            raise ValueError('周交接的类型或状态不正确')
        if not all(text(data.get(k)) for k in HANDOFF_FIELDS):
            raise ValueError('周交接字段不完整')
    else:
        if data.get('kind') != 'week' or data.get('status') not in STATUSES - {'休息'} or not strings(data.get('goals')):
            raise ValueError('周记录的类型、状态或目标格式不正确')
        if 'stageId' in data and (not isinstance(data['stageId'], str) or not ID_RE.fullmatch(data['stageId'])):
            raise ValueError('周目标的关联阶段 ID 不正确')
        days = data.get('days')
        if not isinstance(days, list) or not days or len(days) > 999:
            raise ValueError('每周至少保存一个逻辑日')
        ids = set()
        for day in days:
            if not isinstance(day, dict) or not number(day.get('day')) or day['day'] in ids or day.get('status') not in STATUSES:
                raise ValueError('逻辑日编号不能重复，状态请用已完成、未完成、进行中或休息')
            ids.add(day['day'])
            if not strings(day.get('goals')) or not text(day.get('summary')) or not isinstance(day.get('reports'), list):
                raise ValueError('每日目标、摘要或详细交接格式不正确')
            reports = set()
            for report in day['reports']:
                if not isinstance(report, dict) or not text(report.get('id')) or report['id'] in reports or not all(text(report.get(k)) for k in REPORT_FIELDS):
                    raise ValueError('日交接须有独立 ID 和完整六项字段')
                reports.add(report['id'])
    return data


def encode(data):
    raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise ValueError('单份 JSON 不能超过 5 MB')
    return raw


def etag(raw):
    return '"' + hashlib.sha256(raw).hexdigest() + '"'


def atomic_write(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.saving-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def blank_week(week):
    return dict(schemaVersion=VERSION, kind='week', week=week, status='未完成', goals=[], days=[dict(day=1, status='未完成', goals=[], summary='', reports=[])])


def blank_handoff(week):
    return dict(schemaVersion=VERSION, kind='week-handoff', week=week, status='未完成', **{k: '' for k in HANDOFF_FIELDS})


def blank_roadmap():
    return dict(schemaVersion=VERSION, kind='roadmap', goal={'title': '', 'summary': '', 'outcomes': []}, stages=[], weeklyPlans=[])


def validate_stage_links(files):
    ids = {s['id'] for s in files.get('roadmap.json', {}).get('stages', [])}
    for plan in files.get('roadmap.json', {}).get('weeklyPlans', []):
        if 'stageId' in plan and plan['stageId'] not in ids:
            raise ValueError('每周目标关联的阶段不存在：Week ' + str(plan['week']))
    for name, data in files.items():
        if data.get('kind') == 'week' and 'stageId' in data and data['stageId'] not in ids:
            raise ValueError('周目标关联的阶段不存在：' + name)


class Repository:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.projects_dir = self.directory / 'projects'
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.mutex = threading.RLock()

    @contextlib.contextmanager
    def locked(self):
        with self.mutex, file_lock(self.directory / '.files.lock'):
            yield

    def project_directory(self, project_id):
        if not ID_RE.fullmatch(project_id):
            raise ValueError('项目 ID 格式不正确')
        root = self.projects_dir / project_id
        if self.projects_dir.resolve() not in root.resolve().parents:
            raise ValueError('文件路径超出项目目录')
        return root

    def path(self, project_id, name):
        if name not in {'project.json', 'roadmap.json'} and not FILE_RE.fullmatch(name):
            raise ValueError('不是可读写的项目 JSON 路径')
        root = self.project_directory(project_id)
        base = root / ACTIVE_DIR
        target = base / name
        if base.resolve() not in target.resolve().parents or root.resolve() not in base.resolve().parents:
            raise ValueError('文件路径超出项目目录')
        return target

    def read(self, project_id, name):
        raw = self.path(project_id, name).read_bytes()
        data = validate_document(name, json.loads(raw))
        return data, etag(raw)

    def files(self, project_id, overrides=None):
        overrides = overrides or {}
        project, _ = self.read(project_id, 'project.json')
        if project['id'] != project_id:
            raise ValueError('project.json 的 ID 必须与所在目录一致')
        paths = ['project.json']
        base = self.path(project_id, 'project.json').parent
        if (base / 'roadmap.json').exists() or 'roadmap.json' in overrides:
            paths.append('roadmap.json')
        current = project['current']['week']
        paths.extend(p.relative_to(base).as_posix() for p in sorted((base / 'history').glob('week*.json'))
                     if not FILE_RE.fullmatch(p.relative_to(base).as_posix()) or int(FILE_RE.fullmatch(p.relative_to(base).as_posix())[2]) != current)
        paths += [f'current/week{current:02}.json', f'current/week{current:02}-handoff.json']
        result = {}
        for path in paths:
            if path in overrides:
                data = validate_document(path, overrides[path])
                revision = etag(encode(data))
            else:
                data, revision = self.read(project_id, path)
            result[path] = {'data': data, 'etag': revision}
        week = result[f'current/week{current:02}.json']['data']
        if not any(d['day'] == project['current']['day'] for d in week['days']):
            raise ValueError('当前 Day 在当前周文件中不存在')
        for name, file in result.items():
            if file['data']['kind'] == 'week' and name.replace('.json', '-handoff.json') not in result:
                raise ValueError('周记录缺少独立周交接：' + name)
            if file['data']['kind'] == 'week-handoff' and name.replace('-handoff.json', '.json') not in result:
                raise ValueError('周交接缺少对应周记录：' + name)
        validate_stage_links({name: file['data'] for name, file in result.items()})
        return result

    def locations(self, project_id):
        """Resolve current file locations at read time; never persist machine paths in a copy."""
        with self.locked():
            files = self.files(project_id)
            project = files['project.json']['data']
            current = project['current']['week']
            directory = self.project_directory(project_id).resolve()
            active = self.path(project_id, 'project.json').parent.resolve()
            backups = directory / BACKUP_DIR

            def file_location(key, label, name, note):
                return dict(key=key, label=label, path=str(self.path(project_id, name).resolve()), note=note, exists=True, kind='file')

            reading = []
            if RECORD_GUIDE.is_file():
                reading.append(dict(key='agent-guide', label='记录读写说明', path=str(RECORD_GUIDE), note='规定记录字段、更新职责和保存方式；供负责写入的管理者使用。', exists=True, kind='file'))
            reading.append(file_location('project', '项目概况与结构', 'project.json', '了解结构、运行方式、共同约定、选定角色及当前 Week/Day。'))
            if 'roadmap.json' in files:
                reading.append(file_location('roadmap', '整体目标与阶段', 'roadmap.json', '规划新周或调整方向时核对长期目标、阶段成果和周规划。'))
            reading.append(file_location('current-week', '本周记录', f'current/week{current:02}.json', '读取本周目标、当前日状态及最新报告，确定准确的下一步。'))
            previous = [(name, file['data']) for name, file in files.items() if name.startswith('history/') and file['data']['kind'] == 'week-handoff' and file['data']['status'] == '已完成' and file['data']['week'] < current]
            if previous:
                name, handoff = max(previous, key=lambda pair: pair[1]['week'])
                reading.append(file_location('previous-handoff', f"最近完成周交接 · Week {handoff['week']:02}", name, '承接背景、遗留问题和本周起点；当前状态看本周记录。'))
            handoff_name = f'current/week{current:02}-handoff.json'
            draft = files[handoff_name]['data']['status'] != '已完成'
            others = [file_location('current-handoff', '本周交接' + ('草稿' if draft else ''), handoff_name, '本周汇总；草稿不代表本周已验收完成。' if draft else '本周已保存的交接汇总。')]
            others.extend([
                dict(key='active-directory', label=ACTIVE_DIR, path=str(active), note='项目概况、目标、本周记录和历史周；日常交接读取这里。', exists=True, kind='directory'),
                dict(key='backup-directory', label=BACKUP_DIR, path=str(backups), note='保存前及专项备份，可按需手动清理；不自动删除。', exists=backups.is_dir(), kind='directory', unavailable='尚无备份；下次保存时会创建。')])
            history = active / 'history'
            if history.is_dir():
                others.append(dict(key='history', label='历史周目录', path=str(history.resolve()), note='往期每日记录与周交接。', exists=True, kind='directory'))
            return dict(project_id=project_id, project_name=project['name'], project_directory=str(directory), active_directory=str(active), backup_directory=str(backups), current=project['current'], read_only=project.get('readOnly', False), reading_files=reading, other_locations=others)

    def bundle(self):
        with self.locked():
            projects = []
            for folder in sorted(self.projects_dir.iterdir()):
                if not folder.is_dir() or not ID_RE.fullmatch(folder.name) or not (folder / ACTIVE_DIR / 'project.json').exists():
                    continue
                files = self.files(folder.name)
                meta = files['project.json']['data']
                projects.append({'id': folder.name, 'name': meta['name'], 'files': files})
            # Imported real records appear before newly created test projects.
            projects.sort(key=lambda p: not p['files']['project.json']['data'].get('readOnly', False))
            data = {'schemaVersion': VERSION, 'projects': projects}
            return data, etag(json.dumps(data, ensure_ascii=False, sort_keys=True).encode('utf-8'))

    def backup(self, project_id, name, raw):
        self.path(project_id, name)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        root = self.project_directory(project_id)
        target = root / BACKUP_DIR / '保存前备份' / stamp / name
        if root.resolve() not in target.resolve().parents:
            raise ValueError('备份路径超出项目目录')
        atomic_write(target, raw)

    def save(self, project_id, name, data, expected):
        validate_document(name, data)
        raw = encode(data)
        with self.locked():
            meta, _ = self.read(project_id, 'project.json')
            if meta.get('readOnly'):
                raise PermissionError('该项目当前为只读；可新建项目试写 JSON')
            path = self.path(project_id, name)
            old = path.read_bytes()
            if expected != etag(old):
                raise FileExistsError('JSON 已被其他窗口或 agent 更新，请重新读取后保存')
            if name == 'project.json':
                if data['id'] != project_id:
                    raise ValueError('不能通过编辑文件更改项目 ID')
                week, _ = self.read(project_id, f"current/week{data['current']['week']:02}.json")
                if not any(d['day'] == data['current']['day'] for d in week['days']):
                    raise ValueError('所选当前 Day 不存在')
            elif name == f"current/week{meta['current']['week']:02}.json":
                if not any(d['day'] == meta['current']['day'] for d in data['days']):
                    raise ValueError('不能删除当前逻辑日')
            if name.endswith('-handoff.json') and data['status'] == '已完成':
                week, _ = self.read(project_id, name.replace('-handoff.json', '.json'))
                if any(day['status'] not in {'已完成', '休息'} for day in week['days']):
                    raise ValueError('本周仍有未完成或进行中的逻辑日，周交接请保存为草稿')
            if name == 'roadmap.json' or data['kind'] == 'week':
                self.files(project_id, overrides={name: data})
            self.backup(project_id, name, old)
            atomic_write(path, raw)
        return etag(raw)

    def install(self, files):
        if not isinstance(files, dict) or 'project.json' not in files:
            raise ValueError('导入内容缺少 project.json')
        files = dict(files)
        files.setdefault('roadmap.json', blank_roadmap())
        meta = validate_document('project.json', files['project.json'])
        project_id = meta['id']
        for name, data in files.items():
            self.path(project_id, name)
            validate_document(name, data)
            if data['kind'] == 'week' and name.replace('.json', '-handoff.json') not in files:
                raise ValueError('每份周记录都需要独立的周交接 JSON')
            if data['kind'] == 'week-handoff' and name.replace('-handoff.json', '.json') not in files:
                raise ValueError('周交接缺少对应周记录')
        validate_stage_links(files)
        current = meta['current']
        week_path = f"current/week{current['week']:02}.json"
        handoff_path = f"current/week{current['week']:02}-handoff.json"
        if week_path not in files or handoff_path not in files or not any(d['day'] == current['day'] for d in files[week_path]['days']):
            raise ValueError('导入内容缺少当前周、周交接或当前 Day')
        with self.locked():
            target = self.projects_dir / project_id
            if target.exists():
                raise FileExistsError('项目 ID 已存在；导入不会覆盖已有项目')
            staging = Path(tempfile.mkdtemp(prefix='.import-', dir=self.projects_dir))
            try:
                for name, data in files.items():
                    atomic_write(staging / ACTIVE_DIR / name, encode(data))
                (staging / BACKUP_DIR).mkdir()
                os.replace(staging, target)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        return project_id

    def create(self, name):
        if not text(name) or not name.strip():
            raise ValueError('请填写项目名称')
        project_id = 'project-' + uuid.uuid4().hex[:10]
        meta = dict(schemaVersion=VERSION, kind='project', id=project_id, name=name.strip(), description='', current={'week': 1, 'day': 1}, readOnly=False, structure=[], runtime={'start': '', 'test': '', 'configuration': ''}, contextNotes='', constraints='', collaboration=[], agentRoles=[])
        self.install({'project.json': meta, 'current/week01.json': blank_week(1), 'current/week01-handoff.json': blank_handoff(1)})
        return project_id

    def next_week(self, project_id):
        with self.locked():
            meta, _ = self.read(project_id, 'project.json')
            if meta.get('readOnly'):
                raise PermissionError('只读项目不能推进进度')
            old_week = meta['current']['week']
            prefix = f'week{old_week:02}'
            week, _ = self.read(project_id, 'current/' + prefix + '.json')
            handoff, _ = self.read(project_id, 'current/' + prefix + '-handoff.json')
            if any(d['status'] not in {'已完成', '休息'} for d in week['days']):
                raise ValueError('本周还有未完成或进行中的逻辑日')
            if handoff['status'] != '已完成':
                raise ValueError('请先完成本周周交接')
            new_week = old_week + 1
            if not number(new_week):
                raise ValueError('周编号超出范围')
            new_files = {
                f'current/week{new_week:02}.json': blank_week(new_week),
                f'current/week{new_week:02}-handoff.json': blank_handoff(new_week)}
            for name, data in new_files.items():
                path = self.path(project_id, name)
                if path.exists() and path.read_bytes() != encode(data):
                    raise FileExistsError('下一周文件已有内容，未覆盖')
            week['status'] = '已完成'
            for suffix in ['.json', '-handoff.json']:
                old_path = self.path(project_id, 'current/' + prefix + suffix)
                history = self.path(project_id, 'history/' + prefix + suffix)
                raw = encode(week) if suffix == '.json' else old_path.read_bytes()
                if history.exists() and history.read_bytes() != raw:
                    raise FileExistsError('历史周文件已存在且内容不同，未覆盖')
                atomic_write(history, raw)
            for name, data in new_files.items():
                atomic_write(self.path(project_id, name), encode(data))
            old_project = self.path(project_id, 'project.json').read_bytes()
            meta['current'] = {'week': new_week, 'day': 1}
            self.backup(project_id, 'project.json', old_project)
            atomic_write(self.path(project_id, 'project.json'), encode(meta))
            for suffix in ['.json', '-handoff.json']:
                self.path(project_id, 'current/' + prefix + suffix).unlink()
        return new_week
