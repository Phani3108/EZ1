/**
 * ErrorAlert — displays API errors with expandable details and request ID.
 */

"use client";

import React, { useState } from "react";
import { Alert, AlertTitle, AlertDescription } from "@eduzim/ui";
import { AlertTriangle, ChevronDown, ChevronUp, Copy, Check } from "lucide-react";

interface ErrorAlertProps {
  message: string;
  requestId?: string | null;
  details?: Record<string, unknown> | null;
  className?: string;
  onDismiss?: () => void;
}

export function ErrorAlert({ message, requestId, details, className, onDismiss }: ErrorAlertProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const hasDetails = details && Object.keys(details).length > 0;

  const copyRequestId = async () => {
    if (!requestId) return;
    await navigator.clipboard.writeText(requestId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Alert className={className} variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle className="flex items-center justify-between">
        <span>{message}</span>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-xs underline opacity-70 hover:opacity-100"
          >
            Dismiss
          </button>
        )}
      </AlertTitle>

      {(requestId || hasDetails) && (
        <AlertDescription className="mt-2 space-y-2">
          {/* Request ID */}
          {requestId && (
            <div className="flex items-center gap-2 text-xs opacity-80">
              <span>Request ID: {requestId}</span>
              <button
                onClick={copyRequestId}
                className="inline-flex items-center gap-1 hover:opacity-100"
                title="Copy request ID"
              >
                {copied ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </button>
            </div>
          )}

          {/* Expandable details */}
          {hasDetails && (
            <div>
              <button
                onClick={() => setExpanded(!expanded)}
                className="inline-flex items-center gap-1 text-xs underline opacity-70 hover:opacity-100"
              >
                {expanded ? "Hide" : "Show"} details
                {expanded ? (
                  <ChevronUp className="h-3 w-3" />
                ) : (
                  <ChevronDown className="h-3 w-3" />
                )}
              </button>

              {expanded && (
                <pre className="mt-2 max-h-40 overflow-auto rounded bg-destructive/10 p-2 text-xs">
                  {JSON.stringify(details, null, 2)}
                </pre>
              )}
            </div>
          )}
        </AlertDescription>
      )}
    </Alert>
  );
}
