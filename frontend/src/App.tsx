import { ReactNode, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Input, Select } from "antd";
import {
  BarChart3,
  Bell,
  Boxes,
  ClipboardList,
  CreditCard,
  Grid2X2,
  HelpCircle,
  Info,
  LogOut,
  Mail,
  Megaphone,
  PackageSearch,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShoppingBag,
  Smartphone,
  TimerOff,
  UserRound,
  Wrench,
  ArrowRightLeft,
  ArrowLeft,
  BadgeCheck,
  Camera,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CirclePlus,
  CircleDollarSign,
  Download,
  Edit3,
  FileText,
  Filter,
  Flag,
  Home,
  ReceiptText,
  UserPlus,
  Users,
} from "lucide-react";
import { AnyRecord, api, clearStoredUser, formPayload, getStoredUser, setStoredUser } from "./api";
import { AppButton } from "./components/actions/AppButton";
import { AppTable } from "./components/data/AppTable";
import { QueryState as AntdQueryState } from "./components/data/QueryState";
import { StatusTag } from "./components/data/StatusTag";
import { AppModal } from "./components/feedback/AppModal";
import { notify as feedbackNotify } from "./components/feedback/notify";
import { AppFormSection } from "./components/forms/AppFormSection";
import { AppPanel } from "./components/layout/AppPanel";

type ViewKey = "dashboard" | "repairPool" | "orderDetail" | "recyclePool" | "repair" | "recycle" | "warehouse" | "inventory" | "sales" | "customers" | "payments" | "reports" | "audit";
type OrderMode = "new" | "view" | "edit" | "cancel";
type SortState = { key: string; direction: "asc" | "desc" };

const viewMeta: Record<ViewKey, { label: string; subtitle: string }> = {
  dashboard: { label: "工作台首页", subtitle: "欢迎回来，沐辰科技 MIS 正在平稳运行中。" },
  repairPool: { label: "维修工单池", subtitle: "集中查看维修工单、待补资料、挂账和财务确认。" },
  orderDetail: { label: "工单详情", subtitle: "查看维修工单的设备、客户、检测、报价和进度。" },
  recyclePool: { label: "回收工单池", subtitle: "跟进回收机器、入库和销售流转。" },
  repair: { label: "维修开单", subtitle: "创建维修单并推进检测、报价、交付和收款。" },
  recycle: { label: "回收开单", subtitle: "创建回收单，完成验机报价、付款入库和定价。" },
  warehouse: { label: "库存管理", subtitle: "管理物料、批次、单件码、申领发放、退料和库存流水。" },
  inventory: { label: "回收库存", subtitle: "查看维修物料库存与回收机器库存。" },
  sales: { label: "快速卖机", subtitle: "从回收库存创建销售单。" },
  customers: { label: "客户", subtitle: "查询客户主数据。" },
  payments: { label: "财务流水", subtitle: "登记维修、销售收入和回收支出。" },
  reports: { label: "财务报表", subtitle: "查看库存成本、收入支出和经营概览。" },
  audit: { label: "系统设置", subtitle: "查看关键写操作的审计记录。" },
};

const primaryNav: Array<{ key: ViewKey; label: string; icon: ReactNode }> = [
  { key: "dashboard", label: "个人工作台", icon: <Grid2X2 size={22} /> },
  { key: "repairPool", label: "订单中心", icon: <ClipboardList size={22} /> },
  { key: "warehouse", label: "库存管理", icon: <Wrench size={22} /> },
  { key: "reports", label: "财务报表", icon: <BarChart3 size={22} /> },
  { key: "audit", label: "系统设置", icon: <Settings size={22} /> },
];

const moneyKeys = new Set(["quoted_amount", "cost_amount", "charge_amount", "paid_amount", "pay_amount", "sale_price", "amount", "inventory_cost", "avg_cost", "unit_cost", "total_cost", "refund_amount"]);
const modelOptions = ["iPhone 16", "iPhone 16 Pro", "iPhone 16 Pro Max", "iPhone 15", "iPhone 15 Pro", "iPhone 15 Pro Max", "iPhone 14", "iPhone 14 Pro", "iPhone 14 Pro Max", "iPhone 13", "iPhone 13 Pro", "iPhone 13 Pro Max", "iPhone 12"];
const memoryOptions = ["64GB", "128GB", "256GB", "512GB", "1TB"];
const colorOptions = ["黑色", "白色", "蓝色", "绿色", "粉色", "黄色", "紫色", "红色", "银色", "金色", "深空灰", "午夜色", "星光色", "原色钛金属", "黑色钛金属", "白色钛金属"];
const conditionOptions = ["外观良好", "轻微磕碰", "屏幕破损", "进水", "不开机", "待检测"];

function formatMoney(input: unknown) {
  const amount = Number(input || 0);
  return `¥${amount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function uniqueStrings(values: unknown[]) {
  return Array.from(new Set(values.flatMap(value => Array.isArray(value) ? value : [value]).map(value => String(value || "").trim()).filter(Boolean)));
}

function optionArray(value: unknown) {
  return Array.isArray(value) ? value.map(item => String(item || "")).filter(Boolean) : [];
}

function hasTextValue(value: unknown) {
  return String(value ?? "").trim().length > 0;
}

function digitsOnly(value: unknown) {
  return String(value ?? "").replace(/\D/g, "");
}

function normalizeLookupText(value: unknown) {
  return String(value ?? "").trim().toLowerCase();
}

function nameMatches(row: AnyRecord, query: string) {
  const needle = normalizeLookupText(query);
  if (!needle) return false;
  return normalizeLookupText(row.name || row.customer_name).includes(needle);
}

function phoneMatches(row: AnyRecord, query: string) {
  const rawQuery = String(query ?? "");
  const rawPhone = String(row.phone || row.customer_phone || "");
  const needle = digitsOnly(rawQuery);
  const phone = digitsOnly(rawPhone);
  if (!needle || !phone) return false;
  if (phone.includes(needle)) return true;

  const queryChunks = rawQuery.split(/\*+/).map(digitsOnly).filter(Boolean);
  if (queryChunks.length > 1 && chunksMatch(phone, queryChunks)) return true;

  const storedChunks = rawPhone.split(/\*+/).map(digitsOnly).filter(Boolean);
  return storedChunks.length > 1 && chunksMatch(needle, storedChunks);
}

function chunksMatch(target: string, chunks: string[]) {
  let cursor = 0;
  return chunks.every(chunk => {
    if (!chunk) return true;
    if (chunk.length > target.length) return false;
    const next = target.indexOf(chunk, cursor);
    if (next === -1) return false;
    cursor = next + chunk.length;
    return true;
  });
}

function customerLookupRequestKeyword(anchor: "name" | "phone", keyword: string) {
  if (anchor !== "phone") return keyword;
  const digits = digitsOnly(keyword);
  return digits.length >= 7 ? digits.slice(0, 3) : keyword;
}

function firstNumber(...values: unknown[]) {
  const found = values.find(value => value !== null && value !== undefined && value !== "");
  return Number(found ?? 0);
}

function hasValue(row: AnyRecord, key: string) {
  return row[key] !== null && row[key] !== undefined && row[key] !== "";
}

function repairLineAmounts(row: AnyRecord) {
  const unitCost = firstNumber(row.cost_amount, row.total_cost, row.unit_cost);
  const hasSplitAmounts = hasValue(row, "cost_amount") || hasValue(row, "charge_amount");
  const serviceFee = hasSplitAmounts ? firstNumber(row.charge_amount) : Math.max(firstNumber(row.amount, row.price) - unitCost, 0);
  const lineAmount = hasSplitAmounts ? unitCost + serviceFee : firstNumber(row.amount, row.price, unitCost);
  return { unitCost, serviceFee, lineAmount };
}

function formatOrderNote(type: string, content: string) {
  return `【${type || "内部备注"}】${content.trim()}`;
}

function parseOrderNotes(remark: unknown) {
  return String(remark || "")
    .split(/\n+/)
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => {
      const match = line.match(/^【(.+?)】(.+)$/);
      return { type: match?.[1] || "内部备注", content: match?.[2] || line };
    });
}

function nowText() {
  return new Date().toLocaleString("zh-CN", { hour12: false });
}

function splitOptionText(value: unknown) {
  return String(value || "").split(/[\n,，、]/).map(item => item.trim()).filter(Boolean);
}

function displayValue(row: AnyRecord, key: string) {
  const raw = row[key];
  if (raw === null || raw === undefined || raw === "") return "-";
  if (moneyKeys.has(key)) return formatMoney(raw);
  if (Array.isArray(raw)) return raw.join("、") || "-";
  return String(raw);
}


function Panel({ title, note, action, children }: { title: string; note?: string; action?: ReactNode; children: ReactNode }) {
  return <AppPanel title={title} note={note} action={action}>{children}</AppPanel>;
}

function DataTable({ rows, columns, onRowClick, empty = "暂无数据", defaultSort }: { rows?: AnyRecord[]; columns: Array<[string, string]>; onRowClick?: (row: AnyRecord) => void; empty?: string; defaultSort?: SortState }) {
  return (
    <AppTable
      rows={rows}
      columns={columns}
      empty={empty}
      onRowClick={onRowClick}
      defaultSort={defaultSort}
      formatValue={displayValue}
      isStatusKey={(key) => key.includes("status") || key === "state"}
    />
  );
}

export function compactPageItems(currentPage: number, totalPages: number) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);
  const pages = new Set([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);
  const sorted = Array.from(pages).filter(page => page >= 1 && page <= totalPages).sort((a, b) => a - b);
  return sorted.flatMap((page, index) => {
    const previous = sorted[index - 1];
    return previous && page - previous > 1 ? ["ellipsis", page] : [page];
  });
}

function QueryState({ loading, error }: { loading: boolean; error: unknown }) {
  if (!loading && !error) return null;
  return <AntdQueryState loading={loading} error={error} />;
}

function App() {
  const [user, setUser] = useState(getStoredUser());
  const [view, setView] = useState<ViewKey>("dashboard");
  const [selectedRepairOrderId, setSelectedRepairOrderId] = useState<number | string | null>(null);
  const [detailReturnView, setDetailReturnView] = useState<ViewKey>("repairPool");
  const [orderMode, setOrderMode] = useState<OrderMode>("view");
  const [modal, setModal] = useState<ReactNode | null>(null);
  const queryClient = useQueryClient();
  const current = viewMeta[view];
  const profile = useQuery({ queryKey: ["me", user], queryFn: () => api<AnyRecord>("/api/me"), enabled: Boolean(user) });

  function notify(message: string, error = false) {
    if (error) feedbackNotify.error(message);
    else feedbackNotify.success(message);
  }

  function logout() {
    clearStoredUser();
    setUser("");
    setView("dashboard");
    queryClient.clear();
  }

  function openOrderDetail(row: AnyRecord, from: ViewKey = view, mode: OrderMode = "view") {
    const id = row.repair_order_id;
    if (!id) {
      notify("当前演示行没有绑定真实工单，无法打开详情。", true);
      return;
    }
    setSelectedRepairOrderId(id as number | string);
    setOrderMode(mode);
    setDetailReturnView(from === "orderDetail" ? "repairPool" : from);
    setView("orderDetail");
  }

  function leaveOrderDetail() {
    setView(detailReturnView || "repairPool");
  }

  function openNewOrder(from: ViewKey = view) {
    setSelectedRepairOrderId(null);
    setOrderMode("new");
    setDetailReturnView(from === "orderDetail" ? "repairPool" : from);
    setView("orderDetail");
  }

  if (!user) return <LoginScreen onLogin={(name) => { setStoredUser(name); setUser(name); }} notify={notify} />;

  return (
    <div className={`app-shell ${view === "orderDetail" || view === "repair" ? "order-detail-shell" : ""} ${view === "repairPool" ? "repair-pool-shell" : ""}`}>
      <aside className="sidebar">
        <div className="brand"><div><strong>沐辰科技</strong><span>专业维修与销售</span></div></div>
        <nav className="primary-nav">
          {primaryNav.map(item => (
            <button key={item.key} className={view === item.key || (view === "orderDetail" && item.key === "repairPool") ? "active" : ""} onClick={() => setView(item.key)} type="button">
              {item.icon}{item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button type="button" className="plain-nav-button"><HelpCircle size={20} />帮助中心</button>
          <button type="button" className="plain-nav-button" onClick={logout}><LogOut size={20} />退出登录</button>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="top-search"><Search size={22} /><Input variant="borderless" placeholder="快捷搜索工单、机型或零件..." /></div>
          <div className="top-links">
            <button type="button" onClick={() => setView("warehouse")}>设备入库</button>
            <button type="button" onClick={() => setView("sales")}>快速卖机</button>
          </div>
          <div className="top-icons">
            <button type="button" className="icon-button"><Bell size={23} /><span /></button>
            <button type="button" className="icon-button"><Mail size={23} /></button>
          </div>
          <div className="admin-chip">
            <div><strong>{String(profile.data?.username || user) === "admin" ? "管理员" : String(profile.data?.username || user)}</strong><span>{String(profile.data?.role || "高级维修顾问")}</span></div>
            <div className="avatar-dot"><UserRound size={19} /></div>
          </div>
        </header>
        {view !== "dashboard" && view !== "orderDetail" && view !== "repairPool" && view !== "repair" && <div className="page-title"><h1>{current.label}</h1><p>{current.subtitle}</p></div>}
        <ViewRouter view={view} notify={notify} openModal={setModal} setView={setView} openNewOrder={openNewOrder} openOrderDetail={openOrderDetail} selectedRepairOrderId={selectedRepairOrderId} orderMode={orderMode} setSelectedRepairOrderId={setSelectedRepairOrderId} setOrderMode={setOrderMode} onLeaveOrderDetail={leaveOrderDetail} />
      </main>
      <AppModal open={Boolean(modal)} onClose={() => setModal(null)}>{modal}</AppModal>
    </div>
  );
}

function LoginScreen({ onLogin, notify }: { onLogin: (username: string) => void; notify: (message: string, error?: boolean) => void }) {
  const mutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/login", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: data => onLogin(String(data.username || "")),
    onError: error => notify(error instanceof Error ? error.message : "登录失败", true),
  });
  return (
    <section className="auth-screen">
      <form className="auth-card" onSubmit={(event) => { event.preventDefault(); mutation.mutate(formPayload(event.currentTarget)); }}>
        <div className="brand auth-brand"><div className="brand-mark">M</div><div><strong>沐辰科技 MIS</strong><span>机器生命周期工作台</span></div></div>
        <div><h1>登录工作台</h1><p>进入维修、回收、仓库、销售与财务的一体化操作界面。</p></div>
        <label><span>账号</span><Input name="username" defaultValue="admin" autoComplete="username" /></label>
        <label><span>密码</span><Input.Password name="password" defaultValue="admin" autoComplete="current-password" /></label>
        <AppButton type="primary" htmlType="submit" loading={mutation.isPending} block>{mutation.isPending ? "登录中..." : "登录"}</AppButton>
        <p className="auth-hint">演示账号：admin/admin、frontdesk/frontdesk、engineer/engineer、finance/finance、boss/boss</p>
      </form>
    </section>
  );
}

function ViewRouter({
  view,
  notify,
  openModal,
  setView,
  openNewOrder,
  openOrderDetail,
  selectedRepairOrderId,
  orderMode,
  setSelectedRepairOrderId,
  setOrderMode,
  onLeaveOrderDetail,
}: {
  view: ViewKey;
  notify: (message: string, error?: boolean) => void;
  openModal: (node: ReactNode | null) => void;
  setView: (view: ViewKey) => void;
  openNewOrder: (from?: ViewKey) => void;
  openOrderDetail: (row: AnyRecord, from?: ViewKey, mode?: OrderMode) => void;
  selectedRepairOrderId: number | string | null;
  orderMode: OrderMode;
  setSelectedRepairOrderId: (id: number | string | null) => void;
  setOrderMode: (mode: OrderMode) => void;
  onLeaveOrderDetail: () => void;
}) {
  if (view === "dashboard") return <DashboardHome notify={notify} setView={setView} openOrderDetail={(row) => openOrderDetail(row, "dashboard")} />;
  if (view === "orderDetail") return <OrderDetailPage orderId={selectedRepairOrderId} mode={orderMode} notify={notify} onBack={onLeaveOrderDetail} onCreated={(id) => { setSelectedRepairOrderId(id); setOrderMode("view"); }} onModeChange={setOrderMode} />;
  if (view === "repairPool") return <RepairPool notify={notify} setView={setView} openNewOrder={() => openNewOrder("repairPool")} openOrderDetail={(row, mode) => openOrderDetail(row, "repairPool", mode)} />;
  if (view === "recyclePool") return <RecyclePool openModal={openModal} />;
  if (view === "warehouse") return <WarehousePage notify={notify} />;
  if (view === "inventory") return <InventoryPage />;
  if (view === "customers") return <CustomersPage />;
  if (view === "payments") return <PaymentsPage notify={notify} />;
  if (view === "reports") return <ReportsPage />;
  if (view === "audit") return <AuditPage notify={notify} />;
  if (view === "repair") return <OrderDetailPage orderId={null} mode="new" notify={notify} onBack={() => setView("repairPool")} onCreated={(id) => { setSelectedRepairOrderId(id); setOrderMode("view"); setView("orderDetail"); }} onModeChange={setOrderMode} />;
  if (view === "recycle") return <RecycleOpenPage notify={notify} />;
  return <SalesPage notify={notify} />;
}

function DashboardHome({ notify, setView, openOrderDetail }: { notify: (message: string, error?: boolean) => void; setView: (view: ViewKey) => void; openOrderDetail: (row: AnyRecord) => void }) {
  const [tab, setTab] = useState<"orders" | "approvals" | "finance">("orders");
  const repair = useQuery({ queryKey: ["repair-workbench"], queryFn: () => api<AnyRecord>("/api/repair-workbench") });
  const warehouse = useQuery({ queryKey: ["warehouse"], queryFn: () => api<AnyRecord>("/api/warehouse") });
  const payments = useQuery({ queryKey: ["payments"], queryFn: () => api<AnyRecord[]>("/api/payments") });
  const reports = useQuery({ queryKey: ["machine-reports"], queryFn: () => api<AnyRecord>("/api/machine-reports") });
  const loading = repair.isLoading || warehouse.isLoading || payments.isLoading || reports.isLoading;
  const error = repair.error || warehouse.error || payments.error || reports.error;
  const orders = ((repair.data?.orders as AnyRecord[] | undefined) || []);
  const openOrders = orders.filter(row => !["已完结", "已结单"].includes(String(row.status))).slice(0, 4);
  const financePending = ((repair.data?.finance_pending as AnyRecord[] | undefined) || []);
  const requests = ((warehouse.data?.requests as AnyRecord[] | undefined) || []).filter(row => !["已发放", "已取消", "已拒绝"].includes(String(row.status))).slice(0, 4);
  const todayIncome = (payments.data || []).filter(row => row.direction === "收入").reduce((sum, row) => sum + Number(row.amount || 0), 0);
  const todayExpense = (payments.data || []).filter(row => row.direction === "支出").reduce((sum, row) => sum + Number(row.amount || 0), 0);
  const active = orders.filter(row => String(row.status).includes("维修")).length;
  const done = orders.filter(row => ["已完结", "已结单", "维修完成"].includes(String(row.status))).length;
  const pending = Math.max(openOrders.length, orders.filter(row => ["新建", "待检测", "待报价确认", "待交付检测"].includes(String(row.status))).length);
  const monthlyIncome = ((reports.data?.payment_totals as AnyRecord[] | undefined) || []).find(row => row.direction === "收入")?.amount || todayIncome;
  const inventoryCost = Number(reports.data?.inventory_cost || 0);
  const lowStock = ((warehouse.data?.low_stock as AnyRecord[] | undefined) || []);

  function openRepairDetail(row: AnyRecord) {
    openOrderDetail(row);
  }

  function refreshAll() {
    repair.refetch();
    warehouse.refetch();
    payments.refetch();
    reports.refetch();
  }

  if (loading || error) return <QueryState loading={loading} error={error} />;

  return (
    <div className="home-page">
      <div className="home-heading">
        <div><h1>工作台首页</h1><p>欢迎回来，沐辰科技 MIS 正在平稳运行中。</p></div>
        <button type="button" className="refresh-button" onClick={refreshAll}><RefreshCw size={18} />刷新数据</button>
      </div>

      <section className="insight-grid">
        <div className="insight-card revenue-card">
          <div className="insight-top"><div className="insight-icon"><CreditCard size={28} /></div><span className="trend">↗ +12.5%</span></div>
          <p>今日订单金额 (CNY)</p>
          <strong>{formatMoney(todayIncome || 45280)}</strong>
        </div>
        <div className="insight-card status-card">
          <div className="card-title-row"><p>订单状态实时</p><b>共 {orders.length || 24} 单</b></div>
          <div className="status-cluster">
            <div><strong className="warning-text">{pending || 8}</strong><span>待处理</span></div>
            <div><strong className="primary-text">{active || 12}</strong><span>维修中</span></div>
            <div><strong className="success-text">{done || 4}</strong><span>已完成</span></div>
          </div>
        </div>
        <div className="insight-card finance-card">
          <div className="card-title-row"><p>今日财务收支</p><CreditCard size={24} /></div>
          <div className="money-line"><span>当日收款</span><b className="success-text">+ {formatMoney(todayIncome || 32100)}</b></div>
          <div className="money-line"><span>当日支出</span><b className="danger-text">- {formatMoney(todayExpense || 8400)}</b></div>
        </div>
        <div className="insight-card month-card">
          <div className="card-title-row"><p>本月累计概览</p><span className="live-pill">实时更新</span></div>
          <span>总营收</span>
          <strong>{formatMoney(monthlyIncome || 1204500)}</strong>
          <div className="month-profit"><span>净利润</span><b>{formatMoney(Number(monthlyIncome || 0) - inventoryCost || 342000)}</b></div>
        </div>
      </section>

      <section className="home-layout">
        <div className="todo-card">
          <div className="todo-tabs">
            <button type="button" className={tab === "orders" ? "active" : ""} onClick={() => setTab("orders")}>未完成订单</button>
            <button type="button" className={tab === "approvals" ? "active" : ""} onClick={() => setTab("approvals")}>未完成审批</button>
            <button type="button" className={tab === "finance" ? "active" : ""} onClick={() => setTab("finance")}>财务待处理</button>
          </div>
          {tab === "orders" && <TodoOrders rows={openOrders} onOpen={openRepairDetail} />}
          {tab === "approvals" && <TodoApprovals rows={requests} setView={setView} />}
          {tab === "finance" && <TodoFinance rows={financePending} setView={setView} />}
        </div>
        <div className="right-stack">
          <InventoryAlerts lowStock={lowStock} setView={setView} />
          <WorkMessages financeCount={financePending.length} requestCount={requests.length} />
        </div>
      </section>
    </div>
  );
}

function TodoOrders({ rows, onOpen }: { rows: AnyRecord[]; onOpen: (row: AnyRecord) => void }) {
  const fallback: AnyRecord[] = [
    { order_no: "#MC-20231024-01", model: "iPhone 15 Pro Max", status: "\u7ef4\u4fee\u4e2d", priority: "\u7d27\u6025" },
    { order_no: "#MC-20231024-05", model: "MacBook Air M2", status: "\u5f85\u5206\u914d", priority: "\u666e\u901a" },
    { order_no: "#MC-20231023-12", model: "Huawei Mate 60 Pro", status: "\u7ef4\u4fee\u4e2d", priority: "\u5ef6\u671f" },
    { order_no: "#MC-20231024-09", model: "iPad Pro 12.9", status: "\u5f85\u5907\u6599", priority: "\u666e\u901a" },
  ];
  const data = rows.length ? rows : fallback;
  return (
    <AppTable
      rows={data}
      columns={[["order_no", "\u5de5\u5355\u7f16\u53f7"], ["model", "\u7ef4\u4fee\u673a\u578b"], ["status", "\u72b6\u6001"], ["priority", "\u7d27\u6025\u7a0b\u5ea6"]]}
      formatValue={(row, key) => {
        if (key === "order_no") return String(row.order_no || row.machine_no || "-");
        if (key === "model") return String(row.model || row.fault_description || "-");
        if (key === "status") return String(row.status || "\u5f85\u5904\u7406");
        if (key === "priority") return String(row.priority || "\u666e\u901a");
        return displayValue(row, key);
      }}
      isStatusKey={(key) => key === "status"}
      renderers={{
        priority: (row) => {
          const value = String(row.priority || "\u666e\u901a");
          const tone = value.includes("\u7d27\u6025") ? "danger-text" : value.includes("\u5ef6\u671f") ? "muted-text" : "warning-text";
          return <span className={'priority ' + tone}>{value}</span>;
        },
      }}
      actions={{
        title: "\u64cd\u4f5c",
        render: (row, index) => <AppButton type="link" className="link-button" onClick={() => onOpen(row)}>{index === 1 ? "\u5904\u7406" : index === 3 ? "\u5907\u6599" : "\u8be6\u60c5"}</AppButton>,
      }}
    />
  );
}

function TodoApprovals({ rows, setView }: { rows: AnyRecord[]; setView: (view: ViewKey) => void }) {
  const data = rows.length ? rows : [
    { request_no: "MR-待审-01", engineer_user: "张三", remark: "iPhone 14 电池 x5，尾插 x2", status: "待审核" },
    { request_no: "RT-待审-02", engineer_user: "门店 A", remark: "零件质量问题，待退货审核", status: "待处理" },
  ];
  return <div className="approval-list">{data.map((row, index) => <div className="approval-item" key={String(row.request_id || row.request_no || index)}><div><b>{String(row.request_no || "审批单")} - {String(row.engineer_user || "待确认")}</b><span>{String(row.remark || row.status || "待处理")}</span></div><button type="button" onClick={() => setView("warehouse")}>处理</button></div>)}</div>;
}

function TodoFinance({ rows, setView }: { rows: AnyRecord[]; setView: (view: ViewKey) => void }) {
  const data = rows.length ? rows : [
    { order_no: "SL-9821 / SL-9822", customer_name: "待确认入账", amount: 12400 },
    { order_no: "供应商付款", customer_name: "华强电子城旗舰店", amount: 45000 },
  ];
  return <div className="approval-list">{data.map((row, index) => <div className="approval-item" key={String(row.payment_id || row.order_no || index)}><div><b>{String(row.customer_name || "财务待处理")}</b><span>{String(row.order_no || "业务单据")} · {formatMoney(row.amount)}</span></div><button type="button" onClick={() => setView("payments")}>确认</button></div>)}</div>;
}

function InventoryAlerts({ lowStock, setView }: { lowStock: AnyRecord[]; setView: (view: ViewKey) => void }) {
  const rows = [
    { kind: "danger", title: "缺料预警 (低库存)", note: lowStock[0] ? `${String(lowStock[0].name || lowStock[0].material_code)} x${String(lowStock[0].current_qty ?? 0)}` : "iPhone 13 屏幕总成 x2", action: "补货" },
    { kind: "warning", title: "呆滞物料 (周转慢)", note: "旧款 iPad 硅胶壳 x45", tail: "180天+" },
    { kind: "primary", title: "高库存提醒", note: "Type-C 充电头 x200", tail: "超额 40%" },
  ];
  return <section className="side-card"><div className="side-card-title"><Boxes size={26} /><h3>库存预警</h3><Info size={22} /></div><div className="alert-list">{rows.map(row => <div className={`alert-item ${row.kind}`} key={row.title}><span className="alert-dot" /><div><b>{row.title}</b><p>{row.note}</p></div>{row.action ? <button type="button" onClick={() => setView("warehouse")}>{row.action}</button> : <em>{row.tail}</em>}</div>)}</div></section>;
}

function WorkMessages({ financeCount, requestCount }: { financeCount: number; requestCount: number }) {
  const rows = [
    { icon: <Megaphone size={18} />, title: "系统公告", note: "国庆期间营业时间调整通知...", time: "10:30", kind: "primary" },
    { icon: <TimerOff size={18} />, title: "订单超期预警", note: `当前有 ${financeCount || 2} 条财务/订单待处理`, time: "09:15", kind: "danger" },
    { icon: <ArrowRightLeft size={18} />, title: "物料转派通知", note: `当前有 ${requestCount || 1} 条物料申请需要关注`, time: "昨天", kind: "success" },
  ];
  return <section className="side-card message-card"><div className="side-card-title"><Mail size={26} /><h3>工作消息</h3><button type="button">全部已读</button></div>{rows.map(row => <div className="message-item" key={row.title}><div className={`message-icon ${row.kind}`}>{row.icon}</div><div><div><b>{row.title}</b><span>{row.time}</span></div><p>{row.note}</p></div></div>)}</section>;
}

function RepairPool({ notify, openOrderDetail, openNewOrder }: { notify: (message: string, error?: boolean) => void; openOrderDetail: (row: AnyRecord, mode?: OrderMode) => void; openNewOrder?: () => void; setView?: (view: ViewKey) => void }) {
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("全部状态");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;
  const query = useQuery({ queryKey: ["repair-workbench"], queryFn: () => api<AnyRecord>("/api/repair-workbench") });
  const orders = ((query.data?.orders as AnyRecord[] | undefined) || []);
  const rows = useMemo(() => {
    const q = keyword.trim().toLowerCase();
    return orders.filter(row => {
      const haystack = [row.order_no, row.machine_no, row.imei, row.serial, row.model, row.customer_name, row.phone, row.customer_phone, row.assigned_to].join(" ").toLowerCase();
      return (!q || haystack.includes(q)) && (status === "全部状态" || normalizeRepairStatus(row.status) === status);
    });
  }, [keyword, orders, status]);
  const repairing = orders.filter(row => normalizeRepairStatus(row.status) === "维修中").length;
  const paidWaiting = orders.filter(row => normalizeRepairStatus(row.status) === "待支付").length;
  const done = orders.filter(row => normalizeRepairStatus(row.status) === "已完结").length;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const startIndex = rows.length ? (safePage - 1) * pageSize : 0;
  const visibleRows = rows.slice(startIndex, startIndex + pageSize);
  const pageItems = compactPageItems(safePage, totalPages);

  useEffect(() => {
    setCurrentPage(1);
  }, [keyword, status]);

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages);
  }, [currentPage, totalPages]);

  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;

  return (
    <div className="repair-pool-page">
      <header className="pool-topbar">
        <div className="pool-global-search"><Search size={23} /><Input variant="borderless" placeholder="全局搜索 (订单号, 配件, IMEI)..." /></div>
        <div className="pool-top-actions">
          <button type="button" className="pool-icon-button"><Bell size={23} /><span /></button>
          <button type="button" className="pool-icon-button"><HelpCircle size={23} /></button>
          <div className="pool-user"><div><b>陈经理</b><span>管理员</span></div><div className="pool-avatar"><UserRound size={22} /></div></div>
        </div>
      </header>

      <div className="pool-content">
        <nav className="pool-breadcrumb"><span>维修管理</span><ChevronRight size={16} /><b>维修订单池</b></nav>

        <section className="pool-stat-grid">
          <PoolStat icon={<ReceiptText size={25} />} tone="primary" label="全部工单" value={orders.length || 1284} note="+12%" />
          <PoolStat icon={<Wrench size={25} />} tone="warning" label="维修中" value={repairing || 42} note="进行中" />
          <PoolStat icon={<CircleDollarSign size={25} />} tone="danger" label="待支付" value={paidWaiting || 15} note="紧急" />
          <PoolStat icon={<BadgeCheck size={25} />} tone="success" label="今日完结" value={done || 28} note="新增" />
        </section>

        <section className="pool-actionbar">
          <div className="pool-filter-left">
            <Input className="pool-search-input" prefix={<Search size={20} />} value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="搜索订单号、IMEI 或客户手机..." allowClear />
            <Select className="pool-status-select" value={status} onChange={setStatus} options={["全部状态", "维修中", "待支付", "已完结", "已取消"].map(value => ({ value, label: value }))} />
            <AppButton className="pool-ghost-button" onClick={() => notify("高级筛选已按设计预留，当前可用搜索和状态筛选。")}><Filter size={20} />高级筛选</AppButton>
          </div>
          <div className="pool-filter-right">
            <AppButton className="pool-ghost-button" onClick={() => notify("导出数据入口已预留。")}><Download size={20} />导出数据</AppButton>
            <AppButton className="pool-primary-button" type="primary" onClick={() => openNewOrder?.()}><Plus size={22} />新建工单</AppButton>
          </div>
        </section>

        <section className="pool-table-card">
          <div className="pool-table-scroll">
            <table className="pool-table">
              <thead><tr><th>订单编号</th><th>设备信息</th><th>客户</th><th>状态</th><th>技术员</th><th>最后更新</th><th className="align-right">预估金额</th><th className="align-center">操作</th></tr></thead>
              <tbody>
                {visibleRows.map((row, index) => <PoolOrderRow row={row} key={String(row.repair_order_id || row.order_no || index)} onOpen={openOrderDetail} notify={notify} />)}
                {!visibleRows.length && <tr><td colSpan={8}><div className="pool-empty">没有找到匹配的维修工单</div></td></tr>}
              </tbody>
            </table>
          </div>
          <div className="pool-pagination">
            <span>显示第 <b>{visibleRows.length ? startIndex + 1 : 0} - {visibleRows.length ? startIndex + visibleRows.length : 0}</b> 条，共 <b>{rows.length}</b> 条工单</span>
            <div>
              <button type="button" disabled={safePage <= 1} onClick={() => setCurrentPage(page => Math.max(1, page - 1))}><ChevronLeft size={22} /></button>
              {pageItems.map((item, index) => item === "ellipsis" ? (
                <em key={`ellipsis-${index}`}>...</em>
              ) : (
                <button type="button" key={item} className={safePage === item ? "active" : ""} onClick={() => setCurrentPage(Number(item))}>{item}</button>
              ))}
              <button type="button" disabled={safePage >= totalPages} onClick={() => setCurrentPage(page => Math.min(totalPages, page + 1))}><ChevronRight size={22} /></button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function PoolStat({ icon, tone, label, value, note }: { icon: ReactNode; tone: "primary" | "warning" | "danger" | "success"; label: string; value: number; note: string }) {
  return <div className="pool-stat-card"><div className="pool-stat-top"><div className={`pool-stat-icon ${tone}`}>{icon}</div><span className={tone}>{note}</span></div><p>{label}</p><strong>{value.toLocaleString("zh-CN")}</strong></div>;
}

function PoolOrderRow({ row, onOpen, notify }: { row: AnyRecord; onOpen: (row: AnyRecord, mode?: OrderMode) => void; notify: (message: string, error?: boolean) => void }) {
  const status = normalizeRepairStatus(row.status);
  const phone = String(row.phone || row.customer_phone || "");
  const imei = String(row.imei || row.serial || row.machine_no || "");
  return (
    <tr>
      <td><button type="button" className="pool-order-link" onClick={() => onOpen(row, "view")}>{String(row.order_no || row.repair_order_id || "-")}</button></td>
      <td><div className="pool-device-cell"><b>{String(row.model || "待补机型")}</b><span>IMEI: {maskCode(imei)}</span></div></td>
      <td><div className="pool-customer-cell"><b>{String(row.customer_name || "未关联客户")}</b><span>{maskPhone(phone)}</span></div></td>
      <td><StatusTag value={status} /></td>
      <td>{String(row.assigned_to || row.engineer_user || "--")}</td>
      <td className="muted">{String(row.updated_at || row.created_at || "--")}</td>
      <td className="align-right"><b>{poolMoney(row.quoted_amount || row.charge_amount || row.amount || 0)}</b></td>
      <td className="align-center"><div className="pool-row-actions"><button type="button" onClick={() => onOpen(row, "view")}>详情</button><button type="button" onClick={() => onOpen(row, "edit")}>编辑</button>{status === "待支付" && <button type="button" className="danger" onClick={() => notify("取消入口已预留。")}>取消</button>}</div></td>
    </tr>
  );
}

function normalizeRepairStatus(input: unknown) {
  const text = String(input || "");
  if (text.includes("取消") || text.includes("作废")) return "已取消";
  if (text.includes("完") || text.includes("结") || text.includes("交付")) return "已完结";
  if (text.includes("支付") || text.includes("收款") || text.includes("财务") || text.includes("挂账")) return "待支付";
  return "维修中";
}

export function maskCode(value: string) {
  if (!value) return "-";
  if (value.length <= 8) return value;
  return `${value.slice(0, 6)}******${value.slice(-3)}`;
}

export function maskPhone(value: string) {
  const digits = value.replace(/\D/g, "");
  if (digits.length < 7) return value || "-";
  return `${digits.slice(0, 3)}****${digits.slice(-4)}`;
}

function poolMoney(input: unknown) {
  const amount = Number(input || 0);
  return `¥${amount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}


function LegacyRepairPool({ notify, openOrderDetail }: { notify: (message: string, error?: boolean) => void; openOrderDetail: (row: AnyRecord) => void }) {
  const [keyword, setKeyword] = useState("");
  const query = useQuery({ queryKey: ["repair-workbench"], queryFn: () => api<AnyRecord>("/api/repair-workbench") });
  const rows = useMemo(() => {
    const q = keyword.trim().toLowerCase();
    return (((query.data?.orders as AnyRecord[] | undefined) || [])).filter(row => !q || [row.order_no, row.machine_no, row.imei, row.model, row.customer_name, row.assigned_to].join(" ").toLowerCase().includes(q));
  }, [keyword, query.data]);

  function openDetail(row: AnyRecord) {
    openOrderDetail(row);
  }

  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;
  return (
    <Panel
      title="?????"
      note="???????????????????????"
      action={<AppButton onClick={() => query.refetch()}><RefreshCw size={16} />取消</AppButton>}
    >
      <div className="toolbar filters">
        <Input allowClear value={keyword} onChange={event => setKeyword(event.target.value)} placeholder="??????IMEI?????..." />
      </div>
      <DataTable rows={rows} onRowClick={openDetail} defaultSort={{ key: "updated_at", direction: "desc" }} columns={[["order_no", "????"], ["model", "????"], ["customer_name", "??"], ["status", "??"], ["assigned_to", "???"], ["updated_at", "????"], ["quoted_amount", "????"]]} />
    </Panel>
  );
}

function RepairDetail({ detail, notify, onChanged }: { detail: AnyRecord; notify: (message: string, error?: boolean) => void; onChanged: () => void }) {
  const [data, setData] = useState(detail);
  const order = data.order as AnyRecord;
  const mutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>(`/api/repair-orders/${order.repair_order_id}/workflow-action`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: next => { setData(next); onChanged(); notify("维修闭环动作已保存"); },
    onError: error => notify(error instanceof Error ? error.message : "操作失败", true),
  });
  function run(action: string) {
    const payload: AnyRecord = { action };
    if (action === "delivered") payload.status = window.prompt("交付状态：已交付 / 待取机 / 待送机 / 待返寄", "已交付") || "已交付";
    if (action === "register_payment") {
      const amount = Number(window.prompt("本次收款金额", "0") || 0);
      if (!amount) return;
      payload.amount = amount;
      payload.method = window.prompt("付款方式", "待确认") || "待确认";
      payload.transaction_no = window.prompt("流水号，未知填待补", "待补") || "待补";
      payload.received_by = getStoredUser() || "前台待确认";
    }
    if (action === "finance_confirm") payload.confirmed_by = window.prompt("财务确认人", getStoredUser() || "待确认") || "待确认";
    mutation.mutate(payload);
  }
  return (
    <>
      <header className="modal-header"><div><h2>工单: {String(order.order_no || order.repair_order_id)}</h2><p>{String(order.status)} · {String(order.payment_status)} · {String(order.customer_name || "未关联客户")}</p></div></header>
      <div className="modal-content">
        <div className="repair-detail-grid"><InfoBlock label="维修机型" text={order.model} /><InfoBlock label="客户描述" text={order.fault_description} /><InfoBlock label="检测结论" text={order.diagnosis} /><InfoBlock label="维修方案" text={order.repair_solution} /></div>
        <div className="detail-actions">{[["repair_completed", "维修完成"], ["delivered", "已交付"], ["register_payment", "登记收款"], ["finance_confirm", "财务确认"], ["close", "订单完结"]].map(([action, label]) => <button key={action} type="button" onClick={() => run(action)}>{label}</button>)}</div>
        <DetailSection title="收入项目" rows={data.income_items as AnyRecord[]} columns={[["item_type", "类型"], ["item_name", "项目"], ["amount", "金额"], ["status", "状态"], ["remark", "备注"]]} />
        <DetailSection title="成本项目" rows={data.cost_items as AnyRecord[]} columns={[["item_type", "类型"], ["item_name", "项目"], ["qty", "数量"], ["unit_cost", "单价"], ["total_cost", "成本"], ["status", "状态"]]} />
        <DetailSection title="付款流水" rows={data.payments as AnyRecord[]} columns={[["payment_id", "流水"], ["amount", "金额"], ["method", "方式"], ["transaction_no", "流水号"], ["status", "状态"], ["received_by", "收款人"], ["confirmed_by", "确认人"]]} />
        <DetailSection title="时间线" rows={data.events as AnyRecord[]} columns={[["created_at", "时间"], ["title", "动作"], ["detail", "内容"], ["operator", "操作人"]]} />
      </div>
    </>
  );
}

function OrderDetailPage({
  orderId,
  mode,
  notify,
  onBack,
  onCreated,
  onModeChange,
}: {
  orderId: number | string | null;
  mode: OrderMode;
  notify: (message: string, error?: boolean) => void;
  onBack: () => void;
  onCreated: (id: number | string) => void;
  onModeChange: (mode: OrderMode) => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<AnyRecord>({});
  const [profileEditing, setProfileEditing] = useState(false);
  const [profileForm, setProfileForm] = useState<AnyRecord>({});
  const [showItemForm, setShowItemForm] = useState(false);
  const [itemForm, setItemForm] = useState<AnyRecord>({ quantity: 1 });
  const [preInspectionState, setPreInspectionState] = useState<Record<string, boolean>>({});
  const [postInspectionState, setPostInspectionState] = useState<Record<string, boolean>>({});
  const [preInspectionEditing, setPreInspectionEditing] = useState(false);
  const [postInspectionEditing, setPostInspectionEditing] = useState(false);
  const [preInspectionSaved, setPreInspectionSaved] = useState(false);
  const [preInspectionNote, setPreInspectionNote] = useState("");
  const [postInspectionNote, setPostInspectionNote] = useState("");
  const [noteFormOpen, setNoteFormOpen] = useState(false);
  const [noteForm, setNoteForm] = useState<AnyRecord>({ type: "内部备注" });
  const [newOrderNotes, setNewOrderNotes] = useState<AnyRecord[]>([]);
  const [newOrderNoteLogs, setNewOrderNoteLogs] = useState<AnyRecord[]>([]);
  const [selectedPhoto, setSelectedPhoto] = useState<AnyRecord | null>(null);
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [customerLookupOpen, setCustomerLookupOpen] = useState(false);
  const [customerLookupAnchor, setCustomerLookupAnchor] = useState<"name" | "phone">("name");
  const [machineLookupOpen, setMachineLookupOpen] = useState(false);
  const [machineLookupAnchor, setMachineLookupAnchor] = useState<"imei" | "serial">("imei");
  const [newRepairItems, setNewRepairItems] = useState<AnyRecord[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<AnyRecord | null>(null);
  const [selectedMachine, setSelectedMachine] = useState<AnyRecord | null>(null);
  const query = useQuery({
    queryKey: ["repair-workbench-detail", orderId],
    queryFn: () => api<AnyRecord>(`/api/repair-workbench/${orderId}`),
    enabled: Boolean(orderId) && mode !== "new",
  });
  const data = query.data || {};
  const order = ((data.order || {}) as AnyRecord);
  const modules = ((data.modules || {}) as AnyRecord);
  const availableActions = new Set(((data.available_actions as string[] | undefined) || []));
  const timelineQuery = useQuery({
    queryKey: ["machine-timeline", order.machine_id],
    queryFn: () => api<AnyRecord>(`/api/machines/${order.machine_id}/timeline`),
    enabled: Boolean(order.machine_id) && mode !== "new",
  });
  const photosQuery = useQuery({
    queryKey: ["repair-order-photos", orderId],
    queryFn: () => api<AnyRecord[]>(`/api/repair-orders/${orderId}/photos`),
    enabled: Boolean(orderId) && mode !== "new",
  });
  const customerLookupKeyword = customerLookupAnchor === "phone" ? String(form.phone || "") : String(form.customer_name || "");
  const customerRequestKeyword = customerLookupRequestKeyword(customerLookupAnchor, customerLookupKeyword);
  const machineLookupKeyword = machineLookupAnchor === "imei" ? String(form.imei || "") : String(form.serial || "");
  const customerSearchQuery = useQuery({
    queryKey: ["order-create-customers", customerLookupAnchor, customerRequestKeyword],
    queryFn: () => api<AnyRecord[]>(`/api/customers?q=${encodeURIComponent(customerRequestKeyword)}`),
    enabled: mode === "new" && customerLookupOpen && hasTextValue(customerLookupKeyword),
  });
  const machineSearchQuery = useQuery({
    queryKey: ["order-create-machines", machineLookupAnchor, machineLookupKeyword],
    queryFn: () => api<AnyRecord[]>(`/api/machines?q=${encodeURIComponent(machineLookupKeyword)}`),
    enabled: mode === "new" && machineLookupOpen && hasTextValue(machineLookupKeyword),
  });
  const repairSkuQuery = useQuery({
    queryKey: ["repair-skus", form.model || ""],
    queryFn: () => api<AnyRecord[]>(`/api/repair-skus?model=${encodeURIComponent(String(form.model || ""))}`),
    enabled: mode === "new" && showItemForm,
  });
  const deviceModelsQuery = useQuery({
    queryKey: ["device-models", "enabled"],
    queryFn: () => api<AnyRecord[]>("/api/device-models?enabled_only=true"),
    enabled: mode === "new" || profileEditing,
  });
  const currentUserQuery = useQuery({ queryKey: ["me", "order-detail"], queryFn: () => api<AnyRecord>("/api/me") });
  const events = ((data.events as AnyRecord[] | undefined) || []);
  const savedInspections = useMemo(() => ((data.inspections as AnyRecord[] | undefined) || []), [data.inspections]);
  const incomeItems = ((data.income_items as AnyRecord[] | undefined) || []);
  const costItems = ((data.cost_items as AnyRecord[] | undefined) || []);
  const repairItems = ((data.repair_items as AnyRecord[] | undefined) || []);
  const payments = ((data.payments as AnyRecord[] | undefined) || []);
  const display = mode === "new" ? form : { ...order, ...form };
  const createdAt = String(order.created_at || order.opened_at || "保存后生成");
  const owner = String(display.assigned_to || order.assigned_to || "未指派");
  const statusText = mode === "new" ? "待创建" : mode === "cancel" ? "取消确认" : normalizeRepairStatus(order.status);
  const model = String(display.model || order.model || "");
  const colorCapacity = [display.color || order.color || "", display.memory || order.memory || order.capacity || ""].filter(Boolean).join(" / ");
  const imei = String(display.imei || order.imei || order.serial || "");
  const customer = String(display.customer_name || order.customer_name || "");
  const phone = String(display.phone || order.phone || order.customer_phone || "");
  const profileDisplay = profileEditing ? { ...display, ...profileForm } : display;
  const profileModel = String(profileDisplay.model || "");
  const profileImei = String(profileDisplay.imei || profileDisplay.serial || "");
  const profileColor = String(profileDisplay.color || "");
  const profileMemory = String(profileDisplay.memory || profileDisplay.capacity || "");
  const profileCustomer = String(profileDisplay.customer_name || "");
  const profilePhone = String(profileDisplay.phone || profileDisplay.customer_phone || "");
  const profileCustomerType = String(profileDisplay.customer_type || order.customer_type || (mode === "new" ? "个人客户" : "零售客户"));
  const newQuoted = newRepairItems.reduce((sum, row) => {
    const { lineAmount } = repairLineAmounts(row);
    return sum + lineAmount * firstNumber(row.quantity, row.qty, 1);
  }, 0);
  const quoted = mode === "new" ? newQuoted : Number(display.quoted_amount || order.quoted_amount || incomeItems.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  const cost = Number(order.cost_amount || costItems.reduce((sum, row) => sum + Number(row.total_cost || row.unit_cost || 0), 0));
  const paid = Number(order.paid_amount || payments.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  const detailRows = mode === "new" ? newRepairItems : repairItems;
  const inspections = ["屏幕显示", "触摸功能", "摄像头", "电池健康", "生物识别", "无线网络", "蜂窝网络", "音频模块", "指南针", "扬声器", "听筒", "充电"];
  const inspectionItems = ["屏幕显示", "触摸功能", "摄像头", "电池健康", "生物识别", "无线网络", "蜂窝网络", "音频模块", "指南针", "扬声器", "听筒", "充电", "其他异常"];
  const canAddRepairItem = mode !== "new" && canModifyRepairItems(statusText);
  const historyOrders = (((timelineQuery.data?.repair_orders as AnyRecord[] | undefined) || []))
    .filter(row => String(row.repair_order_id) !== String(order.repair_order_id || orderId))
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  const photos = ((photosQuery.data as AnyRecord[] | undefined) || []);
  const prePhotos = photos.filter(row => row.stage === "pre");
  const postPhotos = photos.filter(row => row.stage === "post");
  const combinedLogs = mode === "new" ? newOrderNoteLogs : events;
  const visibleLogs = logsExpanded ? combinedLogs : combinedLogs.slice(0, 3);
  const customerOptions = ((customerSearchQuery.data as AnyRecord[] | undefined) || [])
    .filter(row => customerLookupAnchor === "phone" ? phoneMatches(row, customerLookupKeyword) : nameMatches(row, customerLookupKeyword))
    .slice(0, 8);
  const machineOptions = ((machineSearchQuery.data as AnyRecord[] | undefined) || []).slice(0, 8);
  const deviceModels = ((deviceModelsQuery.data as AnyRecord[] | undefined) || []);
  const deviceModelNames = deviceModels.length ? deviceModels.map(row => String(row.model_name || "")).filter(Boolean) : modelOptions;
  const selectedDeviceModel = deviceModels.find(row => String(row.model_name || "") === profileModel);
  const colorChoices = selectedDeviceModel ? optionArray(selectedDeviceModel.colors) : uniqueStrings([colorOptions, ...deviceModels.map(row => optionArray(row.colors))]);
  const memoryChoices = selectedDeviceModel ? optionArray(selectedDeviceModel.capacities) : uniqueStrings([memoryOptions, ...deviceModels.map(row => optionArray(row.capacities))]);
  const persistedNotes = ((data.notes as AnyRecord[] | undefined) || []);
  const orderNotes = mode === "new" ? newOrderNotes : persistedNotes.length ? persistedNotes : parseOrderNotes(order.remark);
  const visibleOrderNotes: AnyRecord[] = orderNotes.length ? orderNotes : [{ type: "内部备注", content: "客户要求尽量保留原厂原色原彩，维修后请务必同步写入数据。", readonly: true }, { type: "交付说明", content: "告知客户外壳磕碰处无法复原，仅保证屏幕功能完好。", readonly: true }];
  const currentOperator = String(currentUserQuery.data?.username || "当前用户");

  useEffect(() => {
    if (mode === "new") return;
    const nextPre: Record<string, boolean> = {};
    const nextPost: Record<string, boolean> = {};
    let nextPreNote = "";
    let nextPostNote = "";
    savedInspections.forEach(row => {
      const item = String(row.item || "");
      const stage = String(row.stage || "");
      if (!item) return;
      if (stage === "pre") {
        nextPre[item] = Boolean(row.abnormal);
        nextPreNote = String(row.note || nextPreNote);
      }
      if (stage === "post") {
        nextPost[item] = Boolean(row.abnormal);
        nextPostNote = String(row.note || nextPostNote);
      }
    });
    setPreInspectionState(nextPre);
    setPostInspectionState(nextPost);
    setPreInspectionNote(nextPreNote || String(order.diagnosis || ""));
    setPostInspectionNote(nextPostNote);
  }, [mode, order.diagnosis, savedInspections]);

  const createMutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/repair-orders", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: data => {
      const next = ((data.order || data) as AnyRecord);
      const id = next.repair_order_id || data.repair_order_id;
      notify("维修工单已创建");
      setForm({});
      setSelectedCustomer(null);
      setSelectedMachine(null);
      setNewRepairItems([]);
      setNewOrderNotes([]);
      setNewOrderNoteLogs([]);
      setPreInspectionSaved(false);
      setNoteFormOpen(false);
      setNoteForm({ type: "内部备注" });
      setCustomerLookupOpen(false);
      setMachineLookupOpen(false);
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
      if (id) onCreated(id as number | string);
    },
    onError: error => notify(error instanceof Error ? error.message : "创建失败", true),
  });
  const editMutation = useMutation({
    mutationFn: async (payload: AnyRecord) => {
      if (!orderId) throw new Error("缺少工单 ID");
      const tasks: Promise<unknown>[] = [];
      if (payload.assigned_to && payload.assigned_to !== order.assigned_to) {
        tasks.push(api(`/api/repair-orders/${orderId}/assign`, { method: "POST", body: JSON.stringify({ engineer_user_id: payload.assigned_to, remark: payload.remark || "" }) }));
      }
      if (payload.quoted_amount !== "" && payload.quoted_amount !== undefined && Number(payload.quoted_amount || 0) !== Number(order.quoted_amount || 0)) {
        tasks.push(api(`/api/repair-orders/${orderId}/price`, { method: "POST", body: JSON.stringify({ quoted_amount: Number(payload.quoted_amount || 0), remark: payload.remark || "" }) }));
      }
      if (payload.repair_item_name) {
        tasks.push(api(`/api/repair-orders/${orderId}/items`, { method: "POST", body: JSON.stringify({ item_name: payload.repair_item_name, quantity: Number(payload.repair_item_qty || 1), cost_amount: Number(payload.repair_item_cost || 0), charge_amount: Number(payload.repair_item_charge || 0), remark: payload.remark || "" }) }));
      }
      if (!tasks.length) return query.data;
      await Promise.all(tasks);
      return api<AnyRecord>(`/api/repair-workbench/${orderId}`);
    },
    onSuccess: () => {
      notify("工单修改已保存");
      setForm({});
      onModeChange("view");
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
    },
    onError: error => notify(error instanceof Error ? error.message : "保存失败", true),
  });
  const profileMutation = useMutation({
    mutationFn: (payload: AnyRecord) => {
      if (!order.machine_id) throw new Error("缺少机器档案，无法编辑设备信息");
      return api<AnyRecord>(`/api/machines/${order.machine_id}`, {
        method: "PUT",
        body: JSON.stringify({
          imei: payload.imei || "",
          serial: payload.serial || order.serial || "",
          model: payload.model || order.model || "待补机型",
          memory: payload.memory || "",
          color: payload.color || "",
          condition: payload.condition || order.condition || "",
          current_status: order.current_status || "维修中",
          customer_id: order.customer_id || null,
          customer: {
            name: payload.customer_name || order.customer_name || "待补",
            phone: payload.phone || payload.customer_phone || "",
            category: payload.customer_type || order.customer_type || "零售客户",
          },
        }),
      });
    },
    onSuccess: () => {
      notify("设备与客户信息已保存");
      setProfileEditing(false);
      setProfileForm({});
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
      queryClient.invalidateQueries({ queryKey: ["machine-timeline", order.machine_id] });
    },
    onError: error => notify(error instanceof Error ? error.message : "保存失败", true),
  });
  const addItemMutation = useMutation({
    mutationFn: (payload: AnyRecord) => {
      if (!orderId) throw new Error("缺少工单 ID");
      return api<AnyRecord>(`/api/repair-orders/${orderId}/items`, {
        method: "POST",
        body: JSON.stringify({
          sku_id: payload.sku_id || null,
          item_name: payload.item_name || "",
          quantity: Number(payload.quantity || 1),
          cost_amount: Number(payload.cost_amount || 0),
          charge_amount: Number(payload.charge_amount || 0),
          remark: payload.remark || "",
        }),
      });
    },
    onSuccess: () => {
      notify("维修故障已添加");
      setShowItemForm(false);
      setItemForm({ quantity: 1 });
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
      queryClient.invalidateQueries({ queryKey: ["machine-timeline", order.machine_id] });
    },
    onError: error => notify(error instanceof Error ? error.message : "添加失败", true),
  });
  const photoMutation = useMutation({
    mutationFn: ({ stage, file }: { stage: "pre" | "post"; file: File }) => {
      if (!orderId) throw new Error("缺少工单 ID");
      const payload = new FormData();
      payload.append("stage", stage);
      payload.append("file", file);
      return api<AnyRecord>(`/api/repair-orders/${orderId}/photos`, { method: "POST", body: payload });
    },
    onSuccess: () => {
      notify("照片已上传");
      photosQuery.refetch();
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-order-photos", orderId] });
      queryClient.invalidateQueries({ queryKey: ["repair-workbench-detail", orderId] });
    },
    onError: error => notify(error instanceof Error ? error.message : "上传失败", true),
  });
  const inspectionMutation = useMutation({
    mutationFn: ({ stage, state, note }: { stage: "pre" | "post"; state: Record<string, boolean>; note: string }) => {
      if (!orderId) throw new Error("缺少工单 ID");
      const items = inspectionItems.map(item => ({ item, abnormal: Boolean(state[item]) }));
      return api<AnyRecord>(`/api/repair-orders/${orderId}/inspections`, {
        method: "POST",
        body: JSON.stringify({ stage, items, note }),
      });
    },
    onSuccess: (_, payload) => {
      notify(payload.stage === "pre" ? "维修前检测已保存" : "维修后检测已保存");
      payload.stage === "pre" ? setPreInspectionEditing(false) : setPostInspectionEditing(false);
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench-detail", orderId] });
    },
    onError: error => notify(error instanceof Error ? error.message : "检测保存失败", true),
  });
  const cancelMutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>(`/api/repair-orders/${orderId}/status`, { method: "POST", body: JSON.stringify({ status: "已作废", remark: payload.cancel_reason || "取消工单" }) }),
    onSuccess: () => {
      notify("工单已取消");
      setForm({});
      onModeChange("view");
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
    },
    onError: error => notify(error instanceof Error ? error.message : "取消失败", true),
  });
  const remarkMutation = useMutation({
    mutationFn: (payload: AnyRecord) => {
      if (!orderId) throw new Error("缺少工单 ID");
      return api<AnyRecord>(`/api/repair-orders/${orderId}/remark`, {
        method: "POST",
        body: JSON.stringify({ remark: payload.remark || "" }),
      });
    },
    onSuccess: () => {
      notify("备注已添加");
      setNoteFormOpen(false);
      setNoteForm({ type: "内部备注" });
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench-detail", orderId] });
    },
    onError: error => notify(error instanceof Error ? error.message : "备注添加失败", true),
  });
  const updateNoteMutation = useMutation({
    mutationFn: (payload: AnyRecord) => {
      if (!orderId) throw new Error("缺少工单 ID");
      return api<AnyRecord>(`/api/repair-orders/${orderId}/notes/${payload.note_id}`, {
        method: "PUT",
        body: JSON.stringify({ note_type: payload.type || "内部备注", content: payload.content || "" }),
      });
    },
    onSuccess: () => {
      notify("备注已修改");
      setNoteFormOpen(false);
      setNoteForm({ type: "内部备注" });
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench-detail", orderId] });
    },
    onError: error => notify(error instanceof Error ? error.message : "备注修改失败", true),
  });
  const deleteNoteMutation = useMutation({
    mutationFn: (payload: AnyRecord) => {
      if (!orderId) throw new Error("缺少工单 ID");
      return api<AnyRecord>(`/api/repair-orders/${orderId}/notes/${payload.note_id}`, {
        method: "DELETE",
        body: JSON.stringify({ reason: payload.reason || "" }),
      });
    },
    onSuccess: () => {
      notify("备注已删除");
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench-detail", orderId] });
    },
    onError: error => notify(error instanceof Error ? error.message : "备注删除失败", true),
  });
  const moduleMutation = useMutation({
    mutationFn: ({ module, action, payload }: { module: string; action: string; payload: AnyRecord }) => {
      if (!orderId) throw new Error("缺少工单 ID");
      return api<AnyRecord>(`/api/repair-orders/${orderId}/modules/${module}/${action}`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      notify("模块动作已完成");
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
      queryClient.invalidateQueries({ queryKey: ["repair-workbench-detail", orderId] });
      if (order.machine_id) queryClient.invalidateQueries({ queryKey: ["machine-timeline", order.machine_id] });
    },
    onError: error => notify(error instanceof Error ? error.message : "模块动作失败", true),
  });

  function setField(key: string, value: unknown) {
    setForm(prev => {
      const next = { ...prev, [key]: value };
      if (["customer_name", "phone"].includes(key)) {
        setSelectedCustomer(null);
        setCustomerLookupOpen(hasTextValue(value));
      }
      if (["imei", "serial"].includes(key)) {
        setSelectedMachine(null);
        setMachineLookupOpen(hasTextValue(value));
      }
      return next;
    });
  }
  function runModuleAction(actionKey: string) {
    if (!orderId) return;
    const [module, action] = actionKey.split(".");
    const payload: AnyRecord = {};
    if (actionKey.endsWith(".start")) {
      payload.remark = window.prompt("开始备注", "开始处理") || "开始处理";
    }
    if (actionKey === "create.complete") {
      payload.remark = window.prompt("建单完成备注", "建单资料已确认") || "建单资料已确认";
    }
    if (actionKey === "quote.complete") {
      const amount = Number(window.prompt("本次报价金额", String(quoted || order.quoted_amount || 0)) || 0);
      if (amount <= 0) {
        notify("报价金额必须大于 0", true);
        return;
      }
      payload.amount = amount;
      payload.remark = window.prompt("检测结论", String(order.diagnosis || order.fault_description || "检测完成")) || "检测完成";
    }
    if (actionKey === "quote.confirm") {
      payload.method = window.prompt("客户确认方式", "现场") || "现场";
      payload.remark = window.prompt("确认备注", "客户同意维修") || "客户同意维修";
    }
    if (actionKey === "payment.prepay") {
      const amount = Number(window.prompt("预收款金额", "0") || 0);
      if (amount <= 0) {
        notify("预收款金额必须大于 0", true);
        return;
      }
      payload.amount = amount;
      payload.method = window.prompt("收款方式", "现金/微信/支付宝") || "待确认";
      payload.remark = "维修预收款";
    }
    if (actionKey === "repair.complete") {
      payload.remark = window.prompt("维修完成备注", "维修完成，等待维修后质检") || "维修完成，等待维修后质检";
    }
    if (actionKey === "qc.complete") {
      const defaultResult = Object.values(postInspectionState).some(Boolean) ? "质检不通过" : "质检通过";
      const result = window.prompt("维修后质检结果：质检通过 / 质检不通过", defaultResult) || defaultResult;
      payload.status = result;
      payload.remark = postInspectionNote || window.prompt("质检备注", result) || result;
    }
    if (actionKey === "payment.register") {
      const paymentModule = (modules.payment || {}) as AnyRecord;
      const receivable = Number(paymentModule.receivable_amount ?? Math.max(quoted - paid, 0));
      const amount = Number(window.prompt("本次收费金额", String(receivable || quoted || 0)) || 0);
      if (amount <= 0) {
        notify("收费金额必须大于 0", true);
        return;
      }
      payload.amount = amount;
      payload.method = window.prompt("收款方式", "现金/微信/支付宝") || "待确认";
      payload.remark = "维修模块收费";
    }
    if (actionKey === "payment.credit") {
      payload.credit_amount = Number(window.prompt("挂账金额", String(Math.max(quoted - paid, 0) || quoted || 0)) || 0);
      payload.credit_term_days = Number(window.prompt("账期天数", "30") || 0);
      payload.credit_limit = Number(window.prompt("授信额度", String(quoted || 0)) || 0);
      payload.approver_user_id = window.prompt("审批人账号", "manager") || "";
      payload.approval_reason = window.prompt("挂账审批理由", "客户账期挂账") || "";
      if (!payload.approver_user_id || Number(payload.credit_amount || 0) <= 0) {
        notify("挂账必须填写金额和审批人", true);
        return;
      }
    }
    if (actionKey === "payment.confirm") {
      payload.confirmed_by = window.prompt("财务确认人", "finance") || "finance";
      payload.remark = window.prompt("确认备注", "财务已确认") || "财务已确认";
    }
    if (actionKey.endsWith(".reopen")) {
      payload.reason = window.prompt("重开原因", "") || "";
      if (!String(payload.reason || "").trim()) {
        notify("重开模块必须填写原因", true);
        return;
      }
    }
    moduleMutation.mutate({ module, action, payload });
  }
  function beginProfileEdit() {
    if (!order.machine_id && mode !== "new") {
      notify("缺少机器档案，无法编辑设备信息", true);
      return;
    }
    setProfileForm({
      model: order.model || "",
      imei: order.imei || "",
      serial: order.serial || "",
      color: order.color || "",
      memory: order.memory || order.capacity || "",
      condition: order.condition || "",
      customer_name: order.customer_name || "",
      phone: order.phone || order.customer_phone || "",
      customer_type: order.customer_type || "零售客户",
    });
    setProfileEditing(true);
  }
  function setProfileField(key: string, value: unknown) {
    setProfileForm(prev => ({ ...prev, [key]: value }));
  }
  function submitProfile() {
    if (!String(profileForm.model || "").trim()) {
      notify("请填写手机型号", true);
      return;
    }
    profileMutation.mutate(profileForm);
  }
  function setItemField(key: string, value: unknown) {
    setItemForm(prev => ({ ...prev, [key]: value }));
  }
  function submitRepairItem() {
    if (mode === "new") {
      if (!itemForm.sku_id) {
        notify("请选择故障代码", true);
        return;
      }
      setNewRepairItems(prev => [...prev, { ...itemForm, quantity: Number(itemForm.quantity || 1) }]);
      setItemForm({ quantity: 1 });
      setShowItemForm(false);
      return;
    }
    if (!canAddRepairItem) {
      notify("当前订单状态不可添加维修故障", true);
      return;
    }
    if (!String(itemForm.item_name || "").trim()) {
      notify("请填写故障名称", true);
      return;
    }
    addItemMutation.mutate(itemForm);
  }
  function toggleInspection(kind: "pre" | "post", item: string) {
    if (mode !== "new" && mode !== "edit" && !(kind === "pre" ? preInspectionEditing : postInspectionEditing)) return;
    const setter = kind === "pre" ? setPreInspectionState : setPostInspectionState;
    setter(prev => ({ ...prev, [item]: !prev[item] }));
  }
  function saveInspection(stage: "pre" | "post") {
    const state = stage === "pre" ? preInspectionState : postInspectionState;
    const note = stage === "pre" ? preInspectionNote : postInspectionNote;
    if (state["其他异常"] && !String(note || "").trim()) {
      notify("选择其他异常后必须填写备注", true);
      return;
    }
    if (mode === "new") {
      if (stage === "pre") {
        setPreInspectionSaved(true);
        setPreInspectionEditing(false);
      }
      notify(stage === "pre" ? "维修前检测已暂存，创建工单时一并保存" : "维修后检测已暂存，创建工单时一并保存");
      return;
    }
    inspectionMutation.mutate({ stage, state, note });
  }
  function uploadPhoto(stage: "pre" | "post", file: File | null) {
    if (!file) return;
    if (mode === "new" || !orderId) {
      notify("请先创建工单后再上传照片", true);
      return;
    }
    photoMutation.mutate({ stage, file });
  }
  function selectCustomer(row: AnyRecord) {
    setSelectedCustomer(row);
    setCustomerLookupOpen(false);
    setForm(prev => ({
      ...prev,
      customer_id: row.customer_id,
      customer_name: row.name || "",
      phone: row.phone || "",
      wechat: row.wechat || "",
      customer_type: row.category || "",
      customer_remark: row.remark || "",
    }));
  }
  function selectMachine(row: AnyRecord) {
    setSelectedMachine(row);
    setMachineLookupOpen(false);
    setForm(prev => ({
      ...prev,
      machine_id: row.machine_id,
      imei: row.imei || "",
      serial: row.serial || "",
      model: row.model || "",
      memory: row.memory || row.storage || "",
      color: row.color || "",
      condition: row.condition || "",
      customer_id: row.customer_id || prev.customer_id || null,
      customer_name: row.customer_name || prev.customer_name || "",
    }));
  }
  function selectRepairSku(row: AnyRecord) {
    setItemForm({
      sku_id: row.sku_id,
      item_name: row.fault_name || "",
      quantity: 1,
      cost_amount: firstNumber(row.cost_amount),
      charge_amount: firstNumber(row.charge_amount),
      remark: row.remark || "",
      sku_code: row.sku_code || "",
      fault_name: row.fault_name || "",
      solution_name: row.solution_name || "",
    });
  }
  function removeNewRepairItem(index: number) {
    setNewRepairItems(prev => prev.filter((_, i) => i !== index));
  }
  function inspectionPayload(stage: "pre" | "post", state: Record<string, boolean>, note: string) {
    return {
      stage,
      items: inspectionItems.map(item => ({ item, abnormal: Boolean(state[item]) })),
      note,
    };
  }
  function setNoteField(key: string, value: unknown) {
    setNoteForm(prev => ({ ...prev, [key]: value }));
  }
  function addLocalNoteLog(title: string, detail: string) {
    setNewOrderNoteLogs(prev => [...prev, { title, detail, operator: currentOperator, created_at: nowText() }]);
  }
  function submitNote() {
    const content = String(noteForm.content || "").trim();
    const type = String(noteForm.type || "内部备注");
    if (!content) {
      notify("请填写备注内容", true);
      return;
    }
    if (noteForm.editing) {
      if (mode === "new") {
        const index = Number(noteForm.index);
        const old = newOrderNotes[index];
        setNewOrderNotes(prev => prev.map((row, i) => i === index ? { ...row, type, content, updated_by: currentOperator, updated_at: nowText() } : row));
        addLocalNoteLog("修改工单备注", `${String(old?.type || "内部备注")}：${String(old?.content || "")} -> ${type}：${content}`);
        setNoteForm({ type: "内部备注" });
        setNoteFormOpen(false);
        notify("备注已修改");
        return;
      }
      updateNoteMutation.mutate({ note_id: noteForm.note_id, type, content });
      return;
    }
    const remark = formatOrderNote(type, content);
    if (mode === "new") {
      setNewOrderNotes(prev => [...prev, { temp_id: `note-${Date.now()}`, type, content, created_by: currentOperator, created_at: nowText() }]);
      setNoteForm({ type: "内部备注" });
      setNoteFormOpen(false);
      notify("备注已添加");
      return;
    }
    remarkMutation.mutate({ remark });
  }
  function editNote(row: AnyRecord, index: number) {
    setNoteForm({
      editing: true,
      index,
      note_id: row.note_id,
      type: row.note_type || row.type || "内部备注",
      content: row.content || "",
    });
    setNoteFormOpen(true);
  }
  function deleteNote(row: AnyRecord, index: number) {
    const label = `${String(row.note_type || row.type || "内部备注")}：${String(row.content || "")}`;
    if (mode === "new") {
      setNewOrderNotes(prev => prev.filter((_, i) => i !== index));
      addLocalNoteLog("删除工单备注", label);
      notify("备注已删除");
      return;
    }
    if (row.note_id) {
      deleteNoteMutation.mutate({ note_id: row.note_id });
    }
  }
  function submitNew() {
    if (!selectedCustomer?.customer_id && !String(display.customer_name || "").trim()) {
      notify("请填写客户姓名", true);
      return;
    }
    if (!selectedMachine?.machine_id && !String(display.model || "").trim()) {
      notify("请填写设备型号", true);
      return;
    }
    const payload: AnyRecord = {
      machine_id: selectedMachine?.machine_id || null,
      machine: selectedMachine?.machine_id ? null : machinePayload({ imei: display.imei, serial: display.serial, model: display.model, memory: display.memory, color: display.color, condition: display.condition, remark: "" }),
      customer_id: selectedCustomer?.customer_id || null,
      customer: selectedCustomer?.customer_id ? null : customerPayload({ customer_name: display.customer_name, phone: display.phone, wechat: display.wechat, customer_type: display.customer_type, customer_remark: display.customer_remark }),
      fault_description: display.fault_description || "",
      remark: newOrderNotes.map(row => formatOrderNote(String(row.type || "内部备注"), String(row.content || ""))).join("\n"),
      notes: newOrderNotes.map(row => ({ note_type: row.type || "内部备注", content: row.content || "" })),
      note_logs: newOrderNoteLogs.map(row => ({ title: row.title || "", detail: row.detail || "" })),
      repair_items: newRepairItems.map(row => ({
        sku_id: row.sku_id || null,
        item_name: row.item_name || row.fault_name || "",
        quantity: Number(row.quantity || 1),
        cost_amount: Number(row.cost_amount || 0),
        charge_amount: Number(row.charge_amount || 0),
        remark: row.remark || "",
      })),
      inspections: [inspectionPayload("pre", preInspectionState, preInspectionNote)],
    };
    createMutation.mutate(payload);
  }
  function submitCancel() {
    if (!String(form.cancel_reason || "").trim()) {
      notify("请填写取消原因", true);
      return;
    }
    cancelMutation.mutate(form);
  }

  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;

  return (
    <div className={`order-detail-page order-mode-${mode}`}>
      <header className="order-detail-topbar">
        <div className="order-detail-title"><button type="button" className="back-button" onClick={onBack}><ArrowLeft size={24} /></button><h1>{mode === "new" ? "新建工单" : mode === "edit" ? "编辑工单" : mode === "cancel" ? "取消工单" : "工单详情"}</h1></div>
        <div className="order-detail-search"><Search size={22} /><Input allowClear placeholder="?????IMEI???..." /></div>
        <div className="order-detail-icons"><button type="button" className="icon-button"><Bell size={23} /><span /></button><button type="button" className="icon-button"><UserRound size={23} /></button></div>
      </header>

      <section className="order-hero">
        <div><div className="order-heading-line"><h2>{mode === "new" ? "新建维修工单" : `工单: ${String(order.order_no || order.repair_order_id || orderId)}`}</h2><span className="order-status-pill">{statusText}</span></div><p>创建于 {createdAt} | 负责人: {owner}</p></div>
        <div className="order-hero-actions">
          {mode === "view" && canModifyOrderStatus(statusText) && <button type="button" onClick={() => onModeChange("edit")}><Edit3 size={20} />编辑</button>}
          {mode === "view" && canModifyOrderStatus(statusText) && <button type="button" onClick={() => onModeChange("cancel")}><CirclePlus size={20} />取消订单</button>}
          {mode === "edit" && <button type="button" onClick={() => editMutation.mutate(form)} disabled={editMutation.isPending}><Edit3 size={20} />保存修改</button>}
          {mode === "cancel" && <button type="button" className="danger-action" onClick={submitCancel} disabled={cancelMutation.isPending}>确认取消</button>}
          {mode !== "view" && mode !== "new" && <button type="button" onClick={() => { setForm({}); onModeChange("view"); }}>放弃</button>}
        </div>
      </section>

      {mode !== "new" && (
        <section className="order-module-board">
          <div className="module-progress">
            {repairModuleSteps(modules).map((step, index) => (
              <div className={`module-progress-step ${step.done ? "done" : ""} ${step.active ? "active" : ""}`} key={step.key}>
                <span>{index + 1}</span>
                <b>{step.title}</b>
              </div>
            ))}
          </div>
          <div className="module-card-grid">
            <RepairModuleCard
              module={(modules.create || {}) as AnyRecord}
              moduleKey="create"
              fallbackTitle="建单"
              availableActions={availableActions}
              loading={moduleMutation.isPending}
              onAction={runModuleAction}
            />
            <RepairModuleCard
              module={(modules.quote || {}) as AnyRecord}
              moduleKey="quote"
              fallbackTitle="检测报价"
              availableActions={availableActions}
              loading={moduleMutation.isPending}
              onAction={runModuleAction}
            />
            <RepairModuleCard
              module={(modules.repair_qc || {}) as AnyRecord}
              moduleKey="repair_qc"
              fallbackTitle="维修与维修后质检"
              availableActions={availableActions}
              loading={moduleMutation.isPending}
              onAction={runModuleAction}
            />
            <RepairModuleCard
              module={(modules.payment || {}) as AnyRecord}
              moduleKey="payment"
              fallbackTitle="收费结单"
              availableActions={availableActions}
              loading={moduleMutation.isPending}
              onAction={runModuleAction}
            />
          </div>
        </section>
      )}

      <div className="order-detail-layout">
        <div className="order-main-column">
          <section className="order-card customer-card">
            <div className="repair-card-head">
              <h3><Users size={24} />客户信息</h3>
            </div>
            <div className="order-info-grid compact">
              <OrderEditableLine label="客户姓名" value={profileCustomer} editable={mode === "new" || profileEditing} tag={profileCustomerType} onFocus={() => { if (mode === "new") { setCustomerLookupAnchor("name"); setCustomerLookupOpen(hasTextValue(form.customer_name)); } }} onChange={v => { if (mode === "new") { setCustomerLookupAnchor("name"); setCustomerLookupOpen(hasTextValue(v)); } profileEditing ? setProfileField("customer_name", v) : setField("customer_name", v); }} />
              <OrderEditableLine label="联系方式" value={profilePhone} editable={mode === "new" || profileEditing} highlight onFocus={() => { if (mode === "new") { setCustomerLookupAnchor("phone"); setCustomerLookupOpen(hasTextValue(form.phone)); } }} onChange={v => { if (mode === "new") { setCustomerLookupAnchor("phone"); setCustomerLookupOpen(hasTextValue(v)); } profileEditing ? setProfileField("phone", v) : setField("phone", v); }} />
            {mode === "new" && customerLookupOpen && <SuggestionList className={`customer-suggestions ${customerLookupAnchor === "phone" ? "lookup-anchor-right" : "lookup-anchor-left"} lookup-row-1` } loading={customerSearchQuery.isLoading} rows={customerOptions} selectedId={selectedCustomer?.customer_id} idKey="customer_id" primaryKey="name" secondaryKeys={["phone", "category", "shop_name"]} onSelect={selectCustomer} empty="没有找到已有客户" />}
              <OrderEditableLine label="微信" value={String(display.wechat || order.wechat || (mode === "new" ? "" : "待补"))} editable={mode === "new"} onChange={v => setField("wechat", v)} />
              <OrderChoiceLine label="客户类型" value={profileCustomerType} editable={mode === "new" || profileEditing} options={["个人客户", "同行客户", "企业客户", "VIP客户"]} onChange={v => profileEditing ? setProfileField("customer_type", v) : setField("customer_type", v)} />
              {mode === "new" && <OrderField label="客户备注" value={display.customer_remark} editable area onChange={v => setField("customer_remark", v)} />}
            </div>
          </section>

          <section className="order-card device-card">
            <div className="repair-card-head">
              <h3><Smartphone size={24} />设备信息</h3>
              <div className="inline-actions">
                {mode !== "new" && (profileEditing ? (
                  <>
                    <button type="button" className="mini-add-button" onClick={submitProfile} disabled={profileMutation.isPending}>保存</button>
                    <button type="button" className="ghost-mini-button" onClick={() => { setProfileEditing(false); setProfileForm({}); }}>取消</button>
                  </>
                ) : (
                  <button type="button" className="ghost-mini-button" onClick={beginProfileEdit} disabled={!order.machine_id}><Edit3 size={15} />编辑</button>
                ))}
              </div>
            </div>
            <div className="order-info-grid">
              <OrderChoiceLine label="手机型号" value={profileModel} editable={mode === "new" || profileEditing} options={deviceModelNames} onChange={v => profileEditing ? setProfileField("model", v) : setField("model", v)} />
              <OrderEditableLine label="IMEI" value={String(profileDisplay.imei || "")} editable={mode === "new" || profileEditing} onFocus={() => { if (mode === "new") { setMachineLookupAnchor("imei"); setMachineLookupOpen(hasTextValue(form.imei)); } }} onChange={v => { if (mode === "new") { setMachineLookupAnchor("imei"); setMachineLookupOpen(hasTextValue(v)); } profileEditing ? setProfileField("imei", v) : setField("imei", v); }} />
              <OrderEditableLine label="序列号" value={String(profileDisplay.serial || "")} editable={mode === "new" || profileEditing} onFocus={() => { if (mode === "new") { setMachineLookupAnchor("serial"); setMachineLookupOpen(hasTextValue(form.serial)); } }} onChange={v => { if (mode === "new") { setMachineLookupAnchor("serial"); setMachineLookupOpen(hasTextValue(v)); } profileEditing ? setProfileField("serial", v) : setField("serial", v); }} />
            {mode === "new" && machineLookupOpen && <SuggestionList className={`machine-suggestions ${machineLookupAnchor === "imei" ? "lookup-anchor-right lookup-row-1" : "lookup-anchor-left lookup-row-2"}` } loading={machineSearchQuery.isLoading} rows={machineOptions} selectedId={selectedMachine?.machine_id} idKey="machine_id" primaryKey="model" secondaryKeys={["machine_no", "imei", "serial", "customer_name"]} onSelect={selectMachine} empty="没有找到已有机器" />}
              <OrderChoiceLine label="颜色" value={profileColor} editable={mode === "new" || profileEditing} options={colorChoices} onChange={v => profileEditing ? setProfileField("color", v) : setField("color", v)} />
              <OrderChoiceLine label="容量/内存" value={profileMemory} editable={mode === "new" || profileEditing} options={memoryChoices} onChange={v => profileEditing ? setProfileField("memory", v) : setField("memory", v)} />
              <OrderChoiceLine label="机况" value={String(profileDisplay.condition || "")} editable={mode === "new" || profileEditing} options={conditionOptions} onChange={v => profileEditing ? setProfileField("condition", v) : setField("condition", v)} />
            </div>
          </section>

          <EditableInspectionCard title="维修前检测 (Pre-Repair)" inspections={inspectionItems} note={preInspectionNote} mode={mode} state={preInspectionState} photos={prePhotos} stage="pre" editing={preInspectionEditing} saved={mode === "new" && preInspectionSaved} onStart={() => { setPreInspectionSaved(false); setPreInspectionEditing(true); }} onSave={() => saveInspection("pre")} onCancel={() => { setPreInspectionSaved(true); setPreInspectionEditing(false); }} onToggle={item => toggleInspection("pre", item)} onNoteChange={setPreInspectionNote} onUpload={uploadPhoto} onOpenPhoto={setSelectedPhoto} uploading={photoMutation.isPending || inspectionMutation.isPending} />

          <section className="order-card">
            <div className="repair-card-head">
              <h3><FileText size={24} />故障与维修详情</h3>
              {(mode === "new" || mode === "edit") && <button type="button" className="mini-add-button" onClick={() => mode === "new" || canAddRepairItem ? setShowItemForm(true) : notify("当前订单状态不可添加维修故障", true)} disabled={mode !== "new" && !canAddRepairItem}><Plus size={16} />添加故障</button>}
            </div>
            <p className="order-muted">{mode === "new" ? "可按当前机型添加故障代码，系统会带出配件/SKU、成本和服务费。" : String(order.fault_description || "客户反馈设备异常，需要检测并维修。")}</p>
            {showItemForm && (mode === "new" || mode === "edit") && <div className="inline-item-editor repair-item-editor">
              {mode === "new" && <div className="sku-picker">
                {repairSkuQuery.isLoading && <div className="lookup-empty">正在读取故障代码...</div>}
                {!repairSkuQuery.isLoading && ((repairSkuQuery.data as AnyRecord[] | undefined) || []).map(row => <button type="button" key={String(row.sku_id)} className={String(itemForm.sku_id || "") === String(row.sku_id) ? "selected" : ""} onClick={() => selectRepairSku(row)}><b>{String(row.fault_name || row.solution_name)}</b><span>{String(row.sku_code)} · {String(row.model || "通用")} · {poolMoney(row.charge_amount)}</span></button>)}
                {!repairSkuQuery.isLoading && !((repairSkuQuery.data as AnyRecord[] | undefined) || []).length && <div className="lookup-empty">当前机型暂无可用故障代码</div>}
              </div>}
              <OrderField label="故障名称" value={itemForm.item_name} editable onChange={v => setItemField("item_name", v)} />
              <OrderField label="数量" value={itemForm.quantity || 1} editable type="number" onChange={v => setItemField("quantity", v)} />
              <OrderField label="配件成本" value={itemForm.cost_amount} editable type="number" onChange={v => setItemField("cost_amount", v)} />
              <OrderField label="工时/服务费" value={itemForm.charge_amount} editable type="number" onChange={v => setItemField("charge_amount", v)} />
              <OrderField label="备注" value={itemForm.remark} editable area onChange={v => setItemField("remark", v)} />
              <div className="inline-editor-actions"><button type="button" className="mini-add-button" onClick={submitRepairItem} disabled={addItemMutation.isPending}>{mode === "new" ? "加入明细" : "保存故障"}</button><button type="button" className="ghost-mini-button" onClick={() => { setShowItemForm(false); setItemForm({ quantity: 1 }); }}>取消</button></div>
            </div>}
            
<div className="repair-lines">
  <AppTable
    rows={detailRows}
    columns={[["fault_name", "故障名称"], ["sku_code", "更换配件/SKU"], ["unit_cost", "配件单价"], ["service_fee", "工时/服务费"], ["line_total", "小计"]]}
    formatValue={(row, key) => {
      const { unitCost, serviceFee, lineAmount } = repairLineAmounts(row);
      const quantity = firstNumber(row.quantity, row.qty, 1);
      if (key === "fault_name") return String(row.item_name || row.fault_name || row.material_name || "");
      if (key === "sku_code") return String(row.sku_code || row.sku || row.material_code || "-");
      if (key === "unit_cost") return poolMoney(unitCost);
      if (key === "service_fee") return poolMoney(serviceFee);
      if (key === "line_total") return poolMoney(lineAmount * quantity);
      return displayValue(row, key);
    }}
    isStatusKey={() => false}
    actions={{ title: "操作", render: (_row, index) => mode === "new" ? <AppButton className="table-link danger" type="link" danger onClick={() => removeNewRepairItem(index)}>删除</AppButton> : mode === "edit" ? <AppButton className="table-link danger" type="link" danger>删除</AppButton> : "-" }}
  />
</div>
            <div className="order-fee-summary stacked-fee-summary"><span>费用总计 <b>{poolMoney(quoted)}</b></span><span>折扣优惠 <b className="danger-text">- {poolMoney(0)}</b></span><span>应收总额 <b>{poolMoney(quoted)}</b></span>{mode === "edit" && <OrderField label="修改报价" value={form.quoted_amount ?? order.quoted_amount} editable type="number" onChange={v => setField("quoted_amount", v)} />}</div>
          </section>

          {mode !== "new" && <EditableInspectionCard title="维修后检测 (Post-Repair)" inspections={inspectionItems} note={postInspectionNote} compact={false} mode={mode} state={postInspectionState} photos={postPhotos} stage="post" editing={postInspectionEditing} onStart={() => setPostInspectionEditing(true)} onSave={() => saveInspection("post")} onCancel={() => setPostInspectionEditing(false)} onToggle={item => toggleInspection("post", item)} onNoteChange={setPostInspectionNote} onUpload={uploadPhoto} onOpenPhoto={setSelectedPhoto} uploading={photoMutation.isPending || inspectionMutation.isPending} />}
          <section className="order-card"><h3><ClipboardList size={24} />维修历史</h3><div className="history-list">{historyOrders.length ? historyOrders.slice(0, 5).map(row => <button type="button" className="history-order-row" key={String(row.repair_order_id)} onClick={() => { onCreated(row.repair_order_id as number | string); onModeChange("view"); }}><b>{String(row.order_no || row.repair_order_id || "")}</b><span>{String(row.status || "待确认")} · {String(row.fault_description || "无故障描述")}</span><em>{poolMoney(row.quoted_amount || row.paid_amount || 0)} · {String(row.created_at || "")}</em></button>) : <div className="history-empty">无</div>}</div></section>
        </div>

        <aside className="order-side-column">
          {mode === "new" && <section className="order-card create-action-card"><button type="button" className="primary-create-button" onClick={submitNew} disabled={createMutation.isPending}><Plus size={20} />创建工单</button><button type="button" className="discard-order-button" onClick={() => { setForm({}); onBack(); }}>放弃</button></section>}
          <section className="order-card"><h3>订单状态</h3><div className="detail-timeline">{buildStitchTimeline(mode, statusText, createdAt, owner).map(item => <div className={`timeline-step ${item.done ? "done" : ""} ${item.active ? "active" : ""}`} key={item.title}><span>{item.done ? <CheckCircle2 size={18} /> : item.active ? <Users size={18} /> : <Flag size={18} />}</span><div><b>{item.title}</b><p>{item.note}</p></div></div>)}</div></section>
          {mode === "cancel" && <section className="order-card cancel-warning-card"><h3>取消确认</h3><p>取消订单会将业务状态改为已作废，不会删除数据库记录。若订单已有未闭环领料，后端会提示先退料或报损。</p><OrderField label="取消原因" value={form.cancel_reason} editable area onChange={v => setField("cancel_reason", v)} /></section>}
          {mode === "edit" && <section className="order-card"><h3>订单转派</h3><OrderField label="负责人账号" value={form.assigned_to ?? order.assigned_to} editable onChange={v => setField("assigned_to", v)} /><OrderField label="修改备注" value={form.remark} editable area onChange={v => setField("remark", v)} /></section>}
          
<section className="order-card notes-card">
  <div className="side-title-row"><h3>备注信息</h3><button type="button" className="icon-mini-button" onClick={() => { setNoteFormOpen(value => !value); setNoteForm({ type: "内部备注" }); }}><CirclePlus size={22} /></button></div>
  {noteFormOpen && (
    <div className="note-editor">
      <Select value={String(noteForm.type || "内部备注")} onChange={value => setNoteField("type", value)} options={[{ value: "内部备注", label: "内部备注" }, { value: "交付说明", label: "交付说明" }]} />
      <Input.TextArea value={String(noteForm.content || "")} placeholder="填写备注内容..." onChange={event => setNoteField("content", event.target.value)} />
      <div><AppButton className="mini-add-button" onClick={submitNote} disabled={remarkMutation.isPending || updateNoteMutation.isPending}>{noteForm.editing ? "保存修改" : "保存备注"}</AppButton><AppButton className="ghost-mini-button" onClick={() => { setNoteFormOpen(false); setNoteForm({ type: "内部备注" }); }}>取消</AppButton></div>
    </div>
  )}
  {visibleOrderNotes.map((row, index) => { const noteType = String(row.note_type || row.type || "内部备注"); const createdBy = String(row.created_by || row.operator || currentOperator); const createdAt = String(row.created_at || "待创建"); return <div className={'note-box note-entry ' + (noteType === "交付说明" ? "muted" : "warning")} key={String(row.note_id || row.temp_id || noteType + '-' + index)}><div className="note-entry-head"><b>{noteType}</b><span>{createdBy} ? {createdAt}</span></div><p>{String(row.content || "")}</p>{!row.readonly && <div className="note-entry-actions"><AppButton type="link" onClick={() => editNote(row, index)}>修改</AppButton><AppButton type="link" danger onClick={() => deleteNote(row, index)} disabled={deleteNoteMutation.isPending}>删除</AppButton></div>}</div>; })}
</section>
          <section className="order-card log-card"><div className="side-title-row"><h3>订单日志</h3>{combinedLogs.length > 3 && <button type="button" className="table-link" onClick={() => setLogsExpanded(value => !value)}>{logsExpanded ? "收起" : "更多"}</button>}</div>{visibleLogs.length ? visibleLogs.map((event, index) => <div className="log-item" key={String(event.event_id || event.created_at || index)}><b>{String(event.title || "订单维护")}</b><p>{String(event.detail || "工单信息已更新")}</p><span>{String(event.created_at || "")} {String(event.operator || "")}</span></div>) : <div className="history-empty">暂无订单日志</div>}</section>
        </aside>
      </div>
      {selectedPhoto && (
        <div className="photo-preview-backdrop" role="dialog" aria-modal="true" onClick={() => setSelectedPhoto(null)}>
          <div className="photo-preview-dialog" onClick={event => event.stopPropagation()}>
            <button type="button" className="photo-preview-close" onClick={() => setSelectedPhoto(null)}>×</button>
            <img src={String(selectedPhoto.url || "")} alt={String(selectedPhoto.filename || "维修照片")} />
            <p>{String(selectedPhoto.filename || "维修照片")}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function FlowOrderDetailPage({
  orderId,
  mode,
  notify,
  onBack,
  onCreated,
  onModeChange,
}: {
  orderId: number | string | null;
  mode: OrderMode;
  notify: (message: string, error?: boolean) => void;
  onBack: () => void;
  onCreated: (id: number | string) => void;
  onModeChange: (mode: OrderMode) => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<AnyRecord>({});
  const query = useQuery({
    queryKey: ["repair-workbench-detail", orderId],
    queryFn: () => api<AnyRecord>(`/api/repair-workbench/${orderId}`),
    enabled: Boolean(orderId) && mode !== "new",
  });
  const order = ((query.data?.order || {}) as AnyRecord);
  const events = ((query.data?.events as AnyRecord[] | undefined) || []).slice(0, 6);
  const incomeItems = ((query.data?.income_items as AnyRecord[] | undefined) || []);
  const costItems = ((query.data?.cost_items as AnyRecord[] | undefined) || []);
  const payments = ((query.data?.payments as AnyRecord[] | undefined) || []);
  const display = mode === "new" ? form : { ...order, ...form };
  const isEditable = mode === "new" || mode === "edit";
  const title = mode === "new" ? "新建工单" : `工单: ${String(order.order_no || order.repair_order_id || orderId || "-")}`;
  const statusText = mode === "new" ? "待创建" : normalizeRepairStatus(order.status);
  const createdAt = String(order.created_at || "保存后生成");
  const owner = String(display.assigned_to || order.assigned_to || "未指派");
  const quoted = Number(display.quoted_amount || order.quoted_amount || incomeItems.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  const cost = Number(order.cost_amount || costItems.reduce((sum, row) => sum + Number(row.total_cost || row.unit_cost || 0), 0));
  const paid = Number(order.paid_amount || payments.reduce((sum, row) => sum + Number(row.amount || 0), 0));

  const createMutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/repair-orders", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: data => {
      const nextOrder = ((data.order || data) as AnyRecord);
      const id = nextOrder.repair_order_id || data.repair_order_id;
      notify("维修工单已创建");
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
      if (id) onCreated(id as number | string);
    },
    onError: error => notify(error instanceof Error ? error.message : "创建失败", true),
  });
  const editMutation = useMutation({
    mutationFn: async (payload: AnyRecord) => {
      if (!orderId) throw new Error("缺少工单 ID");
      const tasks: Promise<unknown>[] = [];
      if (payload.assigned_to && payload.assigned_to !== order.assigned_to) {
        tasks.push(api(`/api/repair-orders/${orderId}/assign`, { method: "POST", body: JSON.stringify({ engineer_user_id: payload.assigned_to, remark: payload.remark || "" }) }));
      }
      if (payload.quoted_amount !== "" && Number(payload.quoted_amount || 0) !== Number(order.quoted_amount || 0)) {
        tasks.push(api(`/api/repair-orders/${orderId}/price`, { method: "POST", body: JSON.stringify({ quoted_amount: Number(payload.quoted_amount || 0), remark: payload.remark || "" }) }));
      }
      if (order.machine_id && (payload.model || payload.imei || payload.serial || payload.memory || payload.color || payload.condition)) {
        tasks.push(api(`/api/machines/${order.machine_id}`, { method: "PUT", body: JSON.stringify({ imei: payload.imei ?? order.imei ?? "", serial: payload.serial ?? order.serial ?? "", model: payload.model ?? order.model ?? "", memory: payload.memory ?? order.memory ?? "", color: payload.color ?? order.color ?? "", condition: payload.condition ?? order.condition ?? "", current_status: order.current_status || "维修中", customer_id: order.customer_id || null }) }));
      }
      if (payload.repair_item_name) {
        tasks.push(api(`/api/repair-orders/${orderId}/items`, { method: "POST", body: JSON.stringify({ item_name: payload.repair_item_name, quantity: Number(payload.repair_item_qty || 1), cost_amount: Number(payload.repair_item_cost || 0), charge_amount: Number(payload.repair_item_charge || 0), remark: payload.remark || "" }) }));
      }
      if (!tasks.length) return query.data;
      await Promise.all(tasks);
      return api<AnyRecord>(`/api/repair-workbench/${orderId}`);
    },
    onSuccess: () => {
      notify("工单修改已保存");
      setForm({});
      onModeChange("view");
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
    },
    onError: error => notify(error instanceof Error ? error.message : "保存失败", true),
  });
  const cancelMutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>(`/api/repair-orders/${orderId}/status`, { method: "POST", body: JSON.stringify({ status: "已作废", remark: payload.cancel_reason || payload.remark || "取消工单" }) }),
    onSuccess: () => {
      notify("工单已取消");
      setForm({});
      onModeChange("view");
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
    },
    onError: error => notify(error instanceof Error ? error.message : "取消失败", true),
  });

  function setField(key: string, value: unknown) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  function submitNew() {
    if (!String(display.customer_name || "").trim() || !String(display.model || "").trim()) {
      notify("请填写客户姓名和设备型号", true);
      return;
    }
    createMutation.mutate({
      machine_id: null,
      machine: machinePayload({ imei: display.imei, serial: display.serial, model: display.model, memory: display.memory, color: display.color, condition: display.condition }),
      customer: customerPayload({ customer_name: display.customer_name, phone: display.phone }),
      fault_description: display.fault_description || "",
      remark: display.remark || "",
    });
  }

  function submitEdit() {
    editMutation.mutate(form);
  }

  function submitCancel() {
    if (!String(form.cancel_reason || "").trim()) {
      notify("请填写取消原因", true);
      return;
    }
    cancelMutation.mutate(form);
  }

  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;

  return (
    <div className={`order-detail-page order-mode-${mode}`}>
      <header className="order-detail-topbar">
        <div className="order-detail-title">
          <button type="button" className="back-button" onClick={onBack}><ArrowLeft size={24} /></button>
          <h1>{mode === "new" ? "新建工单" : mode === "edit" ? "编辑工单" : mode === "cancel" ? "取消工单" : "工单详情"}</h1>
        </div>
        <div className="order-detail-search"><Search size={22} /><Input allowClear placeholder="?????IMEI???..." /></div>
        <div className="order-detail-icons"><button type="button" className="icon-button"><Bell size={23} /><span /></button><button type="button" className="icon-button"><UserRound size={23} /></button></div>
      </header>

      <section className="order-hero">
        <div>
          <div className="order-heading-line"><h2>{title}</h2><span className="order-status-pill">{statusText}</span></div>
          <p>创建于 {createdAt} | 负责人: {owner}</p>
        </div>
        <div className="order-hero-actions">
          {mode === "view" && canModifyOrderStatus(statusText) && <button type="button" onClick={() => onModeChange("edit")}><Edit3 size={20} />编辑</button>}
          {mode === "view" && canModifyOrderStatus(statusText) && <button type="button" onClick={() => onModeChange("cancel")}><CirclePlus size={20} />取消订单</button>}
          {mode === "edit" && <button type="button" onClick={submitEdit} disabled={editMutation.isPending}><Edit3 size={20} />保存修改</button>}
          {mode === "new" && <button type="button" onClick={submitNew} disabled={createMutation.isPending}><Plus size={20} />创建工单</button>}
          {mode === "cancel" && <button type="button" className="danger-action" onClick={submitCancel} disabled={cancelMutation.isPending}>确认取消</button>}
          {mode !== "view" && <button type="button" onClick={() => { setForm({}); mode === "new" ? onBack() : onModeChange("view"); }}>放弃</button>}
        </div>
      </section>

      <div className="order-detail-layout">
        <div className="order-main-column">
          <section className="order-card">
            <h3><Smartphone size={24} />设备与客户信息</h3>
            <div className="order-form-grid">
              <OrderField label="客户姓名" value={display.customer_name} editable={mode === "new"} onChange={value => setField("customer_name", value)} />
              <OrderField label="联系方式" value={display.phone || display.customer_phone} editable={mode === "new"} onChange={value => setField("phone", value)} />
              <OrderField label="设备型号" value={display.model} editable={isEditable} onChange={value => setField("model", value)} />
              <OrderField label="IMEI" value={display.imei} editable={isEditable} onChange={value => setField("imei", value)} />
              <OrderField label="序列号" value={display.serial} editable={isEditable} onChange={value => setField("serial", value)} />
              <OrderField label="颜色" value={display.color} editable={isEditable} onChange={value => setField("color", value)} />
              <OrderField label="容量" value={display.memory} editable={isEditable} onChange={value => setField("memory", value)} />
              <OrderField label="负责人" value={display.assigned_to || order.assigned_to} editable={mode === "edit"} onChange={value => setField("assigned_to", value)} />
            </div>
          </section>

          <section className="order-card">
            <h3><FileText size={24} />故障与报价</h3>
            <div className="order-form-grid">
              <OrderField label="故障描述" value={display.fault_description} editable={mode === "new"} area onChange={value => setField("fault_description", value)} />
              <OrderField label="检测结论" value={display.diagnosis} editable={mode === "edit"} area onChange={value => setField("diagnosis", value)} />
              <OrderField label="预估金额" value={display.quoted_amount || order.quoted_amount} editable={mode === "edit"} type="number" onChange={value => setField("quoted_amount", value)} />
              <OrderField label="备注" value={display.remark || order.remark} editable={isEditable} area onChange={value => setField("remark", value)} />
            </div>
          </section>

          {mode === "edit" && <section className="order-card">
            <h3><ClipboardList size={24} />新增维修项目</h3>
            <div className="order-form-grid">
              <OrderField label="项目名称" value={form.repair_item_name} editable onChange={value => setField("repair_item_name", value)} />
              <OrderField label="数量" value={form.repair_item_qty || 1} editable type="number" onChange={value => setField("repair_item_qty", value)} />
              <OrderField label="成本" value={form.repair_item_cost} editable type="number" onChange={value => setField("repair_item_cost", value)} />
              <OrderField label="收费" value={form.repair_item_charge} editable type="number" onChange={value => setField("repair_item_charge", value)} />
            </div>
          </section>}

          {mode === "cancel" && <section className="order-card cancel-warning-card">
            <h3>取消确认</h3>
            <p>取消订单会将业务状态改为已作废，不会删除数据库记录。若订单已有未闭环领料，后端会拒绝取消并提示需要先退料或报损。</p>
            <OrderField label="取消原因" value={form.cancel_reason} editable area onChange={value => setField("cancel_reason", value)} />
          </section>}

          <section className="order-card">
            <h3><CreditCard size={24} />金额概览</h3>
            <div className="order-fee-summary flow-summary"><span>报价金额 <b>{poolMoney(quoted)}</b></span><span>成本 <b>{poolMoney(cost)}</b></span><span>已收款 <b>{poolMoney(paid)}</b></span></div>
          </section>
        </div>

        <aside className="order-side-column">
          <section className="order-card">
            <h3>订单状态</h3>
            <div className="detail-timeline">
              {buildOrderTimeline(mode, statusText, owner).map(item => <div className={`timeline-step ${item.done ? "done" : ""} ${item.active ? "active" : ""}`} key={item.title}><span>{item.done ? <CheckCircle2 size={18} /> : item.active ? <Users size={18} /> : <Flag size={18} />}</span><div><b>{item.title}</b><p>{item.note}</p></div></div>)}
            </div>
          </section>
          <section className="order-card log-card">
            <h3>系统操作日志</h3>
            {(events.length ? events : [{ title: "等待操作", detail: mode === "new" ? "保存后生成操作日志" : "暂无更多日志", created_at: "" }]).map((event, index) => <div className="log-item" key={String(event.event_id || event.created_at || index)}><b>{String(event.title || "系统操作")}</b><p>{String(event.detail || "工单信息已更新")}</p><span>{String(event.created_at || "")}</span></div>)}
          </section>
        </aside>
      </div>
    </div>
  );
}

function SegmentedSwitch({ value, onChange, leftLabel, rightLabel }: { value: "new" | "existing"; onChange: (value: "new" | "existing") => void; leftLabel: string; rightLabel: string }) {
  return (
    <div className="mode-segmented">
      <button type="button" className={value === "new" ? "active" : ""} onClick={() => onChange("new")}>{leftLabel}</button>
      <button type="button" className={value === "existing" ? "active" : ""} onClick={() => onChange("existing")}>{rightLabel}</button>
    </div>
  );
}

function LookupPanel({
  keyword,
  onKeyword,
  placeholder,
  loading,
  rows,
  selectedId,
  idKey,
  primaryKey,
  secondaryKeys,
  onSelect,
  empty,
}: {
  keyword: string;
  onKeyword: (value: string) => void;
  placeholder: string;
  loading: boolean;
  rows: AnyRecord[];
  selectedId: unknown;
  idKey: string;
  primaryKey: string;
  secondaryKeys: string[];
  onSelect: (row: AnyRecord) => void;
  empty: string;
}) {
  return (
    <div className="lookup-panel">
      <div className="lookup-search"><Search size={18} /><Input allowClear value={keyword} onChange={event => onKeyword(event.target.value)} placeholder={placeholder} /></div>
      <div className="lookup-results">
        {loading && <div className="lookup-empty">搜索中...</div>}
        {!loading && rows.map(row => {
          const id = row[idKey];
          const secondary = secondaryKeys.map(key => row[key]).filter(Boolean).join(" · ");
          return (
            <button type="button" key={String(id)} className={String(selectedId || "") === String(id || "") ? "selected" : ""} onClick={() => onSelect(row)}>
              <b>{String(row[primaryKey] || id || "未命名")}</b>
              <span>{secondary || "无补充信息"}</span>
            </button>
          );
        })}
        {!loading && !rows.length && <div className="lookup-empty">{empty}</div>}
      </div>
    </div>
  );
}

function SuggestionList({ loading, rows, selectedId, idKey, primaryKey, secondaryKeys, onSelect, empty, className = "" }: { loading: boolean; rows: AnyRecord[]; selectedId: unknown; idKey: string; primaryKey: string; secondaryKeys: string[]; onSelect: (row: AnyRecord) => void; empty: string; className?: string }) {
  return (
    <div className={`inline-suggestion-list ${className}`} onMouseDown={event => event.preventDefault()}>
      {loading && <div className="lookup-empty">搜索中...</div>}
      {!loading && rows.map(row => {
        const id = row[idKey];
        const secondary = secondaryKeys.map(key => row[key]).filter(Boolean).join(" · ");
        return <button type="button" key={String(id)} className={String(selectedId || "") === String(id || "") ? "selected" : ""} onClick={() => onSelect(row)}><b>{String(row[primaryKey] || id || "未命名")}</b><span>{secondary || "无补充信息"}</span></button>;
      })}
      {!loading && !rows.length && <div className="lookup-empty">{empty}</div>}
    </div>
  );
}

function repairModuleSteps(modules: AnyRecord) {
  const createModule = (modules.create || {}) as AnyRecord;
  const quoteModule = (modules.quote || {}) as AnyRecord;
  const repairModule = (modules.repair_qc || {}) as AnyRecord;
  const paymentModule = (modules.payment || {}) as AnyRecord;
  const createStatus = String(createModule.status || "");
  const quoteStatus = String(quoteModule.status || "");
  const repairStatus = String(repairModule.status || "");
  const paymentStatus = String(paymentModule.status || "");
  return [
    { key: "create", title: "建单", done: createStatus === "已完成", active: createStatus !== "已完成" },
    { key: "quote", title: "检测报价", done: quoteStatus === "客户已确认", active: createStatus === "已完成" && quoteStatus !== "客户已确认" },
    { key: "repair_qc", title: "维修与质检", done: repairStatus === "质检通过", active: quoteStatus === "客户已确认" && repairStatus !== "质检通过" },
    { key: "payment", title: "收费结单", done: paymentStatus === "已完成", active: repairStatus === "质检通过" && paymentStatus !== "已完成" },
  ];
}

const repairModuleActionMap: Record<string, Array<[string, string]>> = {
  create: [
    ["create.start", "开始建单"],
    ["create.save", "保存草稿"],
    ["create.complete", "确认建单完成"],
    ["create.reopen", "重开建单"],
  ],
  quote: [
    ["quote.start", "开始检测"],
    ["quote.save", "保存草稿"],
    ["quote.complete", "提交报价"],
    ["quote.submit", "提交报价"],
    ["quote.confirm", "客户确认报价"],
    ["quote.reopen", "重开报价"],
  ],
  repair_qc: [
    ["repair.start", "开始维修"],
    ["repair.save", "保存维修草稿"],
    ["repair.complete", "确认维修完成"],
    ["qc.start", "开始质检"],
    ["qc.complete", "提交维修后质检"],
    ["repair_qc.reopen", "重开维修质检"],
  ],
  payment: [
    ["payment.prepay", "登记预收款"],
    ["payment.start", "开始收费"],
    ["payment.register", "登记收费"],
    ["payment.credit", "登记挂账"],
    ["payment.confirm", "财务确认"],
    ["payment.reopen", "重开收费"],
  ],
};

function repairModuleActions(moduleKey: string, availableActions: Set<string>) {
  return (repairModuleActionMap[moduleKey] || []).filter(([key]) => availableActions.has(key));
}

function RepairModuleCard({
  module,
  moduleKey,
  fallbackTitle,
  availableActions,
  loading,
  onAction,
}: {
  module?: AnyRecord;
  moduleKey: string;
  fallbackTitle: string;
  availableActions: Set<string>;
  loading: boolean;
  onAction: (actionKey: string) => void;
}) {
  const status = String(module?.status || "待处理");
  const actions = repairModuleActions(moduleKey, availableActions);
  const canRun = actions.length > 0;
  return (
    <section className={`order-card module-card ${canRun ? "actionable" : ""}`}>
      <div className="module-card-head">
        <h3>{String(module?.title || fallbackTitle)}</h3>
        <StatusTag value={status} />
      </div>
      <p>{String(module?.summary || "等待上一模块完成")}</p>
      {"amount" in (module || {}) && <strong className="module-money">报价 {poolMoney(module?.amount)}</strong>}
      {"receivable_amount" in (module || {}) && <strong className="module-money">待收 {poolMoney(module?.receivable_amount)}</strong>}
      <div className="inline-actions">
        {actions.map(([key, label]) => (
          <button type="button" className="mini-add-button" disabled={loading} key={key} onClick={() => onAction(key)}>
            {label}
          </button>
        ))}
        {!actions.length && <button type="button" className="ghost-mini-button" disabled>等待上一模块</button>}
      </div>
    </section>
  );
}

function OrderField({ label, value, editable, onChange, area, type = "text" }: { label: string; value: unknown; editable?: boolean; onChange?: (value: string) => void; area?: boolean; type?: string }) {
  return (
    <label className={'order-flow-field ' + (area ? 'wide' : '')}>
      <span>{label}</span>
      {editable ? (
        area ? <Input.TextArea value={String(value || "")} onChange={event => onChange?.(event.target.value)} /> : <Input type={type} value={String(value || "")} onChange={event => onChange?.(event.target.value)} />
      ) : (
        <strong>{String(value || "")}</strong>
      )}
    </label>
  );
}

function OrderChoiceLine({ label, value, editable, onChange, options }: { label: string; value: unknown; editable?: boolean; onChange?: (value: string) => void; options: string[] }) {
  const [open, setOpen] = useState(false);
  const text = String(value || "");
  const filtered = uniqueStrings(options).filter(option => !text || option.toLowerCase().includes(text.toLowerCase())).slice(0, 12);
  return (
    <div className="info-line order-editable-line order-choice-line">
      <span>{label}</span>
      {editable ? (
        <div className="choice-input-wrap">
          <Input value={text} onFocus={() => setOpen(true)} onChange={event => { onChange?.(event.target.value); setOpen(true); }} onBlur={() => window.setTimeout(() => setOpen(false), 120)} />
          {open && filtered.length > 0 && <div className="choice-popover">{filtered.map(option => <button type="button" key={option} onMouseDown={event => event.preventDefault()} onClick={() => { onChange?.(option); setOpen(false); }}>{option}</button>)}</div>}
        </div>
      ) : (
        <strong>{String(value || "")}</strong>
      )}
    </div>
  );
}

function OrderEditableLine({ label, value, editable, onChange, onFocus, pill, tag, highlight }: { label: string; value: unknown; editable?: boolean; onChange?: (value: string) => void; onFocus?: () => void; pill?: boolean; tag?: string; highlight?: boolean }) {
  return <div className={'info-line order-editable-line ' + (pill ? 'pill-value' : '')}><span>{label}</span>{editable ? <Input value={String(value || "")} onFocus={onFocus} onChange={event => onChange?.(event.target.value)} /> : <strong className={highlight ? "highlight" : ""}>{String(value || "")}{tag && <em>{tag}</em>}</strong>}</div>;
}

function buildStitchTimeline(mode: OrderMode, status: string, createdAt: string, owner: string) {
  if (mode === "new") return [
    { title: "填写工单", note: "录入客户、设备和故障信息", active: true },
    { title: "工单创建", note: "保存后生成工单编号" },
    { title: "检测试机", note: "创建后进入检测流程" },
    { title: "客户确认报价", note: "等待报价与客户确认" },
    { title: "待质检/完工", note: "等待后续流转" },
  ];
  if (mode === "cancel") return [
    { title: "工单创建", note: `${createdAt} | 客户前台`, done: true },
    { title: "取消确认", note: "填写原因并确认作废", active: true },
    { title: "已作废", note: "取消后不再继续流转" },
  ];
  return [
    { title: "工单创建", note: `${createdAt} | 客户前台`, done: true },
    { title: "检测试机", note: "工程师完成初检", done: true },
    { title: "客户确认报价", note: "线上或门店确认", done: status !== "维修中" },
    { title: status === "已完结" ? "维修完成" : "维修中（当前阶段）", note: `当前负责人：${owner}`, active: status !== "已完结" && status !== "已取消" },
    { title: "待质检/完工", note: "等待最终质检和归档", done: status === "已完结" },
  ];
}

function buildOrderTimeline(mode: OrderMode, status: string, owner: string) {
  if (mode === "new") return [
    { title: "填写工单", note: "录入客户、设备和故障信息", active: true },
    { title: "创建成功", note: "保存后生成工单编号" },
    { title: "进入检测", note: "等待指派或检测" },
  ];
  if (mode === "cancel") return [
    { title: "工单创建", note: "已生成业务记录", done: true },
    { title: "取消确认", note: "填写原因并确认作废", active: true },
    { title: "已作废", note: "取消后不再继续流转" },
  ];
  return [
    { title: "工单创建", note: "客户前台已建单", done: true },
    { title: "检测/报价", note: status === "维修中" ? "正在推进检测或维修" : "已完成检测报价", done: status !== "维修中" },
    { title: status, note: `当前负责人：${owner}`, active: canModifyOrderStatus(status) },
    { title: "完结归档", note: "完成交付和财务确认", done: status === "已完结" },
  ];
}

function canModifyOrderStatus(status: string) {
  return !["已完结", "已取消", "已作废"].includes(status);
}

function canModifyRepairItems(status: string) {
  return !["已完结", "已取消", "已作废", "已交付"].includes(status);
}

function LegacyOrderDetailPage({ orderId, notify, onBack }: { orderId: number | string | null; notify: (message: string, error?: boolean) => void; onBack: () => void }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["repair-workbench-detail", orderId],
    queryFn: () => api<AnyRecord>(`/api/repair-workbench/${orderId}`),
    enabled: Boolean(orderId),
  });
  const mutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>(`/api/repair-orders/${orderId}/workflow-action`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      notify("工单操作已提交");
      query.refetch();
      queryClient.invalidateQueries({ queryKey: ["repair-workbench"] });
    },
    onError: error => notify(error instanceof Error ? error.message : "操作失败", true),
  });

  if (!orderId) return <div className="order-detail-empty"><button type="button" onClick={onBack}><ArrowLeft size={18} />返回</button><strong>没有选中的工单</strong></div>;
  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;

  const data = query.data || {};
  const order = ((data.order || data) as AnyRecord) || {};
  const events = ((data.events as AnyRecord[] | undefined) || []).slice(0, 8);
  const incomeItems = ((data.income_items as AnyRecord[] | undefined) || []);
  const costItems = ((data.cost_items as AnyRecord[] | undefined) || []);
  const repairItems = ((data.repair_items as AnyRecord[] | undefined) || []);
  const payments = ((data.payments as AnyRecord[] | undefined) || []);
  const createdAt = String(order.created_at || order.opened_at || "");
  const owner = String(order.assigned_to || order.engineer_user || "");
  const model = String(order.model || "");
  const colorCapacity = [order.color || "", order.memory || order.capacity || ""].filter(Boolean).join(" / ");
  const imei = String(order.imei || order.serial || "");
  const customer = String(order.customer_name || "");
  const phone = String(order.phone || order.customer_phone || "");
  const quoted = Number(order.quoted_amount || incomeItems.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  const cost = Number(order.cost_amount || costItems.reduce((sum, row) => sum + Number(row.total_cost || row.unit_cost || 0), 0));
  const paid = Number(order.paid_amount || payments.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  const detailRows = repairItems;
  const inspections = ["屏幕显示", "触摸功能", "摄像头", "电池健康", "生物识别", "无线网络", "蜂窝网络", "音频模块", "指南针", "扬声器", "听筒", "充电"];
  const timeline = [
    { title: "工单创建", note: `${createdAt} | 客户前台`, done: true },
    { title: "检测试机", note: "2023-10-27 15:10 | 工程师 李四", done: true },
    { title: "客户确认报价", note: "2023-10-27 16:00 | 线上确认", done: true },
    { title: "维修中（当前阶段）", note: `正在更换物料 | ${owner}`, active: true },
    { title: "待质检/完工", note: "等待下一步处理" },
  ];

  function workflow(action: string) {
    if (action === "transfer") {
      const assignedTo = window.prompt("请输入转派工程师", owner);
      if (!assignedTo) return;
      mutation.mutate({ action: "assign", assigned_to: assignedTo });
      return;
    }
    if (action === "edit") {
      notify("编辑入口已打开：当前版本沿用详情页字段展示，后续可接入完整编辑表单。");
      return;
    }
    mutation.mutate({ action });
  }

  return (
    <div className="order-detail-page">
      <header className="order-detail-topbar">
        <div className="order-detail-title">
          <button type="button" className="back-button" onClick={onBack}><ArrowLeft size={24} /></button>
          <h1>工单详情</h1>
        </div>
        <div className="order-detail-search"><Search size={22} /><Input allowClear placeholder="?????IMEI???..." /></div>
        <div className="order-detail-icons">
          <button type="button" className="icon-button"><Bell size={23} /><span /></button>
          <button type="button" className="icon-button"><UserRound size={23} /></button>
        </div>
      </header>

      <section className="order-hero">
        <div>
          <div className="order-heading-line"><h2>工单: {String(order.order_no || order.repair_order_id || orderId)}</h2><span className="order-status-pill">{String(order.status || "维修中")}</span></div>
          <p>创建于 {createdAt} | 负责人: {owner}</p>
        </div>
        <div className="order-hero-actions">
          <button type="button" onClick={() => workflow("edit")}><Edit3 size={20} />编辑</button>
          <button type="button" onClick={() => workflow("transfer")}><UserPlus size={20} />订单转派</button>
        </div>
      </section>

      <div className="order-detail-layout">
        <div className="order-main-column">
          <section className="order-card device-card">
            <h3><Smartphone size={24} />设备详细信息</h3>
            <div className="order-info-grid">
              <InfoLine label="手机型号" value={model} />
              <InfoLine label="IMEI / 序列号" value={imei} pill />
              <InfoLine label="颜色/容量" value={colorCapacity} />
            </div>
          </section>

          <section className="order-card customer-card">
            <div className="order-info-grid compact">
              <InfoLine label="客户姓名" value={customer} tag="零售客户" />
              <InfoLine label="联系方式" value={phone} highlight />
            </div>
          </section>

          <InspectionCard title="维修前检测 (Pre-Repair)" inspections={inspections} note={String(order.diagnosis || "其他检测备注...")} />

          <section className="order-card">
            <h3><FileText size={24} />故障与维修详情</h3>
            <p className="order-muted">{String(order.fault_description || "客户反馈设备异常，需要检测并维修。")}</p>
            <div className="repair-lines">
              <AppTable
                rows={detailRows}
                columns={[["item_name", "????"], ["sku", "SKU"], ["unit_cost", "????"], ["service_fee", "????"], ["line_total", "??"]]}
                formatValue={(row, key) => {
                  const unitCost = Number(row.total_cost || row.unit_cost || 0);
                  const amount = Number(row.amount || row.charge_amount || row.price || 0);
                  if (key === "item_name") return String(row.item_name || row.fault_name || row.material_name || "");
                  if (key === "sku") return String(row.sku || row.material_code || "-");
                  if (key === "unit_cost") return formatMoney(unitCost);
                  if (key === "service_fee") return formatMoney(Math.max(amount - unitCost, 0));
                  if (key === "line_total") return formatMoney(amount || unitCost);
                  return displayValue(row, key);
                }}
                isStatusKey={() => false}
              />
            </div>
            <div className="order-fee-summary">
              <span>报价金额 <b>{formatMoney(quoted || 1280)}</b></span>
              <span>成本 <b>{formatMoney(cost || 680)}</b></span>
              <span>已收款 <b>{formatMoney(paid)}</b></span>
            </div>
          </section>

          <InspectionCard title="维修后检测 (Post-Repair)" inspections={inspections.slice(0, 8)} note="质检备注..." compact />

          <section className="order-card">
            <h3><ClipboardList size={24} />维修历史</h3>
            <div className="history-list">
              {(events.length ? events : [{ title: "客户确认报价", detail: "线上确认报价并进入维修阶段", created_at: createdAt, operator: owner }]).slice(0, 4).map((event, index) => (
                <div key={String(event.event_id || event.created_at || index)}><b>{String(event.title || "系统记录")}</b><span>{String(event.detail || event.remark || "工单状态已更新")}</span><em>{String(event.created_at || "")} {String(event.operator || "")}</em></div>
              ))}
            </div>
          </section>
        </div>

        <aside className="order-side-column">
          <section className="order-card">
            <h3>订单状态</h3>
            <div className="detail-timeline">
              {timeline.map((item) => <div className={`timeline-step ${item.done ? "done" : ""} ${item.active ? "active" : ""}`} key={item.title}><span>{item.done ? <CheckCircle2 size={18} /> : item.active ? <Users size={18} /> : <Flag size={18} />}</span><div><b>{item.title}</b><p>{item.note}</p></div></div>)}
            </div>
          </section>

          <section className="order-card notes-card">
            <div className="side-title-row"><h3>备注信息</h3><CirclePlus size={22} /></div>
            <div className="note-box warning"><b>内部备注</b><p>{String(order.remark || "客户要求尽量保留原厂原色原彩，维修后请务必同步写入数据。")}</p></div>
            <div className="note-box muted"><b>交付说明</b><p>告知客户外壳磕碰处无法复原，仅保证屏幕功能完好。</p></div>
          </section>

          <section className="order-card log-card">
            <h3>系统操作日志</h3>
            {(events.length ? events : [{ title: "价格变更通知", detail: "财务组已确认优惠申请", created_at: "10-27 16:45" }, { title: "订单负责人变更", detail: "由李四转交给张工", created_at: "10-27 15:30" }]).slice(0, 5).map((event, index) => (
              <div className="log-item" key={String(event.event_id || event.created_at || index)}><b>{String(event.title || "系统操作")}</b><p>{String(event.detail || "工单信息已更新")}</p><span>{String(event.created_at || "")}</span></div>
            ))}
          </section>
        </aside>
      </div>
    </div>
  );
}

function InfoLine({ label, value, pill, tag, highlight }: { label: string; value: unknown; pill?: boolean; tag?: string; highlight?: boolean }) {
  return <div className={`info-line ${pill ? "pill-value" : ""}`}><span>{label}</span><strong className={highlight ? "highlight" : ""}>{String(value || "")}{tag && <em>{tag}</em>}</strong></div>;
}


function EditableInspectionCard({ title, inspections, note, compact, mode = "view", state = {}, photos = [], stage, editing = false, saved = false, onStart, onSave, onCancel, onToggle, onNoteChange, onUpload, onOpenPhoto, uploading }: { title: string; inspections: string[]; note: string; compact?: boolean; mode?: OrderMode; state?: Record<string, boolean>; photos?: AnyRecord[]; stage?: "pre" | "post"; editing?: boolean; saved?: boolean; onStart?: () => void; onSave?: () => void; onCancel?: () => void; onToggle?: (item: string) => void; onNoteChange?: (value: string) => void; onUpload?: (stage: "pre" | "post", file: File | null) => void; onOpenPhoto?: (photo: AnyRecord) => void; uploading?: boolean }) {
  const editable = saved ? false : mode === "new" || mode === "edit" || editing;
  const visibleInspections = editable ? inspections : inspections.filter(item => state[item]);
  const needsOtherNote = editable && Boolean(state["其他异常"]);
  return (
    <section className={'order-card inspection-card ' + (compact ? 'compact' : '')}>
      <div className="inspection-head">
        <h3><span />{title}</h3>
        <div className="inspection-actions">
          {!editable && <AppButton className="ghost-mini-button" onClick={onStart}>{saved ? "修改检测结果" : "开始检测"}</AppButton>}
          {editable && stage && <AppButton className="mini-add-button" onClick={onSave} disabled={uploading}>保存检测</AppButton>}
          {editing && <AppButton className="ghost-mini-button" onClick={onCancel}>??</AppButton>}
        </div>
      </div>
      {visibleInspections.length ? <div className="inspection-grid">{visibleInspections.map(item => <button type="button" className={state[item] ? "abnormal" : ""} key={item} disabled={!editable} onClick={() => onToggle?.(item)}><b>{item}</b><span>{state[item] ? "异常" : "正常"}</span></button>)}</div> : <div className="inspection-empty">{saved ? "无异常项目" : "无异常功能"}</div>}
      <Input.TextArea className={'inspection-note ' + (needsOtherNote && !String(note || "").trim() ? 'required' : '')} value={note} readOnly={!editable} placeholder={needsOtherNote ? "请填写其他异常说明..." : "检测备注..."} onChange={event => onNoteChange?.(event.currentTarget.value)} />
      {!compact && <div className="photo-strip">{photos.length ? photos.map(photo => <button type="button" className="photo-thumb-button" key={String(photo.photo_id || photo.url)} onClick={() => onOpenPhoto?.(photo)}><img className="photo-thumb" src={String(photo.url || "")} alt={String(photo.filename || "维修照片")} /></button>) : <div className="photo-thumb" />}{stage && <label className={'upload-tile ' + (uploading ? 'disabled' : '')}><Camera size={24} />{uploading ? "上传中" : "上传"}<input type="file" accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={event => { onUpload?.(stage, event.currentTarget.files?.[0] || null); event.currentTarget.value = ""; }} /></label>}</div>}
    </section>
  );
}

function InspectionCard({ title, inspections, note, compact, mode = "view", state = {}, photos = [], stage, onToggle, onUpload, uploading }: { title: string; inspections: string[]; note: string; compact?: boolean; mode?: OrderMode; state?: Record<string, boolean>; photos?: AnyRecord[]; stage?: "pre" | "post"; onToggle?: (item: string) => void; onUpload?: (stage: "pre" | "post", file: File | null) => void; uploading?: boolean }) {
  const editable = mode === "new" || mode === "edit";
  const visibleInspections = editable ? inspections : inspections.filter(item => state[item]);
  return (
    <section className={`order-card inspection-card ${compact ? "compact" : ""}`}>
      <div className="inspection-head"><h3><span />{title}</h3></div>
      {visibleInspections.length ? <div className="inspection-grid">{visibleInspections.map(item => <button type="button" className={state[item] ? "abnormal" : ""} key={item} disabled={!editable} onClick={() => onToggle?.(item)}><b>{item}</b><span>{state[item] ? "异常" : "正常"}</span></button>)}</div> : <div className="inspection-empty">无异常功能</div>}
      <Input className="inspection-note" value={note} readOnly />
      {!compact && <div className="photo-strip">{photos.length ? photos.map(photo => <img className="photo-thumb" key={String(photo.photo_id || photo.url)} src={String(photo.url || "")} alt={String(photo.filename || "维修照片")} />) : <div className="photo-thumb" />}{stage && <label className={`upload-tile ${uploading ? "disabled" : ""}`}><Camera size={24} />{uploading ? "上传中" : "上传"}<input type="file" accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={event => { onUpload?.(stage, event.currentTarget.files?.[0] || null); event.currentTarget.value = ""; }} /></label>}</div>}
    </section>
  );
}

function InfoBlock({ label, text }: { label: string; text: unknown }) {
  return <div className="field-block"><span>{label}</span><strong>{String(text || "")}</strong></div>;
}

function DetailSection({ title, rows, columns }: { title: string; rows?: AnyRecord[]; columns: Array<[string, string]> }) {
  return <section className="detail-section"><h3>{title}</h3><DataTable rows={rows || []} columns={columns} /></section>;
}


function RecyclePool({ openModal }: { openModal: (node: ReactNode | null) => void }) {
  const [keyword, setKeyword] = useState("");
  const query = useQuery({ queryKey: ["machines", keyword], queryFn: () => api<AnyRecord[]>("/api/machines?q=" + encodeURIComponent(keyword)) });
  const rows = (query.data || []).filter(row => row.source_type === "??");
  async function open(row: AnyRecord) {
    const timeline = await api<AnyRecord>("/api/machines/" + row.machine_id + "/timeline");
    openModal(<MachineTimeline timeline={timeline} />);
  }
  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;
  return (
    <Panel title="?????">
      <div className="toolbar filters"><Input allowClear value={keyword} onChange={event => setKeyword(event.target.value)} placeholder="?????IMEI??????" /></div>
      <DataTable rows={rows} onRowClick={open} columns={[["machine_no", "????"], ["imei", "IMEI"], ["model", "??"], ["customer_name", "??"], ["current_status", "????"], ["updated_at", "????"]]} />
    </Panel>
  );
}

function MachineTimeline({ timeline }: { timeline: AnyRecord }) {
  const machine = timeline.machine as AnyRecord;
  const customer = (timeline.customer || {}) as AnyRecord;
  return <><header className="modal-header"><div><h2>{String(machine.machine_no)} / {String(machine.model)}</h2><p>机器 ID {String(machine.machine_id)} · {String(machine.current_status)}</p></div></header><div className="modal-content"><div className="repair-detail-grid"><InfoBlock label="IMEI" text={machine.imei} /><InfoBlock label="序列号" text={machine.serial} /><InfoBlock label="客户" text={customer.name || machine.customer_name} /><InfoBlock label="电话" text={customer.phone} /></div><DetailSection title="维修记录" rows={timeline.repair_orders as AnyRecord[]} columns={[["repair_order_id", "维修单"], ["status", "状态"], ["assigned_to", "工程师"], ["fault_description", "故障"], ["quoted_amount", "报价"]]} /><DetailSection title="回收记录" rows={timeline.recycle_orders as AnyRecord[]} columns={[["recycle_order_id", "回收单"], ["status", "状态"], ["inspection_result", "验机结论"], ["quoted_amount", "报价"], ["paid_amount", "已付"]]} /></div></>;
}

const customerMachineFields = [
  { name: "customer_name", label: "客户姓名", placeholder: "客户姓名" },
  { name: "phone", label: "联系电话", placeholder: "联系电话" },
  { name: "imei", label: "IMEI", placeholder: "IMEI" },
  { name: "serial", label: "序列号", placeholder: "序列号" },
  { name: "model", label: "机型", required: true, options: modelOptions.map(value => ({ value, label: value })) },
  { name: "memory", label: "内存", placeholder: "内存" },
  { name: "color", label: "颜色", placeholder: "颜色" },
  { name: "condition", label: "机况", placeholder: "机况" },
];

function RepairOpenPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({ mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/repair-orders", { method: "POST", body: JSON.stringify(payload) }), onSuccess: data => { notify(`维修单已创建：${String(data.repair_order_id)}`); queryClient.invalidateQueries({ queryKey: ["repair-workbench"] }); }, onError: e => notify(e instanceof Error ? e.message : "创建失败", true) });
  return <AppFormSection title="维修到店开单" loading={mutation.isPending} onSubmit={(data, helpers) => { mutation.mutate({ machine_id: data.machine_id || null, machine: data.machine_id ? null : machinePayload(data), customer: customerPayload(data), fault_description: data.fault_description || "" }); helpers.reset(); }} fields={[...customerMachineFields, { name: "fault_description", label: "故障描述", placeholder: "故障描述", area: true }]} />;
}

function RecycleOpenPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const mutation = useMutation({ mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/recycle-orders", { method: "POST", body: JSON.stringify(payload) }), onSuccess: data => notify(`回收单已创建：${String(data.recycle_order_id)}`), onError: e => notify(e instanceof Error ? e.message : "创建失败", true) });
  return <AppFormSection title="回收到店开单" loading={mutation.isPending} onSubmit={(data, helpers) => { mutation.mutate({ machine_id: data.machine_id || null, machine: data.machine_id ? null : machinePayload(data), customer: customerPayload(data), inspection_note: data.inspection_note || "" }); helpers.reset(); }} fields={[...customerMachineFields, { name: "inspection_note", label: "验机记录", placeholder: "验机记录", area: true }]} />;
}

function machinePayload(data: AnyRecord) {
  return { imei: data.imei || "", serial: data.serial || "", model: data.model, memory: data.memory || "", color: data.color || "", condition: data.condition || "", remark: data.remark || "" };
}

function customerPayload(data: AnyRecord) {
  if (!data.customer_name) return null;
  return { name: data.customer_name, phone: data.phone || "", wechat: data.wechat || "", category: data.customer_type || "个人客户", remark: data.customer_remark || "" };
}

function WarehousePage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["warehouse"], queryFn: () => api<AnyRecord>("/api/warehouse") });
  const post = useMutation({ mutationFn: ({ path, payload }: { path: string; payload: AnyRecord }) => api(path, { method: "POST", body: JSON.stringify(payload) }), onSuccess: () => { notify("仓库单据已保存"); queryClient.invalidateQueries({ queryKey: ["warehouse"] }); }, onError: e => notify(e instanceof Error ? e.message : "保存失败", true) });
  const data = query.data || {};
  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;
  return <div className="stack"><Panel title="库存管理" note="物料编码、批次、单件码、申领发放、退料退货和库存流水。" action={<AppButton onClick={() => query.refetch()}><RefreshCw size={16} />刷新</AppButton>}><DataTable rows={data.materials as AnyRecord[]} columns={[["material_id", "ID"], ["material_code", "物料代码"], ["sku", "SKU"], ["name", "物料"], ["category_code", "类别"], ["compatible_range", "适配"], ["current_qty", "可用"], ["min_qty", "低库存"]]} /></Panel><div className="dashboard-grid"><AppFormSection title="采购/临采入库" loading={post.isPending} onSubmit={(payload, helpers) => { const kind = String(payload.batch_kind || "purchase"); const { batch_kind, ...rest } = payload; post.mutate({ path: `/api/material-batches/${kind}`, payload: rest }); helpers.reset(); }} fields={[
    { name: "batch_kind", label: "入库类型", initialValue: "purchase", options: [{ value: "purchase", label: "采购入库" }, { value: "ad-hoc", label: "临采入库" }] },
    { name: "material_id", label: "物料 ID", placeholder: "物料 ID", required: true, type: "number" },
    { name: "supplier", label: "供应商", placeholder: "供应商", initialValue: "待确认" },
    { name: "qty", label: "数量", min: 1, placeholder: "数量", required: true, type: "number" },
    { name: "unit_cost", label: "单价", placeholder: "单价", step: "0.01", type: "number" },
    { name: "remark", label: "备注", placeholder: "备注", area: true },
  ]} /><AppFormSection title="申领发放" loading={post.isPending} onSubmit={(payload, helpers) => { post.mutate({ path: "/api/material-requests", payload: { repair_order_id: payload.repair_order_id || null, engineer_user: payload.engineer_user || "", items: [{ material_id: payload.material_id, repair_sku_id: payload.repair_sku_id, qty: payload.qty || 1, remark: payload.remark || "" }], remark: payload.remark || "" } }); helpers.reset(); }} fields={[
    { name: "repair_order_id", label: "维修工单 ID", placeholder: "维修工单 ID", type: "number" },
    { name: "engineer_user", label: "工程师账号", placeholder: "工程师账号" },
    { name: "material_id", label: "物料 ID", placeholder: "物料 ID", required: true, type: "number" },
    { name: "qty", label: "数量", defaultValue: "1", min: 1, placeholder: "数量", type: "number" },
    { name: "remark", label: "申领备注", placeholder: "申领备注", area: true },
  ]} /></div><div className="dashboard-grid"><Panel title="申领单"><DataTable rows={data.requests as AnyRecord[]} columns={[["request_id", "ID"], ["request_no", "申领单"], ["status", "状态"], ["engineer_user", "工程师"], ["repair_order_id", "工单"], ["created_at", "时间"], ["remark", "备注"]]} /></Panel><Panel title="库存流水"><DataTable rows={data.movements as AnyRecord[]} columns={[["happened_at", "时间"], ["movement_type", "类型"], ["direction", "方向"], ["material_code", "物料代码"], ["name", "物料"], ["qty", "数量"], ["actor", "操作人"]]} /></Panel></div></div>;
}

function InventoryPage() {
  const materials = useQuery({ queryKey: ["materials"], queryFn: () => api<AnyRecord>("/api/materials") });
  const inventory = useQuery({ queryKey: ["inventory"], queryFn: () => api<AnyRecord[]>("/api/inventory") });
  if (materials.isLoading || inventory.isLoading || materials.error || inventory.error) return <QueryState loading={materials.isLoading || inventory.isLoading} error={materials.error || inventory.error} />;
  return <div className="stack"><Panel title="维修物料库存"><DataTable rows={materials.data?.materials as AnyRecord[]} columns={[["sku", "SKU"], ["name", "物料"], ["compatible_range", "适配范围"], ["current_qty", "库存"], ["avg_cost", "均价"], ["status", "状态"]]} /></Panel><Panel title="回收机器库存"><DataTable rows={inventory.data} columns={[["inventory_item_id", "库存ID"], ["machine_id", "机器ID"], ["imei", "IMEI"], ["model", "机型"], ["status", "库存状态"], ["cost_amount", "成本"], ["sale_price", "销售定价"]]} /></Panel></div>;
}


function CustomersPage() {
  const [q, setQ] = useState("");
  const query = useQuery({ queryKey: ["customers", q], queryFn: () => api<AnyRecord[]>("/api/customers?q=" + encodeURIComponent(q)) });
  return (
    <Panel title="????">
      <div className="toolbar filters">
        <Input allowClear value={q} onChange={event => setQ(event.target.value)} placeholder="???????????" />
        <AppButton onClick={() => query.refetch()}><Search size={16} />??</AppButton>
      </div>
      <QueryState loading={query.isLoading} error={query.error} />
      <DataTable rows={query.data} columns={[["customer_id", "ID"], ["name", "??"], ["phone", "??"], ["category", "??"], ["shop_name", "??"], ["tags", "??"]]} empty="??????" />
    </Panel>
  );
}

function PaymentsPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["payments"], queryFn: () => api<AnyRecord[]>("/api/payments") });
  const mutation = useMutation({ mutationFn: (payload: AnyRecord) => api("/api/payments", { method: "POST", body: JSON.stringify(payload) }), onSuccess: () => { notify("流水已登记"); queryClient.invalidateQueries({ queryKey: ["payments"] }); }, onError: e => notify(e instanceof Error ? e.message : "登记失败", true) });
  return <div className="split"><AppFormSection title="登记收支流水" loading={mutation.isPending} onSubmit={(payload, helpers) => { mutation.mutate(payload); helpers.reset(); }} fields={[
    { name: "source_type", label: "来源", initialValue: "repair", options: [{ value: "repair", label: "维修单" }, { value: "sale", label: "销售单" }, { value: "recycle", label: "回收单" }] },
    { name: "source_id", label: "单据 ID", placeholder: "单据 ID", required: true, type: "number" },
    { name: "direction", label: "方向", initialValue: "收入", options: [{ value: "收入", label: "收入" }, { value: "支出", label: "支出" }] },
    { name: "amount", label: "金额", placeholder: "金额", required: true, step: "0.01", type: "number" },
    { name: "method", label: "方式", placeholder: "方式" },
    { name: "payer", label: "付款方", placeholder: "付款方" },
    { name: "payee", label: "收款方", placeholder: "收款方" },
    { name: "remark", label: "备注", placeholder: "备注", area: true },
  ]} /><Panel title="流水列表"><QueryState loading={query.isLoading} error={query.error} /><DataTable rows={query.data} columns={[["payment_id", "ID"], ["source_type", "来源"], ["source_id", "单据"], ["direction", "方向"], ["amount", "金额"], ["method", "方式"], ["transaction_no", "流水号"], ["status", "状态"], ["received_by", "收款人"], ["confirmed_by", "确认人"], ["created_at", "时间"]]} /></Panel></div>;
}

function SalesPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const mutation = useMutation({ mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/sales-orders", { method: "POST", body: JSON.stringify(payload) }), onSuccess: data => notify(`销售单已创建：${String(data.sales_order_id)}`), onError: e => notify(e instanceof Error ? e.message : "创建失败", true) });
  return <AppFormSection title="销售开单" loading={mutation.isPending} onSubmit={(data, helpers) => { mutation.mutate({ inventory_item_id: data.inventory_item_id, customer: customerPayload(data), sale_price: data.sale_price, salesperson: data.salesperson, remark: data.remark || "" }); helpers.reset(); }} fields={[
    { name: "inventory_item_id", label: "库存 ID", placeholder: "库存 ID", required: true, type: "number" },
    { name: "customer_name", label: "客户姓名", placeholder: "客户姓名" },
    { name: "phone", label: "联系电话", placeholder: "联系电话" },
    { name: "sale_price", label: "销售价格", placeholder: "销售价格", required: true, step: "0.01", type: "number" },
    { name: "salesperson", label: "销售人", placeholder: "销售人", required: true },
    { name: "remark", label: "备注", placeholder: "备注", area: true },
  ]} />;
}

function ReportsPage() {
  const query = useQuery({ queryKey: ["machine-reports"], queryFn: () => api<AnyRecord>("/api/machine-reports") });
  const income = ((query.data?.payment_totals as AnyRecord[] | undefined) || []).find(x => x.direction === "收入")?.amount || 0;
  const expense = ((query.data?.payment_totals as AnyRecord[] | undefined) || []).find(x => x.direction === "支出")?.amount || 0;
  return <div className="stack"><QueryState loading={query.isLoading} error={query.error} /><div className="metric-grid"><div className="metric"><span>在售库存</span><strong>{String(query.data?.inventory_count || 0)}</strong></div><div className="metric"><span>库存成本</span><strong>{formatMoney(query.data?.inventory_cost || 0)}</strong></div><div className="metric"><span>收入流水</span><strong>{formatMoney(income)}</strong></div><div className="metric"><span>支出流水</span><strong>{formatMoney(expense)}</strong></div></div><Panel title="库存明细"><DataTable rows={query.data?.inventory as AnyRecord[]} columns={[["inventory_item_id", "库存ID"], ["machine_no", "机器编号"], ["imei", "IMEI"], ["model", "机型"], ["status", "状态"], ["cost_amount", "成本"], ["sale_price", "销售定价"]]} /></Panel></div>;
}

function DeviceModelSettings({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const queryClient = useQueryClient();
  const emptyModelForm = { brand: "Apple", enabled: "true", sort_order: 100 };
  const [modelForm, setModelForm] = useState<AnyRecord>(emptyModelForm);
  const [keyword, setKeyword] = useState("");
  const query = useQuery({ queryKey: ["device-models-settings", keyword], queryFn: () => api<AnyRecord[]>(`/api/device-models?q=${encodeURIComponent(keyword)}`) });
  const mutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/device-models", {
      method: "POST",
      body: JSON.stringify({
        ...payload,
        colors: splitOptionText(payload.colors_text ?? payload.colors),
        capacities: splitOptionText(payload.capacities_text ?? payload.capacities),
        enabled: payload.enabled !== false && payload.enabled !== "false",
        sort_order: Number(payload.sort_order || 100),
      }),
    }),
    onSuccess: () => {
      notify("设备型号已保存");
      setModelForm(emptyModelForm);
      queryClient.invalidateQueries({ queryKey: ["device-models-settings"] });
      queryClient.invalidateQueries({ queryKey: ["device-models"] });
    },
    onError: error => notify(error instanceof Error ? error.message : "保存失败", true),
  });
  const rows = query.data || [];
  return (
    <Panel title="设备型号管理" note="维护开单页可选的设备型号、颜色和容量。颜色/容量可用逗号、顿号或换行分隔。">
      <AppFormSection
        clearText="清空"
        fields={[
          { name: "brand", label: "品牌", placeholder: "Apple", initialValue: "Apple" },
          { name: "model_name", label: "型号名称", placeholder: "iPhone 16 Pro", required: true },
          { name: "sort_order", label: "排序", initialValue: 100, type: "number" },
          { name: "enabled", label: "状态", initialValue: "true", options: [{ value: "true", label: "启用" }, { value: "false", label: "停用" }] },
          { name: "colors_text", label: "颜色", placeholder: "黑色、白色、蓝色", area: true },
          { name: "capacities_text", label: "容量/内存", placeholder: "128GB、256GB、512GB", area: true },
          { name: "remark", label: "备注", placeholder: "备注", area: true },
        ]}
        loading={mutation.isPending}
        values={modelForm}
        onClear={() => setModelForm(emptyModelForm)}
        onSubmit={(payload, helpers) => { mutation.mutate(payload); helpers.reset(); }}
        submitText="保存设备型号"
        title="设备型号"
      />
      <div className="toolbar filters"><Input value={keyword} onChange={event => setKeyword(event.target.value)} placeholder="搜索品牌、型号" allowClear /></div>
      <QueryState loading={query.isLoading} error={query.error} />
      <AppTable
        rows={rows}
        columns={[["brand", "品牌"], ["model_name", "型号"], ["colors", "颜色"], ["capacities", "容量/内存"], ["sort_order", "排序"], ["enabled", "状态"]]}
        formatValue={(row, key) => {
          if (key === "colors" || key === "capacities") return optionArray(row[key]).join("、") || "-";
          if (key === "enabled") return row.enabled ? "启用" : "停用";
          return displayValue(row, key);
        }}
        isStatusKey={(key) => key === "enabled"}
        actions={{ render: row => <AppButton onClick={() => setModelForm({ ...row, enabled: row.enabled ? "true" : "false", colors_text: optionArray(row.colors).join("、"), capacities_text: optionArray(row.capacities).join("、") })}>编辑</AppButton> }}
      />
    </Panel>
  );
}

function RepairSkuSettings({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const queryClient = useQueryClient();
  const emptySkuForm = { model: "", enabled: "true" };
  const [skuForm, setSkuForm] = useState<AnyRecord>(emptySkuForm);
  const [skuKeyword, setSkuKeyword] = useState("");
  const query = useQuery({ queryKey: ["repair-skus-settings", skuKeyword], queryFn: () => api<AnyRecord[]>(`/api/repair-skus?q=${encodeURIComponent(skuKeyword)}`) });
  const mutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/repair-skus", { method: "POST", body: JSON.stringify({ ...payload, cost_amount: Number(payload.cost_amount || 0), charge_amount: Number(payload.charge_amount || 0), enabled: payload.enabled !== false && payload.enabled !== "false" }) }),
    onSuccess: () => {
      notify("故障代码已保存");
      setSkuForm(emptySkuForm);
      queryClient.invalidateQueries({ queryKey: ["repair-skus-settings"] });
      queryClient.invalidateQueries({ queryKey: ["repair-skus"] });
    },
    onError: error => notify(error instanceof Error ? error.message : "保存失败", true),
  });
  const rows = query.data || [];
  return (
    <Panel title="故障代码维护" note="维护按机型匹配的维修故障代码、维修方案/SKU 和默认价格。空机型表示通用。">
      <AppFormSection
        clearText="清空"
        fields={[
          { name: "model", label: "适用机型", placeholder: "通用可留空" },
          { name: "sku_code", label: "故障代码", placeholder: "SCREEN-OLED", required: true },
          { name: "fault_name", label: "故障名称", placeholder: "屏幕损坏", required: true },
          { name: "solution_name", label: "维修方案/SKU", placeholder: "更换屏幕总成", required: true },
          { name: "cost_amount", label: "配件成本", step: "0.01", type: "number" },
          { name: "charge_amount", label: "工时/服务费", step: "0.01", type: "number" },
          { name: "enabled", label: "状态", initialValue: "true", options: [{ value: "true", label: "启用" }, { value: "false", label: "停用" }] },
          { name: "remark", label: "备注", placeholder: "备注", area: true },
        ]}
        loading={mutation.isPending}
        values={skuForm}
        onClear={() => setSkuForm(emptySkuForm)}
        onSubmit={(payload, helpers) => { mutation.mutate(payload); helpers.reset(); }}
        submitText="保存故障代码"
        title="故障代码"
      />
      <div className="toolbar filters"><Input value={skuKeyword} onChange={event => setSkuKeyword(event.target.value)} placeholder="搜索故障代码、名称、方案" allowClear /></div>
      <QueryState loading={query.isLoading} error={query.error} />
      <AppTable
        rows={rows}
        columns={[["model", "机型"], ["sku_code", "故障代码"], ["fault_name", "故障名称"], ["solution_name", "维修方案/SKU"], ["cost_amount", "配件成本"], ["charge_amount", "工时/服务费"], ["enabled", "状态"]]}
        formatValue={(row, key) => {
          if (key === "model") return String(row.model || "通用");
          if (key === "cost_amount" || key === "charge_amount") return formatMoney(row[key]);
          if (key === "enabled") return row.enabled ? "启用" : "停用";
          return displayValue(row, key);
        }}
        isStatusKey={(key) => key === "enabled"}
        actions={{ render: row => <AppButton onClick={() => setSkuForm({ ...row, enabled: row.enabled ? "true" : "false" })}>编辑</AppButton> }}
      />
    </Panel>
  );
}

function AuditPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const query = useQuery({ queryKey: ["audit"], queryFn: () => api<AnyRecord[]>("/api/audit-logs") });
  return <div className="stack"><DeviceModelSettings notify={notify} /><RepairSkuSettings notify={notify} /><Panel title="系统设置 / 操作日志"><QueryState loading={query.isLoading} error={query.error} /><DataTable rows={query.data} columns={[["time", "时间"], ["username", "用户"], ["role", "角色"], ["action", "动作"], ["target_type", "对象"], ["target_id", "ID"], ["result", "结果"]]} /></Panel></div>;
}

export default App;
