/**
 * @eduzim/offline-core — Cache Tests
 * Tests for class-based OfflineCache
 */
import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach } from "vitest";
import { resetDB, initDB } from "../src/storage";
import { OfflineCache } from "../src/cache";

describe("OfflineCache", () => {
  let cache: OfflineCache;

  beforeEach(async () => {
    resetDB();
    const db = await initDB();
    await db.clear("actions");
    await db.clear("cache");
    cache = new OfflineCache();
  });

  it("should return null for missing key", async () => {
    expect(await cache.get("nope")).toBeNull();
  });

  it("should set and get a value", async () => {
    await cache.set("school:1", { name: "Harare Primary" }, 60_000);
    const data = await cache.get<{ name: string }>("school:1");
    expect(data).toEqual({ name: "Harare Primary" });
  });

  it("should return null for expired entry and auto-delete", async () => {
    await cache.set("old", { stale: true }, -1); // TTL in the past
    const data = await cache.get("old");
    expect(data).toBeNull();
  });

  it("should overwrite existing entry on same key", async () => {
    await cache.set("k", { v: 1 }, 60_000);
    await cache.set("k", { v: 2 }, 60_000);
    expect(await cache.get("k")).toEqual({ v: 2 });
  });

  it("should invalidate (delete) an entry", async () => {
    await cache.set("inv", "data", 60_000);
    await cache.invalidate("inv");
    expect(await cache.get("inv")).toBeNull();
  });

  it("should handle complex nested data", async () => {
    const data = { students: [{ id: "s1", grades: [90, 85] }] };
    await cache.set("complex", data, 60_000);
    expect(await cache.get("complex")).toEqual(data);
  });

  it("should purge expired entries", async () => {
    await cache.set("fresh", "ok", 60_000);
    await cache.set("exp1", "x", -1000);
    await cache.set("exp2", "y", -5000);
    const count = await cache.purgeExpired();
    expect(count).toBe(2);
    expect(await cache.get("fresh")).toBe("ok");
  });

  it("should handle numeric, string, boolean, and null data", async () => {
    await cache.set("num", 42, 60_000);
    await cache.set("str", "hello", 60_000);
    await cache.set("bool", true, 60_000);
    await cache.set("nil", null, 60_000);

    expect(await cache.get("num")).toBe(42);
    expect(await cache.get("str")).toBe("hello");
    expect(await cache.get("bool")).toBe(true);
    expect(await cache.get("nil")).toBeNull(); // null data — get returns null
  });
});
