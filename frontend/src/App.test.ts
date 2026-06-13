import { describe, expect, it } from "vitest";
import { compactPageItems, maskCode, maskPhone } from "./App";

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
});
