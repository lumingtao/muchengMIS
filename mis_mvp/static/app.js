const defaultPoolSort = {
  repair: { key: "machine_id", direction: "desc" },
  recycle: { key: "machine_id", direction: "desc" },
};

const state = {
  user: localStorage.getItem("mis_user") || "",
  profile: null,
  currentTimeline: null,
  poolSort: {
    repair: { ...defaultPoolSort.repair },
    recycle: { ...defaultPoolSort.recycle },
  },
};

const titles = {
  repairPool: ["维修订单池", "集中查看维修机器、状态和待处理动作。"],
  recyclePool: ["回收订单池", "集中查看回收机器、入库和销售流转。"],
  repair: ["维修开单", "机器到店、检测报价、维修项目、交付检测。"],
  recycle: ["回收开单", "机器到店、验机报价、付款入库、销售定价。"],
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
    "pay_amount", "sale_price", "amount",
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

const moneyKeys = new Set(["quoted_amount", "cost_amount", "charge_amount", "paid_amount", "pay_amount", "sale_price", "amount", "inventory_cost"]);
const idKeys = new Set(["machine_id", "customer_id", "repair_order_id", "recycle_order_id", "inventory_item_id", "sales_order_id", "payment_id", "source_id", "target_id"]);
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
        ["repair_order_id", "维修单"], ["status", "状态"], ["fault_description", "故障"], ["diagnosis", "检测"], ["quoted_amount", "报价"]
      ])}
      ${order ? '<div class="section-action-row"><button type="button" id="open-price-change" class="ghost-button">改价</button></div>' : ""}
    `);
    if (timeline.repair_items?.length) {
      sections.push(`
        <h3>维修项目</h3>
        ${detailTable(timeline.repair_items, [
          ["repair_item_id", "项目ID"], ["repair_order_id", "维修单"], ["item_name", "项目"], ["quantity", "数量"], ["cost_amount", "成本"], ["charge_amount", "收费"]
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
  const sort = state.poolSort[kind];
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

function resetBusinessPoolFilters(kind) {
  const config = poolConfig(kind);
  $(config.keyword).value = "";
  $(config.status).value = "";
  state.poolSort[kind] = { ...defaultPoolSort[kind] };
  loadBusinessPool(kind);
}

async function loadBusinessPool(kind) {
  const config = poolConfig(kind);
  const q = encodeURIComponent($(config.keyword).value || "");
  const rows = await api(`/api/machines?q=${q}`);
  const filtered = sortedRows(applyBusinessPoolFilters(rows, kind), kind);
  const columns = [
    ["machine_no", "机器编号"], ["imei", "IMEI"], ["model", "机型"],
    ["customer_name", "客户"], ["current_status", "当前状态"],
    ["updated_at", "更新时间"],
  ];
  $(config.table).innerHTML = table(filtered, columns, config.empty, { sortable: true, sort: state.poolSort[kind] });
  bindPoolSort(kind);
  bindOrderRows(filtered, config.table);
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
  const rows = await api("/api/inventory");
  $("#inventory-table").innerHTML = table(rows, [
    ["inventory_item_id", "库存ID"], ["machine_id", "机器ID"], ["imei", "IMEI"], ["model", "机型"],
    ["status", "库存状态"], ["cost_amount", "成本"], ["sale_price", "销售定价"],
  ], "暂无回收库存");
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
    ["amount", "金额"], ["method", "方式"], ["operator", "操作人"], ["created_at", "时间"],
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
      body: JSON.stringify({ diagnosis: data.diagnosis, quoted_amount: data.quoted_amount || 0 }),
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

document.querySelectorAll("nav button").forEach(button => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

setView(initialView());
setAuthenticated(Boolean(state.user));
loadProfile();
