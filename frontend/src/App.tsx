import { ReactNode, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
  ChevronDown,
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

type ViewKey = "dashboard" | "repairPool" | "orderDetail" | "recyclePool" | "repair" | "recycle" | "warehouse" | "inventory" | "sales" | "customers" | "payments" | "reports" | "audit";
type OrderMode = "new" | "view" | "edit" | "cancel";
type Toast = { message: string; error?: boolean } | null;
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

function formatMoney(input: unknown) {
  const amount = Number(input || 0);
  return `¥${amount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function displayValue(row: AnyRecord, key: string) {
  const raw = row[key];
  if (raw === null || raw === undefined || raw === "") return "-";
  if (moneyKeys.has(key)) return formatMoney(raw);
  if (Array.isArray(raw)) return raw.join("、") || "-";
  return String(raw);
}

function badgeClass(input: unknown) {
  const text = String(input || "");
  if (["已交付", "已完结", "已结单", "成功", "财务已确认", "已售出", "已完成"].includes(text)) return "done";
  if (["维修中", "待检测", "待报价确认", "待交付检测", "检测中", "已报价", "待分配", "待备料"].includes(text)) return "pending";
  if (["同行挂账", "财务待确认", "未收款", "待支付"].includes(text)) return "warning";
  if (["回收库存", "在库可用"].includes(text)) return "success";
  return "neutral";
}

function sortRows(rows: AnyRecord[], sort: SortState) {
  return [...rows].sort((a, b) => {
    const av = a[sort.key];
    const bv = b[sort.key];
    const an = Number(av);
    const bn = Number(bv);
    const result = !Number.isNaN(an) && !Number.isNaN(bn)
      ? an - bn
      : String(av ?? "").localeCompare(String(bv ?? ""), "zh-CN", { numeric: true, sensitivity: "base" });
    return sort.direction === "asc" ? result : -result;
  });
}

function DataTable({
  rows,
  columns,
  empty = "暂无数据",
  onRowClick,
  defaultSort,
}: {
  rows?: AnyRecord[];
  columns: Array<[string, string]>;
  empty?: string;
  onRowClick?: (row: AnyRecord) => void;
  defaultSort?: SortState;
}) {
  const [sort, setSort] = useState<SortState>(defaultSort || { key: columns[0]?.[0] || "", direction: "asc" });
  const sorted = useMemo(() => sort.key ? sortRows(rows || [], sort) : rows || [], [rows, sort]);
  if (!rows || rows.length === 0) return <div className="empty-state"><strong>{empty}</strong><span>调整筛选条件或新增业务单据后会显示在这里。</span></div>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map(([key, label]) => (
            <th key={key}>
              <button className={`sort-button ${sort.key === key ? "active" : ""}`} type="button" onClick={() => setSort({ key, direction: sort.key === key && sort.direction === "asc" ? "desc" : "asc" })}>
                {label}<span>{sort.key === key ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}</span>
              </button>
            </th>
          ))}</tr>
        </thead>
        <tbody>
          {sorted.map((row, index) => (
            <tr key={String(row.id || row.machine_id || row.repair_order_id || row.unit_id || index)} onClick={() => onRowClick?.(row)} className={onRowClick ? "clickable" : ""}>
              {columns.map(([key]) => {
                const cell = displayValue(row, key);
                const isStatus = ["status", "current_status", "payment_status", "direction", "result", "priority"].includes(key);
                return <td key={key}>{isStatus ? <span className={`badge ${badgeClass(cell)}`}>{cell}</span> : cell}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Panel({ title, note, action, children }: { title: string; note?: string; action?: ReactNode; children: ReactNode }) {
  return <section className="panel"><div className="panel-header"><div><h2>{title}</h2>{note && <p>{note}</p>}</div>{action}</div>{children}</section>;
}

function QueryState({ loading, error }: { loading: boolean; error: unknown }) {
  if (loading) return <div className="empty-state"><strong>正在加载</strong><span>正在读取业务数据。</span></div>;
  if (error) return <div className="empty-state error"><strong>加载失败</strong><span>{error instanceof Error ? error.message : "未知错误"}</span></div>;
  return null;
}

function App() {
  const [user, setUser] = useState(getStoredUser());
  const [view, setView] = useState<ViewKey>("dashboard");
  const [selectedRepairOrderId, setSelectedRepairOrderId] = useState<number | string | null>(null);
  const [detailReturnView, setDetailReturnView] = useState<ViewKey>("repairPool");
  const [orderMode, setOrderMode] = useState<OrderMode>("view");
  const [toast, setToast] = useState<Toast>(null);
  const [modal, setModal] = useState<ReactNode | null>(null);
  const queryClient = useQueryClient();
  const current = viewMeta[view];
  const profile = useQuery({ queryKey: ["me", user], queryFn: () => api<AnyRecord>("/api/me"), enabled: Boolean(user) });

  function notify(message: string, error = false) {
    setToast({ message, error });
    window.setTimeout(() => setToast(null), 3200);
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
          <div className="top-search"><Search size={22} /><input placeholder="快捷搜索工单、机型或零件..." /></div>
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
      {toast && <div className={`toast ${toast.error ? "error" : ""}`}>{toast.message}</div>}
      {modal && <div className="modal"><div className="modal-backdrop" onClick={() => setModal(null)} /><section className="modal-panel">{modal}<div className="modal-footer"><button type="button" className="ghost-button" onClick={() => setModal(null)}>关闭</button></div></section></div>}
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
        <label><span>账号</span><input name="username" defaultValue="admin" autoComplete="username" /></label>
        <label><span>密码</span><input name="password" type="password" defaultValue="admin" autoComplete="current-password" /></label>
        <button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "登录中..." : "登录"}</button>
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
  if (view === "audit") return <AuditPage />;
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
    { order_no: "#MC-20231024-01", model: "iPhone 15 Pro Max (原装屏更换)", status: "维修中", priority: "紧急" },
    { order_no: "#MC-20231024-05", model: "MacBook Air M2 (进水清洗)", status: "待分配", priority: "普通" },
    { order_no: "#MC-20231023-12", model: "Huawei Mate 60 Pro (后盖维修)", status: "维修中", priority: "延期" },
    { order_no: "#MC-20231024-09", model: "iPad Pro 12.9 (电池更换)", status: "待备料", priority: "普通" },
  ];
  const data = rows.length ? rows : fallback;
  return (
    <table className="home-table">
      <thead><tr><th>工单编号</th><th>维修机型</th><th>状态</th><th>紧急程度</th><th>操作</th></tr></thead>
      <tbody>{data.map((row, index) => (
        <tr key={String(row.repair_order_id || row.order_no || index)}>
          <td>{String(row.order_no || row.machine_no || "-")}</td>
          <td>{String(row.model || row.fault_description || "-")}</td>
          <td><span className={`badge ${badgeClass(row.status)}`}>{String(row.status || "待处理")}</span></td>
          <td><span className={`priority ${String(row.priority || "").includes("紧急") ? "danger-text" : String(row.priority || "").includes("延期") ? "muted-text" : "warning-text"}`}>{String(row.priority || "普通")}</span></td>
          <td><button type="button" className="link-button" onClick={() => onOpen(row)}>{index === 1 ? "处理" : index === 3 ? "备料" : "详情"}</button></td>
        </tr>
      ))}</tbody>
    </table>
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
  const visibleRows = rows.slice(0, 15);

  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;

  return (
    <div className="repair-pool-page">
      <header className="pool-topbar">
        <div className="pool-global-search"><Search size={23} /><input placeholder="全局搜索 (订单号, 配件, IMEI)..." /></div>
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
            <div className="pool-search-field"><Search size={20} /><input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="搜索订单号、IMEI 或客户手机..." /></div>
            <label className="pool-select"><select value={status} onChange={event => setStatus(event.target.value)}><option>全部状态</option><option>维修中</option><option>待支付</option><option>已完结</option><option>已取消</option></select><ChevronDown size={18} /></label>
            <button type="button" className="pool-ghost-button" onClick={() => notify("高级筛选已按设计预留，当前可用搜索和状态筛选。")}><Filter size={20} />高级筛选</button>
          </div>
          <div className="pool-filter-right">
            <button type="button" className="pool-ghost-button" onClick={() => notify("导出数据入口已预留。")}><Download size={20} />导出数据</button>
            <button type="button" className="pool-primary-button" onClick={() => openNewOrder?.()}><Plus size={22} />新建工单</button>
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
            <span>显示第 <b>{visibleRows.length ? 1 : 0} - {visibleRows.length}</b> 条，共 <b>{rows.length || orders.length || 0}</b> 条工单</span>
            <div>
              <button type="button" disabled><ChevronLeft size={22} /></button>
              <button type="button" className="active">1</button>
              <button type="button">2</button>
              <button type="button">3</button>
              <em>...</em>
              <button type="button">321</button>
              <button type="button"><ChevronRight size={22} /></button>
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
  const phone = String(row.phone || row.customer_phone || "13800000000");
  const imei = String(row.imei || row.serial || row.machine_no || "");
  return (
    <tr>
      <td><button type="button" className="pool-order-link" onClick={() => onOpen(row, "view")}>{String(row.order_no || row.repair_order_id || "-")}</button></td>
      <td><div className="pool-device-cell"><b>{String(row.model || "待补机型")}</b><span>IMEI: {maskCode(imei)}</span></div></td>
      <td><div className="pool-customer-cell"><b>{String(row.customer_name || "未关联客户")}</b><span>{maskPhone(phone)}</span></div></td>
      <td><span className={`pool-status ${statusClass(status)}`}>{status}</span></td>
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

function statusClass(status: string) {
  if (status === "已完结") return "done";
  if (status === "待支付") return "pay";
  if (status === "已取消") return "cancel";
  return "repairing";
}

function maskCode(value: string) {
  if (!value) return "356821******821";
  if (value.length <= 8) return value;
  return `${value.slice(0, 6)}******${value.slice(-3)}`;
}

function maskPhone(value: string) {
  const digits = value.replace(/\D/g, "");
  if (digits.length < 7) return value || "138****8888";
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
  return <Panel title="维修订单池" note="按订单号、机型、客户、工程师快速定位维修工单。" action={<button type="button" onClick={() => query.refetch()}><RefreshCw size={16} />刷新</button>}><div className="toolbar filters"><input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="搜索订单号、IMEI、客户手机..." /></div><DataTable rows={rows} onRowClick={openDetail} defaultSort={{ key: "updated_at", direction: "desc" }} columns={[["order_no", "订单编号"], ["model", "设备信息"], ["customer_name", "客户"], ["status", "状态"], ["assigned_to", "技术员"], ["updated_at", "最后更新"], ["quoted_amount", "预估金额"]]} /></Panel>;
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
  const query = useQuery({
    queryKey: ["repair-workbench-detail", orderId],
    queryFn: () => api<AnyRecord>(`/api/repair-workbench/${orderId}`),
    enabled: Boolean(orderId) && mode !== "new",
  });
  const data = query.data || {};
  const order = ((data.order || {}) as AnyRecord);
  const timelineQuery = useQuery({
    queryKey: ["machine-timeline", order.machine_id],
    queryFn: () => api<AnyRecord>(`/api/machines/${order.machine_id}/timeline`),
    enabled: Boolean(order.machine_id) && mode !== "new",
  });
  const events = ((data.events as AnyRecord[] | undefined) || []).slice(0, 8);
  const incomeItems = ((data.income_items as AnyRecord[] | undefined) || []);
  const costItems = ((data.cost_items as AnyRecord[] | undefined) || []);
  const payments = ((data.payments as AnyRecord[] | undefined) || []);
  const display = mode === "new" ? form : { ...order, ...form };
  const createdAt = String(order.created_at || order.opened_at || "保存后生成");
  const owner = String(display.assigned_to || order.assigned_to || "未指派");
  const statusText = mode === "new" ? "待创建" : mode === "cancel" ? "取消确认" : normalizeRepairStatus(order.status);
  const model = String(display.model || order.model || "iPhone 13 Pro");
  const colorCapacity = [display.color || order.color || "远峰蓝", display.memory || order.memory || order.capacity || "128GB"].filter(Boolean).join(" / ");
  const imei = String(display.imei || order.imei || order.serial || "869123456789012");
  const customer = String(display.customer_name || order.customer_name || "张先生");
  const phone = String(display.phone || order.phone || order.customer_phone || "138-0000-0000");
  const profileDisplay = profileEditing ? { ...display, ...profileForm } : display;
  const profileModel = String(profileDisplay.model || "iPhone 13 Pro");
  const profileImei = String(profileDisplay.imei || profileDisplay.serial || "869123456789012");
  const profileColor = String(profileDisplay.color || "远峰蓝");
  const profileMemory = String(profileDisplay.memory || profileDisplay.capacity || "128GB");
  const profileCustomer = String(profileDisplay.customer_name || "张先生");
  const profilePhone = String(profileDisplay.phone || profileDisplay.customer_phone || "138-0000-0000");
  const profileCustomerType = String(profileDisplay.customer_type || order.customer_type || "零售客户");
  const quoted = Number(display.quoted_amount || order.quoted_amount || incomeItems.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  const cost = Number(order.cost_amount || costItems.reduce((sum, row) => sum + Number(row.total_cost || row.unit_cost || 0), 0));
  const paid = Number(order.paid_amount || payments.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  const detailRows = costItems.length ? costItems : [
    { item_name: "屏幕总成更换", sku: "IP13P-SCR-OLED", unit_cost: cost || 680, amount: quoted || 980, qty: 1 },
    { item_name: "维修服务费", sku: "SERVICE-PREMIUM", unit_cost: 0, amount: Math.max((quoted || 1280) - (cost || 680), 0), qty: 1 },
  ];
  const inspections = ["屏幕显示", "触摸功能", "摄像头", "电池健康", "生物识别", "无线网络", "蜂窝网络", "音频模块", "指南针", "扬声器", "听筒", "充电"];
  const canAddRepairItem = mode !== "new" && canModifyRepairItems(statusText);
  const historyOrders = (((timelineQuery.data?.repair_orders as AnyRecord[] | undefined) || []))
    .filter(row => String(row.repair_order_id) !== String(order.repair_order_id || orderId))
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));

  const createMutation = useMutation({
    mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/repair-orders", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: data => {
      const next = ((data.order || data) as AnyRecord);
      const id = next.repair_order_id || data.repair_order_id;
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

  function setField(key: string, value: unknown) {
    setForm(prev => ({ ...prev, [key]: value }));
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
    if (mode !== "new" && mode !== "edit") return;
    const setter = kind === "pre" ? setPreInspectionState : setPostInspectionState;
    setter(prev => ({ ...prev, [item]: !prev[item] }));
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
        <div className="order-detail-search"><Search size={22} /><input placeholder="搜索工单、IMEI、客户..." /></div>
        <div className="order-detail-icons"><button type="button" className="icon-button"><Bell size={23} /><span /></button><button type="button" className="icon-button"><UserRound size={23} /></button></div>
      </header>

      <section className="order-hero">
        <div><div className="order-heading-line"><h2>{mode === "new" ? "新建维修工单" : `工单: ${String(order.order_no || order.repair_order_id || orderId)}`}</h2><span className="order-status-pill">{statusText}</span></div><p>创建于 {createdAt} | 负责人: {owner}</p></div>
        <div className="order-hero-actions">
          {mode === "view" && canModifyOrderStatus(statusText) && <button type="button" onClick={() => onModeChange("edit")}><Edit3 size={20} />编辑</button>}
          {mode === "view" && canModifyOrderStatus(statusText) && <button type="button" onClick={() => onModeChange("cancel")}><CirclePlus size={20} />取消订单</button>}
          {mode === "edit" && <button type="button" onClick={() => editMutation.mutate(form)} disabled={editMutation.isPending}><Edit3 size={20} />保存修改</button>}
          {mode === "new" && <button type="button" onClick={submitNew} disabled={createMutation.isPending}><Plus size={20} />创建工单</button>}
          {mode === "cancel" && <button type="button" className="danger-action" onClick={submitCancel} disabled={cancelMutation.isPending}>确认取消</button>}
          {mode !== "view" && <button type="button" onClick={() => { setForm({}); mode === "new" ? onBack() : onModeChange("view"); }}>放弃</button>}
        </div>
      </section>

      <div className="order-detail-layout">
        <div className="order-main-column">
          <section className="order-card device-card">
            <div className="repair-card-head">
              <h3><Smartphone size={24} />设备详细信息</h3>
              <div className="inline-actions">
                {profileEditing ? (
                  <>
                    <button type="button" className="mini-add-button" onClick={submitProfile} disabled={profileMutation.isPending}>保存</button>
                    <button type="button" className="ghost-mini-button" onClick={() => { setProfileEditing(false); setProfileForm({}); }}>取消</button>
                  </>
                ) : (
                  <button type="button" className="ghost-mini-button" onClick={beginProfileEdit} disabled={!order.machine_id && mode !== "new"}><Edit3 size={15} />编辑</button>
                )}
              </div>
            </div>
            <div className="order-info-grid">
              <OrderEditableLine label="手机型号" value={profileModel} editable={mode === "new" || profileEditing} onChange={v => profileEditing ? setProfileField("model", v) : setField("model", v)} />
              <OrderEditableLine label="IMEI / 序列号" value={profileImei} editable={mode === "new" || profileEditing} onChange={v => profileEditing ? setProfileField("imei", v) : setField("imei", v)} />
              <OrderEditableLine label="颜色" value={profileColor} editable={mode === "new" || profileEditing} onChange={v => profileEditing ? setProfileField("color", v) : setField("color", v)} />
              <OrderEditableLine label="容量" value={profileMemory} editable={mode === "new" || profileEditing} onChange={v => profileEditing ? setProfileField("memory", v) : setField("memory", v)} />
              <OrderEditableLine label="机况" value={String(profileDisplay.condition || "待补")} editable={profileEditing} onChange={v => setProfileField("condition", v)} />
            </div>
          </section>
          <section className="order-card customer-card">
            <div className="order-info-grid compact">
              <OrderEditableLine label="客户姓名" value={profileCustomer} editable={mode === "new" || profileEditing} tag={profileCustomerType} onChange={v => profileEditing ? setProfileField("customer_name", v) : setField("customer_name", v)} />
              <OrderEditableLine label="联系方式" value={profilePhone} editable={mode === "new" || profileEditing} highlight onChange={v => profileEditing ? setProfileField("phone", v) : setField("phone", v)} />
              <OrderEditableLine label="客户类型" value={profileCustomerType} editable={profileEditing} onChange={v => setProfileField("customer_type", v)} />
            </div>
          </section>

          <InspectionCard title="维修前检测 (Pre-Repair)" inspections={inspections} note={String(order.diagnosis || "其他检测备注...")} mode={mode} state={preInspectionState} onToggle={item => toggleInspection("pre", item)} />

          <section className="order-card">
            <div className="repair-card-head">
              <h3><FileText size={24} />故障与维修详情</h3>
              <button type="button" className="mini-add-button" onClick={() => canAddRepairItem ? setShowItemForm(true) : notify("当前订单状态不可添加维修故障", true)} disabled={!canAddRepairItem}><Plus size={16} />添加故障</button>
            </div>
            <p className="order-muted">{mode === "new" ? "保存后生成维修明细，可在编辑态继续添加配件和收费项目。" : String(order.fault_description || "客户反馈设备异常，需要检测并维修。")}</p>
            {showItemForm && <div className="inline-item-editor repair-item-editor"><OrderField label="故障名称" value={itemForm.item_name} editable onChange={v => setItemField("item_name", v)} /><OrderField label="数量" value={itemForm.quantity || 1} editable type="number" onChange={v => setItemField("quantity", v)} /><OrderField label="配件成本" value={itemForm.cost_amount} editable type="number" onChange={v => setItemField("cost_amount", v)} /><OrderField label="工时/服务费" value={itemForm.charge_amount} editable type="number" onChange={v => setItemField("charge_amount", v)} /><OrderField label="备注" value={itemForm.remark} editable area onChange={v => setItemField("remark", v)} /><div className="inline-editor-actions"><button type="button" className="mini-add-button" onClick={submitRepairItem} disabled={addItemMutation.isPending}>保存故障</button><button type="button" className="ghost-mini-button" onClick={() => { setShowItemForm(false); setItemForm({ quantity: 1 }); }}>取消</button></div></div>}
            <div className="repair-lines"><table><thead><tr><th>故障名称</th><th>更换配件/SKU</th><th>配件单价</th><th>工时/服务费</th><th>小计</th><th className="align-right">操作</th></tr></thead><tbody>{detailRows.map((row, index) => { const unitCost = Number(row.total_cost || row.unit_cost || 0); const amount = Number(row.amount || row.charge_amount || row.price || 0); return <tr key={String(row.cost_item_id || row.item_name || index)}><td>{String(row.item_name || row.material_name || "维修项目")}</td><td>{String(row.sku || row.material_code || "-")}</td><td>{poolMoney(unitCost)}</td><td>{poolMoney(Math.max(amount - unitCost, 0))}</td><td><b>{poolMoney(amount || unitCost)}</b></td><td className="align-right">{mode === "edit" ? <button type="button" className="table-link danger">删除</button> : "-"}</td></tr>; })}</tbody></table></div>
            <div className="order-fee-summary stacked-fee-summary"><span>费用总计 <b>{poolMoney(quoted || 1430)}</b></span><span>折扣优惠 <b className="danger-text">- {poolMoney(30)}</b></span><span>应收总额 <b>{poolMoney(Math.max((quoted || 1430) - 30, 0))}</b></span>{mode === "edit" && <OrderField label="修改报价" value={form.quoted_amount ?? order.quoted_amount} editable type="number" onChange={v => setField("quoted_amount", v)} />}</div>
          </section>

          <InspectionCard title="维修后检测 (Post-Repair)" inspections={inspections.slice(0, 8)} note="质检备注..." compact={false} mode={mode} state={postInspectionState} onToggle={item => toggleInspection("post", item)} />
          <section className="order-card"><h3><ClipboardList size={24} />维修历史</h3><div className="history-list">{historyOrders.length ? historyOrders.slice(0, 5).map(row => <button type="button" className="history-order-row" key={String(row.repair_order_id)} onClick={() => { onCreated(row.repair_order_id as number | string); onModeChange("view"); }}><b>{String(row.order_no || `RO-${row.repair_order_id}`)}</b><span>{String(row.status || "待确认")} · {String(row.fault_description || "无故障描述")}</span><em>{poolMoney(row.quoted_amount || row.paid_amount || 0)} · {String(row.created_at || "")}</em></button>) : <div className="history-empty">无</div>}</div></section>
        </div>

        <aside className="order-side-column">
          <section className="order-card"><h3>订单状态</h3><div className="detail-timeline">{buildStitchTimeline(mode, statusText, createdAt, owner).map(item => <div className={`timeline-step ${item.done ? "done" : ""} ${item.active ? "active" : ""}`} key={item.title}><span>{item.done ? <CheckCircle2 size={18} /> : item.active ? <Users size={18} /> : <Flag size={18} />}</span><div><b>{item.title}</b><p>{item.note}</p></div></div>)}</div></section>
          {mode === "cancel" && <section className="order-card cancel-warning-card"><h3>取消确认</h3><p>取消订单会将业务状态改为已作废，不会删除数据库记录。若订单已有未闭环领料，后端会提示先退料或报损。</p><OrderField label="取消原因" value={form.cancel_reason} editable area onChange={v => setField("cancel_reason", v)} /></section>}
          {mode === "edit" && <section className="order-card"><h3>订单转派</h3><OrderField label="负责人账号" value={form.assigned_to ?? order.assigned_to} editable onChange={v => setField("assigned_to", v)} /><OrderField label="修改备注" value={form.remark} editable area onChange={v => setField("remark", v)} /></section>}
          <section className="order-card notes-card"><div className="side-title-row"><h3>备注信息</h3><CirclePlus size={22} /></div><div className="note-box warning"><b>内部备注</b><p>{String(order.remark || "客户要求尽量保留原厂原色原彩，维修后请务必同步写入数据。")}</p></div><div className="note-box muted"><b>交付说明</b><p>告知客户外壳磕碰处无法复原，仅保证屏幕功能完好。</p></div></section>
          <section className="order-card log-card"><h3>系统操作日志</h3>{(events.length ? events : [{ title: "价格变更通知", detail: "财务组已确认优惠申请", created_at: "10-27 16:45" }, { title: "订单负责人变更", detail: "由李四转交给张工", created_at: "10-27 16:15" }, { title: "备件申领完成", detail: "原装拆机屏幕已出库", created_at: "10-27 15:50" }]).slice(0, 5).map((event, index) => <div className="log-item" key={String(event.event_id || event.created_at || index)}><b>{String(event.title || "系统操作")}</b><p>{String(event.detail || "工单信息已更新")}</p><span>{String(event.created_at || "")}</span></div>)}</section>
        </aside>
      </div>
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
        <div className="order-detail-search"><Search size={22} /><input placeholder="搜索工单、IMEI、客户..." /></div>
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

function OrderField({ label, value, editable, onChange, area, type = "text" }: { label: string; value: unknown; editable?: boolean; onChange?: (value: string) => void; area?: boolean; type?: string }) {
  return <label className={`order-flow-field ${area ? "wide" : ""}`}><span>{label}</span>{editable ? (area ? <textarea value={String(value || "")} onChange={event => onChange?.(event.target.value)} /> : <input type={type} value={String(value || "")} onChange={event => onChange?.(event.target.value)} />) : <strong>{String(value || "待补")}</strong>}</label>;
}

function OrderEditableLine({ label, value, editable, onChange, pill, tag, highlight }: { label: string; value: unknown; editable?: boolean; onChange?: (value: string) => void; pill?: boolean; tag?: string; highlight?: boolean }) {
  return <div className={`info-line order-editable-line ${pill ? "pill-value" : ""}`}><span>{label}</span>{editable ? <input value={String(value || "")} onChange={event => onChange?.(event.target.value)} /> : <strong className={highlight ? "highlight" : ""}>{String(value || "待补")}{tag && <em>{tag}</em>}</strong>}</div>;
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
  const payments = ((data.payments as AnyRecord[] | undefined) || []);
  const createdAt = String(order.created_at || order.opened_at || "2023-10-27 14:30");
  const owner = String(order.assigned_to || order.engineer_user || "张工程师");
  const model = String(order.model || "iPhone 13 Pro");
  const colorCapacity = [order.color || "远峰蓝", order.memory || order.capacity || "128GB"].filter(Boolean).join(" / ");
  const imei = String(order.imei || order.serial || "869123456789012");
  const customer = String(order.customer_name || "张先生");
  const phone = String(order.phone || order.customer_phone || "138-0000-0000");
  const quoted = Number(order.quoted_amount || incomeItems.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  const cost = Number(order.cost_amount || costItems.reduce((sum, row) => sum + Number(row.total_cost || row.unit_cost || 0), 0));
  const paid = Number(order.paid_amount || payments.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  const detailRows = costItems.length ? costItems : [
    { item_name: "屏幕总成更换", sku: "IP13P-SCR-OLED", unit_cost: cost || 680, amount: quoted || 980, qty: 1 },
    { item_name: "维修服务费", sku: "SERVICE-PREMIUM", unit_cost: 0, amount: Math.max((quoted || 1280) - (cost || 680), 0), qty: 1 },
  ];
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
        <div className="order-detail-search"><Search size={22} /><input placeholder="搜索工单、IMEI、客户..." /></div>
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
              <table>
                <thead><tr><th>维修项目</th><th>SKU</th><th>物料成本</th><th>服务金额</th><th>小计</th></tr></thead>
                <tbody>
                  {detailRows.map((row, index) => {
                    const unitCost = Number(row.total_cost || row.unit_cost || 0);
                    const amount = Number(row.amount || row.charge_amount || row.price || 0);
                    return <tr key={String(row.cost_item_id || row.item_name || index)}><td>{String(row.item_name || row.material_name || "维修项目")}</td><td>{String(row.sku || row.material_code || "-")}</td><td>{formatMoney(unitCost)}</td><td>{formatMoney(Math.max(amount - unitCost, 0))}</td><td>{formatMoney(amount || unitCost)}</td></tr>;
                  })}
                </tbody>
              </table>
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
  return <div className={`info-line ${pill ? "pill-value" : ""}`}><span>{label}</span><strong className={highlight ? "highlight" : ""}>{String(value || "待补")}{tag && <em>{tag}</em>}</strong></div>;
}

function InspectionCard({ title, inspections, note, compact, mode = "view", state = {}, onToggle }: { title: string; inspections: string[]; note: string; compact?: boolean; mode?: OrderMode; state?: Record<string, boolean>; onToggle?: (item: string) => void }) {
  const editable = mode === "new" || mode === "edit";
  const visibleInspections = editable ? inspections : inspections.filter(item => state[item]);
  return (
    <section className={`order-card inspection-card ${compact ? "compact" : ""}`}>
      <div className="inspection-head"><h3><span />{title}</h3></div>
      {visibleInspections.length ? <div className="inspection-grid">{visibleInspections.map(item => <button type="button" className={state[item] ? "abnormal" : ""} key={item} disabled={!editable} onClick={() => onToggle?.(item)}><b>{item}</b><span>{state[item] ? "异常" : "正常"}</span></button>)}</div> : <div className="inspection-empty">无异常功能</div>}
      <input className="inspection-note" value={note} readOnly />
      {!compact && <div className="photo-strip"><div className="photo-thumb" /><button type="button" className="upload-tile"><Camera size={24} />上传</button></div>}
    </section>
  );
}

function InfoBlock({ label, text }: { label: string; text: unknown }) {
  return <div className="field-block"><span>{label}</span><strong>{String(text || "待补")}</strong></div>;
}

function DetailSection({ title, rows, columns }: { title: string; rows?: AnyRecord[]; columns: Array<[string, string]> }) {
  return <section className="detail-section"><h3>{title}</h3><DataTable rows={rows || []} columns={columns} /></section>;
}

function RecyclePool({ openModal }: { openModal: (node: ReactNode | null) => void }) {
  const [keyword, setKeyword] = useState("");
  const query = useQuery({ queryKey: ["machines", keyword], queryFn: () => api<AnyRecord[]>(`/api/machines?q=${encodeURIComponent(keyword)}`) });
  const rows = (query.data || []).filter(row => row.source_type === "回收");
  async function open(row: AnyRecord) {
    const timeline = await api<AnyRecord>(`/api/machines/${row.machine_id}/timeline`);
    openModal(<MachineTimeline timeline={timeline} />);
  }
  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;
  return <Panel title="回收订单池"><div className="toolbar filters"><input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="机器编号、IMEI、机型、客户" /></div><DataTable rows={rows} onRowClick={open} columns={[["machine_no", "机器编号"], ["imei", "IMEI"], ["model", "机型"], ["customer_name", "客户"], ["current_status", "当前状态"], ["updated_at", "更新时间"]]} /></Panel>;
}

function MachineTimeline({ timeline }: { timeline: AnyRecord }) {
  const machine = timeline.machine as AnyRecord;
  const customer = (timeline.customer || {}) as AnyRecord;
  return <><header className="modal-header"><div><h2>{String(machine.machine_no)} / {String(machine.model)}</h2><p>机器 ID {String(machine.machine_id)} · {String(machine.current_status)}</p></div></header><div className="modal-content"><div className="repair-detail-grid"><InfoBlock label="IMEI" text={machine.imei} /><InfoBlock label="序列号" text={machine.serial} /><InfoBlock label="客户" text={customer.name || machine.customer_name} /><InfoBlock label="电话" text={customer.phone} /></div><DetailSection title="维修记录" rows={timeline.repair_orders as AnyRecord[]} columns={[["repair_order_id", "维修单"], ["status", "状态"], ["assigned_to", "工程师"], ["fault_description", "故障"], ["quoted_amount", "报价"]]} /><DetailSection title="回收记录" rows={timeline.recycle_orders as AnyRecord[]} columns={[["recycle_order_id", "回收单"], ["status", "状态"], ["inspection_result", "验机结论"], ["quoted_amount", "报价"], ["paid_amount", "已付"]]} /></div></>;
}

function SimpleForm({ title, fields, onSubmit }: { title: string; fields: ReactNode; onSubmit: (payload: AnyRecord, form: HTMLFormElement) => void }) {
  return <form className="panel form-grid compact" onSubmit={(event) => { event.preventDefault(); onSubmit(formPayload(event.currentTarget), event.currentTarget); }}><div className="panel-header"><div><h2>{title}</h2></div></div>{fields}<button type="submit"><Plus size={16} />保存</button></form>;
}

function RepairOpenPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({ mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/repair-orders", { method: "POST", body: JSON.stringify(payload) }), onSuccess: data => { notify(`维修单已创建：${String(data.repair_order_id)}`); queryClient.invalidateQueries({ queryKey: ["repair-workbench"] }); }, onError: e => notify(e instanceof Error ? e.message : "创建失败", true) });
  return <SimpleForm title="维修到店开单" onSubmit={(data, form) => { mutation.mutate({ machine_id: data.machine_id || null, machine: data.machine_id ? null : machinePayload(data), customer: customerPayload(data), fault_description: data.fault_description || "" }); form.reset(); }} fields={<><input name="customer_name" placeholder="客户姓名" /><input name="phone" placeholder="联系电话" /><input name="imei" placeholder="IMEI" /><input name="serial" placeholder="序列号" /><select name="model" required><option value="">选择机型 *</option>{modelOptions.map(x => <option key={x}>{x}</option>)}</select><input name="memory" placeholder="内存" /><input name="color" placeholder="颜色" /><input name="condition" placeholder="机况" /><textarea name="fault_description" placeholder="故障描述" /></>} />;
}

function RecycleOpenPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const mutation = useMutation({ mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/recycle-orders", { method: "POST", body: JSON.stringify(payload) }), onSuccess: data => notify(`回收单已创建：${String(data.recycle_order_id)}`), onError: e => notify(e instanceof Error ? e.message : "创建失败", true) });
  return <SimpleForm title="回收到店开单" onSubmit={(data, form) => { mutation.mutate({ machine_id: data.machine_id || null, machine: data.machine_id ? null : machinePayload(data), customer: customerPayload(data), inspection_note: data.inspection_note || "" }); form.reset(); }} fields={<><input name="customer_name" placeholder="客户姓名" /><input name="phone" placeholder="联系电话" /><input name="imei" placeholder="IMEI" /><input name="serial" placeholder="序列号" /><select name="model" required><option value="">选择机型 *</option>{modelOptions.map(x => <option key={x}>{x}</option>)}</select><input name="memory" placeholder="内存" /><input name="color" placeholder="颜色" /><input name="condition" placeholder="机况" /><textarea name="inspection_note" placeholder="验机记录" /></>} />;
}

function machinePayload(data: AnyRecord) {
  return { imei: data.imei || "", serial: data.serial || "", model: data.model, memory: data.memory || "", color: data.color || "", condition: data.condition || "" };
}

function customerPayload(data: AnyRecord) {
  if (!data.customer_name) return null;
  return { name: data.customer_name, phone: data.phone || "" };
}

function WarehousePage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["warehouse"], queryFn: () => api<AnyRecord>("/api/warehouse") });
  const post = useMutation({ mutationFn: ({ path, payload }: { path: string; payload: AnyRecord }) => api(path, { method: "POST", body: JSON.stringify(payload) }), onSuccess: () => { notify("仓库单据已保存"); queryClient.invalidateQueries({ queryKey: ["warehouse"] }); }, onError: e => notify(e instanceof Error ? e.message : "保存失败", true) });
  const data = query.data || {};
  if (query.isLoading || query.error) return <QueryState loading={query.isLoading} error={query.error} />;
  return <div className="stack"><Panel title="库存管理" note="物料编码、批次、单件码、申领发放、退料退货和库存流水。" action={<button type="button" onClick={() => query.refetch()}><RefreshCw size={16} />刷新</button>}><DataTable rows={data.materials as AnyRecord[]} columns={[["material_id", "ID"], ["material_code", "物料代码"], ["sku", "SKU"], ["name", "物料"], ["category_code", "类别"], ["compatible_range", "适配"], ["current_qty", "可用"], ["min_qty", "低库存"]]} /></Panel><div className="dashboard-grid"><SimpleForm title="采购/临采入库" onSubmit={(payload, form) => { const kind = String(payload.batch_kind || "purchase"); delete payload.batch_kind; post.mutate({ path: `/api/material-batches/${kind}`, payload }); form.reset(); }} fields={<><select name="batch_kind"><option value="purchase">采购入库</option><option value="ad-hoc">临采入库</option></select><input name="material_id" type="number" placeholder="物料 ID *" required /><input name="supplier" placeholder="供应商" defaultValue="待确认" /><input name="qty" type="number" min="1" placeholder="数量 *" required /><input name="unit_cost" type="number" step="0.01" placeholder="单价" /><textarea name="remark" placeholder="备注" /></>} /><SimpleForm title="申领发放" onSubmit={(payload, form) => { post.mutate({ path: "/api/material-requests", payload: { repair_order_id: payload.repair_order_id || null, engineer_user: payload.engineer_user || "", items: [{ material_id: payload.material_id, repair_sku_id: payload.repair_sku_id, qty: payload.qty || 1, remark: payload.remark || "" }], remark: payload.remark || "" } }); form.reset(); }} fields={<><input name="repair_order_id" type="number" placeholder="维修工单 ID" /><input name="engineer_user" placeholder="工程师账号" /><input name="material_id" type="number" placeholder="物料 ID *" required /><input name="qty" type="number" min="1" defaultValue="1" placeholder="数量" /><textarea name="remark" placeholder="申领备注" /></>} /></div><div className="dashboard-grid"><Panel title="申领单"><DataTable rows={data.requests as AnyRecord[]} columns={[["request_id", "ID"], ["request_no", "申领单"], ["status", "状态"], ["engineer_user", "工程师"], ["repair_order_id", "工单"], ["created_at", "时间"], ["remark", "备注"]]} /></Panel><Panel title="库存流水"><DataTable rows={data.movements as AnyRecord[]} columns={[["happened_at", "时间"], ["movement_type", "类型"], ["direction", "方向"], ["material_code", "物料代码"], ["name", "物料"], ["qty", "数量"], ["actor", "操作人"]]} /></Panel></div></div>;
}

function InventoryPage() {
  const materials = useQuery({ queryKey: ["materials"], queryFn: () => api<AnyRecord>("/api/materials") });
  const inventory = useQuery({ queryKey: ["inventory"], queryFn: () => api<AnyRecord[]>("/api/inventory") });
  if (materials.isLoading || inventory.isLoading || materials.error || inventory.error) return <QueryState loading={materials.isLoading || inventory.isLoading} error={materials.error || inventory.error} />;
  return <div className="stack"><Panel title="维修物料库存"><DataTable rows={materials.data?.materials as AnyRecord[]} columns={[["sku", "SKU"], ["name", "物料"], ["compatible_range", "适配范围"], ["current_qty", "库存"], ["avg_cost", "均价"], ["status", "状态"]]} /></Panel><Panel title="回收机器库存"><DataTable rows={inventory.data} columns={[["inventory_item_id", "库存ID"], ["machine_id", "机器ID"], ["imei", "IMEI"], ["model", "机型"], ["status", "库存状态"], ["cost_amount", "成本"], ["sale_price", "销售定价"]]} /></Panel></div>;
}

function CustomersPage() {
  const [q, setQ] = useState("");
  const query = useQuery({ queryKey: ["customers", q], queryFn: () => api<AnyRecord[]>(`/api/customers?q=${encodeURIComponent(q)}`) });
  return <Panel title="客户查询"><div className="toolbar filters"><input value={q} onChange={e => setQ(e.target.value)} placeholder="姓名、电话、店铺、标签" /><button type="button" onClick={() => query.refetch()}><Search size={16} />查询</button></div><QueryState loading={query.isLoading} error={query.error} /><DataTable rows={query.data} columns={[["customer_id", "ID"], ["name", "姓名"], ["phone", "电话"], ["category", "类别"], ["shop_name", "店铺"], ["tags", "标签"]]} empty="没有找到客户" /></Panel>;
}

function PaymentsPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["payments"], queryFn: () => api<AnyRecord[]>("/api/payments") });
  const mutation = useMutation({ mutationFn: (payload: AnyRecord) => api("/api/payments", { method: "POST", body: JSON.stringify(payload) }), onSuccess: () => { notify("流水已登记"); queryClient.invalidateQueries({ queryKey: ["payments"] }); }, onError: e => notify(e instanceof Error ? e.message : "登记失败", true) });
  return <div className="split"><SimpleForm title="登记收支流水" onSubmit={(payload, form) => { mutation.mutate(payload); form.reset(); }} fields={<><select name="source_type"><option value="repair">维修单</option><option value="sale">销售单</option><option value="recycle">回收单</option></select><input name="source_id" type="number" placeholder="单据 ID *" required /><select name="direction"><option>收入</option><option>支出</option></select><input name="amount" type="number" step="0.01" placeholder="金额 *" required /><input name="method" placeholder="方式" /><input name="payer" placeholder="付款方" /><input name="payee" placeholder="收款方" /><textarea name="remark" placeholder="备注" /></>} /><Panel title="流水列表"><QueryState loading={query.isLoading} error={query.error} /><DataTable rows={query.data} columns={[["payment_id", "ID"], ["source_type", "来源"], ["source_id", "单据"], ["direction", "方向"], ["amount", "金额"], ["method", "方式"], ["transaction_no", "流水号"], ["status", "状态"], ["received_by", "收款人"], ["confirmed_by", "确认人"], ["created_at", "时间"]]} /></Panel></div>;
}

function SalesPage({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const mutation = useMutation({ mutationFn: (payload: AnyRecord) => api<AnyRecord>("/api/sales-orders", { method: "POST", body: JSON.stringify(payload) }), onSuccess: data => notify(`销售单已创建：${String(data.sales_order_id)}`), onError: e => notify(e instanceof Error ? e.message : "创建失败", true) });
  return <SimpleForm title="销售开单" onSubmit={(data, form) => { mutation.mutate({ inventory_item_id: data.inventory_item_id, customer: customerPayload(data), sale_price: data.sale_price, salesperson: data.salesperson, remark: data.remark || "" }); form.reset(); }} fields={<><input name="inventory_item_id" type="number" placeholder="库存 ID *" required /><input name="customer_name" placeholder="客户姓名" /><input name="phone" placeholder="联系电话" /><input name="sale_price" type="number" step="0.01" placeholder="销售价格 *" required /><input name="salesperson" placeholder="销售人 *" required /><textarea name="remark" placeholder="备注" /></>} />;
}

function ReportsPage() {
  const query = useQuery({ queryKey: ["machine-reports"], queryFn: () => api<AnyRecord>("/api/machine-reports") });
  const income = ((query.data?.payment_totals as AnyRecord[] | undefined) || []).find(x => x.direction === "收入")?.amount || 0;
  const expense = ((query.data?.payment_totals as AnyRecord[] | undefined) || []).find(x => x.direction === "支出")?.amount || 0;
  return <div className="stack"><QueryState loading={query.isLoading} error={query.error} /><div className="metric-grid"><div className="metric"><span>在售库存</span><strong>{String(query.data?.inventory_count || 0)}</strong></div><div className="metric"><span>库存成本</span><strong>{formatMoney(query.data?.inventory_cost || 0)}</strong></div><div className="metric"><span>收入流水</span><strong>{formatMoney(income)}</strong></div><div className="metric"><span>支出流水</span><strong>{formatMoney(expense)}</strong></div></div><Panel title="库存明细"><DataTable rows={query.data?.inventory as AnyRecord[]} columns={[["inventory_item_id", "库存ID"], ["machine_no", "机器编号"], ["imei", "IMEI"], ["model", "机型"], ["status", "状态"], ["cost_amount", "成本"], ["sale_price", "销售定价"]]} /></Panel></div>;
}

function AuditPage() {
  const query = useQuery({ queryKey: ["audit"], queryFn: () => api<AnyRecord[]>("/api/audit-logs") });
  return <Panel title="系统设置 / 操作日志"><QueryState loading={query.isLoading} error={query.error} /><DataTable rows={query.data} columns={[["time", "时间"], ["username", "用户"], ["role", "角色"], ["action", "动作"], ["target_type", "对象"], ["target_id", "ID"], ["result", "结果"]]} /></Panel>;
}

export default App;
