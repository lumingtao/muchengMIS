# MIS 当前重构维护说明

本文档取代早期 WinForms / `MIS.Core` 重构笔记，记录当前仓库的实际开发主线。

## 1. 当前主线

当前可运行主线是：

```text
mis_mvp/backend      FastAPI + SQLite
frontend             Vite + React + TypeScript
mis_mvp/frontend_dist React 构建产物，由 FastAPI 托管
```

旧 WinForms、`MIS.Core`、`MIS.WebAPI1` 相关内容只作为历史口径参考，不是当前仓库的运行主线。

## 2. 重构目标

当前重构已经从“验证业务原型”进入“本地可维护 MIS”阶段：

- 用 `machines` 承载机器生命周期。
- 用 `repair_orders` 承载维修工单闭环。
- 用 `customers` 承载会员和同行客户。
- 用物料库存表承载维修配件库存。
- 用 `payments`、`receivables` 承载收款、支出和挂账。
- 用 `machine_events`、`operation_logs` 保证追溯。
- 前端逐步从单文件大页面迁移到 React + Ant Design 项目级组件体系。

## 3. 数据库边界

默认运行库：

```text
mis_mvp/data/mis_mvp.sqlite3
```

开发规则：

- 表结构变更集中在 `mis_mvp/backend/db.py`。
- 输入模型变更同步更新 `mis_mvp/backend/models.py`。
- 业务写入优先走 `MisService`，不要绕过服务层直接写 SQL。
- 旧 `devices/repairs` 表保留兼容，但新功能默认不再扩展它们。
- 真实业务导入前先备份 SQLite，并通过幂等键避免重复导入。

## 4. 前端边界

当前前端已接入 Ant Design 6，但仍有历史 CSS 和大体量 `App.tsx`。

维护方向：

- 新按钮、表格、状态、弹窗、表单优先使用 `frontend/src/components/` 下的项目级组件。
- 新页面按业务域拆分，不继续扩大 `App.tsx`。
- API 调用统一走 `frontend/src/api.ts`。
- 构建输出保持到 `mis_mvp/frontend_dist/`。

## 5. 权限和审计

权限矩阵在 `mis_mvp/backend/auth.py`。

涉及以下动作必须记录审计或时间线：

- 维修开单、指派、报价、改价、交付、作废、收款。
- 机器资料编辑和删除。
- 客户资料编辑和互动记录。
- 物料入库、发放、退料、退货、盘点和调整。
- 财务流水、结账和报表关键口径变更。

## 6. 真实业务资料

以下文档是业务规则来源：

- `BUSINESS_REALITY_LOG.md`
- `MATERIAL_INVENTORY_LOG.md`
- `BUSINESS_TIMELINE_SUMMARY.md`
- `CODEX_LOCAL_NOTES.md`

这些文件不替代数据库订单事实。开发时遇到业务规则冲突，以结构化数据库为事实源，以业务观察文档解释规则来源和待确认字段。

## 7. 开发检查清单

变更后至少确认：

- 后端测试：`pytest mis_mvp/tests --basetemp .runtime/pytest-tmp`
- 前端测试：`cd frontend; npm.cmd run test`
- 前端构建：`cd frontend; npm.cmd run build`
- 若改 API：同步更新 `DESIGN.md` 和 `BUSINESS_FLOW.md`
- 若改开单：同步更新 `ORDER_CREATION_ACTION_DESIGN.md`
- 若改 UI 基础层：同步更新 `docs/ANT_DESIGN_6_MIGRATION_PLAN.md`
