/**
 * Admin-web — API client singleton
 */

import {
  createClient,
  createMockClient,
  authApi,
  schoolApi,
  studentApi,
  attendanceApi,
  feesApi,
  commApi,
  reportsApi,
  usersApi,
  assessmentApi,
  diagnosticsApi,
} from "@eduzim/api-client";
import { getAccessToken, setTokens } from "@eduzim/auth";

const useMock = process.env.NEXT_PUBLIC_MOCK_DATA === "true";

const baseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const api = useMock
  ? createMockClient()
  : createClient({
    baseUrl,
    getAccessToken,
    onTokenExpired: async () => {
      try {
        const { data } = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({}),
        }).then((r) => r.json());
        if (data?.access_token) {
          setTokens(data.access_token, data.expires_in);
          return data.access_token;
        }
      } catch { }
      return null;
    },
    onAuthError: () => {
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    },
  });

export const auth = authApi(api);
export const school = schoolApi(api);
export const student = studentApi(api);
export const attendance = attendanceApi(api);
export const fees = feesApi(api);
export const comm = commApi(api);
export const reports = reportsApi(api);
export const users = usersApi(api);
export const assessment = assessmentApi(api);
export const diagnostics = diagnosticsApi(api);
