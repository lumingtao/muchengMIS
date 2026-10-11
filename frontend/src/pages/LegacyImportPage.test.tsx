import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { AppShellLayout } from "../components/layout/AppShellLayout";
import { LegacyView, legacyNavItems, legacyViews } from "./legacy/navigation";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { LegacyImportPage, LegacyOrderPanel, LegacyEngineerMappings, LegacyCachePanel, LegacyTaskProgress, displayLegacyValue } from "./LegacyImportPage";

beforeEach(() => { vi.stubGlobal("scrollTo", vi.fn()); });

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function mockApi(role: string, ownership = "following") {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const result = url === "/api/me" ? { role, username: "fixture" }
      : url.includes("/orders/") ? { source_id_raw: "1", ownership, classification: "active", amounts: { 报价: "200", 成本: null }, parts: [], raw: { ID: "1", 机型: "fixture-phone", 锁屏密码: "••••••" }, attachments: [] }
      : url.includes("/records") ? { items: [], total: 0 }
      : url.endsWith("/source") ? null
      : url.endsWith("/summary") ? { historical_amounts: {}, unknown_amount_counts: {}, note: "独立口径" }
      : url.endsWith("/cache/status") ? { initialized: 1, total: 1200, excluded: 0, missing: 0, job: null }
      : [];
    return new Response(JSON.stringify(result), { status: 200 });
  }));
}

function wrapper(children: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("legacy import", () => {
  it('shows persisted page progress and failure reasons', () => {
    const view = render(<LegacyTaskProgress title="拉取任务" kind="fetch" task={{ job_id: 'task1234', status: 'reading', result: { phase: '分页读取并保存到本地', received: 500, total: 1200 } }} />);
    expect(screen.getByRole('status', { name: '拉取任务' })).toHaveTextContent('已保存 500 / 1200 条');
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '41');
    view.rerender(<LegacyTaskProgress title="拉取任务" kind="fetch" task={{ job_id: 'task1234', status: 'failed', error: '连接超时，已保存页面保留', result: { received: 500 } }} />);
    expect(screen.getByRole('alert')).toHaveTextContent('连接超时，已保存页面保留');
  });

  it('counts selected synchronization outcomes and keeps preparation visible', () => {
    const view = render(<LegacyTaskProgress title="同步任务" kind="batch" task={{ batch_id: 'batch123', status: 'queued_execute' }} />);
    expect(screen.getByRole('status')).toHaveTextContent('准备连接复核与备份');
    view.rerender(<LegacyTaskProgress title="同步任务" kind="batch" task={{ batch_id: 'batch123', status: 'executing', progress: { done: 3, total: 10 }, counts: [{ result: 'success', count: 3 }] }} />);
    expect(screen.getByRole('status')).toHaveTextContent('已处理 3 / 10 条');
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '30');
  });
  it("pulls to local staging independently of order synchronization", async () => {
    mockApi('admin');
    render(wrapper(<LegacyCachePanel notify={vi.fn()} enabled busy={false} />));
    const button = await screen.findByRole('button', { name: '增量拉取到本地' });
    await userEvent.setup().click(button);
    expect(fetch).toHaveBeenCalledWith('/api/legacy-import/cache/fetch', expect.objectContaining({ method: 'POST', body: JSON.stringify({ mode: 'incremental' }) }));
    expect(vi.mocked(fetch).mock.calls.some(call => String(call[0]).includes('/execute'))).toBe(false);
  });

  it("shows engineers beyond the first ten and searches their mapping", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const names = Array.from({ length: 14 }, (_, index) => `历史工程师${index + 1}`).concat("李蒙悦");
    render(<LegacyEngineerMappings names={names} mappings={{}} employees={[{ username: "li", name: "李蒙悦" }]} onChange={onChange} />);
    expect(screen.getByRole("cell", { name: /^李蒙悦$/ })).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "搜索老工程师姓名" }), "李蒙悦");
    expect(screen.queryByRole("cell", { name: /^历史工程师1$/ })).not.toBeInTheDocument();
    expect(screen.getByText("共 15 位工程师，未映射 15 位；当前匹配 1 位")).toBeInTheDocument();
    await user.click(screen.getAllByRole("combobox")[0]);
    await user.click(screen.getByText("李蒙悦", { selector: ".ant-select-item-option-content" }));
    expect(onChange).toHaveBeenCalledWith("李蒙悦", "li");
  });

  it("distinguishes zero, empty strings and null", () => {
    expect(displayLegacyValue(0)).toBe("0");
    expect(displayLegacyValue("")).toBe("（空字符串）");
    expect(displayLegacyValue(null)).toBe("NULL");
  });

  it("separates the admin overview from setup and synchronization forms", async () => {
    mockApi("admin");
    render(wrapper(<LegacyImportPage notify={vi.fn()} />));
    expect(await screen.findByText("按步骤整理，再确认导入")).toBeInTheDocument();
    expect(screen.queryByLabelText("API 地址")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "从本地生成预览" })).not.toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(call => String(call[0]).includes("/items?"))).toBe(false);
    await userEvent.setup().click(screen.getByRole("button", { name: "配置来源连接" }));
    expect(await screen.findByLabelText("API 地址")).toBeInTheDocument();
    expect(screen.queryByText("任务与进度")).not.toBeInTheDocument();
  });

  it("keeps staff in the read-only imported-record view", async () => {
    mockApi("frontdesk");
    render(wrapper(<LegacyImportPage notify={vi.fn()} />));
    expect(await screen.findByText("已导入维修记录")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "从本地生成预览" })).not.toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(call => String(call[0]).endsWith("/source"))).toBe(false);
  });

  it("requires explicit opening balances at takeover", async () => {
    mockApi("admin");
    render(wrapper(<LegacyOrderPanel orderId={1} notify={vi.fn()} />));
    expect(await screen.findByText("历史已收金额")).toBeInTheDocument();
    expect(screen.getByText("期初待收金额")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("removes the takeover form after ownership transfers", async () => {
    mockApi("admin", "taken");
    render(wrapper(<LegacyOrderPanel orderId={1} notify={vi.fn()} />));
    expect(await screen.findByText("新系统已接管")).toBeInTheDocument();
    expect(screen.queryByText("历史已收金额")).not.toBeInTheDocument();
  });
});


function Workspace({ initial = "legacyImport", admin = true }: { initial?: LegacyView; admin?: boolean }) {
  const [view, setView] = useState<LegacyView>(initial);
  return <AppShellLayout view={view} current={legacyViews[view]} primaryNav={[{ key: admin ? "legacyImport" : "legacyRecords", label: "老系统导入", icon: null, children: legacyNavItems(admin) }]} userLabel="测试用户" roleLabel="管理员" modal={null} setView={setView} notify={vi.fn()} logout={vi.fn()} onCloseModal={vi.fn()}>
    <LegacyImportPage section={view} onNavigate={setView} notify={vi.fn()} />
  </AppShellLayout>;
}

function mockWorkspace() {
  let version = 1;
  const batches = [
    { batch_id: "recent-task", created_at: "2026-10-10 10:00", status: "completed", source_version: 1, total: 1, profile: {} },
    { batch_id: "review-task", created_at: "2026-10-09 10:00", status: "preview", filters: { date_from: "2026-10-01", date_to: "2026-10-09" }, source_version: 1, total: 1, profile: { engineers: { "老员工": 1 } } },
  ];
  vi.stubGlobal("fetch", vi.fn(async (input: string, options?: RequestInit) => {
    const url = String(input);
    let result: unknown = [];
    if (url === "/api/me") result = { role: "admin" };
    else if (url.endsWith("/source")) result = { version, base_url: "https://fixture.example", username: "fixture", mappings: {}, busy: false };
    else if (url.endsWith("/cache/status")) result = { initialized: 1, total: 1200, excluded: 5, busy: false };
    else if (url.endsWith("/batches")) result = batches;
    else if (url.includes("/items?")) result = [{ item_id: 42, source_id_raw: "OLD-42", action: "new", result: "pending" }];
    else if (url.includes("/batches/")) result = batches.find(batch => url.endsWith(batch.batch_id));
    else if (url.endsWith("/dispatch-engineers")) result = [{ username: "engineer", name: "新员工" }];
    else if (url.endsWith("/mappings") && options?.method === "PUT") { version += 1; result = {}; }
    else if (url.includes("/records")) result = { items: [], total: 0 };
    return new Response(JSON.stringify(result), { status: 200 });
  }));
}

describe("legacy workspace navigation", () => {
  it("opens the selected historical batch directly in the audit page", async () => {
    mockWorkspace();
    render(wrapper(<Workspace />));
    const row = await screen.findByRole("row", { name: /2026-10-09/ });
    await userEvent.setup().click(within(row).getByRole("button", { name: "查看任务" }));
    expect(await screen.findByText("OLD-42")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("同步审核");
    expect(screen.getByLabelText("开始日期")).toHaveValue("2026-10-01");
    expect(screen.getByLabelText("结束日期")).toHaveValue("2026-10-09");
    expect(screen.getByRole("status", { name: "当前预览 / 同步" })).toHaveTextContent("review-t");
    expect(screen.queryByText("任务与进度")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("API 地址")).not.toBeInTheDocument();
  });

  it("keeps filters and selection across pages, but blocks stale previews after saving mappings", async () => {
    mockWorkspace();
    const user = userEvent.setup();
    render(wrapper(<Workspace />));
    const row = await screen.findByRole("row", { name: /2026-10-09/ });
    await user.click(within(row).getByRole("button", { name: "查看任务" }));
    await screen.findByText("OLD-42");
    await user.type(screen.getByLabelText("旧账单 ID"), "42");
    await user.click(within(screen.getByRole("row", { name: /OLD-42/ })).getByRole("checkbox"));
    expect(screen.getByRole("button", { name: "确认同步（1 条）" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "调整映射规则" }));
    expect(await screen.findByText("员工与状态映射")).toBeInTheDocument();
    expect(screen.queryByText("OLD-42")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "同步审核" }));
    expect(await screen.findByRole("button", { name: "确认同步（1 条）" })).toBeEnabled();
    expect(screen.getByLabelText("旧账单 ID")).toHaveValue("42");
    await user.click(screen.getByRole("button", { name: "调整映射规则" }));
    await user.click(await screen.findByRole("button", { name: "保存并去重新预览 →" }));
    expect(await screen.findByText("暂存数据、配置或关联已变化，请重新生成预览后再同步")).toBeInTheDocument();
    expect(screen.getByLabelText("旧账单 ID")).toHaveValue("42");
    await waitFor(() => expect(screen.getByRole("button", { name: "确认同步（0 条）" })).toBeDisabled());
    expect(vi.mocked(fetch).mock.calls.some(call => String(call[0]).endsWith("/execute"))).toBe(false);
  });

  it("shows only record navigation to staff even when an admin section is requested", async () => {
    mockApi("frontdesk");
    render(wrapper(<Workspace initial="legacyRecords" admin={false} />));
    expect(await screen.findByText("已导入维修记录")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导入记录" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "连接设置" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "同步审核" })).not.toBeInTheDocument();
  });

  it("keeps connection settings and data staging on distinct pages", async () => {
    mockWorkspace();
    const user = userEvent.setup();
    render(wrapper(<Workspace initial="legacySource" />));
    await waitFor(() => expect(screen.getByLabelText("API 地址")).toHaveValue("https://fixture.example"));
    expect(screen.queryByRole("button", { name: "增量拉取到本地" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "下一步：拉取与整理数据 →" }));
    expect(await screen.findByRole("button", { name: "增量拉取到本地" })).toBeInTheDocument();
    expect(screen.queryByLabelText("API 地址")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "下一步：生成同步预览 →" }));
    expect(await screen.findByRole("button", { name: "从本地生成预览" })).toBeInTheDocument();
  });
});
