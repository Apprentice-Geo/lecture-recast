"""Assemble an attributed article from source.md and Agent-authored analysis.json."""

import argparse
import json
from pathlib import Path

from fetch_article import ROOT, markdown_destination


def navigation_items(analysis):
    layout = analysis.get("layout", "index")
    if layout == "index":
        return analysis["sections"]
    if layout == "matrix":
        matrix = analysis["matrix"]
        return [
            {"title": row["title"], "summary": "；".join(column + "：" + cell.replace("\n", "，") for column, cell in zip(matrix["columns"][1:], row["cells"]))}
            for row in matrix["rows"]
        ]
    if layout == "grouped":
        return [
            {"title": group["title"], "summary": group["summary"] + "；" + "；".join(f'{item["title"]}：{item["summary"]}' for item in group["items"])}
            for group in analysis["groups"]
        ]
    raise ValueError(f"未知的封面布局：{layout}")


def build_publish(work):
    metadata = json.loads((work / "metadata.json").read_text(encoding="utf-8"))
    analysis = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
    if analysis["title"] != metadata["title"] or analysis["lecture"] != metadata["lecture"]:
        raise ValueError("analysis.json 与原文的标题或讲次不一致")
    source = (ROOT / metadata["source_file"]).read_text(encoding="utf-8")
    cover = ROOT / metadata["assets_dir"] / "cover.png"
    if not cover.is_file():
        raise ValueError("请先渲染 cover.png，再组装发布文章")
    license_info = metadata["license"]
    cover_ref = markdown_destination(f'../{metadata["assets_dir"]}/cover.png')
    lines = [
        f'# {metadata["title"]}', "",
        f'> 原文作者：{metadata["author"]}。来源：[生成式软件工程（2026）第 {metadata["lecture"]} 讲]({metadata["url"]})。',
        f'> 原站标注 [{license_info["name"]}]({license_info["url"]}) 授权。本文为非商业转载整理，仅做格式转换，正文未作改写；以下导读和封面由 Agent 整理，不属于原文。',
        "", f'![文章脉络封面]({cover_ref})', "",
        f'预计阅读原文约 **{metadata["reading_minutes"]} 分钟**（{metadata["reading_method"]}）。', "",
        "## 阅读导航（Agent 整理）", "", analysis["summary"], "",
    ]
    for index, section in enumerate(navigation_items(analysis), 1):
        lines.append(f'{index}. **{section["title"]}**：{section["summary"]}')
    lines.extend(["", "---", "", "原文如下：", "", source.rstrip(), ""])
    target = ROOT / metadata["publish_file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=ROOT / "work" / "lect05")
    args = parser.parse_args()
    print(build_publish(args.work))


if __name__ == "__main__":
    main()
