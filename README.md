# lecture-recast

把公开讲义整理为便于阅读和人工审核的 Markdown，并用统一的 HTML/CSS 模板生成文章脉络封面。文章分析由仓库内的 Agent 完成，没有模型调用程序。

项目文章来源于蒋炎岩的[生成式软件工程（GSE/2026）课程讲义](<https://jyywiki.cn/GSE/2026/>)，原站标注 [CC BY-NC 4.0](<https://creativecommons.org/licenses/by-nc/4.0/>)。整理后的文章保留作者、来源链接和授权说明。

第一版已处理第 5 讲「软件工程的来龙去脉」。目录与数据格式见 [CONTRACT.md](<CONTRACT.md>)，开发命令与规范见 [AGENTS.md](<AGENTS.md>)。

## 安装

使用 uv 管理依赖，需要 Python 3.10+。在仓库根目录执行：

```powershell
uv sync
uv run playwright install chromium
```

依赖记录在 `pyproject.toml` 和 `uv.lock` 中。模板使用系统字体（优先微软雅黑、苹方、思源黑体），跨系统字形与换行可能略有差异。

## 工作流

1. 抓取并转换原文。

   ```powershell
   uv run scripts/fetch_article.py --lecture 5
   ```

   生成 `work/lect05/source.html`、`source.md`、`metadata.json`，下载正文图片到 `Assets/<文章名称>/`。页面虽然以 `.md` 结尾，但返回 HTML；只转换 `.wiki` 正文，不纳入导航和站点页脚。下载失败直接报错，不静默丢图。

   已有原始 HTML 时可重新转换（正文图片仍会下载）：

   ```powershell
   uv run scripts/fetch_article.py --lecture 5 --html work/lect05/source.html
   ```

2. 让 Agent 完整阅读 `source.md`，按 CONTRACT.md 格式编辑同目录下的 `analysis.json`。第 5 讲已经完成。重新抓取后应重新核对分析，脚本不会自动更新它。

3. 根据分析渲染封面。`--html` 可选，保存内嵌装饰图的独立预览。

   ```powershell
   uv run scripts/render_cover.py --analysis work/lect05/analysis.json --output Assets/软件工程的来龙去脉/cover.png --html work/lect05/cover.html
   ```

   第一版为 1600×1200 纵向索引，支持 4–7 个脉络条目。复用 `templates/assets/decoration.png`，不调用图像生成。文字溢出时报错，需调整文案再渲染。

4. 组装文章。

   ```powershell
   uv run scripts/build_publish.py --work work/lect05
   ```

   输出 `articles/软件工程的来龙去脉.md`。作者与来源信息、阅读时间、Agent 导读和封面放在正文之前。导读与封面使用同一份 `analysis.json`。

5. 使用 [article-format-correction](<https://github.com/Apprentice-Geo/skills/tree/main/article-format-correction>) skill 校正 `articles/` 中的文章格式。

   由 Agent 按该 skill 轻量校正标点、空格、Markdown 链接和公式标记，保留作者原意、结构、代码及 URL。原始 HTML 和 `source.md` 不作编辑性校正，供对照检查。重新组装文章会覆盖校正结果，需要再次应用该 skill。

## 结果与检查

- 整理后的文章：`articles/软件工程的来龙去脉.md`
- 封面：`Assets/软件工程的来龙去脉/cover.png`
- 原文、原始 HTML、分析、元数据与封面预览：`work/lect05/`

```powershell
uv run python -m unittest discover -s tests -v
```

测试覆盖转换时的代码、链接、表格、图片和 TeX 保留、下载失败处理、封面布局与溢出，以及第 5 讲快照的全文比对。封面测试需要已安装 Chromium，首次运行完整测试前须组装文章。

模板装饰素材 `templates/assets/decoration.png` 由本项目提供，不据原站授权推定其许可。
