/**
 * Parent-web error utilities — mirrors admin-web/lib/errors.ts.
 */

import { ApiError } from "@eduzim/api-client";

export function withRequestId(error: unknown): string | null {
  if (error instanceof ApiError) {
    return error.requestId || null;
  }
  return null;
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "An unexpected error occurred";
}

export function getErrorDetails(error: unknown): Record<string, unknown> | null {
  if (error instanceof ApiError && error.details && Object.keys(error.details).length > 0) {
    return error.details;
  }
  return null;
}
