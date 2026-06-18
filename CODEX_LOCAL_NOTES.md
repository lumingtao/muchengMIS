# 本地维护备注

本文档记录本机开发和业务口径注意事项，不是订单流水台账。

## 1. GitHub CLI 网络

如果 GitHub CLI 报未登录、token 无效或无法连接，先检查是否是网络代理问题。

已知可用代理方式：

```powershell
$env:HTTPS_PROXY="socks5://127.0.0.1:10808"
$env:HTTP_PROXY="socks5://127.0.0.1:10808"
gh auth status
```

如果需要重新登录：

```powershell
gh auth logout -h github.com -u lumingtao
$env:HTTPS_PROXY="socks5://127.0.0.1:10808"
$env:HTTP_PROXY="socks5://127.0.0.1:10808"
gh auth login -h github.com --insecure-storage
```

## 2. 当前项目主线

当前开发主线：

```text
mis_mvp/backend
frontend
mis_mvp/data/mis_mvp.sqlite3
```

前端构建产物：

```text
mis_mvp/frontend_dist/
```

FastAPI 会优先服务 React 构建，缺失时回退 `mis_mvp/static/`。

## 3. 真实业务口径

业务事实来源：

- 数据库订单事实：`mis_mvp/data/mis_mvp.sqlite3`
- 业务观察：`BUSINESS_REALITY_LOG.md`
- 物料观察：`MATERIAL_INVENTORY_LOG.md`
- 业务复盘：`BUSINESS_TIMELINE_SUMMARY.md`

维护原则：

- 结构化订单事实以 SQLite 为准。
- Markdown 记录典型样本、规则来源、异常模式和待确认字段。
- 不伪造未知字段，统一留空、待补或待确认。
- 客户描述、工程师检测结论、维修方案分开写。
- 同行挂账进入应收，不算当日已收款。
- 前台收款和财务确认分开。
- 临采物料先补入库，再绑定维修成本。

## 4. 常用命令

后端测试：

```powershell
& 'C:\Users\admini\AppData\Local\Python\bin\python.exe' -m pytest mis_mvp\tests --basetemp .runtime\pytest-tmp
```

前端测试：

```powershell
cd frontend
npm.cmd run test
```

前端构建：

```powershell
cd frontend
npm.cmd run build
```

启动服务：

```powershell
.\start_project.cmd start
```

Win10 优先使用 `start_project.cmd`，避免 PowerShell 执行策略拦截；`start_project.ps1` 仅在脚本执行策略允许时使用。

## 5. 文档同步规则

- 改表结构或核心 API：更新 `DESIGN.md`。
- 改维修、库存、会员、财务流程：更新 `BUSINESS_FLOW.md`。
- 改新建维修工单：更新 `ORDER_CREATION_ACTION_DESIGN.md`。
- 改 Ant Design 基础层或页面迁移策略：更新 `docs/ANT_DESIGN_6_MIGRATION_PLAN.md`。
- 改启动、构建、测试方式：更新 `README.md` 和 `mis_mvp/README.md`。
