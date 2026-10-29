# 工作线交接约定

## 目录

- `articles/<文章名称>.md`：整理后的 Markdown。所有文章放在同一个目录。
- `Assets/<文章名称>/`：该文章的图片，包括 `cover.png`。文章引用为 `../Assets/<文章名称>/<图片文件名>`。
- `work/lect05/source.html`：抓取响应的原始 HTML。
- `work/lect05/source.md`：转换后的完整正文，图片路径按最终发布目录计算。
- `work/lect05/metadata.json`：抓取与发布元数据。
- `work/lect05/analysis.json`：Agent 阅读 source.md 后手工提炼的内容，也是导读和封面的共同数据源。
- `scripts/`：抓取、发布组装、封面渲染脚本。
- `templates/`：封面 HTML/CSS。
- `templates/assets/`：模板共用素材，包含 `decoration.png`。

`work/<讲次>/` 保留中间结果供人工检查；文章目录仅存放待发布的 Markdown。

## analysis.json

UTF-8 JSON；第一版仅实现纵向索引布局。示意如下，文案必须来自当前正文，不能照抄参考图：

```json
{
  "title": "软件工程的来龙去脉",
  "lecture": 5,
  "subtitle": "两行以内的文章副标题",
  "summary": "文章导读摘要",
  "keywords": ["历史视角", "工程方法", "形式化工具", "面向未来"],
  "highlights": [
    {"title": "历史脉络", "description": "简短说明", "icon": "history"},
    {"title": "方法与工具", "description": "简短说明", "icon": "tools"},
    {"title": "面向未来", "description": "简短说明", "icon": "future"}
  ],
  "sections": [
    {"title": "脉络标题", "summary": "一到两句摘要", "points": ["关键点", "关键点"]}
  ]
}
```

`sections` 允许 4–7 项；`highlights` 为三项；`keywords` 为 2–4 项。模板检测文字溢出并报错，不静默裁剪。

## 元数据与命令

抓取脚本生成 metadata.json，至少包含 `title`、`url`、`author`、`license`、`article_name`、`source_file`、`publish_file`、`assets_dir`、`reading_minutes`、`fetched_at`、`images`。文件路径相对于仓库根目录。

封面命令约定：

```powershell
uv run scripts/render_cover.py --analysis work/lect05/analysis.json --output Assets/软件工程的来龙去脉/cover.png
```

## 内容和验收

- 完整保留正文，只做格式转换，不改写、删减或重排正文。
- 组装后的文章使用 [article-format-correction](<https://github.com/Apprentice-Geo/skills/tree/main/article-format-correction>) skill 校正格式，原始 HTML 与 source.md 保留转换结果；重新组装后需再次校正。
- 转载说明、Agent 导读、阅读时间与原文明确分开；来源和授权链接保留。
- 行内公式用 `$...$`，行间公式用 `$$...$$`；代码内的数学标记保持原样。
- 封面为 1600×1200，使用已复刻的纵向索引模板，文案基于正文，左下装饰直接复用 `templates/assets/decoration.png`。
- 视觉采用冷白、灰、深蓝与青蓝配色，严格栅格、清晰层级和方角；优先以对齐、留白和编号表达关系。左侧布局及公共规范统一，右侧布局按文章适配。
- 知乎中的图片由用户手动上传，不实现平台上传功能。
- 主 Agent 负责抓取转换、分析、发布组装和集成验证；Subagent 负责模板与渲染脚本，不改抓取相关文件。
