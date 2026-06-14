# 沐辰 MIS MVP

`mis_mvp/` 是当前可运行后端主线，负责 FastAPI API、SQLite 表结构、业务服务、静态资源托管和后端测试。

## 运行边界

- API 入口：`backend.app:app`
- 默认数据库：`data/mis_mvp.sqlite3`
- 数据库路径可由 `MIS_DATABASE_PATH` 覆盖，仅用于测试、迁移或临时验证。
- 启动时会执行 `backend.db.migrate()`，自动补齐表、字段、索引和默认用户。
- 根路径 `/` 返回 `frontend_dist/index.html`；缺失时返回构建提示，不再回退旧静态原型。

## 当前数据模型

新业务主线：

- `machines`：机器档案，IMEI 唯一；无 IMEI 时生成 `TMP-` 临时机器编号。
- `repair_orders`：维修工单，包含状态、指派工程师、报价、交付、付款状态和完结时间。
- `repair_items`：维修项目和费用拆分。
- `repair_order_inspections`、`repair_order_photos`、`repair_order_notes`：检测记录、照片和结构化备注。
- `repair_skus`、`device_models`：维修 SKU 和机型基础资料。
- `customers`、`customer_interactions`：会员客户和回访/备注记录。
- `materials`、`material_batches`、`material_units`、`material_requests`、`material_returns`、`stock_movements`、`stock_counts`、`stock_adjustments`：维修物料库存闭环。
- `recycle_orders`、`inventory_items`、`sales_orders`：回收机器库存和销售出库。
- `payments`、`receivables`：收支流水和应收扩展。
- `machine_events`、`operation_logs`：机器生命周期和系统审计。

兼容模型：

- `devices`、`repairs`、`settlements`、`settlement_items` 保留旧 MVP 接口和历史导入能力，不作为新功能首选落点。

## 常用命令

安装依赖：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pip install -r mis_mvp\requirements.txt
```

启动 API：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m uvicorn backend.app:app --host 0.0.0.0 --port 8088 --app-dir mis_mvp
```

运行测试：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pytest mis_mvp\tests --basetemp .runtime\pytest-tmp
```

## 重要接口组

- 登录和账号：`POST /api/login`、`GET /api/me`
- 机器：`POST /api/machines`、`GET /api/machines`、`PUT /api/machines/{id}`、`GET /api/machines/{id}/timeline`
- 维修工单：`POST /api/repair-orders`、`GET /api/repair-workbench`、`GET /api/repair-workbench/{id}`、`POST /api/repair-orders/{id}/workflow-action`
- 工单详情扩展：照片、检测记录、备注、指派、报价、改价、维修项目、作废、工程师结单、交付
- 基础资料：`GET/POST /api/device-models`、`GET/POST /api/repair-skus`
- 物料库存：仓库、类别、物料、批次、单件码、申领、审批、发放、退料、盘点、调整、流水
- 会员：`GET/POST /api/customers`、`GET/PUT /api/customers/{id}`、客户互动记录
- 回收销售财务：回收单、回收入库、库存、销售单、付款流水、报表
- 审计：`GET /api/audit-logs`

## 默认账号

```text
admin / admin
staff / staff
finance / finance
```

角色和权限定义在 `backend/auth.py`。工程师只能读取指派给自己的维修范围；前台、老板、管理员可查看和调度更完整的工单池；财务聚焦付款、结账、报表和审计。

## 导入脚本

- `tools/import_legacy_mvp.py`：把旧 `devices/repairs` 测试数据导入机器主线。
- `tools/import_workflow_sqlite.py`：从真实维修工作流库迁移维修、物料、财务样本。
- `tools/seed_demo_data.py`、`tools/seed_member_demo_500.py`：生成演示数据。

导入真实数据前先备份目标 SQLite，并保证幂等字段不会覆盖人工补录的确认信息。
