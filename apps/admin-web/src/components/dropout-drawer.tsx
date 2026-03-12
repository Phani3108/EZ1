/**
 * Dropout Drilldown Drawer — shows full risk breakdown for a student.
 * Opens as a side sheet with signal details, evidence, and score bar.
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import {
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody,
} from "@eduzim/ui";
import type { DropoutStudentDetail, DropoutSignal } from "@eduzim/api-client";
import { reports } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { RiskBadge, RiskScoreBar } from "./risk-badge";
import { AlertTriangle, Clock, DollarSign, CalendarX } from "lucide-react";

interface DropoutDrawerProps {
  studentId: string | null;
  studentName?: string;
  open: boolean;
  onClose: () => void;
}

const SIGNAL_ICONS: Record<string, React.ElementType> = {
  CONSEC_ABSENT_3: CalendarX,
  CONSEC_ABSENT_5: CalendarX,
  CONSEC_ABSENT_10: CalendarX,
  RATE_BELOW_80: Clock,
  RATE_BELOW_65: Clock,
  RATE_BELOW_50: Clock,
  FEES_OUTSTANDING: DollarSign,
  FEES_OVERDUE_30: DollarSign,
  FEES_OVERDUE_60: DollarSign,
};

export function DropoutDrawer({ studentId, studentName, open, onClose }: DropoutDrawerProps) {
  const t = useTranslations("dropout");

  const { data: detail, isLoading } = useApiQuery(
    () => reports.dropoutStudentDetail(studentId!),
    [studentId],
  );

  return (
    <Sheet open={open} onClose={onClose}>
      <SheetHeader>
        <SheetTitle>{studentName || t("riskDetail")}</SheetTitle>
        <SheetDescription>{t("riskDetailDescription")}</SheetDescription>
      </SheetHeader>
      <SheetBody>
        {isLoading ? (
          <div className="space-y-4">
            <div className="h-8 animate-pulse rounded bg-muted" />
            <div className="h-32 animate-pulse rounded bg-muted" />
          </div>
        ) : detail ? (
          <div className="space-y-6" data-testid="dropout-drawer-content">
            {/* Score header */}
            <div className="flex items-center gap-3">
              <RiskBadge score={detail.risk_score} band={detail.risk_band} size="md" />
              <span className="text-sm text-muted-foreground">
                {t("computedAt")}: {new Date(detail.computed_at).toLocaleString()}
              </span>
            </div>

            {/* Score bar */}
            <RiskScoreBar score={detail.risk_score} band={detail.risk_band} />

            {/* Signals list */}
            <div>
              <h3 className="text-sm font-semibold mb-3">{t("signals")}</h3>
              {detail.signals.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("noSignals")}</p>
              ) : (
                <div className="space-y-3">
                  {detail.signals.map((signal: DropoutSignal, idx: number) => (
                    <SignalCard key={idx} signal={signal} />
                  ))}
                </div>
              )}
            </div>

            {/* Lookback info */}
            <p className="text-xs text-muted-foreground">
              {t("lookbackInfo", { days: detail.lookback_days })}
            </p>
          </div>
        ) : null}
      </SheetBody>
    </Sheet>
  );
}

function SignalCard({ signal }: { signal: DropoutSignal }) {
  const Icon = SIGNAL_ICONS[signal.code] || AlertTriangle;

  return (
    <div className="flex items-start gap-3 rounded-lg border p-3" data-testid="signal-card">
      <div className="mt-0.5 rounded bg-muted p-1.5">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">{signal.label}</span>
          <span className="text-sm font-bold text-red-600">+{signal.points}</span>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">{signal.evidence}</p>
        <span className="text-xs font-mono text-muted-foreground/60">{signal.code}</span>
      </div>
    </div>
  );
}
