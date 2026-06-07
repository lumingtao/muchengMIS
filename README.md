# 沐辰科技 MIS 管理系统

这是沐辰科技二手手机 MIS 管理系统的本地原型项目。当前可运行主线是 `mis_mvp/`，采用 FastAPI + SQLite + 原生静态前端实现，覆盖维修、回收、库存、销售、客户、财务与操作日志等业务闭环。

## 项目结构

```text
mis_mvp/                 当前可运行主线
  backend/               FastAPI 后端、数据模型、数据库迁移与业务服务
  static/                单页前端页面、脚本与样式
  tests/                 API、业务流和机器生命周期测试
  tools/                 数据导入与演示数据脚本
mis_pwa/data/            真实维修工作流迁移来源数据
project_ctl.py           命令行启动、重启、停止控制器
project_launcher.py      图形化启动入口
start_project.ps1        PowerShell 启动脚本
项目启动入口.vbs          双击打开图形化启动入口
```

更多设计与业务说明见：

- [DESIGN.md](DESIGN.md)
- [BUSINESS_FLOW.md](BUSINESS_FLOW.md)
- [BUSINESS_REALITY_LOG.md](BUSINESS_REALITY_LOG.md)
- [MATERIAL_INVENTORY_LOG.md](MATERIAL_INVENTORY_LOG.md)

真实业务录入原则：

- 后续新增订单、交付、收款、挂账和物料消耗优先写入固定 SQLite 数据库：`mis_mvp/data/mis_mvp.sqlite3`。
- 启动器、`project_ctl.py` 和 `start_project.ps1` 默认都指向这一个固定库；不要再使用临时目录数据库作为真实业务运行库。
- `BUSINESS_REALITY_LOG.md` 和 `MATERIAL_INVENTORY_LOG.md` 只补充有典型特征、会影响系统设计或业务规则判断的样本，不再作为完整订单流水台账。
- 订单事实以数据库为准；文档用于记录业务经验、异常模式、待确认规则和开发调整依据。

## 启动项目

安装依赖：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pip install -r mis_mvp\requirements.txt
```

启动服务：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m uvicorn backend.app:app --host 0.0.0.0 --port 8088 --app-dir mis_mvp
```

也可以使用项目启动器：

```powershell
.\start_project.ps1 start
```

访问地址：

```text
http://127.0.0.1:8088/
```

默认原型账号：

```text
admin / admin
staff / staff
finance / finance
```

## 测试

普通测试命令：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pytest mis_mvp\tests
```

如果 Windows 系统临时目录权限异常，可把 pytest 临时目录放到工作区：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pytest mis_mvp\tests --basetemp .runtime\pytest-tmp
```

## 数据与运维

固定 SQLite 数据库位置：

```text
mis_mvp/data/mis_mvp.sqlite3
```

启动器、命令行控制器和 PowerShell 启动脚本都默认使用上面的固定库。真实业务迁移来源数据保留在：

```text
mis_pwa/data/mis_workflow.sqlite3
```

## Git 注意事项

请勿提交真实 MIS 账号密码、本地 `.env`、运行日志、Python 缓存、虚拟环境、编译产物或本地数据库备份。

## React frontend upgrade

The project now includes a Vite + React + TypeScript frontend in `frontend/`. The FastAPI backend APIs and SQLite database remain unchanged.

Development:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8088`, so start the FastAPI service first.

Production build:

```powershell
cd frontend
npm.cmd run build
```

The build output is written to `mis_mvp/frontend_dist/`. FastAPI serves that React build first; if it is missing, it falls back to the legacy `mis_mvp/static/` frontend.

Frontend tests:

```powershell
cd frontend
npm.cmd run test
```
