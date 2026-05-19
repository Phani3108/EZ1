/**
 * Invoices — list with status/student filters, create invoice sheet.
 * UX: Serious, institutional. Status color coding minimal (neutral badges).
 * Permission: fees:read (list), fees:write (create)
 */

"use client";

import React, { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  Button, Badge, Select,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  ExportMenu,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { Invoice, Student, FeeStructure } from "@eduzim/api-client";
import { fees, student as studentApi } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { FileText, Plus } from "lucide-react";

function statusVariant(status: string) {
  switch (status) {
    case "PAID": return "default" as const;
    case "PARTIAL": return "secondary" as const;
    case "OVERDUE": return "destructive" as const;
    default: return "outline" as const;
  }
}

export default function InvoicesPage() {
  const t = useTranslations("fees");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");

  // Create form state
  const [formStudentId, setFormStudentId] = useState("");
  const [formStructureId, setFormStructureId] = useState("");
  const [formDueDate, setFormDueDate] = useState("");

  // Data
  const { data: invoices, isLoading, error, refetch } = useApiQuery(
    () => fees.listInvoices(statusFilter ? { status: statusFilter } : undefined),
    [statusFilter],
  );
  const { data: students } = useApiQuery(() => studentApi.list(), []);
  const { data: structures } = useApiQuery(() => fees.listStructures(), []);

  const studentMap = useMemo(() => {
    const m = new Map<string, Student>();
    students?.forEach((s: Student) => m.set(s.id, s));
    return m;
  }, [students]);

  const studentOptions = useMemo(() => {
    if (!students) return [];
    return students.map((s: Student) => ({
      value: s.id,
      label: `${s.first_name} ${s.last_name}`,
    }));
  }, [students]);

  const structureOptions = useMemo(() => {
    if (!structures) return [];
    return structures.map((fs: FeeStructure) => ({
      value: fs.id,
      label: `${fs.name} ($${fs.total.toFixed(2)})`,
    }));
  }, [structures]);

  const statusOptions = [
    { value: "", label: t("allStatuses") },
    { value: "PENDING", label: t("pending") },
    { value: "PARTIAL", label: t("partial") },
    { value: "PAID", label: t("paidStatus") },
    { value: "OVERDUE", label: t("overdue") },
  ];

  const { mutate: createInvoice, isSubmitting, error: createError } = useApiMutation(
    (data: Record<string, unknown>) => fees.createInvoice(data),
    {
      onSuccess: () => {
        setSheetOpen(false);
        setFormStudentId("");
        setFormStructureId("");
        setFormDueDate("");
        refetch();
      },
    },
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formStudentId || !formStructureId || !formDueDate) return;
    createInvoice({
      student_id: formStudentId,
      fee_structure_id: formStructureId,
      due_date: formDueDate,
    });
  };

  return (
    <RouteGuard permissions={["fees:read"]} onUnauthenticated={() => { }}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <PageHeader title={t("invoices")} />
          <div className="flex items-center gap-2">
            <ExportMenu
              filename="invoices"
              title="Invoices"
              subtitle={`${invoices?.length ?? 0} invoice(s)${statusFilter ? ` · ${statusFilter}` : ""}`}
              columns={[
                { key: (i: Invoice) => {
                    const s = studentMap.get(i.student_id);
                    return s ? `${s.first_name} ${s.last_name}` : i.student_id;
                  }, label: "Student", width: 24 },
                { key: "total_amount", label: "Total", width: 12 },
                { key: "paid_amount",  label: "Paid",  width: 12 },
                { key: "balance",      label: "Balance", width: 12 },
                { key: "status",       label: "Status", width: 10 },
                { key: "due_date",     label: "Due date", width: 14 },
              ]}
              rows={invoices ?? []}
            />
            <Button size="sm" onClick={() => setSheetOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              {t("createInvoice")}
            </Button>
          </div>
        </div>

        {/* Create invoice sheet */}
        <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} width="max-w-lg">
          <SheetHeader>
            <SheetTitle>{t("createInvoice")}</SheetTitle>
            <SheetDescription>{t("createInvoiceDescription")}</SheetDescription>
          </SheetHeader>
          <SheetBody>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">{t("studentName")}</label>
                <Select
                  options={studentOptions}
                  placeholder={t("selectStudent")}
                  value={formStudentId}
                  onChange={(e) => setFormStudentId(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">{t("structures")}</label>
                <Select
                  options={structureOptions}
                  placeholder={t("selectStructure")}
                  value={formStructureId}
                  onChange={(e) => setFormStructureId(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">{t("dueDate")}</label>
                <input
                  type="date"
                  value={formDueDate}
                  onChange={(e) => setFormDueDate(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  required
                />
              </div>
              {createError && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {createError.message}
                </div>
              )}
              <Button
                type="submit"
                className="w-full"
                disabled={!formStudentId || !formStructureId || !formDueDate || isSubmitting}
              >
                {isSubmitting ? t("creating") : t("createInvoice")}
              </Button>
            </form>
          </SheetBody>
        </Sheet>

        {/* Filters */}
        <div className="flex items-end gap-4">
          <div className="w-48 space-y-1">
            <label className="text-sm font-medium text-muted-foreground">{t("filterByStatus")}</label>
            <Select
              options={statusOptions}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            />
          </div>
        </div>

        {error && <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />}

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-muted" />)}
          </div>
        ) : !invoices || invoices.length === 0 ? (
          <EmptyState icon={FileText} title={t("noInvoices")} description={t("noInvoicesDescription")} />
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("studentName")}</TableHead>
                  <TableHead className="text-right">{t("amount")}</TableHead>
                  <TableHead className="text-right">{t("paid")}</TableHead>
                  <TableHead className="text-right">{t("balance")}</TableHead>
                  <TableHead>{t("status")}</TableHead>
                  <TableHead>{t("dueDate")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((inv: Invoice) => {
                  const s = studentMap.get(inv.student_id);
                  return (
                    <TableRow key={inv.id}>
                      <TableCell className="font-medium">
                        <a href={`/students/${inv.student_id}`} className="text-primary hover:underline">
                          {s ? `${s.first_name} ${s.last_name}` : inv.student_id.slice(0, 8)}
                        </a>
                      </TableCell>
                      <TableCell className="text-right font-mono">${inv.total_amount.toFixed(2)}</TableCell>
                      <TableCell className="text-right font-mono">${inv.paid_amount.toFixed(2)}</TableCell>
                      <TableCell className="text-right font-mono font-medium">${inv.balance.toFixed(2)}</TableCell>
                      <TableCell><Badge variant={statusVariant(inv.status)}>{inv.status}</Badge></TableCell>
                      <TableCell className="text-sm text-muted-foreground">{inv.due_date}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </RouteGuard>
  );
}
