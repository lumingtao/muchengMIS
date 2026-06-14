# Stitch Design Brief

将本文件作为 Stitch / Figma 设计修改的固定上下文。

## Product

沐辰科技 MIS 是手机维修、会员、库存、回收销售和财务管理后台。使用者主要是前台、维修工程师、仓库、财务、管理员和老板。

## Current Stack

- React 18 + Vite + TypeScript
- TanStack Query
- Ant Design 6
- lucide-react
- 项目级组件封装优先，不引入 Tailwind 或新的主 UI 库

## Visual Direction

- 企业后台，不做营销页。
- 高密度、可扫读、稳定、克制。
- 主色：深蓝 `#003d9b`
- 背景：浅灰页面 + 白色内容区
- 圆角：6-8px 为主
- 状态色：成功绿、待处理黄、异常红、信息蓝、中性灰
- 表格和表单优先考虑效率、对齐和信息密度。

## Stable Design Boundaries

Stitch 方案需要优先映射到这些生产边界：

- `frontend/src/theme/antdTheme.ts`
- `frontend/src/components/actions/AppButton.tsx`
- `frontend/src/components/data/AppTable.tsx`
- `frontend/src/components/data/StatusTag.tsx`
- `frontend/src/components/feedback/AppModal.tsx`
- `frontend/src/components/forms/AppFormSection.tsx`
- `frontend/src/components/layout/AppPanel.tsx`
- `frontend/src/components/layout/AppShellLayout.tsx`

## Core Screens

- 工作台首页：指标、待办、消息、审批、库存预警。
- 订单中心：维修工单池、搜索、状态筛选、高级筛选、导出、新建、查看、编辑、取消。
- 工单详情：设备、客户、检测、照片、报价、维修项目、备注、时间线、交付和收款。
- 会员管理：会员列表、筛选、档案、互动记录、欠款和回访。
- 库存管理：物料、批次、单件码、申领、审批、退料、流水。
- 财务：付款流水、报表、审计。

## Output Rules

- 优先生成可映射到 Ant Design 组件的设计。
- 表格需支持横向滚动、状态标签、金额格式和空态。
- 表单需紧凑、字段分组清晰、校验提示一致。
- 图标优先使用 lucide 风格。
- 不输出需要新运行时依赖的复杂视觉方案，除非明确说明收益。
- 不输出整站一次性重绘方案；优先组件库或单页面区域。
