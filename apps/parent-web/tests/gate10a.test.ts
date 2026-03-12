/**
 * Parent-web — Unit Tests (10A-0 / 10A-1 Quality Gate)
 */

import { describe, it, expect, beforeEach } from "vitest";
import { z } from "zod";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

describe("Parent login validation", () => {
  it("accepts valid parent login", () => {
    const result = loginSchema.safeParse({
      email: "parent@example.com",
      password: "myP@ssword",
    });
    expect(result.success).toBe(true);
  });

  it("rejects invalid email", () => {
    const result = loginSchema.safeParse({ email: "bad", password: "x" });
    expect(result.success).toBe(false);
  });
});

import { ApiError } from "@eduzim/api-client";

describe("Error handling", () => {
  it("ApiError parses 403 forbidden", () => {
    const err = new ApiError(403, {
      code: "FORBIDDEN",
      message: "Parents cannot access admin pages",
      details: {},
      request_id: "p-001",
    });
    expect(err.code).toBe("FORBIDDEN");
    expect(err.status).toBe(403);
  });
});

import {
  setTokens,
  getAccessToken,
  clearTokens,
  isAuthenticated,
} from "@eduzim/auth";

describe("Parent auth tokens", () => {
  beforeEach(() => clearTokens());

  it("stores parent token in memory", () => {
    setTokens("parent-token", 1800);
    expect(getAccessToken()).toBe("parent-token");
    expect(isAuthenticated()).toBe(true);
  });

  it("clears on logout", () => {
    setTokens("p", 100);
    clearTokens();
    expect(isAuthenticated()).toBe(false);
  });
});

describe("API client service scope", () => {
  it("parent has limited api services", async () => {
    const { authApi, studentApi, attendanceApi, feesApi, commApi, createClient } =
      await import("@eduzim/api-client");
    const client = createClient({ baseUrl: "http://localhost" });

    // Parent can use these
    expect(typeof authApi(client).login).toBe("function");
    expect(typeof studentApi(client).list).toBe("function");
    expect(typeof attendanceApi(client).dailySummary).toBe("function");
    expect(typeof feesApi(client).listInvoices).toBe("function");
    expect(typeof commApi(client).listAnnouncements).toBe("function");
  });
});
