/**
 * Sync Monitor — Admin debugging page.
 * Shows recent attendance sync batches.
 * Permission: school:manage
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { AttendanceSyncBatch } from "@eduzim/api-client";
import { attendance } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { ErrorAlert } from "@/components/error-alert";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import {
    Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@eduzim/ui";
import { Radio } from "lucide-react";

export default function SyncMonitorPage() {
    const t = useTranslations("attendance");

    const { data: batches, isLoading, error } = useApiQuery(
        () => attendance.syncBatches({ limit: "20" }),
        [],
    );

    return (
        <RouteGuard permissions={["school:manage"]} onUnauthenticated={() => { }}>
            <div className="space-y-6">
                <PageHeader title={t("syncMonitor")} />

                {error && (
                    <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />
                )}

                {isLoading ? (
                    <div className="space-y-2">
                        {[1, 2, 3, 4].map((i) => (
                            <div key={i} className="h-12 animate-pulse rounded bg-muted" />
                        ))}
                    </div>
                ) : !batches || batches.length === 0 ? (
                    <EmptyState
                        icon={Radio}
                        title={t("noBatches")}
                        description={t("noBatchesDescription")}
                    />
                ) : (
                    <div className="rounded-lg border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>{t("batchId")}</TableHead>
                                    <TableHead>{t("deviceId")}</TableHead>
                                    <TableHead>{t("receivedAt")}</TableHead>
                                    <TableHead className="text-right">{t("totalEvents")}</TableHead>
                                    <TableHead className="text-right">{t("accepted")}</TableHead>
                                    <TableHead className="text-right">{t("updated")}</TableHead>
                                    <TableHead className="text-right">{t("ignored")}</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {batches.map((b: AttendanceSyncBatch) => (
                                    <TableRow key={b.id}>
                                        <TableCell className="font-mono text-xs">
                                            {b.sync_batch_id.slice(0, 12)}…
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="secondary">{b.device_id}</Badge>
                                        </TableCell>
                                        <TableCell className="text-sm">
                                            {new Date(b.received_at).toLocaleString()}
                                        </TableCell>
                                        <TableCell className="text-right font-medium">
                                            {b.total_events}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <span className="text-emerald-600 font-medium">{b.accepted_count}</span>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <span className="text-amber-600 font-medium">{b.updated_count}</span>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <span className="text-muted-foreground">{b.ignored_count}</span>
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
