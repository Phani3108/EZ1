"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[EduZim Parent]", error);
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col">
      <div className="h-2 bg-green-600" />

      <div className="flex-1 flex flex-col items-center justify-center px-4 text-center">
        <p className="text-8xl font-black text-muted-foreground/20 select-none">500</p>
        <h1 className="mt-4 text-2xl font-bold">Something went wrong</h1>
        <p className="mt-2 text-muted-foreground max-w-sm">
          An unexpected error occurred. Please try refreshing the page.
        </p>
        {error.digest && (
          <code className="mt-2 text-xs font-mono text-muted-foreground bg-muted px-2 py-1 rounded">
            Ref: {error.digest}
          </code>
        )}
        <div className="mt-6 flex gap-3">
          <button
            onClick={reset}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            Try Again
          </button>
          <Link
            href="/home"
            className="rounded-lg border px-4 py-2 text-sm font-semibold hover:bg-muted"
          >
            Back to Home
          </Link>
        </div>
      </div>

      <div className="h-2 bg-red-600" />
    </div>
  );
}
