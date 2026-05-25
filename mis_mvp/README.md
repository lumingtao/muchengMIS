# 沐辰 MIS 重构 MVP

这是从文档重新搭建的 FastAPI + PWA MVP，不依赖上一版原型代码。开发期默认使用 SQLite/Mock 数据跑通业务闭环，后续再把真实 MIS 通过 Bridge 接入。

## 运行

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pip install -r mis_mvp\requirements.txt
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m uvicorn backend.app:app --host 0.0.0.0 --port 8088 --app-dir mis_mvp
```

打开：

```text
http://127.0.0.1:8088
```

默认账号：

- `admin / admin`：管理员
- `staff / staff`：员工
- `finance / finance`：财务

## 设计边界

- SQLite 保存机器主线业务数据、客户主数据、收支流水、操作日志、用户配置。
- 新业务主表为 `machines`，维修、回收、库存、销售、收支都通过 `machine_id` 关联到机器生命周期。
- IMEI 优先唯一；无 IMEI 的机器会生成 `TMP-` 临时机器编号，后续可补录。
- 旧 MVP 的 `devices`、`repairs` 表保留兼容，但不再作为新业务主表。
- Bridge 适配器先保留只读入口，真实 MIS 写入需要测试库、备份和字段白名单后再启用。

## 数据库位置

默认 SQLite 文件：

```text
mis_mvp/data/mis_mvp.sqlite3
```

核心表：

- `machines`：机器档案和当前状态。
- `repair_orders` / `repair_items`：维修开单、检测报价、维修项目、交付检测。
- `recycle_orders`：回收开单、验机报价、付款入库。
- `inventory_items`：回收机器库存和销售定价。
- `sales_orders`：销售开单。
- `payments`：回收支出、维修收入、销售收入。
- `machine_events`：机器生命周期时间线。
- `customers`、`users`、`operation_logs`：客户、账号和审计。

## 旧 MVP 数据导入

如果需要把旧 `devices` / `repairs` 测试数据导入机器主线表：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' mis_mvp\tools\import_legacy_mvp.py
```

## 测试

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pytest mis_mvp\tests
```
