/**
 * @eduzim/offline-core — Types
 * ==============================
 * Core shared types for the offline queue and cache system.
 * No business logic — pure type definitions.
 */

// ───── Action Types ─────

export type OfflineActionType = "ATTENDANCE" | "MARKS" | "ANNOUNCEMENT";

export type OfflineStatus = "QUEUED" | "SYNCING" | "SYNCED" | "FAILED";

export interface OfflineAction {
  id: string;
  type: OfflineActionType;
  schoolId: string;
  userId: string;
  deviceId: string;
  payload: any;
  syncBatchId: string;
  status: OfflineStatus;
  retryCount: number;
  error?: string;
  /** Unix timestamp (ms) */
  createdAt: number;
  /** Unix timestamp (ms) */
  lastAttemptAt?: number;
}

// ───── Cache Types ─────

export interface CacheEntry<T = any> {
  key: string;
  data: T;
  /** Unix timestamp (ms) when entry expires */
  expiresAt: number;
  /** Unix timestamp (ms) when entry was last set */
  lastUpdated: number;
}

// ───── Sync Handler Map ─────

export type SyncHandlerMap = {
  [K in OfflineActionType]: (action: OfflineAction) => Promise<void>;
};
