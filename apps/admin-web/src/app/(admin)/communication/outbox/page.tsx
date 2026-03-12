/**
 * Outbox — delivery audit trail. Admin-only.
 * Shows per-recipient delivery status, retries, and errors.
 * Permission: school:manage
 */

"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Badge, Select,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { OutboxEntry } from "@eduzim/api-client";
import { comm } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Inbox } from "lucide-react";

function statusVariant(status: string) {
  switch (status) {
    case "SENT": return "default" as const;
    case "FAILED": return "destructive" as const;
    default: return "outline" as const;
  }
}

export default function OutboxPage() {
  const t = useTranslations("comm");
  const [statusFilter, setStatusFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");

  const params: Record<string, string> = {};
  if (statusFilter) params.status = statusFilter;
  // Channel filter is client-side since backend only supports status + announcement_id

  const { data: entries, isLoading, error } = useApiQuery(
    () => comm.listOutbox(statusFilter ? { status: statusFilter } : undefined),
    [statusFilter],
  );

  // Client-side channel filter
  const filtered = entries?.filter((e: OutboxEntry) =>
    !channelFilter || e.channel === channelFilter
  );

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
  ];

  return (
    <RouteGuard permissions={["school:manage"]} onUnauthenticated={() => { }}>
      <div className="space-y-6">
        <PageHeader title={t("outbox")} />

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
          <div className="w-48 space-y-1">
            <label className="text-sm font-medium text-muted-foreground">{t("filterByChannel")}</label>
            <Select
              options={channelOptions}
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
            />
          </div>
        </div>

        {error && <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />}

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-muted" />)}
          </div>
        ) : !filtered || filtered.length === 0 ? (
          <EmptyState icon={Inbox} title={t("noOutbox")} description={t("noOutboxDescription")} />
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
                      <Badge variant={statusVariant(entry.status)}>{entry.status}</Badge>
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
                        <span className="text-xs text-destructive" title={entry.error_message}>
                          {entry.error_message.length > 40
                            ? `${entry.error_message.slice(0, 40)}…`
                            : entry.error_message}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
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
