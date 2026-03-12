/**
 * @eduzim/offline-core — IndexedDB Storage Layer
 * =================================================
 * Pure persistence. No business logic.
 *
 * Database : eduzim_offline_v1
 * Stores   :
 *   actions — OfflineAction records  (write queue)
 *   cache   — CacheEntry records     (read cache)
 *
 * Indexes  :
 *   actions.status, actions.createdAt
 *   cache.key (keyPath), cache.expiresAt
 */

import { openDB, type IDBPDatabase } from "idb";
import type { OfflineAction, OfflineStatus, CacheEntry } from "./types";

const DB_NAME = "eduzim_offline_v1";
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase> | null = null;

// ─── Init ────────────────────────────────────────────

/** Open (or reuse) the IndexedDB database. */
export function initDB(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains("actions")) {
          const s = db.createObjectStore("actions", { keyPath: "id" });
          s.createIndex("by-status", "status");
          s.createIndex("by-createdAt", "createdAt");
        }
        if (!db.objectStoreNames.contains("cache")) {
          const c = db.createObjectStore("cache", { keyPath: "key" });
          c.createIndex("by-expiresAt", "expiresAt");
        }
      },
    });
  }
  return dbPromise;
}

/** Reset DB promise — for test isolation. */
export function resetDB(): void {
  dbPromise = null;
}

// ─── Actions (Write Queue) ───────────────────────────

/** Persist (insert or update) an action. */
export async function saveAction(action: OfflineAction): Promise<void> {
  const db = await initDB();
  await db.put("actions", action);
}

/** Get all actions with a given status. */
export async function getQueuedActions(
  status: OfflineStatus = "QUEUED",
): Promise<OfflineAction[]> {
  const db = await initDB();
  return db.getAllFromIndex("actions", "by-status", status);
}

/** Get a single action by ID. */
export async function getAction(id: string): Promise<OfflineAction | undefined> {
  const db = await initDB();
  return db.get("actions", id);
}

/** Get every action regardless of status. */
export async function getAllActions(): Promise<OfflineAction[]> {
  const db = await initDB();
  return db.getAll("actions");
}

/** Update just the status (and optional fields) of an action. */
export async function updateActionStatus(
  id: string,
  status: OfflineStatus,
  patch?: Partial<Pick<OfflineAction, "retryCount" | "error" | "lastAttemptAt">>,
): Promise<void> {
  const db = await initDB();
  const action = await db.get("actions", id);
  if (!action) return;
  action.status = status;
  if (patch) Object.assign(action, patch);
  await db.put("actions", action);
}

/** Delete an action by ID. */
export async function deleteAction(id: string): Promise<void> {
  const db = await initDB();
  await db.delete("actions", id);
}

// ─── Cache (Read Cache) ─────────────────────────────

/** Get a cache entry by key. Returns undefined if missing. */
export async function getCache<T = any>(
  key: string,
): Promise<CacheEntry<T> | undefined> {
  const db = await initDB();
  return db.get("cache", key);
}

/** Insert or update a cache entry. */
export async function setCache<T = any>(entry: CacheEntry<T>): Promise<void> {
  const db = await initDB();
  await db.put("cache", entry);
}

/** Delete a single cache entry. */
export async function deleteCache(key: string): Promise<void> {
  const db = await initDB();
  await db.delete("cache", key);
}

/** Remove every cache entry whose expiresAt < now. Returns count deleted. */
export async function clearExpiredCache(): Promise<number> {
  const db = await initDB();
  const all = await db.getAll("cache");
  const now = Date.now();
  let count = 0;
  const tx = db.transaction("cache", "readwrite");
  for (const entry of all) {
    if (entry.expiresAt < now) {
      await tx.store.delete(entry.key);
      count++;
    }
  }
  await tx.done;
  return count;
}
