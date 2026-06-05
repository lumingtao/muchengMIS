# Codex Local Notes

## GitHub CLI authentication on this machine

When Codex reports that GitHub CLI is unavailable, not logged in, or that the
token is invalid, first check whether the issue is actually network/proxy access.

Known working setup on this machine:

```powershell
$env:HTTPS_PROXY="socks5://127.0.0.1:10808"
$env:HTTP_PROXY="socks5://127.0.0.1:10808"
gh auth status
```

The `10808` port comes from v2rayN's local mixed listening port.

If Codex cannot read the Windows keyring token, re-authenticate with file-backed
storage:

```powershell
gh auth logout -h github.com -u lumingtao
$env:HTTPS_PROXY="socks5://127.0.0.1:10808"
$env:HTTP_PROXY="socks5://127.0.0.1:10808"
gh auth login -h github.com --insecure-storage
```

Expected successful check:

```text
Logged in to github.com account lumingtao
Token scopes: gist, read:org, repo, workflow
```

If `gh auth status` fails without proxy but succeeds with the proxy variables,
the token is valid; the failure is caused by direct GitHub access being blocked.

## 沐辰科技二手机 MIS 真实业务口径

后续维护“沐辰科技二手机 MIS 管理系统”时，以下外部文件是现有真实业务事实和数据口径来源，不是示例数据：

- `D:/软件开发/沐辰科技二手机MIS管理系统/BUSINESS_REALITY_LOG.md`
- `D:/软件开发/沐辰科技二手机MIS管理系统/MATERIAL_INVENTORY_LOG.md`
- `D:/软件开发/沐辰科技二手机MIS管理系统/BUSINESS_TIMELINE_SUMMARY.md`
- `D:/软件开发/沐辰科技二手机MIS管理系统/MIS_REFACTOR_NOTES.md`
- `D:/软件开发/沐辰科技二手机MIS管理系统/mis_pwa/data/mis_workflow.sqlite3`

当前业务目标是把维修业务从简单维修单升级为完整维修工单闭环中心，覆盖接单、检测、报价、客户确认、维修、领料、库存消耗、交付、收款、同行挂账、财务确认和订单完结。

关键维护原则：

- 客户描述、工程师检测结论、维修方案必须分开记录。
- 技术维修完成不等于订单完结。
- 客户取机不等于已收款。
- 前台收款不等于财务已确认到账。
- 同行挂账不计入当日已收款，应进入应收账款。
- 临采物料必须先补采购/入库，再绑定订单消耗。
- 每个节点必须记录真实时间点，用于核对维修时效和超期预警。
- 一个工单可能同时有物料成本、人工服务费、扩容款、客户自带配件安装费等多项收入/成本，系统应支持拆分。
- 不要伪造未知字段，未知内容统一标记为“待补”或“待确认”。

推荐维修状态流转：

`新建 -> 待检测 -> 待报价确认 -> 维修中 -> 待领料 -> 已领料 -> 维修完成 -> 待交付检测 -> 待取机/待送机/待返寄 -> 已交付 -> 财务待确认/同行挂账 -> 已完结`

推荐收款状态：

`未收款`、`已付款待财务确认`、`财务已确认`、`同行挂账`、`预付款已收`、`无需收款`

截至 2026-06-04 已补录/导入的核心维修工单包括：

- `R-20260601-001` 蓝色 iPhone 12 Pro Max，不开机，主板短路维修，报价 200，工程师鲁明涛，客户已付款，财务已确认，已完结。
- `R-20260601-002` 苹果二代耳机待机短，更换两颗电池，报价 120，销售蒋国权，工程师鲁明涛，已付款，财务已确认，已完结。
- `R-20260601-003` 王哥寄修客户 iPhone 15 Pro，重摔不开机，板底资料抢修，报价 400，工程师鲁明涛，已维修完成，待送机/收款待确认。
- `R-20260601-004` iPhone 16 Pro 扩容 512GB，预付款订单，工程师鲁明涛，已取机完结，预付款金额待补。
- `R-20260601-005` iPhone 16 Pro Max 不开机，主板故障，联系人 176****1128，工程师鲁明涛，沟通时效 3 天，维修中。
- `R-20260603-001` 华为手机进水清理，同行客户王春梅柜台，已取机，同行记账，金额待补。
- `R-20260603-002` 荣耀 Magic4 不开机，CPU 脱焊，柜台 0b11d，报价 120，已取机未付款，同行挂账。
- `R-20260604-001` 同行客户 4D13，iPhone 15 Pro 更换闪电蜂高容电池，已取机未付款，同行挂账，金额待补。
- `R-20260604-002` Mate 30 更换组装屏幕和组装后盖，报价 205，小飞家临采，已付款取走，财务确认/流水待补。
- `R-20260604-003` OPPO Reno 14 刷机解除锁屏密码，报价 180，已付款取走，财务确认/流水待补。
- `R-20260604-004` iPad 10 中框变形矫正，报价 150，已维修好，待取机。
- `R-20260604-005` 到店客户 iPhone 16 Plus，串号 358915821241848，扩容升级 512GB + 客户自带电池安装，电话 187****8042，已取机并付款；自带电池安装费 20 元，扩容实收金额待补；已绑定库存 512GB 物料 1 颗，库存从 3 片扣到 2 片，成本 375 元；财务待确认。

截至 2026-06-04 的关键库存事实：

- 采购 iPhone 12-15 系列通用 512GB 硬盘 3 片，单价 375，总价 1125，SKU：`SSD-IPH12-15-512G-20260604`。
- 采购 iPhone X-11 系列通用 512GB 硬盘 3 片，单价 265，总价 795，SKU：`SSD-IPHX-11-512G-20260604`。
- `R-20260604-005` 已消耗 `SSD-IPH12-15-512G-20260604` 1 片，当前库存应为 2 片。
- 闪电蜂高容电池已用于 `R-20260604-001`，但库存档案、成本、批次待补。
- Mate 30 组装屏幕和组装后盖为小飞家临采，成本、付款方式、经手人待补。
- `R-20260601-003` 使用 iPhone 15 Pro ID 板底库存回收配件，内部成本待补。
