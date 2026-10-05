"""招聘研判独立于事实事件；只导出有审核记录、可回溯的条目。"""
from datetime import date
from pathlib import Path

import yaml


def load_research_signals(root: Path, orgs: dict, events: list) -> list:
    by_id = {e['id']: e for e in events}
    result, seen = [], set()
    required = {'id', 'org', 'topic', 'title', 'judgment', 'limitations',
                'strength', 'evidence_events', 'reviewed_on', 'review_reference'}
    for path in sorted((root / 'research/hiring').glob('*.yaml')):
        row = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f'{path}: 研判字段不完整或含未知字段')
        for key in required - {'evidence_events'}:
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError(f'{path}: {key} 必须为非空字符串（日期请加引号）')
        if row['id'] in seen or row['org'] not in orgs:
            raise ValueError(f'{path}: 重复研判 ID 或未知主体')
        if row['strength'] not in {'limited', 'supported', 'corroborated'}:
            raise ValueError(f'{path}: 未知证据强度')
        reviewed = date.fromisoformat(row['reviewed_on'])
        if reviewed > date.today():
            raise ValueError(f'{path}: 审核日期不能在未来')
        refs = row['evidence_events']
        if not isinstance(refs, list) or not refs or any(not isinstance(x, str) for x in refs):
            raise ValueError(f'{path}: 必须引用事实事件')
        if len(set(refs)) != len(refs):
            raise ValueError(f'{path}: 证据事件重复')
        linked = []
        for eid in refs:
            ev = by_id.get(eid)
            if not ev or not any(o['id'] == row['org'] and o.get('role') == 'subject'
                                 for o in ev.get('orgs', [])):
                raise ValueError(f'{path}: 证据不存在或不是该主体的事件：{eid}')
            linked.append(ev)
        hiring = [e for e in linked if e['type'] == 'hiring_signal']
        if not hiring:
            raise ValueError(f'{path}: 至少引用一条招聘事实')
        # 审核时间不用于刷新线索。核验日期也不等于岗位发布日期或仍在招聘。
        observed = [str(s['retrieved']) for e in hiring for s in e.get('evidence', [])
                    if s.get('retrieved')]
        if not observed:
            raise ValueError(f'{path}: 招聘证据缺少核验日期')
        if any(date.fromisoformat(d) > reviewed for d in observed):
            raise ValueError(f'{path}: 审核不能早于引用的招聘证据核验')
        seen.add(row['id'])
        result.append(dict(row, last_observed=max(observed)))
    return result
