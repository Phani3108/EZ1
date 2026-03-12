/**
 * BulkUpload — drag-and-drop CSV / Excel / PDF uploader.
 * CSV files are parsed client-side for immediate preview.
 * Excel & PDF are forwarded to the server as binary.
 */

"use client";

import React, { useRef, useState, useCallback } from "react";
import { Upload, X, FileText, Table, FileUp, CheckCircle } from "lucide-react";

export interface BulkUploadResult {
  file: File;
  /** Parsed rows (CSV preview only). Empty for binary uploads. */
  rows: Record<string, string>[];
  headers: string[];
}

interface BulkUploadProps {
  accept?: string;
  maxSizeMB?: number;
  onUpload: (result: BulkUploadResult) => void | Promise<void>;
  label?: string;
  hint?: string;
  className?: string;
}

function parseCsv(text: string): { headers: string[]; rows: Record<string, string>[] } {
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) return { headers: [], rows: [] };
  const headers = lines[0].split(",").map((h) => h.trim().replace(/^"|"$/g, ""));
  const rows = lines.slice(1).map((line) => {
    const values = line.split(",").map((v) => v.trim().replace(/^"|"$/g, ""));
    const row: Record<string, string> = {};
    headers.forEach((h, i) => { row[h] = values[i] ?? ""; });
    return row;
  });
  return { headers, rows };
}

const FILE_ICONS: Record<string, React.ReactNode> = {
  csv: <Table className="h-5 w-5 text-green-600" />,
  xlsx: <Table className="h-5 w-5 text-blue-600" />,
  xls: <Table className="h-5 w-5 text-blue-600" />,
  pdf: <FileText className="h-5 w-5 text-red-600" />,
};

export function BulkUpload({
  accept = ".csv,.xlsx,.xls,.pdf,.doc,.docx",
  maxSizeMB = 10,
  onUpload,
  label = "Upload file",
  hint,
  className = "",
}: BulkUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ headers: string[]; rows: Record<string, string>[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [done, setDone] = useState(false);

  const ext = file?.name.split(".").pop()?.toLowerCase() ?? "";

  const processFile = useCallback(
    async (f: File) => {
      setError(null);
      setDone(false);

      if (f.size > maxSizeMB * 1024 * 1024) {
        setError(`File is too large (max ${maxSizeMB} MB).`);
        return;
      }

      setFile(f);
      const fileExt = f.name.split(".").pop()?.toLowerCase() ?? "";

      let headers: string[] = [];
      let rows: Record<string, string>[] = [];

      if (fileExt === "csv") {
        try {
          const text = await f.text();
          const parsed = parseCsv(text);
          headers = parsed.headers;
          rows = parsed.rows;
          setPreview(parsed);
        } catch {
          setPreview(null);
        }
      } else {
        setPreview(null);
      }

      setIsProcessing(true);
      try {
        await onUpload({ file: f, rows, headers });
        setDone(true);
      } catch (err: unknown) {
        setError((err as Error)?.message ?? "Upload failed. Please try again.");
      } finally {
        setIsProcessing(false);
      }
    },
    [maxSizeMB, onUpload],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const dropped = e.dataTransfer.files[0];
      if (dropped) processFile(dropped);
    },
    [processFile],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0];
      if (selected) processFile(selected);
      e.target.value = "";
    },
    [processFile],
  );

  const reset = () => {
    setFile(null);
    setPreview(null);
    setError(null);
    setDone(false);
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
          isDragging
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30"
        }`}
      >
        <FileUp className={`h-10 w-10 mb-3 ${isDragging ? "text-primary" : "text-muted-foreground/40"}`} />
        <p className="font-medium text-sm">{label}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {hint ?? `Drag and drop, or click to browse. Accepts ${accept}`}
        </p>
        <p className="text-xs text-muted-foreground/60 mt-1">Max {maxSizeMB} MB</p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleChange}
          className="sr-only"
        />
      </div>

      {/* Selected file */}
      {file && (
        <div className={`flex items-center justify-between rounded-lg border px-4 py-3 ${done ? "border-green-200 bg-green-50" : "bg-card"}`}>
          <div className="flex items-center gap-3">
            {done ? <CheckCircle className="h-5 w-5 text-green-600" /> : (FILE_ICONS[ext] ?? <FileText className="h-5 w-5 text-muted-foreground" />)}
            <div>
              <p className="text-sm font-medium">{file.name}</p>
              <p className="text-xs text-muted-foreground">
                {(file.size / 1024).toFixed(1)} KB
                {preview ? ` · ${preview.rows.length} rows` : ""}
                {done ? " · Uploaded" : ""}
              </p>
            </div>
          </div>
          {!isProcessing && (
            <button
              onClick={reset}
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="Remove file"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          {isProcessing && (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
          {error}
        </div>
      )}

      {/* CSV Preview */}
      {preview && preview.rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-xs">
            <thead className="bg-muted/50">
              <tr>
                {preview.headers.map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.rows.slice(0, 5).map((row, i) => (
                <tr key={i} className="border-t">
                  {preview.headers.map((h) => (
                    <td key={h} className="px-3 py-1.5 text-muted-foreground">
                      {row[h] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {preview.rows.length > 5 && (
            <p className="px-3 py-2 text-xs text-muted-foreground border-t bg-muted/20">
              Showing first 5 of {preview.rows.length} rows…
            </p>
          )}
        </div>
      )}
    </div>
  );
}
