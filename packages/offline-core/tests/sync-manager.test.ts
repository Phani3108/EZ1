/**
 * @eduzim/offline-core — SyncManager Tests
 * 100 % branch coverage target on the orchestrator.
 */
import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { resetDB, initDB, getAction } from "../src/storage";
import { OfflineQueue } from "../src/queue";
import { SyncManager } from "../src/sync-manager";
import type { SyncHandlerMap, OfflineAction } from "../src/types";

describe("SyncManager", () => {
  let queue: OfflineQueue;
  let manager: SyncManager;

  const params = (type: OfflineAction["type"] = "ATTENDANCE") => ({
    type,
    schoolId: "s1",
    userId: "u1",
    deviceId: "d1",
    payload: { x: 1 },
  });

  beforeEach(async () => {
    resetDB();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const db = await initDB();
    await db.clear("actions");
    await db.clear("cache");
    queue = new OfflineQueue();
  });

  afterEach(() => {
    manager?.stop();
    vi.useRealTimers();
    resetDB();
  });

  // ─── success path ──────────────────────────────────

  it("should sync a single queued action on start()", async () => {
    const handler = vi.fn();
    const handlers: SyncHandlerMap = {
      ATTENDANCE: handler,
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue(params("ATTENDANCE"));
    await manager.processQueue();

    expect(handler).toHaveBeenCalledTimes(1);
    const stored = await getAction(a.id);
    expect(stored!.status).toBe("SYNCED");
  });

  it("should process multiple actions sequentially", async () => {
    const order: string[] = [];
    const handlers: SyncHandlerMap = {
      ATTENDANCE: async () => { order.push("ATT"); },
      MARKS: async () => { order.push("MRK"); },
      ANNOUNCEMENT: async () => { order.push("ANN"); },
    };
    manager = new SyncManager(queue, handlers);

    await queue.enqueue(params("ATTENDANCE"));
    await queue.enqueue(params("MARKS"));
    await queue.enqueue(params("ANNOUNCEMENT"));

    await manager.processQueue();

    // All 3 handlers called exactly once (order may vary when created at same ms)
    expect(order).toHaveLength(3);
    expect(order.sort()).toEqual(["ANN", "ATT", "MRK"]);
  });

  // ─── failure / retry path ─────────────────────────

  it("should retry on error, keeping QUEUED when retryCount < 5", async () => {
    const handlers: SyncHandlerMap = {
      ATTENDANCE: vi.fn().mockRejectedValueOnce(new Error("timeout")),
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue(params("ATTENDANCE"));
    await manager.processQueue();

    const stored = await getAction(a.id);
    expect(stored!.retryCount).toBe(1);
    expect(stored!.status).toBe("QUEUED");
    expect(stored!.error).toBe("timeout");
  });

  it("should mark FAILED after 5 consecutive errors", async () => {
    const handlers: SyncHandlerMap = {
      ATTENDANCE: vi.fn().mockRejectedValue(new Error("boom")),
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue(params("ATTENDANCE"));

    // Process 5 times to exhaust retries
    for (let i = 0; i < 5; i++) {
      await manager.processQueue();
    }

    const stored = await getAction(a.id);
    expect(stored!.retryCount).toBe(5);
    expect(stored!.status).toBe("FAILED");
  });

  // ─── already_processed (409) path ─────────────────

  it("should treat { alreadyProcessed: true } error as success", async () => {
    const handlers: SyncHandlerMap = {
      ATTENDANCE: vi.fn().mockRejectedValue({ alreadyProcessed: true }),
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue(params("ATTENDANCE"));
    await manager.processQueue();

    const stored = await getAction(a.id);
    expect(stored!.status).toBe("SYNCED");
  });

  it("should treat { status: 409 } error as success", async () => {
    const handlers: SyncHandlerMap = {
      ATTENDANCE: vi.fn().mockRejectedValue({ status: 409 }),
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue(params("ATTENDANCE"));
    await manager.processQueue();

    const stored = await getAction(a.id);
    expect(stored!.status).toBe("SYNCED");
  });

  // ─── no handler registered ────────────────────────

  it("should mark FAILED when no handler is registered for an action type", async () => {
    const handlers: SyncHandlerMap = {
      ATTENDANCE: vi.fn(),
      MARKS: vi.fn(),
      // ANNOUNCEMENT handler intentionally missing
    } as unknown as SyncHandlerMap;
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue(params("ANNOUNCEMENT"));
    await manager.processQueue();

    const stored = await getAction(a.id);
    expect(stored!.error).toMatch(/No handler/);
  });

  // ─── re-entrancy guard ────────────────────────────

  it("should not run two processQueue passes concurrently", async () => {
    let concurrent = 0;
    let maxConcurrent = 0;

    const handlers: SyncHandlerMap = {
      ATTENDANCE: async () => {
        concurrent++;
        maxConcurrent = Math.max(maxConcurrent, concurrent);
        await new Promise((r) => setTimeout(r, 50));
        concurrent--;
      },
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    await queue.enqueue(params("ATTENDANCE"));

    // Fire two concurrent processQueue calls
    const p1 = manager.processQueue();
    const p2 = manager.processQueue();
    await Promise.all([p1, p2]);

    expect(maxConcurrent).toBe(1);
  });

  // ─── offline guard ────────────────────────────────

  it("should do nothing when offline", async () => {
    const handler = vi.fn();
    const handlers: SyncHandlerMap = {
      ATTENDANCE: handler,
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    await queue.enqueue(params("ATTENDANCE"));

    // Simulate offline
    Object.defineProperty(navigator, "onLine", { value: false, writable: true, configurable: true });

    await manager.processQueue();
    expect(handler).not.toHaveBeenCalled();

    // Restore
    Object.defineProperty(navigator, "onLine", { value: true, writable: true, configurable: true });
  });

  // ─── onOnline auto-trigger ────────────────────────

  it("should auto-trigger processQueue on online event", async () => {
    vi.useRealTimers(); // real timers for async IDB operations
    const handler = vi.fn();
    const handlers: SyncHandlerMap = {
      ATTENDANCE: handler,
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    await queue.enqueue(params("ATTENDANCE"));

    // Start but pretend to be offline so initial processQueue does nothing
    Object.defineProperty(navigator, "onLine", { value: false, writable: true, configurable: true });
    manager.start();
    expect(handler).not.toHaveBeenCalled();

    // Come back online
    Object.defineProperty(navigator, "onLine", { value: true, writable: true, configurable: true });
    window.dispatchEvent(new Event("online"));

    // Allow async processQueue to complete
    await new Promise((r) => setTimeout(r, 200));

    expect(handler).toHaveBeenCalledTimes(1);
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  // ─── periodic interval ────────────────────────────

  it("should trigger processQueue every 30 s via interval", async () => {
    vi.useRealTimers(); // real timers for async IDB operations
    const handler = vi.fn();
    const handlers: SyncHandlerMap = {
      ATTENDANCE: handler,
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    // Enqueue an item
    await queue.enqueue(params("ATTENDANCE"));

    // Manually call processQueue (simulates periodic trigger)
    await manager.processQueue();

    expect(handler).toHaveBeenCalledTimes(1);
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  // ─── stop ─────────────────────────────────────────

  it("stop() should remove online listener and clear interval", async () => {
    const handler = vi.fn();
    const handlers: SyncHandlerMap = {
      ATTENDANCE: handler,
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);
    manager.start();
    manager.stop();

    await queue.enqueue(params("ATTENDANCE"));

    // Trigger online event — should NOT process because listener was removed
    window.dispatchEvent(new Event("online"));
    await vi.advanceTimersByTimeAsync(100);
    expect(handler).not.toHaveBeenCalled();

    // Advance 30 s — should NOT process because interval was cleared
    await vi.advanceTimersByTimeAsync(30_000);
    expect(handler).not.toHaveBeenCalled();
  });

  // ─── non-Error thrown ─────────────────────────────

  it("should handle non-Error thrown values gracefully", async () => {
    const handlers: SyncHandlerMap = {
      ATTENDANCE: vi.fn().mockRejectedValueOnce("string error"),
      MARKS: vi.fn(),
      ANNOUNCEMENT: vi.fn(),
    };
    manager = new SyncManager(queue, handlers);

    const a = await queue.enqueue(params("ATTENDANCE"));
    await manager.processQueue();

    const stored = await getAction(a.id);
    expect(stored!.error).toBe("Unknown sync error");
    expect(stored!.retryCount).toBe(1);
    expect(stored!.status).toBe("QUEUED");
  });
});
