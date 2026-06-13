# 项目重建开发记录

本文档保留重建背景，并按当前进展重新整理为维护参考。早期 `mis_pwa`、C# Bridge、WinForms 相关内容已经退为历史参考；当前仓库主线是 `mis_mvp` + `frontend`。

## 1. 重建结论

早期原型验证了维修、回收、销售、客户和报表方向，但继续在原型上堆功能会带来状态、权限、数据和前端复杂度问题。当前重建后的主线已经形成：

- FastAPI 服务层集中业务规则。
- SQLite 保存本地结构化业务数据。
- `machines` 统一机器生命周期。
- React 前端承载工作台、维修工单池、会员、库存、财务和设置页面。
- Ant Design 6 作为主 UI 组件库。
- 测试覆盖后端业务流和前端基础组件。

## 2. 已继承的业务经验

从早期原型和真实业务观察继承的关键规则：

- 客户描述、工程师检测结论、维修方案必须拆开。
- 技术完成不等于订单完结。
- 客户取机不等于已收款。
- 前台收款不等于财务已确认。
- 同行挂账要进入应收口径。
- 物料库存必须有批次、单件码、流水和维修绑定。
- 临采物料要先补入库，再进入维修成本。
- 机型、IMEI、客户、柜台号等关键字段允许待补，但不能伪造。

## 3. 当前实现资产

### 后端

- `backend/app.py`：API 路由和前端托管。
- `backend/service.py`：业务动作、权限调用、状态流转和事务。
- `backend/repository.py`：SQL 访问。
- `backend/db.py`：SQLite 结构、迁移和默认数据。
- `backend/models.py`：Pydantic 输入模型和枚举。
- `backend/auth.py`：角色权限矩阵。

### 前端

- `frontend/src/App.tsx`：当前页面主入口。
- `frontend/src/api.ts`：API 封装。
- `frontend/src/components/`：Ant Design 项目级适配层。
- `frontend/src/theme/antdTheme.ts`：主题 token。

### 测试

- `mis_mvp/tests/test_business_flow.py`
- `mis_mvp/tests/test_machine_flow.py`
- `mis_mvp/tests/test_api.py`
- `frontend/src/*.test.tsx`

## 4. 仍需持续推进

- 拆分 `frontend/src/App.tsx`。
- 继续将业务表单迁移到 Ant Design Form。
- 强化维修工单状态机，补齐财务确认、同行挂账、预付款核销和反向流水。
- 完善客户结账和应收账款。
- 增加真实数据导入前后的校验工具。
- 对库存低库存预警、盘点差异和物料成本归集补更多测试。

## 5. 历史资料定位

旧原型和真实业务资料仍有价值，但使用方式不同：

- `BUSINESS_TIMELINE_SUMMARY.md`：真实业务经验总结。
- `BUSINESS_REALITY_LOG.md`：典型维修订单观察。
- `MATERIAL_INVENTORY_LOG.md`：典型物料和库存观察。
- `MIS_REFACTOR_NOTES.md`：当前重构维护说明。

开发时不要把历史文档中的表名和状态直接当成当前实现，应回到 `backend/db.py`、`backend/models.py`、`backend/service.py` 核对。
