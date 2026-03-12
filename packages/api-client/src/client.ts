/**
 * EduZim API Client — Core HTTP Client
 * ======================================
 * Wraps fetch with:
 *  - X-Request-Id injection
 *  - Standard envelope parsing ({data,meta} / {error})
 *  - Token injection via callback
 *  - Refresh flow support (cookie-based — credentials: "include")
 */

import { v4 as uuidv4 } from "uuid";
import type { ApiSuccess, ApiErrorDetail, ApiMeta } from "./types";

// ─── Types ───

export interface ClientConfig {
  baseUrl: string;
  getAccessToken?: () => string | null;
  /** Called on 401 to attempt refresh. Returns new access token or null. */
  onTokenExpired?: () => Promise<string | null>;
  onAuthError?: () => void; // e.g. redirect to login
}

export class ApiError extends Error {
  public code: string;
  public status: number;
  public details: Record<string, unknown>;
  public requestId: string;

  constructor(status: number, err: ApiErrorDetail) {
    super(err.message);
    this.name = "ApiError";
    this.code = err.code;
    this.status = status;
    this.details = err.details;
    this.requestId = err.request_id;
  }
}

// ─── Client ───

export function createClient(config: ClientConfig) {
  const { baseUrl } = config;

  async function request<T>(
    method: string,
    path: string,
    options?: {
      body?: unknown;
      params?: Record<string, string>;
      headers?: Record<string, string>;
    }
  ): Promise<{ data: T; meta: ApiMeta }> {
    const requestId = uuidv4();
    const url = new URL(path, baseUrl);

    if (options?.params) {
      Object.entries(options.params).forEach(([k, v]) =>
        url.searchParams.set(k, v)
      );
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Request-Id": requestId,
      ...options?.headers,
    };

    const token = config.getAccessToken?.();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    let res = await fetch(url.toString(), {
      method,
      headers,
      credentials: "include",
      body: options?.body ? JSON.stringify(options.body) : undefined,
    });

    // If 401, attempt refresh once (cookie sent automatically)
    if (res.status === 401 && config.onTokenExpired) {
      const newToken = await config.onTokenExpired();
      if (newToken) {
        headers["Authorization"] = `Bearer ${newToken}`;
        res = await fetch(url.toString(), {
          method,
          headers,
          credentials: "include",
          body: options?.body ? JSON.stringify(options.body) : undefined,
        });
      }
    }

    const json = await res.json();

    // Error envelope
    if (json.error) {
      if (json.error.code === "UNAUTHORIZED" && config.onAuthError) {
        config.onAuthError();
      }
      throw new ApiError(res.status, json.error);
    }

    return { data: json.data as T, meta: json.meta as ApiMeta };
  }

  return {
    get<T>(path: string, params?: Record<string, string>) {
      return request<T>("GET", path, { params });
    },
    post<T>(path: string, body?: unknown) {
      return request<T>("POST", path, { body });
    },
    put<T>(path: string, body?: unknown) {
      return request<T>("PUT", path, { body });
    },
    patch<T>(path: string, body?: unknown) {
      return request<T>("PATCH", path, { body });
    },
    delete<T>(path: string) {
      return request<T>("DELETE", path);
    },
  };
}

export type ApiClient = ReturnType<typeof createClient>;
