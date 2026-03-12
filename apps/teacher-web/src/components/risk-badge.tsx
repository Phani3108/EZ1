/**
 * Risk Badge — Compact risk-band indicator for teacher-web.
 * Shows colored badge with risk score and band label.
 * Teacher view: attendance signals only (fee signals hidden).
 */

"use client";

import React from "react";

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
