"""Download a GSE lecture and convert its article body without rewriting it."""

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, NavigableString
from markdownify import MarkdownConverter

ROOT = Path(__file__).resolve().parents[1]
LICENSE_URL = "https://creativecommons.org/licenses/by-nc/4.0/"
COURSE_URL = "https://jyywiki.cn/GSE/2026/"


def safe_name(value):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value).strip(" .")
    if not name or name in {".", ".."}:
        raise ValueError("文章名称为空或无法用于文件名")
    return name


def reading_minutes(text):
    # Chinese characters plus Latin words, at 400 units per minute.
    count = len(re.findall(r"[\u3400-\u9fff]|[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", text))
    return max(1, math.ceil(count / 400)), count


def markdown_destination(path):
    return f"<{path}>" if re.search(r"[\s()]", path) else path


class LectureConverter(MarkdownConverter):
    def convert_img(self, el, text, parent_tags):
        # Images inside spans/links remain images rather than becoming alt text.
        return super().convert_img(el, text, parent_tags - {"_inline"})

    def convert_pre(self, el, text, parent_tags):
        code = el.find("code")
        value = (code or el).get_text().rstrip("\n")
        classes = (code or el).get("class", [])
        language = next((c[9:] for c in classes if c.startswith("language-")), "")
        longest = max((len(m[0]) for m in re.finditer(r"`+", value)), default=0)
        fence = "`" * max(3, longest + 1)
        return f"\n\n{fence}{language}\n{value}\n{fence}\n\n"


def article_body(html):
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".wiki")
    if body is None or body.find("h1") is None:
        raise ValueError("未找到带标题的 .wiki 正文；请人工检查原始 HTML，避免转换导航页")
    for tag in body.select("script:not([type^='math/tex']), style, nav"):
        tag.decompose()
    return body


def course_title(html, article_url):
    for link in article_body(html).find_all("a", href=True):
        if urljoin(COURSE_URL, link["href"]) == article_url:
            title = link.get_text(strip=True)
            if title:
                return title
    raise ValueError(f"课程目录中未找到讲义标题：{article_url}")


def protect_math(body):
    """Restore TeX once, dropping KaTeX's duplicated visual/accessibility trees."""
    replacements = {}

    def replace(node, tex, display):
        token = f"LECTUREMATHTOKEN{len(replacements)}END"
        replacements[token] = f"\n\n$$\n{tex.strip()}\n$$\n\n" if display else f"${tex.strip()}$"
        node.replace_with(NavigableString(token))

    for node in list(body.select(".katex-display, .katex, script[type^='math/tex'], .math")):
        if node.parent is None or node.find_parent("pre") or node.find_parent("code"):
            continue
        annotation = node.select_one('annotation[encoding="application/x-tex"]')
        if annotation:
            tex = annotation.get_text()
        elif node.name == "script" or "math" in node.get("class", []):
            tex = node.get_text()
        else:
            # A nested KaTeX node can have been detached with its outer wrapper.
            if node.find_parent(class_="katex-display"):
                continue
            raise ValueError("公式缺少 TeX annotation，无法无损转换")
        display = "katex-display" in node.get("class", []) or "display" in node.get("class", []) or "mode=display" in node.get("type", "")
        tex = re.sub(r"^\\[\[(]|\\[\])]$", "", tex.strip())
        replace(node, tex, display)

    # Some pages retain MathJax delimiters as plain text instead of rendered DOM.
    for node in list(body.find_all(string=True)):
        if node.find_parent(["pre", "code"]):
            continue
        value = str(node)
        pattern = r"\\\((.*?)\\\)|\\\[(.*?)\\\]|\$\$(.*?)\$\$|(?<![\\$])\$(?!\$)([^\n$]+?)(?<!\\)\$(?!\$)"
        def stash(match):
            tex = next(g for g in match.groups() if g is not None)
            display = match.group(2) is not None or match.group(3) is not None
            token = f"LECTUREMATHTOKEN{len(replacements)}END"
            replacements[token] = f"\n\n$$\n{tex.strip()}\n$$\n\n" if display else f"${tex.strip()}$"
            return token
        node.replace_with(NavigableString(re.sub(pattern, stash, value, flags=re.S)))
    return replacements


def convert_article(html, url, article_name, download_image):
    body = article_body(html)
    title = body.h1.get_text(strip=True)
    stats = {tag: len(body.find_all(tag)) for tag in ("h1", "h2", "p", "pre", "img", "table")}
    plain_text = body.get_text(" ", strip=True)
    formulas = protect_math(body)
    images = []
    downloaded = {}
    for img in body.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            raise ValueError("正文图片缺少 src/data-src")
        image_url = urljoin(url, src)
        if urlsplit(image_url).scheme not in {"http", "https"}:
            raise ValueError(f"暂不支持该图片地址，请人工检查：{image_url[:100]}")
        if image_url not in downloaded:
            original = safe_name(unquote(Path(urlsplit(image_url).path).name) or "image")
            stem, ext = Path(original).stem, Path(original).suffix
            filename = f"{stem}-{hashlib.sha256(image_url.encode()).hexdigest()[:10]}{ext}"
            download_image(image_url, filename)
            downloaded[image_url] = filename
            images.append({"url": image_url, "file": f"Assets/{article_name}/{filename}"})
        img["src"] = markdown_destination(f"../Assets/{article_name}/{downloaded[image_url]}")
    for link in body.find_all("a", href=True):
        if not link["href"].startswith("#"):
            link["href"] = urljoin(url, link["href"])
    result = LectureConverter(heading_style="ATX", bullets="-", wrap=False,
                              keep_inline_images_in=["a", "p", "td", "th"]).convert(str(body))
    for token, formula in formulas.items():
        result = result.replace(token, formula)
    return result.strip() + "\n", title, plain_text, images, stats


def prepare_article(client, raw, url, lecture, title, title_url, work, root=ROOT):
    """Convert and download everything before touching existing article files."""
    name = safe_name(title)
    downloads = {}

    def download(image_url, filename):
        response = client.get(image_url)
        response.raise_for_status()
        downloads[f"Assets/{name}/{filename}"] = response.content

    markdown, source_title, text, images, stats = convert_article(
        raw.decode("utf-8-sig"), url, name, download)
    minutes, units = reading_minutes(text)
    metadata = {
        "title": title, "source_title": source_title, "title_url": title_url,
        "url": url, "author": "蒋炎岩（Yanyan Jiang）",
        "license": {"name": "CC BY-NC 4.0", "url": LICENSE_URL},
        "article_name": name, "lecture": lecture,
        "source_file": (work / "source.md").relative_to(root).as_posix(),
        "publish_file": f"articles/{name}.md", "assets_dir": f"Assets/{name}",
        "reading_minutes": minutes, "reading_units": units,
        "reading_method": "中文逐字及英文单词计数，按每分钟 400 单位估算，不含 Agent 导读",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "images": images, "body_counts": stats,
    }
    return raw, markdown, metadata, downloads


def save_article(prepared, work, root=ROOT):
    raw, markdown, metadata, downloads = prepared
    work.mkdir(parents=True, exist_ok=True)
    for relative, content in downloads.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (work / "source.html").write_bytes(raw)
    (work / "source.md").write_text(markdown, encoding="utf-8")
    (work / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lecture", type=int, default=5)
    parser.add_argument("--url", help="默认使用 GSE/2026/lect<讲次>.md")
    parser.add_argument("--html", type=Path, help="从本地原始 HTML 重新转换（图片仍按需联网）")
    args = parser.parse_args()
    if args.lecture < 1:
        parser.error("lecture 必须是正整数")
    url = args.url or f"https://jyywiki.cn/GSE/2026/lect{args.lecture}.md"
    work = ROOT / "work" / f"lect{args.lecture:02}"
    with httpx.Client(follow_redirects=True, timeout=40,
                      headers={"User-Agent": "lecture-recast/0.1 (personal article preparation)"}) as client:
        if args.html:
            raw = args.html.read_bytes()
        else:
            response = client.get(url)
            response.raise_for_status()
            raw = response.content
            url = str(response.url)
        html = raw.decode("utf-8-sig")
        source_title = article_body(html).h1.get_text(strip=True)
        title_url = url
        title = source_title
        if not args.url:
            response = client.get(COURSE_URL)
            response.raise_for_status()
            title = course_title(response.text, url)
            title_url = COURSE_URL
        prepared = prepare_article(client, raw, url, args.lecture, title, title_url, work)
    save_article(prepared, work)
    metadata = prepared[2]
    print(f"已转换第 {args.lecture} 讲：{title}；约 {metadata['reading_minutes']} 分钟；{len(metadata['images'])} 张原文图片")


if __name__ == "__main__":
    main()
