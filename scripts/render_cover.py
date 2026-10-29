"""Render an Agent-authored article outline as a local 1600×1200 PNG."""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = ROOT / "templates" / "assets" / "fonts" / "source-han-sans" / "SourceHanSansSC-VF.otf.woff2"
LAYOUTS = ("index", "matrix", "grouped")
ICONS = {
    "history": '<path d="M4 6c5-2 8-1 12 1v22c-4-2-7-3-12-1zM28 6c-5-2-8-1-12 1v22c4-2 7-3 12-1z"/>',
    "tools": '<path d="M28 5a9 9 0 0 1-11 11L8 27a4 4 0 0 1-5-5l11-9A9 9 0 0 1 25 2l-6 6 5 5z"/>',
    "future": '<rect x="4" y="11" width="24" height="18" rx="4"/><path d="M16 11V5M2 18v6M30 18v6M11 24h10"/><circle cx="16" cy="3" r="2"/><circle cx="10" cy="18" r="1"/><circle cx="22" cy="18" r="1"/>',
}


def validate_analysis(data: object, layout: str | None = None) -> dict:
    """Reject incomplete outlines before they produce plausible blank covers."""
    if not isinstance(data, dict):
        raise ValueError("analysis.json 必须是对象")
    layout = layout or data.get("layout", "index")
    if layout not in LAYOUTS:
        raise ValueError("layout 必须是 index、matrix 或 grouped")

    def text_field(item: dict, field: str, location: str) -> None:
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"{location}.{field} 必须是非空字符串")

    for key in ("title", "subtitle", "summary"):
        text_field(data, key, "analysis")
    if type(data.get("lecture")) is not int or data["lecture"] < 1:
        raise ValueError("lecture 必须是正整数")
    for key, low, high in (("keywords", 2, 4), ("highlights", 3, 3)):
        if not isinstance(data.get(key), list) or not low <= len(data[key]) <= high:
            raise ValueError(f"{key} 必须包含 {low}–{high} 项")
    if any(not isinstance(k, str) or not k.strip() for k in data["keywords"]):
        raise ValueError("keywords 必须是非空字符串列表")
    for i, item in enumerate(data["highlights"]):
        if not isinstance(item, dict):
            raise ValueError(f"highlights[{i}] 必须是对象")
        for key in ("title", "description"):
            text_field(item, key, f"highlights[{i}]")
        if not isinstance(item.get("icon"), str) or item["icon"] not in ICONS:
            raise ValueError(f"highlights[{i}].icon 必须是 history、tools 或 future")
    def objects(value, name, low, high):
        if not isinstance(value, list) or not low <= len(value) <= high:
            raise ValueError(f"{name} 必须包含 {low}–{high} 项")
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                raise ValueError(f"{name}[{i}] 必须是对象")
            for key in ("title", "summary"):
                text_field(item, key, f"{name}[{i}]")

    if layout == "index":
        objects(data.get("sections"), "sections", 4, 7)
        for i, item in enumerate(data["sections"]):
            points = item.get("points")
            if not isinstance(points, list) or not points or any(not isinstance(p, str) or not p.strip() for p in points):
                raise ValueError(f"sections[{i}].points 必须是非空字符串列表")
    else:
        for key in ("structure_title", "structure_summary"):
            text_field(data, key, "analysis")
    if layout == "matrix":
        matrix = data.get("matrix")
        if not isinstance(matrix, dict):
            raise ValueError("matrix 必须包含 columns 和 rows")
        columns = matrix.get("columns")
        if not isinstance(columns, list) or not 3 <= len(columns) <= 4 or any(not isinstance(c, str) or not c.strip() for c in columns):
            raise ValueError("matrix.columns 必须包含 3–4 个非空列名（首列为比较对象）")
        objects(matrix.get("rows"), "matrix.rows", 3, 6)
        for i, row in enumerate(matrix["rows"]):
            cells = row.get("cells")
            if not isinstance(cells, list) or len(cells) != len(columns) - 1 or any(not isinstance(c, str) or not c.strip() for c in cells):
                raise ValueError(f"matrix.rows[{i}].cells 必须与比较维度列数一致，且为非空字符串")
    elif layout == "grouped":
        groups = data.get("groups")
        objects(groups, "groups", 2, 4)
        for i, group in enumerate(groups):
            objects(group.get("items"), f"groups[{i}].items", 2, 4)
    return data


def build_html(data: dict, layout: str | None = None, *, font_url: str | None = None) -> str:
    layout = layout or data.get("layout", "index")
    escape = html.escape
    template = (ROOT / "templates" / "cover.html").read_text(encoding="utf-8")
    decoration = base64.b64encode((ROOT / "templates" / "assets" / "decoration.png").read_bytes()).decode("ascii")
    highlights = "".join(
        '<div class="highlight" data-check><div class="icon"><svg viewBox="0 0 32 32" aria-hidden="true">'
        + ICONS[item["icon"]]
        + '</svg></div><div><div class="highlight-title" data-check>'
        + escape(item["title"])
        + '</div><div class="highlight-description" data-check>'
        + escape(item["description"])
        + '</div></div></div>'
        for item in data["highlights"]
    )

    def section_html(i, item):
        return (
            f'<section class="section" data-check data-boundary><div class="number">{i:02d}</div>'
            f'<div class="section-text"><h2 class="section-title" data-check>{escape(item["title"])}</h2>'
            f'<p class="section-summary" data-check>{escape(item["summary"])}</p></div>'
            '<ul class="points" data-check>'
            + "".join(f'<li data-check>{escape(p)}</li>' for p in item["points"])
            + '</ul></section>'
        )

    structure_header = (
        '<header class="structure-header" data-check data-boundary>'
        f'<h2 data-check>{escape(data.get("structure_title", ""))}</h2>'
        f'<p data-check>{escape(data.get("structure_summary", ""))}</p></header>'
    )
    count, columns = 0, 0
    if layout == "index":
        count = len(data["sections"])
        content = "".join(section_html(i, item) for i, item in enumerate(data["sections"], 1))
    elif layout == "matrix":
        matrix = data["matrix"]
        count, columns = len(matrix["rows"]), len(matrix["columns"])
        content = structure_header + '<div class="comparison" role="table" data-check data-boundary>'
        content += '<div class="comparison-head" role="row" data-check data-boundary>'
        content += "".join(f'<div role="columnheader" data-check>{escape(c)}</div>' for c in matrix["columns"])
        content += '</div>'
        for row in matrix["rows"]:
            content += (
                '<div class="comparison-row" role="row" data-check data-boundary>'
                f'<div class="comparison-label" role="rowheader" data-check><h3 data-check>{escape(row["title"])}</h3>'
                f'<p data-check>{escape(row["summary"])}</p></div>'
                + "".join(f'<div class="comparison-cell" role="cell" data-check>{escape(c)}</div>' for c in row["cells"])
                + '</div>'
            )
        content += '</div>'
    else:
        count = len(data["groups"])
        content = structure_header + '<div class="clusters" data-check data-boundary>'
        for group in data["groups"]:
            content += (
                f'<section class="cluster" style="--item-count:{len(group["items"])}" data-check data-boundary>'
                f'<header class="cluster-heading" data-check data-boundary><h3 data-check>{escape(group["title"])}</h3>'
                f'<p data-check>{escape(group["summary"])}</p></header>'
                '<div class="cluster-items" data-check data-boundary>'
                + "".join(
                    f'<div class="cluster-item" data-check data-boundary><h4 data-check>{escape(item["title"])}</h4>'
                    f'<p data-check>{escape(item["summary"])}</p></div>' for item in group["items"]
                )
                + '</div></section>'
            )
        content += '</div>'
    values = {
        "TITLE": escape(data["title"]),
        "LECTURE": f'{data["lecture"]:02d}',
        "SUBTITLE": escape(data["subtitle"]),
        "SUMMARY": escape(data["summary"]),
        "KEYWORDS": "".join(f"<span>{escape(k)}</span>" for k in data["keywords"]),
        "HIGHLIGHTS": highlights,
        "COUNT": str(count),
        "LAYOUT": layout,
        "COLUMNS": str(columns),
        "CONTENT": content,
        "DECORATION": "data:image/png;base64," + decoration,
        "FONT": escape(font_url) if font_url else "data:font/woff2;base64," + base64.b64encode(FONT_PATH.read_bytes()).decode("ascii"),
    }
    return re.sub(r"%%([A-Z]+)%%", lambda match: values[match[1]], template)


CHECK_OVERFLOW = """() => {
  const errors = [];
  const box = document.querySelector('.cover').getBoundingClientRect();
  for (const el of document.querySelectorAll('[data-check]')) {
    const r = el.getBoundingClientRect();
    const label = `${el.className || el.tagName}: ${el.textContent.trim().slice(0, 45)}`;
    if (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2)
      errors.push(`文字超出容器 ${label}`);
    if (r.left < box.left - 1 || r.top < box.top - 1 || r.right > box.right + 1 || r.bottom > box.bottom + 1)
      errors.push(`超出画布 ${label}`);
    let boundary = el.parentElement.closest('[data-boundary]');
    while (boundary) {
      const s = boundary.getBoundingClientRect();
      if (r.bottom > s.bottom + 1 || r.right > s.right + 1 || r.left < s.left - 1 || r.top < s.top - 1)
        errors.push(`超出信息区域 ${label}`);
      boundary = boundary.parentElement.closest('[data-boundary]');
    }
  }
  const intro = document.querySelector('.intro-copy').getBoundingClientRect();
  const footer = document.querySelector('.footer').getBoundingClientRect();
  if (intro.bottom > footer.top - 20) errors.push('左侧文案与页脚重叠，请精简封面摘要');
  return [...new Set(errors)];
}"""


def render(analysis: Path, output: Path, preview: Path | None = None, layout: str | None = None) -> None:
    data = validate_analysis(json.loads(analysis.read_text(encoding="utf-8-sig")), layout)
    layout = layout or data.get("layout", "index")
    document = build_html(data, layout)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1600, "height": 1200}, device_scale_factor=1)
            page.set_content(document, wait_until="load")
            page.evaluate("document.fonts.ready")
            font_statuses = page.evaluate("() => Array.from(document.fonts, font => font.status)")
            if not font_statuses or any(status != "loaded" for status in font_statuses):
                raise ValueError("思源黑体加载失败")
            if not page.locator(".decoration").evaluate("img => img.complete && img.naturalWidth > 0"):
                raise ValueError("装饰图加载失败")
            errors = page.evaluate(CHECK_OVERFLOW)
            if errors:
                raise ValueError("封面内容溢出，请调整 analysis.json 文案：\n" + "\n".join(errors))
            output.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output), type="png", full_page=False)
        finally:
            browser.close()
    if preview:
        preview.parent.mkdir(parents=True, exist_ok=True)
        try:
            font_url = quote(Path(os.path.relpath(FONT_PATH, preview.resolve().parent)).as_posix())
        except ValueError:  # Windows cannot form a relative path across drives.
            font_url = FONT_PATH.as_uri()
        preview.write_text(build_html(data, layout, font_url=font_url), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--html", type=Path, help="可选：保存内嵌装饰图、引用仓库字体的 HTML 预览")
    parser.add_argument("--layout", choices=LAYOUTS, help="右侧布局；覆盖 analysis.json 的 layout，默认 index")
    args = parser.parse_args()
    try:
        render(args.analysis, args.output, args.html, args.layout)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"封面已生成：{args.output} (1600×1200)")


if __name__ == "__main__":
    main()
