/**
 * @eduzim/offline-core — Integration Tests
 * Full workflow tests: Queue ↔ Cache ↔ SyncManager ↔ Storage
 */
import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { resetDB, initDB, getAction, getAllActions } from "../src/storage";
import { OfflineQueue } from "../src/queue";
import { OfflineCache } from "../src/cache";
import { SyncManager } from "../src/sync-manager";
import type { SyncHandlerMap, OfflineAction } from "../src/types";

describe("Integration — Offline Workflow", () => {
  let queue: OfflineQueue;
  let cache: OfflineCache;
  let manager: SyncManager;

  beforeEach(async () => {
    resetDB();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const db = await initDB();
    await db.clear("actions");
    await db.clear("cache");
    queue = new OfflineQueue();
    cache = new OfflineCache();
  });

  afterEach(() => {
    manager?.stop();
    vi.useRealTimers();
    resetDB();
  });

  it("full attendance sync workflow: enqueue → sync → SYNCED", async () => {
    const synced: any[] = [];
    const handlers: SyncHandlerMap = {
      ATTENDANCE: async (a) => { synced.push(a.payload); },
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "school-1",
      userId: "teacher-1",
      deviceId: "tw:teacher-1",
      payload: { classId: "form1a", events: [{ sid: "s1", status: "PRESENT" }] },
    });

    await manager.processQueue();

    const stored = await getAction(a.id);
    expect(stored!.status).toBe("SYNCED");
    expect(synced[0]).toEqual(a.payload);
  });

  it("marks sync workflow with custom syncBatchId", async () => {
    const handlers: SyncHandlerMap = {
      ATTENDANCE: vi.fn(),
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue({
      type: "MARKS",
      schoolId: "s1",
      userId: "u1",
      deviceId: "d1",
      payload: { marks: [{ sid: "s1", score: 85 }] },
      syncBatchId: "marks-math-midterm",
    });

    await manager.processQueue();
    expect(a.syncBatchId).toBe("marks-math-midterm");
    expect((await getAction(a.id))!.status).toBe("SYNCED");
  });

  it("retry cycle: fail → retry queued → eventually FAILED at 5", async () => {
    const handlers: SyncHandlerMap = {
      ATTENDANCE: vi.fn().mockRejectedValue(new Error("503")),
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue({
      type: "ATTENDANCE",
      schoolId: "s1",
      userId: "u1",
      deviceId: "d1",
      payload: {},
    });

    for (let i = 0; i < 5; i++) {
      await manager.processQueue();
    }

    const stored = await getAction(a.id);
    expect(stored!.status).toBe("FAILED");
    expect(stored!.retryCount).toBe(5);
  });

  it("cache set → get → invalidate round-trip", async () => {
    await cache.set("parent:child:s1", { present: 45, absent: 3 }, 60_000);
    const data = await cache.get("parent:child:s1");
    expect(data).toEqual({ present: 45, absent: 3 });

    await cache.invalidate("parent:child:s1");
    expect(await cache.get("parent:child:s1")).toBeNull();
  });

  it("cache expiry returns null", async () => {
    await cache.set("old-data", { stale: true }, -1);
    expect(await cache.get("old-data")).toBeNull();
  });

  it("mixed queue: 3 types enqueued and all synced", async () => {
    const handlers: SyncHandlerMap = {
      ATTENDANCE: vi.fn(),
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    await queue.enqueue({ type: "ATTENDANCE", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });
    await queue.enqueue({ type: "MARKS", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });
    await queue.enqueue({ type: "ANNOUNCEMENT", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });

    await manager.processQueue();

    const all = await getAllActions();
    expect(all.every((a) => a.status === "SYNCED")).toBe(true);
    expect(all).toHaveLength(3);
  });

  it("SyncManager processQueue can be called manually", async () => {
    const handler = vi.fn();
    const handlers: SyncHandlerMap = {
      ATTENDANCE: handler,
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    await queue.enqueue({ type: "ATTENDANCE", schoolId: "s1", userId: "u1", deviceId: "d1", payload: {} });

    await manager.processQueue();

    expect(handler).toHaveBeenCalledTimes(1);
  });
});
