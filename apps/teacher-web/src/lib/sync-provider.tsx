/**
 * Teacher-web — Offline Sync Provider
 * =======================================
 * Wraps @eduzim/offline-core OfflineQueue + SyncManager in a React context.
 * Provides:
 *   - enqueueOffline(params) — queue an action for sync
 *   - syncStatus — current counts (queued, syncing, failed, synced)
 *   - online — network status
 *   - retryAll() — retry all failed actions
 *   - processQueue() — manually trigger sync
 *   - getAllActions() — for sync-center admin view
 *   - clearSynced() — remove synced items from queue
 *   - retryOne(id) — retry a single failed action
 */

"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
} from "react";
import {
  OfflineQueue,
  SyncManager,
  isOnline as checkOnline,
  onOnline,
  onOffline,
  type EnqueueParams,
  type OfflineAction,
  type SyncHandlerMap,
  type OfflineStatus,
} from "@eduzim/offline-core";
import { attendance, assessment, comm } from "@/lib/api";

// ───── Sync Handler Map ─────

const handlers: SyncHandlerMap = {
  ATTENDANCE: async (action: OfflineAction) => {
    await attendance.syncAttendance(action.payload as any);
  },
  MARKS: async (action: OfflineAction) => {
    const p = action.payload as { assessmentId: string; marks: any };
    await assessment.bulkUpsertMarks(p.assessmentId, { marks: p.marks });
  },
  ANNOUNCEMENT: async (action: OfflineAction) => {
    await comm.createAnnouncement(action.payload as any);
  },
};

// ───── Status Counts ─────

export interface SyncStatusCounts {
  queued: number;
  syncing: number;
  failed: number;
  synced: number;
  total: number;
}

const defaultStatus: SyncStatusCounts = {
  queued: 0,
  syncing: 0,
  failed: 0,
  synced: 0,
  total: 0,
};

function computeStatus(actions: OfflineAction[]): SyncStatusCounts {
  const counts = { ...defaultStatus };
  for (const a of actions) {
    counts.total++;
    if (a.status === "QUEUED") counts.queued++;
    else if (a.status === "SYNCING") counts.syncing++;
    else if (a.status === "FAILED") counts.failed++;
    else if (a.status === "SYNCED") counts.synced++;
  }
  return counts;
}

// ───── Context ─────

interface SyncContextValue {
  /** Enqueue an action for offline sync */
  enqueueOffline: (params: EnqueueParams) => Promise<OfflineAction>;
  /** Current sync counts */
  syncStatus: SyncStatusCounts;
  /** Whether the browser is online */
  online: boolean;
  /** Retry all failed actions */
  retryAll: () => Promise<void>;
  /** Manually trigger queue processing */
  processQueue: () => Promise<void>;
  /** Get all actions (for sync-center) */
  getAllActions: () => Promise<OfflineAction[]>;
  /** Clear all synced actions (for sync-center) */
  clearSynced: () => Promise<void>;
  /** Retry a single failed action (for sync-center) */
  retryOne: (id: string) => Promise<void>;
}

const SyncContext = createContext<SyncContextValue>({
  enqueueOffline: () => Promise.reject(new Error("SyncProvider not mounted")),
  syncStatus: defaultStatus,
  online: true,
  retryAll: () => Promise.resolve(),
  processQueue: () => Promise.resolve(),
  getAllActions: () => Promise.resolve([]),
  clearSynced: () => Promise.resolve(),
  retryOne: () => Promise.resolve(),
});

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const [syncStatus, setSyncStatus] = useState<SyncStatusCounts>(defaultStatus);
  const [online, setOnline] = useState(true);
  const queueRef = useRef<OfflineQueue | null>(null);
  const managerRef = useRef<SyncManager | null>(null);

  /** Refresh status counts from the queue. */
  const refreshStatus = useCallback(async () => {
    if (!queueRef.current) return;
    const all = await queueRef.current.getAll();
    setSyncStatus(computeStatus(all));
  }, []);

  useEffect(() => {
    setOnline(checkOnline());

    const unsubOn = onOnline(() => setOnline(true));
    const unsubOff = onOffline(() => setOnline(false));

    // Create queue and manager
    const queue = new OfflineQueue();
    const manager = new SyncManager(queue, handlers);
    queueRef.current = queue;
    managerRef.current = manager;

    manager.start();

    // Load initial status
    queue.getAll().then((all) => setSyncStatus(computeStatus(all)));

    // Poll status while active (picks up changes from SyncManager processing)
    const pollId = setInterval(() => {
      queue.getAll().then((all) => setSyncStatus(computeStatus(all)));
    }, 5_000);

    return () => {
      unsubOn();
      unsubOff();
      manager.stop();
      clearInterval(pollId);
      queueRef.current = null;
      managerRef.current = null;
    };
  }, []);

  const enqueueOffline = useCallback(
    async (params: EnqueueParams): Promise<OfflineAction> => {
      if (!queueRef.current) throw new Error("SyncProvider not initialized");
      const action = await queueRef.current.enqueue(params);
      await refreshStatus();
      // Attempt sync immediately if online
      if (checkOnline() && managerRef.current) {
        managerRef.current.processQueue().then(refreshStatus);
      }
      return action;
    },
    [refreshStatus],
  );

  const retryAll = useCallback(async () => {
    if (!queueRef.current) return;
    await queueRef.current.resetAllFailed();
    await refreshStatus();
    if (managerRef.current) {
      managerRef.current.processQueue().then(refreshStatus);
    }
  }, [refreshStatus]);

  const processQueueCb = useCallback(async () => {
    if (!managerRef.current) return;
    await managerRef.current.processQueue();
    await refreshStatus();
  }, [refreshStatus]);

  const getAllActionsCb = useCallback(async (): Promise<OfflineAction[]> => {
    if (!queueRef.current) return [];
    return queueRef.current.getAll();
  }, []);

  const clearSynced = useCallback(async () => {
    if (!queueRef.current) return;
    await queueRef.current.clearSynced();
    await refreshStatus();
  }, [refreshStatus]);

  const retryOne = useCallback(async (id: string) => {
    if (!queueRef.current) return;
    await queueRef.current.resetFailed(id);
    await refreshStatus();
    if (managerRef.current) {
      managerRef.current.processQueue().then(refreshStatus);
    }
  }, [refreshStatus]);

  return (
    <SyncContext.Provider
      value={{
        enqueueOffline,
        syncStatus,
        online,
        retryAll,
        processQueue: processQueueCb,
        getAllActions: getAllActionsCb,
        clearSynced,
        retryOne,
      }}
    >
      {children}
    </SyncContext.Provider>
  );
}

/** Hook to access the offline sync system */
export function useSync() {
  return useContext(SyncContext);
}
