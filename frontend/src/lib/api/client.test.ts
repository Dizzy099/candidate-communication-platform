import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, errorMessage } from "./client";

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("returns parsed JSON on success and sends JSON bodies", async () => {
    mockFetch(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await expect(apiFetch("/x", { method: "POST", json: { a: 1 } })).resolves.toEqual({ ok: true });
    const [url, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/x");
    expect(init.body).toBe('{"a":1}');
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("surfaces the API's friendly message and field errors", async () => {
    mockFetch(
      async () =>
        new Response(
          JSON.stringify({ error: { code: "validation_error", message: "Please correct the highlighted fields.", fields: { phone: "Bad number" } } }),
          { status: 400 },
        ),
    );
    const error = await apiFetch("/x").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("validation_error");
    expect(error.fields).toEqual({ phone: "Bad number" });
  });

  it("never shows raw proxy pages: falls back to a generic message", async () => {
    mockFetch(async () => new Response("<html>Bad Gateway</html>", { status: 502 }));
    const error = await apiFetch("/x").catch((e) => e);
    expect(errorMessage(error)).toBe("The server is temporarily unreachable. Please try again shortly.");
  });

  it("explains network failures", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const error = await apiFetch("/x").catch((e) => e);
    expect(error.code).toBe("network_error");
    expect(error.message).toMatch(/Can't reach the server/);
  });

  it("handles 204 No Content", async () => {
    mockFetch(async () => new Response(null, { status: 204 }));
    await expect(apiFetch("/x", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
