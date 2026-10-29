# 开发约定

## 常用命令

在仓库根目录执行，使用 uv 管理依赖和运行 Python：

```powershell
uv sync
uv run playwright install chromium
uv run scripts/fetch_article.py --lecture 5
uv run scripts/fetch_article.py --lecture 5 --html work/lect05/source.html
uv run scripts/render_cover.py --analysis work/lect05/analysis.json --output Assets/软件工程的来龙去脉/cover.png --html work/lect05/cover.html
uv run scripts/build_publish.py --work work/lect05
uv run python -m unittest discover -s tests -v
```

依赖以 `pyproject.toml` 为准，通过 `uv add`、`uv remove` 修改，并同步更新 `uv.lock`。不维护第二份依赖清单。

## 开发规范

- 代码、模板实现及开发文档使用 GPL v3；文章、分析文案与图片等内容资源使用 CC BY-NC 4.0。具体范围见 README 的许可证说明，保留原作者署名、来源和第三方授权声明。
- 保持脚本轻量、职责明确，优先复用已有代码，不引入数据库、Web 服务、LLM SDK 或调度框架。
- 文章分析由 Agent 完整阅读正文后完成，不编写模型调用程序。目录和交接格式以 [CONTRACT.md](<CONTRACT.md>) 为准。
- `source.html` 与 `source.md` 保留抓取结果供核对，不对其应用编辑性校正；文章校正在 `articles/` 中进行，不改写、删减或重排作者内容。
- 每次组装文章后，使用 [article-format-correction](<https://github.com/Apprentice-Geo/skills/tree/main/article-format-correction>) skill 轻量校正文章格式，保留原意、段落、代码、URL 和有效公式。不要用全局正则替代 Agent 对技术内容的判断。重新运行组装脚本会覆盖校正结果，需再次应用该 skill。
- `analysis.json` 是导读和封面文案的共同数据源；重新抓取后人工核对分析，不将旧摘要当作新正文的分析结果。
- 封面默认使用 `index`，右侧采用带编号的 `sections`；对照矩阵使用 `matrix.columns/rows`，分组使用 `groups/items`，两者不带编号或连接线。每篇只维护所选布局的数据，`--layout` 仅覆盖选择，不自动转换大纲。字段约定见 CONTRACT.md。
- 所有文章集中放在 `articles/`；正文图片放在 `Assets/<文章名称>/`，模板素材放在 `templates/assets/`。图片引用使用相对路径，Markdown 链接目标使用尖括号。
- 保留用户已有改动；只修改当前任务涉及的文件，不顺手重构或清理无关内容。
- 修改后执行相关检查；涉及转换或渲染时运行测试，模板变更还需查看导出的 PNG，确认尺寸、可读性及文字溢出情况。如实说明验证失败或受阻情况。
