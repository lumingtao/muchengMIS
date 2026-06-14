# Stitch / Figma UI Workflow

本文档定义沐辰 MIS 的 UI 双向同步流程。目标是让 Stitch 快速产出 UI 方案，同时保护当前 React + Ant Design 生产项目。

## 边界

- Stitch 和 Figma 是设计输入，不是生产源码入口。
- `frontend/src/` 是唯一前端源码入口。
- `mis_mvp/frontend_dist/` 是 `npm run build` 生成物，不人工编辑、不提交为源码。
- 真实数据、上传文件、后端业务逻辑不参与 UI 设计同步。

## 正向流程：项目到 Stitch / Figma

1. 从当前项目提取上下文：
   - 主题 token：`frontend/src/theme/antdTheme.ts`
   - 项目级组件：`AppButton`、`AppTable`、`StatusTag`、`AppPanel`、`AppFormSection`、`AppModal`
   - 关键页面截图：工作台、订单中心、工单详情、会员、库存、财务
2. 将 `docs/STITCH_DESIGN_BRIEF.md` 作为 Stitch prompt 基础上下文。
3. 在 Stitch 中生成或调整方案后，导出到 Figma 做设计确认。
4. Stitch/Figma 文件只表达视觉和交互意图，不直接覆盖生产代码。

## 反向流程：Stitch / Figma 到项目

1. 将 Stitch/Figma 的变更拆成组件级和页面级：
   - 组件级优先落到 `frontend/src/components/` 和 `frontend/src/theme/`。
   - 页面级落到 `frontend/src/pages/`；尚未拆分的页面暂时落到 `App.tsx` 的局部片段。
2. Stitch 导出的代码、截图、说明放入 `docs/stitch/exports/`，只作参考。
3. 每次只合并一个组件族或一个页面区域。
4. 合并前确认没有修改后端 API payload、数据库字段和真实运行数据。

## 代码落点

- 主题色、圆角、字体、Ant Design token：`frontend/src/theme/antdTheme.ts`
- 通用按钮、表格、状态、表单、弹窗、面板：`frontend/src/components/`
- 顶层壳层：`frontend/src/components/layout/AppShellLayout.tsx`
- 页面样式：
  - `frontend/src/styles/base.css`
  - `frontend/src/styles/layout.css`
  - `frontend/src/styles/components.css`
  - `frontend/src/styles/pages.css`

## 验收

每轮 UI 同步后运行：

```bash
cd frontend
npm run test
npm run build
```

如果涉及后端托管入口，还要验证 `/` 在存在 `mis_mvp/frontend_dist/index.html` 时能返回 React 页面。

可选的浏览器冒烟验证：

```bash
# 先启动带 DevTools 端口的系统 Chrome，再运行：
cd frontend
source ../tools/npm/use-npm.sh
node ../tools/verify-ui.mjs
```

该脚本会连接 `http://127.0.0.1:9222`，登录本地 MIS，切换核心导航，并把截图保存到 `outputs/ui-smoke.png`。

## 禁止事项

- 不让 Stitch 直接覆盖 `frontend/src/App.tsx`。
- 不把 `mis_mvp/frontend_dist/` 当成可编辑源码。
- 不恢复 `mis_mvp/static/` 旧原型回退。
- 不在业务页面大量覆盖 Ant Design 内部 DOM class。
- 不提交 `mis_mvp/data/*.sqlite3`、`mis_mvp/uploads/`、运行日志、缓存和构建产物。
