# Ant Design 6 迁移计划与当前进展

本文档记录 Ant Design 6 在当前 React 前端中的落地状态和后续迁移路线。

## 1. 当前进展

已完成：

- 安装 `antd@^6.4.3`。
- `frontend/src/main.tsx` 接入 `ConfigProvider`。
- 接入中文 locale：`antd/locale/zh_CN`。
- 接入 Ant Design `App` 上下文。
- 引入 `dayjs/locale/zh-cn`。
- 建立 `frontend/src/theme/antdTheme.ts`。
- 建立反馈桥：`components/feedback/AntdFeedbackBridge.tsx`。
- 建立项目级组件：
  - `components/actions/AppButton.tsx`
  - `components/data/AppTable.tsx`
  - `components/data/StatusTag.tsx`
  - `components/data/QueryState.tsx`
  - `components/feedback/AppModal.tsx`
  - `components/forms/AppFormSection.tsx`
  - `components/layout/AppPanel.tsx`
- 前端测试已覆盖部分组件。

仍在进行：

- `frontend/src/App.tsx` 仍承担大量页面、状态和业务逻辑。
- 全局 CSS 仍有历史样式，需要继续收敛作用域。
- 多数业务表单仍未完全迁移到 Ant Design Form。
- 页面级代码还没有按业务域拆分。

## 2. 目标结构

目标不是套用 Ant Design 默认模板，而是形成项目自己的 MIS 前端基础层：

```text
frontend/src/
  api.ts
  main.tsx
  theme/
    antdTheme.ts
  components/
    actions/
    data/
    feedback/
    forms/
    layout/
  pages/
    dashboard/
    repair/
    customers/
    warehouse/
    finance/
    settings/
```

## 3. 迁移原则

- 业务行为不因 UI 迁移改变。
- 新组件先进入项目级封装，再进入业务页。
- 不直接覆盖 Ant Design 内部 class。
- 保持当前构建输出到 `mis_mvp/frontend_dist/`，并把它作为生成物处理。
- 每次迁移一个页面或组件族，配套补测试。
- 优先处理高频、高价值、低风险区域。

## 4. 下一阶段路线

### 阶段 A：CSS 收敛

目标：减少历史全局选择器对 Ant Design 的影响。

任务：

- 找出 `button`、`input`、`select`、`textarea`、`table`、`th`、`td` 等全局选择器。
- 将旧样式收敛到明确的业务容器或低权重选择器。
- 保留 CSS 变量作为主题来源。
- 避免使用 `!important` 修补 Ant Design。

验收：

- Ant Design Button、Input、Table 不被旧规则破坏。
- 旧页面视觉保持稳定。

### 阶段 B：表格统一

目标：维修工单池、会员列表、库存流水、财务流水都通过 `AppTable` 统一。

任务：

- 补充列渲染、金额、状态、空态和加载态能力。
- 增加分页、排序和必要的横向滚动。
- 保留现有筛选逻辑。

验收：

- 主要列表可扫读、无横向挤压、状态色一致。
- 表格变更不影响 API 请求和工单详情跳转。

### 阶段 C：表单迁移

目标：把高频业务表单迁移到 Ant Design Form 或项目级 `AppFormSection`。

优先级：

1. 新建维修工单。
2. 工单详情编辑。
3. 会员新增/编辑。
4. 物料入库和申领。
5. 财务流水登记。

验收：

- 校验提示一致。
- 字段布局紧凑。
- 提交 payload 与现有 API 保持兼容。

### 阶段 D：页面拆分

目标：降低 `App.tsx` 维护成本。

建议拆分：

- `pages/repair/RepairPool.tsx`
- `pages/repair/OrderDetailPage.tsx`
- `pages/customers/CustomersPage.tsx`
- `pages/warehouse/WarehousePage.tsx`
- `pages/finance/PaymentsPage.tsx`
- `pages/settings/SettingsPage.tsx`

验收：

- `App.tsx` 只保留 shell、路由和顶层状态。
- 页面内部 API query key 和 mutation 仍清晰可追踪。

## 5. 测试要求

前端每轮迁移至少运行：

```powershell
cd frontend
npm.cmd run test
npm.cmd run build
```

建议新增测试：

- 表格列格式化。
- 状态标签映射。
- 表单提交 payload。
- 弹窗确认/取消行为。
- API 错误提示。

## 6. 风险清单

- 全局 CSS 污染 Ant Design 内部 DOM。
- 表格迁移导致点击行、排序和筛选行为回归。
- 表单迁移时数字字段被当成字符串，影响后端 Pydantic 校验。
- Ant Design Modal/message 使用静态 API 时丢失主题上下文，需继续走项目级封装。
- `App.tsx` 拆分时 query invalidation key 不一致，导致数据刷新异常。

## 7. 当前保留策略

- `lucide-react` 继续作为主图标库。
- 历史 `mis_mvp/static/` 已移除，不再保留旧原型回退。
- Ant Design 作为主组件库，不再重复评估新主库，除非出现明确阻塞。
