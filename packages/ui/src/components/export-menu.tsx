"use client";

/**
 * EduZim — ExportMenu
 * ====================
 * Drop-in split button that exports the current page's records
 * to .xlsx or .pdf entirely client-side (works in guest mode).
 *
 * Usage:
 *
 *   <ExportMenu
 *       filename="students"
 *       title="Students — Form 2A"
 *       columns={[
 *           { key: "student_code", label: "Code" },
 *           { key: "first_name",   label: "First name" },
 *           { key: "last_name",    label: "Last name" },
 *       ]}
 *       rows={students}
 *   />
 */

import * as React from "react";
import { Download, FileSpreadsheet, FileText } from "lucide-react";
import { cn } from "../lib/utils";
import { exportToXlsx, exportToPdf, type ExportColumn, type ExportOptions } from "../lib/export";

export interface ExportMenuProps<T> {
    filename: string;
    title?: string;
    subtitle?: string;
    columns: ExportColumn<T>[];
    rows: T[];
    meta?: ExportOptions<T>["meta"];
    className?: string;
    label?: string;
    disabled?: boolean;
    /** Render variant (default | compact for table headers) */
    variant?: "default" | "compact";
}

export function ExportMenu<T>({
    filename, title, subtitle, columns, rows, meta,
    className, label = "Export", disabled, variant = "default",
}: ExportMenuProps<T>) {
    const [open, setOpen] = React.useState(false);
    const rootRef = React.useRef<HTMLDivElement | null>(null);
    const firstItemRef = React.useRef<HTMLButtonElement | null>(null);

    React.useEffect(() => {
        if (!open) return;
        const onClick = (e: MouseEvent) => {
            if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
        };
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") setOpen(false);
        };
        window.addEventListener("mousedown", onClick);
        window.addEventListener("keydown", onKey);
        // Focus the first item for keyboard users.
        firstItemRef.current?.focus();
        return () => {
            window.removeEventListener("mousedown", onClick);
            window.removeEventListener("keydown", onKey);
        };
    }, [open]);

    const hasRows = rows.length > 0;
    const reallyDisabled = disabled || !hasRows;

    const handleExcel = () => {
        exportToXlsx({ filename, title, subtitle, columns, rows, meta });
        setOpen(false);
    };
    const handlePdf = () => {
        exportToPdf({ filename, title, subtitle, columns, rows, meta });
        setOpen(false);
    };

    const baseBtn =
        "inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";
    const compactBtn =
        "inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-1.5 text-xs font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

    return (
        <div ref={rootRef} className={cn("relative inline-block text-left", className)}>
            <button
                type="button"
                disabled={reallyDisabled}
                aria-haspopup="menu"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
                className={variant === "compact" ? compactBtn : baseBtn}
                data-testid="export-menu-trigger"
            >
                <Download className={variant === "compact" ? "h-3.5 w-3.5" : "h-4 w-4"} />
                {label}
                {!hasRows && <span className="ml-1 text-xs text-muted-foreground">(empty)</span>}
            </button>
            {open && (
                <div
                    role="menu"
                    aria-label="Export options"
                    className="absolute right-0 z-50 mt-2 w-48 origin-top-right rounded-md border border-input bg-popover p-1 shadow-md focus:outline-none"
                    data-testid="export-menu"
                >
                    <button
                        ref={firstItemRef}
                        type="button"
                        role="menuitem"
                        onClick={handleExcel}
                        className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm transition-colors hover:bg-accent focus:bg-accent focus:outline-none"
                        data-testid="export-menu-xlsx"
                    >
                        <FileSpreadsheet className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                        <span>Download Excel (.xlsx)</span>
                    </button>
                    <button
                        type="button"
                        role="menuitem"
                        onClick={handlePdf}
                        className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm transition-colors hover:bg-accent focus:bg-accent focus:outline-none"
                        data-testid="export-menu-pdf"
                    >
                        <FileText className="h-4 w-4 text-rose-600" aria-hidden="true" />
                        <span>Download PDF (.pdf)</span>
                    </button>
                </div>
            )}
        </div>
    );
}

export type { ExportColumn, ExportOptions } from "../lib/export";
