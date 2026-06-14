# 当前业务流说明

本文档以当前 `mis_mvp` 实现为准，说明维修、会员、物料库存、回收销售和财务的业务流。所有新业务优先围绕 `machines.machine_id` 展开。

## 1. 总体业务对象

- `machines`：机器生命周期主表。
- `customers`：会员和客户主数据。
- `repair_orders`：维修工单主表。
- `materials` 和相关库存表：维修配件库存。
- `recycle_orders`、`inventory_items`、`sales_orders`：回收机器和销售。
- `payments`、`receivables`：收支和应收。
- `machine_events`、`operation_logs`：生命周期和审计。

旧 `devices/repairs` 是兼容层，不作为新业务培训和开发主线。

## 2. 角色分工

| 角色 | 主要职责 |
| --- | --- |
| 前台 | 接待、开单、查单、补客户资料、指派工程师、沟通报价、交付和登记收款 |
| 工程师 | 检测、维修方案、维修项目、物料申领、维修完成、工程师结单 |
| 仓库/管理员 | 物料建档、入库、审批、发放、退料验收、盘点和调整 |
| 财务 | 付款流水、结账、挂账核对、报表和审计 |
| 老板/管理员 | 全局查看、异常处理、权限兜底、基础资料和经营报表 |

## 3. 维修工单流

当前可落地流程：

```text
新建维修工单
-> 指派工程师
-> 开始检测
-> 检测报价
-> 客户确认报价
-> 维修处理中
-> 添加维修项目/物料
-> 工程师结单
-> 交付
-> 登记收款或挂账
-> 财务确认/结账
-> 完结
```

### 3.1 开单

入口：

- 前端“维修工单池”的新建订单。
- 后端 `POST /api/repair-orders`。

系统动作：

- 创建或复用客户。
- 创建或复用机器。
- 创建维修工单，初始状态 `已开单`。
- 机器状态进入 `检测中`，来源为 `维修`。
- 如果开单人是工程师，可直接指派到该工程师。
- 写入机器时间线和操作审计。

允许资料不完整，但必须能关联机器。无 IMEI 设备使用 `TMP-` 临时编号，后续补全。

### 3.2 指派与可见性

接口：`POST /api/repair-orders/{id}/assign`

- 前台、老板、管理员可指派。
- 工程师只看到指派给自己的维修范围。
- 改派应记录备注和审计。

### 3.3 检测和报价

接口：

- `POST /api/repair-orders/{id}/inspections`
- `POST /api/repair-orders/{id}/quote`
- `GET/POST /api/repair-skus`
- `GET /api/repair-orders/{id}/material-hints`

规则：

- 客户口述故障、工程师检测结论、维修方案要分开。
- SKU 可提供故障、方案、成本、收费和推荐物料。
- 报价后工单进入 `已报价`，机器状态同步为 `已报价`。
- 人工改价必须记录原因。

### 3.4 客户确认

接口：`POST /api/repair-orders/{id}/confirm-quote`

记录确认结果、沟通方式、联系人和备注。客户拒修或误开单应走作废/取消，不应静默删除。

### 3.5 维修、物料和工程师结单

接口：

- `POST /api/repair-orders/{id}/items`
- `POST /api/material-requests`
- `POST /api/material-requests/{id}/approve`
- `POST /api/material-requests/{id}/issue`
- `POST /api/repair-orders/{id}/engineer-close`

规则：

- 维修项目记录成本和收费。
- 物料申领不扣库存；仓库发放具体单件码才扣库存。
- 临采物料应先入库，再绑定维修消耗。
- 工程师结单表示技术处理完成，不等于订单完结。

### 3.6 交付和收款

接口：

- `POST /api/repair-orders/{id}/deliver`
- `POST /api/payments`

规则：

- 客户取机或送回只代表交付完成，不等于已收款。
- 前台收款只代表已登记流水，不等于财务确认到账。
- 同行挂账进入应收口径，不计入当日已收款。
- 财务确认、结账和完结应保留可追溯流水。

## 4. 工单详情资料

工单详情页目前支持：

- 机器资料编辑。
- 客户资料查询和复用。
- 维修项目增补。
- 检测项保存。
- 阶段照片上传。
- 结构化备注编辑和删除。
- 作废工单。
- 工作流动作推进。
- 机器时间线查看。

开发时要保持资料修改、状态推进和审计事件一致，不要只更新前端展示字段。

## 5. 会员管理流

入口：前端“会员管理”。

接口：

- `GET /api/customers`
- `POST /api/customers`
- `GET /api/customers/{id}`
- `PUT /api/customers/{id}`
- `POST /api/customers/{id}/interactions`
- `PUT /api/customer-interactions/{id}`

业务规则：

- 会员编号、姓名、手机号、微信、客户类型、店铺、标签、等级、折扣和状态都属于客户主数据。
- 维修、回收、销售和结账应尽量绑定 `customer_id`。
- 客户互动记录用于备注、回访和待办，不覆盖客户主档。
- 同行客户和商家客户要保留店铺/柜台线索，方便挂账和对账。

## 6. 维修物料库存流

### 6.1 基础资料

先建：

- 物料类别
- 库区
- 库位
- 物料档案

物料档案包含 SKU、物料编码、适配范围、单位、低库存阈值、是否单件追踪、默认库位和成本。

### 6.2 入库

接口：

- `POST /api/material-batches/purchase`
- `POST /api/material-batches/ad-hoc`

系统动作：

- 生成批次。
- 生成单件码。
- 更新可用库存。
- 写入 `stock_movements`。

### 6.3 申领、审批、发放

接口：

- `POST /api/material-requests`
- `POST /api/material-requests/{id}/approve`
- `POST /api/material-requests/{id}/reject`
- `POST /api/material-requests/{id}/issue`
- `POST /api/material-requests/{id}/cancel`

规则：

- 工程师发起申领。
- 审批通过不扣库存。
- 仓库发放单件码时扣库存。
- 发放后物料可绑定维修工单成本。

### 6.4 退料、退货、盘点

接口：

- `POST /api/material-issues/{unit_id}/return-request`
- `POST /api/material-returns/{id}/inspect`
- `POST /api/material-batches/{id}/return`
- `POST /api/stock-counts`
- `POST /api/stock-counts/{id}/confirm`
- `POST /api/stock-adjustments`
- `GET /api/stock-movements`

规则：

- 退料要验收，区分可复用、损坏、待检等结果。
- 已使用或报损物料不能直接采购退货。
- 盘点确认后通过调整和流水反映差异。

## 7. 回收、库存和销售流

回收：

```text
创建回收单 -> 验机报价 -> 改价可选 -> 付款入库 -> 回收库存
```

主要接口：

- `POST /api/recycle-orders`
- `POST /api/recycle-orders/{id}/quote`
- `POST /api/recycle-orders/{id}/price`
- `POST /api/recycle-orders/{id}/stock-in`

销售：

```text
库存机器 -> 创建销售单 -> 机器已售出 -> 登记销售收入
```

主要接口：

- `GET /api/inventory`
- `POST /api/sales-orders`

## 8. 财务和报表

接口：

- `GET/POST /api/payments`
- `GET /api/machine-reports`
- `GET /api/reports`
- `POST /api/settlements`

财务状态口径：

- 未收款：业务已发生但无收款。
- 已付款待财务确认：前台或业务人员已登记，财务未核对。
- 财务已确认：可进入结账/完结口径。
- 同行挂账：客户已取机或交付，但按客户/柜台进入应收。
- 预付款已收：交付时需要核销，避免重复收款。
- 无需收款：保修、内部处理或特殊减免。

报表必须能追溯明细，不做只看汇总的黑盒数字。

## 9. 审计和时间线

机器生命周期事件写入 `machine_events`。系统操作审计写入 `operation_logs`。

必须记录的动作：

- 开单、指派、检测、报价、确认、改价、维修项目、工程师结单、交付、收款、作废。
- 机器资料修改和删除。
- 物料入库、发放、退料、退货、盘点、调整。
- 客户资料新增、编辑和互动记录。
- 财务流水和结账。

## 10. 真实业务口径

结构化数据库是订单事实源。以下文档是业务规则和样本来源：

- `BUSINESS_REALITY_LOG.md`
- `MATERIAL_INVENTORY_LOG.md`
- `BUSINESS_TIMELINE_SUMMARY.md`
- `CODEX_LOCAL_NOTES.md`

当 Markdown 观察文档和 SQLite 记录不一致时，以数据库为订单事实，Markdown 用于解释为什么这么设计、哪些字段待补、哪些规则待确认。
