"""Detect course article changes without modifying local files."""

import argparse
from datetime import datetime, timezone
import json
import re
from urllib.parse import urljoin, urlsplit

import httpx

from fetch_article import COURSE_URL, ROOT, article_body, prepare_article


def discover_articles(html):
    """Use published lecture links, not guessed consecutive lecture numbers."""
    articles = {}
    for link in article_body(html).find_all("a", href=True):
        url = urljoin(COURSE_URL, link["href"])
        parts = urlsplit(url)
        match = re.fullmatch(r"/GSE/2026/lect([1-9][0-9]*)\.md", parts.path)
        if parts.netloc != urlsplit(COURSE_URL).netloc or not match or parts.query or parts.fragment:
            continue
        lecture = int(match[1])
        title = link.get_text(strip=True)
        if not title:
            raise ValueError(f"第 {lecture} 讲的目录标题为空")
        entry = {"lecture": lecture, "title": title, "url": url}
        if lecture in articles and articles[lecture] != entry:
            raise ValueError(f"目录中第 {lecture} 讲有冲突的链接或标题")
        articles[lecture] = entry
    if not articles:
        raise ValueError("课程目录中没有讲义链接，请检查页面结构")
    return [articles[key] for key in sorted(articles)]


def change_reasons(prepared, work, root):
    _, markdown, metadata, downloads = prepared
    previous = work / "metadata.json"
    if not previous.is_file():
        return "new", ["本地尚未抓取"]
    old = json.loads(previous.read_text(encoding="utf-8"))
    # Custom --url imports share the lecture work directory. Never replace them.
    if old["url"] != metadata["url"]:
        raise ValueError("本地元数据的 URL 与课程目录不同，保留本地文件，请人工核对")
    reasons = []
    if old["title"] != metadata["title"]:
        reasons.append("目录标题变化")
    source = work / "source.md"
    if not source.is_file() or source.read_text(encoding="utf-8") != markdown:
        reasons.append("正文变化或缺失")
    if any(not (root / path).is_file() or (root / path).read_bytes() != content
           for path, content in downloads.items()):
        reasons.append("图片变化或缺失")
    if not (work / "source.html").is_file():
        reasons.append("原始 HTML 缺失")
    return ("updated" if reasons else "unchanged"), reasons


def check_updates(client, root=ROOT):
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "course_url": COURSE_URL, "check_only": True, "articles": []}
    response = client.get(COURSE_URL)
    response.raise_for_status()
    articles = discover_articles(response.text)
    for entry in articles:
        result = dict(entry)
        work = root / "work" / f"lect{entry['lecture']:02}"
        pending = work / "update_pending.json"
        try:
            response = client.get(entry["url"])
            response.raise_for_status()
            prepared = prepare_article(client, response.content, entry["url"], entry["lecture"],
                                       entry["title"], COURSE_URL, work, root)
            status, reasons = change_reasons(prepared, work, root)
            result.update(status=status, reasons=reasons, processing="none")
            # Retain visibility of unfinished work left by older versions.
            if status != "unchanged" or pending.exists():
                result["processing"] = "pending_agent"
            label = {"new": "新增", "updated": "有更新", "unchanged": "无变化"}[status]
            action = {"none": "仅探测，未写入",
                      "pending_agent": "仅探测，未写入；待 Agent 核对并处理"}[result["processing"]]
            detail = f"（{'、'.join(reasons)}）" if reasons else ""
            print(f"[第 {entry['lecture']:02} 讲] {entry['title']}：{label}{detail}；{action}", flush=True)
        except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
            result.update(status="failed", processing="failed", error=str(exc))
            print(f"[第 {entry['lecture']:02} 讲] {entry['title']}：失败；{exc}", flush=True)
        report["articles"].append(result)
    return report


def print_summary(report):
    entries = report["articles"]
    counts = {status: sum(item["status"] == status for item in entries)
              for status in ("new", "updated", "unchanged", "failed")}
    pending = [item for item in entries if item["processing"] == "pending_agent"]
    print(f"\n检查完成：共 {len(entries)} 篇，新增 {counts['new']}，更新 {counts['updated']}，"
          f"无变化 {counts['unchanged']}，失败 {counts['failed']}；待 Agent 处理 {len(pending)} 篇。")
    for item in pending:
        print(f"  待处理：第 {item['lecture']:02} 讲（{item['title']}） {item['url']}")
    return 1 if counts["failed"] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="兼容旧命令；默认即只探测，不写文件")
    parser.parse_args()
    try:
        with httpx.Client(follow_redirects=True, timeout=40,
                          headers={"User-Agent": "lecture-recast/0.1 (update check)"}) as client:
            report = check_updates(client, root=ROOT)
        return print_summary(report)
    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        print(f"检查失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
