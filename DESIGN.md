# 沐辰科技 MIS 当前设计说明

本文档描述当前项目真实实现状态，用于后续开发、测试和交接。当前主线不是旧 PWA，也不是纯静态页，而是：

```text
FastAPI + SQLite + Vite React + TypeScript + TanStack Query + Ant Design 适配层
```

## 1. 架构边界

```text
frontend/                 React 前端源码
  src/App.tsx             当前页面与业务交互主入口
  src/api.ts              fetch 封装，自动写入 X-User
  src/components/         项目级 Ant Design 适配组件
  src/theme/antdTheme.ts  主题 token
mis_mvp/
  backend/app.py          FastAPI 路由和静态资源托管
  backend/auth.py         角色权限矩阵
  backend/config.py       数据库和运行配置
  backend/db.py           SQLite 建表、迁移、默认数据
  backend/models.py       Pydantic 输入模型和枚举
  backend/repository.py   SQL 数据访问
  backend/service.py      业务规则、状态流转和审计
  frontend_dist/          React build 输出
  static/                 历史静态前端回退
  tests/                  后端业务测试
```

FastAPI 根路径 `/` 的服务顺序：

1. 若 `mis_mvp/frontend_dist/index.html` 存在，返回 React 构建产物。
2. 否则返回 `mis_mvp/static/index.html`。

数据库默认路径：

```text
mis_mvp/data/mis_mvp.sqlite3
```

`MIS_DATABASE_PATH` 可覆盖数据库路径，但只建议用于测试、迁移或临时验证。真实业务运行库以固定路径为准。

## 2. 领域主线

### 2.1 机器生命周期

新业务统一以 `machines.machine_id` 为核心。维修、回收、库存、销售、付款和时间线都应能追溯到机器。

关键规则：

- IMEI 非空时唯一。
- 无 IMEI 的机器允许先建档，系统生成 `TMP-` 编号。
- 机器创建写入 `machine_events`。
- 编辑机器、开维修单、检测报价、交付、付款、回收入库和销售都应补充时间线。

机器状态枚举来自 `MachineStatus`：

```text
到店、检测中、已报价、维修中、待交付、已交付、已回收、回收库存、待销售、已售出、已结单
```

### 2.2 维修工单

维修是当前最完整的业务闭环。

核心表：

- `repair_orders`：工单主表，保存订单号、机器、客户、状态、指派、报价、交付、付款和完结字段。
- `repair_items`：维修项目、成本、收费和 SKU 关联。
- `repair_order_inspections`：开单或维修过程检测项。
- `repair_order_photos`：按阶段上传的照片。
- `repair_order_notes`：结构化备注。
- `repair_skus`：常见故障、维修方案、成本和收费。
- `repair_fault_materials`：维修 SKU 与推荐物料映射。

工单状态枚举来自 `OrderStatus`：

```text
已开单、检测中、已报价、处理中、待交付、已交付、已入库、已售出、已结单、已作废
```

维修流转由 `MisService` 控制。开发时优先调用专用方法或 `/workflow-action`，避免在前端直接猜状态。

### 2.3 会员客户

客户主数据在 `customers`：

- 支持会员号、姓名、电话、微信、客户类别、店铺名、地址、标签、会员等级、折扣策略、来源、生日、状态和备注。
- `customer_interactions` 保存回访、备注、待办和完成状态。
- 开单可以复用 `customer_id`，也可以提交 `customer` 创建或更新客户。

后续涉及结账、挂账、同行客户、商家折扣的功能，应优先绑定稳定 `customer_id`，不要只依赖客户姓名字符串。

### 2.4 维修物料库存

物料库存已从回收机器库存独立出来。

核心表：

- 基础资料：`material_categories`、`warehouse_areas`、`warehouse_locations`、`materials`
- 入库与单件码：`material_batches`、`material_units`
- 申领发放：`material_requests`、`material_request_items`
- 退料：`material_returns`
- 维修绑定：`repair_materials`
- 库存流水：`stock_movements`
- 盘点调整：`stock_counts`、`stock_count_items`、`stock_adjustments`

库存规则：

- 库存数量由单件状态和库存流水共同维护。
- 采购/临采入库生成批次和单件码。
- 申领和审批不扣库存，发放单件码时扣库存。
- 退料必须经过仓库验收。
- 盘点和调整要写入流水，不应硬改数量。

### 2.5 回收、销售和财务

回收销售沿用机器主线：

- `recycle_orders`：回收开单、验机报价、改价、付款入库。
- `inventory_items`：回收机器库存。
- `sales_orders`：销售出库。
- `payments`：维修收入、销售收入、回收支出。
- `receivables`：同行挂账和应收扩展口径。

财务设计原则：

- 报价金额、应收金额、实收金额、付款状态、财务确认状态要分开。
- 同行挂账不计入当日已收款。
- 前台已收款不等于财务已确认。
- 退款、冲正和销售退货后续应通过反向流水扩展，不直接覆盖历史流水。

### 2.6 旧兼容模型

`devices`、`repairs`、`settlements`、`settlement_items` 保留旧 MVP 能力和测试覆盖：

- `POST /api/purchases`
- `GET /api/stock`
- `POST /api/sales`
- `POST /api/repairs`
- `GET /api/repairs`
- `POST /api/settlements`
- `GET /api/reports`

新功能不要继续扩大这些表的职责，除非是在做历史兼容或迁移。

## 3. API 分层

路由集中在 `backend/app.py`，业务规则集中在 `MisService`。

主要接口组：

- 登录：`POST /api/login`、`GET /api/me`
- 机器：`POST /api/machines`、`GET /api/machines`、`PUT /api/machines/{id}`、`DELETE /api/machines/{id}`、`GET /api/machines/{id}/timeline`
- 维修工作台：`POST /api/repair-orders`、`GET /api/repair-workbench`、`GET /api/repair-workbench/{id}`
- 维修动作：指派、报价、客户确认、改价、加项目、状态变更、备注、工程师结单、交付、照片、检测记录、工作流动作
- 基础资料：`GET/POST /api/device-models`、`GET/POST /api/repair-skus`
- 仓库：物料类别、库区库位、物料、批次、单件码、申领、审批、发放、退料、盘点、调整、流水
- 会员：客户列表、详情、新增、编辑、互动记录
- 回收销售财务：回收单、回收入库、库存、销售单、付款流水、机器报表
- 审计：`GET /api/audit-logs`

错误处理：

- `BusinessError` 返回 HTTP 400。
- `PermissionError` 返回 HTTP 403。
- 当前用户由 `X-User` 请求头传入；未传时默认 `admin`，这是本地原型机制，不是生产认证方案。

## 4. 权限模型

角色枚举：

```text
admin、boss、frontdesk、engineer、staff、finance
```

权限矩阵在 `backend/auth.py`。

重点边界：

- 管理员和老板拥有全局业务、基础资料、仓库、财务、报表和审计权限。
- 前台可开单、查看和调度维修、维护客户、登记部分业务流水。
- 工程师可创建维修单、查看机器和指派给自己的维修订单、补充检测/维修信息、提交物料申领。
- 财务可读业务、登记付款、做结账、看报表和审计。
- 工程师读取维修工作台和机器时间线时会按指派范围收窄。

## 5. 前端设计

当前前端在 `frontend/src/App.tsx` 中仍较集中，但已经接入：

- React 18
- Vite
- TypeScript
- TanStack Query
- Ant Design 6
- lucide-react
- 项目级组件：`AppButton`、`AppTable`、`StatusTag`、`QueryState`、`AppModal`、`AppFormSection`
- 主题：`frontend/src/theme/antdTheme.ts`
- Ant Design 上下文：`ConfigProvider`、`App`、`AntdFeedbackBridge`

主要页面：

- 个人工作台
- 维修工单池
- 工单详情/新建/编辑/作废
- 回收工单池
- 维修开单
- 回收开单
- 库存管理
- 回收库存
- 快速卖机
- 会员管理
- 财务流水
- 财务报表
- 系统设置/审计

前端开发原则：

- API 调用统一走 `api()`，保持 `X-User` 行为一致。
- 新 UI 优先用项目级 Ant Design 适配组件，不在业务页散落直接定制 Ant 内部 DOM。
- 逐步拆分 `App.tsx`，优先按业务域拆：维修、会员、库存、财务、系统设置。
- 旧静态前端只作为回退，不继续作为新功能主线。

## 6. 数据迁移

迁移脚本：

- `mis_mvp/tools/import_legacy_mvp.py`
- `mis_mvp/tools/import_workflow_sqlite.py`

迁移原则：

- 迁移前备份目标 SQLite。
- 使用 `order_no`、`sku`、`batch_no`、`source_key` 等字段保证幂等。
- 不覆盖人工补录和已确认字段。
- 真实业务订单事实落到结构化表，Markdown 只保存业务观察、规则来源和待确认口径。

## 7. 测试策略

后端测试目录：`mis_mvp/tests`

覆盖重点：

- 登录和权限矩阵
- 旧 purchase/stock/sale/settlement 兼容流程
- 机器唯一性、临时编号、编辑时间线、追加备注、删除权限
- 维修生命周期、工单池、工程师指派与可见性、禁止跳转、作废保护
- 回收、库存、销售、付款时间线
- 物料批次、单件码、申领、发放、退料、盘点
- 会员 CRM 和互动记录
- 照片上传、检测记录、基础资料

前端测试目录：`frontend/src`

覆盖重点：

- API 封装
- 项目级 Ant Design 适配组件

## 8. 开发注意事项

- 新业务写入前先判断是否应落到机器主线。
- 不直接绕过 `MisService` 写业务状态。
- 涉及财务、库存、交付、作废、删除的动作必须写审计。
- 不在文档或代码里写真实账号密码。
- 本地数据库和运行日志不提交。
- 若数据库结构变化，更新 `backend/db.py`、测试和本文档。
