import { Empty, Table, type TableColumnsType } from "antd";
import type { ReactNode } from "react";
import type { AnyRecord } from "../../api";
import { StatusTag } from "./StatusTag";

type SortState = { key: string; direction: "asc" | "desc" };

type AppTableProps = {
  rows?: AnyRecord[];
  columns: Array<[string, string]>;
  actions?: {
    title?: string;
    render: (row: AnyRecord, index: number) => ReactNode;
  };
  empty?: string;
  onRowClick?: (row: AnyRecord) => void;
  defaultSort?: SortState;
  formatValue: (row: AnyRecord, key: string) => string;
  isStatusKey: (key: string) => boolean;
  renderers?: Record<string, (row: AnyRecord, index: number) => ReactNode>;
};

function compareValues(a: unknown, b: unknown) {
  const an = Number(a);
  const bn = Number(b);
  if (!Number.isNaN(an) && !Number.isNaN(bn)) return an - bn;
  return String(a ?? "").localeCompare(String(b ?? ""), "zh-CN", {
    numeric: true,
    sensitivity: "base",
  });
}

function rowKey(row: AnyRecord) {
  return String(
      row.id ??
      row.employee_id ??
      row.device_model_id ??
      row.sku_id ??
      row.repair_item_id ??
      row.cost_item_id ??
      row.machine_id ??
      row.repair_order_id ??
      row.recycle_order_id ??
      row.inventory_item_id ??
      row.material_id ??
      row.request_id ??
      row.payment_id ??
      row.customer_id ??
      row.unit_id ??
      row.order_no ??
      row.machine_no ??
      JSON.stringify(row) ??
      ""
  );
}

export function AppTable({
  actions,
  rows,
  columns,
  empty = "暂无数据",
  onRowClick,
  defaultSort,
  formatValue,
  isStatusKey,
  renderers,
}: AppTableProps) {
  const tableColumns: TableColumnsType<AnyRecord> = columns.map(([key, label]) => ({
    title: label,
    dataIndex: key,
    key,
    sorter: (a, b) => compareValues(a[key], b[key]),
    defaultSortOrder: defaultSort?.key === key ? (defaultSort.direction === "asc" ? "ascend" : "descend") : undefined,
    render: (_value, row, index) => {
      if (renderers?.[key]) return renderers[key](row, index);
      const cell = formatValue(row, key);
      return isStatusKey(key) ? <StatusTag value={cell} /> : cell;
    },
  }));

  if (actions) {
    tableColumns.push({
      title: actions.title || "操作",
      key: "actions",
      align: "right",
      fixed: "right",
      render: (_value, row, index) => actions.render(row, index),
    });
  }

  return (
    <Table
      className="app-table"
      columns={tableColumns}
      dataSource={rows || []}
      locale={{ emptyText: <Empty description={empty} /> }}
      pagination={false}
      rowClassName={onRowClick ? "clickable" : ""}
      rowKey={(row) => rowKey(row)}
      scroll={{ x: "max-content" }}
      size="small"
      onRow={(row) => ({
        onClick: () => onRowClick?.(row),
      })}
    />
  );
}
