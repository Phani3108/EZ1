/**
 * EduZim Auth — React Context Provider
 * =======================================
 * Provides auth state (user, permissions, loading) to the component tree.
 * Handles login, logout, refresh, and /auth/me fetching.
 *
 * Refresh tokens live in an httpOnly cookie managed by the API gateway.
 * The provider only stores the access token in memory.
 */

"use client";

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useMemo,
} from "react";
import type { MeData, LoginData } from "@eduzim/api-client";
import { setTokens, clearTokens, getAccessToken } from "./tokens";

// ─── Guest mode (pre-production exploration) ─────────────────────────────
// When the user clicks "Continue as Guest", we bypass the API entirely and
// hydrate the AuthProvider with a synthetic MeData. A small marker is kept
// in sessionStorage so that the session survives page reloads even when no
// backend is reachable.

const GUEST_STORAGE_KEY = "eduzim_guest_user";

function readStoredGuest(): MeData | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(GUEST_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as MeData) : null;
  } catch {
    return null;
  }
}

function writeStoredGuest(user: MeData | null) {
  if (typeof window === "undefined") return;
  try {
    if (user) sessionStorage.setItem(GUEST_STORAGE_KEY, JSON.stringify(user));
    else sessionStorage.removeItem(GUEST_STORAGE_KEY);
  } catch {
    /* storage unavailable */
  }
}

// ─── Types ───

export interface AuthState {
  user: MeData | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginData) => Promise<void>;
  /**
   * Pre-production helper: hydrate auth state from a synthetic MeData payload
   * without contacting the API. Persisted in sessionStorage so reloads work.
   */
  loginAsGuest: (user: MeData) => void;
  logout: () => void;
  hasPermission: (perm: string) => boolean;
  hasAnyPermission: (...perms: string[]) => boolean;
  hasRole: (role: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

// ─── Provider Props ───

interface AuthProviderProps {
  children: React.ReactNode;
  fetchMe: () => Promise<MeData>;
  /** Attempts cookie-based refresh. Returns login data or null. */
  refreshTokens: () => Promise<LoginData | null>;
  onLogout?: () => void;
}

// ─── Provider ───

export function AuthProvider({
  children,
  fetchMe,
  refreshTokens,
  onLogout,
}: AuthProviderProps) {
  const [user, setUser] = useState<MeData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, attempt to restore session via refresh-token cookie
  const loadUser = useCallback(async () => {
    setIsLoading(true);
    // Guest session takes priority and is fully offline.
    const guest = readStoredGuest();
    if (guest) {
      setUser(guest);
      setIsLoading(false);
      return;
    }
    try {
      const tokenData = await refreshTokens();
      if (tokenData) {
        setTokens(tokenData.access_token, tokenData.expires_in);
        const me = await fetchMe();
        setUser(me);
      }
    } catch {
      // No valid session — user will be directed to the login page
    } finally {
      setIsLoading(false);
    }
  }, [fetchMe, refreshTokens]);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(
    async (data: LoginData) => {
      setTokens(data.access_token, data.expires_in);
      const me = await fetchMe();
      setUser(me);
    },
    [fetchMe]
  );

  const loginAsGuest = useCallback((guestUser: MeData) => {
    // Synthetic short-lived in-memory token; satisfies any code that calls
    // getAccessToken() while in guest mode. Real API calls will still fail —
    // that is acceptable because guest mode is for UI exploration only.
    setTokens("guest-mode-token", 60 * 60);
    writeStoredGuest(guestUser);
    setUser(guestUser);
    setIsLoading(false);
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    writeStoredGuest(null);
    setUser(null);
    onLogout?.();
  }, [onLogout]);

  const hasPermission = useCallback(
    (perm: string) => {
      if (!user) return false;
      if (user.permissions.includes("*")) return true;
      return user.permissions.includes(perm);
    },
    [user]
  );

  const hasAnyPermission = useCallback(
    (...perms: string[]) => perms.some((p) => hasPermission(p)),
    [hasPermission]
  );

  const hasRole = useCallback(
    (role: string) => user?.roles.includes(role) ?? false,
    [user]
  );

  const value = useMemo<AuthState>(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      loginAsGuest,
      logout,
      hasPermission,
      hasAnyPermission,
      hasRole,
    }),
    [user, isLoading, login, loginAsGuest, logout, hasPermission, hasAnyPermission, hasRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ─── Hook ───

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within <AuthProvider>");
  }
  return ctx;
}
