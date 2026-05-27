/**
 * Phase 15d — Ministry onboarding queue.
 *
 * Cross-tenant view of every school the Ministry user is allowed to see,
 * grouped by readiness state. Users holding `Ministry+Provisioner` (or
 * `EduZimOps`) get a "+ New school" button to invite the first
 * SchoolAdmin.
 *
 * Permission gate: Ministry role (set by parent layout). The "+ New
 * school" button checks for `school:create` in the actor's permissions.
 */
"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "@eduzim/auth";
import {
  ministryApi,
  type MinistrySchool,
  type EnrolmentDistrictRow,
} from "@/lib/ministry-api";
import { invitationsApi } from "@/lib/onboarding-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Dialog, DialogHeader, DialogTitle, DialogFooter,
  Input, Label, Alert, AlertTitle, AlertDescription,
} from "@eduzim/ui";

const STATUS_GROUPS = {
  live: { label: "🟢 Live", color: "border-emerald-500" },
  setup: { label: "🟡 Setting up", color: "border-amber-500" },
  new: { label: "🔴 New", color: "border-red-500" },
};

export default function MinistryOnboardingPage() {
  const { user, hasPermission } = useAuth();
  const canProvision = hasPermission("school:create");

  const [schools, setSchools] = useState<MinistrySchool[]>([]);
  const [loading, setLoading] = useState(true);
  const [openModal, setOpenModal] = useState(false);

  useEffect(() => {
    ministryApi
      .schools()
      .then((r) => setSchools(r.data))
      .finally(() => setLoading(false));
  }, []);

  // For v1 the readiness-by-school overlay is computed in admin-web
  // from each school's onboarding status. Ministry-side, we don't have
  // per-school onboarding status without going cross-tenant via
  // EduZimOps. So we group by `is_active` + heuristic for v1; the
  // proper roll-up is a Phase 15+ follow-up.
  const grouped = useMemo(() => {
    const out: Record<"live" | "setup" | "new", MinistrySchool[]> = {
      live: [],
      setup: [],
      new: [],
    };
    for (const s of schools) {
      // is_active=true & has a province_code → "setup" (we don't have
      // is_live cross-tenant here yet); is_active=false → "new".
      // The proper bucket needs a /ministry/onboarding/rollup endpoint
      // that aggregates each school's onboarding/status — Phase 15+ TBD.
      if (!s.is_active) out.new.push(s);
      else out.setup.push(s);
    }
    return out;
  }, [schools]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">School onboarding</h1>
          <p className="text-sm text-muted-foreground">
            Every school in the Ministry's view, grouped by readiness.
          </p>
        </div>
        {canProvision && (
          <Button onClick={() => setOpenModal(true)}>+ New school</Button>
        )}
      </div>

      {loading ? (
        <div className="h-48 animate-pulse rounded bg-muted" />
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {(Object.keys(STATUS_GROUPS) as Array<"live" | "setup" | "new">).map((g) => (
            <Card key={g} className={`border-l-4 ${STATUS_GROUPS[g].color}`}>
              <CardHeader>
                <CardTitle className="text-base">
                  {STATUS_GROUPS[g].label} ({grouped[g].length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                {grouped[g].length === 0 ? (
                  <div className="text-xs text-muted-foreground">—</div>
                ) : (
                  grouped[g].slice(0, 12).map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center justify-between border-b last:border-0 py-1.5 text-sm"
                    >
                      <span className="truncate">{s.name}</span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {s.district_code ?? s.province_code ?? "—"}
                      </span>
                    </div>
                  ))
                )}
                {grouped[g].length > 12 && (
                  <div className="text-xs text-muted-foreground pt-2">
                    +{grouped[g].length - 12} more
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {openModal && (
        <NewSchoolModal
          onClose={() => setOpenModal(false)}
          onCreated={() => {
            setOpenModal(false);
            // Re-fetch the list.
            setLoading(true);
            ministryApi
              .schools()
              .then((r) => setSchools(r.data))
              .finally(() => setLoading(false));
          }}
        />
      )}
    </div>
  );
}


function NewSchoolModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [province, setProvince] = useState("");
  const [district, setDistrict] = useState("");
  const [schoolType, setSchoolType] = useState("COMBINED");
  const [adminFullName, setAdminFullName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPhone, setAdminPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manualCode, setManualCode] = useState<string | null>(null);

  const handleSubmit = async () => {
    setBusy(true);
    setError(null);
    try {
      const base =
        process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      // 1. Create the school.
      const schoolRes = await fetch(`${base}/api/v1/schools`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name,
          province_code: province || undefined,
          district_code: district || undefined,
          school_type: schoolType,
        }),
      });
      const schoolJ = await schoolRes.json();
      if (!schoolRes.ok) {
        setError(schoolJ?.error?.message ?? "Could not create school.");
        return;
      }
      const schoolId = (schoolJ.data as any)?.id;
      // 2. Invite the first SchoolAdmin.
      const invRes = await invitationsApi.create({
        school_id: schoolId,
        role: "SchoolAdmin",
        full_name: adminFullName,
        contact_email: adminEmail || undefined,
        contact_phone: adminPhone || undefined,
      });
      const inv = invRes.data;
      setManualCode(inv.manual_code);
      // 3. Dispatch.
      await invitationsApi.dispatch({
        invitation_id: inv.id,
        school_name: name,
        role: "SchoolAdmin",
        full_name: adminFullName,
        contact_email: adminEmail || undefined,
        contact_phone: adminPhone || undefined,
        manual_code: inv.manual_code,
        invite_url: `${window.location.origin}/invite/${inv.raw_token}`,
      });
    } catch (e: any) {
      setError(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={onClose}>
      <DialogHeader>
        <DialogTitle>Onboard a new school</DialogTitle>
      </DialogHeader>
      <div className="space-y-3 p-4">
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Could not create</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {manualCode && (
          <Alert>
            <AlertTitle>School created · invite dispatched</AlertTitle>
            <AlertDescription>
              Activation code: <span className="font-mono text-lg font-bold">{manualCode}</span>
              {" "}— read this out to the admin if they don't receive the SMS/email.
            </AlertDescription>
          </Alert>
        )}
        <div className="space-y-2">
          <Label htmlFor="name">School name</Label>
          <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-2">
            <Label htmlFor="province">Province code</Label>
            <Input id="province" value={province} onChange={(e) => setProvince(e.target.value)} placeholder="HRE" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="district">District code</Label>
            <Input id="district" value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="hre-cn" />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="schoolType">School type</Label>
          <select
            id="schoolType"
            value={schoolType}
            onChange={(e) => setSchoolType(e.target.value)}
            className="w-full rounded-md border bg-background px-2 py-1.5 text-sm"
          >
            <option>PRIMARY</option>
            <option>SECONDARY</option>
            <option>COMBINED</option>
          </select>
        </div>
        <div className="border-t pt-3 space-y-2">
          <Label>First SchoolAdmin</Label>
          <Input value={adminFullName} onChange={(e) => setAdminFullName(e.target.value)} placeholder="Full name" />
          <Input value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} placeholder="Email" type="email" />
          <Input value={adminPhone} onChange={(e) => setAdminPhone(e.target.value)} placeholder="+263770…" type="tel" />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>{manualCode ? "Close" : "Cancel"}</Button>
        {!manualCode && (
          <Button onClick={handleSubmit} disabled={busy || !name || !adminFullName || (!adminEmail && !adminPhone)}>
            {busy ? "Creating…" : "Create school + invite admin"}
          </Button>
        )}
        {manualCode && <Button onClick={onCreated}>Done</Button>}
      </DialogFooter>
    </Dialog>
  );
}
