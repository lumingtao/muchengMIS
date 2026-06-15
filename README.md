# 沐辰科技 MIS 管理系统

当前主线是本地私有化 MIS：FastAPI + SQLite 后端，Vite + React + TypeScript 前端，覆盖维修工单、会员客户、维修物料库存、回收库存、销售、财务流水、报表和审计。

## 当前状态

- 后端主目录：`mis_mvp/`
- 前端主目录：`frontend/`
- 生产前端构建输出：`mis_mvp/frontend_dist/`，由 `npm run build` 生成，不作为源码提交
- 固定运行数据库：`mis_mvp/data/mis_mvp.sqlite3`
- FastAPI 服务 React 构建产物；若 `frontend_dist` 不存在，会返回明确的构建提示。

## 目录说明

```text
mis_mvp/
  backend/              FastAPI 路由、权限、SQLite 迁移、业务服务
  data/                 本地 SQLite 运行库目录
  frontend_dist/        React 构建产物，由 FastAPI 托管，本地构建生成
  tests/                后端 API、业务流、机器生命周期测试
  tools/                演示数据、旧数据和真实工作流导入脚本
frontend/
  src/                  React + TypeScript 前端源码
  src/components/       Ant Design 适配组件
  src/theme/            Ant Design 主题 token
docs/                   UI 组件库和迁移参考
project_ctl.py          命令行启动、重启、停止控制器
project_launcher.py     图形化启动入口
start_project.ps1       Windows PowerShell 启动脚本
start_project.command   macOS 本地启动脚本
```

## 核心业务主线

新业务围绕 `machines.machine_id` 展开：

- 维修：`repair_orders`、`repair_items`、检测记录、照片、备注、工单时间线和收款。
- 会员：`customers`、`customer_interactions`，支持会员编号、标签、商家资料和回访记录。
- 物料库存：物料档案、批次、单件码、申领、审批、发放、退料、退货、盘点和库存流水。
- 回收/销售：回收单入库形成 `inventory_items`，销售单出库并生成收入。
- 财务：`payments` 保存维修收入、销售收入、回收支出；挂账和未收款保留应收扩展口径。
- 审计：关键写操作写入 `operation_logs`；机器生命周期写入 `machine_events`。

旧 `devices`、`repairs` 仍保留兼容接口和测试，但不再是新业务主表。

## 本地启动

后端依赖：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pip install -r mis_mvp\requirements.txt
```

macOS / Codex 本地虚拟环境：

```bash
.venv/bin/python -m pip install -r mis_mvp/requirements.txt
```

启动后端：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m uvicorn backend.app:app --host 0.0.0.0 --port 8088 --app-dir mis_mvp
```

macOS / Codex 本地虚拟环境：

```bash
.venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port 8088 --app-dir mis_mvp
```

或使用启动器：

```powershell
.\start_project.ps1 start
```

访问：

```text
http://127.0.0.1:8088/
```

默认原型账号：

```text
admin / admin
staff / staff
finance / finance
```

## 前端开发

如果当前 shell 没有系统 `npm`，先启用项目本地 npm：

```powershell
source tools/npm/use-npm.sh
```

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Vite 默认运行在 `http://127.0.0.1:5173`，并把 `/api` 代理到 `http://127.0.0.1:8088`。开发前先启动 FastAPI。

构建生产前端：

```powershell
cd frontend
npm.cmd run build
```

构建产物会写入 `mis_mvp/frontend_dist/`，该目录是生成物，不作为 Stitch 或人工 UI 修改入口。

## 维修物料仓

维修物料仓前端入口已拆到 `frontend/src/pages/warehouse/WarehousePage.tsx`，覆盖库存看板、物料档案、入库批次、单件码、申领、退料、盘点、调整、流水和基础资料。

后端仓库能力集中在 `mis_mvp/backend/service.py` 与 `/api/warehouse`、`/api/materials`、`/api/material-batches`、`/api/material-requests`、`/api/material-returns`、`/api/stock-*` 等接口。演示库需要重建维修物料仓数据时，可使用：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' mis_mvp\tools\reset_warehouse_demo.py --yes
```

该脚本会清空维修物料仓相关表并重建演示物料、库区、库位和入库批次，不能对真实生产库直接执行。

## 测试

后端：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pytest mis_mvp\tests --basetemp .runtime\pytest-tmp
```

macOS / Codex 本地虚拟环境：

```bash
.venv/bin/python -m pytest mis_mvp/tests --basetemp .runtime/pytest-tmp
```

前端：

```powershell
cd frontend
npm.cmd run test
```

UI 冒烟验证可参考 [docs/STITCH_UI_WORKFLOW.md](docs/STITCH_UI_WORKFLOW.md) 中的浏览器验证步骤。

## 维护原则

- 真实订单事实以 `mis_mvp/data/mis_mvp.sqlite3` 为准。
- `BUSINESS_REALITY_LOG.md`、`MATERIAL_INVENTORY_LOG.md`、`BUSINESS_TIMELINE_SUMMARY.md` 是业务观察和规则来源，不替代结构化订单流水。
- 新功能优先接入 `machines` 主线，避免继续扩大旧 `devices/repairs` 兼容模型。
- 未知业务字段不要伪造，统一留空、标记“待补”或“待确认”。
- 不提交真实账号密码、本地 `.env`、运行日志、虚拟环境、缓存、数据库备份和构建中间产物。

## 开发参考文档

- [DESIGN.md](DESIGN.md)：当前架构、数据模型、API 和权限边界。
- [BUSINESS_FLOW.md](BUSINESS_FLOW.md)：维修、库存、会员、回收销售和财务业务流。
- [ORDER_CREATION_ACTION_DESIGN.md](ORDER_CREATION_ACTION_DESIGN.md)：新建维修工单动作说明。
- [mis_mvp/README.md](mis_mvp/README.md)：MVP 子项目运行和数据边界。
- [docs/UI_COMPONENT_LIBRARY_EVALUATION.md](docs/UI_COMPONENT_LIBRARY_EVALUATION.md)：UI 组件库选型结论。
- [docs/ANT_DESIGN_6_MIGRATION_PLAN.md](docs/ANT_DESIGN_6_MIGRATION_PLAN.md)：Ant Design 当前落地状态和后续迁移计划。
- [docs/STITCH_UI_WORKFLOW.md](docs/STITCH_UI_WORKFLOW.md)：Stitch / Figma 双向 UI 修改流程。
- [docs/STITCH_DESIGN_BRIEF.md](docs/STITCH_DESIGN_BRIEF.md)：可复制到 Stitch 的项目设计上下文。
