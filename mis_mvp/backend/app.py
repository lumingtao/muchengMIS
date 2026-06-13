from __future__ import annotations

from contextlib import asynccontextmanager
import re
from typing import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT_DIR, settings
from .db import connect, migrate
from .models import (
    DeviceModelInput,
    LoginInput,
    MachineInput,
    MachineNoteInput,
    MachineUpdateInput,
    MaterialBatchInput,
    MaterialBatchReturnInput,
    MaterialCategoryInput,
    MaterialInput,
    MaterialIssueReturnInput,
    MaterialRequestActionInput,
    MaterialRequestInput,
    MaterialReturnInspectInput,
    PaymentInput,
    PriceChangeInput,
    PurchaseInput,
    RecycleOrderInput,
    RecycleQuoteInput,
    RepairAssignInput,
    RepairDeliverInput,
    RepairEngineerCloseInput,
    RepairInspectionInput,
    RepairInput,
    RepairItemInput,
    RepairOrderNoteDeleteInput,
    RepairOrderNoteUpdateInput,
    RepairOrderInput,
    RepairRemarkInput,
    RepairOrderStatusInput,
    RepairQuoteConfirmInput,
    RepairQuoteInput,
    RepairSkuInput,
    RepairFaultMaterialInput,
    RepairWorkflowActionInput,
    RepairStatusInput,
    SalesOrderInput,
    SellDeviceInput,
    SettlementInput,
    StockInInput,
    StockAdjustmentInput,
    StockCountInput,
    User,
    WarehouseAreaInput,
    WarehouseLocationInput,
)
from .service import BusinessError, MisService


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = connect(settings.database_path)
    try:
        migrate(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
static_dir = ROOT_DIR / "static"
frontend_dir = ROOT_DIR / "frontend_dist"
uploads_dir = ROOT_DIR / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
if (frontend_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="frontend_assets")


def get_service():
    conn = connect(settings.database_path)
    migrate(conn)
    try:
        yield MisService(conn)
    finally:
        conn.close()


def current_user(x_user: str = Header(default="admin"), service: MisService = Depends(get_service)) -> User:
    try:
        return service.get_user(x_user)
    except BusinessError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def endpoint(call: Callable):
    try:
        return call()
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BusinessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def parse_photo_upload(content_type: str, body: bytes) -> tuple[str, str, str, bytes]:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise HTTPException(status_code=400, detail="缺少 multipart boundary")
    boundary = match.group("boundary").strip().strip('"')
    delimiter = b"--" + boundary.encode("utf-8")
    stage = ""
    filename = ""
    file_content_type = ""
    file_content = b""
    for raw_part in body.split(delimiter):
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if part.endswith(b"--"):
            part = part[:-2].rstrip(b"\r\n")
        header_blob, _, content = part.partition(b"\r\n\r\n")
        headers = header_blob.decode("latin1", errors="ignore")
        name_match = re.search(r'name="([^"]+)"', headers)
        if not name_match:
            continue
        field_name = name_match.group(1)
        if field_name == "stage":
            stage = content.decode("utf-8", errors="ignore").strip()
        elif field_name == "file":
            filename_match = re.search(r'filename="([^"]*)"', headers)
            type_match = re.search(r"Content-Type:\s*([^\r\n]+)", headers, re.IGNORECASE)
            filename = filename_match.group(1) if filename_match else ""
            file_content_type = type_match.group(1).strip() if type_match else ""
            file_content = content
    if not stage or not file_content:
        raise HTTPException(status_code=400, detail="缺少 stage 或 file")
    return stage, filename, file_content_type, file_content


@app.get("/")
def index() -> FileResponse:
    if (frontend_dir / "index.html").exists():
        return FileResponse(frontend_dir / "index.html")
    return FileResponse(static_dir / "index.html")


@app.post("/api/login")
def login(data: LoginInput, service: MisService = Depends(get_service)):
    return endpoint(lambda: service.login(data))


@app.get("/api/me")
def me(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.user_profile(user))


@app.post("/api/purchases")
def create_purchase(data: PurchaseInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_purchase(user, data))


@app.post("/api/machines")
def create_machine(data: MachineInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_machine(user, data))


@app.get("/api/machines")
def machines(q: str = Query(default=""), user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.search_machines(user, q))


@app.get("/api/machines/{machine_id}/timeline")
def machine_timeline(machine_id: int, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.machine_timeline(user, machine_id))


@app.put("/api/machines/{machine_id}")
def update_machine(machine_id: int, data: MachineUpdateInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.update_machine(user, machine_id, data))


@app.post("/api/machines/{machine_id}/notes")
def add_machine_note(machine_id: int, data: MachineNoteInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.add_machine_note(user, machine_id, data))


@app.delete("/api/machines/{machine_id}")
def delete_machine(machine_id: int, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.delete_machine(user, machine_id))


@app.post("/api/repair-orders")
def create_repair_order(data: RepairOrderInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_repair_order(user, data))


@app.get("/api/repair-skus")
def repair_skus(
    model: str = Query(default=""),
    q: str = Query(default=""),
    user: User = Depends(current_user),
    service: MisService = Depends(get_service),
):
    return endpoint(lambda: service.list_repair_skus(user, model=model, keyword=q))


@app.get("/api/device-models")
def device_models(
    q: str = Query(default=""),
    enabled_only: bool = Query(default=False),
    user: User = Depends(current_user),
    service: MisService = Depends(get_service),
):
    return endpoint(lambda: service.list_device_models(user, keyword=q, enabled_only=enabled_only))


@app.get("/api/repair-workbench")
def repair_workbench(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.repair_workbench(user))


@app.get("/api/repair-workbench/{repair_order_id}")
def repair_workbench_detail(repair_order_id: int, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.repair_workbench_detail(user, repair_order_id))


@app.get("/api/repair-orders/{repair_order_id}/photos")
def repair_order_photos(repair_order_id: int, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.list_repair_order_photos(user, repair_order_id))


@app.post("/api/repair-orders/{repair_order_id}/photos")
async def upload_repair_order_photo(
    repair_order_id: int,
    request: Request,
    user: User = Depends(current_user),
    service: MisService = Depends(get_service),
):
    stage, filename, content_type, content = parse_photo_upload(request.headers.get("content-type", ""), await request.body())
    return endpoint(lambda: service.add_repair_order_photo(user, repair_order_id, stage, filename, content_type, content))


@app.post("/api/repair-orders/{repair_order_id}/inspections")
def save_repair_order_inspection(repair_order_id: int, data: RepairInspectionInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.save_repair_order_inspection(user, repair_order_id, data))


@app.post("/api/repair-orders/{repair_order_id}/workflow-action")
def repair_workflow_action(repair_order_id: int, data: RepairWorkflowActionInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.apply_repair_workflow_action(user, repair_order_id, data))


@app.get("/api/materials")
def materials(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.list_materials(user))


@app.get("/api/warehouse")
def warehouse(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.warehouse_overview(user))


@app.get("/api/warehouse/areas")
def warehouse_areas(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.warehouse_overview(user)["areas"])


@app.post("/api/warehouse/areas")
def create_warehouse_area(data: WarehouseAreaInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_warehouse_area(user, data))


@app.get("/api/warehouse/locations")
def warehouse_locations(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.warehouse_overview(user)["locations"])


@app.post("/api/warehouse/locations")
def create_warehouse_location(data: WarehouseLocationInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_warehouse_location(user, data))


@app.get("/api/material-categories")
def material_categories(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.warehouse_overview(user)["categories"])


@app.post("/api/material-categories")
def create_material_category(data: MaterialCategoryInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_material_category(user, data))


@app.post("/api/materials")
def create_material(data: MaterialInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_material(user, data))


@app.get("/api/material-units")
def material_units(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.material_units(user))


@app.get("/api/material-batches")
def material_batches(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.material_batches(user))


@app.post("/api/material-batches/purchase")
def create_purchase_material_batch(data: MaterialBatchInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_material_batch(user, data, "purchase"))


@app.post("/api/material-batches/ad-hoc")
def create_ad_hoc_material_batch(data: MaterialBatchInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_material_batch(user, data, "ad_hoc"))


@app.post("/api/material-batches/{batch_id}/return")
def return_material_batch(batch_id: int, data: MaterialBatchReturnInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.return_material_batch(user, batch_id, data))


@app.get("/api/material-requests")
def material_requests(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.material_requests(user))


@app.get("/api/material-requests/mine")
def my_material_requests(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.material_requests(user, mine=True))


@app.post("/api/material-requests")
def create_material_request(data: MaterialRequestInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_material_request(user, data))


@app.post("/api/material-requests/{request_id}/approve")
def approve_material_request(request_id: int, data: MaterialRequestActionInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.approve_material_request(user, request_id, data))


@app.post("/api/material-requests/{request_id}/reject")
def reject_material_request(request_id: int, data: MaterialRequestActionInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.reject_material_request(user, request_id, data))


@app.post("/api/material-requests/{request_id}/issue")
def issue_material_request(request_id: int, data: MaterialRequestActionInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.issue_material_request(user, request_id, data))


@app.post("/api/material-requests/{request_id}/cancel")
def cancel_material_request(request_id: int, data: MaterialRequestActionInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.cancel_material_request(user, request_id, data))


@app.post("/api/material-issues/{unit_id}/return-request")
def request_material_return(unit_id: int, data: MaterialIssueReturnInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.request_material_return(user, unit_id, data))


@app.post("/api/material-returns/{return_id}/inspect")
def inspect_material_return(return_id: int, data: MaterialReturnInspectInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.inspect_material_return(user, return_id, data))


@app.post("/api/stock-counts")
def create_stock_count(data: StockCountInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_stock_count(user, data))


@app.post("/api/stock-counts/{count_id}/confirm")
def confirm_stock_count(count_id: int, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.confirm_stock_count(user, count_id))


@app.post("/api/stock-adjustments")
def create_stock_adjustment(data: StockAdjustmentInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_stock_adjustment(user, data))


@app.get("/api/stock-movements")
def stock_movements(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.stock_movements(user))


@app.get("/api/repair-fault-materials")
def repair_fault_materials(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.repair_fault_materials(user))


@app.post("/api/repair-fault-materials")
def upsert_repair_fault_material(data: RepairFaultMaterialInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.upsert_repair_fault_material(user, data))


@app.get("/api/repair-skus/{sku_id}/material-hints")
def repair_sku_material_hints(sku_id: int, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.material_hints_for_sku(user, sku_id))


@app.get("/api/repair-orders/{repair_order_id}/material-hints")
def repair_order_material_hints(repair_order_id: int, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.material_hints_for_order(user, repair_order_id))


@app.post("/api/repair-skus")
def upsert_repair_sku(data: RepairSkuInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.upsert_repair_sku(user, data))


@app.post("/api/device-models")
def upsert_device_model(data: DeviceModelInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.upsert_device_model(user, data))


@app.post("/api/repair-orders/{repair_order_id}/assign")
def assign_repair_order(repair_order_id: int, data: RepairAssignInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.assign_repair_order(user, repair_order_id, data))


@app.post("/api/repair-orders/{repair_order_id}/quote")
def quote_repair_order(repair_order_id: int, data: RepairQuoteInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.quote_repair_order(user, repair_order_id, data))


@app.post("/api/repair-orders/{repair_order_id}/confirm-quote")
def confirm_repair_quote(repair_order_id: int, data: RepairQuoteConfirmInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.confirm_repair_quote(user, repair_order_id, data))


@app.post("/api/repair-orders/{repair_order_id}/price")
def change_repair_order_price(repair_order_id: int, data: PriceChangeInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.change_repair_order_price(user, repair_order_id, data))


@app.post("/api/repair-orders/{repair_order_id}/items")
def add_repair_item(repair_order_id: int, data: RepairItemInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.add_repair_item(user, repair_order_id, data))


@app.post("/api/repair-orders/{repair_order_id}/status")
def update_repair_order_status(repair_order_id: int, data: RepairOrderStatusInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.update_repair_order_status(user, repair_order_id, data))


@app.post("/api/repair-orders/{repair_order_id}/remark")
def append_repair_order_remark(repair_order_id: int, data: RepairRemarkInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.append_repair_order_remark(user, repair_order_id, data))


@app.put("/api/repair-orders/{repair_order_id}/notes/{note_id}")
def update_repair_order_note(repair_order_id: int, note_id: int, data: RepairOrderNoteUpdateInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.update_repair_order_note(user, repair_order_id, note_id, data))


@app.delete("/api/repair-orders/{repair_order_id}/notes/{note_id}")
def delete_repair_order_note(repair_order_id: int, note_id: int, data: RepairOrderNoteDeleteInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.delete_repair_order_note(user, repair_order_id, note_id, data))


@app.post("/api/repair-orders/{repair_order_id}/engineer-close")
def engineer_close_repair_order(repair_order_id: int, data: RepairEngineerCloseInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.engineer_close_repair_order(user, repair_order_id, data))


@app.post("/api/repair-orders/{repair_order_id}/deliver")
def deliver_repair_order(repair_order_id: int, data: RepairDeliverInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.deliver_repair_order(user, repair_order_id, data))


@app.post("/api/recycle-orders")
def create_recycle_order(data: RecycleOrderInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_recycle_order(user, data))


@app.post("/api/recycle-orders/{recycle_order_id}/quote")
def quote_recycle_order(recycle_order_id: int, data: RecycleQuoteInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.quote_recycle_order(user, recycle_order_id, data))


@app.post("/api/recycle-orders/{recycle_order_id}/price")
def change_recycle_order_price(recycle_order_id: int, data: PriceChangeInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.change_recycle_order_price(user, recycle_order_id, data))


@app.post("/api/recycle-orders/{recycle_order_id}/stock-in")
def stock_in_recycle_order(recycle_order_id: int, data: StockInInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.stock_in_recycle_order(user, recycle_order_id, data))


@app.get("/api/inventory")
def inventory(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.list_inventory(user))


@app.post("/api/sales-orders")
def create_sales_order(data: SalesOrderInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_sales_order(user, data))


@app.post("/api/payments")
def create_payment(data: PaymentInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_payment(user, data))


@app.get("/api/payments")
def payments(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.list_payments(user))


@app.get("/api/machine-reports")
def machine_reports(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.machine_reports(user))


@app.get("/api/stock")
def stock(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.list_stock(user))


@app.post("/api/sales")
def sell_device(data: SellDeviceInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.sell_device(user, data))


@app.post("/api/repairs")
def create_repair(data: RepairInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.create_repair(user, data))


@app.get("/api/repairs")
def repairs(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.list_repairs(user))


@app.post("/api/repairs/status")
def update_repair_status(data: RepairStatusInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.update_repair_status(user, data))


@app.get("/api/customers")
def customers(q: str = Query(default=""), user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.search_customers(user, q))


@app.get("/api/imei/{imei}")
def lookup_imei(imei: str, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.lookup_imei(user, imei))


@app.get("/api/settlements/preview/{customer_id}")
def settlement_preview(customer_id: int, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.settlement_preview(user, customer_id))


@app.post("/api/settlements")
def settle_customer(data: SettlementInput, user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.settle_customer(user, data))


@app.get("/api/reports")
def reports(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.reports(user))


@app.get("/api/audit-logs")
def audit_logs(user: User = Depends(current_user), service: MisService = Depends(get_service)):
    return endpoint(lambda: service.audit_logs(user))
