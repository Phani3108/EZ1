/**
 * @eduzim/offline-core — SyncManager
 * =====================================
 * Orchestrator — the brain of the sync system.
 *
 * Responsibilities:
 *   - Accept a SyncHandlerMap (apps inject per-type async handlers)
 *   - Process QUEUED actions sequentially (not parallel)
 *   - On success / already_processed → markSynced
 *   - On error → markFailed (retryCount++, >=5 → FAILED else QUEUED)
 *   - Auto-trigger on online event + periodic 30 s interval
 *   - start() / stop() / processQueue()
 */

import { isOnline, onOnline } from "./network";
import { OfflineQueue } from "./queue";
import type { SyncHandlerMap, OfflineAction } from "./types";
import { getAction } from "./storage";

const SYNC_INTERVAL_MS = 30_000;

export class SyncManager {
  private queue: OfflineQueue;
  private handlers: SyncHandlerMap;
  private isSyncing = false;
  private unsubOnline: (() => void) | null = null;
  private intervalId: ReturnType<typeof setInterval> | null = null;

  constructor(queue: OfflineQueue, handlers: SyncHandlerMap) {
    this.queue = queue;
    this.handlers = handlers;
  }

  /** Begin auto-sync: listen for online + periodic 30 s interval. */
  start(): void {
    this.unsubOnline = onOnline(() => {
      this.processQueue();
    });

    this.intervalId = setInterval(() => {
      if (isOnline()) {
        this.processQueue();
      }
    }, SYNC_INTERVAL_MS);

    // If already online, kick off immediately
    if (isOnline()) {
      this.processQueue();
    }
  }

  /** Tear down listeners and interval. */
  stop(): void {
    if (this.unsubOnline) {
      this.unsubOnline();
      this.unsubOnline = null;
    }
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /**
   * Process the queue sequentially.
   * Re-entrant guard ensures only one pass runs at a time.
   * Items that fail are NOT retried in the same pass — they wait for the next trigger.
   */
  async processQueue(): Promise<void> {
    if (this.isSyncing) return;
    if (!isOnline()) return;
    this.isSyncing = true;

    const attempted = new Set<string>();

    try {
      let pending = await this.queue.getPending();

      while (pending.length > 0 && isOnline()) {
        for (const action of pending) {
          if (!isOnline()) break;
          attempted.add(action.id);

          await this.queue.markSyncing(action.id);

          const handler = this.handlers[action.type];
          if (!handler) {
            await this.queue.markFailed(
              action.id,
              `No handler registered for type: ${action.type}`,
            );
            continue;
          }

          try {
            // Re-read the action to get the latest state (with SYNCING status)
            const current = await getAction(action.id);
            await handler(current ?? action);
            await this.queue.markSynced(action.id);
          } catch (err: any) {
            // 409 / already_processed → treat as success
            if (err?.alreadyProcessed || err?.status === 409) {
              await this.queue.markSynced(action.id);
            } else {
              const msg =
                err instanceof Error ? err.message : "Unknown sync error";
              await this.queue.markFailed(action.id, msg);
            }
          }
        }

        // Only pick up *newly* queued items (not items we already attempted that went back to QUEUED)
        pending = (await this.queue.getPending()).filter(
          (a) => !attempted.has(a.id),
        );
      }
    } finally {
      this.isSyncing = false;
    }
  }
}
