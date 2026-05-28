/**
 * AttachmentImage — Phase 19a wires the Phase 17b thumbnail flow.
 *
 * Before this primitive landed, every caller that wanted to render an
 * `image/*` Attachment hit `/comm/attachments/{id}` for the full bytes,
 * even on long announcement feeds + curriculum trees on phones. The
 * thumbnail endpoint (`/comm/attachments/{id}/thumbnail`) had been live
 * since Phase 17b but had zero usage.
 *
 * Usage:
 *
 *   <AttachmentImage
 *     attachmentId={a.id}
 *     hasThumbnail={a.has_thumbnail}
 *     filename={a.filename}
 *     gatewayBase={API_BASE}
 *   />
 *
 * Behaviour:
 *  - When `hasThumbnail` is true, lazily renders the 256x256 JPEG.
 *    Clicking opens the full attachment in a new tab.
 *  - When `hasThumbnail` is false (old upload, non-image, or Pillow
 *    fallback path), renders a placeholder pill with the filename.
 *  - `loading="lazy"` so feeds with many attachments don't kick off
 *    every request at once.
 */
"use client";

import React from "react";

export interface AttachmentImageProps {
  attachmentId: string;
  hasThumbnail: boolean;
  filename?: string;
  /**
   * Absolute base URL for the gateway. Pass `process.env.NEXT_PUBLIC_API_BASE`
   * (or the app's API client base) at the caller. Defaults to relative
   * `/api/v1/...` which works when the app + gateway share a host.
   */
  gatewayBase?: string;
  /** Tailwind sizing classes. Defaults to a tile that fits a feed. */
  className?: string;
  /** Optional alt text override. */
  alt?: string;
}

export function AttachmentImage({
  attachmentId,
  hasThumbnail,
  filename,
  gatewayBase = "",
  className = "h-32 w-32 rounded-md object-cover",
  alt,
}: AttachmentImageProps) {
  const fullUrl = `${gatewayBase}/api/v1/comm/attachments/${attachmentId}/download`;
  const thumbUrl = `${gatewayBase}/api/v1/comm/attachments/${attachmentId}/thumbnail`;
  const safeAlt = alt ?? filename ?? "attachment";

  if (!hasThumbnail) {
    return (
      <a
        href={fullUrl}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-2 rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground hover:bg-muted"
      >
        <svg
          aria-hidden="true"
          className="h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
        </svg>
        <span className="max-w-[12rem] truncate">{filename ?? "Attachment"}</span>
      </a>
    );
  }

  return (
    <a
      href={fullUrl}
      target="_blank"
      rel="noreferrer"
      className="inline-block"
      aria-label={`Open ${safeAlt} full-size`}
    >
      <img
        src={thumbUrl}
        alt={safeAlt}
        loading="lazy"
        className={className}
      />
    </a>
  );
}
