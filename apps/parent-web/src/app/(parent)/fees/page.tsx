/**
 * Parent Fees — view invoices, balance, and payment history per child.
 */

"use client";

import React, { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, Button, ExportMenu } from "@eduzim/ui";
import { Receipt, Loader2, AlertCircle, ChevronDown, CheckCircle, Clock, XCircle, CreditCard } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { student, fees } from "@/lib/api";
import type { Student, Invoice } from "@eduzim/api-client";
import { PayInvoiceDialog } from "@/components/pay-invoice-dialog";

const STATUS_STYLES: Record<string, string> = {
  PAID: "bg-green-50 text-green-700 ring-1 ring-green-200",
  PARTIAL: "bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200",
  UNPAID: "bg-red-50 text-red-700 ring-1 ring-red-200",
};
const STATUS_ICONS: Record<string, React.ReactNode> = {
  PAID: <CheckCircle className="h-3.5 w-3.5" />,
  PARTIAL: <Clock className="h-3.5 w-3.5" />,
  UNPAID: <XCircle className="h-3.5 w-3.5" />,
};

function fmt(amount: number, currency = "USD") {
  return new Intl.NumberFormat("en-ZW", { style: "currency", currency }).format(amount);
}

export default function ParentFeesPage() {
  const { data: children, isLoading: loadingChildren } = useApiQuery<Student[]>(
    () => student.getMyChildren(),
    [],
  );

  const [selectedChildId, setSelectedChildId] = useState<string>("");
  const childId = selectedChildId || children?.[0]?.id || "";

  const [payInvoice, setPayInvoice] = useState<Invoice | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const { data: invoices, isLoading: loadingInvoices, error } = useApiQuery<Invoice[]>(
    () => {
      if (!childId) return Promise.resolve({ data: [] });
      return fees.listInvoices({ student_id: childId });
    },
    [childId, refreshKey],
  );

  const child = useMemo(() => (children ?? []).find((c) => c.id === childId), [children, childId]);

  const totalBalance = (invoices ?? []).reduce((sum, inv) => sum + inv.balance, 0);
  const totalPaid = (invoices ?? []).reduce((sum, inv) => sum + inv.paid_amount, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <Receipt className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Fees</h1>
            <p className="text-sm text-muted-foreground">Invoices and payment history</p>
          </div>
        </div>
        <ExportMenu
          filename={`fee-statement-${child?.first_name?.toLowerCase() ?? "child"}`}
          title="Fee Statement"
          subtitle={child ? `${child.first_name} ${child.last_name}` : "Fee statement"}
          meta={[
            ["Total billed", fmt((invoices ?? []).reduce((s, i) => s + i.total_amount, 0))],
            ["Total paid",   fmt(totalPaid)],
            ["Outstanding",  fmt(totalBalance)],
          ]}
          columns={[
            { key: "id",            label: "Invoice", width: 14 },
            { key: "total_amount",  label: "Total",   width: 12 },
            { key: "paid_amount",   label: "Paid",    width: 12 },
            { key: "balance",       label: "Balance", width: 12 },
            { key: "status",        label: "Status",  width: 10 },
            { key: "due_date",      label: "Due date", width: 14 },
          ]}
          rows={invoices ?? []}
        />
      </div>

      {/* Child selector */}
      {children && children.length > 1 && (
        <div className="relative inline-block">
          <select
            value={childId}
            onChange={(e) => setSelectedChildId(e.target.value)}
            className="appearance-none rounded-lg border border-input bg-background pl-3 pr-8 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            {children.map((c) => (
              <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error.message}</span>
        </div>
      )}

      {(loadingChildren || loadingInvoices) && (
        <div className="flex items-center justify-center p-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {!loadingInvoices && invoices && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 gap-3">
            <Card>
              <CardContent className="p-5">
                <p className="text-2xl font-bold text-green-600">{fmt(totalPaid)}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Total Paid</p>
              </CardContent>
            </Card>
            <Card className={totalBalance > 0 ? "border-red-200 bg-red-50" : ""}>
              <CardContent className="p-5">
                <p className={`text-2xl font-bold ${totalBalance > 0 ? "text-red-600" : "text-green-600"}`}>
                  {fmt(totalBalance)}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {totalBalance > 0 ? "Outstanding Balance" : "All Fees Cleared"}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Invoices list */}
          {invoices.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground text-sm">
                No invoices found for {child?.first_name ?? "this child"}.
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  {child ? `${child.first_name} ${child.last_name}` : "Invoices"}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <ul className="divide-y">
                  {invoices.map((inv) => (
                    <li key={inv.id} className="flex items-center justify-between px-5 py-4">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">Invoice #{inv.id.split("-").pop()?.toUpperCase()}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Due {new Date(inv.due_date + "T00:00:00").toLocaleDateString("en-ZW", {
                            day: "numeric", month: "short", year: "numeric",
                          })}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 ml-4">
                        <div className="text-right">
                          <p className="text-sm font-semibold">{fmt(inv.total_amount, inv.currency)}</p>
                          {inv.balance > 0 && (
                            <p className="text-xs text-red-600">Balance: {fmt(inv.balance, inv.currency)}</p>
                          )}
                        </div>
                        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[inv.status] ?? "bg-muted"}`}>
                          {STATUS_ICONS[inv.status]}
                          {inv.status}
                        </span>
                        {inv.balance > 0 && (
                          <Button
                            size="sm"
                            onClick={() => setPayInvoice(inv)}
                            aria-label={`Pay invoice ${inv.id}`}
                          >
                            <CreditCard className="h-4 w-4" />
                            Pay
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Payment methods info */}
          <div className="rounded-lg border bg-blue-50 px-4 py-3 text-sm text-blue-700">
            <p className="font-semibold mb-1">Payment Methods Accepted</p>
            <p>EcoCash · ZIPIT · Cash at School Bursar's Office</p>
            <p className="mt-1 text-xs text-blue-600">Reference your invoice number when making payments.</p>
          </div>
        </>
      )}

      {payInvoice && (
        <PayInvoiceDialog
          invoice={payInvoice}
          onClose={() => setPayInvoice(null)}
          onPaid={() => setRefreshKey((k) => k + 1)}
        />
      )}
    </div>
  );
}

