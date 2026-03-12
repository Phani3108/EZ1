/**
 * @eduzim/offline-core — Public API
 * ====================================
 * Single barrel entry. No internal leakage.
 */

// ── Classes ──────────────────────────────────────────
export { OfflineQueue } from "./queue";
export type { EnqueueParams } from "./queue";

export { OfflineCache } from "./cache";

export { SyncManager } from "./sync-manager";

// ── Helpers ──────────────────────────────────────────
export { isOnline, onOnline, onOffline } from "./network";

// ── Storage (for advanced / test use) ────────────────
export { initDB, resetDB, getAllActions, deleteAction, updateActionStatus } from "./storage";

// ── Types ────────────────────────────────────────────
export type {
  OfflineAction,
  OfflineActionType,
  OfflineStatus,
  CacheEntry,
  SyncHandlerMap,
} from "./types";
