/**
 * @eduzim/offline-core — Types compile-time checks
 * These tests ensure the exported types have the expected shape.
 */
import { describe, it, expect } from "vitest";
import type {
  OfflineAction,
  OfflineActionType,
  OfflineStatus,
  CacheEntry,
  SyncHandlerMap,
} from "../src/types";

describe("Types", () => {
  it("OfflineAction has numeric timestamps", () => {
    const a: OfflineAction = {
      id: "1",
      type: "ATTENDANCE",
      schoolId: "s",
      userId: "u",
      deviceId: "d",
      payload: {},
      syncBatchId: "b",
      status: "QUEUED",
      retryCount: 0,
      createdAt: Date.now(),
    };
    expect(typeof a.createdAt).toBe("number");
  });

  it("CacheEntry is generic", () => {
    const c: CacheEntry<{ name: string }> = {
      key: "k",
      data: { name: "hi" },
      expiresAt: Date.now() + 1000,
      lastUpdated: Date.now(),
    };
    expect(c.data.name).toBe("hi");
  });

  it("SyncHandlerMap covers all action types", () => {
    const map: SyncHandlerMap = {
      ATTENDANCE: async () => {},
      MARKS: async () => {},
      ANNOUNCEMENT: async () => {},
    };
    expect(Object.keys(map)).toHaveLength(3);
  });
});
