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

UTF-8 JSON；左侧信息共用，右侧支持纵向索引、网格矩阵和分组结构。示意如下，文案必须来自当前正文：

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

`highlights` 为三项；`keywords` 为 2–4 项。模板检测文字溢出并报错，不静默裁剪。

### 右侧布局

在 JSON 中设置 `layout`，不指定时默认 `index`。`--layout` 可以覆盖选择，但数据必须满足所选结构；不自动将同一组章节改排成不同形状。每篇仅维护其采用的布局数据。

| layout | 表达关系 | 右侧数据 | 样例 |
| --- | --- | --- | --- |
| `index` | 阅读路线与论述顺序 | `sections`，4–7 项，带编号 | 第 5 讲 |
| `matrix` | 多个对象在共同维度上的对照 | `matrix.columns/rows`，3–4 列、3–6 行，无编号 | 第 7 讲 |
| `grouped` | 类别与概念的归属 | `groups/items`，2–4 组，每组 2–4 项，无编号 | 第 9 讲 |

三种布局共用左侧字段。矩阵和分组还需要 `structure_title` 与 `structure_summary`，用于概括右侧的比较问题或分类主题。两者均不使用连接线，通过行列对齐、留白、背景和字体层级表达关系。数量范围不代表任意长度的文案都能容纳，溢出时报错。

对照矩阵的首列为比较对象，其余列是共同维度；每行包含对象标题、简短说明和对应单元格。`cells` 数量必须等于列数减一，内容为非空字符串，可用换行分隔短句：

```json
{
  "layout": "matrix",
  "structure_title": "架构固定什么，又开放什么",
  "structure_summary": "用共同维度观察不同架构。",
  "matrix": {
    "columns": ["架构案例", "稳定的约定", "留下的变化空间"],
    "rows": [
      {"title": "UNIX", "summary": "工具与组合", "cells": ["文本流与统一接口", "工具组合与新用途"]},
      {"title": "关系数据库", "summary": "逻辑与物理", "cells": ["关系与查询规则", "查询和底层实现独立演化"]},
      {"title": "Internet", "summary": "协议与分层", "cells": ["共同的通信协议", "应用与网络持续演化"]}
    ]
  }
}
```

分组结构直接组织类别及其子项，不引用索引章节的编号。组标题说明分类，组内标题和摘要解释具体概念；第一版仅支持两级结构：

```json
{
  "layout": "grouped",
  "structure_title": "围绕共同接口组织一个 Harness",
  "structure_summary": "从领域对象到扩展方向理解系统。",
  "groups": [
    {
      "title": "共同对象", "summary": "插件共同理解的概念",
      "items": [
        {"title": "Session", "summary": "保存事件，并通过投影解释事实。"},
        {"title": "Agent", "summary": "接收输入并推动执行。"}
      ]
    },
    {
      "title": "应用扩展", "summary": "复用基础能力形成新用途",
      "items": [
        {"title": "已有 App 增强", "summary": "在明确的对象边界内协作编辑。"},
        {"title": "GenUI", "summary": "让界面交互回到同一会话。"}
      ]
    }
  ]
}
```

以上片段需与公共左侧字段组成完整 analysis.json；矩阵和分组不需要 `sections`。导读组装直接使用所选结构的行或分类，保持分析数据为单一来源。原有索引数据格式保持可用。实际样例见 `work/lect05/analysis.json`、`work/lect07/analysis.json` 和 `work/lect09/analysis.json`。

## 元数据与命令

抓取脚本生成 metadata.json，至少包含 `title`、`url`、`author`、`license`、`article_name`、`source_file`、`publish_file`、`assets_dir`、`reading_minutes`、`fetched_at`、`images`。文件路径相对于仓库根目录。

默认课程抓取以课程目录中的完整标题为准，保留 `(1)`、`(2)` 等括注；文章主标题、文件名、资源目录和 `analysis.title` 使用该标题。`source_title` 记录正文原始标题，`title_url` 记录发布标题的来源。目录与正文标题不一致时，`source.html`、`source.md` 及发布文章的原文部分保留正文标题，不自行补写。使用 `--url` 抓取自定义页面时，标题取该页面正文的 h1。

封面命令约定：

```powershell
uv run scripts/render_cover.py --analysis work/lect05/analysis.json --output Assets/软件工程的来龙去脉/cover.png
```

## 内容和验收

- 完整保留正文，只做格式转换，不改写、删减或重排正文。
- 组装后的文章使用 [article-format-correction](<https://github.com/Apprentice-Geo/skills/tree/main/article-format-correction>) skill 校正格式，原始 HTML 与 source.md 保留转换结果；重新组装后需再次校正。
- 转载说明、Agent 导读、阅读时间与原文明确分开；来源和授权链接保留。
- 行内公式用 `$...$`，行间公式用 `$$...$$`；代码内的数学标记保持原样。
- 封面为 1600×1200，三种布局使用同一模板与视觉规范，文案基于正文，左下装饰直接复用 `templates/assets/decoration.png`。
- 视觉采用冷白、灰、深蓝与青蓝配色，严格栅格、清晰层级和方角；通过对齐、留白、文字层级表达关系，编号仅用于纵向索引。左侧布局及公共规范统一，右侧布局按文章适配。
- 知乎中的图片由用户手动上传，不实现平台上传功能。
- 主 Agent 负责抓取转换、分析、发布组装和集成验证；Subagent 负责模板与渲染脚本，不改抓取相关文件。
