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


if __name__ == '__main__':
    unittest.main()
