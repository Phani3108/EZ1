/**
 * API Client — Unit Tests
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createClient, ApiError } from "../src/client";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function makeResponse(status: number, body: unknown) {
  return {
    status,
    json: () => Promise.resolve(body),
  };
}

describe("createClient", () => {
  let client: ReturnType<typeof createClient>;

  beforeEach(() => {
    vi.clearAllMocks();
    client = createClient({
      baseUrl: "http://localhost:8000",
      getAccessToken: () => "test-token",
    });
  });

  it("sends GET with auth header, X-Request-Id, and credentials", async () => {
    mockFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: [{ id: "1" }],
        meta: { request_id: "abc", timestamp: "2026-01-01T00:00:00Z" },
      })
    );

    const result = await client.get("/api/v1/students");
    expect(result.data).toEqual([{ id: "1" }]);

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/v1/students");
    expect(opts.headers["Authorization"]).toBe("Bearer test-token");
    expect(opts.headers["X-Request-Id"]).toBeDefined();
    expect(opts.method).toBe("GET");
    expect(opts.credentials).toBe("include");
  });

  it("sends POST with JSON body", async () => {
    mockFetch.mockResolvedValueOnce(
      makeResponse(201, {
        data: { id: "new-1", name: "Test" },
        meta: { request_id: "abc", timestamp: "2026-01-01T00:00:00Z" },
      })
    );

    const result = await client.post("/api/v1/students", { name: "Test" });
    expect(result.data.id).toBe("new-1");

    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ name: "Test" });
  });

  it("throws ApiError on error envelope", async () => {
    mockFetch.mockResolvedValueOnce(
      makeResponse(400, {
        error: {
          code: "BAD_REQUEST",
          message: "Invalid data",
          details: { field: "email" },
          request_id: "err-123",
        },
      })
    );

    try {
      await client.get("/api/v1/students");
      expect.unreachable("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const err = e as ApiError;
      expect(err.code).toBe("BAD_REQUEST");
      expect(err.status).toBe(400);
      expect(err.details).toEqual({ field: "email" });
      expect(err.requestId).toBe("err-123");
    }
  });

  it("appends query params", async () => {
    mockFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: [],
        meta: { request_id: "q", timestamp: "2026-01-01T00:00:00Z" },
      })
    );

    await client.get("/api/v1/students", { page: "2", search: "moyo" });

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("page=2");
    expect(url).toContain("search=moyo");
  });

  it("attempts token refresh on 401", async () => {
    const refreshed = createClient({
      baseUrl: "http://localhost:8000",
      getAccessToken: () => "expired-token",
      onTokenExpired: async () => "new-token",
    });

    // First call → 401
    mockFetch.mockResolvedValueOnce(
      makeResponse(401, {
        error: {
          code: "UNAUTHORIZED",
          message: "Token expired",
          details: {},
          request_id: "r1",
        },
      })
    );
    // Retry after refresh → 200
    mockFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: { id: "1" },
        meta: { request_id: "r2", timestamp: "2026-01-01T00:00:00Z" },
      })
    );

    const result = await refreshed.get<{ id: string }>("/api/v1/students");
    expect(result.data.id).toBe("1");
    expect(mockFetch).toHaveBeenCalledTimes(2);

    // Second call should have new token
    const [, retryOpts] = mockFetch.mock.calls[1];
    expect(retryOpts.headers["Authorization"]).toBe("Bearer new-token");
  });

  it("calls onAuthError when refresh fails", async () => {
    const onAuthError = vi.fn();
    const failClient = createClient({
      baseUrl: "http://localhost:8000",
      getAccessToken: () => "bad-token",
      onAuthError,
    });

    mockFetch.mockResolvedValueOnce(
      makeResponse(401, {
        error: {
          code: "UNAUTHORIZED",
          message: "Invalid token",
          details: {},
          request_id: "e1",
        },
      })
    );

    await expect(failClient.get("/api/v1/me")).rejects.toThrow(ApiError);
    expect(onAuthError).toHaveBeenCalledTimes(1);
  });

  it("supports PUT and DELETE methods", async () => {
    mockFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: { updated: true },
        meta: { request_id: "u1", timestamp: "2026-01-01T00:00:00Z" },
      })
    );
    await client.put("/api/v1/students/123", { name: "Updated" });
    expect(mockFetch.mock.calls[0][1].method).toBe("PUT");

    mockFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: null,
        meta: { request_id: "d1", timestamp: "2026-01-01T00:00:00Z" },
      })
    );
    await client.delete("/api/v1/students/123");
    expect(mockFetch.mock.calls[1][1].method).toBe("DELETE");
  });

  it("works without auth token", async () => {
    const noAuthClient = createClient({
      baseUrl: "http://localhost:8000",
    });

    mockFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: { access_token: "t" },
        meta: { request_id: "l1", timestamp: "2026-01-01T00:00:00Z" },
      })
    );

    await noAuthClient.post("/api/v1/auth/login", {
      email: "a@b.com",
      password: "pass",
    });
    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers["Authorization"]).toBeUndefined();
  });
});
