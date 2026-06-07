# 沐辰科技二手机 MIS 管理系统设计说明

## 1. 项目定位

本项目是“沐辰科技二手机 MIS 管理系统”的本地私有化业务系统原型与维护主线。当前开发主线固定为 `mis_mvp`，以 FastAPI + SQLite + 原生静态前端实现，目标是把维修、回收、库存、销售、客户、财务与日志串成可追溯的机器生命周期工作台。

现阶段重点是维修业务闭环和配件仓库闭环：

- 维修闭环覆盖接单、检测、报价、客户确认、维修、领料、库存消耗、交付、收款、同行挂账、财务确认和订单完结。
- 配件仓库闭环覆盖物料档案、库区库位、采购/临采入库、批次与单件码、申领审核、发放、退料、退货、库存流水、盘点调整和维修故障物料绑定。
- 未知业务字段不得伪造，统一保留为“待补”或“待确认”。

## 2. 代码结构

```text
.
├── mis_mvp/                         # 当前运行主线
│   ├── backend/
│   │   ├── app.py                   # FastAPI 路由层
│   │   ├── auth.py                  # 用户、角色、权限
│   │   ├── config.py                # 配置和数据库路径
│   │   ├── db.py                    # SQLite 建表、迁移、种子用户
│   │   ├── models.py                # Pydantic 输入/输出模型
│   │   ├── repository.py            # 传统机器生命周期数据访问
│   │   └── service.py               # 核心业务服务与状态动作
│   ├── static/
│   │   ├── index.html               # 单页应用结构
│   │   ├── app.js                   # 前端状态、接口调用、渲染与交互
│   │   └── styles.css               # 页面样式
│   ├── tools/
│   │   ├── import_workflow_sqlite.py # 从真实工作流库迁移
│   │   ├── import_legacy_mvp.py      # 旧 MVP 数据导入
│   │   └── seed_demo_data.py         # 演示数据
│   └── tests/                       # API、业务流与机器生命周期测试
├── mis_pwa/data/mis_workflow.sqlite3 # 真实维修工作流迁移来源
├── BUSINESS_REALITY_LOG.md           # 典型真实业务观察，不再作为完整订单流水
├── MATERIAL_INVENTORY_LOG.md         # 典型物料采购、库存、领料观察，不再替代库存数据库
├── BUSINESS_TIMELINE_SUMMARY.md      # 业务复盘与系统改造依据
├── project_ctl.py                    # 命令式启动/重启/停止控制
├── project_launcher.py               # 图形化启动入口
└── 项目启动入口.vbs                  # 双击打开启动入口
```

## 3. 运行架构

系统采用三层结构：

- 前端：`mis_mvp/static/index.html` + `app.js` + `styles.css`，通过浏览器访问 `http://127.0.0.1:8088/`。
- 后端：`mis_mvp/backend/app.py` 使用 FastAPI 暴露 REST API，并挂载 `/static` 静态资源。
- 数据：SQLite 作为运行库，启动时由 `backend.db.migrate()` 自动补齐表结构。

固定数据库路径由 `mis_mvp/backend/config.py` 和启动入口共同指向：

```text
mis_mvp/data/mis_mvp.sqlite3
```

项目启动器仍支持手动选择数据库文件，但真实业务默认运行库固定为上面这个路径；临时目录数据库只作为历史迁移来源或本地测试备份，不再作为日常运行库。

## 4. 核心业务模块

### 4.1 维修闭环中心

维修业务主线由 `machines + repair_orders + repair_items + payments + machine_events` 承载，并扩展收入、成本、物料和应收结构。

核心表：

- `machines`：机器档案、机器编号、IMEI/序列号、机型、客户、当前状态、生命周期时间。
- `repair_orders`：维修工单，保存客户描述、检测结论、维修方案、报价、工程师、付款状态、交付与完结时间。
- `repair_items`：维修项目/SKU 项。
- `repair_income_items`：维修费、扩容款、客户自带配件安装费、预付款等收入拆分。
- `repair_cost_items`：库存物料、临采物料、回收配件、人工成本等成本拆分。
- `payments`：收付款流水，包含状态、账号、流水号、收款人、财务确认人和确认时间。
- `receivables`：同行挂账、未收款和应收记录。
- `machine_events`：机器生命周期事件时间线。

推荐维修状态：

```text
新建 -> 待检测 -> 待报价确认 -> 维修中 -> 待领料 -> 已领料 -> 维修完成 -> 待交付检测 -> 待取机/待送机/待返寄 -> 已交付 -> 财务待确认/同行挂账 -> 已完结
```

推荐收款状态：

```text
未收款、已付款待财务确认、财务已确认、同行挂账、预付款已收、无需收款
```

关键业务约束：

- 客户描述、工程师检测结论、维修方案必须分开记录。
- 技术维修完成不等于订单完结。
- 客户取机不等于已收款。
- 前台收款不等于财务已确认到账。
- 同行挂账不计入当日已收款，应进入 `receivables`。
- 状态流转优先使用专用动作接口，避免直接把“维修完成”跳成“已完结”。

### 4.2 配件仓库

配件仓库从“回收机器库存”独立出来，关注维修配件的采购、入库、领用、退料、退货、盘点和维修协同。

核心表：

- `material_categories`：物料类别。
- `warehouse_areas`：库区。
- `warehouse_locations`：库位。
- `materials`：物料档案，包含 `sku`、`material_code`、适配范围、低库存阈值和默认库位。
- `material_batches`：采购/临采入库批次。
- `material_units`：每一件物料的单件编码与状态。
- `material_requests` / `material_request_items`：工程师申领单与明细。
- `material_returns`：退料申请与仓库验收。
- `repair_materials`：维修工单绑定的物料消耗。
- `stock_movements`：所有库存变化流水。
- `stock_counts` / `stock_count_items`：盘点单。
- `stock_adjustments`：库存调整与反向冲销。
- `repair_fault_materials`：维修故障/SKU 与推荐物料绑定。

库存设计原则：

- 所有库存变化都通过 `stock_movements` 记录，不应绕过流水直接改数量。
- 入库生成批次和单件码，单件初始状态为在库可用。
- 工程师申请和审核不扣库存；仓库发放具体单件码时才扣库存。
- 已发放、已使用、报损物料不能直接采购退货。
- 工程师退料经仓库验收后，按可复用、已损坏、拆回待检等结果决定是否恢复可用库存。
- 盘点确认后不可硬删除，只能做反向调整。

### 4.3 回收、销售与财务

回收与销售模块继续沿用机器生命周期主线：

- `recycle_orders`：回收开单、验机报价和付款入库。
- `inventory_items`：回收机器库存和销售定价。
- `sales_orders`：销售出库。
- `payments`：维修收入、销售收入、回收支出以及后续退款/反向流水。

当前第一阶段不做销售退货主线大改，但设计上应保留销售退货入库和财务反向流水的扩展空间。

## 5. API 设计

后端 API 由 `mis_mvp/backend/app.py` 统一暴露，业务规则集中在 `MisService`。

主要接口组：

- 登录与用户：`POST /api/login`、`GET /api/me`
- 机器：`POST /api/machines`、`GET /api/machines`、`GET /api/machines/{id}/timeline`
- 维修：`POST /api/repair-orders`、`GET /api/repair-workbench`、`GET /api/repair-workbench/{id}`、`POST /api/repair-orders/{id}/workflow-action`
- 维修 SKU：`GET/POST /api/repair-skus`
- 仓库基础：`GET/POST /api/warehouse/areas`、`GET/POST /api/warehouse/locations`、`GET/POST /api/material-categories`、`GET/POST /api/materials`
- 入库退货：`POST /api/material-batches/purchase`、`POST /api/material-batches/ad-hoc`、`POST /api/material-batches/{id}/return`
- 申领发放退料：`POST /api/material-requests`、`GET /api/material-requests/mine`、`POST /api/material-requests/{id}/approve`、`POST /api/material-requests/{id}/issue`、`POST /api/material-issues/{id}/return-request`、`POST /api/material-returns/{id}/inspect`
- 盘点流水：`POST /api/stock-counts`、`POST /api/stock-counts/{id}/confirm`、`POST /api/stock-adjustments`、`GET /api/stock-movements`
- 故障物料提示：`GET/POST /api/repair-fault-materials`、`GET /api/repair-skus/{id}/material-hints`、`GET /api/repair-orders/{id}/material-hints`
- 客户、财务、报表、日志：`GET /api/customers`、`GET/POST /api/payments`、`GET /api/machine-reports`、`GET /api/audit-logs`

## 6. 前端设计

前端是一个无构建步骤的单页应用：

- 视图切换通过侧边栏 `data-view` 控制。
- 接口调用统一走 `api(path, options)`。
- 表格、徽章、弹窗、时间线等由 `app.js` 直接渲染。
- 页面模块包括维修订单池、回收订单池、配件仓库、回收库存、销售开单、客户、财务流水、报表、日志。

维修闭环中心：

- 顶部显示真实工单、未完结、财务待确认、同行挂账、待补资料等指标。
- 主表支持关键词、维修状态、收款状态、客户类型、待补资料和更新时间范围筛选。
- 主表展示工单号、维修状态、收款状态、客户、类型、柜台/同行、机型、建单时间、维修完成时间、订单完结时间、维修进度、工程师和更新时间。
- 主表表头支持排序，排序作用于当前筛选结果。

配件仓库：

- 页面入口包含物料类别、库区库位、物料档案、采购/临采入库、申领发放、退货/退料/盘点、维修故障物料绑定。
- 数据区展示物料档案与余量、单件库存状态、批次与退货、我的/全部申领、退料验收、库存流水。

## 7. 数据迁移与真实数据口径

日常真实订单录入口径：

- 维修订单、物料消耗、收款、挂账和交付状态以固定 SQLite 数据库 `mis_mvp/data/mis_mvp.sqlite3` 中的结构化数据为准。
- 启动器、`project_ctl.py` 和 `start_project.ps1` 默认都指向固定库；如临时指定其他 `MIS_DATABASE_PATH`，只能用于测试或迁移，不应作为真实业务录入库。
- 后续新增真实订单应优先写入数据库，至少落到 `machines`、`repair_orders`，涉及收费/挂账/物料时同步落到 `payments`、`receivables`、`repair_items`、`stock_movements` 等对应表。
- `BUSINESS_REALITY_LOG.md`、`MATERIAL_INVENTORY_LOG.md`、`BUSINESS_TIMELINE_SUMMARY.md` 只记录有典型特征、会改变业务理解或系统设计的样本，不再逐单充当完整业务台账。
- 当数据库记录和 Markdown 观察文档不一致时，以数据库为订单事实源；Markdown 只作为需求、规则和业务经验的解释材料。

真实业务数据来源：

```text
mis_pwa/data/mis_workflow.sqlite3
```

迁移脚本：

```text
mis_mvp/tools/import_workflow_sqlite.py
```

迁移目标：

```text
mis_mvp/data/mis_mvp.sqlite3
```

迁移规则：

- 迁移前备份目标 SQLite。
- 以 `order_no`、`sku`、`batch_no`、`source_key` 等字段保证幂等。
- 不覆盖人工后续补录的已确认字段。
- `repair_orders` 导入当前维修工单，并创建/绑定 `machines`。
- `repair_events` 导入 `machine_events`。
- `materials`、`material_batches`、`repair_materials`、`stock_movements` 映射到物料与库存表。
- `payments` 和 `receivables` 导入财务和应收结构。

真实业务资料文件：

- `BUSINESS_REALITY_LOG.md`
- `MATERIAL_INVENTORY_LOG.md`
- `BUSINESS_TIMELINE_SUMMARY.md`
- `MIS_REFACTOR_NOTES.md`

这些文件是后续维护依据，不是示例数据。

## 8. 权限与审计

系统内置角色包括 `admin`、`boss`、`frontdesk`、`engineer`、`staff`、`finance`。后端通过 `current_user` 从请求头 `X-User` 取当前用户，并由 `MisService._allowed()` 校验权限。

操作日志写入 `operation_logs`，机器生命周期写入 `machine_events`。涉及状态变更、库存变更、财务确认、退货退料和盘点调整的操作都应保留操作人、时间和原因。

## 9. 启动与运维

本地启动入口：

- `项目启动入口.vbs`：双击打开图形化入口，提供启动、重启、停止和数据库绑定。
- `project_launcher.py`：图形化启动器主程序。
- `project_ctl.py`：命令行控制器，可指定端口启动、重启、停止。
- `start_project.ps1`：PowerShell 启动脚本。

常用开发启动方式：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m uvicorn backend.app:app --host 0.0.0.0 --port 8088 --app-dir mis_mvp
```

默认访问：

```text
http://127.0.0.1:8088/
```

## 10. 测试策略

已有测试目录：

```text
mis_mvp/tests
```

测试重点：

- API 基础可用性。
- 机器生命周期流转。
- 维修闭环状态机：维修完成不能直接等于订单完结。
- 财务确认：前台收款进入待确认，财务确认后才可完结。
- 同行挂账：进入 `receivables`，不计入当日已收款。
- 仓库入库：采购入库生成批次和单件码。
- 申领发放：申请和审核不扣库存，发放扣库存。
- 退料退货：通过反向流水恢复或减少库存，禁止硬删除。
- 故障物料提示：选择维修 SKU 时显示推荐物料、可用库存、库位和低库存预警。

前端语法检查：

```powershell
node --check mis_mvp/static/app.js
```

后端测试：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pytest mis_mvp\tests
```

## 11. 后续设计原则

- `mis_mvp` 是当前主线，`mis_pwa/data/mis_workflow.sqlite3` 仅作为真实业务迁移来源。
- Markdown 业务日志、SQLite 迁移结果和前端展示口径必须保持一致。
- 新增业务动作应优先补服务层方法和测试，再接前端按钮。
- 已确认的入库、退货、发放、退料、盘点、财务流水不允许硬删除，只允许反向单冲销。
- 所有金额、成本、工程师、付款方式、流水号、财务确认人缺失时保持“待补/待确认”。
- 扩展销售退货、客户退款、采购退款时，应复用 `payments` 反向流水与库存反向单设计。
