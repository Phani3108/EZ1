/**
 * Admin Integrations Hub — sovereign theme
 * =========================================
 * One screen where an admin can see, at a glance, the health of every
 * integration the platform depends on (services, payments, messaging),
 * run a deep test against any of them on demand, and read plain-language
 * remediation advice when something is wrong.
 *
 * Working principle: "no backend without a frontend surface to see it,
 * test it, and read its errors". Every future integration (Paynow, WhatsApp,
 * SMS, ministry-service) plugs in here automatically — the gateway already
 * advertises its known integrations via `GET /diagnostics/services`.
 */

"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  FlagHeader,
  MinistryStatCard,
  OfficialBadge,
  FriendlyError,
  classifyError,
} from "@eduzim/ui";
import {
  ApiError,
  type IntegrationSummary,
  type IntegrationProbeResult,
} from "@eduzim/api-client";
import { diagnostics } from "@/lib/api";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Settings2,
  PlayCircle,
  RefreshCw,
  Loader2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

type Status = IntegrationSummary["status"];

const STATUS_META: Record<
  Status,
  { label: string; icon: React.ComponentType<{ className?: string }>; pill: string; ring: string }
> = {
  ok: {
    label: "Healthy",
    icon: CheckCircle2,
    pill: "bg-emerald-100 text-emerald-800 border-emerald-200",
    ring: "ring-emerald-200",
  },
  degraded: {
    label: "Slow",
    icon: AlertTriangle,
    pill: "bg-amber-100 text-amber-800 border-amber-200",
    ring: "ring-amber-200",
  },
  down: {
    label: "Not responding",
    icon: XCircle,
    pill: "bg-red-100 text-red-800 border-red-200",
    ring: "ring-red-200",
  },
  not_configured: {
    label: "Not set up",
    icon: Settings2,
    pill: "bg-slate-100 text-slate-700 border-slate-200",
    ring: "ring-slate-200",
  },
  unknown: {
    label: "Unknown",
    icon: Activity,
    pill: "bg-slate-100 text-slate-600 border-slate-200",
    ring: "ring-slate-200",
  },
};

function StatusPill({ status }: { status: Status }) {
  const meta = STATUS_META[status] ?? STATUS_META.unknown;
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${meta.pill}`}
    >
      <Icon className="h-3.5 w-3.5" />
      {meta.label}
    </span>
  );
}

function formatLatency(ms?: number): string {
  if (ms === undefined || ms === null) return "—";
  if (ms < 1) return "<1 ms";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

/**
 * Per-integration configuration hint shown when a service reports
 * `not_configured`. We currently know about Paynow (fees-service);
 * other integrations get a generic placeholder.
 */
function SetupHint({ id }: { id: string }) {
  // Anything containing "fees" → Paynow setup hint.
  if (/fees/i.test(id)) {
    return (
      <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm">
        <p className="font-semibold text-amber-900">
          Paynow keys aren&apos;t set yet
        </p>
        <p className="mt-1 text-amber-800">
          Until you add them, parents can only make payments in demo mode (no
          real money moves). Set these environment variables on the
          fees-service and restart it:
        </p>
        <ul className="mt-2 space-y-1 font-mono text-xs text-amber-900">
          <li>PAYNOW_INTEGRATION_ID=&lt;your numeric id&gt;</li>
          <li>PAYNOW_INTEGRATION_KEY=&lt;your secret key&gt;</li>
          <li>
            PAYNOW_RESULT_URL=https://&lt;your-host&gt;/api/v1/fees/payments/webhook/paynow
          </li>
          <li>PAYNOW_RETURN_URL=https://&lt;your-host&gt;/fees</li>
        </ul>
        <p className="mt-2 text-xs text-amber-800">
          After restarting, click <strong>Run test</strong> above — the
          deep-probe verifies your hash key without contacting Paynow.
        </p>
      </div>
    );
  }
  if (/communication|messag/i.test(id)) {
    return (
      <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm">
        <p className="font-semibold text-amber-900">
          No messaging channels are set up yet
        </p>
        <p className="mt-1 text-amber-800">
          Announcements will be saved but won&apos;t reach parents until at
          least one channel is configured. Set these on the
          communication-service and restart it:
        </p>
        <ul className="mt-2 space-y-1 font-mono text-xs text-amber-900">
          <li># SMS (Africa&apos;s Talking)</li>
          <li>AFRICASTALKING_API_KEY=…</li>
          <li>AFRICASTALKING_USERNAME=…</li>
          <li className="mt-2"># Email</li>
          <li>SMTP_HOST=smtp.example.com</li>
          <li>SMTP_PORT=587</li>
          <li>SMTP_USER=… &nbsp; SMTP_PASSWORD=…</li>
          <li className="mt-2"># Push (Firebase)</li>
          <li>FCM_SERVER_KEY=…</li>
          <li className="mt-2"># WhatsApp Business Cloud API</li>
          <li>WHATSAPP_ACCESS_TOKEN=…</li>
          <li>WHATSAPP_PHONE_NUMBER_ID=…</li>
        </ul>
        <p className="mt-2 text-xs text-amber-800">
          After restarting, click <strong>Run test</strong> — each channel
          reports its own status (configured / reachable / not configured).
        </p>
      </div>
    );
  }
  return (
    <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
      This integration isn&apos;t configured yet. Check the service&apos;s
      environment variables.
    </div>
  );
}

function timeOfDay(d: Date): string {
  return d.toLocaleTimeString("en-ZW", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

interface CardState {
  summary: IntegrationSummary;
  probing: boolean;
  probe?: IntegrationProbeResult;
  probeError?: unknown;
  probedAt?: Date;
  expanded: boolean;
}

export default function IntegrationsPage() {
  const [cards, setCards] = useState<CardState[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);

  const loadServices = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const { data } = await diagnostics.listServices();
      setCards((prev) => {
        const prevMap = new Map((prev ?? []).map((c) => [c.summary.id, c]));
        return data.integrations.map((summary) => ({
          summary,
          probing: false,
          probe: prevMap.get(summary.id)?.probe,
          probeError: prevMap.get(summary.id)?.probeError,
          probedAt: prevMap.get(summary.id)?.probedAt,
          expanded: prevMap.get(summary.id)?.expanded ?? false,
        }));
      });
      setRefreshedAt(new Date());
    } catch (e) {
      setLoadError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadServices();
    const id = window.setInterval(loadServices, 30000); // refresh every 30s
    return () => window.clearInterval(id);
  }, [loadServices]);

  const runProbe = async (id: string) => {
    setCards((prev) =>
      (prev ?? []).map((c) =>
        c.summary.id === id ? { ...c, probing: true, probeError: undefined, expanded: true } : c,
      ),
    );
    try {
      const { data } = await diagnostics.probe(id);
      setCards((prev) =>
        (prev ?? []).map((c) =>
          c.summary.id === id
            ? {
                ...c,
                probing: false,
                probe: data,
                probedAt: new Date(),
                summary: { ...c.summary, status: data.status, message: data.message },
              }
            : c,
        ),
      );
    } catch (e) {
      setCards((prev) =>
        (prev ?? []).map((c) =>
          c.summary.id === id ? { ...c, probing: false, probeError: e } : c,
        ),
      );
    }
  };

  const toggleExpanded = (id: string) =>
    setCards((prev) =>
      (prev ?? []).map((c) =>
        c.summary.id === id ? { ...c, expanded: !c.expanded } : c,
      ),
    );

  // ─── Rollup counts ───
  const counts = (cards ?? []).reduce(
    (acc, c) => {
      acc[c.summary.status] = (acc[c.summary.status] ?? 0) + 1;
      return acc;
    },
    {} as Record<Status, number>,
  );

  return (
    <div className="space-y-6">
      <FlagHeader
        title="Platform Integrations"
        subtitle="Live status of every service, payment gateway and messaging channel EduZim relies on."
        emblem={
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src="/national/coat-of-arms.svg"
            alt="Zimbabwe coat of arms"
            className="h-10 w-10"
          />
        }
        actions={
          <>
            <OfficialBadge variant="mopse" label="MoPSE" />
            <button
              onClick={loadServices}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-md border bg-card px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Refresh all
            </button>
          </>
        }
        stripe="thick"
        className="rounded-lg"
      />

      {refreshedAt && (
        <p className="text-xs text-muted-foreground">
          Last refreshed {timeOfDay(refreshedAt)} · refreshes automatically every 30 seconds
        </p>
      )}

      {/* Rollup KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MinistryStatCard
          label="Healthy"
          value={String(counts.ok ?? 0)}
          icon={CheckCircle2}
          accent="green"
          source="Gateway diagnostics"
        />
        <MinistryStatCard
          label="Slow"
          value={String(counts.degraded ?? 0)}
          icon={AlertTriangle}
          accent="gold"
          source="Gateway diagnostics"
        />
        <MinistryStatCard
          label="Not responding"
          value={String(counts.down ?? 0)}
          icon={XCircle}
          accent="red"
          source="Gateway diagnostics"
        />
        <MinistryStatCard
          label="Not set up"
          value={String(counts.not_configured ?? 0)}
          icon={Settings2}
          accent="black"
          source="Gateway diagnostics"
        />
      </div>

      {/* Load error */}
      {loadError != null && (
        <FriendlyError
          variant="card"
          error={loadError}
          onRetry={loadServices}
          technical={{
            requestId:
              loadError instanceof ApiError ? loadError.requestId : undefined,
            status:
              loadError instanceof ApiError ? loadError.status : undefined,
            service: "api-gateway · diagnostics",
            raw: loadError,
          }}
        />
      )}

      {/* Integration cards */}
      {loading && !cards ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading integrations…
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {(cards ?? []).map((card) => {
            const { summary, probing, probe, probeError, probedAt, expanded } = card;
            const meta = STATUS_META[summary.status] ?? STATUS_META.unknown;
            return (
              <article
                key={summary.id}
                className={`rounded-lg border bg-card p-5 shadow-sm ring-1 ${meta.ring}`}
                aria-labelledby={`integration-${summary.id}-title`}
              >
                <header className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2
                      id={`integration-${summary.id}-title`}
                      className="text-base font-semibold text-foreground"
                    >
                      {summary.label}
                    </h2>
                    <p className="mt-0.5 text-xs uppercase tracking-wide text-muted-foreground">
                      {summary.category}
                    </p>
                  </div>
                  <StatusPill status={summary.status} />
                </header>

                <p className="mt-3 text-sm text-muted-foreground">
                  {summary.description}
                </p>

                {summary.message && (
                  <p className="mt-2 text-sm text-foreground">{summary.message}</p>
                )}

                <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <dt className="text-muted-foreground">Response time</dt>
                    <dd className="font-medium">{formatLatency(summary.latency_ms)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Last tested</dt>
                    <dd className="font-medium">
                      {probedAt ? timeOfDay(probedAt) : "—"}
                    </dd>
                  </div>
                </dl>

                <div className="mt-4 flex items-center gap-2">
                  <button
                    onClick={() => runProbe(summary.id)}
                    disabled={probing}
                    className="inline-flex items-center gap-1.5 rounded-md border border-foreground/15 bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
                  >
                    {probing ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <PlayCircle className="h-4 w-4" />
                    )}
                    {probing ? "Testing…" : "Run test"}
                  </button>
                  {(probe != null || probeError != null) && (
                    <button
                      onClick={() => toggleExpanded(summary.id)}
                      className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:text-foreground"
                    >
                      {expanded ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                      {expanded ? "Hide details" : "Show details"}
                    </button>
                  )}
                </div>

                {/* Setup hint — shown when service reports not_configured */}
                {summary.status === "not_configured" && (
                  <SetupHint id={summary.id} />
                )}

                {/* Probe error — friendly, with technical disclosure */}
                {probeError != null && expanded && (
                  <div className="mt-4">
                    <FriendlyError
                      variant="inline"
                      error={probeError}
                      onRetry={() => runProbe(summary.id)}
                      technical={{
                        requestId:
                          probeError instanceof ApiError
                            ? probeError.requestId
                            : undefined,
                        status:
                          probeError instanceof ApiError
                            ? probeError.status
                            : undefined,
                        service: summary.label,
                        raw: probeError,
                      }}
                    />
                  </div>
                )}

                {/* Probe results — list of checks */}
                {probe && expanded && (
                  <div className="mt-4 space-y-2">
                    {!probe.deep_probe && (
                      <p className="text-xs text-muted-foreground italic">
                        This service hasn&apos;t implemented a deep test yet, so
                        we did a basic health check instead.
                      </p>
                    )}
                    <ul className="divide-y rounded-md border bg-background">
                      {(probe.checks ?? []).map((check) => {
                        const cmeta =
                          STATUS_META[check.status as Status] ??
                          STATUS_META.unknown;
                        const CIcon = cmeta.icon;
                        return (
                          <li
                            key={check.id}
                            className="flex items-start gap-3 p-3 text-sm"
                          >
                            <CIcon
                              className={`mt-0.5 h-4 w-4 shrink-0 ${
                                check.status === "ok"
                                  ? "text-emerald-600"
                                  : check.status === "degraded"
                                  ? "text-amber-600"
                                  : check.status === "down"
                                  ? "text-red-600"
                                  : "text-slate-500"
                              }`}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-medium">{check.label}</span>
                                <StatusPill status={check.status as Status} />
                                {check.latency_ms !== undefined && (
                                  <span className="text-xs text-muted-foreground">
                                    {formatLatency(check.latency_ms)}
                                  </span>
                                )}
                              </div>
                              {check.detail && (
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {check.detail}
                                </p>
                              )}
                              {check.error && (
                                <pre className="mt-1 max-w-full overflow-x-auto rounded bg-muted/50 p-2 text-[11px] text-foreground/80">
                                  {check.error}
                                </pre>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}

      <footer className="border-t pt-4 text-xs text-muted-foreground">
        Diagnostics are read-only and never change live data. If a test fails,
        the error message tells you the next step. For help, contact your
        EduZim support officer with the request ID shown in the details panel.
      </footer>
    </div>
  );
}
