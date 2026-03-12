/**
 * @eduzim/offline-core — Queue Admin Methods Tests
 * ===================================================
 * Tests cover the new admin/sync-center helper methods on OfflineQueue:
 *   - getAll() — all actions regardless of status
 *   - clearSynced() — delete all SYNCED actions
 *   - resetFailed(id) — reset single FAILED → QUEUED
 *   - resetAllFailed() — reset all FAILED → QUEUED
 */

import { describe, it, expect, beforeEach } from "vitest";
import "fake-indexeddb/auto";
import { OfflineQueue } from "../src/queue";
import { resetDB, initDB, getAllActions, updateActionStatus } from "../src/storage";
import type { OfflineAction } from "../src/types";

beforeEach(async () => {
  resetDB();
  const db = await initDB();
  await db.clear("actions");
  await db.clear("cache");
});

describe("OfflineQueue.getAll", () => {
  it("returns empty array when queue is empty", async () => {
    const queue = new OfflineQueue();
    const all = await queue.getAll();
    expect(all).toEqual([]);
  });

  it("returns all actions regardless of status", async () => {
    const queue = new OfflineQueue();
    const a1 = await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });
    const a2 = await queue.enqueue({
      type: "MARKS",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });

    // Manually set a2 to SYNCED
    await queue.markSynced(a2.id);

    const all = await queue.getAll();
    expect(all).toHaveLength(2);
    const statuses = all.map((a) => a.status);
    expect(statuses).toContain("QUEUED");
    expect(statuses).toContain("SYNCED");
  });
});

describe("OfflineQueue.clearSynced", () => {
  it("returns 0 when no synced actions", async () => {
    const queue = new OfflineQueue();
    await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });
    const count = await queue.clearSynced();
    expect(count).toBe(0);
  });

  it("deletes all SYNCED actions", async () => {
    const queue = new OfflineQueue();
    const a1 = await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });
    const a2 = await queue.enqueue({
      type: "MARKS",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });
    const a3 = await queue.enqueue({
      type: "ANNOUNCEMENT",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });

    await queue.markSynced(a1.id);
    await queue.markSynced(a3.id);

    const count = await queue.clearSynced();
    expect(count).toBe(2);

    const remaining = await queue.getAll();
    expect(remaining).toHaveLength(1);
    expect(remaining[0].id).toBe(a2.id);
  });

  it("does not delete QUEUED or FAILED actions", async () => {
    const queue = new OfflineQueue();
    const a1 = await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });

    // Force to FAILED
    await queue.markFailed(a1.id, "err");
    await queue.markFailed(a1.id, "err");
    await queue.markFailed(a1.id, "err");
    await queue.markFailed(a1.id, "err");
    await queue.markFailed(a1.id, "err");

    const count = await queue.clearSynced();
    expect(count).toBe(0);
    const all = await queue.getAll();
    expect(all).toHaveLength(1);
  });
});

describe("OfflineQueue.resetFailed", () => {
  it("resets a FAILED action back to QUEUED", async () => {
    const queue = new OfflineQueue();
    const a = await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });

    // Force to FAILED (5 failures)
    for (let i = 0; i < 5; i++) {
      await queue.markFailed(a.id, `error-${i}`);
    }

    // Verify it's FAILED
    let all = await queue.getAll();
    expect(all[0].status).toBe("FAILED");
    expect(all[0].retryCount).toBe(5);

    // Reset it
    await queue.resetFailed(a.id);

    all = await queue.getAll();
    expect(all[0].status).toBe("QUEUED");
    expect(all[0].retryCount).toBe(0);
    expect(all[0].error).toBeUndefined();
  });
});

describe("OfflineQueue.resetAllFailed", () => {
  it("resets all FAILED actions to QUEUED", async () => {
    const queue = new OfflineQueue();
    const a1 = await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });
    const a2 = await queue.enqueue({
      type: "MARKS",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });
    const a3 = await queue.enqueue({
      type: "ANNOUNCEMENT",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });

    // Fail a1 and a3 (5 times each), leave a2 as QUEUED
    for (let i = 0; i < 5; i++) {
      await queue.markFailed(a1.id, "err");
      await queue.markFailed(a3.id, "err");
    }

    // Verify
    let all = await queue.getAll();
    const failedBefore = all.filter((a) => a.status === "FAILED");
    expect(failedBefore).toHaveLength(2);

    // Reset all
    await queue.resetAllFailed();

    all = await queue.getAll();
    const failedAfter = all.filter((a) => a.status === "FAILED");
    expect(failedAfter).toHaveLength(0);

    // All should be QUEUED now
    const queued = all.filter((a) => a.status === "QUEUED");
    expect(queued).toHaveLength(3);
  });

  it("does nothing when no FAILED actions", async () => {
    const queue = new OfflineQueue();
    await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
    });

    // Should not throw
    await queue.resetAllFailed();

    const all = await queue.getAll();
    expect(all).toHaveLength(1);
    expect(all[0].status).toBe("QUEUED");
  });
});
