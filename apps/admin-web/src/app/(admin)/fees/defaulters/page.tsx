/**
 * Defaulters — overdue invoices with outstanding balances.
 * This is what principals care about most.
 * Permission: fees:read
 */

"use client";

import React, { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  Badge,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { Invoice, Student } from "@eduzim/api-client";
import { fees, student as studentApi } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { AlertTriangle } from "lucide-react";

function daysOverdue(dueDate: string): number {
  const due = new Date(dueDate);
  const now = new Date();
  const diff = Math.floor((now.getTime() - due.getTime()) / 86400000);
  return diff > 0 ? diff : 0;
}

export default function DefaultersPage() {
  const t = useTranslations("fees");

  const { data: defaulters, isLoading, error } = useApiQuery(
    () => fees.listDefaulters(),
    [],
  );
  const { data: students } = useApiQuery(() => studentApi.list(), []);

  const studentMap = useMemo(() => {
    const m = new Map<string, Student>();
    students?.forEach((s: Student) => m.set(s.id, s));
    return m;
  }, [students]);

  return (
    <RouteGuard permissions={["fees:read"]} onUnauthenticated={() => { }}>
      <div className="space-y-6">
        <PageHeader title={t("defaulters")} />

        {error && <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />}

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-muted" />)}
          </div>
        ) : !defaulters || defaulters.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title={t("noDefaulters")}
            description={t("noDefaultersDescription")}
          />
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("studentName")}</TableHead>
                  <TableHead className="text-right">{t("amount")}</TableHead>
                  <TableHead className="text-right">{t("paid")}</TableHead>
                  <TableHead className="text-right">{t("outstandingBalance")}</TableHead>
                  <TableHead className="text-right">{t("daysOverdue")}</TableHead>
                  <TableHead>{t("status")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {defaulters.map((inv: Invoice) => {
                  const s = studentMap.get(inv.student_id);
                  const overdue = daysOverdue(inv.due_date);
                  return (
                    <TableRow key={inv.id}>
                      <TableCell className="font-medium">
                        <a href={`/students/${inv.student_id}`} className="text-primary hover:underline">
                          {s ? `${s.first_name} ${s.last_name}` : inv.student_id.slice(0, 8)}
                        </a>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        ${inv.total_amount.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        ${inv.paid_amount.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono font-medium text-destructive">
                        ${inv.balance.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {overdue > 0 ? (
                          <span className="font-medium text-destructive">{overdue}d</span>
                        ) : "—"}
                      </TableCell>
                      <TableCell>
                        <Badge variant="destructive">{inv.status}</Badge>
                      </TableCell>
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
