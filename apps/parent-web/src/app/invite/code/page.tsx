/**
 * Phase 15c — Manual-code activation (offline fallback).
 *
 * Parent enters phone + 6-digit code (read out by admin) + password.
 * Same backend semantics as the token path.
 */
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardHeader, CardTitle, CardContent, Button, Input, Alert, AlertTitle, AlertDescription } from "@eduzim/ui";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function InviteByCode() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [pwd, setPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (pwd !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    if (pwd.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (code.length !== 6) {
      setError("The activation code is 6 digits.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/v1/invitations/by-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, code, password: pwd }),
      });
      const j = await r.json();
      if (!r.ok) {
        setError(j?.error?.message ?? "Activation failed.");
      } else {
        router.push("/login?activated=1");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
      <Card className="max-w-md w-full">
        <CardHeader>
          <CardTitle className="text-lg">Activate with a code</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Your school admin will read you a 6-digit code over the phone.
            Enter it below along with your phone number and choose a
            password.
          </p>
          {error && (
            <Alert variant="destructive">
              <AlertTitle>Could not activate</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="phone">
              Your phone number
            </label>
            <Input
              id="phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+263770…"
              autoComplete="tel"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="code">
              Activation code
            </label>
            <Input
              id="code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="6 digits"
              inputMode="numeric"
              maxLength={6}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="pwd">
              Choose a password
            </label>
            <Input
              id="pwd"
              type="password"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
              placeholder="At least 8 characters"
              autoComplete="new-password"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="confirm">
              Confirm password
            </label>
            <Input
              id="confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          <Button onClick={handleSubmit} disabled={submitting || !phone || !code || !pwd}>
            {submitting ? "Activating…" : "Activate my account"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
