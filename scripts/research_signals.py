"""招聘研判独立于事实事件；只导出有审核记录、可回溯的条目。"""
from datetime import date
from pathlib import Path
import json
import re

import yaml


def detailed_evidence(root, row, linked):
    """Counts come from reviewed body groups and must resolve to event snapshots."""
    groups = row.get('evidence_groups')
    if not isinstance(groups, list) or not groups:
        raise ValueError('evidence_groups 必须是非空列表')
    coverage = row.get('coverage')
    keys = {'known_urls', 'saved_bodies', 'unique_bodies', 'reviewed_bodies'}
    if not isinstance(coverage, dict) or set(coverage) != keys or any(type(v) is not int or v < 0 for v in coverage.values()):
        raise ValueError('采集覆盖字段不合法')
    if not coverage['known_urls'] >= coverage['saved_bodies'] >= coverage['unique_bodies'] == coverage['reviewed_bodies'] > 0:
        raise ValueError('采集覆盖数量不自洽或正文尚未全量复核')
    sources = {s['url']: s for ev in linked if ev['type'] == 'hiring_signal'
               for s in ev.get('evidence', []) if s.get('url')}
    snapshots, seen, result, dates = {}, set(), [], []
    for g in groups:
        if not isinstance(g, dict) or set(g) != {'hash', 'role', 'quote', 'reason', 'urls'}:
            raise ValueError('证据组字段不完整或未知')
        digest = g['hash']
        if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest) or digest in seen:
            raise ValueError('正文hash无效或重复')
        seen.add(digest)
        if g['role'] not in {'岗位职责', '任职要求', '公司自述'}:
            raise ValueError('证据角色无效')
        if any(not isinstance(g[k], str) or not g[k].strip() for k in ('quote', 'reason')):
            raise ValueError('缺少原文或支持理由')
        urls = g['urls']
        if not isinstance(urls, list) or not urls or any(not isinstance(u, str) for u in urls) or len(set(urls)) != len(urls):
            raise ValueError('证据链接为空或重复')
        resolved = []
        for url in urls:
            source = sources.get(url)
            if not source or not url.startswith('https://'):
                raise ValueError('证据链接不属于所引招聘事实')
            snapshot = source.get('snapshot', '')
            path = (root / snapshot).resolve()
            if not path.is_relative_to((root / 'snapshots').resolve()) or path.suffix != '.json':
                raise ValueError('证据快照路径不合法')
            if snapshot not in snapshots:
                doc = json.loads(path.read_text(encoding='utf-8'))
                if doc.get('org') != row['org'] or doc.get('format') != 'hiring-reviewed-excerpts-v1':
                    raise ValueError('快照主体或格式不符')
                snapshots[snapshot] = {x['hash']: x for x in doc['groups']}
            raw = snapshots[snapshot].get(digest)
            if not raw or g['quote'] not in raw['excerpts'] or set(urls) != {s['url'] for s in raw['sources']}:
                raise ValueError('原文/正文组/完整链接与快照不符')
            archived = next(s for s in raw['sources'] if s['url'] == url)
            if str(source['retrieved']) != archived['retrieved']:
                raise ValueError('核验日期与快照不符')
            dates.append(archived['retrieved'])
            resolved.append(dict(archived, snapshot=snapshot))
        result.append(dict(g, sources=resolved))
    if len(result) > coverage['reviewed_bodies']:
        raise ValueError('方向证据数超过已审核正文数')
    counts = {'direct': sum(g['role'] == '岗位职责' for g in result),
              'requirements': sum(g['role'] == '任职要求' for g in result),
              'statements': sum(g['role'] == '公司自述' for g in result),
              'groups': len(result), 'links': sum(len(g['urls']) for g in result)}
    return result, counts, dates


def load_research_signals(root: Path, orgs: dict, events: list) -> list:
    by_id = {e['id']: e for e in events}
    result, seen = [], set()
    required = {'id', 'org', 'topic', 'title', 'judgment', 'limitations',
                'strength', 'evidence_events', 'reviewed_on', 'review_reference'}
    optional = {'evidence_groups', 'coverage', 'kind', 'next_check'}
    for path in sorted((root / 'research/hiring').glob('*.yaml')):
        row = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(row, dict) or not required <= set(row) or set(row) - required - optional:
            raise ValueError(f'{path}: 研判字段不完整或含未知字段')
        for key in required - {'evidence_events'}:
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError(f'{path}: {key} 必须为非空字符串（日期请加引号）')
        if row.get('kind', 'focus') not in {'focus', 'watch'}:
            raise ValueError(f'{path}: 未知研判类型')
        if 'next_check' in row and (not isinstance(row['next_check'], str) or not row['next_check'].strip()):
            raise ValueError(f'{path}: 核验下一步不能为空')
        if ('coverage' in row) != ('evidence_groups' in row):
            raise ValueError(f'{path}: 原文证据与覆盖口径必须一起提供')
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
        extra = {}
        if 'evidence_groups' in row:
            groups, counts, observed = detailed_evidence(root, row, linked)
            extra = {'evidence_groups': groups, 'evidence_counts': counts}
        if not observed:
            raise ValueError(f'{path}: 招聘证据缺少核验日期')
        if any(date.fromisoformat(d) > reviewed for d in observed):
            raise ValueError(f'{path}: 审核不能早于引用的招聘证据核验')
        seen.add(row['id'])
        result.append(dict(row, last_observed=max(observed), **extra))
    return result
