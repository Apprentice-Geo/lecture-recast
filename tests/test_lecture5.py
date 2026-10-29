"""Verify the checked-in real lecture against its original HTML snapshot."""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_article import ROOT, article_body


class LectureFiveTests(unittest.TestCase):
    def test_complete_body_text_and_code_match_html_snapshot(self):
        body = article_body((ROOT / 'work/lect05/source.html').read_text(encoding='utf-8'))
        markdown = (ROOT / 'work/lect05/source.md').read_text(encoding='utf-8')
        plain = re.sub(r'\[([^\]]+)\]\([^\n]+?\)', r'\1', markdown)
        plain = re.sub(r'^```[^\n]*$', '', plain, flags=re.M)
        plain = re.sub(r'^#{1,6} |^- ', '', plain, flags=re.M)
        plain = plain.replace('**', '').replace('`', '')
        normalize = lambda value: re.sub(r'\s+', '', value)
        self.assertEqual(normalize(plain), normalize(body.get_text()))
        self.assertEqual(len(re.findall(r'^## ', markdown, re.M)), len(body.find_all('h2')))
        for code in body.select('pre code'):
            self.assertIn(code.get_text().rstrip('\n'), markdown)
        for link in body.select('a[href]'):
            self.assertIn(link['href'], markdown)

    def test_formatted_article_retains_body_and_images_resolve(self):
        import json
        metadata = json.loads((ROOT / 'work/lect05/metadata.json').read_text(encoding='utf-8'))
        source = (ROOT / metadata['source_file']).read_text(encoding='utf-8')
        published_path = ROOT / metadata['publish_file']
        published = published_path.read_text(encoding='utf-8')
        body = published.split('原文如下：\n\n', 1)[1]

        def normalize_format(text):
            # Allow the reviewed typography and math notation changes while
            # still comparing every paragraph, link destination and code line.
            text = re.sub(r'\]\(<([^>\n]+)>\)', r'](\1)', text)
            text = text.replace('“', '「').replace('”', '」')
            text = text.replace('Applying "Design by Contract"', 'Applying 「Design by Contract」')
            text = text.replace('《Boys’ Life》', 'Boys’ Life').replace('*Boys’ Life*', 'Boys’ Life')
            text = text.replace(r'$\text{balance} \ge 0$', '`balance >= 0`')
            text = text.replace('```eiffel\n', '```text\n')
            return [re.sub(r'\s+', '', p) for p in re.split(r'\n\s*\n', text.strip())]

        self.assertEqual(normalize_format(body), normalize_format(source))
        original = article_body((ROOT / 'work/lect05/source.html').read_text(encoding='utf-8'))
        for code in original.select('pre code'):
            self.assertIn(code.get_text().rstrip('\n'), body)
        self.assertIn('CC BY-NC 4.0', published)
        self.assertIn(metadata['url'], published)
        for target in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', published):
            self.assertTrue((published_path.parent / target.strip('<>')).is_file(), target)


if __name__ == '__main__':
    unittest.main()
