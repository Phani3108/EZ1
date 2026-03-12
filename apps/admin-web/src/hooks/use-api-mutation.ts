/**
 * useApiMutation — Lightweight mutation hook for create/update operations.
 * Returns mutate(), isSubmitting, and error state.
 */

"use client";

import { useState, useCallback } from "react";
import { getErrorMessage, withRequestId, getErrorDetails } from "@/lib/errors";

interface MutationError {
  message: string;
  requestId: string | null;
  details: Record<string, unknown> | null;
}

interface MutationState<TInput, TResult> {
  mutate: (input: TInput) => Promise<TResult | null>;
  isSubmitting: boolean;
  error: MutationError | null;
  clearError: () => void;
}

export function useApiMutation<TInput, TResult>(
  fn: (input: TInput) => Promise<{ data: TResult }>,
  options?: { onSuccess?: (data: TResult) => void }
): MutationState<TInput, TResult> {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<MutationError | null>(null);

  const mutate = useCallback(
    async (input: TInput): Promise<TResult | null> => {
      setIsSubmitting(true);
      setError(null);
      try {
        const result = await fn(input);
        options?.onSuccess?.(result.data);
        return result.data;
      } catch (err) {
        setError({
          message: getErrorMessage(err),
          requestId: withRequestId(err),
          details: getErrorDetails(err),
        });
        return null;
      } finally {
        setIsSubmitting(false);
      }
    },
    [fn, options]
  );

  const clearError = useCallback(() => setError(null), []);

  return { mutate, isSubmitting, error, clearError };
}
