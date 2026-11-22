"""All three cover structures remain usable by the article assembly workflow."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_publish

class PublishTests(unittest.TestCase):
    def test_navigation_uses_selected_structure_and_preserves_source(self):
        cases = (
            ({"sections": [{"title": "提交历史", "summary": "追踪版本变化"}]},
             "**提交历史**：追踪版本变化"),
            ({"layout": "index", "sections": [{"title": "接口契约", "summary": "约定调用条件"}]},
             "**接口契约**：约定调用条件"),
            ({"layout": "matrix", "matrix": {
                "columns": ["对象", "规则", "演化"],
                "rows": [{"title": "数据库", "cells": ["关系\n查询", "独立演化"]}],
            }}, "**数据库**：规则：关系，查询；演化：独立演化"),
            ({"layout": "grouped", "groups": [{
                "title": "共同对象", "summary": "定义协作边界",
                "items": [{"title": "会话", "summary": "记录事件"}, {"title": "代理", "summary": "推进执行"}],
            }]}, "**共同对象**：定义协作边界；会话：记录事件；代理：推进执行"),
        )
        for lecture, (structure, navigation) in enumerate(cases, 3):
            with self.subTest(layout=structure.get("layout")), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                work = root / "work"
                work.mkdir()
                analysis = {"title": "示例讲义 (1)", "lecture": lecture, "summary": "导读摘要", **structure}
                (work / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")
                source_title = "示例讲义" if lecture == 3 else analysis["title"]
                source = f'# {source_title}\n\n保留原文段落与 `code`。\n'
                (work / "source.md").write_text(source, encoding="utf-8")
                assets = root / "Assets/示例"
                assets.mkdir(parents=True)
                (assets / "cover.png").write_bytes(b"cover existence fixture")
                metadata = {
                    "title": analysis["title"], "lecture": lecture,
                    "source_file": "work/source.md", "publish_file": "articles/示例.md",
                    "assets_dir": "Assets/示例", "author": "示例作者",
                    "url": "https://example.com/article", "license": {"name": "CC BY-NC 4.0", "url": "https://example.com/license"},
                    "reading_minutes": 1, "reading_method": "测试估算",
                }
                (work / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
                with patch.object(build_publish, "ROOT", root):
                    output = build_publish.build_publish(work).read_text(encoding="utf-8")
                self.assertTrue(output.endswith(source))
                self.assertTrue(output.startswith(f'# {analysis["title"]}\n'))
                self.assertIn(f"\n1. {navigation}\n", output)


if __name__ == "__main__":
    unittest.main()
