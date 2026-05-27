"""Dropout Risk Engine — Pure Rules-Based Compute (no I/O).

Lifted verbatim from reporting-service/app/services/dropout_service.py at
PH2-11. The engine is now hosted inside academics because the route layer
that drives it (the /api/v1/reports/dropout/* endpoints) moved here. The
reporting-service container has no HTTP surface anymore.

Risk Model v1 — unchanged:
  Score 0-100, capped.
  Bands: LOW (0-29), MEDIUM (30-59), HIGH (60-79), CRITICAL (80-100)

Attendance Signals:
  - Consecutive absences: 3→+25, 5→+40, 10→+60  (mutually exclusive, highest)
  - 30-day rate: <80%→+15, <65%→+30, <50%→+45   (mutually exclusive, worst)

Fee Signals:
  - Outstanding balance > 0 → +10
  - Overdue > 30 days → +20  (mutually exclusive with 60-day)
  - Overdue > 60 days → +30
"""
from __future__ import annotations

from datetime import date
from typing import Optional


class DropoutRiskEngine:
    """Pure rules engine — no database, no HTTP, fully deterministic."""

    BANDS = [
        (0, 29, "LOW"),
        (30, 59, "MEDIUM"),
        (60, 79, "HIGH"),
        (80, 100, "CRITICAL"),
    ]

    @staticmethod
    def compute(
        attendance_days: list[dict],
        invoices: list[dict],
        today: Optional[date] = None,
    ) -> dict:
        today = today or date.today()
        signals: list[dict] = []
        signals.extend(DropoutRiskEngine._attendance_signals(attendance_days))
        signals.extend(DropoutRiskEngine._fee_signals(invoices, today))

        raw_score = sum(s["points"] for s in signals)
        score = min(raw_score, 100)

        band = "LOW"
        for lo, hi, label in DropoutRiskEngine.BANDS:
            if lo <= score <= hi:
                band = label
                break

        return {"risk_score": score, "risk_band": band, "signals": signals}

    @staticmethod
    def _attendance_signals(days: list[dict]) -> list[dict]:
        signals: list[dict] = []
        if not days:
            return signals

        consecutive = 0
        for day in reversed(days):
            if day.get("status") == "A":
                consecutive += 1
            else:
                break

        if consecutive >= 10:
            signals.append({
                "code": "CONSEC_ABSENT_10",
                "label": "10+ consecutive days absent",
                "points": 60,
                "evidence": f"{consecutive} consecutive absences",
            })
        elif consecutive >= 5:
            signals.append({
                "code": "CONSEC_ABSENT_5",
                "label": "5+ consecutive days absent",
                "points": 40,
                "evidence": f"{consecutive} consecutive absences",
            })
        elif consecutive >= 3:
            signals.append({
                "code": "CONSEC_ABSENT_3",
                "label": "3+ consecutive days absent",
                "points": 25,
                "evidence": f"{consecutive} consecutive absences",
            })

        total = len(days)
        present = sum(1 for d in days if d.get("status") == "P")
        rate = present / total * 100

        if rate < 50:
            signals.append({
                "code": "RATE_BELOW_50",
                "label": "Attendance rate below 50%",
                "points": 45,
                "evidence": f"{rate:.1f}% attendance rate over {total} days",
            })
        elif rate < 65:
            signals.append({
                "code": "RATE_BELOW_65",
                "label": "Attendance rate below 65%",
                "points": 30,
                "evidence": f"{rate:.1f}% attendance rate over {total} days",
            })
        elif rate < 80:
            signals.append({
                "code": "RATE_BELOW_80",
                "label": "Attendance rate below 80%",
                "points": 15,
                "evidence": f"{rate:.1f}% attendance rate over {total} days",
            })

        return signals

    @staticmethod
    def _fee_signals(invoices: list[dict], today: date) -> list[dict]:
        signals: list[dict] = []
        if not invoices:
            return signals

        total_outstanding = 0.0
        for inv in invoices:
            if inv.get("status") in ("PENDING", "PARTIAL", "OVERDUE"):
                total_outstanding += float(inv.get("total_amount", 0)) - float(
                    inv.get("paid_amount", 0)
                )

        if total_outstanding > 0:
            signals.append({
                "code": "FEES_OUTSTANDING",
                "label": "Outstanding fees balance",
                "points": 10,
                "evidence": f"${total_outstanding:.2f} outstanding",
            })

        max_overdue_days = 0
        for inv in invoices:
            if inv.get("status") in ("PENDING", "PARTIAL", "OVERDUE"):
                due = inv.get("due_date")
                if due:
                    if isinstance(due, str):
                        due = date.fromisoformat(due)
                    overdue_days = (today - due).days
                    if overdue_days > max_overdue_days:
                        max_overdue_days = overdue_days

        if max_overdue_days > 60:
            signals.append({
                "code": "FEES_OVERDUE_60",
                "label": "Fees overdue by 60+ days",
                "points": 30,
                "evidence": f"{max_overdue_days} days overdue",
            })
        elif max_overdue_days > 30:
            signals.append({
                "code": "FEES_OVERDUE_30",
                "label": "Fees overdue by 30+ days",
                "points": 20,
                "evidence": f"{max_overdue_days} days overdue",
            })

        return signals
