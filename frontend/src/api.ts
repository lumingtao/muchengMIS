export type AnyRecord = Record<string, unknown>;

const USER_KEY = "mis_user";

export function getStoredUser() {
  return localStorage.getItem(USER_KEY) || "";
}

export function setStoredUser(username: string) {
  localStorage.setItem(USER_KEY, username);
}

export function clearStoredUser() {
  localStorage.removeItem(USER_KEY);
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!response.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? String(data.detail) : "请求失败";
    throw new Error(detail === "请求失败" && typeof data === "string" && data.trim() ? data.trim() : detail);
  }
  return data as T;
}

export function formPayload(form: HTMLFormElement) {
  const out: AnyRecord = {};
  new FormData(form).forEach((value, key) => {
    if (value === "") return;
    const text = String(value);
    out[key] = /^-?\d+(\.\d+)?$/.test(text) && key.endsWith("_id") || ["amount", "qty", "quantity", "unit_cost", "cost_amount", "charge_amount", "sale_price", "quoted_amount", "pay_amount"].includes(key)
      ? Number(text)
      : text;
  });
  return out;
}
