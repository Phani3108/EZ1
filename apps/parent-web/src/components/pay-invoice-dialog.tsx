/**
 * PayInvoiceDialog — parent-facing Paynow flow
 * =============================================
 * Three steps:
 *   1. Pick method (EcoCash / OneMoney / Telecash) + amount + phone.
 *   2. Submit → calls /fees/payments/initiate. Show instructions ("Check
 *      your phone for a USSD prompt").
 *   3. Poll /fees/payments/{ref}/status every 4s for up to 2 minutes;
 *      stop when status is terminal. Show success or FriendlyError.
 *
 * All errors render via <FriendlyError> so a parent always sees a clear
 * sentence + a fix line, not a stack trace.
 */
"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Card,
  CardContent,
  Button,
  FriendlyError,
} from "@eduzim/ui";
import {
  X,
  Smartphone,
  Loader2,
  CheckCircle2,
  Phone,
} from "lucide-react";
import { fees } from "@/lib/api";
import {
  ApiError,
  type Invoice,
  type PaynowMethod,
  type PaymentTransactionStatus,
  type PaynowInitiateResult,
} from "@eduzim/api-client";

type Step = "form" | "waiting" | "done" | "error";

interface Props {
  invoice: Invoice;
  onClose: () => void;
  onPaid?: () => void;
}

const METHODS: { id: PaynowMethod; label: string; tagline: string }[] = [
  { id: "ECOCASH", label: "EcoCash", tagline: "Econet" },
  { id: "ONEMONEY", label: "OneMoney", tagline: "NetOne" },
  { id: "TELECASH", label: "Telecash", tagline: "Telecel" },
];

function fmt(amount: number, currency = "USD") {
  return new Intl.NumberFormat("en-ZW", {
    style: "currency",
    currency,
  }).format(amount);
}

function normalisePhone(input: string): string {
  // Accept "0772123456", "+263772123456", "263 77 212 3456" → +263772123456
  const digits = input.replace(/\D/g, "");
  if (digits.startsWith("263")) return "+" + digits;
  if (digits.startsWith("0")) return "+263" + digits.slice(1);
  return "+" + digits;
}

export function PayInvoiceDialog({ invoice, onClose, onPaid }: Props) {
  const [step, setStep] = useState<Step>("form");
  const [method, setMethod] = useState<PaynowMethod>("ECOCASH");
  const [amount, setAmount] = useState<string>(String(invoice.balance));
  const [phone, setPhone] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [initResult, setInitResult] = useState<PaynowInitiateResult | null>(null);
  const [statusResult, setStatusResult] = useState<PaymentTransactionStatus | null>(null);
  const [error, setError] = useState<unknown>(null);

  // ─── Polling ───
  const pollTimer = useRef<number | null>(null);
  const pollDeadline = useRef<number>(0);

  useEffect(() => {
    return () => {
      if (pollTimer.current) window.clearInterval(pollTimer.current);
    };
  }, []);

  function startPolling(transactionRef: string) {
    pollDeadline.current = Date.now() + 2 * 60 * 1000; // 2 minutes
    const tick = async () => {
      try {
        const { data } = await fees.paymentStatus(transactionRef);
        setStatusResult(data);
        const terminal = ["PAID", "CANCELLED", "FAILED", "EXPIRED"].includes(
          data.status,
        );
        if (terminal) {
          if (pollTimer.current) window.clearInterval(pollTimer.current);
          if (data.status === "PAID") {
            setStep("done");
            onPaid?.();
          } else {
            setError(
              new ApiError(400, {
                code:
                  data.status === "CANCELLED"
                    ? "VALIDATION_FAILED"
                    : "PAYNOW_UNREACHABLE",
                message:
                  data.last_error ||
                  `Payment ${data.status.toLowerCase()}. No money was taken.`,
                details: {},
                request_id: "",
              }),
            );
            setStep("error");
          }
        } else if (Date.now() > pollDeadline.current) {
          if (pollTimer.current) window.clearInterval(pollTimer.current);
          setError(
            new ApiError(504, {
              code: "NET_TIMEOUT",
              message:
                "We didn't get a confirmation from Paynow within 2 minutes.",
              details: {},
              request_id: "",
            }),
          );
          setStep("error");
        }
      } catch (e) {
        // Network blip during polling — keep trying until deadline.
        if (Date.now() > pollDeadline.current) {
          if (pollTimer.current) window.clearInterval(pollTimer.current);
          setError(e);
          setStep("error");
        }
      }
    };
    // Run once immediately, then every 4s
    void tick();
    pollTimer.current = window.setInterval(tick, 4000);
  }

  // ─── Submit ───

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const amt = Number(amount);
    if (!amt || amt <= 0 || amt > invoice.balance) {
      setError(
        new ApiError(422, {
          code: "VALIDATION_FAILED",
          message: `Enter an amount between 0 and ${fmt(invoice.balance, invoice.currency)}.`,
          details: {},
          request_id: "",
        }),
      );
      setStep("error");
      setSubmitting(false);
      return;
    }

    const normalisedPhone = normalisePhone(phone);
    if (normalisedPhone.length < 12) {
      setError(
        new ApiError(422, {
          code: "VALIDATION_FAILED",
          message:
            "Enter your full mobile number, e.g. 0772 123 456.",
          details: {},
          request_id: "",
        }),
      );
      setStep("error");
      setSubmitting(false);
      return;
    }

    try {
      const { data } = await fees.initiatePaynow({
        invoice_id: invoice.id,
        amount: amt,
        method,
        phone: normalisedPhone,
      });
      setInitResult(data);
      setStep("waiting");
      startPolling(data.transaction_ref);
    } catch (e) {
      setError(e);
      setStep("error");
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    if (pollTimer.current) window.clearInterval(pollTimer.current);
    setStep("form");
    setError(null);
    setStatusResult(null);
    setInitResult(null);
  }

  // ─── Render ───

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="pay-dialog-title"
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <Card className="relative w-full max-w-md rounded-b-none sm:rounded-2xl">
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 rounded-full p-1.5 text-muted-foreground hover:bg-muted"
        >
          <X className="h-5 w-5" />
        </button>

        <CardContent className="p-6 space-y-4">
          <header>
            <h2 id="pay-dialog-title" className="text-lg font-bold">
              Pay invoice
            </h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Balance:{" "}
              <span className="font-semibold text-foreground">
                {fmt(invoice.balance, invoice.currency)}
              </span>
            </p>
          </header>

          {step === "form" && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">
                  Choose your wallet
                </legend>
                <div className="grid grid-cols-3 gap-2">
                  {METHODS.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setMethod(m.id)}
                      aria-pressed={method === m.id}
                      className={`rounded-lg border p-3 text-left text-sm transition ${
                        method === m.id
                          ? "border-primary bg-primary/5 ring-2 ring-primary/30"
                          : "border-input hover:border-muted-foreground/40"
                      }`}
                    >
                      <Smartphone className="mb-1 h-4 w-4" />
                      <div className="font-semibold">{m.label}</div>
                      <div className="text-xs text-muted-foreground">
                        {m.tagline}
                      </div>
                    </button>
                  ))}
                </div>
              </fieldset>

              <label className="block">
                <span className="text-sm font-medium">Amount ({invoice.currency})</span>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={invoice.balance}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  required
                  className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-base focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  You can pay any amount up to the balance.
                </p>
              </label>

              <label className="block">
                <span className="text-sm font-medium">Mobile number</span>
                <div className="mt-1 flex items-center rounded-lg border border-input bg-background focus-within:ring-2 focus-within:ring-primary/30">
                  <Phone className="ml-3 h-4 w-4 text-muted-foreground" />
                  <input
                    type="tel"
                    inputMode="tel"
                    placeholder="0772 123 456"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    required
                    className="w-full bg-transparent px-3 py-2 text-base focus:outline-none"
                  />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  We'll send a USSD prompt to this number.
                </p>
              </label>

              <Button
                type="submit"
                disabled={submitting}
                className="w-full"
                size="lg"
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Sending request…
                  </>
                ) : (
                  `Pay ${fmt(Number(amount) || 0, invoice.currency)}`
                )}
              </Button>
            </form>
          )}

          {step === "waiting" && (
            <div className="space-y-3 py-4 text-center">
              <Loader2 className="mx-auto h-10 w-10 animate-spin text-primary" />
              <p className="text-base font-semibold">
                Check your phone — there's a USSD prompt waiting.
              </p>
              <p className="text-sm text-muted-foreground">
                {initResult?.instructions ||
                  "Enter your mobile money PIN to approve the payment."}
              </p>
              {initResult?.demo_mode && (
                <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  Demo mode: no real transaction was created. Paynow keys are
                  not configured.
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Reference: {initResult?.transaction_ref}
              </p>
              {statusResult && statusResult.status !== "PAID" && (
                <p className="text-xs text-muted-foreground">
                  Current status:{" "}
                  <span className="font-medium">{statusResult.status}</span>
                </p>
              )}
              <Button variant="outline" onClick={onClose} className="w-full">
                Close — I'll check back later
              </Button>
            </div>
          )}

          {step === "done" && (
            <div className="space-y-3 py-4 text-center">
              <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-600" />
              <p className="text-lg font-bold">Payment received</p>
              <p className="text-sm text-muted-foreground">
                We've recorded your payment of{" "}
                <span className="font-semibold text-foreground">
                  {fmt(statusResult?.amount ?? 0, statusResult?.currency)}
                </span>
                .
              </p>
              {statusResult?.paynow_reference && (
                <p className="text-xs text-muted-foreground">
                  Receipt reference:{" "}
                  <span className="font-mono">{statusResult.paynow_reference}</span>
                </p>
              )}
              <Button onClick={onClose} className="w-full" size="lg">
                Done
              </Button>
            </div>
          )}

          {step === "error" && (
            <div className="space-y-3">
              <FriendlyError
                variant="inline"
                error={error}
                onRetry={reset}
                technical={{
                  status:
                    error instanceof ApiError ? error.status : undefined,
                  requestId:
                    error instanceof ApiError ? error.requestId : undefined,
                  service: "fees-service · Paynow",
                  raw: error,
                }}
              />
              <Button variant="outline" onClick={onClose} className="w-full">
                Close
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
