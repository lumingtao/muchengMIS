const defaultPoolSort = {
  repair: { key: "machine_id", direction: "desc" },
  recycle: { key: "machine_id", direction: "desc" },
};

const state = {
  user: localStorage.getItem("mis_user") || "",
  profile: null,
  currentTimeline: null,
  repairWorkbench: null,
  warehouse: null,
  repairWorkbenchSort: { key: "updated_at", direction: "desc" },
  poolSort: {
    repair: { ...defaultPoolSort.repair },
    recycle: { ...defaultPoolSort.recycle },
  },
};

const titles = {
  repairPool: ["维修闭环中心", "集中查看真实维修工单、待补资料、挂账和财务确认。"],
  recyclePool: ["回收订单池", "集中查看回收机器、入库和销售流转。"],
  repair: ["维修开单", "机器到店、检测报价、维修项目、交付检测。"],
  recycle: ["回收开单", "机器到店、验机报价、付款入库、销售定价。"],
  warehouse: ["配件仓库", "物料编码、批次、单件码、申领发放、退料退货、盘点调整和维修协同。"],
  inventory: ["回收库存", "查看已回收入库并可销售的机器。"],
  sales: ["销售开单", "从回收库存创建销售单。"],
  customers: ["客户", "查询由机器业务产生的客户主数据。"],
  payments: ["财务流水", "登记回收支出、维修收入和销售收入。"],
  reports: ["报表", "查看机器状态、库存成本和收支汇总。"],
  audit: ["日志", "查看后端写操作审计记录。"],
};

function $(selector) {
  return document.querySelector(selector);
}

function showToast(message, isError = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.hidden = true; }, 3200);
}

function setAuthenticated(loggedIn) {
  $("#auth-screen").hidden = loggedIn;
  $("#app-shell").hidden = !loggedIn;
  $("#account-menu").hidden = !loggedIn;
  if (!loggedIn) {
    closeAccountDropdown();
    $("#account-detail").textContent = "";
  }
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(state.user ? { "X-User": state.user } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(path, {
    ...options,
    headers,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new Error(data?.detail || "请求失败");
  return data;
}

function numericKeys() {
  return new Set([
    "machine_id", "repair_order_id", "recycle_order_id", "inventory_item_id",
    "source_id", "customer_id", "quoted_amount", "quantity", "cost_amount", "charge_amount",
    "pay_amount", "sale_price", "amount", "sku_id", "category_id", "area_id", "location_id",
    "default_location_id", "material_id", "batch_id", "unit_id", "request_id", "return_id",
    "repair_sku_id", "qty", "unit_cost", "min_qty", "priority", "adjust_material_id", "adjust_qty",
  ]);
}

function formData(form) {
  const numbers = numericKeys();
  const out = {};
  new FormData(form).forEach((value, key) => {
    if (value === "") return;
    out[key] = numbers.has(key) ? Number(value) : value;
  });
  return out;
}

function machinePayload(data) {
  return {
    imei: data.imei || "",
    serial: data.serial || "",
    model: data.model,
    memory: data.memory || "",
    color: data.color || "",
    condition: data.condition || "",
  };
}

function customerPayload(data) {
  if (!data.customer_name) return null;
  return { name: data.customer_name, phone: data.phone || "" };
}

const moneyKeys = new Set(["quoted_amount", "cost_amount", "charge_amount", "paid_amount", "pay_amount", "sale_price", "amount", "inventory_cost", "avg_cost", "unit_cost", "total_cost", "refund_amount"]);
const idKeys = new Set(["machine_id", "customer_id", "repair_order_id", "recycle_order_id", "inventory_item_id", "sales_order_id", "payment_id", "source_id", "target_id", "income_item_id", "cost_item_id", "repair_material_id", "stock_movement_id", "material_id", "batch_id", "unit_id", "request_id", "return_id", "category_id", "location_id", "area_id", "binding_id"]);
const strongKeys = new Set(["machine_no", "model", "name", "customer_name"]);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatMoney(value) {
  const amount = Number(value || 0);
  return `¥${amount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatMetric(label, value) {
  return label.includes("成本") || label.includes("流水") ? formatMoney(value) : escapeHtml(value);
}

function badgeClass(value) {
  if (["维修"].includes(value)) return "repair";
  if (["回收", "回收库存"].includes(value)) return "recycle";
  if (["销售", "已售出"].includes(value)) return "sale";
  if (["已交付", "已结单", "成功", "已付款"].includes(value)) return "done";
  if (["到店", "检测中", "已报价", "维修中", "在库"].includes(value)) return "pending";
  return "neutral";
}

function renderCell(row, column) {
  const key = column[0];
  const raw = row[key];
  if (raw === null || raw === undefined || raw === "") return '<span class="muted-cell">-</span>';
  if (moneyKeys.has(key)) return `<span class="money-cell">${formatMoney(raw)}</span>`;
  if (["source_type", "current_status", "status", "direction", "result"].includes(key)) {
    return `<span class="badge ${badgeClass(raw)}">${escapeHtml(raw)}</span>`;
  }
  const className = [
    idKeys.has(key) ? "id-cell" : "",
    strongKeys.has(key) ? "strong-cell" : "",
  ].filter(Boolean).join(" ");
  return `<span${className ? ` class="${className}"` : ""}>${escapeHtml(raw)}</span>`;
}

function table(rows, columns, emptyText = "暂无数据", options = {}) {
  if (!rows || rows.length === 0) {
    return `<div class="empty-state"><div><strong>${escapeHtml(emptyText)}</strong><span>调整筛选条件或新增业务单据后会显示在这里。</span></div></div>`;
  }
  const sort = options.sort || {};
  const header = columns.map(c => {
    const key = c[0];
    const isActive = sort.key === key;
    const marker = isActive ? (sort.direction === "asc" ? "↑" : "↓") : "↕";
    if (!options.sortable) return `<th>${escapeHtml(c[1])}</th>`;
    return `<th><button type="button" class="sort-button ${isActive ? "active" : ""}" data-sort-key="${escapeHtml(key)}" aria-label="按${escapeHtml(c[1])}排序">${escapeHtml(c[1])}<span>${marker}</span></button></th>`;
  }).join("");
  return `<table><thead><tr>${header}</tr></thead><tbody>${
    rows.map(row => `<tr>${columns.map(c => `<td>${renderCell(row, c)}</td>`).join("")}</tr>`).join("")
  }</tbody></table>`;
}

function detailTable(rows, columns) {
  return table(rows || [], columns);
}

function hasPermission(permission) {
  return Boolean(state.profile?.permissions?.includes(permission));
}

function option(value, label, current) {
  return `<option value="${escapeHtml(value)}"${value === current ? " selected" : ""}>${escapeHtml(label)}</option>`;
}

const modelOptions = [
  "iPhone 16", "iPhone 16 Pro", "iPhone 16 Pro Max",
  "iPhone 15", "iPhone 15 Pro", "iPhone 15 Pro Max",
  "iPhone 14", "iPhone 14 Pro", "iPhone 14 Pro Max",
  "iPhone 13", "iPhone 13 Pro", "iPhone 13 Pro Max",
  "iPhone 12",
];
const memoryOptions = ["64G", "128G", "256G", "512G", "1TB"];
const colorOptions = ["黑色", "白色", "银色", "金色", "蓝色", "绿色", "红色", "原色钛金属", "沙漠色钛金属"];
const conditionOptions = ["功能正常", "屏幕划痕", "屏幕损坏", "外观磕碰", "电池老化", "主板故障", "不开机", "进水检测"];

function selectOptions(values, current, placeholder = "请选择") {
  const normalized = current || "";
  const merged = normalized && !values.includes(normalized) ? [normalized, ...values] : values;
  return option("", placeholder, normalized) + merged.map(value => option(value, value, normalized)).join("");
}

const statusOptionsByLine = {
  "": ["到店", "检测中", "已报价", "维修中", "待交付", "已交付", "已回收", "回收库存", "待销售", "已售出", "已结单"],
  "维修": ["到店", "检测中", "已报价", "维修中", "待交付", "已交付", "已结单"],
  "回收": ["到店", "检测中", "已报价", "已回收", "回收库存", "待销售", "已售出", "已结单"],
  "销售": ["待销售", "已售出", "已结单"],
};

function statusOptions(sourceType, currentStatus) {
  const values = [...(statusOptionsByLine[sourceType || ""] || statusOptionsByLine[""])];
  if (currentStatus && !values.includes(currentStatus)) values.unshift(currentStatus);
  return values.map(status => option(status, status, currentStatus)).join("");
}

function labeledField(label, control) {
  return `<label class="field"><span>${escapeHtml(label)}</span>${control}</label>`;
}

function editGroup(title, fields) {
  return `
    <section class="info-group">
      <div class="info-group-title">${escapeHtml(title)}</div>
      <div class="info-group-grid">
        ${fields.join("")}
      </div>
    </section>
  `;
}

function infoItem(label, value) {
  return `<div class="info-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "未录入")}</strong></div>`;
}

function infoGroup(title, items) {
  return `
    <section class="info-group">
      <div class="info-group-title">${escapeHtml(title)}</div>
      <div class="info-group-grid">
        ${items.map(([label, value]) => infoItem(label, value)).join("")}
      </div>
    </section>
  `;
}

function renderPriceChangeForm(kind, order) {
  if (!order) return "";
  const idKey = kind === "repair" ? "repair_order_id" : "recycle_order_id";
  return `
    <form id="price-change-form" class="machine-edit-form price-change-form" data-kind="${kind}" data-order-id="${escapeHtml(order[idKey])}" hidden>
      <div class="info-group">
        <div class="info-group-title">改价</div>
        <div class="info-group-grid">
          ${labeledField("新报价", `<input name="quoted_amount" type="number" step="0.01" min="0" value="${escapeHtml(order.quoted_amount || 0)}" required>`)}
          ${labeledField("改价备注", `<input name="remark" placeholder="填写原因，便于后续追踪">`)}
        </div>
      </div>
      <div class="button-row">
        <button type="submit">保存改价</button>
        <button type="button" class="ghost-button" id="cancel-price-change">取消</button>
      </div>
    </form>
  `;
}

function renderBusinessSections(timeline) {
  const line = timeline.machine.source_type || "";
  const sections = [];
  if (line === "维修") {
    const order = timeline.repair_orders?.[0];
    sections.push(`
      <div class="section-title-row">
        <h3>维修记录</h3>
      </div>
      ${renderPriceChangeForm("repair", order)}
      ${detailTable(timeline.repair_orders, [
        ["repair_order_id", "维修单"], ["status", "状态"], ["workflow_status", "待办归属"], ["assigned_to", "工程师"],
        ["fault_description", "前台故障"], ["fault_detail", "检测故障"], ["repair_solution", "维修方案"],
        ["quote_confirm_status", "客户确认"], ["quoted_amount", "报价"]
      ])}
      ${order ? `
        <form id="repair-assign-form" class="inline-action-form">
          <input name="engineer_user_id" placeholder="工程师账号，例如 engineer" required>
          <input name="remark" placeholder="指派备注">
          <button type="submit">指派工程师</button>
        </form>
        <form id="repair-confirm-form" class="inline-action-form">
          <select name="confirm_result">
            <option>客户同意维修</option>
            <option>客户拒修</option>
            <option>待考虑</option>
          </select>
          <input name="confirm_method" placeholder="确认方式">
          <input name="contact_person" placeholder="联系人">
          <input name="remark" placeholder="沟通备注">
          <button type="submit">客户确认</button>
        </form>
        <form id="repair-engineer-close-form" class="inline-action-form">
          <input name="remark" placeholder="工程师结单备注">
          <button type="submit">工程师结单</button>
        </form>
        <div class="section-action-row"><button type="button" id="open-price-change" class="ghost-button">改价</button></div>
      ` : ""}
    `);
    if (timeline.repair_items?.length) {
      sections.push(`
        <h3>维修项目</h3>
        ${detailTable(timeline.repair_items, [
          ["repair_item_id", "项目ID"], ["repair_order_id", "维修单"], ["sku_id", "SKU"], ["item_name", "项目"], ["quantity", "数量"], ["cost_amount", "成本"], ["charge_amount", "收费"]
        ])}
      `);
    }
    if (timeline.repair_payments?.length) {
      sections.push(`
        <h3>维修收款</h3>
        ${detailTable(timeline.repair_payments, [
          ["payment_id", "流水"], ["source_id", "维修单"], ["direction", "方向"], ["amount", "金额"], ["method", "方式"], ["created_at", "时间"]
        ])}
      `);
    }
    return sections.join("");
  }
  if (line === "回收") {
    const order = timeline.recycle_orders?.[0];
    sections.push(`
      <div class="section-title-row">
        <h3>回收记录</h3>
      </div>
      ${renderPriceChangeForm("recycle", order)}
      ${detailTable(timeline.recycle_orders, [
        ["recycle_order_id", "回收单"], ["status", "状态"], ["inspection_note", "验机记录"], ["inspection_result", "验机结论"], ["quoted_amount", "报价"], ["paid_amount", "已付"]
      ])}
      ${order ? '<div class="section-action-row"><button type="button" id="open-price-change" class="ghost-button">改价</button></div>' : ""}
    `);
    if (timeline.inventory_items?.length) {
      sections.push(`
        <h3>库存记录</h3>
        ${detailTable(timeline.inventory_items, [
          ["inventory_item_id", "库存ID"], ["status", "库存状态"], ["cost_amount", "成本"], ["sale_price", "销售定价"]
        ])}
      `);
    }
    if (timeline.sales_orders?.length) {
      sections.push(`
        <h3>销售记录</h3>
        ${detailTable(timeline.sales_orders, [
          ["sales_order_id", "销售单"], ["status", "状态"], ["sale_price", "销售价"], ["salesperson", "销售人"], ["created_at", "时间"]
        ])}
      `);
    }
    return sections.join("");
  }
  if (line === "销售") {
    sections.push(`
      <h3>销售记录</h3>
      ${detailTable(timeline.sales_orders, [
        ["sales_order_id", "销售单"], ["status", "状态"], ["sale_price", "销售价"], ["salesperson", "销售人"], ["created_at", "时间"]
      ])}
    `);
    return sections.join("");
  }
  return `
    <h3>业务记录</h3>
    ${detailTable([], [["id", "单据"], ["status", "状态"]])}
  `;
}

function renderNotes(notes = []) {
  return `
    <div class="section-title-row">
      <h3>备注</h3>
    </div>
    <form id="machine-note-form" class="machine-edit-form note-form" hidden>
      ${labeledField("新增备注", `<textarea name="content" placeholder="输入本次备注，保存后不可修改" required></textarea>`)}
      <div class="button-row">
        <button type="submit">保存备注</button>
        <button type="button" class="ghost-button" id="cancel-note">取消</button>
      </div>
    </form>
    ${detailTable(notes, [
      ["created_at", "时间"], ["content", "内容"], ["operator", "备注人"]
    ])}
    <div class="section-action-row"><button type="button" id="add-note" class="ghost-button">备注</button></div>
  `;
}

function syncViewUrl(name) {
  const url = new URL(window.location.href);
  if (name === "repairPool") {
    url.searchParams.delete("view");
  } else {
    url.searchParams.set("view", name);
  }
  window.history.replaceState({}, "", url);
}

function setView(name, options = {}) {
  const view = titles[name] ? name : "repairPool";
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === view));
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $("#view-title").textContent = titles[view][0];
  $("#view-subtitle").textContent = titles[view][1];
  $("#page-path").textContent = `当前位置 / 机器生命周期工作台 / ${titles[view][0]}`;
  if (options.syncUrl !== false) syncViewUrl(view);
  refresh(view);
}

function initialView() {
  const view = new URLSearchParams(window.location.search).get("view");
  return titles[view] ? view : "repairPool";
}

function openOrderFormPage(view) {
  const url = new URL(window.location.href);
  url.searchParams.set("view", view);
  const opened = window.open(url.toString(), "_blank");
  if (opened) opened.opener = null;
  if (!opened) {
    showToast("浏览器阻止了新标签页，请允许弹出窗口后重试");
  }
}

async function loadProfile() {
  if (!state.user) {
    state.profile = null;
    setAuthenticated(false);
    return;
  }
  try {
    state.profile = await api("/api/me");
    renderAccount(true);
    setAuthenticated(true);
    refresh(document.querySelector(".view.active").id);
  } catch (_) {
    localStorage.removeItem("mis_user");
    state.user = "";
    state.profile = null;
    renderAccount(false);
  }
}

function renderAccount(loggedIn) {
  if (!loggedIn) {
    setAuthenticated(false);
    closeAccountDropdown();
    return;
  }
  $("#account-button").textContent = state.profile.username;
  $("#account-name").textContent = state.profile.username;
  $("#account-role").textContent = `角色：${state.profile.role}`;
}

function openAccountDropdown() {
  $("#account-dropdown").classList.add("open");
  $("#account-dropdown").setAttribute("aria-hidden", "false");
}

function closeAccountDropdown() {
  $("#account-dropdown").classList.remove("open");
  $("#account-dropdown").setAttribute("aria-hidden", "true");
}

function toggleAccountDropdown() {
  if ($("#account-dropdown").classList.contains("open")) {
    closeAccountDropdown();
  } else {
    openAccountDropdown();
  }
}

function showAccountDetail(kind) {
  if (!state.profile) return;
  if (kind === "permissions") {
    $("#account-detail").textContent = state.profile.permissions.join("\n");
  } else {
    $("#account-detail").textContent = JSON.stringify({
      username: state.profile.username,
      role: state.profile.role,
    }, null, 2);
  }
}

async function refresh(name = "repairPool") {
  try {
    if (name === "repairPool") await loadBusinessPool("repair");
    if (name === "recyclePool") await loadBusinessPool("recycle");
    if (name === "warehouse") await loadWarehouse();
    if (name === "inventory") await loadInventory();
    if (name === "customers") await loadCustomers();
    if (name === "payments") await loadPayments();
    if (name === "reports") await loadReports();
    if (name === "audit") await loadAudit();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshActiveBusinessPool() {
  const active = document.querySelector(".view.active")?.id;
  if (active === "recyclePool") {
    await loadBusinessPool("recycle");
  } else if (active === "repairPool") {
    await loadBusinessPool("repair");
  }
}

function poolConfig(kind) {
  if (kind === "repair") {
    return {
      line: "维修",
      keyword: "#repair-keyword",
      status: "#repair-status",
      table: "#repair-order-table",
      empty: "没有匹配的维修订单",
    };
  }
  return {
    line: "回收",
    keyword: "#recycle-keyword",
    status: "#recycle-status",
    table: "#recycle-order-table",
    empty: "没有匹配的回收订单",
  };
}

function applyBusinessPoolFilters(rows, kind) {
  const config = poolConfig(kind);
  const status = $(config.status).value;
  return rows.filter(row => {
    const lineOk = row.source_type === config.line;
    const statusOk = !status || row.current_status === status;
    return lineOk && statusOk;
  });
}

function sortValue(row, key) {
  const sourceKey = {
    completed_at_display: "completed_at",
    closed_at_display: "closed_at",
    workflow_progress: "workflow_status",
    engineer_name: "assigned_to",
  }[key] || key;
  if (sourceKey !== key) {
    return sortValue(row, sourceKey);
  }
  const value = row[key];
  if (value === null || value === undefined || value === "") return "";
  if (numericKeys().has(key)) return Number(value);
  if (key.endsWith("_at") || key.endsWith("_time")) {
    const time = Date.parse(value);
    return Number.isNaN(time) ? String(value) : time;
  }
  return String(value).toLocaleLowerCase("zh-CN");
}

function sortedRows(rows, kind) {
  const sort = kind === "repairWorkbench" ? state.repairWorkbenchSort : state.poolSort[kind];
  return [...rows].sort((a, b) => {
    const av = sortValue(a, sort.key);
    const bv = sortValue(b, sort.key);
    if (typeof av === "number" && typeof bv === "number") {
      return sort.direction === "asc" ? av - bv : bv - av;
    }
    const result = String(av).localeCompare(String(bv), "zh-CN", { numeric: true, sensitivity: "base" });
    return sort.direction === "asc" ? result : -result;
  });
}

function bindRepairWorkbenchSort() {
  document.querySelectorAll("#repair-order-table [data-sort-key]").forEach(button => {
    button.addEventListener("click", () => {
      const key = button.dataset.sortKey;
      const current = state.repairWorkbenchSort;
      state.repairWorkbenchSort = {
        key,
        direction: current.key === key && current.direction === "asc" ? "desc" : "asc",
      };
      if (state.repairWorkbench) renderRepairWorkbench(state.repairWorkbench);
    });
  });
}

function resetBusinessPoolFilters(kind) {
  const config = poolConfig(kind);
  $(config.keyword).value = "";
  $(config.status).value = "";
  if (kind === "repair") {
    $("#repair-payment-status").value = "";
    $("#repair-customer-type").value = "";
    $("#repair-missing-only").value = "";
    $("#repair-date-from").value = "";
    $("#repair-date-to").value = "";
    state.repairWorkbenchSort = { key: "updated_at", direction: "desc" };
  }
  state.poolSort[kind] = { ...defaultPoolSort[kind] };
  loadBusinessPool(kind);
}

async function loadBusinessPool(kind) {
  if (kind === "repair") {
    await loadRepairWorkbench();
    return;
  }
  const config = poolConfig(kind);
  const q = encodeURIComponent($(config.keyword).value || "");
  const rows = await api(`/api/machines?q=${q}`);
  const filtered = sortedRows(applyBusinessPoolFilters(rows, kind), kind);
  const columns = [
    ["machine_no", "机器编号"], ["imei", "IMEI"], ["model", "机型"],
    ["customer_name", "客户"], ["current_status", "当前状态"], ["assigned_to", "工程师"],
    ["updated_at", "更新时间"],
  ];
  $(config.table).innerHTML = table(filtered, columns, config.empty, { sortable: true, sort: state.poolSort[kind] });
  bindPoolSort(kind);
  bindOrderRows(filtered, config.table);
}

function repairFilterText(order) {
  return [
    order.order_no, order.machine_no, order.imei, order.serial, order.model, order.customer_name,
    order.customer_type, order.counter_no, order.assigned_to, order.service_type, order.remark,
  ].join(" ").toLowerCase();
}

function dateBoundary(value, endOfDay = false) {
  if (!value) return null;
  const date = new Date(`${value}T${endOfDay ? "23:59:59" : "00:00:00"}`);
  const time = date.getTime();
  return Number.isNaN(time) ? null : time;
}

function repairOrderUpdatedAt(order) {
  const time = Date.parse(order.updated_at || "");
  return Number.isNaN(time) ? null : time;
}

function repairWorkbenchDisplayRow(order) {
  return {
    ...order,
    completed_at_display: order.completed_at || "待完成",
    closed_at_display: order.closed_at || "未完结",
    workflow_progress: order.workflow_status || order.status || "待确认",
    engineer_name: order.assigned_to || "待指派",
  };
}

function repairWorkbenchRows(orders) {
  const keyword = ($("#repair-keyword").value || "").trim().toLowerCase();
  const status = $("#repair-status").value || "";
  const payment = $("#repair-payment-status").value || "";
  const customerType = $("#repair-customer-type").value || "";
  const missingOnly = $("#repair-missing-only").value === "1";
  const fromTime = dateBoundary($("#repair-date-from")?.value || "");
  const toTime = dateBoundary($("#repair-date-to")?.value || "", true);
  return (orders || []).filter(order => {
    if (keyword && !repairFilterText(order).includes(keyword)) return false;
    if (status && order.status !== status) return false;
    if (payment && order.payment_status !== payment) return false;
    if (customerType && order.customer_type !== customerType) return false;
    if (missingOnly && !(order.unknown_fields || []).length && !String(order.remark || "").includes("待补") && !String(order.remark || "").includes("待确认")) return false;
    if (fromTime !== null || toTime !== null) {
      const updatedAt = repairOrderUpdatedAt(order);
      if (updatedAt === null) return false;
      if (fromTime !== null && updatedAt < fromTime) return false;
      if (toTime !== null && updatedAt > toTime) return false;
    }
    return true;
  }).map(repairWorkbenchDisplayRow);
}

function renderRepairMetrics(data) {
  const orders = data.orders || [];
  const total = orders.length;
  const finance = orders.filter(x => x.payment_status === "已付款待财务确认").length;
  const receivable = orders.filter(x => x.payment_status === "同行挂账").length;
  const open = orders.filter(x => !["已完结", "已结单"].includes(x.status)).length;
  const missing = orders.filter(x => (x.unknown_fields || []).length || String(x.remark || "").includes("待补") || String(x.remark || "").includes("待确认")).length;
  $("#repair-workbench-metrics").innerHTML = [
    ["真实工单", total],
    ["未完结", open],
    ["财务待确认", finance],
    ["同行挂账", receivable],
    ["待补资料", missing],
  ].map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
}

function renderRepairWorkbench(data) {
  state.repairWorkbench = data;
  renderRepairMetrics(data);
  const rows = sortedRows(repairWorkbenchRows(data.orders), "repairWorkbench");
  const columns = [
    ["order_no", "工单号"], ["status", "维修状态"], ["payment_status", "收款状态"],
    ["customer_name", "客户"], ["customer_type", "类型"], ["counter_no", "柜台/同行"],
    ["model", "机型"], ["created_at", "建单时间"], ["completed_at_display", "维修完成时间"],
    ["closed_at_display", "订单完结时间"], ["workflow_progress", "维修进度"],
    ["engineer_name", "工程师"], ["updated_at", "更新时间"],
  ];
  $("#repair-order-table").innerHTML = table(rows, columns, "暂无匹配维修工单", { sortable: true, sort: state.repairWorkbenchSort });
  bindRepairWorkbenchSort();
  document.querySelectorAll("#repair-order-table tbody tr").forEach((tr, index) => {
    tr.addEventListener("click", () => openRepairWorkbenchDetail(rows[index].repair_order_id));
  });
  $("#repair-finance-pending").innerHTML = table(data.finance_pending, [
    ["order_no", "工单"], ["customer_name", "客户"], ["amount", "金额"],
    ["method", "方式"], ["transaction_no", "流水号"], ["received_by", "收款人"], ["paid_at", "收款时间"],
  ], "暂无财务待确认流水");
  $("#repair-receivables").innerHTML = table(data.receivable_summary, [
    ["customer_name", "客户/柜台"], ["counter_no", "柜台号"], ["receivable_type", "类型"],
    ["count", "单数"], ["amount", "金额"], ["status", "状态"],
  ], "暂无未结应收");
  $("#repair-material-summary").innerHTML = table(data.material_summary, [
    ["sku", "SKU"], ["name", "物料"], ["compatible_range", "适配范围"],
    ["current_qty", "库存"], ["avg_cost", "均价"], ["status", "状态"], ["remark", "备注"],
  ], "暂无维修物料库存");
}

async function loadRepairWorkbench() {
  const data = await api("/api/repair-workbench");
  renderRepairWorkbench(data);
}

function fieldBlock(label, value) {
  return `<div class="field-block"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "待补")}</strong></div>`;
}

function repairActionButton(action, label, extra = "") {
  return `<button type="button" class="repair-action-button" data-action="${escapeHtml(action)}" ${extra}>${escapeHtml(label)}</button>`;
}

function renderRepairWorkbenchDetail(detail) {
  const order = detail.order;
  $("#modal-title").textContent = `${order.order_no} / ${order.model}`;
  $("#modal-subtitle").textContent = `${order.status} · ${order.payment_status} · ${order.customer_name}`;
  $("#modal-content").innerHTML = `
    <div class="repair-detail-grid">
      ${fieldBlock("客户描述", order.fault_description)}
      ${fieldBlock("工程师检测结论", order.diagnosis)}
      ${fieldBlock("维修方案", order.repair_solution)}
      ${fieldBlock("待补字段", (order.unknown_fields || []).join("、") || "无")}
    </div>
    <div class="detail-actions">
      ${repairActionButton("repair_completed", "维修完成")}
      ${repairActionButton("delivered", "已交付")}
      ${repairActionButton("register_payment", "登记收款")}
      ${repairActionButton("finance_confirm", "财务确认")}
      ${repairActionButton("mark_receivable", "同行/应收挂账")}
      ${repairActionButton("settle_receivable", "挂账结清")}
      ${repairActionButton("close", "订单完结")}
    </div>
    <h3>收入项目</h3>
    ${detailTable(detail.income_items, [["item_type", "类型"], ["item_name", "项目"], ["amount", "金额"], ["status", "状态"], ["remark", "备注"]])}
    <h3>成本项目</h3>
    ${detailTable(detail.cost_items, [["item_type", "类型"], ["item_name", "项目"], ["qty", "数量"], ["unit_cost", "单价"], ["total_cost", "成本"], ["status", "状态"]])}
    <h3>物料消耗</h3>
    ${detailTable(detail.materials, [["sku", "SKU"], ["name", "物料"], ["qty", "数量"], ["unit_cost", "单价"], ["total_cost", "成本"], ["issued_at", "领料时间"], ["remark", "备注"]])}
    <h3>付款流水</h3>
    ${detailTable(detail.payments, [["payment_id", "流水"], ["amount", "金额"], ["method", "方式"], ["transaction_no", "流水号"], ["status", "状态"], ["received_by", "收款人"], ["confirmed_by", "确认人"], ["paid_at", "收款时间"]])}
    <h3>应收/挂账</h3>
    ${detailTable(detail.receivables, [["customer_name", "客户"], ["receivable_type", "类型"], ["amount", "金额"], ["status", "状态"], ["settled_at", "结清时间"], ["remark", "备注"]])}
    <h3>时间线</h3>
    ${detailTable(detail.events, [["created_at", "时间"], ["title", "动作"], ["detail", "内容"], ["operator", "操作人"]])}
  `;
  document.querySelectorAll(".repair-action-button").forEach(button => {
    button.addEventListener("click", () => runRepairAction(order.repair_order_id, button.dataset.action));
  });
}

async function openRepairWorkbenchDetail(repairOrderId) {
  const detail = await api(`/api/repair-workbench/${repairOrderId}`);
  renderRepairWorkbenchDetail(detail);
  $("#order-modal").hidden = false;
  document.body.classList.add("modal-open");
}

async function runRepairAction(repairOrderId, action) {
  const payload = { action };
  if (action === "delivered") {
    payload.status = prompt("交付状态：已交付 / 待取机 / 待送机 / 待返寄", "已交付") || "已交付";
  }
  if (action === "register_payment") {
    const amount = Number(prompt("本次收款金额", "0") || 0);
    if (!amount) return;
    payload.amount = amount;
    payload.method = prompt("付款方式", "待确认") || "待确认";
    payload.transaction_no = prompt("流水号，未知填待补", "待补") || "待补";
    payload.received_by = state.user || "前台待确认";
  }
  if (action === "finance_confirm") {
    payload.confirmed_by = prompt("财务确认人", state.user || "待确认") || "待确认";
  }
  if (action === "mark_receivable") {
    payload.payment_status = prompt("应收类型：同行挂账 / 未收款", "同行挂账") || "同行挂账";
    const amountText = prompt("应收金额，未知可填 0", "0");
    payload.amount = Number(amountText || 0);
    payload.remark = prompt("挂账备注", "待补") || "待补";
  }
  if (action === "settle_receivable") {
    payload.remark = prompt("结清备注", "财务已确认") || "财务已确认";
  }
  try {
    const detail = await api(`/api/repair-orders/${repairOrderId}/workflow-action`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast("维修闭环动作已保存");
    renderRepairWorkbenchDetail(detail);
    await loadRepairWorkbench();
  } catch (error) {
    showToast(error.message, true);
  }
}

function bindPoolSort(kind) {
  const config = poolConfig(kind);
  document.querySelectorAll(`${config.table} [data-sort-key]`).forEach(button => {
    button.addEventListener("click", () => {
      const key = button.dataset.sortKey;
      const current = state.poolSort[kind];
      state.poolSort[kind] = {
        key,
        direction: current.key === key && current.direction === "asc" ? "desc" : "asc",
      };
      loadBusinessPool(kind);
    });
  });
}

function bindOrderRows(rows, tableSelector) {
  const bodyRows = document.querySelectorAll(`${tableSelector} tbody tr`);
  bodyRows.forEach((tr, index) => {
    tr.addEventListener("click", async () => {
      const machineId = rows[index].machine_id;
      await openOrderModal(machineId);
    });
  });
}

async function fetchTimeline(machineId) {
  return api(`/api/machines/${machineId}/timeline`);
}

function renderOrderModal(timeline) {
  const machine = timeline.machine;
  const customer = timeline.customer || {};
  const customerName = customer.name || machine.customer_name || "";
  const customerPhone = customer.phone || "";
  const customerCategory = customer.category || "";
  state.currentTimeline = timeline;
  $("#modal-title").textContent = `${machine.machine_no} / ${machine.model}`;
  $("#modal-subtitle").textContent = `机器ID ${machine.machine_id} · ${machine.current_status}`;
  $("#modal-content").innerHTML = `
    <form id="machine-edit-form" class="machine-edit-form" hidden>
      <div class="info-panel">
        ${editGroup("设备标识", [
          labeledField("机器编号", `<input value="${escapeHtml(machine.machine_no || "")}" disabled>`),
          labeledField("IMEI", `<input name="imei" placeholder="扫描或输入 IMEI" value="${escapeHtml(machine.imei || "")}" inputmode="numeric">`),
          labeledField("序列号", `<input name="serial" placeholder="输入序列号" value="${escapeHtml(machine.serial || "")}">`),
        ])}
        ${editGroup("规格属性", [
          labeledField("机型", `<select name="model" required>${selectOptions(modelOptions, machine.model || "", "选择机型")}</select>`),
          labeledField("内存", `<select name="memory">${selectOptions(memoryOptions, machine.memory || "", "选择内存")}</select>`),
          labeledField("颜色", `<select name="color">${selectOptions(colorOptions, machine.color || "", "选择颜色")}</select>`),
          labeledField("机况", `<select name="condition">${selectOptions(conditionOptions, machine.condition || "", "选择机况")}</select>`),
        ])}
        ${editGroup("客户信息", [
          `<input type="hidden" name="customer_id" value="${escapeHtml(customer.customer_id || machine.customer_id || "")}">`,
          labeledField("客户姓名", `<input name="customer_name" value="${escapeHtml(customerName || "")}" placeholder="输入客户姓名">`),
          labeledField("电话", `<input name="customer_phone" value="${escapeHtml(customerPhone || "")}" placeholder="输入电话号码" inputmode="tel">`),
          labeledField("客户类型", `<select name="customer_category">${selectOptions(["个人客户", "同行客户", "商家客户"], customerCategory || "", "选择客户类型")}</select>`),
        ])}
        ${editGroup("订单状态", [
          `<input type="hidden" name="source_type" id="machine-source-type" value="${escapeHtml(machine.source_type || "")}">`,
          labeledField("当前状态", `<select name="current_status" id="machine-current-status">${statusOptions(machine.source_type || "", machine.current_status)}</select>`),
        ])}
      </div>
      <div class="section-action-row">
        <button type="submit" id="save-machine-edit" form="machine-edit-form" hidden>保存修改</button>
        <button type="button" class="ghost-button" id="cancel-machine-edit" hidden>取消</button>
      </div>
    </form>
    <div id="machine-info-panel" class="info-panel">
      ${infoGroup("设备标识", [
        ["机器编号", machine.machine_no],
        ["IMEI", machine.imei],
        ["序列号", machine.serial],
      ])}
      ${infoGroup("规格属性", [
        ["机型", machine.model],
        ["内存", machine.memory],
        ["颜色", machine.color],
        ["机况", machine.condition],
      ])}
      ${infoGroup("客户信息", [
        ["客户姓名", customerName || "未关联客户"],
        ["电话", customerPhone || "未录入"],
        ["客户类型", customerCategory || "未录入"],
      ])}
      ${infoGroup("订单状态", [
        ["当前状态", machine.current_status],
      ])}
      <div class="section-action-row"><button type="button" id="edit-machine" class="ghost-button">编辑</button></div>
    </div>
    ${renderBusinessSections(timeline)}
    ${renderNotes(timeline.notes)}
    <h3>操作日志</h3>
    ${detailTable(timeline.events, [
      ["created_at", "时间"], ["event_type", "类型"], ["title", "动作"], ["detail", "内容"], ["operator", "操作人"]
    ])}
  `;
  bindMachineEditForm(machine.machine_id);
  bindPriceChangeForm(machine.machine_id);
  bindMachineNoteForm(machine.machine_id);
  bindRepairOrderActionForms(machine.machine_id, timeline.repair_orders?.[0]);
}

function bindRepairOrderActionForms(machineId, order) {
  if (!order) return;
  const assignForm = $("#repair-assign-form");
  if (assignForm) {
    assignForm.hidden = !hasPermission("repair_order:assign");
    assignForm.onsubmit = async event => {
      event.preventDefault();
      try {
        await api(`/api/repair-orders/${order.repair_order_id}/assign`, {
          method: "POST",
          body: JSON.stringify(formData(assignForm)),
        });
        showToast("工程师已指派");
        await openOrderModal(machineId);
        await refreshActiveBusinessPool();
      } catch (error) {
        showToast(error.message, true);
      }
    };
  }
  const confirmForm = $("#repair-confirm-form");
  if (confirmForm) {
    confirmForm.hidden = !hasPermission("repair_order:confirm");
    confirmForm.onsubmit = async event => {
      event.preventDefault();
      try {
        await api(`/api/repair-orders/${order.repair_order_id}/confirm-quote`, {
          method: "POST",
          body: JSON.stringify(formData(confirmForm)),
        });
        showToast("客户确认已记录");
        await openOrderModal(machineId);
        await refreshActiveBusinessPool();
      } catch (error) {
        showToast(error.message, true);
      }
    };
  }
  const closeForm = $("#repair-engineer-close-form");
  if (closeForm) {
    closeForm.hidden = !hasPermission("repair_order:engineer_close");
    closeForm.onsubmit = async event => {
      event.preventDefault();
      try {
        await api(`/api/repair-orders/${order.repair_order_id}/engineer-close`, {
          method: "POST",
          body: JSON.stringify(formData(closeForm)),
        });
        showToast("工程师已结单，订单转前台收费");
        await openOrderModal(machineId);
        await refreshActiveBusinessPool();
      } catch (error) {
        showToast(error.message, true);
      }
    };
  }
}

function bindMachineEditForm(machineId) {
  const form = $("#machine-edit-form");
  if (!form) return;
  $("#edit-machine").hidden = !hasPermission("machine:update");
  const sourceSelect = $("#machine-source-type");
  const statusSelect = $("#machine-current-status");
  sourceSelect.addEventListener("change", () => {
    statusSelect.innerHTML = statusOptions(sourceSelect.value, statusSelect.value);
  });
  $("#edit-machine").onclick = () => {
    form.hidden = false;
    $("#machine-info-panel").hidden = true;
    $("#edit-machine").hidden = true;
    $("#save-machine-edit").hidden = false;
    $("#cancel-machine-edit").hidden = false;
    form.querySelector("input, select, textarea")?.focus();
  };
  $("#cancel-machine-edit").onclick = () => {
    form.hidden = true;
    $("#machine-info-panel").hidden = false;
    $("#edit-machine").hidden = !hasPermission("machine:update");
    $("#save-machine-edit").hidden = true;
    $("#cancel-machine-edit").hidden = true;
  };
  form.onsubmit = async event => {
    event.preventDefault();
    const data = formData(form);
    if (data.customer_name) {
      data.customer = {
        name: data.customer_name,
        phone: data.customer_phone || "",
        category: data.customer_category || "个人客户",
      };
    }
    delete data.customer_name;
    delete data.customer_phone;
    delete data.customer_category;
    try {
      const updated = await api(`/api/machines/${machineId}`, {
        method: "PUT",
        body: JSON.stringify(data),
      });
      showToast(`订单已更新：${updated.machine_no}`);
      await openOrderModal(machineId);
      await refreshActiveBusinessPool();
    } catch (error) {
      showToast(error.message, true);
    }
  };
}

function bindMachineNoteForm(machineId) {
  const form = $("#machine-note-form");
  if (!form) return;
  $("#add-note").hidden = !hasPermission("machine:update");
  $("#add-note").onclick = () => {
    form.hidden = false;
    $("#add-note").hidden = true;
    form.querySelector("textarea")?.focus();
  };
  $("#cancel-note").onclick = () => {
    form.reset();
    form.hidden = true;
    $("#add-note").hidden = !hasPermission("machine:update");
  };
  form.onsubmit = async event => {
    event.preventDefault();
    try {
      await api(`/api/machines/${machineId}/notes`, {
        method: "POST",
        body: JSON.stringify(formData(form)),
      });
      showToast("备注已添加");
      await openOrderModal(machineId);
    } catch (error) {
      showToast(error.message, true);
    }
  };
}

function bindPriceChangeForm(machineId) {
  const form = $("#price-change-form");
  const openButton = $("#open-price-change");
  if (!form || !openButton) return;
  const kind = form.dataset.kind;
  const permission = kind === "repair" ? "repair_order:update" : "recycle_order:update";
  openButton.hidden = !hasPermission(permission);
  openButton.onclick = () => {
    form.hidden = false;
    openButton.hidden = true;
    form.querySelector("input")?.focus();
  };
  $("#cancel-price-change").onclick = () => {
    form.reset();
    form.hidden = true;
    openButton.hidden = !hasPermission(permission);
  };
  form.onsubmit = async event => {
    event.preventDefault();
    const data = formData(form);
    const endpoint = kind === "repair"
      ? `/api/repair-orders/${form.dataset.orderId}/price`
      : `/api/recycle-orders/${form.dataset.orderId}/price`;
    try {
      await api(endpoint, {
        method: "POST",
        body: JSON.stringify({ quoted_amount: data.quoted_amount || 0, remark: data.remark || "" }),
      });
      showToast("改价已保存");
      await openOrderModal(machineId);
      await refreshActiveBusinessPool();
    } catch (error) {
      showToast(error.message, true);
    }
  };
}

async function openOrderModal(machineId) {
  const timeline = await api(`/api/machines/${machineId}/timeline`);
  renderOrderModal(timeline);
  $("#order-modal").hidden = false;
  document.body.classList.add("modal-open");
}

function closeOrderModal() {
  $("#order-modal").hidden = true;
  state.currentTimeline = null;
  document.body.classList.remove("modal-open");
}

async function loadInventory() {
  const repairMaterials = await api("/api/materials");
  const recycleRows = await api("/api/inventory");
  $("#inventory-table").innerHTML = `
    <h3>维修物料库存</h3>
    ${table(repairMaterials.materials, [
      ["sku", "SKU"], ["name", "物料"], ["compatible_range", "适配范围"],
      ["current_qty", "库存"], ["avg_cost", "均价"], ["status", "状态"], ["remark", "备注"],
    ], "暂无维修物料库存")}
    <h3>库存流水</h3>
    ${table(repairMaterials.movements, [
      ["happened_at", "时间"], ["sku", "SKU"], ["movement_type", "类型"], ["qty", "数量"],
      ["unit_cost", "单价"], ["order_no", "关联工单"], ["actor", "经手人"], ["note", "备注"],
    ], "暂无物料流水")}
    <h3>回收机器库存</h3>
    ${table(recycleRows, [
      ["inventory_item_id", "库存ID"], ["machine_id", "机器ID"], ["imei", "IMEI"], ["model", "机型"],
      ["status", "库存状态"], ["cost_amount", "成本"], ["sale_price", "销售定价"],
    ], "暂无回收库存")}
  `;
}

function parseIds(value) {
  return String(value || "")
    .split(",")
    .map(x => Number(x.trim()))
    .filter(Boolean);
}

function requestItemsFromForm(data) {
  return [{
    material_id: data.material_id,
    repair_sku_id: data.repair_sku_id,
    qty: data.qty || 1,
    remark: data.remark || "",
  }];
}

async function loadWarehouse() {
  const data = await api("/api/warehouse");
  state.warehouse = data;
  const available = (data.units || []).filter(row => row.current_status === "在库可用").length;
  const issued = (data.units || []).filter(row => row.current_status === "已发放").length;
  $("#warehouse-metrics").innerHTML = [
    ["物料档案", data.materials?.length || 0],
    ["在库可用单件", available],
    ["已发放单件", issued],
    ["低库存预警", data.low_stock?.length || 0],
    ["待验收退料", (data.returns || []).filter(row => row.status === "待验收").length],
  ].map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");

  $("#warehouse-material-table").innerHTML = table(data.materials, [
    ["material_id", "ID"], ["material_code", "物料代码"], ["sku", "SKU"], ["name", "物料"],
    ["category_code", "类别"], ["compatible_range", "适配"], ["spec", "规格"],
    ["current_qty", "可用"], ["min_qty", "低库存"], ["default_location_code", "默认库位"],
  ], "暂无物料档案");
  $("#warehouse-unit-table").innerHTML = table(data.units, [
    ["unit_id", "ID"], ["unit_code", "单件编码"], ["material_code", "物料代码"], ["name", "物料"],
    ["current_status", "状态"], ["location_code", "库位"], ["engineer_user", "工程师"],
    ["repair_order_id", "工单"], ["request_id", "申领单"], ["unit_cost", "成本"],
  ], "暂无单件库存");
  $("#warehouse-batch-table").innerHTML = table(data.batches, [
    ["batch_id", "ID"], ["batch_no", "批次"], ["purchase_type", "类型"], ["material_code", "物料代码"],
    ["name", "物料"], ["supplier", "供应商"], ["qty", "入库"], ["remaining_qty", "批次余量"],
    ["refund_status", "退款"], ["location_code", "库位"], ["purchased_at", "时间"],
  ], "暂无入库批次");
  $("#warehouse-request-table").innerHTML = table(data.requests, [
    ["request_id", "ID"], ["request_no", "申领单"], ["status", "状态"], ["engineer_user", "工程师"],
    ["repair_order_id", "工单"], ["requested_by", "申请人"], ["approved_by", "审核人"],
    ["issued_by", "发放人"], ["created_at", "时间"], ["remark", "备注"],
  ], "暂无申领单");
  $("#warehouse-return-table").innerHTML = table(data.returns, [
    ["return_id", "ID"], ["unit_code", "单件编码"], ["name", "物料"], ["status", "状态"],
    ["return_type", "类型"], ["inspect_result", "验收"], ["engineer_user", "工程师"],
    ["repair_order_id", "工单"], ["inspected_by", "验收人"], ["remark", "备注"],
  ], "暂无退料单");
  $("#warehouse-movement-table").innerHTML = table(data.movements, [
    ["happened_at", "时间"], ["movement_type", "类型"], ["direction", "方向"], ["unit_code", "单件编码"],
    ["material_code", "物料代码"], ["name", "物料"], ["qty", "数量"], ["location_code", "库位"],
    ["order_no", "工单"], ["actor", "操作人"], ["counterparty", "对象"], ["note", "备注"],
  ], "暂无库存流水");
}

async function submitWarehouseForm(formSelector, path, transform = data => data) {
  const form = $(formSelector);
  const payload = transform(formData(form));
  await api(path, { method: "POST", body: JSON.stringify(payload) });
  form.reset();
  await loadWarehouse();
  showToast("仓库单据已保存");
}

async function showRepairMaterialHints() {
  const form = $("#repair-step-form");
  const data = formData(form);
  const skuId = parseIds(data.sku_ids)[0] || data.sku_id;
  const orderId = data.repair_order_id;
  if (!skuId && !orderId) {
    showToast("请先填写维修 SKU ID 或维修单 ID", true);
    return;
  }
  const result = skuId
    ? await api(`/api/repair-skus/${skuId}/material-hints`)
    : await api(`/api/repair-orders/${orderId}/material-hints`);
  const groups = skuId ? [result] : result.hints;
  $("#repair-material-hints").innerHTML = groups.map(group => `
    <div class="hint-group">
      <strong>${escapeHtml(group.repair_sku?.fault_name || "推荐物料")}</strong>
      ${table(group.materials || [], [
        ["material_code", "物料代码"], ["name", "物料"], ["current_qty", "可用库存"],
        ["locations", "库位"], ["pending_issue_qty", "已发放"], ["stock_warning", "提示"],
      ], "暂无绑定物料")}
    </div>
  `).join("");
}

async function loadCustomers() {
  const q = encodeURIComponent($("#customer-keyword").value || "");
  const rows = await api(`/api/customers?q=${q}`);
  $("#customer-table").innerHTML = table(rows, [
    ["customer_id", "ID"], ["name", "姓名"], ["phone", "电话"], ["category", "类别"], ["shop_name", "店铺"], ["tags", "标签"],
  ], "没有找到客户");
}

async function loadPayments() {
  const rows = await api("/api/payments");
  $("#payment-table").innerHTML = table(rows, [
    ["payment_id", "ID"], ["source_type", "来源"], ["source_id", "单据"], ["direction", "方向"],
    ["amount", "金额"], ["method", "方式"], ["transaction_no", "流水号"], ["status", "状态"],
    ["received_by", "收款人"], ["confirmed_by", "确认人"], ["created_at", "时间"],
  ], "暂无流水记录");
}

async function loadReports() {
  const report = await api("/api/machine-reports");
  const income = report.payment_totals.find(x => x.direction === "收入")?.amount || 0;
  const expense = report.payment_totals.find(x => x.direction === "支出")?.amount || 0;
  $("#metrics").innerHTML = [
    ["在售库存", report.inventory_count],
    ["库存成本", report.inventory_cost],
    ["收入流水", income],
    ["支出流水", expense],
  ].map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${formatMetric(label, value)}</strong></div>`).join("");
  $("#report-details").innerHTML = table(report.inventory, [
    ["inventory_item_id", "库存ID"], ["machine_no", "机器编号"], ["imei", "IMEI"], ["model", "机型"],
    ["status", "状态"], ["cost_amount", "成本"], ["sale_price", "销售定价"],
  ], "暂无库存明细");
}

async function loadAudit() {
  const rows = await api("/api/audit-logs");
  $("#audit-table").innerHTML = table(rows, [
    ["time", "时间"], ["username", "用户"], ["role", "角色"], ["action", "动作"],
    ["target_type", "对象"], ["target_id", "ID"], ["result", "结果"],
  ], "暂无操作日志");
}

$("#auth-login-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const payload = formData(event.currentTarget);
    const user = await api("/api/login", { method: "POST", body: JSON.stringify(payload) });
    state.user = user.username;
    localStorage.setItem("mis_user", state.user);
    state.profile = await api("/api/me");
    renderAccount(true);
    setAuthenticated(true);
    showToast("登录成功");
    refresh(document.querySelector(".view.active").id);
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#account-button").addEventListener("click", () => {
  toggleAccountDropdown();
});

$("#show-permissions").addEventListener("click", () => showAccountDetail("permissions"));
$("#show-profile").addEventListener("click", () => showAccountDetail("profile"));
$("#logout-button").addEventListener("click", () => {
  localStorage.removeItem("mis_user");
  state.user = "";
  state.profile = null;
  closeAccountDropdown();
  renderAccount(false);
  showToast("已退出登录");
});

document.addEventListener("click", event => {
  if (!event.target.closest(".account-menu")) {
    closeAccountDropdown();
  }
});

$("#search-repair-orders").addEventListener("click", () => loadBusinessPool("repair"));
$("#repair-keyword").addEventListener("keydown", event => {
  if (event.key === "Enter") loadBusinessPool("repair");
});
$("#repair-status").addEventListener("change", () => loadBusinessPool("repair"));
$("#repair-payment-status").addEventListener("change", () => loadBusinessPool("repair"));
$("#repair-customer-type").addEventListener("change", () => loadBusinessPool("repair"));
$("#repair-missing-only").addEventListener("change", () => loadBusinessPool("repair"));
$("#repair-date-from").addEventListener("change", () => loadBusinessPool("repair"));
$("#repair-date-to").addEventListener("change", () => loadBusinessPool("repair"));
$("#reset-repair-filters").addEventListener("click", () => resetBusinessPoolFilters("repair"));
$("#open-repair-tab").addEventListener("click", () => openOrderFormPage("repair"));

$("#search-recycle-orders").addEventListener("click", () => loadBusinessPool("recycle"));
$("#recycle-keyword").addEventListener("keydown", event => {
  if (event.key === "Enter") loadBusinessPool("recycle");
});
$("#recycle-status").addEventListener("change", () => loadBusinessPool("recycle"));
$("#reset-recycle-filters").addEventListener("click", () => resetBusinessPoolFilters("recycle"));
$("#open-recycle-tab").addEventListener("click", () => openOrderFormPage("recycle"));
$("#search-customers").addEventListener("click", loadCustomers);

document.querySelectorAll("[data-close-modal]").forEach(node => {
  node.addEventListener("click", closeOrderModal);
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && $("#account-dropdown").classList.contains("open")) closeAccountDropdown();
  if (event.key === "Escape" && !$("#order-modal").hidden) closeOrderModal();
});

$("#repair-open-form").addEventListener("submit", async event => {
  event.preventDefault();
  const data = formData(event.currentTarget);
  const payload = {
    machine_id: data.machine_id || null,
    machine: data.machine_id ? null : machinePayload(data),
    customer: customerPayload(data),
    fault_description: data.fault_description || "",
  };
  try {
    const order = await api("/api/repair-orders", { method: "POST", body: JSON.stringify(payload) });
    showToast(`维修单已创建：${order.repair_order_id}`);
    event.currentTarget.reset();
    $("#repair-step-form [name='repair_order_id']").value = order.repair_order_id;
    await loadBusinessPool("repair");
  } catch (error) {
    showToast(error.message, true);
  }
});

async function updateRepairOrderStatus(status, remark = "") {
  const data = formData($("#repair-step-form"));
  await api(`/api/repair-orders/${data.repair_order_id}/status`, {
    method: "POST",
    body: JSON.stringify({ status, remark }),
  });
}

$("#start-repair-diagnosis").addEventListener("click", async () => {
  try {
    await updateRepairOrderStatus("检测中");
    showToast("维修单已进入检测中");
    await loadBusinessPool("repair");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#quote-repair").addEventListener("click", async () => {
  const data = formData($("#repair-step-form"));
  try {
    await api(`/api/repair-orders/${data.repair_order_id}/quote`, {
      method: "POST",
      body: JSON.stringify({
        diagnosis: data.diagnosis,
        fault_detail: data.fault_detail || "",
        repair_solution: data.repair_solution || "",
        sku_ids: String(data.sku_ids || "").split(",").map(x => Number(x.trim())).filter(Boolean),
        quoted_amount: data.quoted_amount || 0,
      }),
    });
    showToast("维修报价已记录");
    await loadBusinessPool("repair");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#add-repair-item").addEventListener("click", async () => {
  const data = formData($("#repair-step-form"));
  try {
    await api(`/api/repair-orders/${data.repair_order_id}/items`, {
      method: "POST",
      body: JSON.stringify({
        sku_id: data.sku_id || null,
        item_name: data.item_name,
        quantity: data.quantity || 1,
        cost_amount: data.cost_amount || 0,
        charge_amount: data.charge_amount || 0,
      }),
    });
    showToast("维修项目已记录");
    await loadBusinessPool("repair");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#ready-repair").addEventListener("click", async () => {
  try {
    await updateRepairOrderStatus("待交付");
    showToast("维修单已进入待交付");
    await loadBusinessPool("repair");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#engineer-close-repair").addEventListener("click", async () => {
  const data = formData($("#repair-step-form"));
  try {
    await api(`/api/repair-orders/${data.repair_order_id}/engineer-close`, {
      method: "POST",
      body: JSON.stringify({ remark: data.delivery_check || "" }),
    });
    showToast("工程师已结单");
    await loadBusinessPool("repair");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#deliver-repair").addEventListener("click", async () => {
  const data = formData($("#repair-step-form"));
  try {
    await api(`/api/repair-orders/${data.repair_order_id}/deliver`, {
      method: "POST",
      body: JSON.stringify({ delivery_check: data.delivery_check, remark: "" }),
    });
    showToast("交付检测已记录");
    await loadBusinessPool("repair");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#go-repair-payment").addEventListener("click", () => {
  const data = formData($("#repair-step-form"));
  setView("payments");
  $("#payment-form [name='source_type']").value = "repair";
  $("#payment-form [name='source_id']").value = data.repair_order_id || "";
  $("#payment-form [name='direction']").value = "收入";
  $("#payment-form [name='amount']").focus();
});

$("#recycle-open-form").addEventListener("submit", async event => {
  event.preventDefault();
  const data = formData(event.currentTarget);
  const payload = {
    machine_id: data.machine_id || null,
    machine: data.machine_id ? null : machinePayload(data),
    customer: customerPayload(data),
    inspection_note: data.inspection_note || "",
  };
  try {
    const order = await api("/api/recycle-orders", { method: "POST", body: JSON.stringify(payload) });
    showToast(`回收单已创建：${order.recycle_order_id}`);
    event.currentTarget.reset();
    $("#recycle-step-form [name='recycle_order_id']").value = order.recycle_order_id;
    await loadBusinessPool("recycle");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#quote-recycle").addEventListener("click", async () => {
  const data = formData($("#recycle-step-form"));
  try {
    await api(`/api/recycle-orders/${data.recycle_order_id}/quote`, {
      method: "POST",
      body: JSON.stringify({ inspection_result: data.inspection_result, quoted_amount: data.quoted_amount || 0 }),
    });
    showToast("回收报价已记录");
    await loadBusinessPool("recycle");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#stock-in-recycle").addEventListener("click", async () => {
  const data = formData($("#recycle-step-form"));
  try {
    await api(`/api/recycle-orders/${data.recycle_order_id}/stock-in`, {
      method: "POST",
      body: JSON.stringify({ pay_amount: data.pay_amount || 0, sale_price: data.sale_price || 0 }),
    });
    showToast("已付款入库");
    await loadBusinessPool("recycle");
    await loadInventory();
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#sales-form").addEventListener("submit", async event => {
  event.preventDefault();
  const data = formData(event.currentTarget);
  const payload = {
    inventory_item_id: data.inventory_item_id,
    customer: customerPayload(data),
    sale_price: data.sale_price,
    salesperson: data.salesperson,
    remark: data.remark || "",
  };
  try {
    const order = await api("/api/sales-orders", { method: "POST", body: JSON.stringify(payload) });
    showToast(`销售单已创建：${order.sales_order_id}`);
    event.currentTarget.reset();
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#payment-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await api("/api/payments", { method: "POST", body: JSON.stringify(formData(event.currentTarget)) });
    showToast("流水已登记");
    event.currentTarget.reset();
    await loadPayments();
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#refresh-warehouse").addEventListener("click", loadWarehouse);

$("#warehouse-category-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await submitWarehouseForm("#warehouse-category-form", "/api/material-categories");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#warehouse-location-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const data = formData(event.currentTarget);
    if (!data.area_id) {
      const area = await api("/api/warehouse/areas", {
        method: "POST",
        body: JSON.stringify({ name: "默认库区", area_code: "AREA-DEFAULT" }),
      });
      data.area_id = area.area_id;
    }
    await api("/api/warehouse/locations", { method: "POST", body: JSON.stringify(data) });
    event.currentTarget.reset();
    await loadWarehouse();
    showToast("库位已保存");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#warehouse-material-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await submitWarehouseForm("#warehouse-material-form", "/api/materials");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#warehouse-batch-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const data = formData(event.currentTarget);
    const kind = data.batch_kind || "purchase";
    delete data.batch_kind;
    await api(`/api/material-batches/${kind}`, { method: "POST", body: JSON.stringify(data) });
    event.currentTarget.reset();
    await loadWarehouse();
    showToast("入库批次已生成");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#warehouse-request-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const data = formData(event.currentTarget);
    const payload = {
      repair_order_id: data.repair_order_id || null,
      engineer_user: data.engineer_user || "",
      items: requestItemsFromForm(data),
      remark: data.remark || "",
    };
    await api("/api/material-requests", { method: "POST", body: JSON.stringify(payload) });
    event.currentTarget.reset();
    await loadWarehouse();
    showToast("申领单已创建");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#approve-material-request").addEventListener("click", async () => {
  try {
    const data = formData($("#warehouse-request-form"));
    await api(`/api/material-requests/${data.request_id}/approve`, { method: "POST", body: JSON.stringify({ remark: data.remark || "" }) });
    await loadWarehouse();
    showToast("申领单已审核");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#issue-material-request").addEventListener("click", async () => {
  try {
    const data = formData($("#warehouse-request-form"));
    await api(`/api/material-requests/${data.request_id}/issue`, {
      method: "POST",
      body: JSON.stringify({ unit_ids: parseIds(data.unit_ids), remark: data.remark || "" }),
    });
    await loadWarehouse();
    showToast("物料已发放");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#return-material-batch").addEventListener("click", async () => {
  try {
    const data = formData($("#warehouse-return-form"));
    await api(`/api/material-batches/${data.batch_id}/return`, {
      method: "POST",
      body: JSON.stringify({
        unit_ids: parseIds(data.return_unit_ids),
        refund_status: data.refund_status || "待确认",
        remark: data.remark || "",
      }),
    });
    await loadWarehouse();
    showToast("采购退货已登记");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#request-material-return").addEventListener("click", async () => {
  try {
    const data = formData($("#warehouse-return-form"));
    await api(`/api/material-issues/${data.unit_id}/return-request`, {
      method: "POST",
      body: JSON.stringify({ remark: data.remark || "" }),
    });
    await loadWarehouse();
    showToast("退料已提交待验收");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#inspect-material-return").addEventListener("click", async () => {
  try {
    const data = formData($("#warehouse-return-form"));
    await api(`/api/material-returns/${data.return_id}/inspect`, {
      method: "POST",
      body: JSON.stringify({ inspect_result: data.inspect_result, remark: data.remark || "" }),
    });
    await loadWarehouse();
    showToast("退料验收已完成");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#create-stock-adjustment").addEventListener("click", async () => {
  try {
    const data = formData($("#warehouse-return-form"));
    await api("/api/stock-adjustments", {
      method: "POST",
      body: JSON.stringify({
        material_id: data.adjust_material_id,
        qty: data.adjust_qty || 1,
        adjustment_type: data.adjustment_type,
        reason: data.remark || "待补",
      }),
    });
    await loadWarehouse();
    showToast("库存调整已生成");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#warehouse-binding-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await submitWarehouseForm("#warehouse-binding-form", "/api/repair-fault-materials");
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#show-repair-material-hints").addEventListener("click", async () => {
  try {
    await showRepairMaterialHints();
  } catch (error) {
    showToast(error.message, true);
  }
});

document.querySelectorAll("nav button").forEach(button => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

setView(initialView());
setAuthenticated(Boolean(state.user));
loadProfile();
