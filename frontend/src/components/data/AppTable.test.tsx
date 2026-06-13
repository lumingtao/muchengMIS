import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AppTable } from "./AppTable";

describe("AppTable", () => {
  const columns: Array<[string, string]> = [["order_no", "订单编号"], ["status", "状态"]];
  const formatValue = (row: Record<string, unknown>, key: string) => String(row[key] ?? "-");
  const isStatusKey = (key: string) => key === "status";

  it("renders rows and status tags", () => {
    render(
      <AppTable
        columns={columns}
        formatValue={formatValue}
        isStatusKey={isStatusKey}
        rows={[{ repair_order_id: 1, order_no: "RO-1", status: "维修中" }]}
      />
    );

    expect(screen.getAllByText("RO-1").length).toBeGreaterThan(0);
    expect(screen.getByText("维修中")).toBeInTheDocument();
    expect(document.querySelector(".ant-tag")).not.toBeNull();
  });

  it("calls onRowClick when a row is selected", async () => {
    const onRowClick = vi.fn();
    const { container } = render(
      <AppTable
        columns={columns}
        formatValue={formatValue}
        isStatusKey={isStatusKey}
        rows={[{ repair_order_id: 1, order_no: "RO-1", status: "维修中" }]}
        onRowClick={onRowClick}
      />
    );

    const row = container.querySelector("tbody tr.clickable");
    expect(row).not.toBeNull();
    await userEvent.click(row as HTMLElement);
    expect(onRowClick).toHaveBeenCalledWith(expect.objectContaining({ order_no: "RO-1" }));
  });

  it("renders action column controls", async () => {
    const onEdit = vi.fn();
    render(
      <AppTable
        actions={{ render: (row) => <button type="button" onClick={() => onEdit(row)}>编辑</button> }}
        columns={columns}
        formatValue={formatValue}
        isStatusKey={isStatusKey}
        rows={[{ repair_order_id: 1, order_no: "RO-1", status: "维修中" }]}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "编辑" }));
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ order_no: "RO-1" }));
  });

  it("renders custom column values", () => {
    render(
      <AppTable
        columns={[["amount", "金额"]]}
        formatValue={formatValue}
        isStatusKey={isStatusKey}
        renderers={{ amount: (row, index) => <strong>{`${index + 1}:${row.amount}`}</strong> }}
        rows={[{ repair_order_id: 1, amount: 128 }]}
      />
    );

    expect(screen.getByText("1:128")).toBeInTheDocument();
  });

  it("renders the empty text", () => {
    render(
      <AppTable
        columns={columns}
        empty="没有找到数据"
        formatValue={formatValue}
        isStatusKey={isStatusKey}
        rows={[]}
      />
    );

    expect(screen.getByText("没有找到数据")).toBeInTheDocument();
  });
});
