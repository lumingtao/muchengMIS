from __future__ import annotations

from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
import pytest
from fastapi.testclient import TestClient

from backend.app import app, get_service
from backend.db import connect, migrate
from backend.repair_finance import analyze_repair_billing_xlsx
from backend.service import MisService


HEADERS = ["ID", "时间", "顾客", "备注", "工程师", "配件1", "配件来源", "配件2", "配件3", "报价", "成本", "利润", "销售姓名"]


class SessionTestClient(TestClient):
    def request(self, method, url, *, headers=None, **kwargs):  # type: ignore[no-untyped-def]
        supplied = dict(headers or {})
        username = supplied.pop("X-User", supplied.pop("x-user", ""))
        if username:
            login = super().request("POST", "/api/login", json={"username": username, "password": username})
            assert login.status_code == 200, login.text
        return super().request(method, url, headers=supplied or None, **kwargs)


@pytest.fixture()
def client(tmp_path: Path):
    connection = connect(tmp_path / "finance-api.sqlite3")
    migrate(connection)
    service = MisService(connection)

    def override_service() -> MisService:
        return service

    app.dependency_overrides[get_service] = override_service
    try:
        yield SessionTestClient(app)
    finally:
        app.dependency_overrides.clear()


def workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "订单详情"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_finance_upload_excludes_pending_and_deducts_sales_before_partner_share() -> None:
    content = workbook_bytes([
        ["A1", "2026-08-01", "客户1", "维修完成", "工程师A", "", "无", "", "", 1000, 200, 1, "销售A"],
        ["A2", "2026-08-02", "客户2", "待结账", "工程师A", "", "无", "", "", 500, 100, 400, "销售A"],
        ["A3", "2026-08-03", "客户3", "维修完成", "合伙人", "", "无", "", "", 500, 100, 400, ""],
    ])
    result = analyze_repair_billing_xlsx(content, "orders.xlsx", {
        "eligible_statuses": ["维修完成"],
        "employee_rules": [{"name": "工程师A", "base_salary": 100, "commission_rate": 0.1, "subsidy": 20, "deduction": 10}],
        "sales_commission_rate": 0.05,
        "partner_name": "合伙人",
        "partner_share_rate": 0.5,
        "operating_expense": 30,
    })

    assert result["source"] == {"filename": "orders.xlsx", "sheet": "订单详情", "total_rows": 3, "accepted_orders": 2, "excluded_orders": 1}
    assert result["summary"] == {
        "order_count": 2,
        "revenue": 1500.0,
        "direct_cost": 300.0,
        "gross_profit": 1200.0,
        "gross_margin": 0.8,
        "labor_expense": 200.0,
        "cash_payroll": 190.0,
        "sales_commission": 40.0,
        "operating_expense": 30.0,
        "profit_before_share": 930.0,
        "partner_share": 465.0,
        "retained_profit": 465.0,
    }
    assert result["payroll"][0]["commission"] == 80.0
    assert result["payroll"][0]["gross_pay"] == 200.0
    assert result["payroll"][0]["net_pay"] == 190.0
    assert result["excluded_status_summary"] == [{"status": "待结账", "count": 1}]
    assert result["can_finalize"] is True


def test_finance_upload_blocks_duplicates_missing_cost_and_unknown_engineer() -> None:
    content = workbook_bytes([
        ["A1", "2026-08-01", "客户1", "维修完成", "工程师A", "", "无", "", "", 100, 20, 80, ""],
        ["A1", "2026-08-01", "客户1", "维修完成", "工程师A", "", "无", "", "", 100, 20, 80, ""],
        ["A2", "2026-08-02", "客户2", "维修完成", "工程师A", "屏幕", "仓库", "", "", 300, 0, 300, ""],
        ["A3", "2026-08-03", "客户3", "维修完成", "未配置工程师", "", "无", "", "", 200, 50, 150, ""],
        ["A4", "2026-08-04", "客户4", "维修完成", "工程师A", "", "无", "", "", 120, 20, 999, ""],
    ])
    result = analyze_repair_billing_xlsx(content, "orders.xlsx", {
        "employee_rules": [{"name": "工程师A", "base_salary": 0, "commission_rate": 0, "subsidy": 0, "deduction": 0}],
    })

    assert result["source"]["accepted_orders"] == 2
    assert result["summary"]["revenue"] == 220.0
    assert result["summary"]["gross_profit"] == 180.0
    assert result["can_finalize"] is False
    assert {item["code"] for item in result["issues"]} == {
        "duplicate_id",
        "missing_part_cost",
        "missing_employee_rule",
        "profit_recalculated",
    }


def test_finance_upload_api_requires_report_permission(client) -> None:
    content = workbook_bytes([
        ["A1", "2026-08-01", "客户1", "维修完成", "鲁明涛", "", "无", "", "", 100, 20, 80, ""],
    ])
    allowed = client.post(
        "/api/finance/repair-billing/analyze",
        headers={"X-User": "finance"},
        files={"file": ("orders.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"policy": '{"employee_rules": [], "partner_name": "鲁明涛", "partner_share_rate": 0.5}'},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["summary"]["retained_profit"] == 40.0

    forbidden = client.post(
        "/api/finance/repair-billing/analyze",
        headers={"X-User": "engineer"},
        files={"file": ("orders.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert forbidden.status_code == 403


def test_finance_upload_preserves_chinese_filename(client) -> None:
    content = workbook_bytes([
        ["A1", "2026-08-01", "客户1", "维修完成", "鲁明涛", "", "无", "", "", 100, 20, 80, ""],
    ])
    response = client.post(
        "/api/finance/repair-billing/analyze",
        headers={"X-User": "finance"},
        files={"file": ("沐辰科技8月维修账单.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"policy": '{"employee_rules": [], "partner_name": "鲁明涛", "partner_share_rate": 0.5}'},
    )

    assert response.status_code == 200, response.text
    assert response.json()["source"]["filename"] == "沐辰科技8月维修账单.xlsx"


def test_finance_settings_and_batches_are_persisted(client) -> None:
    policy = {
        "eligible_statuses": ["维修完成"],
        "employee_rules": [{"name": "工程师A", "base_salary": 100, "commission_rate": 0.1, "subsidy": 20, "deduction": 10}],
        "sales_commission_rate": 0.05,
        "partner_name": "合伙人",
        "partner_share_rate": 0.5,
        "operating_expense": 30,
    }
    saved = client.put("/api/finance/repair-billing/settings", headers={"X-User": "finance"}, json=policy)
    assert saved.status_code == 200, saved.text
    assert saved.json()["policy"]["employee_rules"][0]["name"] == "工程师A"

    content = workbook_bytes([
        ["A1", "2026-08-01", "客户1", "维修完成", "工程师A", "", "无", "", "", 1000, 200, 800, "销售A"],
    ])
    uploaded = client.post(
        "/api/finance/repair-billing/analyze",
        headers={"X-User": "finance"},
        files={"file": ("8月账单.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert uploaded.status_code == 200, uploaded.text
    batch_id = uploaded.json()["batch_id"]
    assert uploaded.json()["persisted"] is True

    batches = client.get("/api/finance/repair-billing/batches", headers={"X-User": "finance"})
    assert batches.status_code == 200, batches.text
    assert batches.json()[0]["batch_id"] == batch_id
    assert batches.json()[0]["summary"]["retained_profit"] == 265.0

    detail = client.get(f"/api/finance/repair-billing/batches/{batch_id}", headers={"X-User": "finance"})
    assert detail.status_code == 200, detail.text
    assert detail.json()["policy"]["operating_expense"] == 30.0
    assert detail.json()["result"]["summary"]["retained_profit"] == 265.0
