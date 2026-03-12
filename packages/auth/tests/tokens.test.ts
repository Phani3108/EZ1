/// <reference types="vitest/globals" />

import { describe, it, expect, beforeEach } from "vitest";
import {
  setTokens,
  getAccessToken,
  clearTokens,
  isAuthenticated,
} from "../src/tokens";

describe("Token Store", () => {
  beforeEach(() => {
    clearTokens();
  });

  it("stores and retrieves access token", () => {
    setTokens("access-123", 3600);
    expect(getAccessToken()).toBe("access-123");
    expect(isAuthenticated()).toBe(true);
  });

  it("returns null when no tokens set", () => {
    expect(getAccessToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("clears tokens", () => {
    setTokens("a", 3600);
    clearTokens();
    expect(getAccessToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("returns null for expired access token", () => {
    setTokens("expired", -1); // expired immediately
    expect(getAccessToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });
});
