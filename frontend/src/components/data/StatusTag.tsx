import { Tag } from "antd";

type StatusTone = "success" | "processing" | "warning" | "error" | "default";

const doneStatuses = new Set(["已交付", "已完结", "已结单", "成功", "财务已确认", "已售出", "已完成", "客户已确认", "质检通过"]);
const pendingStatuses = new Set(["维修中", "待检测", "待报价确认", "待交付检测", "检测中", "已报价", "待分配", "待备料", "待维修", "待质检", "待收费", "部分收款"]);
const warningStatuses = new Set(["同行挂账", "财务待确认", "未收款", "待支付", "已收款待确认"]);
const successStatuses = new Set(["回收库存", "在库可用", "启用"]);
const errorStatuses = new Set(["已取消", "取消", "失败", "异常", "质检不通过"]);

export function statusTone(input: unknown): StatusTone {
  const text = String(input || "");
  if (doneStatuses.has(text) || successStatuses.has(text)) return "success";
  if (pendingStatuses.has(text)) return "processing";
  if (warningStatuses.has(text)) return "warning";
  if (errorStatuses.has(text)) return "error";
  return "default";
}

export function StatusTag({ value }: { value: unknown }) {
  const text = String(value || "-");
  return <Tag color={statusTone(text)}>{text}</Tag>;
}
