/**
 * Admin-web — Auth Providers wrapper
 * Wires @eduzim/auth to the admin API client.
 * Refresh tokens are managed via httpOnly cookie by the gateway.
 */

"use client";

import React from "react";
import { AuthProvider } from "@eduzim/auth";
import { auth } from "@/lib/api";
import type { LoginData, MeData } from "@eduzim/api-client";
import { useRouter } from "next/navigation";

async function fetchMe(): Promise<MeData> {
  const { data } = await auth.me();
  return data;
}

async function refreshTokens(): Promise<LoginData | null> {
  try {
    const { data } = await auth.refresh();
    return data;
  } catch {
    return null;
  }
}

export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  return (
    <AuthProvider
      fetchMe={fetchMe}
      refreshTokens={refreshTokens}
      onLogout={() => router.push("/login")}
    >
      {children}
    </AuthProvider>
  );
}
