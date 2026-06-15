# Git 合并与远端同步记录

建立日期：2026-06-14

用途：记录本仓库每次合并、拉取、提交、推送与远端同步的自然语言说明，方便后续回退、定位变更来源、补充修改或恢复某个版本。

## 使用规则

- 每次执行合并、拉取、提交、推送前后，都在本文档追加一条记录。
- 记录要写清楚：时间、分支、远端、操作类型、提交号、变更内容、验证情况、回退参考。
- 每次修改代码、配置、业务流程、数据口径或操作方式时，要实时更新项目中相应的文档。
- 如果本次变更涉及多个文档范围，要在记录中说明已更新哪些文档；如果确认无需更新文档，也要写明原因。
- 不覆盖历史记录；如需修正，只追加“更正说明”。
- 如果发生冲突、合并失败、推送失败或回滚，也必须记录原因和处理结果。
- 自然语言优先，避免只写提交号，确保非开发人员也能看懂版本变化。

## 记录模板

```text
### YYYY-MM-DD HH:mm | 操作摘要

- 分支：main
- 远端：origin/main
- 操作：提交 / 拉取 / 合并 / 推送 / 回滚 / 冲突处理
- 提交：短提交号 提交标题
- 变更内容：
  - 用业务语言说明改了什么。
  - 用影响范围说明涉及哪些页面、接口、数据或流程。
- 同步结果：本地与远端一致 / 本地超前 / 远端超前 / 存在冲突
- 验证情况：运行了哪些检查；如未运行，说明原因。
- 回退参考：如需回退，可优先查看或 revert 哪个提交。
- 备注：其他风险、后续待办或人工确认项。
```

## 变更记录

### 2026-06-15 09:13 CST | 更正后端测试环境并补跑测试

- 分支：main
- 远端：origin/main
- 操作：更正文档中的本地测试命令说明，补充 macOS / Codex 本地虚拟环境用法
- 提交：Document local pytest environment（本记录随该提交一起生成，最终短提交号以 `git log` 为准）
- 变更内容：
  - 确认仓库根目录存在 `.venv/bin/python`，其中已安装 `pytest 9.0.3`；上次失败原因是使用了不存在的 `../.venv/bin/python` 相对路径。
  - 更新 `README.md` 和 `mis_mvp/README.md`，补充 `.venv/bin/python` 安装依赖、启动 API 和运行后端测试命令。
- 同步结果：本地提交已生成，当前本地 `main` 超前 `origin/main`，待推送。
- 验证情况：已运行 `.venv/bin/python -m pytest mis_mvp/tests --basetemp .runtime/pytest-tmp`，结果 `46 passed, 1 warning in 1.77s`。
- 回退参考：如需撤销本次文档更正，可 revert 本条记录对应的 `Document local pytest environment` 提交。
- 备注：保留上一条历史记录原文，本条作为更正说明追加。

### 2026-06-15 09:08 CST | 提交维修物料仓模块更新并同步远端

- 分支：main
- 远端：origin/main
- 操作：提交当前工作区变更，随后 fetch 并推送到远端
- 提交：待生成
- 变更内容：
  - 新增维修物料仓前端页面 `frontend/src/pages/warehouse/WarehousePage.tsx`，覆盖库存看板、物料档案、入库批次、单件码、申领、退料、盘点、调整、流水和基础资料。
  - 后端扩展仓库相关 API、数据库迁移、模型、仓储和服务层，支持物料查询、批次详情、单件码筛选、申领/退料详情、盘点、调整、流水，以及维修工单物料预留/消耗/释放。
  - 新增 `mis_mvp/tools/reset_warehouse_demo.py`，用于清空并重建演示维修物料仓数据。
  - 更新后端 API 和维修流程测试，更新前端布局、页面样式和构建产物。
  - 实时更新 `README.md` 和 `MATERIAL_INVENTORY_LOG.md`，补充仓库模块入口、脚本用法和库存业务口径。
- 同步结果：待提交并推送后确认。
- 验证情况：已尝试运行后端测试；`../.venv/bin/python` 不存在，Codex 自带 Python 和系统 Python 均未安装 `pytest`，因此本次未能完成自动化测试。
- 回退参考：如需撤销本次仓库模块更新，可优先 revert 本次待生成提交；如只撤销演示数据脚本，可单独恢复 `mis_mvp/tools/reset_warehouse_demo.py`。
- 备注：新构建资源受 `.gitignore` 忽略，需要强制纳入提交，避免 `frontend_dist/index.html` 指向缺失 bundle。

### 2026-06-14 20:58 CST | 快进同步远端 main 最新提交

- 分支：main
- 远端：origin/main
- 操作：fetch 后将本地 `main` 快进到 `origin/main`，并准备提交本次同步留痕
- 提交：
  - 同步前本地基线：96f985c Document codex stitch merge
  - 同步后远端最新：a3e26f4 Add repair order module updates
  - 本次拉取范围：远端新增 6 个提交
- 变更内容：
  - 引入维修工单模块相关更新，包括需求文档、开发计划、问题报告和前后端功能调整。
  - 新增 `docs/BUG_REPORT.md`、`docs/repair-order-module-development-plan.md`、`docs/repair-order-module-requirements.md`、`docs/repair-order-module-requirements-questionnaire.md`，补齐维修工单模块文档。
  - 前端新增 `frontend/src/App.test.ts`，调整 `App.tsx`、状态标签测试和页面样式，并更新 `package.json`、`package-lock.json`。
  - 后端新增 `mis_mvp/backend/order_numbers.py`，并更新 API、认证、数据库、模型、仓储和服务层逻辑。
  - 更新维修工单相关测试和前端构建产物，替换旧 bundle 文件。
- 同步结果：本地已从 `96f985c` 快进到 `a3e26f4`；当前将通过后续留痕提交再次推送，使远端包含本同步记录。
- 验证情况：本次执行的是快进同步和文档留痕；尚未运行自动化测试或 UI 验证。
- 回退参考：
  - 如需回退本次远端同步带来的业务变更，可优先从 `a3e26f4` 往前分析这 6 个远端提交。
  - 如只需撤销本地同步留痕，可 revert 后续的同步记录提交。
- 备注：本次没有冲突；项目文档已随远端提交新增和更新，本文件按要求实时记录同步过程。

### 2026-06-14 09:18 CST | 合并 codex/stitch 到主分支

- 分支：main
- 远端：origin/main
- 操作：从本地分支 `codex/stitch` 合并到 `main`，准备提交最新留痕并推送远端
- 提交：
  - 合并提交：d394ea4 Merge codex/stitch into main
  - 来源提交：1cd75c0 Remove obsolete code and simplify backend
- 变更内容：
  - 引入 Stitch 相关界面整理成果，新增 `docs/STITCH_DESIGN_BRIEF.md`、`docs/STITCH_UI_WORKFLOW.md`、`docs/stitch/` 目录和前端页面说明。
  - 新增 `frontend/src/components/layout/AppShellLayout.tsx`，并将原先集中的样式拆分为 `base.css`、`components.css`、`layout.css`、`pages.css`，降低单个样式文件体积。
  - 更新 `README.md`、`DESIGN.md`、Ant Design 迁移计划和 UI 组件库评估文档，使文档与当前 Stitch/UI 结构同步。
  - 删除旧静态页面资源 `mis_mvp/static/app.js`、`mis_mvp/static/index.html`、`mis_mvp/static/styles.css`，以及部分旧前端构建产物和 TypeScript 构建缓存。
  - 新增 `tools/npm/` 辅助脚本和 `tools/verify-ui.mjs`，用于后续 UI 验证和本地工具链说明。
  - `.gitignore` 补充运行时/缓存类文件忽略规则，并移除仓库中已存在的 pytest 临时链接和 pid 文件。
- 同步结果：合并已在本地完成，无冲突；当前 `main` 暂时超前 `origin/main`，等待推送。
- 验证情况：本次先完成 Git 合并和文档留痕；尚未运行自动化测试或 UI 验证。
- 回退参考：
  - 如需撤销整个分支合并，可优先评估 revert 合并提交 `d394ea4`。
  - 如只需撤销 Stitch 来源变更，可评估来源提交 `1cd75c0` 涉及的文件范围。
- 备注：本记录文件 `GIT_SYNC_LOG.md` 已按要求实时更新；Stitch 相关项目文档已由合并内容同步更新。

### 2026-06-14 | 新增 Git 同步记录机制

- 分支：main
- 远端：origin/main
- 操作：新增版本记录文件，准备提交并同步远端
- 提交：待生成
- 变更内容：
  - 新增 `GIT_SYNC_LOG.md`，作为后续 Git 合并、提交、推送、回滚的统一留痕文件。
  - 明确后续每次更新都要写自然语言记录，说明变更内容、同步结果、验证情况和回退参考。
  - 补充要求：项目代码、配置、业务流程、数据口径或操作方式发生变化时，要实时更新对应文档。
- 同步结果：待提交并推送后确认。
- 验证情况：文档类变更，暂不需要运行自动化测试。
- 回退参考：如不再需要该机制，可删除本文件或 revert 对应提交。
- 备注：后续每次执行“提交最新变更”“与远端同步”“合并远端变化”等操作时，应先或同步更新本文档。

### 2026-06-14 | 修复手动维修故障录入并同步远端

- 分支：main
- 远端：origin/main
- 操作：提交并推送
- 提交：232e80a Fix manual repair item handling
- 变更内容：
  - 修复新建维修工单时手动输入故障必须选择故障代码的问题。
  - 后端支持为手动故障自动生成 `AUTO-` 故障代码，并写入维修 SKU/故障代码列表，便于后续复用。
  - 前端移除空字段显示 `??` 的兜底，详情页空值保持为空。
  - 维修报价文案统一为“配件价格”和“人工费”，减少与内部成本口径混淆。
  - 新增 `BUG_TIMELINE.md`，记录已发现 bug、影响范围、修复状态和验证结果。
  - 更新前端构建产物。
- 同步结果：已推送到 `origin/main`，本地 `main` 与远端一致。
- 验证情况：本次记录根据提交内容和已生成构建产物整理；详细测试结果见 `BUG_TIMELINE.md` 中对应 bug 记录。
- 回退参考：如需撤销该轮业务修复，可优先评估 revert `232e80a`。
- 备注：该提交包含业务修复、测试更新、bug 台账和构建产物替换。

### 2026-06-14 | 更新维修工单流程并同步远端

- 分支：main
- 远端：origin/main
- 操作：提交并推送
- 提交：2927de5 Update machine repair workflow
- 变更内容：
  - 更新维修工单相关前后端逻辑。
  - 调整维修流程数据模型、仓储、服务层和测试。
  - 更新前端界面和样式，并替换前端构建产物。
  - 同步运行时 pid 文件变更。
- 同步结果：已推送到 `origin/main`，之后远端基线推进到 `2927de5`。
- 验证情况：未在当次同步记录中单独留存测试命令输出。
- 回退参考：如需撤销该轮维修流程调整，可优先评估 revert `2927de5`。
- 备注：后续 `232e80a` 基于该提交继续修复手动故障录入问题。
