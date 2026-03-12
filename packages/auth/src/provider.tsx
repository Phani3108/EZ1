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

// ─── Types ───

export interface AuthState {
  user: MeData | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginData) => Promise<void>;
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

  const logout = useCallback(() => {
    clearTokens();
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
      logout,
      hasPermission,
      hasAnyPermission,
      hasRole,
    }),
    [user, isLoading, login, logout, hasPermission, hasAnyPermission, hasRole]
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
