import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_updates import check_updates, discover_articles, print_summary
from fetch_article import COURSE_URL


def page(body):
    return f'<div class="wiki"><h1>标题</h1>{body}</div>'


class UpdateTests(unittest.TestCase):
    def client(self, pages):
        def respond(request):
            value = pages.get(str(request.url), (404, "missing"))
            status, content = value if isinstance(value, tuple) else (200, value)
            return httpx.Response(status, content=content.encode() if isinstance(content, str) else content)
        return httpx.Client(transport=httpx.MockTransport(respond))

    def run_check(self, pages, root, **kwargs):
        with self.client(pages) as client, contextlib.redirect_stdout(io.StringIO()):
            return check_updates(client, root, **kwargs)

    def test_discovery_uses_links_skips_labs_and_handles_gaps(self):
        entries = discover_articles(page('<a href="lect12.md">十二</a><a href="lab1.md">实验</a>'
                                          '<a href="lect2.md">二 (1)</a><a href="lect12.md">十二</a>'
                                          '<a href="https://evil.test/GSE/2026/lect3.md">其它</a>'))
        self.assertEqual([item["lecture"] for item in entries], [2, 12])
        self.assertEqual(entries[0]["title"], "二 (1)")
        with self.assertRaises(ValueError):
            discover_articles(page('<a href="lab1.md">实验</a>'))

    def test_new_unchanged_body_title_and_image_updates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            url = COURSE_URL + "lect1.md"
            pages = {COURSE_URL: page('<a href="lect1.md">文章</a>'),
                     url: page('<p>原文</p><img src="/image.png">'),
                     "https://jyywiki.cn/image.png": b"image v1"}
            first = self.run_check(pages, root)
            self.assertEqual(first["articles"][0]["status"], "new")
            work = root / "work/lect01"
            (work / "analysis.json").write_text('{"summary":"人工分析"}', encoding="utf-8")
            publish = root / "articles/文章.md"
            publish.parent.mkdir()
            publish.write_text("已校正文章", encoding="utf-8")
            old_metadata = (work / "metadata.json").read_bytes()
            pages[url] = '<nav>站点变化</nav>' + pages[url]
            second = self.run_check(pages, root)["articles"][0]
            self.assertEqual(second["status"], "unchanged")
            self.assertEqual(second["processing"], "pending_agent")
            self.assertEqual(old_metadata, (work / "metadata.json").read_bytes())
            (work / "update_pending.json").unlink()
            completed = self.run_check(pages, root)["articles"][0]
            self.assertEqual(completed["processing"], "none")
            pages["https://jyywiki.cn/image.png"] = b"image v2"
            changed = self.run_check(pages, root)["articles"][0]
            self.assertIn("图片变化或缺失", changed["reasons"])
            pages[url] = page('<p>新正文</p>')
            changed = self.run_check(pages, root)["articles"][0]
            self.assertIn("正文变化或缺失", changed["reasons"])
            pages[COURSE_URL] = page('<a href="lect1.md">新标题 (1)</a>')
            changed = self.run_check(pages, root)["articles"][0]
            self.assertIn("目录标题变化", changed["reasons"])
            self.assertEqual(publish.read_text(encoding="utf-8"), "已校正文章")
            self.assertEqual(json.loads((work / "analysis.json").read_text(encoding="utf-8"))["summary"], "人工分析")

    def test_check_only_writes_nothing_and_reports_new(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = self.run_check({COURSE_URL: page('<a href="lect1.md">一</a>'),
                                     COURSE_URL + "lect1.md": page('<p>原文</p>')}, root, check_only=True)
            self.assertEqual(report["articles"][0]["status"], "new")
            self.assertEqual(list(root.iterdir()), [])

    def test_custom_import_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pages = {COURSE_URL: page('<a href="lect1.md">一</a>'),
                     COURSE_URL + "lect1.md": page('<p>正文</p>')}
            self.run_check(pages, root)
            metadata = root / "work/lect01/metadata.json"
            saved = json.loads(metadata.read_text(encoding="utf-8"))
            saved["url"] = "https://example.com/custom"
            metadata.write_text(json.dumps(saved), encoding="utf-8")
            before = metadata.read_bytes()
            report = self.run_check(pages, root)
            self.assertEqual(report["articles"][0]["status"], "failed")
            self.assertEqual(metadata.read_bytes(), before)

    def test_failure_keeps_previous_source_and_continues(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pages = {COURSE_URL: page('<a href="lect1.md">一</a>'), COURSE_URL + "lect1.md": page('<p>旧正文</p>')}
            self.run_check(pages, root)
            source = root / "work/lect01/source.md"
            old = source.read_bytes()
            pages[COURSE_URL] = page('<a href="lect1.md">一</a><a href="lect3.md">三</a>')
            pages[COURSE_URL + "lect1.md"] = page('<p>新正文</p><img src="/missing.png">')
            pages[COURSE_URL + "lect3.md"] = page('<p>三正文</p>')
            report = self.run_check(pages, root)
            self.assertEqual([item["status"] for item in report["articles"]], ["failed", "new"])
            self.assertEqual(source.read_bytes(), old)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(print_summary(report), 1)
            self.assertIn("失败 1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
