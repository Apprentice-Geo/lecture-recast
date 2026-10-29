"""All three cover structures remain usable by the article assembly workflow."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_publish

ROOT = Path(__file__).resolve().parents[1]


class PublishTests(unittest.TestCase):
    def test_navigation_uses_selected_structure_and_preserves_source(self):
        for lecture in (3, 5, 7, 9):
            with self.subTest(lecture=lecture), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                work = root / "work"
                work.mkdir()
                analysis = json.loads((ROOT / f"work/lect{lecture:02}/analysis.json").read_text(encoding="utf-8"))
                (work / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")
                source_title = "版本管理" if lecture == 3 else analysis["title"]
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
                if lecture in (3, 5):
                    for section in analysis["sections"]:
                        self.assertIn(section["title"], output)
                elif lecture == 7:
                    for row in analysis["matrix"]["rows"]:
                        self.assertIn(row["title"], output)
                        for cell in row["cells"]:
                            self.assertIn(cell.replace("\n", "，"), output)
                else:
                    for group in analysis["groups"]:
                        self.assertIn(group["title"], output)
                        for item in group["items"]:
                            self.assertIn(item["title"], output)


if __name__ == "__main__":
    unittest.main()
