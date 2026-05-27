/**
 * Phase 15c — Teacher invite landing.
 *
 * Same shape as parent-web. Teacher's classes are pre-attached
 * via the InviteRequest flow (admin-web dispatches → identity
 * activates → ClassTeacherAssignment is wired by admin-web at
 * dispatch time).
 */
"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardHeader, CardTitle, CardContent, Button, Input, Alert, AlertTitle, AlertDescription } from "@eduzim/ui";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface Preview {
  school_id: string;
  role: string;
  full_name: string;
  expires_at: string;
}

export default function TeacherInviteLanding() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = params?.token ?? "";

  const [preview, setPreview] = useState<Preview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pwd, setPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/v1/invitations/${token}/preview`)
      .then(async (r) => {
        const j = await r.json();
        if (!r.ok) setError(j?.error?.message ?? "Could not load.");
        else setPreview(j.data);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [token]);

  const handleAccept = async () => {
    if (pwd !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    if (pwd.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch(
        `${API_BASE}/api/v1/invitations/${token}/accept`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password: pwd }),
        },
      );
      const j = await r.json();
      if (!r.ok) setError(j?.error?.message ?? "Activation failed.");
      else router.push("/login?activated=1");
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error && !preview) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Card className="max-w-md w-full">
          <CardHeader>
            <CardTitle className="text-base">Invitation not available</CardTitle>
          </CardHeader>
          <CardContent>
            <Alert variant="destructive">
              <AlertTitle>Sorry</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!preview) return null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
      <Card className="max-w-md w-full">
        <CardHeader>
          <CardTitle className="text-lg">
            Welcome, {preview.full_name} 👋
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Your school has set up an EduZim teacher account. Pick a
            password to activate it; your classes will be ready when you
            log in.
          </p>
          {error && (
            <Alert variant="destructive">
              <AlertTitle>Could not activate</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
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
          <Button onClick={handleAccept} disabled={submitting || !pwd}>
            {submitting ? "Activating…" : "Activate"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
