import { ReactNode } from "react";
import { Input } from "antd";
import { Bell, HelpCircle, LogOut, Mail, Search, UserRound } from "lucide-react";
import { AppModal } from "../feedback/AppModal";

type ViewMeta = {
  label: string;
  subtitle: string;
};

type NavItem<TView extends string> = {
  key: TView;
  label: string;
  icon: ReactNode;
};

type AppShellLayoutProps<TView extends string> = {
  view: TView;
  current: ViewMeta;
  primaryNav: Array<NavItem<TView>>;
  userLabel: string;
  roleLabel: string;
  modal: ReactNode | null;
  children: ReactNode;
  setView: (view: TView) => void;
  notify: (message: string, error?: boolean) => void;
  logout: () => void;
  onCloseModal: () => void;
};

export function AppShellLayout<TView extends string>({
  view,
  current,
  primaryNav,
  userLabel,
  roleLabel,
  modal,
  children,
  setView,
  notify,
  logout,
  onCloseModal,
}: AppShellLayoutProps<TView>) {
  const isOrderDetailShell = view === "orderDetail" || view === "repair";
  const isRepairPoolShell = view === "repairPool";
  const showPageTitle = view !== "dashboard" && view !== "orderDetail" && view !== "repairPool" && view !== "repair";

  return (
    <div className={`app-shell ${isOrderDetailShell ? "order-detail-shell" : ""} ${isRepairPoolShell ? "repair-pool-shell" : ""}`}>
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
          <button type="button" className="plain-nav-button" onClick={() => notify("帮助中心已接入当前业务说明文档，可先查看 README 和 BUSINESS_FLOW。")}><HelpCircle size={20} />帮助中心</button>
          <button type="button" className="plain-nav-button" onClick={logout}><LogOut size={20} />退出登录</button>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="top-search"><Search size={22} /><Input variant="borderless" placeholder="快捷搜索工单、机型或零件..." /></div>
          <div className="top-links">
            <button type="button" onClick={() => setView("warehouse" as TView)}>设备入库</button>
            <button type="button" onClick={() => setView("sales" as TView)}>快速卖机</button>
          </div>
          <div className="top-icons">
            <button type="button" className="icon-button" aria-label="查看待处理提醒" onClick={() => setView("dashboard" as TView)}><Bell size={23} /><span /></button>
            <button type="button" className="icon-button" aria-label="查看工作消息" onClick={() => { setView("dashboard" as TView); notify("工作消息在首页右侧消息区查看。"); }}><Mail size={23} /></button>
          </div>
          <div className="admin-chip">
            <div><strong>{userLabel}</strong><span>{roleLabel}</span></div>
            <div className="avatar-dot"><UserRound size={19} /></div>
          </div>
        </header>
        {showPageTitle && <div className="page-title"><h1>{current.label}</h1><p>{current.subtitle}</p></div>}
        {children}
      </main>
      <AppModal open={Boolean(modal)} onClose={onCloseModal}>{modal}</AppModal>
    </div>
  );
}
