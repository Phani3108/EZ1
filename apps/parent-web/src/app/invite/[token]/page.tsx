/**
 * Phase 15c — Parent invite landing.
 *
 * Public route (no auth). Renders the invite preview, accepts a
 * password, activates the account, and lands the parent on /home with
 * their children pre-listed.
 */
"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardHeader, CardTitle, CardContent, Button, Input, Alert, AlertTitle, AlertDescription } from "@eduzim/ui";

/**
 * Phase 19b H7 — friendly invite-error copy.
 * Replaces the generic "Sorry: <backend message>" with per-status copy
 * so a parent can tell apart "link expired" from "code wrong" from
 * "server down".
 */
function _friendlyInviteError(status: number, body: any): string {
  const code = body?.error?.code as string | undefined;
  if (status === 404 || code === "NOT_FOUND" || code === "INVALID_TOKEN") {
    return "This invitation link isn't valid. Ask your school admin to send you a new one.";
  }
  if (status === 410 || code === "EXPIRED") {
    return "This invitation has expired. Ask your school admin to send you a fresh link.";
  }
  if (status === 409 || code === "ALREADY_ACTIVATED" || code === "ALREADY_USED") {
    return "You've already activated this account. Sign in with your password instead.";
  }
  if (status === 429 || code === "RATE_LIMITED") {
    return "Too many attempts — please wait a minute and try again.";
  }
  if (status >= 500) {
    return "Something went wrong on our side. Please try again in a minute.";
  }
  return body?.error?.message ?? "Could not process this invitation.";
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface Preview {
  school_id: string;
  role: string;
  full_name: string;
  target_resource_type: string | null;
  expires_at: string;
}

export default function InviteLanding() {
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
        const j = await r.json().catch(() => ({}));
        if (!r.ok) {
          // Phase 19b H7 — specific copy per failure mode so the user
          // doesn't see a generic "Sorry" for every error. The backend
          // already returns appropriate codes; we just translate.
          setError(_friendlyInviteError(r.status, j));
        } else {
          setPreview(j.data);
        }
      })
      .catch(() =>
        setError(
          "Couldn't reach EduZim — check your internet connection and try again."
        ),
      )
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
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(_friendlyInviteError(r.status, j));
      } else {
        // Land on /home — the user will be prompted to log in normally.
        router.push("/login?activated=1");
      }
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
            <div className="mt-4 text-sm text-muted-foreground">
              Ask your school admin to send you a fresh invitation, or use
              your activation code if you have one.
            </div>
            <Button className="mt-3" variant="outline" onClick={() => router.push("/invite/code")}>
              Use an activation code
            </Button>
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
            Your school has set up an EduZim {preview.role.toLowerCase()}{" "}
            account for you. Choose a password to activate it.
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
              autoComplete="new-password"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
              placeholder="At least 8 characters"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="confirm">
              Confirm password
            </label>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          <Button onClick={handleAccept} disabled={submitting || !pwd}>
            {submitting ? "Activating…" : "Activate my account"}
          </Button>
          <div className="text-xs text-muted-foreground text-center">
            This invitation expires{" "}
            {new Date(preview.expires_at).toLocaleDateString()}.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
