import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_updates import check_updates, discover_articles, main, print_summary
from fetch_article import COURSE_URL, prepare_article, save_article


def page(body):
    return f'<div class="wiki"><h1>标题</h1>{body}</div>'


class UpdateTests(unittest.TestCase):
    def client(self, pages):
        def respond(request):
            value = pages.get(str(request.url), (404, "missing"))
            status, content = value if isinstance(value, tuple) else (200, value)
            return httpx.Response(status, content=content.encode() if isinstance(content, str) else content)
        return httpx.Client(transport=httpx.MockTransport(respond))

    def run_check(self, pages, root):
        with self.client(pages) as client, contextlib.redirect_stdout(io.StringIO()):
            return check_updates(client, root)

    def save_source(self, pages, root, title="一"):
        url = COURSE_URL + "lect1.md"
        work = root / "work/lect01"
        with self.client(pages) as client:
            prepared = prepare_article(client, pages[url].encode(), url, 1,
                                       title, COURSE_URL, work, root)
        save_article(prepared, work, root)

    def snapshot(self, root):
        return {path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
                for path in root.rglob("*")}

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
            self.assertEqual(first["articles"][0]["processing"], "pending_agent")
            self.assertEqual(list(root.iterdir()), [])
            self.save_source(pages, root, "文章")
            work = root / "work/lect01"
            (work / "analysis.json").write_text('{"summary":"人工分析"}', encoding="utf-8")
            publish = root / "articles/文章.md"
            publish.parent.mkdir()
            publish.write_text("已校正文章", encoding="utf-8")
            before = self.snapshot(root)
            pages[url] = '<nav>站点变化</nav>' + pages[url]
            second = self.run_check(pages, root)["articles"][0]
            self.assertEqual(second["status"], "unchanged")
            self.assertEqual(second["processing"], "none")
            pages["https://jyywiki.cn/image.png"] = b"image v2"
            changed = self.run_check(pages, root)["articles"][0]
            self.assertEqual(changed["status"], "updated")
            self.assertIn("图片变化或缺失", changed["reasons"])
            self.assertEqual(self.snapshot(root), before)
            pages[url] = page('<p>新正文</p>')
            changed = self.run_check(pages, root)["articles"][0]
            self.assertIn("正文变化或缺失", changed["reasons"])
            pages[COURSE_URL] = page('<a href="lect1.md">新标题 (1)</a>')
            changed = self.run_check(pages, root)["articles"][0]
            self.assertIn("目录标题变化", changed["reasons"])
            self.assertEqual(self.snapshot(root), before)
            self.assertEqual(publish.read_text(encoding="utf-8"), "已校正文章")
            self.assertEqual(json.loads((work / "analysis.json").read_text(encoding="utf-8"))["summary"], "人工分析")

    def test_cli_always_writes_nothing_and_reports_new(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pages = {COURSE_URL: page('<a href="lect1.md">一</a>'),
                     COURSE_URL + "lect1.md": page('<p>原文</p>')}
            client = self.client(pages)
            with patch("check_updates.ROOT", root), \
                 patch("check_updates.httpx.Client", return_value=client), \
                 patch.object(sys, "argv", ["check_updates.py"]), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(), 0)
            self.assertIn("新增 1", output.getvalue())
            self.assertIn("待 Agent 处理 1 篇", output.getvalue())
            self.assertIn(COURSE_URL + "lect1.md", output.getvalue())
            self.assertEqual(list(root.iterdir()), [])

    def test_legacy_pending_and_report_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pages = {COURSE_URL: page('<a href="lect1.md">一</a>'),
                     COURSE_URL + "lect1.md": page('<p>原文</p>')}
            self.save_source(pages, root)
            (root / "work/lect01/update_pending.json").write_text('{"reasons":["旧待办"]}', encoding="utf-8")
            (root / "work/update-report.json").write_text('{"checked_at":"旧报告"}', encoding="utf-8")
            before = self.snapshot(root)
            for _ in range(2):
                report = self.run_check(pages, root)
                self.assertTrue(report["check_only"])
                self.assertEqual(report["articles"][0]["status"], "unchanged")
                self.assertEqual(report["articles"][0]["processing"], "pending_agent")
                self.assertEqual(self.snapshot(root), before)

    def test_custom_import_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pages = {COURSE_URL: page('<a href="lect1.md">一</a>'),
                     COURSE_URL + "lect1.md": page('<p>正文</p>')}
            self.save_source(pages, root)
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
            self.save_source(pages, root)
            before = self.snapshot(root)
            pages[COURSE_URL] = page('<a href="lect1.md">一</a><a href="lect3.md">三</a>')
            pages[COURSE_URL + "lect1.md"] = page('<p>新正文</p><img src="/missing.png">')
            pages[COURSE_URL + "lect3.md"] = page('<p>三正文</p>')
            report = self.run_check(pages, root)
            self.assertEqual([item["status"] for item in report["articles"]], ["failed", "new"])
            self.assertEqual(self.snapshot(root), before)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(print_summary(report), 1)
            self.assertIn("失败 1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
