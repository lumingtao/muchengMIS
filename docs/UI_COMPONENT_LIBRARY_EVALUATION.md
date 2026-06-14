# UI 组件库选型与当前结论

评估对象：沐辰科技 MIS React 前端  
当前状态：已采用 Ant Design 6，并保留 lucide-react 图标库。

## 1. 当前技术栈

```text
React 18
Vite 5
TypeScript
TanStack Query 5
Ant Design 6
lucide-react
自研业务 CSS + 项目级 Ant Design 适配组件
```

FastAPI 托管 `mis_mvp/frontend_dist/`；该目录由前端构建生成，缺失时返回构建提示。

## 2. 结论

主 UI 库：Ant Design 6  
图标库：lucide-react  
主题策略：`Muchen MIS Compact`，通过 `frontend/src/theme/antdTheme.ts` 管理 token。  
迁移策略：项目级组件封装优先，页面逐步替换。

选择 Ant Design 的原因：

- 适合维修、库存、会员、财务这类高密度企业后台。
- 表格、表单、弹窗、反馈、选择器、上传、布局能力完整。
- 中文后台生态成熟。
- 不需要引入 Tailwind。
- 适合和当前 Vite + React + TypeScript 结构共存。

## 3. 已落地内容

已接入：

- `antd` 依赖。
- `ConfigProvider` 中文 locale。
- Ant Design `App` 上下文。
- `dayjs/locale/zh-cn`。
- `frontend/src/theme/antdTheme.ts`。
- `AntdFeedbackBridge`。
- 项目级组件：
  - `AppButton`
  - `AppTable`
  - `StatusTag`
  - `QueryState`
  - `AppModal`
  - `AppFormSection`

已覆盖测试：

- `frontend/src/api.test.ts`
- `frontend/src/components/data/AppTable.test.tsx`
- `frontend/src/components/data/StatusTag.test.tsx`
- `frontend/src/components/forms/AppFormSection.test.tsx`

## 4. 主题原则

```text
主色：深蓝
背景：浅灰页面 + 白色内容区
圆角：6-8px
表格：紧凑、高可读
状态色：成功绿、待处理黄、异常红、信息蓝、中性灰
```

设计重点：

- 不做营销页式大卡片和装饰渐变。
- 表格和表单密度优先。
- 状态、金额、客户、工单号、库存数量要易扫读。
- 旧 CSS 逐步收敛作用域，避免污染 Ant Design 内部 DOM。

## 5. 备选方案结论

| 方案 | 结论 |
| --- | --- |
| Arco Design | 可作为 Ant Design 的强备选，但当前无需切换 |
| Semi Design | 组件完整，但视觉体系更强，迁移收益不如继续推进 Ant Design |
| MUI | 成熟，但 Material 风格与本土 MIS 不完全贴合 |
| Mantine | 开发体验好，但业务后台表格生态不如 Ant Design |
| shadcn/ui | 可控性高，但会引入 Tailwind 和组件复制维护 |
| DaisyUI/HeroUI/Flowbite | 更偏 Tailwind 生态，不适合作为当前主库 |
| Tremor | 可局部用于报表，不适合作为完整 MIS 主库 |

## 6. 后续建议

优先顺序：

1. 继续把 `App.tsx` 中的表格、按钮、状态、弹窗统一到项目级组件。
2. 按业务域拆页面：维修、会员、库存、财务、系统设置。
3. 将高频表单逐步迁移到 Ant Design Form。
4. 收敛全局 CSS 选择器，避免直接影响 `button/input/table`。
5. 对维修工单池、会员列表、库存流水和财务流水增加表格分页、固定列和更稳定的筛选状态。

## 7. 维护约束

- 不在业务页面直接写大量 Ant Design 低层覆盖样式。
- 新状态标签统一走 `StatusTag`。
- 新数据表统一走 `AppTable`，需要特殊列时扩展项目组件能力。
- 新反馈提示统一走 `notify`，保持 Ant Design 上下文、主题和 locale。
- 引入新 UI 库前必须有明确不可由 Ant Design 解决的需求。
