import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Card, Form, Input, InputNumber, Row, Select, Space, Statistic } from "antd";
import { RefreshCw } from "lucide-react";
import { AnyRecord, api } from "../../api";
import { AppButton } from "../../components/actions/AppButton";
import { AppTable } from "../../components/data/AppTable";
import { QueryState } from "../../components/data/QueryState";
import { AppPanel } from "../../components/layout/AppPanel";

type WarehousePageProps = {
  notify: (message: string, error?: boolean) => void;
  section: string;
};

type WarehouseMutation = {
  isPending: boolean;
  mutate: (variables: { path: string; payload?: AnyRecord }) => void;
};

const statusOptions = ["在库可用", "已发放", "退料待验收", "已退货", "已报损", "盘亏", "拆回待检", "拆回验收可退"];
const requestStatusOptions = ["待审核", "已审核待发放", "已发放", "已拒绝", "已取消"];
const returnResults = ["可复用", "已损坏", "已使用拆回", "可退供应商"];
const adjustmentTypes = ["盘盈入库", "盘亏出库", "报损出库", "反向调整入库", "反向调整出库"];

function formatMoney(input: unknown) {
  const amount = Number(input || 0);
  return `¥${amount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function displayValue(row: AnyRecord, key: string) {
  const raw = row[key];
  if (raw === null || raw === undefined || raw === "") return "-";
  if (["unit_cost", "total_cost", "avg_cost", "refund_amount", "stock_value"].includes(key)) return formatMoney(raw);
  return String(raw);
}

function isStatusKey(key: string) {
  return key.includes("status") || key === "current_status" || key === "direction";
}

function toOptions(rows: AnyRecord[] | undefined, valueKey: string, labelKeys: string[]) {
  return (rows || []).map(row => ({
    value: Number(row[valueKey]),
    label: labelKeys.map(key => String(row[key] || "")).filter(Boolean).join(" · ") || String(row[valueKey]),
  }));
}

function warehouseQuery(path: string) {
  return () => api<AnyRecord | AnyRecord[]>(path);
}

export function WarehousePage({ notify, section }: WarehousePageProps) {
  const queryClient = useQueryClient();
  const [materialQueryText, setMaterialQueryText] = useState("");
  const [unitStatus, setUnitStatus] = useState("");
  const [requestStatus, setRequestStatus] = useState("");

  const dashboard = useQuery({ queryKey: ["warehouse-dashboard"], queryFn: warehouseQuery("/api/warehouse/dashboard") });
  const overview = useQuery({ queryKey: ["warehouse-overview"], queryFn: warehouseQuery("/api/warehouse") });
  const materials = useQuery({ queryKey: ["warehouse-materials", materialQueryText], queryFn: warehouseQuery(`/api/materials${materialQueryText ? `?q=${encodeURIComponent(materialQueryText)}` : ""}`) });
  const batches = useQuery({ queryKey: ["warehouse-batches"], queryFn: warehouseQuery("/api/material-batches") });
  const units = useQuery({ queryKey: ["warehouse-units", unitStatus], queryFn: warehouseQuery(`/api/material-units${unitStatus ? `?status=${encodeURIComponent(unitStatus)}` : ""}`) });
  const requests = useQuery({ queryKey: ["warehouse-requests", requestStatus], queryFn: warehouseQuery(`/api/material-requests${requestStatus ? `?status=${encodeURIComponent(requestStatus)}` : ""}`) });
  const returns = useQuery({ queryKey: ["warehouse-returns"], queryFn: warehouseQuery("/api/material-returns") });
  const counts = useQuery({ queryKey: ["warehouse-counts"], queryFn: warehouseQuery("/api/stock-counts") });
  const adjustments = useQuery({ queryKey: ["warehouse-adjustments"], queryFn: warehouseQuery("/api/stock-adjustments") });
  const movements = useQuery({ queryKey: ["warehouse-movements"], queryFn: warehouseQuery("/api/stock-movements") });

  const overviewData = (overview.data || {}) as AnyRecord;
  const materialRows = ((materials.data as AnyRecord | undefined)?.materials as AnyRecord[] | undefined) || [];
  const materialOptions = useMemo(() => toOptions(materialRows.length ? materialRows : overviewData.materials as AnyRecord[], "material_id", ["material_code", "name"]), [materialRows, overviewData.materials]);
  const categoryOptions = useMemo(() => toOptions(overviewData.categories as AnyRecord[], "category_id", ["category_code", "name"]), [overviewData.categories]);
  const locationOptions = useMemo(() => toOptions(overviewData.locations as AnyRecord[], "location_id", ["location_code", "name"]), [overviewData.locations]);
  const areaOptions = useMemo(() => toOptions(overviewData.areas as AnyRecord[], "area_id", ["area_code", "name"]), [overviewData.areas]);

  const invalidateWarehouse = () => {
    ["warehouse-dashboard", "warehouse-overview", "warehouse-materials", "warehouse-batches", "warehouse-units", "warehouse-requests", "warehouse-returns", "warehouse-counts", "warehouse-adjustments", "warehouse-movements"].forEach(key => {
      queryClient.invalidateQueries({ queryKey: [key] });
    });
  };

  const mutation = useMutation({
    mutationFn: ({ path, payload }: { path: string; payload?: AnyRecord }) => api(path, { method: "POST", body: payload ? JSON.stringify(payload) : undefined }),
    onSuccess: () => {
      notify("仓库操作已完成");
      invalidateWarehouse();
    },
    onError: error => notify(error instanceof Error ? error.message : "仓库操作失败", true),
  });

  const loading = dashboard.isLoading || overview.isLoading;
  const error = dashboard.error || overview.error;
  if (loading || error) return <QueryState loading={loading} error={error} />;

  const metrics = ((dashboard.data as AnyRecord | undefined)?.metrics || {}) as AnyRecord;
  const lowStock = ((dashboard.data as AnyRecord | undefined)?.low_stock as AnyRecord[] | undefined) || [];

  if (section === "warehouseMaterials") return <MaterialsTab rows={materialRows} categoryOptions={categoryOptions} locationOptions={locationOptions} queryText={materialQueryText} setQueryText={setMaterialQueryText} mutation={mutation} />;
  if (section === "warehouseBatches") return <BatchesTab rows={batches.data as AnyRecord[]} materialOptions={materialOptions} locationOptions={locationOptions} mutation={mutation} loading={batches.isLoading} error={batches.error} />;
  if (section === "warehouseUnits") return <UnitsTab rows={units.data as AnyRecord[]} status={unitStatus} setStatus={setUnitStatus} mutation={mutation} loading={units.isLoading} error={units.error} />;
  if (section === "warehouseRequests") return <RequestsTab rows={requests.data as AnyRecord[]} materialOptions={materialOptions} status={requestStatus} setStatus={setRequestStatus} mutation={mutation} loading={requests.isLoading} error={requests.error} />;
  if (section === "warehouseReturns") return <ReturnsTab rows={returns.data as AnyRecord[]} mutation={mutation} loading={returns.isLoading} error={returns.error} />;
  if (section === "warehouseCounts") return <CountsTab counts={counts.data as AnyRecord[]} adjustments={adjustments.data as AnyRecord[]} materialOptions={materialOptions} locationOptions={locationOptions} mutation={mutation} loading={counts.isLoading || adjustments.isLoading} error={counts.error || adjustments.error} />;
  if (section === "warehouseMovements") return <TablePanel loading={movements.isLoading} error={movements.error} title="库存流水" rows={movements.data as AnyRecord[]} columns={[["happened_at", "时间"], ["movement_type", "类型"], ["direction", "方向"], ["material_code", "物料代码"], ["name", "物料"], ["unit_code", "单件码"], ["qty", "数量"], ["unit_cost", "成本"], ["actor", "操作人"], ["order_no", "工单"]]} />;
  if (section === "warehouseBasics") return <BasicsTab categories={overviewData.categories as AnyRecord[]} areas={overviewData.areas as AnyRecord[]} locations={overviewData.locations as AnyRecord[]} areaOptions={areaOptions} mutation={mutation} />;

  return (
    <div className="stack">
      <AppPanel
        title="库存看板"
        note="维修物料仓库存金额、预警、待处理单据和近期流水。"
        action={<AppButton onClick={invalidateWarehouse}><RefreshCw size={16} />刷新</AppButton>}
      >
        <Row gutter={[12, 12]}>
          <Metric title="库存金额" value={formatMoney(metrics.stock_value)} />
          <Metric title="在库件数" value={String(metrics.available_qty || 0)} />
          <Metric title="低库存" value={String(metrics.low_stock_count || 0)} />
          <Metric title="待审批/发放" value={`${metrics.pending_request_count || 0}`} />
          <Metric title="待退料验收" value={String(metrics.pending_return_count || 0)} />
          <Metric title="今日出入库" value={`${metrics.today_in_qty || 0} / ${metrics.today_out_qty || 0}`} />
        </Row>
        {lowStock.length > 0 && <Alert className="warehouse-alert" type="warning" showIcon message={`低库存：${lowStock.slice(0, 3).map(row => `${row.name} ${row.current_qty}/${row.min_qty}`).join("，")}`} />}
      </AppPanel>
      <div className="dashboard-grid">
        <TablePanel title="待审批申领" rows={((dashboard.data as AnyRecord).pending_requests as AnyRecord[]) || []} columns={[["request_no", "申领单"], ["engineer_user", "工程师"], ["created_at", "时间"], ["remark", "备注"]]} />
        <TablePanel title="待退料验收" rows={((dashboard.data as AnyRecord).pending_returns as AnyRecord[]) || []} columns={[["return_id", "退料单"], ["unit_code", "单件码"], ["name", "物料"], ["engineer_user", "工程师"]]} />
      </div>
      <TablePanel title="近期库存流水" rows={((dashboard.data as AnyRecord).recent_movements as AnyRecord[]) || []} columns={[["happened_at", "时间"], ["movement_type", "类型"], ["direction", "方向"], ["material_code", "物料代码"], ["name", "物料"], ["qty", "数量"], ["actor", "操作人"]]} />
    </div>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return <Card className="warehouse-metric"><Statistic title={title} value={value} /></Card>;
}

function TablePanel({ title, rows, columns, loading, error, actions }: { title: string; rows?: AnyRecord[]; columns: Array<[string, string]>; loading?: boolean; error?: unknown; actions?: { title?: string; render: (row: AnyRecord, index: number) => ReactNode } }) {
  if (loading || error) return <QueryState loading={!!loading} error={error} />;
  return <AppPanel title={title}><AppTable rows={rows || []} columns={columns} actions={actions} formatValue={displayValue} isStatusKey={isStatusKey} /></AppPanel>;
}

function MaterialsTab({ rows, categoryOptions, locationOptions, queryText, setQueryText, mutation }: { rows: AnyRecord[]; categoryOptions: Array<{ value: number; label: string }>; locationOptions: Array<{ value: number; label: string }>; queryText: string; setQueryText: (value: string) => void; mutation: WarehouseMutation }) {
  return (
    <div className="stack">
      <AppPanel title="新增/更新物料" note="SKU 相同会更新物料档案。">
        <WarehouseForm
          loading={mutation.isPending}
          fields={[
            { name: "sku", label: "SKU", required: true },
            { name: "material_code", label: "物料代码" },
            { name: "name", label: "物料名称", required: true },
            { name: "category_id", label: "类别", options: categoryOptions },
            { name: "default_location_id", label: "默认库位", options: locationOptions },
            { name: "brand", label: "品牌" },
            { name: "spec", label: "规格" },
            { name: "compatible_range", label: "适配范围" },
            { name: "min_qty", label: "低库存线", number: true },
            { name: "avg_cost", label: "参考成本", number: true },
            { name: "remark", label: "备注", wide: true },
          ]}
          onSubmit={payload => mutation.mutate({ path: "/api/materials", payload })}
        />
      </AppPanel>
      <AppPanel title="物料档案" action={<Input.Search placeholder="搜索 SKU/名称/适配范围" allowClear value={queryText} onChange={event => setQueryText(event.target.value)} />}>
        <AppTable rows={rows} columns={[["material_id", "ID"], ["material_code", "物料代码"], ["sku", "SKU"], ["name", "物料"], ["category_name", "类别"], ["default_location_code", "默认库位"], ["compatible_range", "适配"], ["current_qty", "可用"], ["min_qty", "低库存"], ["avg_cost", "均价"], ["status", "状态"]]} formatValue={displayValue} isStatusKey={isStatusKey} />
      </AppPanel>
    </div>
  );
}

function BatchesTab({ rows, materialOptions, locationOptions, mutation, loading, error }: { rows: AnyRecord[]; materialOptions: Array<{ value: number; label: string }>; locationOptions: Array<{ value: number; label: string }>; mutation: WarehouseMutation; loading?: boolean; error?: unknown }) {
  return (
    <div className="stack">
      <AppPanel title="采购/临采入库">
        <WarehouseForm
          loading={mutation.isPending}
          fields={[
            { name: "batch_kind", label: "入库类型", options: [{ value: "purchase", label: "采购入库" }, { value: "ad-hoc", label: "临采入库" }], initialValue: "purchase" },
            { name: "material_id", label: "物料", options: materialOptions, required: true },
            { name: "location_id", label: "库位", options: locationOptions },
            { name: "supplier", label: "供应商", initialValue: "待确认" },
            { name: "purchase_no", label: "采购单号" },
            { name: "qty", label: "数量", number: true, required: true, initialValue: 1 },
            { name: "unit_cost", label: "单价", number: true },
            { name: "remark", label: "备注", wide: true },
          ]}
          onSubmit={payload => {
            const kind = String(payload.batch_kind || "purchase");
            const { batch_kind, ...rest } = payload;
            mutation.mutate({ path: `/api/material-batches/${kind}`, payload: rest });
          }}
        />
      </AppPanel>
      <TablePanel
        title="入库批次"
        loading={loading}
        error={error}
        rows={rows}
        columns={[["batch_id", "ID"], ["batch_no", "批次号"], ["purchase_type", "类型"], ["material_code", "物料代码"], ["name", "物料"], ["location_code", "库位"], ["qty", "入库"], ["remaining_qty", "剩余"], ["unit_cost", "单价"], ["supplier", "供应商"], ["payment_status", "付款"]]}
        actions={{ render: row => <AppButton onClick={() => mutation.mutate({ path: `/api/material-batches/${row.batch_id}/return`, payload: { qty: 1, refund_status: "待确认" } })}>退货1件</AppButton> }}
      />
    </div>
  );
}

function UnitsTab({ rows, status, setStatus, mutation, loading, error }: { rows: AnyRecord[]; status: string; setStatus: (value: string) => void; mutation: WarehouseMutation; loading?: boolean; error?: unknown }) {
  return <TablePanel title="单件码" loading={loading} error={error} rows={rows} columns={[["unit_id", "ID"], ["unit_code", "单件码"], ["current_status", "状态"], ["material_code", "物料代码"], ["name", "物料"], ["batch_no", "批次"], ["location_code", "库位"], ["engineer_user", "工程师"], ["order_no", "工单"], ["unit_cost", "成本"]]} actions={{ title: <Select allowClear placeholder="状态筛选" value={status || undefined} options={statusOptions.map(value => ({ value, label: value }))} onChange={value => setStatus(value || "")} /> as unknown as string, render: row => ["已发放", "已使用", "拆回待检"].includes(String(row.current_status)) ? <AppButton onClick={() => mutation.mutate({ path: `/api/material-issues/${row.unit_id}/return-request`, payload: { return_type: "工程师退料" } })}>发起退料</AppButton> : null }} />;
}

function RequestsTab({ rows, materialOptions, status, setStatus, mutation, loading, error }: { rows: AnyRecord[]; materialOptions: Array<{ value: number; label: string }>; status: string; setStatus: (value: string) => void; mutation: WarehouseMutation; loading?: boolean; error?: unknown }) {
  return (
    <div className="stack">
      <AppPanel title="创建申领单">
        <WarehouseForm
          loading={mutation.isPending}
          fields={[
            { name: "repair_order_id", label: "维修工单 ID", number: true },
            { name: "engineer_user", label: "工程师账号" },
            { name: "material_id", label: "物料", options: materialOptions, required: true },
            { name: "qty", label: "数量", number: true, initialValue: 1 },
            { name: "remark", label: "备注", wide: true },
          ]}
          onSubmit={payload => mutation.mutate({ path: "/api/material-requests", payload: { repair_order_id: payload.repair_order_id || null, engineer_user: payload.engineer_user || "", items: [{ material_id: payload.material_id, qty: payload.qty || 1, remark: payload.remark || "" }], remark: payload.remark || "" } })}
        />
      </AppPanel>
      <AppPanel title="申领单" action={<Select allowClear placeholder="状态筛选" value={status || undefined} options={requestStatusOptions.map(value => ({ value, label: value }))} onChange={value => setStatus(value || "")} />}>
        <QueryState loading={!!loading} error={error} />
        {!loading && !error && <AppTable rows={rows} columns={[["request_id", "ID"], ["request_no", "申领单"], ["status", "状态"], ["engineer_user", "工程师"], ["order_no", "工单"], ["created_at", "创建时间"], ["remark", "备注"]]} formatValue={displayValue} isStatusKey={isStatusKey} actions={{ render: row => <Space><AppButton disabled={row.status !== "待审核"} onClick={() => mutation.mutate({ path: `/api/material-requests/${row.request_id}/approve`, payload: {} })}>审批</AppButton><AppButton disabled={row.status !== "已审核待发放"} onClick={() => mutation.mutate({ path: `/api/material-requests/${row.request_id}/issue`, payload: {} })}>发放</AppButton><AppButton disabled={!["待审核", "已审核待发放"].includes(String(row.status))} onClick={() => mutation.mutate({ path: `/api/material-requests/${row.request_id}/cancel`, payload: { remark: "页面取消" } })}>取消</AppButton></Space> }} />}
      </AppPanel>
    </div>
  );
}

function ReturnsTab({ rows, mutation, loading, error }: { rows: AnyRecord[]; mutation: WarehouseMutation; loading?: boolean; error?: unknown }) {
  return <TablePanel title="退料验收" loading={loading} error={error} rows={rows} columns={[["return_id", "ID"], ["status", "状态"], ["return_type", "类型"], ["unit_code", "单件码"], ["material_code", "物料代码"], ["name", "物料"], ["engineer_user", "工程师"], ["order_no", "工单"], ["created_at", "创建时间"], ["inspect_result", "验收结果"]]} actions={{ render: row => row.status === "待验收" ? <Space>{returnResults.map(result => <AppButton key={result} onClick={() => mutation.mutate({ path: `/api/material-returns/${row.return_id}/inspect`, payload: { inspect_result: result, remark: `页面验收：${result}` } })}>{result}</AppButton>)}</Space> : null }} />;
}

function CountsTab({ counts, adjustments, materialOptions, locationOptions, mutation, loading, error }: { counts: AnyRecord[]; adjustments: AnyRecord[]; materialOptions: Array<{ value: number; label: string }>; locationOptions: Array<{ value: number; label: string }>; mutation: WarehouseMutation; loading?: boolean; error?: unknown }) {
  return (
    <div className="stack">
      <AppPanel title="创建盘点单">
        <WarehouseForm
          loading={mutation.isPending}
          fields={[
            { name: "material_id", label: "物料", options: materialOptions, required: true },
            { name: "location_id", label: "库位", options: locationOptions },
            { name: "actual_qty", label: "实盘数量", number: true, required: true },
            { name: "reason", label: "差异原因" },
            { name: "remark", label: "盘点备注", wide: true },
          ]}
          onSubmit={payload => mutation.mutate({ path: "/api/stock-counts", payload: { items: [{ material_id: payload.material_id, location_id: payload.location_id || null, actual_qty: payload.actual_qty || 0, reason: payload.reason || "" }], remark: payload.remark || "" } })}
        />
      </AppPanel>
      <AppPanel title="库存调整/报损">
        <WarehouseForm
          loading={mutation.isPending}
          fields={[
            { name: "material_id", label: "物料", options: materialOptions, required: true },
            { name: "location_id", label: "库位", options: locationOptions },
            { name: "adjustment_type", label: "调整类型", options: adjustmentTypes.map(value => ({ value, label: value })), required: true },
            { name: "qty", label: "数量", number: true, required: true, initialValue: 1 },
            { name: "reason", label: "原因", wide: true },
          ]}
          onSubmit={payload => mutation.mutate({ path: "/api/stock-adjustments", payload })}
        />
      </AppPanel>
      <TablePanel title="盘点单" loading={loading} error={error} rows={counts} columns={[["count_id", "ID"], ["count_no", "盘点单"], ["status", "状态"], ["item_count", "物料数"], ["diff_qty", "差异"], ["counted_by", "盘点人"], ["created_at", "创建时间"]]} actions={{ render: row => <AppButton disabled={row.status !== "草稿"} onClick={() => mutation.mutate({ path: `/api/stock-counts/${row.count_id}/confirm` })}>确认盘点</AppButton> }} />
      <TablePanel title="调整记录" loading={loading} error={error} rows={adjustments} columns={[["adjustment_no", "调整单"], ["adjustment_type", "类型"], ["material_code", "物料代码"], ["name", "物料"], ["qty", "数量"], ["location_code", "库位"], ["operator", "操作人"], ["reason", "原因"], ["created_at", "时间"]]} />
    </div>
  );
}

function BasicsTab({ categories, areas, locations, areaOptions, mutation }: { categories: AnyRecord[]; areas: AnyRecord[]; locations: AnyRecord[]; areaOptions: Array<{ value: number; label: string }>; mutation: WarehouseMutation }) {
  return (
    <div className="stack">
      <AppPanel title="新增类别/库区/库位">
        <div className="dashboard-grid">
          <WarehouseForm loading={mutation.isPending} fields={[{ name: "category_code", label: "类别代码" }, { name: "name", label: "类别名称", required: true }, { name: "remark", label: "备注", wide: true }]} onSubmit={payload => mutation.mutate({ path: "/api/material-categories", payload })} />
          <WarehouseForm loading={mutation.isPending} fields={[{ name: "area_code", label: "库区代码" }, { name: "name", label: "库区名称", required: true }, { name: "remark", label: "备注", wide: true }]} onSubmit={payload => mutation.mutate({ path: "/api/warehouse/areas", payload })} />
          <WarehouseForm loading={mutation.isPending} fields={[{ name: "area_id", label: "所属库区", options: areaOptions }, { name: "location_code", label: "库位代码" }, { name: "name", label: "库位名称", required: true }, { name: "remark", label: "备注", wide: true }]} onSubmit={payload => mutation.mutate({ path: "/api/warehouse/locations", payload })} />
        </div>
      </AppPanel>
      <TablePanel title="物料类别" rows={categories} columns={[["category_code", "代码"], ["name", "名称"], ["remark", "备注"]]} />
      <TablePanel title="库区" rows={areas} columns={[["area_code", "代码"], ["name", "名称"], ["status", "状态"], ["remark", "备注"]]} />
      <TablePanel title="库位" rows={locations} columns={[["location_code", "代码"], ["name", "名称"], ["area_code", "库区"], ["status", "状态"], ["remark", "备注"]]} />
    </div>
  );
}

type WarehouseField = {
  name: string;
  label: string;
  required?: boolean;
  number?: boolean;
  wide?: boolean;
  initialValue?: string | number;
  options?: Array<{ value: string | number; label: string }>;
};

function WarehouseForm({ fields, onSubmit, loading }: { fields: WarehouseField[]; onSubmit: (payload: AnyRecord) => void; loading?: boolean }) {
  const [form] = Form.useForm();
  return (
    <Form
      className="app-form-section"
      form={form}
      layout="vertical"
      onFinish={values => {
        onSubmit(values);
        form.resetFields();
      }}
    >
      <div className="app-form-section-grid">
        {fields.map(field => (
          <Form.Item key={field.name} className={field.wide ? "wide" : undefined} name={field.name} label={field.label} initialValue={field.initialValue} rules={field.required ? [{ required: true, message: `请填写${field.label}` }] : undefined}>
            {field.options ? <Select allowClear showSearch optionFilterProp="label" options={field.options} /> : field.number ? <InputNumber min={0} precision={field.name.includes("cost") || field.name.includes("amount") ? 2 : 0} style={{ width: "100%" }} /> : <Input />}
          </Form.Item>
        ))}
      </div>
      <div className="app-form-section-actions">
        <AppButton htmlType="submit" loading={loading} type="primary">保存</AppButton>
        <AppButton onClick={() => form.resetFields()}>清空</AppButton>
      </div>
    </Form>
  );
}
