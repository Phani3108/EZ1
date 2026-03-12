/**
 * withRequestId — utility to extract request ID from ApiError.
 * Returns a string like "Request ID: abc123" for display in error UIs.
 */

import { ApiError } from "@eduzim/api-client";

export function withRequestId(error: unknown): string | null {
  if (error instanceof ApiError) {
    return error.requestId || null;
  }
  return null;
}

/**
 * Extract a user-friendly error message from any caught error.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "An unexpected error occurred";
}

/**
 * Extract error details (field validation errors, etc.) from ApiError.
 */
export function getErrorDetails(error: unknown): Record<string, unknown> | null {
  if (error instanceof ApiError && error.details && Object.keys(error.details).length > 0) {
    return error.details;
  }
  return null;
}
