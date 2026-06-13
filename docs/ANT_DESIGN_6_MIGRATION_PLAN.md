# Ant Design 6 兼容优先改造计划书

日期：2026-06-12  
项目：沐辰科技 MIS 管理系统  
目标：优先将现有 React 前端改造为兼容 Ant Design 6 的工程结构、样式结构和组件边界，然后再逐步使用 Ant Design 6 UI 组件库。

## 1. 改造原则

本计划不建议一开始就大面积替换页面 UI。当前项目已有可运行的 React + Vite 前端，业务逻辑集中在 `frontend/src/App.tsx`，样式集中在 `frontend/src/styles.css`，且存在大量全局 `button`、`input`、`select`、`textarea`、`table` 选择器。若直接安装并使用 Ant Design 6，最大风险不是组件 API，而是全局样式污染、视觉不一致、页面布局抖动和一次性改动过大。

因此采用“两步走”：

1. 先兼容：建立 Ant Design 6 可安全共存的依赖、主题、样式隔离、组件适配层和验收机制。
2. 再使用：按页面价值和风险，逐步把现有自研组件替换为 Ant Design 6 组件。

## 1.1 自查修订记录

对本计划做二次审查后，发现原计划方向正确，但有 5 个容易在实际落地时踩坑的遗漏，已在后续阶段补充：

1. Ant Design 的 `message`、`notification`、`Modal` 静态能力需要考虑主题上下文，不能只接 `ConfigProvider`，还应规划 `App` 组件或项目级 `notify` 封装。
2. `legacy-ui` 如果包住整个应用，新引入的 Ant Design 组件仍可能被旧选择器影响；兼容策略应改为“旧组件局部 legacy，新组件默认干净”，不能简单给根节点套一层。
3. 安装 `antd` 但没有任何 import 时，构建不能证明 Ant Design 能被 Vite 正确打包；应增加最小兼容探针或在 `ConfigProvider` 阶段验证真实 import。
4. Ant Design 组件测试常需要 `ResizeObserver`、`matchMedia` 等浏览器 API，当前 `testSetup.ts` 只有 `jest-dom`，需要提前规划 polyfill。
5. 日期、时间类组件除中文 locale 外，还需要确认 dayjs locale 和业务日期格式，否则后续迁移 DatePicker 时会出现中英文混排或格式不一致。

## 2. 当前状态判断

前端技术栈：

- React 18.3.1
- Vite 5.4.x
- TypeScript 5.6.x
- TanStack Query 5
- lucide-react
- 自研 CSS

当前未接入：

- `antd`
- Ant Design `ConfigProvider`
- Ant Design `App` 上下文组件
- Ant Design 主题 token
- Ant Design 样式重置或兼容层
- Ant Design 相关测试环境 polyfill

现有重点组件边界：

| 当前实现 | 位置 | 后续 Ant Design 对应 |
| --- | --- | --- |
| `DataTable` | `frontend/src/App.tsx` | `Table` + `Tag` + `Empty` |
| `Panel` | `frontend/src/App.tsx` | `Card` 或项目级 `AppPanel` |
| `SimpleForm` | `frontend/src/App.tsx` | `Form` + `Input` + `Select` |
| `QueryState` | `frontend/src/App.tsx` | `Spin` + `Result` + `Empty` |
| 自研 modal | `frontend/src/App.tsx` / `styles.css` | `Modal` 或 `Drawer` |
| 自研 toast | `frontend/src/App.tsx` / `styles.css` | `message` 或 `notification` |
| `.badge` | `styles.css` | `Tag` 或项目级 `StatusTag` |

主要兼容风险：

- 全局 `button/input/select/textarea/table` 样式会影响 Ant Design 内部 DOM。
- 当前 `.panel`、`.modal`、`.table-wrap`、`.badge` 等类名承担了业务语义和视觉样式，直接替换会牵动范围大。
- `App.tsx` 体量很大，页面、组件、数据逻辑混在一起，直接替换组件容易引入行为回归。
- 现有构建输出由 FastAPI 服务 `mis_mvp/frontend_dist/`，改造必须保持 `npm.cmd run build` 输出路径不变。
- 反馈类组件若直接使用 Ant Design 静态 API，可能拿不到当前主题、locale 或上下文配置。
- Ant Design Table、Modal、Dropdown 等组件在测试环境可能依赖浏览器 API，需要补齐 jsdom 缺失能力。

## 3. 目标架构

目标不是把项目变成“Ant Design 默认模板”，而是形成一个可控的 MIS 前端基础层：

```text
frontend/src/
  App.tsx
  main.tsx
  api.ts
  theme/
    antdTheme.ts
  components/
    shell/
      AppShell.tsx
      PageHeader.tsx
    data/
      AppTable.tsx
      StatusTag.tsx
      QueryState.tsx
    forms/
      AppFormSection.tsx
    feedback/
      AppModal.tsx
      notify.ts
  pages/
    dashboard/
    repair/
    warehouse/
    finance/
```

第一阶段不强制完成完整拆分，但每次替换 Ant Design 组件时，优先进入项目级组件层，而不是在业务页面里散落直接使用。

## 4. 阶段 0：基线冻结与验收准备

目的：确认引入 Ant Design 前的当前行为，避免改造过程中“看起来好了，业务坏了”。

任务：

1. 记录当前可运行入口：`.\start_project.ps1 start` 或前后端独立启动。
2. 运行后端测试：`pytest mis_mvp/tests --basetemp .runtime/pytest-tmp`。
3. 运行前端测试：`cd frontend; npm.cmd run test`。
4. 运行前端构建：`cd frontend; npm.cmd run build`。
5. 抽查核心页面：登录、首页、维修工单池、工单详情、库存、财务、系统设置。

交付物：

- 基线测试结果记录。
- 改造前关键页面截图。
- 当前未提交变更清单，避免把无关变更混入 UI 改造。

验收标准：

- 现有测试能跑通，或明确记录已有失败项。
- 明确哪些页面属于第一轮 Ant Design 改造范围。

## 5. 阶段 1：安装依赖但不替换页面

目的：让项目可以加载 Ant Design 6，但 UI 行为保持不变。

任务：

1. 安装依赖：`antd`。
2. 保留 `lucide-react`，不切换到 Ant Design Icons。
3. 确认 React 18 与 Ant Design 6 版本兼容。
4. 增加最小 import 验证，避免“只安装未使用”导致构建没有覆盖 Ant Design 打包路径。
5. 构建验证 Vite 能正确打包 Ant Design 6。

建议命令：

```powershell
cd frontend
npm.cmd install antd
npm.cmd run build
npm.cmd run test
```

交付物：

- `frontend/package.json` 增加 `antd`。
- `frontend/package-lock.json` 更新。
- 一个临时或测试用 Ant Design import 探针，例如 `Button` 渲染测试；进入阶段 2 后可由 `ConfigProvider` 真实接入替代。
- 构建产物仍输出到 `mis_mvp/frontend_dist/`。

验收标准：

- 不改业务页面组件的情况下，`npm.cmd run build` 通过。
- 构建中确实解析了 `antd` import，而不是只验证 package-lock。
- 应用启动后现有页面无明显样式变化。

## 6. 阶段 2：接入 ConfigProvider 与主题 token

目的：建立 Ant Design 6 主题入口，但不让它破坏现有样式。

任务：

1. 新建 `frontend/src/theme/antdTheme.ts`。
2. 在 `frontend/src/main.tsx` 外层接入 `ConfigProvider`。
3. 在 `ConfigProvider` 内接入 Ant Design 的 `App` 组件，用于承载 `message`、`notification`、`modal` 上下文。
4. 配置 `locale` 为中文，日期组件迁移前同步确认 dayjs locale。
5. 配置 `theme.token`，保持当前 MIS 视觉基调。
6. 不启用大面积 reset，先观察和现有 CSS 的共存情况；如后续需要 reset，必须先确认不会覆盖旧页面。

建议主题：

```ts
export const antdTheme = {
  token: {
    colorPrimary: "#003d9b",
    colorSuccess: "#16a34a",
    colorWarning: "#d97706",
    colorError: "#dc2626",
    colorText: "#1e293b",
    colorTextSecondary: "#64748b",
    colorBorder: "#e2e8f0",
    colorBgLayout: "#f8fafc",
    borderRadius: 8,
    fontFamily: 'Inter, "Microsoft YaHei", "Segoe UI", system-ui, sans-serif',
  },
  components: {
    Button: { controlHeight: 38 },
    Input: { controlHeight: 38 },
    Select: { controlHeight: 38 },
    Table: {
      cellPaddingBlock: 10,
      cellPaddingInline: 14,
      headerBg: "#f1f5f9",
    },
    Card: { borderRadiusLG: 8 },
    Tag: { borderRadiusSM: 6 },
  },
};
```

交付物：

- `theme/antdTheme.ts`
- `main.tsx` 接入 `ConfigProvider`
- `main.tsx` 接入 Ant Design `App` 上下文
- 如进入日期组件迁移，补充 `dayjs/locale/zh-cn` 的统一入口

验收标准：

- 未使用 Ant Design 组件的页面视觉不发生明显变化。
- 新增一个临时隐藏验证组件时，Ant Design 主题色与现有主色一致。
- `message`、`notification` 或 `modal` 的调用经过项目级封装，能继承主题和 locale。

## 7. 阶段 3：全局 CSS 兼容改造

目的：先让 Ant Design 组件不被现有全局选择器误伤。

当前高风险选择器：

```css
button { ... }
button:hover { ... }
input, select, textarea { ... }
table { ... }
th, td { ... }
```

改造策略：

1. 将全局控件样式收敛到项目旧组件作用域，例如 `.legacy-ui button`、`.legacy-ui input`、`.legacy-ui table`。
2. 不把 `.legacy-ui` 简单套在整个 `App` 根节点上；应只包裹尚未迁移的旧组件或旧页面区域。
3. 对未来 Ant Design 页面使用干净容器，不继承 `.legacy-ui`；必要时用 `.antd-ui` 做局部布局标记，但不要给 Ant Design 内部 DOM 写强覆盖样式。
4. 保留 CSS 变量 `--accent`、`--line`、`--surface` 等，作为项目 token 的来源。
5. 不一次性删除旧 CSS，先改选择器作用域。

建议顺序：

1. 把 `button/input/select/textarea/table/th/td` 改为 `.legacy-ui :where(button)` 等低权重选择器。
2. 给旧版 `Panel`、`DataTable`、`SimpleForm` 或旧页面外层补 `.legacy-ui`，而不是给整个应用补。
3. 验证当前页面视觉是否保持。
4. 新增 Ant Design `Button`、`Input`、`Table` 的小型测试区域，确认不受旧规则影响。

交付物：

- `styles.css` 全局控件选择器降权或作用域化。
- 根容器增加兼容 class。

验收标准：

- 旧页面视觉保持。
- Ant Design `Button` 不继承旧 `button` 背景、边框、字体权重。
- Ant Design `Table` 不被旧 `table/th/td` 样式破坏。
- 新旧组件同屏时，旧组件样式不泄漏到新组件，新组件样式不需要依赖 `!important` 修补。

## 8. 阶段 4：建立项目级 Ant Design 适配组件

目的：避免业务页面直接依赖大量 Ant Design API，为以后换主题、调密度、处理中文格式留出统一入口。

优先组件：

| 组件 | 职责 | Ant Design 基础 |
| --- | --- | --- |
| `AppButton` | 统一按钮尺寸、危险态、图标间距 | `Button` |
| `StatusTag` | 工单、付款、库存等状态色映射 | `Tag` |
| `QueryState` | 加载、空态、错误态 | `Spin`、`Empty`、`Result` |
| `AppModal` | 替代自研 modal，统一 footer | `Modal` |
| `notify` | 统一成功、失败、警告提示，并承接 Ant Design `App` 上下文 | `message`、`notification` |
| `AppTable` | 统一列、空态、滚动、分页、状态渲染 | `Table` |
| `AppFormSection` | 表单区块和字段布局 | `Form`、`Input`、`Select` |

第一批建议先做：

1. `StatusTag`
2. `QueryState`
3. `AppButton`

原因：风险低、覆盖广、能快速验证主题和 CSS 兼容。

交付物：

- `frontend/src/components/data/StatusTag.tsx`
- `frontend/src/components/data/QueryState.tsx`
- `frontend/src/components/actions/AppButton.tsx`
- `frontend/src/components/feedback/notify.ts` 或等价的通知封装设计

验收标准：

- 这些组件有最小单元测试或渲染测试。
- 业务页面可以同时使用旧组件和新组件。
- 业务代码不直接散落调用 `message.success`、`Modal.confirm`，优先通过项目封装进入。

## 9. 阶段 5：低风险替换

目的：在不改变数据结构和页面布局的前提下使用 Ant Design。

推荐替换顺序：

1. Toast：自研 `.toast` 替换为项目级 `notify`，内部使用 `message` 或 `notification`。
2. Modal：自研 `.modal` 替换为 `Modal`。
3. Badge：`.badge` 替换为 `StatusTag`。
4. Button：关键操作按钮替换为 `AppButton`。
5. Empty/Loading/Error：`QueryState` 替换为 Ant Design 反馈组件。

不建议此阶段替换：

- 复杂表单。
- 所有表格。
- 主导航布局。

验收标准：

- 替换后业务 API 调用不变。
- 原有按钮点击、弹窗关闭、提示消息行为不变。
- 移动端布局没有明显退化。

## 10. 阶段 6：表格迁移

目的：把高频数据密集区迁移到 Ant Design `Table`，提升排序、分页、滚动、空态和列配置能力。

优先页面：

1. 维修工单池。
2. 库存管理。
3. 财务流水。
4. 审计日志。

迁移方式：

1. 保留现有 API 返回结构。
2. 将当前 `columns: Array<[string, string]>` 适配为 Ant Design `ColumnsType`。
3. 将 `badgeClass` 与状态字段统一交给 `StatusTag`。
4. 使用 `scroll={{ x: "max-content" }}` 保护宽表。
5. 使用 `rowKey` 替代当前手写 key 推断。
6. 表格排序先保留前端排序，后续再考虑服务端排序。

验收标准：

- 表格列不丢失。
- 排序行为与旧版一致或更明确。
- 空数据展示清晰。
- 宽表横向滚动正常。
- 行点击打开详情功能不回归。

## 11. 阶段 7：表单迁移

目的：统一复杂表单校验、必填提示、联动选择和提交反馈。

优先页面：

1. 维修开单/工单详情编辑。
2. 设备型号管理。
3. 故障代码维护。
4. 采购/入库、领料发放。
5. 财务流水登记。

迁移方式：

1. 先封装 `AppFormSection`，不直接在页面里散用复杂布局。
2. 将 `formPayload(event.currentTarget)` 逐步替换为 Ant Design `Form` 的 `onFinish`。
3. 必填、数字、金额、手机号等规则统一在字段配置中表达。
4. 保留提交 payload 结构，避免影响后端。
5. 表单默认值、编辑态、只读态统一处理。
6. 涉及日期、时间、金额输入时，先固定业务格式，再替换为 `DatePicker`、`InputNumber` 等组件。

验收标准：

- 提交 payload 与旧实现一致。
- 必填和金额校验清楚。
- 编辑、取消、保存状态不回归。
- 测试覆盖至少包含一个成功提交和一个校验失败。
- 日期、时间、金额字段的展示格式和提交格式均有明确测试或人工验收记录。

## 12. 阶段 8：布局迁移

目的：统一主框架、页面标题、筛选区、操作栏和卡片区。

建议最后做布局迁移，因为布局影响最大。

候选 Ant Design 组件：

- `Layout`
- `Menu`
- `Card`
- `Tabs`
- `Breadcrumb`
- `Space`
- `Flex`
- `Grid`

迁移顺序：

1. 页面局部操作栏。
2. 筛选区。
3. 页面标题区。
4. 侧边栏和顶栏。
5. 首页指标卡片。

验收标准：

- 桌面端信息密度不下降。
- 900px 以下响应式仍可使用。
- 侧边栏、顶部搜索、用户信息不重叠。
- 不引入营销化大卡片风格。

## 13. 测试与质量门槛

每个阶段至少执行：

```powershell
cd frontend
npm.cmd run test
npm.cmd run build
```

涉及后端联调或构建产物服务时执行：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pytest mis_mvp\tests --basetemp .runtime\pytest-tmp
```

建议增加的前端测试：

- `StatusTag` 状态映射测试。
- `AppTable` 列渲染与行点击测试。
- `QueryState` 加载、错误、空态测试。
- 关键表单提交 payload 测试。

测试环境准备：

- 在 `frontend/src/testSetup.ts` 补齐 Ant Design 常用组件可能依赖的 `ResizeObserver`。
- 如组件测试涉及响应式、下拉、弹层，补齐 `window.matchMedia`。
- 如测试 Modal、Dropdown、Select，需要确认 portal 渲染容器和清理逻辑。
- 对依赖动画或定时器的反馈组件，测试中使用可控 timer，避免偶发失败。

视觉验收：

- 登录页。
- 首页。
- 维修工单池。
- 工单详情。
- 库存管理。
- 财务流水。
- 系统设置。

## 14. 推荐里程碑

| 里程碑 | 内容 | 预计耗时 | 结果 |
| --- | --- | ---: | --- |
| M1 | 安装 Ant Design 6，接入 `ConfigProvider` 和主题 | 0.5-1 天 | 项目可加载 Ant Design，不影响旧页面 |
| M2 | 全局 CSS 作用域化，建立兼容层 | 1-2 天 | Ant Design 组件不被旧样式污染 |
| M3 | 新建项目级适配组件 | 1-2 天 | 低风险组件可在业务中使用 |
| M4 | 替换反馈、弹窗、状态标签、按钮 | 2-3 天 | UI 基础件开始使用 Ant Design |
| M5 | 迁移高频表格 | 2-4 天 | 工单池、库存、财务列表体验提升 |
| M6 | 迁移复杂表单 | 3-5 天 | 表单校验和提交体验统一 |
| M7 | 迁移布局与页面结构 | 3-5 天 | 整体视觉统一为 Ant Design 主题体系 |

## 15. 风险与应对

| 风险 | 表现 | 应对 |
| --- | --- | --- |
| 全局 CSS 污染 Ant Design | 按钮、表格、输入框样式异常 | 阶段 3 先做选择器作用域化 |
| `.legacy-ui` 范围过大 | 新组件仍被旧样式污染 | 只包旧组件或旧页面区域，不包整个应用 |
| 一次性改动过大 | 难定位回归 | 每阶段只替换一个组件族 |
| Ant Design 默认感太强 | 系统像通用模板 | 通过 `Muchen MIS Compact` token 和项目级组件控制 |
| 反馈组件拿不到主题上下文 | message/modal 视觉和 locale 不一致 | 使用 Ant Design `App` 上下文和项目级 `notify` 封装 |
| jsdom 缺少浏览器 API | 前端测试报 `ResizeObserver` 或 `matchMedia` 错误 | 在 `testSetup.ts` 统一 polyfill |
| 表格行为回归 | 排序、点击、状态标签异常 | 先做 `AppTable`，逐页迁移 |
| 表单 payload 改变 | 后端接口报错 | 表单迁移必须对比旧 payload |
| 日期与金额格式漂移 | 后端收到格式变化或页面中英文混排 | 先定义格式契约，再迁移 DatePicker/InputNumber |
| 构建产物路径变化 | FastAPI 无法服务前端 | 保持 Vite `outDir` 和现有部署方式 |

## 16. 第一轮建议执行清单

第一轮只做兼容，不做大面积 UI 替换：

1. 安装 `antd`。
2. 新建 `frontend/src/theme/antdTheme.ts`。
3. 在 `main.tsx` 接入 `ConfigProvider`、Ant Design `App` 与中文 locale。
4. 在 `testSetup.ts` 补齐 `ResizeObserver`、`matchMedia` 等基础 polyfill。
5. 将 `styles.css` 的裸 `button/input/select/textarea/table/th/td` 选择器作用域化，且 `.legacy-ui` 只包旧组件区域。
6. 新建 `StatusTag`、`QueryState` 和 `notify` 适配组件。
7. 在一个低风险页面局部试用 `StatusTag`。
8. 运行前端测试、构建和关键页面人工验收。

第一轮完成后再进入第二轮：Modal、Toast、Button、Table。

## 17. 完成定义

当以下条件全部满足时，可以认为“兼容 Ant Design 6”阶段完成：

- `antd` 已安装并能通过 Vite 构建。
- `ConfigProvider` 和项目主题已接入。
- Ant Design `App` 上下文或等价反馈封装已接入。
- 现有全局 CSS 不再污染 Ant Design 基础组件。
- 前端测试环境已补齐 Ant Design 常用组件所需的基础 polyfill。
- 至少有一个项目级 Ant Design 适配组件在业务页面中运行。
- 原有核心页面仍可访问，关键交互不回归。
- `npm.cmd run build` 通过。

当以下条件全部满足时，可以认为“使用 Ant Design 6 UI 组件库”阶段完成第一期：

- 状态标签、反馈、弹窗、按钮已迁移到 Ant Design 或项目级适配组件。
- 至少一个高频表格页面完成 Ant Design Table 迁移。
- 至少一个复杂表单完成 Ant Design Form 迁移。
- 主题视觉保持 `Muchen MIS Compact`，没有明显默认模板感。

## 18. 推荐结论

建议按“兼容层优先”的路线推进。第一轮不要重写页面，也不要急着替换所有表格和表单；先让 Ant Design 6 在项目中安全共存。等依赖、主题、CSS 隔离和项目级适配组件稳定后，再从状态标签、反馈组件、弹窗、按钮这些低风险区域开始使用，最后迁移表格、表单和布局。

这条路线能最大限度保护现有维修、库存、财务等业务流程，同时为后续 UI 统一和组件化拆分打开空间。
