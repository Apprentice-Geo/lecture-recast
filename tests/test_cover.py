"""Check exported dimensions and fail visibly when cover text cannot fit."""

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from scripts.render_cover import render, validate_analysis


OUTLINE = {
    "title": "软件工程的来龙去脉",
    "lecture": 5,
    "subtitle": "从软件危机到 AI 时代，\n理解工程方法的意义",
    "summary": "回顾软件工程的发展，理解需求、契约与建模工具如何帮助人们明确意图，并检查系统的行为。",
    "keywords": ["历史视角", "工程方法", "形式化工具", "面向未来"],
    "highlights": [
        {"title": "历史脉络", "description": "从软件危机到现代软件工程", "icon": "history"},
        {"title": "方法与工具", "description": "需求、设计、契约与 UML", "icon": "tools"},
        {"title": "面向未来", "description": "AI 时代的承诺与检查", "icon": "future"},
    ],
    "sections": [],
}


class CoverTests(unittest.TestCase):
    def test_render_supported_section_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for count in (4, 7):
                with self.subTest(sections=count):
                    data = copy.deepcopy(OUTLINE)
                    data["sections"] = [
                        {"title": "需求、规约与契约", "summary": "明确双方的责任，用可以检查的承诺连接意图与实现。", "points": ["前置与后置条件", "约束与检查"]}
                        for _ in range(count)
                    ]
                    source = folder / "analysis.json"
                    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    output = folder / f"cover-{count}.png"
                    render(source, output)
                    png = output.read_bytes()
                    self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
                    self.assertEqual(struct.unpack(">II", png[16:24]), (1600, 1200))

    def test_overflow_is_rejected_before_export(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            data = copy.deepcopy(OUTLINE)
            data["sections"] = [{"title": "需求", "summary": "意图与实现", "points": ["约束"]} for _ in range(4)]
            data["summary"] = "过长的封面文案需要被明确拒绝。" * 50
            source = folder / "analysis.json"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            output = folder / "cover.png"
            with self.assertRaisesRegex(ValueError, "溢出"):
                render(source, output)
            self.assertFalse(output.exists())

    def test_incomplete_outline_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "sections"):
            validate_analysis(copy.deepcopy(OUTLINE))


if __name__ == "__main__":
    unittest.main()
