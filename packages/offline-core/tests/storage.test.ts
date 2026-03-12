/**
 * @eduzim/offline-core — Storage Tests
 * Tests for the IndexedDB persistence layer (actions + cache stores)
 */
import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach } from "vitest";
import {
  initDB,
  resetDB,
  saveAction,
  getAction,
  getQueuedActions,
  getAllActions,
  updateActionStatus,
  deleteAction,
  getCache,
  setCache,
  deleteCache,
  clearExpiredCache,
} from "../src/storage";
import type { OfflineAction, CacheEntry } from "../src/types";

function makeAction(overrides: Partial<OfflineAction> = {}): OfflineAction {
  return {
    id: `action-${Math.random().toString(36).slice(2)}`,
    type: "ATTENDANCE",
    schoolId: "school-1",
    userId: "user-1",
    deviceId: "device-1",
    payload: { classId: "class-1", date: "2025-01-01" },
    syncBatchId: `batch-${Date.now()}`,
    status: "QUEUED",
    retryCount: 0,
    createdAt: Date.now(),
    ...overrides,
  };
}

describe("Storage — Actions", () => {
  beforeEach(async () => {
    resetDB();
    const db = await initDB();
    await db.clear("actions");
    await db.clear("cache");
  });

  it("should initialise the DB and return a handle", async () => {
    const db = await initDB();
    expect(db.objectStoreNames.contains("actions")).toBe(true);
    expect(db.objectStoreNames.contains("cache")).toBe(true);
  });

  it("should save and retrieve an action by ID", async () => {
    const action = makeAction({ id: "test-1" });
    await saveAction(action);
    const retrieved = await getAction("test-1");
    expect(retrieved).toBeDefined();
    expect(retrieved!.id).toBe("test-1");
    expect(retrieved!.status).toBe("QUEUED");
  });

  it("should return undefined for non-existent action", async () => {
    expect(await getAction("nope")).toBeUndefined();
  });

  it("should get all actions", async () => {
    await saveAction(makeAction({ id: "a1" }));
    await saveAction(makeAction({ id: "a2" }));
    await saveAction(makeAction({ id: "a3" }));
    expect(await getAllActions()).toHaveLength(3);
  });

  it("should query actions by status via getQueuedActions", async () => {
    await saveAction(makeAction({ id: "q1", status: "QUEUED" }));
    await saveAction(makeAction({ id: "q2", status: "QUEUED" }));
    await saveAction(makeAction({ id: "s1", status: "SYNCED" }));
    await saveAction(makeAction({ id: "f1", status: "FAILED" }));

    expect(await getQueuedActions("QUEUED")).toHaveLength(2);
    expect(await getQueuedActions("SYNCED")).toHaveLength(1);
    expect(await getQueuedActions("FAILED")).toHaveLength(1);
  });

  it("should update just the status of an action", async () => {
    await saveAction(makeAction({ id: "u1" }));
    await updateActionStatus("u1", "SYNCING", { lastAttemptAt: Date.now() });
    const a = await getAction("u1");
    expect(a!.status).toBe("SYNCING");
    expect(a!.lastAttemptAt).toBeGreaterThan(0);
  });

  it("should silently no-op when updating non-existent ID", async () => {
    await updateActionStatus("ghost", "SYNCED"); // should not throw
  });

  it("should update retryCount + error via patch", async () => {
    await saveAction(makeAction({ id: "r1", retryCount: 0 }));
    await updateActionStatus("r1", "QUEUED", { retryCount: 1, error: "timeout" });
    const a = await getAction("r1");
    expect(a!.retryCount).toBe(1);
    expect(a!.error).toBe("timeout");
  });

  it("should delete an action by ID", async () => {
    await saveAction(makeAction({ id: "d1" }));
    await deleteAction("d1");
    expect(await getAction("d1")).toBeUndefined();
  });

  it("should preserve payload through round-trip", async () => {
    const payload = { events: [{ studentId: "s1", status: "PRESENT" }] };
    await saveAction(makeAction({ id: "p1", payload }));
    const a = await getAction("p1");
    expect(a!.payload).toEqual(payload);
  });
});

describe("Storage — Cache", () => {
  beforeEach(async () => {
    resetDB();
    const db = await initDB();
    await db.clear("actions");
    await db.clear("cache");
  });

  it("should set and get a cache entry", async () => {
    const entry: CacheEntry = {
      key: "k1",
      data: { name: "School A" },
      expiresAt: Date.now() + 60000,
      lastUpdated: Date.now(),
    };
    await setCache(entry);
    const r = await getCache("k1");
    expect(r).toBeDefined();
    expect(r!.data).toEqual({ name: "School A" });
  });

  it("should return undefined for missing cache key", async () => {
    expect(await getCache("nope")).toBeUndefined();
  });

  it("should overwrite an existing cache entry", async () => {
    await setCache({ key: "ow", data: 1, expiresAt: Date.now() + 60000, lastUpdated: Date.now() });
    await setCache({ key: "ow", data: 2, expiresAt: Date.now() + 60000, lastUpdated: Date.now() });
    const r = await getCache("ow");
    expect(r!.data).toBe(2);
  });

  it("should delete a single cache entry", async () => {
    await setCache({ key: "del", data: "x", expiresAt: Date.now() + 60000, lastUpdated: Date.now() });
    await deleteCache("del");
    expect(await getCache("del")).toBeUndefined();
  });

  it("should clear only expired cache entries", async () => {
    await setCache({ key: "valid", data: "ok", expiresAt: Date.now() + 60000, lastUpdated: Date.now() });
    await setCache({ key: "old1", data: "x", expiresAt: Date.now() - 1000, lastUpdated: Date.now() });
    await setCache({ key: "old2", data: "y", expiresAt: Date.now() - 5000, lastUpdated: Date.now() });

    const count = await clearExpiredCache();
    expect(count).toBe(2);
    expect(await getCache("valid")).toBeDefined();
  });
});
