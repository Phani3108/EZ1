/**
 * @eduzim/offline-core — Network Tests
 * Tests for isOnline, onOnline, onOffline
 */
import { describe, it, expect, afterEach, vi } from "vitest";
import { isOnline, onOnline, onOffline } from "../src/network";

describe("Network", () => {
  const unsubs: (() => void)[] = [];
  afterEach(() => {
    unsubs.forEach((u) => u());
    unsubs.length = 0;
  });

  it("isOnline returns true in jsdom (navigator.onLine)", () => {
    expect(isOnline()).toBe(true);
  });

  it("onOnline fires when 'online' event dispatched", () => {
    const cb = vi.fn();
    unsubs.push(onOnline(cb));
    window.dispatchEvent(new Event("online"));
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("onOffline fires when 'offline' event dispatched", () => {
    const cb = vi.fn();
    unsubs.push(onOffline(cb));
    window.dispatchEvent(new Event("offline"));
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("unsubscribe stops further callbacks", () => {
    const cb = vi.fn();
    const unsub = onOnline(cb);
    window.dispatchEvent(new Event("online"));
    expect(cb).toHaveBeenCalledTimes(1);

    unsub();
    window.dispatchEvent(new Event("online"));
    expect(cb).toHaveBeenCalledTimes(1); // no new call
  });

  it("multiple listeners are independent", () => {
    const cb1 = vi.fn();
    const cb2 = vi.fn();
    unsubs.push(onOnline(cb1));
    const unsub2 = onOnline(cb2);

    window.dispatchEvent(new Event("online"));
    expect(cb1).toHaveBeenCalledTimes(1);
    expect(cb2).toHaveBeenCalledTimes(1);

    unsub2();
    window.dispatchEvent(new Event("online"));
    expect(cb1).toHaveBeenCalledTimes(2);
    expect(cb2).toHaveBeenCalledTimes(1);
  });
});
