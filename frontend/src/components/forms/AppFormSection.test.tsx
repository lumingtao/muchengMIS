import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AppFormSection } from "./AppFormSection";

describe("AppFormSection", () => {
  it("submits Ant Design form values with configured defaults", async () => {
    const onSubmit = vi.fn();

    render(
      <AppFormSection
        fields={[
          { name: "source_type", label: "来源", initialValue: "repair", options: [{ value: "repair", label: "维修单" }] },
          { name: "source_id", label: "单据 ID", required: true, type: "number" },
          { name: "direction", label: "方向", initialValue: "收入", options: [{ value: "收入", label: "收入" }] },
          { name: "amount", label: "金额", required: true, step: "0.01", type: "number" },
        ]}
        onSubmit={onSubmit}
        title="登记收支流水"
      />
    );

    await userEvent.type(screen.getByLabelText("单据 ID"), "12");
    await userEvent.type(screen.getByLabelText("金额"), "20.5");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        amount: "20.5",
        direction: "收入",
        source_id: "12",
        source_type: "repair",
      }),
      expect.objectContaining({ reset: expect.any(Function) })
    );
  });
});
