/**
 * Dropout Risk Monitor — Intelligence Dashboard
 * ================================================
 * KPI cards (total students, at-risk count, band breakdown)
 * Filterable + sortable student table with risk scores
 * Drilldown drawer for individual student risk detail
 *
 * Permission: report:read
 * Route: /intelligence/dropout
 */

"use client";

import React, { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  Card, CardContent, CardHeader, CardTitle,
  Badge, Button,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { DropoutSummary, DropoutStudentRow } from "@eduzim/api-client";
import { reports } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { RiskBadge } from "@/components/risk-badge";
import { DropoutDrawer } from "@/components/dropout-drawer";
import {
  AlertTriangle, Users, ShieldAlert, BarChart3,
  Eye, ChevronLeft, ChevronRight, CalendarRange,
} from "lucide-react";

type RiskBand = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export default function DropoutMonitorPage() {
  const t = useTranslations("dropout");

  // State
  const [page, setPage] = useState(1);
  const [bandFilter, setBandFilter] = useState<string>("");
  const [drawerStudentId, setDrawerStudentId] = useState<string | null>(null);
  const [drawerStudentName, setDrawerStudentName] = useState<string>("");
  const pageSize = 20;

  // Fetch summary
  const { data: summary, isLoading: summaryLoading, error: summaryError } = useApiQuery(
    () => reports.dropoutSummary(),
    [],
  );

  // Fetch students list
  const params = useMemo(() => {
    const p: Record<string, string> = {
      page: String(page),
      page_size: String(pageSize),
      sort: "risk_score",
      order: "desc",
    };
    if (bandFilter) p.band = bandFilter;
    return p;
  }, [page, bandFilter]);

  const { data: students, isLoading: studentsLoading, error: studentsError } = useApiQuery(
    () => reports.dropoutStudents(params),
    [page, bandFilter],
  );

  const sum = summary as DropoutSummary | undefined;
  const rows = (students ?? []) as DropoutStudentRow[];

  const openDrawer = (student: DropoutStudentRow) => {
    setDrawerStudentId(student.student_id);
    setDrawerStudentName(`${student.first_name} ${student.last_name}`);
  };

  return (
    <RouteGuard permissions={["report:read"]} onUnauthenticated={() => { }}>
      <div className="space-y-6">
        <PageHeader title={t("title")} description={t("description")} />

        {/* ─── Lookback Date Range ─── */}
        <div className="flex items-center gap-2 rounded-lg border bg-muted/40 px-4 py-2 text-sm text-muted-foreground" data-testid="lookback-range">
          <CalendarRange className="h-4 w-4" />
          <span>
            {t("signalsComputedFor")}{" "}
            <strong className="text-foreground">
              {new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10)}
              {" → "}
              {new Date().toISOString().slice(0, 10)}
            </strong>
          </span>
        </div>

        {(summaryError || studentsError) && (
          <ErrorAlert
            message={(summaryError || studentsError)!.message}
            requestId={(summaryError || studentsError)!.requestId}
          />
        )}

        {/* ─── KPI Cards ─── */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6" data-testid="dropout-kpi-cards">
          <KpiCard
            label={t("totalStudents")}
            value={sum?.total_students ?? "—"}
            icon={Users}
            loading={summaryLoading}
          />
          <KpiCard
            label={t("atRisk")}
            value={sum?.at_risk_count ?? "—"}
            icon={AlertTriangle}
            variant="destructive"
            loading={summaryLoading}
          />
          <BandCard
            label="LOW"
            count={sum?.band_breakdown?.LOW ?? 0}
            color="green"
            loading={summaryLoading}
          />
          <BandCard
            label="MEDIUM"
            count={sum?.band_breakdown?.MEDIUM ?? 0}
            color="amber"
            loading={summaryLoading}
          />
          <BandCard
            label="HIGH"
            count={sum?.band_breakdown?.HIGH ?? 0}
            color="orange"
            loading={summaryLoading}
          />
          <BandCard
            label="CRITICAL"
            count={sum?.band_breakdown?.CRITICAL ?? 0}
            color="red"
            loading={summaryLoading}
          />
        </div>

        {/* ─── Filter Bar ─── */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">{t("filterByBand")}:</span>
          {["", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((b) => (
            <Button
              key={b}
              variant={bandFilter === b ? "default" : "outline"}
              size="sm"
              onClick={() => { setBandFilter(b); setPage(1); }}
            >
              {b || t("all")}
            </Button>
          ))}
        </div>

        {/* ─── Student Risk Table ─── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-muted-foreground" />
              {t("studentRiskTable")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {studentsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-10 animate-pulse rounded bg-muted" />
                ))}
              </div>
            ) : rows.length === 0 ? (
              <EmptyState icon={Users} title={t("noStudents")} />
            ) : (
              <>
                <div className="rounded-lg border" data-testid="dropout-students-table">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("studentCode")}</TableHead>
                        <TableHead>{t("studentName")}</TableHead>
                        <TableHead className="text-center">{t("riskScore")}</TableHead>
                        <TableHead className="text-center">{t("riskBand")}</TableHead>
                        <TableHead className="text-center">{t("signalCount")}</TableHead>
                        <TableHead>{t("primaryReason")}</TableHead>
                        <TableHead className="text-right">{t("actions")}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((row) => (
                        <TableRow key={row.student_id}>
                          <TableCell className="font-mono text-sm">{row.student_code}</TableCell>
                          <TableCell>{row.first_name} {row.last_name}</TableCell>
                          <TableCell className="text-center font-bold">{row.risk_score}</TableCell>
                          <TableCell className="text-center">
                            <RiskBadge score={row.risk_score} band={row.risk_band} showScore={false} />
                          </TableCell>
                          <TableCell className="text-center">{row.signal_count}</TableCell>
                          <TableCell>
                            {row.top_signal ? (
                              <span className="text-sm">
                                {row.top_signal}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openDrawer(row)}
                            >
                              <Eye className="h-4 w-4 mr-1" />
                              {t("viewDetails")}
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {/* Pagination */}
                <div className="flex items-center justify-between mt-4">
                  <span className="text-sm text-muted-foreground">
                    {t("page")} {page}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage(page - 1)}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={rows.length < pageSize}
                      onClick={() => setPage(page + 1)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* ─── Drilldown Drawer ─── */}
        <DropoutDrawer
          studentId={drawerStudentId}
          studentName={drawerStudentName}
          open={!!drawerStudentId}
          onClose={() => setDrawerStudentId(null)}
        />
      </div>
    </RouteGuard>
  );
}

// ─── KPI Card ───

function KpiCard({
  label,
  value,
  icon: Icon,
  variant = "default",
  loading = false,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  variant?: "default" | "destructive";
  loading?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        {loading ? (
          <div className="space-y-2">
            <div className="h-4 w-16 animate-pulse rounded bg-muted" />
            <div className="h-8 w-12 animate-pulse rounded bg-muted" />
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Icon className="h-4 w-4" />
              <span className="text-xs font-medium">{label}</span>
            </div>
            <div className={`mt-1 text-2xl font-bold ${variant === "destructive" ? "text-red-600" : ""}`}>
              {value}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Band Count Card ───

function BandCard({
  label,
  count,
  color,
  loading,
}: {
  label: string;
  count: number;
  color: "green" | "amber" | "orange" | "red";
  loading: boolean;
}) {
  const colors: Record<string, string> = {
    green: "text-green-600 border-green-200",
    amber: "text-amber-600 border-amber-200",
    orange: "text-orange-600 border-orange-200",
    red: "text-red-600 border-red-200",
  };

  return (
    <Card className={loading ? "" : colors[color]}>
      <CardContent className="p-4">
        {loading ? (
          <div className="space-y-2">
            <div className="h-4 w-16 animate-pulse rounded bg-muted" />
            <div className="h-8 w-12 animate-pulse rounded bg-muted" />
          </div>
        ) : (
          <>
            <span className="text-xs font-medium">{label}</span>
            <div className="mt-1 text-2xl font-bold">{count}</div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
