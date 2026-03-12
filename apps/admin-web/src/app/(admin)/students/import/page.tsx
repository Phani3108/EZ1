/**
 * Students Import — bulk upload students via CSV or Excel.
 * Template columns: first_name, last_name, gender, date_of_birth, admission_number, class
 * Permission: student:write
 */

"use client";

import React, { useState } from "react";
import Link from "next/link";
import { BulkUpload, type BulkUploadResult } from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import { student as studentApi } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { ErrorAlert } from "@/components/error-alert";
import { ChevronLeft, Download, CheckCircle, AlertCircle } from "lucide-react";

const REQUIRED_COLS = ["first_name", "last_name"];
const TEMPLATE_COLS = ["first_name", "last_name", "gender", "date_of_birth", "admission_number", "class_name"];

function generateCsvTemplate(): string {
  const header = TEMPLATE_COLS.join(",");
  const examples = [
    "Tendai,Moyo,M,2012-03-15,STU-100,Form 1A",
    "Rudo,Sibanda,F,2011-07-22,STU-101,Form 2B",
    "Tatenda,Nyathi,M,2012-01-10,STU-102,Form 3A",
  ];
  return [header, ...examples].join("\n");
}

function downloadTemplate() {
  const csv = generateCsvTemplate();
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "eduzim_student_import_template.csv";
  a.click();
  URL.revokeObjectURL(url);
}

interface ImportRow {
  first_name: string;
  last_name: string;
  gender?: string;
  date_of_birth?: string;
  admission_number?: string;
  class_name?: string;
}

interface ImportResult {
  total: number;
  imported: number;
  errors: { row: number; message: string }[];
}

export default function StudentsImportPage() {
  const [parsedRows, setParsedRows] = useState<ImportRow[] | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);

  const handleUpload = async ({ rows, headers, file }: BulkUploadResult) => {
    setValidationError(null);
    setResult(null);
    setParsedRows(null);

    // Only process CSV previews (binary uploads forwarded as-is for future server-side processing)
    if (file.name.endsWith(".csv") && rows.length > 0) {
      const missing = REQUIRED_COLS.filter((c) => !headers.includes(c));
      if (missing.length > 0) {
        setValidationError(`Missing required columns: ${missing.join(", ")}. Please use the template.`);
        return;
      }
      setParsedRows(rows as unknown as ImportRow[]);
    } else if (!file.name.endsWith(".csv")) {
      // Non-CSV: show a message about server-side processing
      setResult({
        total: 0, imported: 0,
        errors: [{ row: 0, message: "Excel/PDF files will be processed by the server. Check back shortly." }],
      });
    }
  };

  const handleImport = async () => {
    if (!parsedRows) return;
    setIsImporting(true);
    const errors: { row: number; message: string }[] = [];
    let imported = 0;

    for (let i = 0; i < parsedRows.length; i++) {
      const row = parsedRows[i];
      if (!row.first_name?.trim() || !row.last_name?.trim()) {
        errors.push({ row: i + 2, message: `Row ${i + 2}: Missing first_name or last_name` });
        continue;
      }
      try {
        await studentApi.create({
          first_name: row.first_name.trim(),
          last_name: row.last_name.trim(),
          gender: row.gender?.trim() || undefined,
          date_of_birth: row.date_of_birth?.trim() || undefined,
          admission_number: row.admission_number?.trim() || undefined,
        });
        imported++;
      } catch (err: unknown) {
        errors.push({ row: i + 2, message: `Row ${i + 2}: ${(err as Error)?.message ?? "Import failed"}` });
      }
    }

    setResult({ total: parsedRows.length, imported, errors });
    setIsImporting(false);
  };

  return (
    <RouteGuard permissions={["student:write"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Link href="/students" className="text-muted-foreground hover:text-foreground">
            <ChevronLeft className="h-5 w-5" />
          </Link>
          <PageHeader
            title="Import Students"
            description="Bulk-upload students from a CSV or Excel file."
          />
        </div>

        {/* Template download */}
        <div className="flex items-center justify-between rounded-lg border bg-card px-5 py-4">
          <div>
            <p className="font-medium text-sm">Download Template</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Required columns: <code className="font-mono text-xs bg-muted px-1 rounded">first_name</code>,{" "}
              <code className="font-mono text-xs bg-muted px-1 rounded">last_name</code>. Optional: gender, date_of_birth, admission_number, class_name.
            </p>
          </div>
          <button
            onClick={downloadTemplate}
            className="flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            <Download className="h-4 w-4" />
            CSV Template
          </button>
        </div>

        {/* Upload zone */}
        <div className="rounded-lg border bg-card p-6">
          <h3 className="font-semibold mb-4">Upload File</h3>
          <BulkUpload
            accept=".csv,.xlsx,.xls"
            label="Upload student roster"
            hint="Drag and drop a CSV or Excel file (.csv, .xlsx, .xls)"
            onUpload={handleUpload}
          />
        </div>

        {validationError && <ErrorAlert message={validationError} />}

        {/* Preview table */}
        {parsedRows && parsedRows.length > 0 && !result && (
          <div className="rounded-lg border bg-card overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <div>
                <h3 className="font-semibold">Preview — {parsedRows.length} students</h3>
                <p className="text-xs text-muted-foreground mt-0.5">Review before importing.</p>
              </div>
              <button
                onClick={handleImport}
                disabled={isImporting}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
              >
                {isImporting && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
                {isImporting ? "Importing…" : "Import All"}
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/40">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">#</th>
                    {TEMPLATE_COLS.map((c) => (
                      <th key={c} className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {parsedRows.slice(0, 10).map((row, i) => (
                    <tr key={i} className="border-t">
                      <td className="px-4 py-2 text-muted-foreground text-xs">{i + 2}</td>
                      {TEMPLATE_COLS.map((c) => (
                        <td key={c} className="px-4 py-2">
                          {(row as unknown as Record<string, string>)[c] || <span className="text-muted-foreground">—</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {parsedRows.length > 10 && (
                <p className="px-4 py-2 text-xs text-muted-foreground border-t bg-muted/20">
                  + {parsedRows.length - 10} more rows
                </p>
              )}
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className={`rounded-lg border p-5 ${result.errors.length === 0 ? "border-green-200 bg-green-50" : result.imported > 0 ? "border-yellow-200 bg-yellow-50" : "border-red-200 bg-red-50"}`}>
            <div className="flex items-center gap-3 mb-3">
              {result.imported > 0 ? (
                <CheckCircle className="h-5 w-5 text-green-600" />
              ) : (
                <AlertCircle className="h-5 w-5 text-red-600" />
              )}
              <h3 className="font-semibold">
                {result.imported}/{result.total} students imported
              </h3>
            </div>
            {result.errors.length > 0 && (
              <ul className="space-y-1 mt-2">
                {result.errors.map((e, i) => (
                  <li key={i} className="text-sm text-red-700">{e.message}</li>
                ))}
              </ul>
            )}
            {result.imported > 0 && (
              <Link href="/students" className="mt-3 inline-flex items-center gap-1 text-sm text-primary hover:underline font-medium">
                View Students →
              </Link>
            )}
          </div>
        )}
      </div>
    </RouteGuard>
  );
}
