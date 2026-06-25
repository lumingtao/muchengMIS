import { describe, expect, it } from "vitest";
import { compactPageItems, firstText, isRepairPoolRowInDateRange, maskCode, maskPhone, repairBillHeaders, repairMonthlySummaryValues, repairPoolColumnOrder, repairPoolDateDisplay, repairPoolDateValue, splitHonorificName, toRepairBillExportRow } from "./App";

describe("repair pool helpers", () => {
  it("builds compact pagination items around the current page", () => {
    expect(compactPageItems(1, 3)).toEqual([1, 2, 3]);
    expect(compactPageItems(5, 10)).toEqual([1, "ellipsis", 4, 5, 6, "ellipsis", 10]);
  });

  it("keeps missing phone and imei values blank for table display", () => {
    expect(maskPhone("")).toBe("-");
    expect(maskCode("")).toBe("-");
  });

  it("masks real phone and imei values without fabricating defaults", () => {
    expect(maskPhone("13812345678")).toBe("138****5678");
    expect(maskCode("359239123456447")).toBe("359239******447");
  });

  it("normalizes stored customer names with honorific suffixes for detail display", () => {
    expect(splitHonorificName("徐娜静498女士", "女")).toEqual({ name: "徐娜静498", honorific: "女士" });
    expect(splitHonorificName("张三先生")).toEqual({ name: "张三", honorific: "先生" });
    expect(splitHonorificName("李四", "男")).toEqual({ name: "李四", honorific: "先生" });
  });

  it("keeps missing detail fields blank instead of fabricating demo values", () => {
    expect(firstText("", null, undefined)).toBe("");
    expect(firstText("", "869123456789012")).toBe("869123456789012");
    expect(firstText("")).toBe("");
  });

  it("uses the dedicated repair monthly summary rather than payment-list totals", () => {
    expect(repairMonthlySummaryValues({ confirmed_revenue: 680, net_profit: 255 })).toEqual({ revenue: 680, netProfit: 255 });
    expect(repairMonthlySummaryValues(undefined)).toEqual({ revenue: 0, netProfit: 0 });
  });

  it("keeps the repair pool business columns in the requested reading order", () => {
    expect(repairPoolColumnOrder).toEqual(["订单编号", "下单时间", "设备信息", "客户信息", "维修前检测", "故障名称", "价格", "订单状态", "最后更新", "工程师", "操作"]);
  });

  it("filters repair pool rows by an inclusive created date range", () => {
    expect(isRepairPoolRowInDateRange({ created_at: "2026-06-01 09:00:00" }, ["2026-06-01", "2026-06-10"])).toBe(true);
    expect(isRepairPoolRowInDateRange({ created_at: "2026-06-10 23:59:59" }, ["2026-06-01", "2026-06-10"])).toBe(true);
    expect(isRepairPoolRowInDateRange({ created_at: "2026-05-31 23:59:59" }, ["2026-06-01", "2026-06-10"])).toBe(false);
    expect(isRepairPoolRowInDateRange({ created_at: "2026-06-11 00:00:00" }, ["2026-06-01", "2026-06-10"])).toBe(false);
    expect(isRepairPoolRowInDateRange({ created_at: "2026-01-01 00:00:00" }, ["", ""])).toBe(true);
  });

  it("filters repair pool rows by repair completion dates when requested", () => {
    expect(repairPoolDateValue({ created_at: "2026-06-01 09:00:00", completed_at: "2026-06-24 12:00:00" }, "created")).toBe("2026-06-01");
    expect(repairPoolDateValue({ created_at: "2026-06-01 09:00:00", completed_at: "2026-06-24 12:00:00" }, "completed")).toBe("2026-06-24");
    expect(isRepairPoolRowInDateRange({ created_at: "2026-06-01 09:00:00", completed_at: "2026-06-24 12:00:00" }, ["2026-06-24", "2026-06-24"], "completed")).toBe(true);
    expect(isRepairPoolRowInDateRange({ created_at: "2026-06-24 09:00:00", completed_at: "" }, ["2026-06-24", "2026-06-24"], "completed")).toBe(false);
    expect(isRepairPoolRowInDateRange({ updated_at: "2026-06-24 12:00:00", status: "维修中" }, ["2026-06-24", "2026-06-24"], "completed")).toBe(false);
  });

  it("keeps the date range independent from the selected repair pool date basis", () => {
    const row = { created_at: "2026-06-01 09:00:00", completed_at: "2026-06-24 12:00:00", status: "已完结" };
    expect(isRepairPoolRowInDateRange(row, ["2026-06-01", "2026-06-01"], "created")).toBe(true);
    expect(isRepairPoolRowInDateRange(row, ["2026-06-01", "2026-06-01"], "completed")).toBe(false);
    expect(isRepairPoolRowInDateRange(row, ["2026-06-24", "2026-06-24"], "created")).toBe(false);
    expect(isRepairPoolRowInDateRange(row, ["2026-06-24", "2026-06-24"], "completed")).toBe(true);
  });

  it("shows repair pool table timestamps as date-only values", () => {
    expect(repairPoolDateDisplay("2026-06-24 08:56:37")).toBe("2026-06-24");
    expect(repairPoolDateDisplay("")).toBe("--");
  });

  it("maps filtered repair pool rows to the repair bill template columns", () => {
    expect(repairBillHeaders).toEqual(["ID", "机型", "时间", "串号", "顾客", "备注", "解决方案", "工程师", "配件1", "付款方式", "图片", "故障", "配件来源", "配件2", "配件3", "报价", "成本", "利润"]);
    expect(toRepairBillExportRow({
      order_no: "WX20260614-0001",
      model: "iPhone 15",
      created_at: "2026-06-14 12:00:00",
      imei: "860000000000001",
      customer_name: "张三",
      remark: "加急",
      repair_solution: "更换电池",
      assigned_to: "engineer",
      export_parts: "电池||防水胶||屏幕",
      export_payment_method: "微信",
      fault_description: "待机短",
      export_part_sources: "库存||临采",
      quoted_amount: 180,
      export_cost_amount: 80,
      export_profit_amount: 100,
    })).toEqual([
      "WX20260614-0001",
      "iPhone 15",
      "2026-06-14 12:00:00",
      "860000000000001",
      "张三",
      "加急",
      "更换电池",
      "engineer",
      "电池",
      "微信",
      "",
      "待机短",
      "库存、临采",
      "防水胶",
      "屏幕",
      180,
      80,
      100,
    ]);
  });

  it("keeps unmatched repair bill template columns blank", () => {
    expect(toRepairBillExportRow({ repair_order_id: 12, model: "iPhone" })).toEqual([
      12,
      "iPhone",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
    ]);
  });
});
