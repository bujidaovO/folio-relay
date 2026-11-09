import json
from pathlib import Path
import shutil
import tempfile
import unittest

from storage import ACTIVE_DIR, BACKUP_DIR, Repository, REPORT_FIELDS, atomic_write, encode


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(self.temp.name)
        self.id = self.repo.create('测试项目')

    def tearDown(self):
        self.temp.cleanup()

    def save(self, path, change):
        data, revision = self.repo.read(self.id, path)
        change(data)
        self.repo.save(self.id, path, data, revision)

    def test_files_are_the_source_of_truth_and_agent_edits_reload(self):
        path = self.repo.path(self.id, 'current/week01.json')
        data = json.loads(path.read_text())
        data['days'][0]['goals'] = ['agent 直接修改 JSON']
        atomic_write(path, encode(data))
        bundle, _ = self.repo.bundle()
        self.assertEqual(bundle['projects'][0]['files']['current/week01.json']['data']['days'][0]['goals'], ['agent 直接修改 JSON'])

    def test_report_history_and_unknown_fields_are_preserved(self):
        report = dict(id='part-1', **{field: '' for field in REPORT_FIELDS}, decision='保留一次讨论结论')
        report['completed'] = '第一段完成'
        def update(data):
            data['days'][0]['status'] = '进行中'
            data['days'][0]['reports'] = [report, dict(report, id='part-2', completed='第二段完成')]
        self.save('current/week01.json', update)
        raw = self.repo.read(self.id, 'current/week01.json')[0]['days'][0]
        self.assertEqual(len(raw['reports']), 2)
        self.assertEqual(raw['reports'][0]['decision'], report['decision'])
        self.assertEqual(raw['status'], '进行中')

    def test_stale_save_is_rejected_and_backup_is_json_v2(self):
        first, rev = self.repo.read(self.id, 'current/week01.json')
        self.save('current/week01.json', lambda d: d['days'][0].update(summary='新的记录'))
        first['days'][0]['summary'] = '旧的记录'
        with self.assertRaises(FileExistsError):
            self.repo.save(self.id, 'current/week01.json', first, rev)
        self.assertEqual(self.repo.read(self.id, 'current/week01.json')[0]['days'][0]['summary'], '新的记录')
        backups = list((self.repo.project_directory(self.id) / BACKUP_DIR).rglob('*.json'))
        self.assertTrue(backups)
        self.assertTrue(all(json.loads(p.read_text())['schemaVersion'] == 2 for p in backups))

    def test_each_project_owns_its_records_and_backups(self):
        other = self.repo.create('另一个项目')
        self.save('current/week01.json', lambda d: d['days'][0].update(summary='第一个项目'))
        data, revision = self.repo.read(other, 'project.json')
        data['description'] = '第二个项目'
        self.repo.save(other, 'project.json', data, revision)
        for project_id in (self.id, other):
            root = self.repo.project_directory(project_id)
            self.assertEqual({p.name for p in root.iterdir()}, {ACTIVE_DIR, BACKUP_DIR})
            backups = list((root / BACKUP_DIR / '保存前备份').rglob('*.json'))
            self.assertEqual(len(backups), 1)
            self.assertTrue(self.repo.path(project_id, 'project.json').is_relative_to(root / ACTIVE_DIR))
        self.assertFalse((self.repo.directory / 'backups').exists())
        self.assertEqual(self.repo.read(other, 'current/week01.json')[0]['days'][0]['summary'], '')

    def test_backups_are_manual_and_can_be_deleted_without_affecting_records(self):
        root = self.repo.project_directory(self.id)
        backups = root / BACKUP_DIR
        old = backups / '保存前备份' / '20000101-000000-000000' / 'project.json'
        atomic_write(old, self.repo.path(self.id, 'project.json').read_bytes())
        self.save('current/week01.json', lambda d: d['days'][0].update(summary='新的记录'))
        self.assertTrue(old.exists(), '旧备份不自动删除')
        before = {name: file['data'] for name, file in self.repo.files(self.id).items()}
        shutil.rmtree(backups)
        self.assertEqual({name: file['data'] for name, file in self.repo.files(self.id).items()}, before)
        missing = next(item for item in self.repo.locations(self.id)['other_locations'] if item['key'] == 'backup-directory')
        self.assertFalse(missing['exists'])
        self.assertFalse(backups.exists(), '读取资料不会重建已手动删除的备份目录')
        self.save('current/week01.json', lambda d: d['days'][0].update(summary='清理后继续'))
        self.assertEqual(len(list(backups.rglob('*.json'))), 1)

    def test_copying_one_project_folder_includes_records_and_backups(self):
        self.save('current/week01.json', lambda d: d['days'][0].update(summary='迁移前记录'))
        root = self.repo.project_directory(self.id)
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        moved = Repository(Path(self.temp.name) / '另一份资料 有空格')
        target = moved.project_directory(self.id)
        shutil.copytree(root, target)
        self.assertEqual(before, {str(p.relative_to(target)): p.read_bytes() for p in target.rglob('*') if p.is_file()})
        self.assertEqual(moved.bundle()[0]['projects'][0]['id'], self.id)
        data, revision = moved.read(self.id, 'current/week01.json')
        data['days'][0]['summary'] = '迁移后继续'
        moved.save(self.id, 'current/week01.json', data, revision)
        self.assertEqual(self.repo.read(self.id, 'current/week01.json')[0]['days'][0]['summary'], '迁移前记录')
        self.assertEqual(len(list((target / BACKUP_DIR).rglob('*.json'))), 2)

    def test_invalid_json_does_not_reset_files(self):
        path = self.repo.path(self.id, 'current/week01.json')
        path.write_text('{invalid')
        with self.assertRaises(ValueError):
            self.repo.bundle()
        self.assertEqual(path.read_text(), '{invalid')

    def test_readonly_copy_cannot_be_overwritten(self):
        self.save('project.json', lambda d: d.update(readOnly=True))
        week, rev = self.repo.read(self.id, 'current/week01.json')
        with self.assertRaises(PermissionError):
            self.repo.save(self.id, 'current/week01.json', week, rev)
        with self.assertRaises(PermissionError):
            self.repo.next_week(self.id)

    def test_week_handoff_is_independent_and_has_no_redundant_column(self):
        handoff, _ = self.repo.read(self.id, 'current/week01-handoff.json')
        self.assertNotIn('days', handoff)
        self.assertNotIn('reports', handoff)
        self.assertNotIn('doNotRepeat', handoff)
        self.assertNotIn('requirements', handoff)

    def test_cannot_finalize_or_archive_an_unfinished_week(self):
        handoff, rev = self.repo.read(self.id, 'current/week01-handoff.json')
        handoff['status'] = '已完成'
        with self.assertRaises(ValueError):
            self.repo.save(self.id, 'current/week01-handoff.json', handoff, rev)
        with self.assertRaises(ValueError):
            self.repo.next_week(self.id)

    def test_next_week_preserves_reports_and_handoff_in_history(self):
        self.save('current/week01.json', lambda d: d['days'][0].update(status='已完成', summary='本周完成'))
        self.save('current/week01-handoff.json', lambda d: d.update(status='已完成', completed='本周成果', nextStep='下周起点'))
        self.assertEqual(self.repo.next_week(self.id), 2)
        self.assertEqual(self.repo.read(self.id, 'project.json')[0]['current'], {'week': 2, 'day': 1})
        self.assertEqual(self.repo.read(self.id, 'history/week01.json')[0]['days'][0]['summary'], '本周完成')
        self.assertEqual(self.repo.read(self.id, 'history/week01-handoff.json')[0]['nextStep'], '下周起点')
        self.assertFalse(self.repo.path(self.id, 'current/week01.json').exists())
        self.repo.bundle()

    def test_locations_follow_the_data_directory_without_writing_records(self):
        repo = Repository(Path(self.temp.name) / '自选 资料目录')
        project_id = repo.create('路径测试')
        before = {p: p.read_bytes() for p in repo.directory.rglob('*') if p.is_file()}
        locations = repo.locations(project_id)
        reading = {item['key']: item for item in locations['reading_files']}
        self.assertEqual(Path(locations['project_directory']), repo.project_directory(project_id).resolve())
        self.assertEqual(Path(locations['active_directory']), repo.path(project_id, 'project.json').parent.resolve())
        self.assertEqual(Path(reading['current-week']['path']), repo.path(project_id, 'current/week01.json').resolve())
        self.assertEqual(set(reading), {'agent-guide', 'project', 'roadmap', 'current-week'})
        self.assertEqual(Path(reading['agent-guide']['path']), Path(__file__).resolve().parent / '记录读写说明.md')
        self.assertNotIn('source-backups', {item['key'] for item in locations['other_locations']})
        self.assertTrue(all(Path(item['path']).exists() for item in locations['reading_files']))
        self.assertEqual(before, {p: p.read_bytes() for p in repo.directory.rglob('*') if p.is_file()})

    def test_locations_select_the_latest_final_handoff_after_archiving(self):
        for week in (1, 2):
            self.save(f'current/week{week:02}.json', lambda d: d['days'][0].update(status='已完成'))
            self.save(f'current/week{week:02}-handoff.json', lambda d: d.update(status='已完成'))
            self.repo.next_week(self.id)
        locations = self.repo.locations(self.id)
        reading = {item['key']: item for item in locations['reading_files']}
        self.assertEqual(reading['current-week']['path'], str(self.repo.path(self.id, 'current/week03.json').resolve()))
        self.assertEqual(reading['previous-handoff']['path'], str(self.repo.path(self.id, 'history/week02-handoff.json').resolve()))
        current = next(item for item in locations['other_locations'] if item['key'] == 'current-handoff')
        self.assertIn('草稿', current['label'])
        self.assertNotIn(current['path'], [item['path'] for item in reading.values()])

    def test_locations_only_include_managed_records(self):
        outside = Path(self.temp.name) / 'outside-documents'
        outside.mkdir()
        self.save('project.json', lambda d: d.update(provenance={'sourceDirectory': str(outside)}))
        (self.repo.path(self.id, 'project.json').parent / 'source-backups').mkdir()
        locations = self.repo.locations(self.id)
        self.assertEqual({item['key'] for item in locations['other_locations']}, {'current-handoff', 'active-directory', 'backup-directory'})
        outside.rmdir()
        self.assertEqual(self.repo.locations(self.id), locations)

    def test_import_cannot_replace_existing_project_or_escape_directory(self):
        files = {path: file['data'] for path, file in self.repo.files(self.id).items()}
        with self.assertRaises(FileExistsError):
            self.repo.install(files)
        with self.assertRaises(ValueError):
            self.repo.path(self.id, '../project.json')
        with self.assertRaises(ValueError):
            self.repo.path('../outside', 'project.json')

    def test_current_day_must_exist_and_daily_status_is_simple(self):
        project, rev = self.repo.read(self.id, 'project.json')
        project['current']['day'] = 9
        with self.assertRaises(ValueError):
            self.repo.save(self.id, 'project.json', project, rev)
        week, rev = self.repo.read(self.id, 'current/week01.json')
        week['days'][0]['status'] = '待开始'
        with self.assertRaises(ValueError):
            self.repo.save(self.id, 'current/week01.json', week, rev)

    def seed_stage(self):
        def update(data):
            data['goal'].update(title='完成本地项目', summary='形成可用成果', outcomes=['可重复验证'])
            data['stages'] = [{'id': 'prototype', 'title': '原型', 'status': '进行中', 'outcome': '可使用', 'acceptance': '通过真实数据验证', 'plannedWeeks': [1, 2], 'sections': []}]
        self.save('roadmap.json', update)

    def test_project_and_roadmap_roundtrip_without_external_documents(self):
        self.seed_stage()
        self.save('project.json', lambda d: d.update(collaboration=['先说明设计，再逐步实现']))
        self.save('current/week01.json', lambda d: d['days'][0].update(status='已完成', summary='历史记录'))
        self.save('current/week01-handoff.json', lambda d: d.update(status='已完成', summary='历史周交接'))
        self.repo.next_week(self.id)
        self.save('current/week02.json', lambda d: d['days'][0].update(status='进行中', summary='从这里继续'))
        files = {name: file['data'] for name, file in self.repo.files(self.id).items()}
        self.assertEqual(set(files['roadmap.json']), {'schemaVersion', 'kind', 'goal', 'stages', 'weeklyPlans'})
        restored = Repository(Path(self.temp.name) / '载入的资料')
        restored_id = restored.install(json.loads(json.dumps(files)))
        self.assertEqual(restored_id, self.id)
        self.assertEqual({name: file['data'] for name, file in restored.files(restored_id).items()}, files)
        self.assertEqual(files['project.json']['current'], {'week': 2, 'day': 1})
        self.assertEqual(files['history/week01.json']['days'][0]['summary'], '历史记录')
        self.assertEqual(files['history/week01-handoff.json']['summary'], '历史周交接')

    def test_stage_references_must_survive_roadmap_updates(self):
        self.seed_stage()
        self.save('current/week01.json', lambda d: d.update(stageId='prototype'))
        roadmap, rev = self.repo.read(self.id, 'roadmap.json')
        roadmap['stages'] = []
        with self.assertRaises(ValueError):
            self.repo.save(self.id, 'roadmap.json', roadmap, rev)
        self.assertEqual(len(self.repo.read(self.id, 'roadmap.json')[0]['stages']), 1)
        with self.assertRaises(ValueError):
            self.save('current/week01.json', lambda d: d.update(stageId='missing'))
        self.assertEqual(self.repo.read(self.id, 'current/week01.json')[0]['stageId'], 'prototype')

    def test_roadmap_stale_write_and_readonly_copy_are_protected(self):
        original, rev = self.repo.read(self.id, 'roadmap.json')
        self.seed_stage()
        with self.assertRaises(FileExistsError):
            self.repo.save(self.id, 'roadmap.json', original, rev)
        roadmap, rev = self.repo.read(self.id, 'roadmap.json')
        self.save('project.json', lambda d: d.update(readOnly=True))
        with self.assertRaises(PermissionError):
            self.repo.save(self.id, 'roadmap.json', roadmap, rev)

    def test_future_weekly_goals_do_not_create_execution_or_advance_progress(self):
        self.seed_stage()
        plan = {'week': 5, 'title': '后续周', 'stageId': 'prototype', 'goals': ['后续目标'], 'outcome': '预期成果', 'acceptance': '可验证', 'scope': '保持范围'}
        self.save('roadmap.json', lambda d: d.update(weeklyPlans=[plan]))
        self.assertEqual(self.repo.read(self.id, 'project.json')[0]['current'], {'week': 1, 'day': 1})
        self.assertFalse(self.repo.path(self.id, 'current/week05.json').exists())
        files = self.repo.files(self.id)
        self.assertEqual(files['roadmap.json']['data']['weeklyPlans'][0], plan)
        self.assertEqual(files['current/week01.json']['data']['status'], '未完成')

    def test_weekly_plan_duplicates_and_unknown_stage_are_rejected(self):
        self.seed_stage()
        plan = {'week': 4, 'title': '周目标', 'stageId': 'prototype', 'goals': ['目标'], 'outcome': '成果', 'acceptance': '验收', 'scope': '边界'}
        with self.assertRaises(ValueError):
            self.save('roadmap.json', lambda d: d.update(weeklyPlans=[plan, plan]))
        with self.assertRaises(ValueError):
            self.save('roadmap.json', lambda d: d.update(weeklyPlans=[dict(plan, stageId='missing')]))
        self.save('roadmap.json', lambda d: d.update(weeklyPlans=[plan]))
        with self.assertRaises(ValueError):
            self.save('roadmap.json', lambda d: d.update(stages=[]))

    def test_conditional_goals_require_a_condition_and_do_not_change_progress(self):
        self.seed_stage()
        plan = {'week': 10, 'title': '可选接入', 'stageId': 'prototype', 'goals': ['接入验证'], 'outcome': '示例', 'acceptance': '可重复', 'scope': '本项目部分', 'condition': []}
        with self.assertRaises(ValueError):
            self.save('roadmap.json', lambda d: d.update(weeklyPlans=[plan]))
        plan['condition'] = '仅在选择本项目作为示例时执行'
        self.save('roadmap.json', lambda d: d.update(weeklyPlans=[plan]))
        self.assertEqual(self.repo.read(self.id, 'project.json')[0]['current'], {'week': 1, 'day': 1})
        self.assertFalse(self.repo.path(self.id, 'current/week10.json').exists())

    def test_collaboration_rules_can_be_updated_without_changing_progress(self):
        rules = ['整体设计先行，具体实现渐进', '当前问题处理完再进入下一步']
        self.save('project.json', lambda d: d.update(collaboration=rules))
        project, revision = self.repo.read(self.id, 'project.json')
        self.assertEqual(project['collaboration'], rules)
        self.assertEqual(project['current'], {'week': 1, 'day': 1})
        project['collaboration'] = '应当是列表'
        with self.assertRaises(ValueError):
            self.repo.save(self.id, 'project.json', project, revision)

    def test_agent_roles_roundtrip_without_changing_week_records(self):
        self.assertEqual(self.repo.read(self.id, 'project.json')[0]['agentRoles'], [])
        before = self.repo.read(self.id, 'current/week01.json')
        role = {'id': 'execution', 'title': '执行对话', 'summary': '执行当前任务并提交交接', 'reads': ['project', 'current-week'], 'sections': [{'title': '操作方式', 'items': ['从当前步骤继续', '结束时提交六项交接']}]}
        role['scenarios'] = [{'id': 'new-week', 'title': '新周开始', 'description': '先承接上周状态', 'additionalReads': ['previous-handoff'], 'optionalReads': [{'key': 'roadmap', 'when': '核对阶段时'}]}]
        self.save('project.json', lambda d: d.update(agentRoles=[role]))
        self.assertEqual(self.repo.read(self.id, 'current/week01.json'), before)
        files = {name: file['data'] for name, file in self.repo.files(self.id).items()}
        files['project.json']['id'] = 'roles-roundtrip'
        self.repo.install(files)
        restored = self.repo.read('roles-roundtrip', 'project.json')[0]
        self.assertEqual(restored['agentRoles'], [role])
        self.assertEqual(restored['current'], {'week': 1, 'day': 1})

    def test_invalid_or_duplicate_agent_roles_are_rejected(self):
        role = {'id': 'manager', 'title': '管理对话', 'summary': '维护项目记录', 'reads': ['project'], 'sections': [{'title': '更新', 'items': ['先读当前记录']}]}
        for roles in ([role, role], [dict(role, sections='应当是章节列表')], [dict(role, sections=[{'title': '更新', 'items': '应当是规则列表'}])], [dict(role, reads='project.json')]):
            with self.assertRaises(ValueError):
                self.save('project.json', lambda d: d.update(agentRoles=roles))
        self.assertEqual(self.repo.read(self.id, 'project.json')[0]['agentRoles'], [])

    def test_invalid_scenario_configuration_is_rejected(self):
        role = {'id': 'manager', 'title': '管理', 'summary': '读取总结并更新记录', 'reads': ['project'], 'sections': []}
        scene = {'id': 'summary', 'title': '读取执行总结', 'description': '从指定位置读取后更新 JSON', 'additionalReads': [], 'optionalReads': [{'key': 'roadmap', 'when': '调整目标时'}]}
        for scenarios in ('不是列表', [scene, scene], [dict(scene, additionalReads='previous-handoff')], [dict(scene, optionalReads=[{'key': 'roadmap', 'when': False}])]):
            with self.assertRaises(ValueError):
                self.save('project.json', lambda d: d.update(agentRoles=[dict(role, scenarios=scenarios)]))
        self.assertEqual(self.repo.read(self.id, 'project.json')[0]['current'], {'week': 1, 'day': 1})

    def test_future_goals_are_not_limited_by_a_previous_learning_schedule(self):
        self.seed_stage()
        plan = {'week': 27, 'title': '项目后续迭代', 'stageId': 'prototype', 'goals': ['按实际需求安排'], 'outcome': '可用迭代', 'acceptance': '通过相应检查', 'scope': '当前项目'}
        self.save('roadmap.json', lambda d: d.update(weeklyPlans=[plan]))
        self.assertEqual(self.repo.read(self.id, 'roadmap.json')[0]['weeklyPlans'], [plan])
        self.assertEqual(self.repo.read(self.id, 'project.json')[0]['current']['week'], 1)


if __name__ == '__main__':
    unittest.main()
