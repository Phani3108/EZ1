/**
 * Parent-web — API client singleton
 */

import {
  createClient,
  createMockClient,
  authApi,
  studentApi,
  schoolApi,
  attendanceApi,
  feesApi,
  commApi,
  assessmentApi,
} from "@eduzim/api-client";
import { getAccessToken } from "@eduzim/auth";

const useMock = process.env.NEXT_PUBLIC_MOCK_DATA === "true";

const baseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const api = useMock
  ? createMockClient()
  : createClient({
    baseUrl,
    getAccessToken,
    onAuthError: () => {
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    },
  });

export const auth = authApi(api);
export const student = studentApi(api);
export const school = schoolApi(api);
export const attendance = attendanceApi(api);
export const fees = feesApi(api);
export const comm = commApi(api);
export const assessment = assessmentApi(api);
