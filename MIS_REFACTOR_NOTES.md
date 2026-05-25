# MIS 数据库读写重构说明

## 当前主线

本轮重构以 `二手机未结` 作为统一 WinForms 主程序，并新增 `MIS.Core` 共享源码层。`MIS.WebAPI1` 也编译同一套共享数据访问代码，避免桌面端和 API 的 SQL 口径分叉。

## 数据库边界

- 不新增、不删除、不修改数据库表、字段、索引或其他结构。
- 固定业务查询集中在 `MIS.Core/MisQueryService.cs`。
- 所有 MIS 访问都通过 `MIS.Core/MisSession.cs` 封装 `MIS.API.MISServer`。
- SQL 控制台完全开放，但界面会提示“数据库结构不能改动”，并把执行历史写入备份目录的 `sql-history.csv`。

## 凭据配置

- 桌面端：启动后通过 `LoginForm` 输入 MIS 账号和密码，代码中不保存固定账号密码。
- WebAPI：优先读取 `appsettings.json` 的 `Mis:Username` / `Mis:Password`；为空时读取环境变量 `MIS_USERNAME` / `MIS_PASSWORD`。
- 不要把真实账号密码提交到源码文件中。

## 备份输出

- 默认目录：当前用户“我的文档”下的 `MIS数据备份`。
- 每次完整备份会导出：
  - `沐辰科技二手机.xlsx`
  - `维修账单.xlsx`
  - `库存记录.xlsx` 追加库存成本汇总
  - `sql-history.csv` 记录 SQL 控制台执行历史

## WebAPI 端点

- `GET /api/mis/stock`
- `GET /api/mis/unsettled-sales`
- `GET /api/mis/repair-pending`
- `GET /api/mis/bad-or-pending-devices`
- `GET /api/mis/inventory-summary`

这些接口返回 JSON 行对象列表，数据来源和桌面端固定视图相同。
