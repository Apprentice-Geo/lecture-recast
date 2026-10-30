# lecture-recast

把公开讲义整理为便于阅读和人工审核的 Markdown，并用统一的 HTML/CSS 模板生成文章脉络封面。文章分析由仓库内的 Agent 完成，没有模型调用程序。

项目文章来源于蒋炎岩的[生成式软件工程（GSE/2026）课程讲义](<https://jyywiki.cn/GSE/2026/>)，原站标注 [CC BY-NC 4.0](<https://creativecommons.org/licenses/by-nc/4.0/>)。整理后的文章保留作者、来源链接和授权说明。

目录与数据格式见 [CONTRACT.md](<CONTRACT.md>)，开发命令与规范见 [AGENTS.md](<AGENTS.md>)。

## 安装

使用 uv 管理依赖，需要 Python 3.10+。在仓库根目录执行：

```powershell
uv sync
uv run playwright install chromium
```

依赖记录在 `pyproject.toml` 和 `uv.lock` 中。封面统一使用仓库内置的思源黑体（Source Han Sans SC）可变字体，无需安装系统字体。主标题使用 800 字重，章节与分组标题、讲次数字使用 700，次级标题、标签与条目编号使用 500–600，正文使用 400。

## 工作流

1. 抓取并转换原文。

   ```powershell
   uv run scripts/fetch_article.py --lecture 5
   ```

   生成 `work/lect05/source.html`、`source.md`、`metadata.json`，下载正文图片到 `Assets/<文章名称>/`。页面虽然以 `.md` 结尾，但返回 HTML；只转换 `.wiki` 正文，不纳入导航和站点页脚。下载失败直接报错，不静默丢图。

   发布标题以课程目录为准，完整保留分讲括注；原文部分保留正文自身的标题。例如第 3 讲发布为「版本管理 (1)」，正文标题仍为「版本管理」。

   已有原始 HTML 时可重新转换（正文图片仍会下载）：

   ```powershell
   uv run scripts/fetch_article.py --lecture 5 --html work/lect05/source.html
   ```

2. 让 Agent 完整阅读 `source.md`，按 CONTRACT.md 格式编辑同目录下的 `analysis.json`。第 5 讲已经完成。重新抓取后应重新核对分析，脚本不会自动更新它。

3. 根据分析渲染封面。`--html` 可选，保存内嵌装饰图的 HTML 预览；字体通过相对路径引用 `templates/assets/fonts/`，离线查看时需保留仓库目录结构。

   ```powershell
   uv run scripts/render_cover.py --analysis work/lect05/analysis.json --output Assets/软件工程的来龙去脉/cover.png --html work/lect05/cover.html
   ```

   封面为 1600×1200，三种布局共用左侧、配色和字体层级。纵向索引（`index`）用编号引导阅读；对照矩阵（`matrix`）用明确的行列维度比较对象；分组结构（`grouped`）用分类与子项表达归属。矩阵和分组不使用右侧编号或连接线。复用 `templates/assets/decoration.png`，不调用图像生成。文字溢出时报错，需调整文案再渲染。

   在 analysis.json 中设置 `layout` 并填写对应数据，格式见 [布局约定](<CONTRACT.md#右侧布局>)。也可用 `--layout` 覆盖选择，但必须提供所选布局的数据，不会自动把章节大纲转换为对照表或分组。现有样图使用不同文章：

   ```powershell
   uv run scripts/render_cover.py --analysis work/lect07/analysis.json --output "Assets/需求和架构 (2)/cover.png" --html work/lect07/cover.html
   uv run scripts/render_cover.py --analysis work/lect09/analysis.json --output "Assets/DeepSeek Harness/cover.png" --html work/lect09/cover.html
   ```

4. 组装文章。

   ```powershell
   uv run scripts/build_publish.py --work work/lect05
   ```

   输出 `articles/软件工程的来龙去脉.md`。作者与来源信息、阅读时间、Agent 导读和封面放在正文之前。导读与封面使用同一份 `analysis.json`。

5. 使用 [article-format-correction](<https://github.com/Apprentice-Geo/skills/tree/main/article-format-correction>) skill 校正 `articles/` 中的文章格式。

   由 Agent 按该 skill 轻量校正标点、空格、Markdown 链接和公式标记，保留作者原意、结构、代码及 URL。原始 HTML 和 `source.md` 不作编辑性校正，供对照检查。重新组装文章会覆盖校正结果，需要再次应用该 skill。

## 更新检查

```powershell
uv run scripts/check_updates.py
uv run scripts/check_updates.py --check-only
```

脚本从课程目录发现已发布的讲义，检查所有讲次，不依赖连续编号；实验链接不纳入处理。对比本地 `source.md`、目录标题及正文图片的实际内容，因此同一 URL 下的图片更新也能识别。页面导航或页脚变化不会触发重新处理。

默认下载新增或变化的正文、图片和元数据，终端逐篇输出检查与处理状态，最后给出统计和待办路径，同时保存 `work/update-report.json`。`--check-only` 只读取远端与本地内容，不写文件。单篇失败继续检查其余文章；有失败时返回退出码 1，否则为 0。

发现变化后，`work/lectNN/update_pending.json` 标记后续工作。让 Agent 根据报告完整阅读当前 `source.md`，核对或创建 `analysis.json`，渲染并查看封面，组装文章，再使用 article-format-correction skill 校正格式；全部完成后删除该篇的待办标记。未完成的待办会在下次检查时继续提示。旧分析和已校正文章在抓取阶段保留，脚本不会把抓取完成误报为发布完成，也不会调用模型或自动沿用旧摘要。

下载或转换失败不会覆盖该篇已有正文和元数据。标题改变时，新资源使用新标题的目录，旧文章和资源保留，由 Agent 在完成处理后核对。重新运行检查不会改写无变化文章的校正成果。

## 结果与检查

| 讲次 | 整理后的文章 | 封面 | 布局与内容关系 |
| --- | --- | --- | --- |
| 1 | [欢迎来到未来](<articles/欢迎来到未来.md>) | [PNG](<Assets/欢迎来到未来/cover.png>) | 索引：从能力变化、工具组合到工程反馈 |
| 2 | [提示词与上下文工程](<articles/提示词与上下文工程.md>) | [PNG](<Assets/提示词与上下文工程/cover.png>) | 分组：任务表达、方法积累、长程探索 |
| 3 | [版本管理 (1)](<articles/版本管理 (1).md>) | [PNG](<Assets/版本管理 (1)/cover.png>) | 索引：快照、操作、提交、交付与并发 |
| 4 | [版本管理 (2)](<articles/版本管理 (2).md>) | [PNG](<Assets/版本管理 (2)/cover.png>) | 索引：制品关系、变化身份、协作与 MVP |
| 5 | [软件工程的来龙去脉](<articles/软件工程的来龙去脉.md>) | [PNG](<Assets/软件工程的来龙去脉/cover.png>) | 索引：保留此前完成的成果 |
| 6 | [需求和架构 (1)](<articles/需求和架构 (1).md>) | [PNG](<Assets/需求和架构 (1)/cover.png>) | 分组：计算表示、历史依据、业务职责 |
| 7 | [需求和架构 (2)](<articles/需求和架构 (2).md>) | [PNG](<Assets/需求和架构 (2)/cover.png>) | 矩阵：四类系统的稳定约定与变化空间 |
| 8 | [Agent Native 开发](<articles/Agent Native 开发.md>) | [PNG](<Assets/Agent Native 开发/cover.png>) | 分组：工作状态、检查流程、验证学习 |
| 9 | [DeepSeek Harness](<articles/DeepSeek Harness.md>) | [PNG](<Assets/DeepSeek Harness/cover.png>) | 分组：共同对象、协作规则、应用扩展 |
| 10 | [软件的演化](<articles/软件的演化.md>) | [PNG](<Assets/软件的演化/cover.png>) | 索引：演化案例、提交历史与规则的边界 |

原文、原始 HTML、分析、元数据与封面预览保存在各自的 `work/lect01/` 至 `work/lect10/` 中。封面均为 1600×1200，并经过溢出检查和逐张视觉核对。文章保留作者署名、来源与 CC BY-NC 4.0 授权；导读与正文分开。

文章已按 article-format-correction skill 校正引号、链接目标、英文书名及少量数学标记，代码、URL、有效公式与正文段落顺序保留。第 8 讲正文「从 Agent 周围的工具……也能理解本讲『Deepseek Harness』这个题目的着眼点」与当前标题「Agent Native 开发」不一致，可能是旧标题残留；正文保留原句，需原作者确认。

```powershell
uv run python -m unittest discover -s tests -v
```

测试覆盖转换时的代码、链接、表格、图片和 TeX 保留、下载失败处理、封面布局与溢出，以及第 5 讲快照的全文比对。封面测试需要已安装 Chromium，首次运行完整测试前须组装文章。

## 许可证

本仓库按内容类型分别授权：

| 范围 | 许可证 |
| --- | --- |
| 本项目代码、脚本、测试、HTML/CSS 模板实现、开发配置及开发文档 | [GNU GPL v3（GPL-3.0-only）](<LICENSE>) |
| 文章正文、导读与分析文案、图片、装饰素材和生成封面等内容资源 | [CC BY-NC 4.0（署名—非商业性使用 4.0 国际）](<LICENSE-CC-BY-NC-4.0>) |
| 第三方思源黑体字体文件 | [SIL Open Font License 1.1](<templates/assets/fonts/source-han-sans/LICENSE.txt>)（保留原授权） |

文章和图片等资源采用与[原课程讲义](<https://jyywiki.cn/GSE/2026/>)相同的 CC BY-NC 4.0 协议，包括 `articles/`、`Assets/`、`templates/assets/` 中除第三方字体外的资源，以及 `work/` 中保存的讲义与整理文案。使用这些资源时须保留署名、来源和许可证链接，注明修改，并遵守非商业性使用条件。原文版权归原作者所有；另有明确授权声明的第三方内容保留其原有授权。

内置字体为 Adobe [思源黑体（Source Han Sans）](<https://github.com/adobe-fonts/source-han-sans>)官方发布的简体中文可变字体 `SourceHanSansSC-VF.otf.woff2`，未经修改，保存在 `templates/assets/fonts/source-han-sans/`。字体及原始许可证取自[上游固定提交](<https://github.com/adobe-fonts/source-han-sans/tree/a4f7cf94edfb9d7ffbdfc4841de276358bd7e0f2>)，版权为 Copyright 2014–2025 Adobe，保留字体名称为 “Source”。字体继续遵循 SIL Open Font License 1.1，不改为本项目的 GPL 或 CC 协议；原始版权声明和许可证全文随字体保留在 [LICENSE.txt](<templates/assets/fonts/source-han-sans/LICENSE.txt>) 中。使用该字体生成的封面仍按本项目的内容资源授权。

生成的 HTML 预览包含模板代码与文章、图片内容，分别遵循上述许可证；引用的字体保留其原授权。第三方依赖遵循其各自的许可证。
