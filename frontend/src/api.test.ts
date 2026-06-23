import { describe, expect, it, vi, beforeEach } from "vitest";
import { api } from "./api";

describe("api", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("uses same-origin credentials and parses JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api<{ ok: boolean }>("/api/me")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith("/api/me", expect.objectContaining({
      headers: expect.any(Headers),
      credentials: "same-origin",
    }));
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("X-User")).toBeNull();
  });

  it("throws backend detail messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "没有权限" }), { status: 403 })));
    await expect(api("/api/secure")).rejects.toThrow("没有权限");
  });

  it("throws plain text error responses without JSON parse failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Internal Server Error", { status: 500 })));
    await expect(api("/api/broken")).rejects.toThrow("Internal Server Error");
  });
});
