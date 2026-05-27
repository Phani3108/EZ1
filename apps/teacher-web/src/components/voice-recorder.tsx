/**
 * VoiceRecorder — Phase 11c / T-009.
 *
 * A self-contained record / stop / preview / upload widget. Uses the
 * browser's MediaRecorder API; the resulting Blob is POSTed to
 * `/api/v1/comm/attachments` (the T-008 polymorphic attachment
 * endpoint) tagged with the consumer-supplied `ownerKind` + `ownerId`.
 *
 * Why this lives in teacher-web and not @eduzim/ui: the upload call
 * is teacher-web's api-client. The visual shell is small enough to
 * stay co-located until parent-web needs it too.
 *
 * Failure modes:
 *   - getUserMedia rejected → renders a not-supported notice; the
 *     parent should fall back to text-only entry.
 *   - Upload fails → calls `onError` with a translation-key + the
 *     raw error, so the consumer can decide how to surface it.
 *
 * Microphone permission is requested lazily on the first record
 * click — not on mount. We don't want to prompt the user just for
 * rendering a marks-entry screen.
 */

"use client";

import React, { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@eduzim/ui";
import { Mic, MicOff, Square, Trash2, Upload, AlertCircle } from "lucide-react";

interface VoiceRecorderProps {
  ownerKind: "mark" | "incident" | "message" | "announcement";
  ownerId: string;
  onUploaded?: (attachmentId: string) => void;
  onError?: (key: string, err: unknown) => void;
  /** Max duration in seconds. Hard stop at this mark; default 60s. */
  maxSeconds?: number;
}

type State = "idle" | "recording" | "stopped" | "uploading" | "error";

export function VoiceRecorder({
  ownerKind,
  ownerId,
  onUploaded,
  onError,
  maxSeconds = 60,
}: VoiceRecorderProps) {
  const t = useTranslations("voiceNotes");
  const [state, setState] = useState<State>("idle");
  const [blob, setBlob] = useState<Blob | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stopRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  // Clean up any tracks + intervals + object URLs on unmount.
  useEffect(() => {
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
      if (stopRef.current) clearTimeout(stopRef.current);
      if (recorderRef.current?.state === "recording") {
        recorderRef.current.stop();
      }
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, []);

  const supported =
    typeof window !== "undefined" &&
    typeof navigator !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof window.MediaRecorder === "function";

  const handleStart = async () => {
    if (!supported) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Prefer audio/webm (smaller); fall back to default. The
      // backend allow-list accepts both webm + mpeg + ogg.
      let mimeType = "audio/webm";
      if (!window.MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = "";
      }
      const rec = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const out = new Blob(chunksRef.current, {
          type: rec.mimeType || "audio/webm",
        });
        if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = URL.createObjectURL(out);
        setBlob(out);
        setState("stopped");
        stream.getTracks().forEach((tr) => tr.stop());
      };
      rec.start();
      setElapsed(0);
      tickRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
      stopRef.current = setTimeout(() => {
        // Auto-stop at the max duration so a forgotten recording
        // doesn't fill the user's storage quota.
        if (rec.state === "recording") rec.stop();
      }, maxSeconds * 1000);
      setState("recording");
    } catch (err) {
      setState("error");
      onError?.("permissionDenied", err);
    }
  };

  const handleStop = () => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
    if (tickRef.current) clearInterval(tickRef.current);
    if (stopRef.current) clearTimeout(stopRef.current);
  };

  const handleDiscard = () => {
    setBlob(null);
    setElapsed(0);
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setState("idle");
  };

  const handleUpload = async () => {
    if (!blob) return;
    setState("uploading");
    const fd = new FormData();
    fd.append("owner_kind", ownerKind);
    fd.append("owner_id", ownerId);
    const ext = (blob.type.split("/")[1] || "webm").split(";")[0];
    fd.append("file", blob, `voice-note-${Date.now()}.${ext}`);

    try {
      // We post directly via fetch rather than the api-client because
      // the api-client's typed helpers don't (yet) support multipart.
      const baseUrl =
        process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      // Auth token retrieval uses the same in-memory path the api-client
      // uses; we import lazily to avoid pulling auth into the SSR bundle.
      const { getAccessToken } = await import("@eduzim/auth");
      const tok = getAccessToken();
      const res = await fetch(`${baseUrl}/api/v1/comm/attachments`, {
        method: "POST",
        headers: tok ? { Authorization: `Bearer ${tok}` } : undefined,
        body: fd,
      });
      if (!res.ok) {
        throw new Error(`upload failed: ${res.status}`);
      }
      const body = (await res.json()) as { data: { id: string } };
      onUploaded?.(body.data.id);
      handleDiscard();
    } catch (err) {
      setState("error");
      onError?.("uploadFailed", err);
    }
  };

  if (!supported) {
    return (
      <div
        role="status"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground"
        data-testid="voice-recorder-unsupported"
      >
        <MicOff className="h-3.5 w-3.5" /> {t("notSupported")}
      </div>
    );
  }

  return (
    <div
      className="inline-flex items-center gap-2"
      data-testid="voice-recorder"
    >
      {state === "idle" && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleStart}
          data-testid="voice-record-start"
        >
          <Mic className="h-3.5 w-3.5 mr-1" />
          {t("record")}
        </Button>
      )}

      {state === "recording" && (
        <>
          <span
            className="inline-flex items-center gap-1 text-xs text-red-700"
            data-testid="voice-recording-indicator"
          >
            <span className="h-2 w-2 rounded-full bg-red-600 animate-pulse" />
            {elapsed}s
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleStop}
            data-testid="voice-record-stop"
          >
            <Square className="h-3.5 w-3.5 mr-1" />
            {t("stop")}
          </Button>
        </>
      )}

      {state === "stopped" && blob && objectUrlRef.current && (
        <>
          <audio
            src={objectUrlRef.current}
            controls
            className="h-8"
            data-testid="voice-recorder-preview"
          />
          <Button
            type="button"
            size="sm"
            onClick={handleUpload}
            data-testid="voice-record-upload"
          >
            <Upload className="h-3.5 w-3.5 mr-1" />
            {t("upload")}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleDiscard}
            data-testid="voice-record-discard"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </>
      )}

      {state === "uploading" && (
        <span className="text-xs text-muted-foreground">{t("uploading")}</span>
      )}

      {state === "error" && (
        <span
          className="inline-flex items-center gap-1 text-xs text-red-700"
          data-testid="voice-recorder-error"
        >
          <AlertCircle className="h-3.5 w-3.5" /> {t("error")}
          <button
            type="button"
            onClick={() => setState("idle")}
            className="underline ml-1"
          >
            {t("retry")}
          </button>
        </span>
      )}
    </div>
  );
}
