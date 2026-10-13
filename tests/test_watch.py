"""发现漏报的回归：论文链接归属、摘要尾部、同名及伪造域名。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import watch


class WatchAttributionTests(unittest.TestCase):
    def setUp(self):
        self.orgs = [dict(id='dexforce', zh='跨维智能', en='DexForce',
                          aliases=['UNITAS'], accounts={'github': 'DexForce'}),
                     dict(id='other', zh='另一主体', en='Other',
                          aliases=[], accounts={'github': 'Other'})]

    def test_official_repo_after_long_abstract(self):
        summary = 'Robot manipulation. ' * 30 + 'https://github.com/dexforce/UNITAS.'
        xml = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>UNITAS</title>'
               '<summary>' + summary + '</summary></entry></feed>').encode()
        response = watch.httpx.Response(200, content=xml,
                                      request=watch.httpx.Request('GET', 'https://export.arxiv.org'))
        with patch.object(watch.time, 'sleep'), patch.object(watch.httpx, 'get', return_value=response):
            item = watch.fetch_arxiv('cat:cs.RO', 40)[0]
        self.assertEqual(watch.match_paper_org(item['summary'], self.orgs)['id'], 'dexforce')

    def test_untrusted_names_and_domains_do_not_attribute(self):
        for text in ['Uses DexForce robots', 'https://github.com.evil.test/DexForce/UNITAS',
                     'https://github.com/DexForceElse/UNITAS', 'https://github.com/DexForce',
                     'https://[invalid/DexForce/UNITAS']:
            self.assertIsNone(watch.match_paper_org(text, self.orgs))

    def test_ambiguous_owners_remain_unattributed(self):
        self.assertIsNone(watch.match_paper_org(
            'https://github.com/DexForce/UNITAS https://github.com/Other/baseline', self.orgs))

    def test_company_title_still_required_for_news(self):
        self.assertIsNone(watch.match_org('合作方提到跨维智能', self.orgs, title='另一公司发布产品'))


class WatchGroupingTests(unittest.TestCase):
    def item(self, title, url, date='2026-10-12', source='GitHub'):
        return dict(title=title, url=url, date=date, source=source,
                    tier='official', kind='publication', org={'id': 'a', 'zh': '甲公司'})

    def groups(self, *items):
        return watch.cluster_hits([(str(i), item) for i, item in enumerate(items)])

    def test_same_company_and_day_do_not_merge_different_artifacts(self):
        self.assertEqual(len(self.groups(
            self.item('发布 Trident 模型', 'https://huggingface.co/a/Trident'),
            self.item('新建 llama.cpp-omni', 'https://github.com/a/llama.cpp-omni'))), 2)

    def test_complete_title_required_not_shared_prefix(self):
        prefix = '相同的长标题前缀' * 8
        self.assertEqual(len(self.groups(self.item(prefix + '模型甲', 'https://a/1'),
                                         self.item(prefix + '模型乙', 'https://b/2'))), 2)

    def test_identical_title_across_dates_still_groups(self):
        groups = self.groups(self.item('模型发布', 'https://a/1'),
                             self.item('模型发布', 'https://b/2', '2026-10-08'))
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)

    def test_repeated_url_does_not_add_corroboration(self):
        groups = self.groups(self.item('模型发布', 'https://a/1'),
                             self.item('另一标题', 'https://a/1#details'))
        self.assertEqual([len(g) for g in groups], [1])

    def test_links_do_not_assert_independence(self):
        body = watch.issue_body_group([self.item('模型发布', 'https://a/1'),
                                       self.item('模型发布', 'https://b/2')])
        self.assertIn('待核验', body)
        self.assertNotIn('多个独立来源报了同一件事', body)
        self.assertIn('同稿转载不算独立佐证', body)


if __name__ == '__main__':
    unittest.main()
