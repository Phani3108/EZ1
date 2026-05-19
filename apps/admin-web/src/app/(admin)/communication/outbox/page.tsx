/**
 * Outbox / Notifications Center — admin-only.
 *
 * Visibility-first: a single screen that answers
 *   1. Are messages going out?              → stats tiles
 *   2. Which channels are healthy?           → per-channel breakdown
 *   3. What's failing right now?             → FAILED list + reason
 *   4. Can I retry?                          → row-level retry button
 *
 * Errors render via <FriendlyError> so admin always sees a clear
 * sentence + a fix line, with technical disclosure for support.
 *
 * Permission: school:manage
 */

"use client";

import React, { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Badge,
  Select,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  MinistryStatCard,
  FriendlyError,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import {
  ApiError,
  type OutboxEntry,
  type OutboxStats,
} from "@eduzim/api-client";
import { comm } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import {
  Inbox,
  CheckCircle2,
  Clock,
  XCircle,
  RotateCcw,
  Loader2,
} from "lucide-react";

function statusVariant(status: string): "default" | "destructive" | "outline" {
  switch (status) {
    case "SENT":
    case "DELIVERED":
      return "default";
    case "FAILED":
      return "destructive";
    default:
      return "outline";
  }
}

export default function OutboxPage() {
  const t = useTranslations("comm");
  const [statusFilter, setStatusFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<unknown>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // ─── Stats tile ───
  const {
    data: stats,
    error: statsError,
    refetch: refetchStats,
  } = useApiQuery<OutboxStats>(() => comm.outboxStats(), [refreshKey]);

  // ─── Outbox list ───
  const {
    data: entries,
    isLoading,
    error,
    refetch: refetchList,
  } = useApiQuery<OutboxEntry[]>(
    () =>
      comm.listOutbox(statusFilter ? { status: statusFilter } : undefined),
    [statusFilter, refreshKey],
  );

  const filtered = entries?.filter(
    (e: OutboxEntry) => !channelFilter || e.channel === channelFilter,
  );

  const handleRetry = useCallback(async (entry: OutboxEntry) => {
    setRetryingId(entry.id);
    setRetryError(null);
    try {
      await comm.retryOutboxEntry(entry.id);
      // Bump refreshKey so both queries re-run.
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setRetryError(e);
    } finally {
      setRetryingId(null);
    }
  }, []);

  const statusOptions = [
    { value: "", label: t("allStatuses") },
    { value: "PENDING", label: t("pending") },
    { value: "SENT", label: t("sent") },
    { value: "FAILED", label: t("failed") },
  ];

  const channelOptions = [
    { value: "", label: t("allChannels") },
    { value: "IN_APP", label: t("channelInApp") },
    { value: "SMS", label: t("channelSMS") },
    { value: "EMAIL", label: "Email" },
    { value: "PUSH", label: "Push" },
    { value: "WHATSAPP", label: "WhatsApp" },
  ];

  // Stats math — tolerate either SENT or DELIVERED as "delivered".
  const total: Record<string, number> = stats?.totals ?? {};
  const delivered = (total.DELIVERED ?? 0) + (total.SENT ?? 0);
  const pending = total.PENDING ?? 0;
  const failed = total.FAILED ?? 0;

  // Per-channel breakdown pre-computed so JSX stays simple.
  const channelBreakdown: Array<{
    channel: string;
    delivered: number;
    pending: number;
    failed: number;
    successRate: number;
  }> = stats?.by_channel
    ? Object.entries(stats.by_channel).map(([channel, rawCounts]) => {
        const counts = rawCounts as Record<string, number>;
        const d = (counts.DELIVERED ?? 0) + (counts.SENT ?? 0);
        const p = counts.PENDING ?? 0;
        const f = counts.FAILED ?? 0;
        const tot = d + p + f;
        return {
          channel,
          delivered: d,
          pending: p,
          failed: f,
          successRate: tot > 0 ? Math.round((d / tot) * 100) : 0,
        };
      })
    : [];

  return (
    <RouteGuard permissions={["school:manage"]} onUnauthenticated={() => {}}>
      <div className="space-y-6">
        <PageHeader title={t("outbox")} />

        {/* Stats — three tiles */}
        <section aria-labelledby="delivery-stats-heading">
          <h2 id="delivery-stats-heading" className="sr-only">
            {t("deliveryStats")}
          </h2>
          {statsError ? (
            <FriendlyError
              variant="inline"
              error={statsError}
              onRetry={() => refetchStats()}
              technical={{
                status:
                  statsError instanceof ApiError
                    ? statsError.status
                    : undefined,
                requestId:
                  statsError instanceof ApiError
                    ? statsError.requestId
                    : undefined,
                service: "communication-service",
                raw: statsError,
              }}
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <MinistryStatCard
                label={t("totalDelivered")}
                value={delivered.toLocaleString()}
                icon={CheckCircle2}
                accent="green"
                source="Source: communication-service · live"
              />
              <MinistryStatCard
                label={t("totalPending")}
                value={pending.toLocaleString()}
                icon={Clock}
                accent="gold"
                source="Awaiting worker pickup"
              />
              <MinistryStatCard
                label={t("totalFailed")}
                value={failed.toLocaleString()}
                icon={XCircle}
                accent="red"
                source="Use Retry to re-queue"
              />
            </div>
          )}

          {/* Per-channel breakdown */}
          {channelBreakdown.length > 0 && (
            <div className="mt-4 rounded-lg border bg-card p-4">
              <p className="text-sm font-semibold">{t("byChannel")}</p>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {channelBreakdown.map((row) => (
                  <div
                    key={row.channel}
                    className="rounded-md border bg-background p-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold">
                        {row.channel}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {row.successRate}% success
                      </span>
                    </div>
                    <dl className="mt-2 grid grid-cols-3 gap-1 text-xs">
                      <div>
                        <dt className="text-muted-foreground">
                          {t("totalDelivered")}
                        </dt>
                        <dd className="font-mono">{row.delivered}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">
                          {t("pending")}
                        </dt>
                        <dd className="font-mono">{row.pending}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">
                          {t("failed")}
                        </dt>
                        <dd className="font-mono text-destructive">
                          {row.failed}
                        </dd>
                      </div>
                    </dl>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Filters */}
        <div className="flex items-end gap-4">
          <div className="w-48 space-y-1">
            <label className="text-sm font-medium text-muted-foreground">
              {t("filterByStatus")}
            </label>
            <Select
              options={statusOptions}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            />
          </div>
          <div className="w-48 space-y-1">
            <label className="text-sm font-medium text-muted-foreground">
              {t("filterByChannel")}
            </label>
            <Select
              options={channelOptions}
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
            />
          </div>
        </div>

        {retryError ? (
          <FriendlyError
            variant="inline"
            error={retryError}
            onRetry={() => setRetryError(null)}
            technical={{
              status:
                retryError instanceof ApiError ? retryError.status : undefined,
              requestId:
                retryError instanceof ApiError
                  ? retryError.requestId
                  : undefined,
              service: "communication-service · retry",
              raw: retryError,
            }}
          />
        ) : null}

        {error && (
          <FriendlyError
            variant="inline"
            error={error}
            onRetry={() => refetchList()}
            technical={{
              status: error instanceof ApiError ? error.status : undefined,
              requestId:
                error instanceof ApiError ? error.requestId : undefined,
              service: "communication-service",
              raw: error,
            }}
          />
        )}

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : !filtered || filtered.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title={t("noOutbox")}
            description={t("noOutboxDescription")}
          />
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("announcement")}</TableHead>
                  <TableHead>{t("recipient")}</TableHead>
                  <TableHead>{t("channel")}</TableHead>
                  <TableHead>{t("status")}</TableHead>
                  <TableHead className="text-right">{t("retryCount")}</TableHead>
                  <TableHead>{t("lastAttempt")}</TableHead>
                  <TableHead>{t("error")}</TableHead>
                  <TableHead className="text-right">{/* actions */}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((entry: OutboxEntry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="font-mono text-xs">
                      {entry.announcement_id.slice(0, 8)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {entry.user_id.slice(0, 8)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{entry.channel}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(entry.status)}>
                        {entry.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {entry.retry_count}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {entry.last_attempt_at
                        ? new Date(entry.last_attempt_at).toLocaleString()
                        : "—"}
                    </TableCell>
                    <TableCell>
                      {entry.error_message ? (
                        <span
                          className="text-xs text-destructive"
                          title={entry.error_message}
                        >
                          {entry.error_message.length > 40
                            ? `${entry.error_message.slice(0, 40)}…`
                            : entry.error_message}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {entry.status === "FAILED" && (
                        <button
                          onClick={() => handleRetry(entry)}
                          disabled={retryingId === entry.id}
                          aria-label={t("retry")}
                          title={t("retryHint")}
                          className="inline-flex items-center gap-1 rounded-md border border-foreground/15 bg-background px-2 py-1 text-xs font-medium hover:bg-accent disabled:opacity-50"
                        >
                          {retryingId === entry.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <RotateCcw className="h-3.5 w-3.5" />
                          )}
                          {retryingId === entry.id ? t("retrying") : t("retry")}
                        </button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </RouteGuard>
  );
}
