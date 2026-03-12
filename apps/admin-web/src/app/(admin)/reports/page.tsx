/**
 * Reports — School-Wide Intelligence Dashboard
 * ==============================================
 * KPI row + attendance trend + financial summary.
 * Defaults to school-wide scope. Ministry-friendly, credible even when partial.
 * Permission: report:read
 */

"use client";

import React, { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  Card, CardContent, CardHeader, CardTitle,
  Badge, Select,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { DashboardData, AttendanceTrendPoint, FinancialSummaryData, AcademicYear } from "@eduzim/api-client";
import { reports, school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import {
  Users, UserCheck, CalendarCheck, DollarSign,
  Wallet, Megaphone, TrendingUp, BarChart3,
} from "lucide-react";

/** Format currency with $ prefix and 2 decimals */
function fmtCurrency(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Format percentage */
function fmtPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

/** Get date N days ago as YYYY-MM-DD */
function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().split("T")[0];
}

export default function ReportsPage() {
  const t = useTranslations("reports");
  const [trendRange, setTrendRange] = useState<7 | 30>(7);

  // ─── Data ───
  const { data: dashboard, isLoading: dashLoading, error: dashError } = useApiQuery(
    () => reports.dashboard(),
    [],
  );

  const fromDate = useMemo(() => daysAgo(trendRange), [trendRange]);
  const toDate = useMemo(() => daysAgo(0), []);

  const { data: trend, isLoading: trendLoading } = useApiQuery(
    () => reports.attendanceTrend({ from: fromDate, to: toDate }),
    [fromDate, toDate],
  );

  const { data: financial, isLoading: finLoading } = useApiQuery(
    () => reports.financialSummary(),
    [],
  );

  const kpis = dashboard as DashboardData | undefined;

  return (
    <RouteGuard permissions={["report:read"]} onUnauthenticated={() => { }}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <PageHeader title={t("title")} />
          <Badge variant="outline" className="text-sm">
            {t("schoolWide")}
          </Badge>
        </div>

        {dashError && (
          <ErrorAlert
            message={dashError.message}
            requestId={dashError.requestId}
            details={dashError.details}
          />
        )}

        {/* ─── KPI Cards ─── */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <KpiCard
            icon={Users}
            label={t("totalStudents")}
            value={kpis?.total_students ?? "—"}
            loading={dashLoading}
          />
          <KpiCard
            icon={CalendarCheck}
            label={t("attendanceToday")}
            value={kpis ? fmtPct(kpis.attendance_today_rate) : "—"}
            variant={kpis && kpis.attendance_today_rate < 70 ? "destructive" : "default"}
            loading={dashLoading}
          />
          <KpiCard
            icon={DollarSign}
            label={t("outstandingFees")}
            value={kpis ? fmtCurrency(kpis.outstanding_fees) : "—"}
            variant={kpis && kpis.outstanding_fees > 0 ? "warning" : "default"}
            loading={dashLoading}
          />
          <KpiCard
            icon={Wallet}
            label={t("collectedThisTerm")}
            value={kpis ? fmtCurrency(kpis.collected_this_term) : "—"}
            variant="success"
            loading={dashLoading}
          />
          <KpiCard
            icon={Megaphone}
            label={t("announcementsThisMonth")}
            value={kpis?.announcements_this_month ?? "—"}
            loading={dashLoading}
          />
        </div>

        {/* ─── Attendance Trend ─── */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-muted-foreground" />
                {t("attendanceTrend")}
              </CardTitle>
              <div className="flex gap-2">
                <button
                  className={`rounded px-3 py-1 text-sm ${trendRange === 7 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}
                  onClick={() => setTrendRange(7)}
                >
                  {t("last7Days")}
                </button>
                <button
                  className={`rounded px-3 py-1 text-sm ${trendRange === 30 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}
                  onClick={() => setTrendRange(30)}
                >
                  {t("last30Days")}
                </button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {trendLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => <div key={i} className="h-8 animate-pulse rounded bg-muted" />)}
              </div>
            ) : !trend || trend.length === 0 ? (
              <div className="rounded-lg border bg-muted/30 p-6 text-center">
                <p className="text-sm text-muted-foreground">{t("noData")}</p>
                <p className="text-xs text-muted-foreground mt-1">{t("noDataDescription")}</p>
              </div>
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("date")}</TableHead>
                      <TableHead className="text-right">{t("present")}</TableHead>
                      <TableHead className="text-right">{t("absent")}</TableHead>
                      <TableHead className="text-right">{t("late")}</TableHead>
                      <TableHead className="text-right">{t("rate")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(trend as AttendanceTrendPoint[]).map((d) => (
                      <TableRow key={d.date}>
                        <TableCell className="font-mono text-sm">{d.date}</TableCell>
                        <TableCell className="text-right font-mono text-green-600">{d.present}</TableCell>
                        <TableCell className="text-right font-mono text-red-600">{d.absent}</TableCell>
                        <TableCell className="text-right font-mono text-amber-600">{d.late}</TableCell>
                        <TableCell className="text-right">
                          <Badge variant={d.rate >= 80 ? "default" : d.rate >= 60 ? "secondary" : "destructive"}>
                            {fmtPct(d.rate)}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ─── Financial Summary ─── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-muted-foreground" />
              {t("financialSummary")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {finLoading ? (
              <div className="space-y-2">
                {[1, 2].map((i) => <div key={i} className="h-8 animate-pulse rounded bg-muted" />)}
              </div>
            ) : !financial || financial.length === 0 ? (
              <div className="rounded-lg border bg-muted/30 p-6 text-center">
                <p className="text-sm text-muted-foreground">{t("noData")}</p>
                <p className="text-xs text-muted-foreground mt-1">{t("noDataDescription")}</p>
              </div>
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("selectAcademicYear")}</TableHead>
                      <TableHead className="text-right">{t("totalInvoiced")}</TableHead>
                      <TableHead className="text-right">{t("totalPaid")}</TableHead>
                      <TableHead className="text-right">{t("totalOutstanding")}</TableHead>
                      <TableHead className="text-right">{t("collectionRate")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(financial as FinancialSummaryData[]).map((f) => {
                      const colRate = f.total_invoiced > 0
                        ? (f.total_paid / f.total_invoiced) * 100
                        : 0;
                      return (
                        <TableRow key={f.academic_year_id}>
                          <TableCell className="font-mono text-xs">
                            {f.academic_year_id.slice(0, 8)}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {fmtCurrency(f.total_invoiced)}
                          </TableCell>
                          <TableCell className="text-right font-mono text-green-600">
                            {fmtCurrency(f.total_paid)}
                          </TableCell>
                          <TableCell className="text-right font-mono text-red-600 font-medium">
                            {fmtCurrency(f.total_outstanding)}
                          </TableCell>
                          <TableCell className="text-right">
                            <Badge variant={colRate >= 80 ? "default" : colRate >= 50 ? "secondary" : "destructive"}>
                              {fmtPct(colRate)}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </RouteGuard>
  );
}

// ─── KPI Card Component ───

function KpiCard({
  icon: Icon,
  label,
  value,
  variant = "default",
  loading = false,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  variant?: "default" | "destructive" | "warning" | "success";
  loading?: boolean;
}) {
  const variantStyles = {
    default: "text-foreground",
    destructive: "text-red-600",
    warning: "text-amber-600",
    success: "text-green-600",
  };

  return (
    <Card>
      <CardContent className="p-4">
        {loading ? (
          <div className="space-y-2">
            <div className="h-4 w-20 animate-pulse rounded bg-muted" />
            <div className="h-8 w-16 animate-pulse rounded bg-muted" />
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Icon className="h-4 w-4" />
              <span className="text-xs font-medium">{label}</span>
            </div>
            <div className={`mt-1 text-2xl font-bold ${variantStyles[variant]}`}>
              {value}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
