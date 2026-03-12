/**
 * Risk Badge — Compact risk-band indicator.
 * Shows colored badge with risk score and band label.
 * Used in dropout dashboard table, Student 360 header, and teacher student view.
 */

"use client";

import React from "react";
import { Badge } from "@eduzim/ui";

type RiskBand = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

interface RiskBadgeProps {
  score: number;
  band: RiskBand;
  showScore?: boolean;
  size?: "sm" | "md";
  onClick?: () => void;
}

const BAND_STYLES: Record<RiskBand, string> = {
  LOW: "bg-green-100 text-green-800 border-green-200",
  MEDIUM: "bg-amber-100 text-amber-800 border-amber-200",
  HIGH: "bg-orange-100 text-orange-800 border-orange-200",
  CRITICAL: "bg-red-100 text-red-800 border-red-200",
};

const BAND_DOT: Record<RiskBand, string> = {
  LOW: "bg-green-500",
  MEDIUM: "bg-amber-500",
  HIGH: "bg-orange-500",
  CRITICAL: "bg-red-500",
};

export function RiskBadge({ score, band, showScore = true, size = "sm", onClick }: RiskBadgeProps) {
  const sizeStyles = size === "md" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs";

  return (
    <span
      role="status"
      data-testid="risk-badge"
      data-band={band}
      data-score={score}
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${BAND_STYLES[band]} ${sizeStyles} ${onClick ? "cursor-pointer hover:opacity-80" : ""}`}
      onClick={onClick}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${BAND_DOT[band]}`} />
      {showScore && <span>{score}</span>}
      <span>{band}</span>
    </span>
  );
}

/**
 * Risk Score Bar — horizontal gauge from 0 to 100.
 */
export function RiskScoreBar({ score, band }: { score: number; band: RiskBand }) {
  const fillColor: Record<RiskBand, string> = {
    LOW: "bg-green-500",
    MEDIUM: "bg-amber-500",
    HIGH: "bg-orange-500",
    CRITICAL: "bg-red-500",
  };

  return (
    <div className="w-full" data-testid="risk-score-bar">
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
        <span>0</span>
        <span className="font-medium text-foreground">{score}/100</span>
        <span>100</span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${fillColor[band]}`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
    </div>
  );
}
