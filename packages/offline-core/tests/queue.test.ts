/**
 * @eduzim/offline-core — Queue Tests
 * Tests for class-based OfflineQueue
 */
import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach } from "vitest";
import { resetDB, initDB, getAction } from "../src/storage";
import { OfflineQueue } from "../src/queue";

describe("OfflineQueue", () => {
  let queue: OfflineQueue;

  beforeEach(async () => {
    resetDB();
    const db = await initDB();
    await db.clear("actions");
    await db.clear("cache");
    queue = new OfflineQueue();
  });

  it("should enqueue an action with QUEUED status and retryCount 0", async () => {
    const action = await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "school-1",
      userId: "user-1",
      deviceId: "device-1",
      payload: { classId: "c1" },
    });

    expect(action.id).toBeDefined();
    expect(action.status).toBe("QUEUED");
    expect(action.retryCount).toBe(0);
    expect(typeof action.createdAt).toBe("number");
  });

  it("should generate a UUID for the action ID", async () => {
    const action = await queue.enqueue({
      type: "MARKS",
      schoolId: "s1",
      userId: "u1",
      deviceId: "d1",
      payload: {},
    });
    // UUID v4 format: 8-4-4-4-12
    expect(action.id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
  });

  it("should auto-generate syncBatchId when not provided", async () => {
    const a = await queue.enqueue({
      type: "MARKS",
      schoolId: "s1",
      userId: "u1",
      deviceId: "d1",
      payload: {},
    });
    expect(a.syncBatchId).toMatch(/^batch-/);
  });

  it("should use provided syncBatchId", async () => {
    const a = await queue.enqueue({
      type: "MARKS",
      schoolId: "s1",
      userId: "u1",
      deviceId: "d1",
      payload: {},
      syncBatchId: "custom-batch-99",
    });
    expect(a.syncBatchId).toBe("custom-batch-99");
  });

  it("should persist the action in IndexedDB", async () => {
    const a = await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "s1",
      userId: "u1",
      deviceId: "d1",
      payload: { x: 1 },
    });
    const stored = await getAction(a.id);
    expect(stored).toBeDefined();
    expect(stored!.payload).toEqual({ x: 1 });
  });

  it("getPending returns only QUEUED actions", async () => {
    const a = await queue.enqueue({ type: "ATTENDANCE", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });
    await queue.enqueue({ type: "MARKS", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });

    await queue.markSynced(a.id); // move first to SYNCED

    const pending = await queue.getPending();
    expect(pending).toHaveLength(1);
    expect(pending[0].status).toBe("QUEUED");
  });

  it("markSyncing sets status to SYNCING and lastAttemptAt", async () => {
    const a = await queue.enqueue({ type: "ATTENDANCE", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });
    await queue.markSyncing(a.id);
    const stored = await getAction(a.id);
    expect(stored!.status).toBe("SYNCING");
    expect(stored!.lastAttemptAt).toBeGreaterThan(0);
  });

  it("markSynced sets status to SYNCED", async () => {
    const a = await queue.enqueue({ type: "ATTENDANCE", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });
    await queue.markSynced(a.id);
    const stored = await getAction(a.id);
    expect(stored!.status).toBe("SYNCED");
  });

  it("markFailed increments retryCount and keeps QUEUED when < 5", async () => {
    const a = await queue.enqueue({ type: "MARKS", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });
    await queue.markFailed(a.id, "timeout");
    const stored = await getAction(a.id);
    expect(stored!.retryCount).toBe(1);
    expect(stored!.status).toBe("QUEUED");
    expect(stored!.error).toBe("timeout");
  });

  it("markFailed sets FAILED when retryCount reaches 5", async () => {
    const a = await queue.enqueue({ type: "MARKS", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });
    // Fail 5 times
    for (let i = 0; i < 5; i++) {
      await queue.markFailed(a.id, `attempt ${i + 1}`);
    }
    const stored = await getAction(a.id);
    expect(stored!.retryCount).toBe(5);
    expect(stored!.status).toBe("FAILED");
  });

  it("should generate unique IDs for 20 concurrent enqueues", async () => {
    const ids = new Set<string>();
    for (let i = 0; i < 20; i++) {
      const a = await queue.enqueue({ type: "ATTENDANCE", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });
      ids.add(a.id);
    }
    expect(ids.size).toBe(20);
  });
});
