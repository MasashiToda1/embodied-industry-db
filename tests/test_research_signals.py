"""研判不得绕过事实引用、主体归属和时间约束。"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from research_signals import load_research_signals


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dir = self.root / 'research/hiring'
        self.dir.mkdir(parents=True)
        self.events = [{'id': 'hiring', 'type': 'hiring_signal',
                        'orgs': [{'id': 'org', 'role': 'subject'}],
                        'evidence': [{'retrieved': '2025-01-01'}]}]
        self.row = dict(id='reading', org='org', topic='control', title='方向线索',
                        judgment='经审核的假设', limitations='不能确认产品采用',
                        strength='limited', evidence_events=['hiring'],
                        reviewed_on='2025-01-03', review_reference='维护者批次记录')

    def run_load(self):
        (self.dir / 'reading.yaml').write_text(yaml.safe_dump(self.row, allow_unicode=True), encoding='utf-8')
        return load_research_signals(self.root, {'org': {}}, self.events)

    def test_uses_observation_not_review_date_and_preserves_facts(self):
        before = copy.deepcopy(self.events)
        self.assertEqual(self.run_load()[0]['last_observed'], '2025-01-01')
        self.assertEqual(self.events, before)

    def test_rejects_missing_review_unknown_or_duplicate_evidence(self):
        original = copy.deepcopy(self.row)
        for change in ({'review_reference': ''}, {'evidence_events': ['missing']},
                       {'evidence_events': ['hiring', 'hiring']}, {'strength': 'high'},
                       {'reviewed_on': '2024-12-31'}, {'reviewed_on': '9999-01-01'}):
            with self.subTest(change=change):
                self.row = dict(original, **change)
                with self.assertRaises(ValueError): self.run_load()

    def test_rejects_wrong_org_role_or_non_hiring_evidence(self):
        for role in ('investor', 'counterparty'):
            self.events[0]['orgs'][0]['role'] = role
            with self.assertRaises(ValueError): self.run_load()
        self.events[0]['orgs'][0]['role'] = 'subject'
        self.events[0]['orgs'][0]['id'] = 'another'
        with self.assertRaises(ValueError): self.run_load()
        self.events[0]['orgs'][0]['id'] = 'org'
        self.events[0]['type'] = 'publication'
        with self.assertRaises(ValueError): self.run_load()

    def test_rejects_duplicate_assessment(self):
        self.run_load()
        (self.dir / 'duplicate.yaml').write_text((self.dir / 'reading.yaml').read_text(encoding='utf-8'), encoding='utf-8')
        with self.assertRaises(ValueError): self.run_load()

    def detailed(self):
        snapshot='snapshots/hiring.json'
        urls=['https://example.com/job/1','https://example.com/job/2']
        raw={'format':'hiring-reviewed-excerpts-v1','org':'org','groups':[
            {'hash':'a'*64,'excerpts':['负责机器人真机测试'],
             'sources':[{'url':u,'title':'测试工程师','retrieved':'2025-01-01'} for u in urls]}]}
        (self.root/'snapshots').mkdir(exist_ok=True)
        (self.root/snapshot).write_text(json.dumps(raw),encoding='utf-8')
        self.events[0]['evidence']=[{'url':u,'retrieved':'2025-01-01','snapshot':snapshot} for u in urls]
        self.row.update(coverage=dict(known_urls=10,saved_bodies=4,unique_bodies=3,reviewed_bodies=3),
            evidence_groups=[dict(hash='a'*64,role='岗位职责',quote='负责机器人真机测试',reason='支持真机验证',urls=urls)])

    def test_count_bodies_not_duplicate_links(self):
        self.detailed()
        result=self.run_load()[0]
        self.assertEqual(result['evidence_counts'],dict(direct=1,requirements=0,statements=0,groups=1,links=2))
        self.assertEqual(len(result['evidence_groups'][0]['sources']),2)
        self.row['evidence_groups'][0]['role']='任职要求'
        self.assertEqual(self.run_load()[0]['evidence_counts']['direct'],0)

    def test_reject_fabricated_quote_foreign_link_duplicate_group_and_incomplete_coverage(self):
        self.detailed(); original=copy.deepcopy(self.row)
        for field,value in [('quote','不存在的原文'),('hash','b'*64),('urls',['https://other.org/job']),('role','产品事实')]:
            with self.subTest(field=field):
                self.row=copy.deepcopy(original);self.row['evidence_groups'][0][field]=value
                with self.assertRaises(ValueError):self.run_load()
        self.row=copy.deepcopy(original)
        self.row['evidence_groups']*=2
        with self.assertRaises(ValueError):self.run_load()
        self.row=copy.deepcopy(original);self.row['coverage']['reviewed_bodies']=2
        with self.assertRaises(ValueError):self.run_load()
        self.row=copy.deepcopy(original);self.row['evidence_groups'][0]['urls'].pop()
        with self.assertRaises(ValueError):self.run_load()

    def test_direction_recency_uses_its_own_sources(self):
        self.detailed()
        self.events[0]['evidence'].append({'url':'https://example.com/other','retrieved':'2025-01-03'})
        self.assertEqual(self.run_load()[0]['last_observed'],'2025-01-01')


if __name__ == '__main__': unittest.main()
