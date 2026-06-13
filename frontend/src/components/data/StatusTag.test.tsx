import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { statusTone, StatusTag } from "./StatusTag";

describe("StatusTag", () => {
  it("maps known business statuses to Ant Design tag tones", () => {
    expect(statusTone("已完成")).toBe("success");
    expect(statusTone("启用")).toBe("success");
    expect(statusTone("维修中")).toBe("processing");
    expect(statusTone("待质检")).toBe("processing");
    expect(statusTone("质检通过")).toBe("success");
    expect(statusTone("质检不通过")).toBe("error");
    expect(statusTone("财务待确认")).toBe("warning");
    expect(statusTone("已取消")).toBe("error");
    expect(statusTone("停用")).toBe("default");
  });

  it("renders the status text", () => {
    render(<StatusTag value="维修中" />);
    expect(screen.getByText("维修中")).toBeInTheDocument();
  });
});
