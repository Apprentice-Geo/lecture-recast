"""Check exported dimensions and fail visibly when cover text cannot fit."""

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from scripts.render_cover import build_html, render, validate_analysis


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
    def test_preview_loads_bundled_font_offline(self):
        with tempfile.TemporaryDirectory(prefix="cover preview ") as folder:
            folder = Path(folder)
            data = self.sample("grouped")
            source = folder / "analysis.json"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            preview = folder / "cover.html"
            render(source, folder / "cover.png", preview)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = browser.new_page()
                    page.context.set_offline(True)
                    page.goto(preview.as_uri())
                    faces = page.evaluate("""async () => {
                        await document.fonts.ready;
                        return (await document.fonts.load('400 22px "Source Han Sans SC"', '软件工程 0123')).map(font => font.status);
                    }""")
                    self.assertEqual(faces, ["loaded"])
                finally:
                    browser.close()

    def test_invalid_font_is_rejected_before_export(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            data = self.sample("grouped")
            source = folder / "analysis.json"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            font = folder / "broken.woff2"
            font.write_bytes(b"invalid font")
            output = folder / "cover.png"
            with patch("scripts.render_cover.FONT_PATH", font):
                with self.assertRaisesRegex(ValueError, "思源黑体加载失败"):
                    render(source, output)
            self.assertFalse(output.exists())

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

    def sample(self, layout, count=3, dimensions=3, items=2):
        data = copy.deepcopy(OUTLINE)
        data.pop("sections")
        data.update(layout=layout, structure_title="共同规则与变化空间", structure_summary="比较共同维度，理解对象归属。")
        if layout == "matrix":
            data["matrix"] = {
                "columns": ["对象"] + [f"维度 {i}" for i in range(1, dimensions)],
                "rows": [
                    {"title": f"案例 {i}", "summary": f"主题说明 {i}", "cells": [f"案例 {i} 的维度 {j} 内容" for j in range(1, dimensions)]}
                    for i in range(1, count + 1)
                ],
            }
        else:
            data["groups"] = [
                {"title": f"分类 {i}", "summary": f"分类说明 {i}", "items": [
                    {"title": f"概念 {i}-{j}", "summary": f"概念解释 {i}-{j}。"} for j in range(1, items + 1)
                ]} for i in range(1, count + 1)
            ]
        return data

    def test_new_layouts_render_without_sections_or_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for layout, count, dimensions, items in (("matrix", 3, 3, 2), ("matrix", 6, 4, 2), ("grouped", 2, 3, 2), ("grouped", 4, 3, 4)):
                with self.subTest(layout=layout, count=count):
                    data = self.sample(layout, count, dimensions, items)
                    source = folder / "analysis.json"
                    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    output, preview = folder / "cover.png", folder / "cover.html"
                    render(source, output, preview)
                    self.assertEqual(struct.unpack(">II", output.read_bytes()[16:24]), (1600, 1200))
                    document = preview.read_text(encoding="utf-8")
                    self.assertNotIn('class="number"', document)
                    if layout == "matrix":
                        for column in data["matrix"]["columns"]:
                            self.assertIn(column, document)
                        for row in data["matrix"]["rows"]:
                            self.assertEqual(document.count(row["title"] + "</h3>"), 1)
                            for cell in row["cells"]:
                                self.assertEqual(document.count(cell), 1)
                    else:
                        for group in data["groups"]:
                            self.assertEqual(document.count(group["title"] + "</h3>"), 1)
                            for item in group["items"]:
                                self.assertEqual(document.count(item["title"] + "</h4>"), 1)
                                self.assertEqual(document.count(item["summary"]), 1)

    def test_matrix_requires_consistent_named_dimensions(self):
        for cells in (["少一个维度"], ["说明", ""], ["说明", 1]):
            with self.subTest(cells=cells):
                data = self.sample("matrix")
                data["matrix"]["rows"][0]["cells"] = cells
                with self.assertRaisesRegex(ValueError, "cells"):
                    validate_analysis(data)
        data = self.sample("matrix")
        data["matrix"]["columns"] = ["对象", ""]
        with self.assertRaisesRegex(ValueError, "columns"):
            validate_analysis(data)

    def test_groups_require_actual_children_instead_of_section_references(self):
        data = self.sample("grouped")
        data["groups"][0].pop("items")
        data["groups"][0]["sections"] = [1, 2]
        with self.assertRaisesRegex(ValueError, "items"):
            validate_analysis(data)
        data = self.sample("grouped")
        data["groups"][0]["items"][0]["summary"] = ""
        with self.assertRaisesRegex(ValueError, "summary"):
            validate_analysis(data)

    def test_layout_override_requires_matching_data(self):
        data = self.sample("matrix")
        data["layout"] = "index"
        validate_analysis(data, "matrix")
        with self.assertRaisesRegex(ValueError, "sections"):
            validate_analysis(data)
        with self.assertRaisesRegex(ValueError, "layout"):
            validate_analysis(data, "unknown")
        document = build_html(data, "matrix")
        self.assertIn('data-layout="matrix"', document)

    def test_new_layouts_reject_overflow_in_right_region(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for layout in ("matrix", "grouped"):
                with self.subTest(layout=layout):
                    data = self.sample(layout)
                    text = "这段文字无法放入信息区域。" * 100
                    if layout == "matrix":
                        data["matrix"]["rows"][0]["cells"][0] = text
                    else:
                        data["groups"][0]["items"][0]["summary"] = text
                    source = folder / "analysis.json"
                    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    output = folder / f"{layout}.png"
                    with self.assertRaisesRegex(ValueError, "溢出"):
                        render(source, output)
                    self.assertFalse(output.exists())

    def test_new_layout_text_is_escaped(self):
        for layout in ("matrix", "grouped"):
            with self.subTest(layout=layout):
                data = self.sample(layout)
                text = '<script>alert("x")</script>'
                if layout == "matrix":
                    data["matrix"]["rows"][0]["cells"][0] = text
                else:
                    data["groups"][0]["items"][0]["summary"] = text
                document = build_html(validate_analysis(data))
                self.assertNotIn(text, document)
                self.assertIn('&lt;script&gt;', document)


if __name__ == "__main__":
    unittest.main()
