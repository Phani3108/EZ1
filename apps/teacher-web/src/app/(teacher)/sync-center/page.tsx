/**
 * Sync Center — 10B-4B.
 * Shows all offline queue items, their status, and provides retry controls.
 * Route: /sync-center
 */

"use client";

import React, { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Badge,
} from "@eduzim/ui";
import {
  RefreshCw,
  Trash2,
  CheckCircle,
  Clock,
  AlertTriangle,
  Loader2,
  WifiOff,
  CloudOff,
} from "lucide-react";
import { useSync } from "@/lib/sync-provider";
import type { OfflineAction } from "@eduzim/offline-core";

const STATUS_CONFIG = {
  QUEUED: {
    color: "bg-yellow-100 text-yellow-800",
    icon: Clock,
    label: "Queued",
  },
  SYNCING: {
    color: "bg-blue-100 text-blue-800",
    icon: Loader2,
    label: "Syncing",
  },
  SYNCED: {
    color: "bg-green-100 text-green-800",
    icon: CheckCircle,
    label: "Synced",
  },
  FAILED: {
    color: "bg-red-100 text-red-800",
    icon: AlertTriangle,
    label: "Failed",
  },
} as const;

const TYPE_LABELS: Record<string, string> = {
  ATTENDANCE: "Attendance",
  MARKS: "Marks",
  ANNOUNCEMENT: "Announcement",
};

export default function SyncCenterPage() {
  const tCommon = useTranslations("common");
  const { syncStatus, online, retryAll, processQueue, getAllActions, clearSynced, retryOne } = useSync();
  const [actions, setActions] = useState<OfflineAction[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadActions = async () => {
    try {
      const all = await getAllActions();
      // Sort: failed first, then queued, syncing, synced. Within each, newest first.
      all.sort((a, b) => {
        const order = { FAILED: 0, QUEUED: 1, SYNCING: 2, SYNCED: 3 };
        const diff = order[a.status] - order[b.status];
        if (diff !== 0) return diff;
        return b.createdAt - a.createdAt;
      });
      setActions(all);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadActions();
  }, [syncStatus]);

  const handleRetryOne = async (action: OfflineAction) => {
    await retryOne(action.id);
    await loadActions();
  };

  const handleRetryAll = async () => {
    await retryAll();
    await loadActions();
  };

  const handleClearSynced = async () => {
    await clearSynced();
    await loadActions();
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Sync Center</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {online ? (
              "Connected — changes sync automatically"
            ) : (
              <span className="flex items-center gap-1 text-yellow-700">
                <WifiOff className="h-3.5 w-3.5" />
                Offline — changes will sync when connection is restored
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard
          label="Queued"
          count={syncStatus.queued}
          color="text-yellow-600"
          icon={Clock}
        />
        <SummaryCard
          label="Syncing"
          count={syncStatus.syncing}
          color="text-blue-600"
          icon={Loader2}
        />
        <SummaryCard
          label="Synced"
          count={syncStatus.synced}
          color="text-green-600"
          icon={CheckCircle}
        />
        <SummaryCard
          label="Failed"
          count={syncStatus.failed}
          color="text-red-600"
          icon={AlertTriangle}
        />
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {syncStatus.failed > 0 && (
          <Button size="sm" variant="outline" onClick={handleRetryAll}>
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Retry All Failed
          </Button>
        )}
        {syncStatus.synced > 0 && (
          <Button size="sm" variant="outline" onClick={handleClearSynced}>
            <Trash2 className="h-4 w-4 mr-1.5" />
            Clear Synced
          </Button>
        )}
      </div>

      {/* Queue table */}
      {isLoading ? (
        <Card className="animate-pulse">
          <CardContent className="p-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-muted rounded" />
            ))}
          </CardContent>
        </Card>
      ) : actions.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <CloudOff className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground">
              No offline actions in the queue.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Actions appear here when you save while offline.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      Type
                    </th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      Created
                    </th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      Status
                    </th>
                    <th className="px-4 py-3 text-center font-medium text-muted-foreground">
                      Retries
                    </th>
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                      Error
                    </th>
                    <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {actions.map((action) => {
                    const cfg = STATUS_CONFIG[action.status];
                    const Icon = cfg.icon;
                    return (
                      <tr
                        key={action.id}
                        className="border-b last:border-0 hover:bg-muted/30"
                      >
                        <td className="px-4 py-3 font-medium">
                          {TYPE_LABELS[action.type] || action.type}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatTime(action.createdAt)}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant="secondary"
                            className={`${cfg.color} gap-1`}
                          >
                            <Icon
                              className={`h-3 w-3 ${
                                action.status === "SYNCING" ? "animate-spin" : ""
                              }`}
                            />
                            {cfg.label}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-center text-muted-foreground">
                          {action.retryCount}
                        </td>
                        <td className="px-4 py-3 text-xs text-red-600 max-w-[200px] truncate">
                          {action.error || "—"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {action.status === "FAILED" && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs"
                              onClick={() => handleRetryOne(action)}
                            >
                              Retry
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  count,
  color,
  icon: Icon,
}: {
  label: string;
  count: number;
  color: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <Icon className={`h-5 w-5 ${color}`} />
        <div>
          <p className="text-2xl font-bold">{count}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}
