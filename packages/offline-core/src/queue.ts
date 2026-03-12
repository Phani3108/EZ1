/**
 * @eduzim/offline-core — OfflineQueue
 * ======================================
 * Class-based write-queue engine.
 * Generates UUIDs, sets defaults, delegates persistence to storage.
 */

import { v4 as uuid } from "uuid";
import {
  saveAction,
  getQueuedActions,
  getAction,
  getAllActions,
  updateActionStatus,
  deleteAction,
} from "./storage";
import type { OfflineAction, OfflineActionType } from "./types";

export interface EnqueueParams {
  type: OfflineActionType;
  schoolId: string;
  userId: string;
  deviceId: string;
  payload: any;
  syncBatchId?: string;
}

export class OfflineQueue {
  /** Enqueue a new action. Returns the persisted action. */
  async enqueue(params: EnqueueParams): Promise<OfflineAction> {
    const now = Date.now();
    const action: OfflineAction = {
      id: uuid(),
      type: params.type,
      schoolId: params.schoolId,
      userId: params.userId,
      deviceId: params.deviceId,
      payload: params.payload,
      syncBatchId: params.syncBatchId ?? `batch-${uuid()}`,
      status: "QUEUED",
      retryCount: 0,
      createdAt: now,
    };
    await saveAction(action);
    return action;
  }

  /** Return all actions with status QUEUED, ordered by createdAt (FIFO). */
  async getPending(): Promise<OfflineAction[]> {
    const actions = await getQueuedActions("QUEUED");
    return actions.sort((a, b) => a.createdAt - b.createdAt);
  }

  /** Transition an action to SYNCING. */
  async markSyncing(id: string): Promise<void> {
    await updateActionStatus(id, "SYNCING", {
      lastAttemptAt: Date.now(),
    });
  }

  /** Transition an action to SYNCED. */
  async markSynced(id: string): Promise<void> {
    await updateActionStatus(id, "SYNCED", {
      lastAttemptAt: Date.now(),
    });
  }

  /**
   * Record an error. Increments retryCount.
   * If retryCount >= 5 → FAILED; else → QUEUED (retry later).
   */
  async markFailed(id: string, error: string): Promise<void> {
    const action = await getAction(id);
    if (!action) return;

    const newRetryCount = action.retryCount + 1;
    const newStatus = newRetryCount >= 5 ? "FAILED" : "QUEUED";

    await updateActionStatus(id, newStatus, {
      retryCount: newRetryCount,
      error,
      lastAttemptAt: Date.now(),
    });
  }

  // ─── Admin / Sync-Center helpers ─────────────────────

  /** Return every action regardless of status. */
  async getAll(): Promise<OfflineAction[]> {
    return getAllActions();
  }

  /** Delete all SYNCED actions. Returns count deleted. */
  async clearSynced(): Promise<number> {
    const synced = await getQueuedActions("SYNCED");
    for (const a of synced) {
      await deleteAction(a.id);
    }
    return synced.length;
  }

  /** Reset a FAILED action back to QUEUED for retry. */
  async resetFailed(id: string): Promise<void> {
    await updateActionStatus(id, "QUEUED", {
      retryCount: 0,
      error: undefined,
    });
  }

  /** Reset ALL failed actions back to QUEUED. */
  async resetAllFailed(): Promise<void> {
    const failed = await getQueuedActions("FAILED");
    for (const a of failed) {
      await updateActionStatus(a.id, "QUEUED", {
        retryCount: 0,
        error: undefined,
      });
    }
  }
}
