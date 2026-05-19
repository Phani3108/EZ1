/**
 * EduZim — Client-side Excel / PDF export helpers
 * ================================================
 * Used by the ExportMenu component to generate downloads
 * directly in the browser. This means downloads work in
 * guest mode (no backend) and online mode alike.
 */

import * as XLSX from "xlsx";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { saveAs } from "file-saver";

export interface ExportColumn<T> {
    /** Property key on the row or a getter function */
    key: keyof T | ((row: T) => unknown);
    /** Display label shown in the header */
    label: string;
    /** Optional numeric/string formatter */
    format?: (value: unknown, row: T) => string;
    /** PDF column width hint */
    width?: number;
}

export interface ExportOptions<T> {
    filename: string;          // base name without extension
    title?: string;            // sheet title / PDF heading
    subtitle?: string;         // optional subtitle line
    columns: ExportColumn<T>[];
    rows: T[];
    /** Extra metadata rows printed at top of sheet / PDF */
    meta?: Array<[string, string | number]>;
}

const PRIMARY_GREEN = "#00843D";
const PRIMARY_YELLOW = "#FCD116";

function todayStamp(): string {
    return new Date().toISOString().slice(0, 10);
}

function cellValue<T>(row: T, col: ExportColumn<T>): unknown {
    const raw = typeof col.key === "function" ? col.key(row) : (row as Record<string, unknown>)[col.key as string];
    return col.format ? col.format(raw, row) : raw;
}

/* ──────────────────────────  Excel  ───────────────────────────── */

export function exportToXlsx<T>(opts: ExportOptions<T>): void {
    const { filename, title, subtitle, meta, columns, rows } = opts;
    const aoa: unknown[][] = [];

    if (title) aoa.push([title]);
    if (subtitle) aoa.push([subtitle]);
    aoa.push([`Generated ${new Date().toLocaleString()}`]);
    if (meta && meta.length) {
        aoa.push([]);
        for (const [k, v] of meta) aoa.push([k, v]);
    }
    aoa.push([]);
    aoa.push(columns.map((c) => c.label));
    for (const row of rows) {
        aoa.push(columns.map((c) => cellValue(row, c) ?? ""));
    }

    const ws = XLSX.utils.aoa_to_sheet(aoa);
    // Width hints
    ws["!cols"] = columns.map((c) => ({ wch: Math.max(c.width ?? 12, c.label.length + 2) }));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, (title ?? "Data").slice(0, 28));
    const buf = XLSX.write(wb, { type: "array", bookType: "xlsx" });
    saveAs(new Blob([buf], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }), `${filename}-${todayStamp()}.xlsx`);
}

/* ──────────────────────────  PDF  ─────────────────────────────── */

export function exportToPdf<T>(opts: ExportOptions<T>): void {
    const { filename, title, subtitle, meta, columns, rows } = opts;
    const doc = new jsPDF({ orientation: columns.length > 6 ? "landscape" : "portrait", unit: "pt", format: "a4" });

    // Header band — Zimbabwe colours
    doc.setFillColor(PRIMARY_GREEN);
    doc.rect(0, 0, doc.internal.pageSize.getWidth(), 56, "F");
    doc.setFillColor(PRIMARY_YELLOW);
    doc.rect(0, 56, doc.internal.pageSize.getWidth(), 4, "F");

    doc.setTextColor(255, 255, 255);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(18);
    doc.text("EduZim", 40, 30);

    doc.setFontSize(10);
    doc.setFont("helvetica", "normal");
    doc.text("Zimbabwe Education Platform", 40, 46);

    let y = 90;
    doc.setTextColor(0, 0, 0);
    if (title) {
        doc.setFont("helvetica", "bold");
        doc.setFontSize(14);
        doc.text(title, 40, y);
        y += 18;
    }
    if (subtitle) {
        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        doc.text(subtitle, 40, y);
        y += 14;
    }
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(100, 100, 100);
    doc.text(`Generated ${new Date().toLocaleString()}`, 40, y);
    y += 12;

    if (meta && meta.length) {
        doc.setFontSize(9);
        doc.setTextColor(50, 50, 50);
        for (const [k, v] of meta) {
            doc.text(`${k}: ${v}`, 40, y);
            y += 12;
        }
    }
    y += 6;

    const head = [columns.map((c) => c.label)];
    const body = rows.map((row) => columns.map((c) => {
        const v = cellValue(row, c);
        return v == null ? "" : String(v);
    }));

    autoTable(doc, {
        head,
        body,
        startY: y,
        margin: { left: 40, right: 40 },
        styles: { font: "helvetica", fontSize: 9, cellPadding: 5 },
        headStyles: { fillColor: [0, 132, 61], textColor: 255, fontStyle: "bold" },
        alternateRowStyles: { fillColor: [245, 247, 245] },
        didDrawPage: () => {
            const pageHeight = doc.internal.pageSize.getHeight();
            doc.setFontSize(8);
            doc.setTextColor(120, 120, 120);
            doc.text(`EduZim • Page ${doc.getCurrentPageInfo().pageNumber}`, 40, pageHeight - 20);
        },
    });

    doc.save(`${filename}-${todayStamp()}.pdf`);
}

/* ──────────────────────────  Report Card PDF (rich, single subject) ────── */

export interface ReportCardSubject {
    code: string;
    name: string;
    mark: number | null;
    max_marks: number;
    grade?: string;
    remarks?: string;
}

export interface ReportCardOptions {
    school_name: string;
    school_address?: string;
    term_name: string;
    academic_year: string;
    student_name: string;
    student_code: string;
    class_name: string;
    date_of_issue?: string;
    attendance_pct?: number;
    teacher_comment?: string;
    head_comment?: string;
    subjects: ReportCardSubject[];
}

export function exportReportCardPdf(opts: ReportCardOptions): void {
    const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
    const pageW = doc.internal.pageSize.getWidth();

    // Header
    doc.setFillColor(PRIMARY_GREEN);
    doc.rect(0, 0, pageW, 80, "F");
    doc.setFillColor(PRIMARY_YELLOW);
    doc.rect(0, 80, pageW, 5, "F");

    doc.setTextColor(255, 255, 255);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(22);
    doc.text(opts.school_name, 40, 36);

    doc.setFontSize(10);
    doc.setFont("helvetica", "normal");
    if (opts.school_address) doc.text(opts.school_address, 40, 54);
    doc.text(`${opts.term_name} • ${opts.academic_year}`, 40, 70);

    let y = 110;
    doc.setTextColor(0, 0, 0);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.text("STUDENT REPORT CARD", pageW / 2, y, { align: "center" });
    y += 24;

    // Student details box
    doc.setDrawColor(0, 132, 61);
    doc.setLineWidth(1);
    doc.rect(40, y, pageW - 80, 70);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    const detLeftX = 50;
    const detRightX = pageW / 2 + 10;
    doc.text("Name:", detLeftX, y + 18);
    doc.text("Student Code:", detLeftX, y + 36);
    doc.text("Class:", detLeftX, y + 54);
    doc.text("Issued:", detRightX, y + 18);
    doc.text("Attendance:", detRightX, y + 36);
    doc.setFont("helvetica", "normal");
    doc.text(opts.student_name, detLeftX + 90, y + 18);
    doc.text(opts.student_code, detLeftX + 90, y + 36);
    doc.text(opts.class_name, detLeftX + 90, y + 54);
    doc.text(opts.date_of_issue ?? todayStamp(), detRightX + 90, y + 18);
    doc.text(opts.attendance_pct != null ? `${opts.attendance_pct}%` : "—", detRightX + 90, y + 36);

    y += 80;

    // Subjects table
    const body = opts.subjects.map((s) => [
        s.code,
        s.name,
        s.mark == null ? "—" : `${s.mark}/${s.max_marks}`,
        s.mark == null ? "—" : `${Math.round((s.mark / s.max_marks) * 100)}%`,
        s.grade ?? gradeFor(s.mark, s.max_marks),
        s.remarks ?? "",
    ]);

    autoTable(doc, {
        head: [["Code", "Subject", "Marks", "%", "Grade", "Remarks"]],
        body,
        startY: y,
        margin: { left: 40, right: 40 },
        styles: { font: "helvetica", fontSize: 10, cellPadding: 6 },
        headStyles: { fillColor: [0, 132, 61], textColor: 255 },
        alternateRowStyles: { fillColor: [245, 247, 245] },
    });

    const finalY = (doc as unknown as { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY ?? y;
    let cy = finalY + 24;

    // Average
    const scored = opts.subjects.filter((s) => s.mark != null);
    if (scored.length) {
        const avg = scored.reduce((acc, s) => acc + (s.mark! / s.max_marks) * 100, 0) / scored.length;
        doc.setFont("helvetica", "bold");
        doc.setFontSize(11);
        doc.text(`Overall Average: ${avg.toFixed(1)}%`, 40, cy);
        cy += 18;
    }

    if (opts.teacher_comment) {
        doc.setFont("helvetica", "bold");
        doc.setFontSize(10);
        doc.text("Class Teacher's Comment:", 40, cy);
        cy += 14;
        doc.setFont("helvetica", "normal");
        doc.text(doc.splitTextToSize(opts.teacher_comment, pageW - 80), 40, cy);
        cy += 30;
    }
    if (opts.head_comment) {
        doc.setFont("helvetica", "bold");
        doc.setFontSize(10);
        doc.text("Head Teacher's Comment:", 40, cy);
        cy += 14;
        doc.setFont("helvetica", "normal");
        doc.text(doc.splitTextToSize(opts.head_comment, pageW - 80), 40, cy);
        cy += 30;
    }

    // Footer signatures
    const sigY = Math.max(cy + 20, doc.internal.pageSize.getHeight() - 80);
    doc.setDrawColor(180, 180, 180);
    doc.line(40, sigY, 200, sigY);
    doc.line(pageW - 200, sigY, pageW - 40, sigY);
    doc.setFontSize(9);
    doc.setTextColor(80, 80, 80);
    doc.setFont("helvetica", "normal");
    doc.text("Class Teacher", 40, sigY + 14);
    doc.text("Head Teacher", pageW - 200, sigY + 14);

    doc.save(`report-card-${opts.student_code}-${todayStamp()}.pdf`);
}

function gradeFor(mark: number | null, max: number): string {
    if (mark == null) return "—";
    const pct = (mark / max) * 100;
    if (pct >= 80) return "A";
    if (pct >= 70) return "B";
    if (pct >= 60) return "C";
    if (pct >= 50) return "D";
    if (pct >= 40) return "E";
    return "U";
}
