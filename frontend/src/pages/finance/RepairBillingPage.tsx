import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Input, InputNumber, Select } from "antd";
import { Calculator, Database, FileSpreadsheet, Plus, Save, Trash2, UploadCloud } from "lucide-react";

import { AnyRecord, api } from "../../api";
import { AppButton } from "../../components/actions/AppButton";
import { AppTable } from "../../components/data/AppTable";
import { QueryState } from "../../components/data/QueryState";
import { AppPanel } from "../../components/layout/AppPanel";

type EmployeeRule = { name: string; base_salary: number; commission_rate: number; subsidy: number; deduction: number };
type Policy = { eligible_statuses: string[]; employee_rules: EmployeeRule[]; sales_commission_rate: number; partner_name: string; partner_share_rate: number; operating_expense: number };

const emptyPolicy: Policy = { eligible_statuses: ["维修完成"], employee_rules: [], sales_commission_rate: 0.05, partner_name: "鲁明涛", partner_share_rate: 0.5, operating_expense: 0 };

function money(value: unknown) { return Number(value || 0).toLocaleString("zh-CN", { style: "currency", currency: "CNY", minimumFractionDigits: 2 }); }
function percent(value: unknown) { return `${(Number(value || 0) * 100).toFixed(2).replace(/\.00$/, "")}%`; }
function display(row: AnyRecord, key: string) {
  const value = row[key];
  if (["order_profit", "base_salary", "commission", "subsidy", "deduction", "gross_pay", "net_pay"].includes(key)) return money(value);
  if (key.includes("rate") || key === "gross_margin") return percent(value);
  return value === null || value === undefined || value === "" ? "-" : String(value);
}
function policyFrom(value: unknown): Policy {
  const raw = (value || {}) as Partial<Policy>;
  return { eligible_statuses: raw.eligible_statuses || emptyPolicy.eligible_statuses, employee_rules: raw.employee_rules || [], sales_commission_rate: Number(raw.sales_commission_rate ?? 0.05), partner_name: String(raw.partner_name ?? "鲁明涛"), partner_share_rate: Number(raw.partner_share_rate ?? 0.5), operating_expense: Number(raw.operating_expense ?? 0) };
}

function FinanceResult({ result, filename }: { result: AnyRecord; filename?: string }) {
  const summary = (result.summary as AnyRecord | undefined) || {};
  const source = (result.source as AnyRecord | undefined) || {};
  const payroll = (result.payroll as AnyRecord[] | undefined) || [];
  const sales = (result.sales as AnyRecord[] | undefined) || [];
  const statuses = (result.status_summary as AnyRecord[] | undefined) || [];
  const issues = (result.issues as AnyRecord[] | undefined) || [];
  const cards: Array<[string, string | number, string]> = [
    ["结算订单", Number(summary.order_count || 0), "单"], ["营收", money(summary.revenue), ""], ["直接成本", money(summary.direct_cost), ""], ["订单毛利", money(summary.gross_profit), percent(summary.gross_margin)],
    ["应发工资", money(summary.labor_expense), ""], ["销售提成", money(summary.sales_commission), ""], ["分润前利润", money(summary.profit_before_share), ""], ["公司留存利润", money(summary.retained_profit), ""],
  ];
  return <>
    <div className={`billing-result-banner ${result.can_finalize ? "ready" : "blocked"}`}><FileSpreadsheet size={24} /><div><strong>{result.can_finalize ? "检查通过，可以结算" : `发现 ${String(result.error_count || 0)} 个阻断项，当前不能结算`}</strong><span>{filename || String(source.filename || "")} · 原始 {String(source.total_rows || 0)} 单 · 纳入 {String(source.accepted_orders || 0)} 单 · 排除 {String(source.excluded_orders || 0)} 单</span></div></div>
    <section className="billing-summary-grid">{cards.map(([label, value, note]) => <div className="billing-summary-card" key={label}><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>)}</section>
    <AppPanel title="工资结算" note={`实发工资合计 ${money(summary.cash_payroll)}；财务利润使用应发工资 ${money(summary.labor_expense)}。`}><AppTable rows={payroll} columns={[["name", "姓名"], ["order_count", "订单"], ["order_profit", "订单利润"], ["base_salary", "基础工资"], ["commission_rate", "提成比例"], ["commission", "应发提成"], ["subsidy", "补贴"], ["deduction", "扣款"], ["gross_pay", "应发"], ["net_pay", "实发"]]} formatValue={display} isStatusKey={() => false} /></AppPanel>
    <div className="billing-two-column"><AppPanel title="销售提成" note="销售提成先从利润中扣除，再计算合作分润。"><AppTable rows={sales} columns={[["name", "销售"], ["order_count", "订单"], ["order_profit", "销售利润"], ["commission_rate", "比例"], ["commission", "提成"]]} formatValue={display} isStatusKey={() => false} empty="没有销售归属数据" /></AppPanel><AppPanel title="状态口径" note="只有基础设置中指定的状态才计入结算。"><AppTable rows={statuses} columns={[["status", "订单状态"], ["count", "数量"], ["included", "结算口径"]]} formatValue={(row, key) => key === "included" ? (row.included ? "纳入" : "排除") : display(row, key)} isStatusKey={key => key === "included"} /></AppPanel></div>
    <AppPanel title="数据校准结果" note={`阻断项 ${String(result.error_count || 0)} 条，提示 ${String(result.warning_count || 0)} 条。`}><AppTable rows={issues} columns={[["severity", "级别"], ["row", "Excel行"], ["order_id", "订单ID"], ["message", "问题"]]} formatValue={(row, key) => key === "severity" ? (row.severity === "error" ? "阻断" : "提示") : display(row, key)} isStatusKey={key => key === "severity"} empty="未发现数据问题" /></AppPanel>
  </>;
}

export function RepairBillingSettingsPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["repair-finance-settings"], queryFn: () => api<AnyRecord>("/api/finance/repair-billing/settings") });
  const [policy, setPolicy] = useState<Policy>(emptyPolicy);
  const [statuses, setStatuses] = useState("维修完成");
  useEffect(() => { if (query.data) { const next = policyFrom(query.data.policy); setPolicy(next); setStatuses(next.eligible_statuses.join("，")); } }, [query.data]);
  const save = useMutation({ mutationFn: () => api<AnyRecord>("/api/finance/repair-billing/settings", { method: "PUT", body: JSON.stringify({ ...policy, eligible_statuses: statuses.split(/[,，]/).map(item => item.trim()).filter(Boolean) }) }), onSuccess: async () => { notify("基础设置已保存"); await qc.invalidateQueries({ queryKey: ["repair-finance-settings"] }); }, onError: error => notify(error instanceof Error ? error.message : "保存失败", true) });
  const updateEmployee = (index: number, key: keyof EmployeeRule, value: string | number | null) => setPolicy(current => ({ ...current, employee_rules: current.employee_rules.map((row, i) => i === index ? { ...row, [key]: key === "name" ? String(value || "") : Number(value || 0) } : row) }));
  return <div className="repair-billing-page"><AppPanel title="维修结算基础设置" note="设置保存后长期生效；每个上传批次还会保存一份当时的规则快照。"><QueryState loading={query.isLoading} error={query.error} />
    <div className="billing-policy-grid"><label><span>纳入结算的状态</span><Input value={statuses} onChange={event => setStatuses(event.target.value)} /></label><label><span>销售提成比例 (%)</span><InputNumber min={0} max={100} precision={2} value={policy.sales_commission_rate * 100} onChange={value => setPolicy(current => ({ ...current, sales_commission_rate: Number(value || 0) / 100 }))} /></label><label><span>合作分润人</span><Input value={policy.partner_name} onChange={event => setPolicy(current => ({ ...current, partner_name: event.target.value }))} /></label><label><span>合作分润比例 (%)</span><InputNumber min={0} max={100} precision={2} value={policy.partner_share_rate * 100} onChange={value => setPolicy(current => ({ ...current, partner_share_rate: Number(value || 0) / 100 }))} /></label><label><span>其他经营支出</span><InputNumber min={0} precision={2} value={policy.operating_expense} onChange={value => setPolicy(current => ({ ...current, operating_expense: Number(value || 0) }))} /></label></div>
    <section className="billing-rule-section"><div className="billing-section-heading"><div><h3>员工工资规则</h3><p>应发工资计入人工成本，扣款只影响实发金额。</p></div><AppButton onClick={() => setPolicy(current => ({ ...current, employee_rules: [...current.employee_rules, { name: "", base_salary: 0, commission_rate: 0, subsidy: 0, deduction: 0 }] }))}><Plus size={15} />添加员工</AppButton></div><div className="billing-rule-table"><div className="billing-rule-header"><span>姓名</span><span>基础工资</span><span>提成比例</span><span>补贴</span><span>扣款</span><span></span></div>{policy.employee_rules.map((rule, index) => <div className="billing-rule-row" key={`${index}-${rule.name}`}><Input value={rule.name} onChange={event => updateEmployee(index, "name", event.target.value)} /><InputNumber min={0} precision={2} value={rule.base_salary} onChange={value => updateEmployee(index, "base_salary", value)} /><InputNumber min={0} max={100} precision={2} value={rule.commission_rate * 100} onChange={value => updateEmployee(index, "commission_rate", Number(value || 0) / 100)} addonAfter="%" /><InputNumber min={0} precision={2} value={rule.subsidy} onChange={value => updateEmployee(index, "subsidy", value)} /><InputNumber min={0} precision={2} value={rule.deduction} onChange={value => updateEmployee(index, "deduction", value)} /><AppButton danger type="text" onClick={() => setPolicy(current => ({ ...current, employee_rules: current.employee_rules.filter((_, i) => i !== index) }))}><Trash2 size={16} /></AppButton></div>)}</div></section>
    <div className="billing-calculate-action"><AppButton type="primary" size="large" loading={save.isPending} onClick={() => save.mutate()}><Save size={18} />保存基础设置</AppButton></div></AppPanel></div>;
}

export function RepairBillingUploadPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const qc = useQueryClient(); const [file, setFile] = useState<File | null>(null);
  const settings = useQuery({ queryKey: ["repair-finance-settings"], queryFn: () => api<AnyRecord>("/api/finance/repair-billing/settings") });
  const upload = useMutation({ mutationFn: async () => { if (!file) throw new Error("请先选择订单明细 .xlsx 文件"); const body = new FormData(); body.append("file", file); return api<AnyRecord>("/api/finance/repair-billing/analyze", { method: "POST", body }); }, onSuccess: async result => { notify(result.can_finalize ? "批次已保存，可以结算" : "批次已保存，请处理校准问题"); await qc.invalidateQueries({ queryKey: ["repair-finance-batches"] }); }, onError: error => notify(error instanceof Error ? error.message : "上传失败", true) });
  const policy = policyFrom(settings.data?.policy);
  return <div className="repair-billing-page"><AppPanel title="上传与数据校准" note="上传后立即校验并保存为历史批次；修正原表后可再次上传，不会覆盖旧批次。"><div className="billing-upload-layout"><label className="billing-upload-card"><UploadCloud size={34} /><strong>{file ? file.name : "选择订单明细"}</strong><span>{file ? `${(file.size / 1024).toFixed(1)} KB` : "支持 .xlsx，最大10MB"}</span><input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={event => setFile(event.target.files?.[0] || null)} /></label><div className="billing-policy-snapshot"><strong>当前结算规则</strong><span>状态：{policy.eligible_statuses.join("、")}</span><span>员工规则：{policy.employee_rules.length} 人</span><span>销售提成：{percent(policy.sales_commission_rate)}</span><span>合作分润：{policy.partner_name || "未设置"} / {percent(policy.partner_share_rate)}</span></div></div><QueryState loading={settings.isLoading || upload.isPending} error={settings.error || upload.error} /><div className="billing-calculate-action"><AppButton type="primary" size="large" loading={upload.isPending} disabled={!file || settings.isLoading} onClick={() => upload.mutate()}><Calculator size={18} />上传、校准并保存</AppButton></div></AppPanel>{upload.data && <FinanceResult result={upload.data} filename={file?.name} />}</div>;
}

export function RepairBillingDataPage() {
  const batches = useQuery({ queryKey: ["repair-finance-batches"], queryFn: () => api<AnyRecord[]>("/api/finance/repair-billing/batches") });
  const [batchId, setBatchId] = useState<number | null>(null);
  useEffect(() => { if (!batchId && batches.data?.length) setBatchId(Number(batches.data[0].batch_id)); }, [batchId, batches.data]);
  const detail = useQuery({ queryKey: ["repair-finance-batch", batchId], queryFn: () => api<AnyRecord>(`/api/finance/repair-billing/batches/${batchId}`), enabled: Boolean(batchId) });
  const selected = detail.data; const result = selected ? ({ ...((selected.result as AnyRecord) || {}), issues: selected.issues || [] } as AnyRecord) : null;
  return <div className="repair-billing-page"><AppPanel title="维修结算数据" note="所有上传结果按批次保存，可随时追溯文件、规则快照、财务结果和校准问题。"><div className="billing-history-toolbar"><Database size={22} /><Select value={batchId || undefined} onChange={value => setBatchId(Number(value))} placeholder="选择结算批次" options={(batches.data || []).map(row => ({ value: Number(row.batch_id), label: `#${row.batch_id} ${row.filename} · ${row.created_at} · ${row.status === "ready" ? "可结算" : "待校准"}` }))} /></div><QueryState loading={batches.isLoading || detail.isLoading} error={batches.error || detail.error} />{!batches.isLoading && !batches.data?.length && <div className="billing-empty-history">暂无结算数据，请先到“上传与数据校准”创建批次。</div>}</AppPanel>{selected && result && <><div className="billing-persisted-meta">批次 #{String(selected.batch_id)} · 上传人 {String(selected.created_by || "-")} · 保存时间 {String(selected.created_at || "-")}</div><FinanceResult result={result} /></>}</div>;
}
