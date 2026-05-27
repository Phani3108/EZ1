/**
 * Phase 15b — Setup wizard: parents step.
 *
 * Review parent invitations. Per-row "Show manual code" reveals the
 * 6-digit fallback to read out over the phone.
 */
"use client";

import React, { useEffect, useState } from "react";
import { useSetup } from "../setup-context";
import { onboardingApi, type InviteRow, type InviteOutboxRow } from "@/lib/onboarding-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, InvitationStatusPill,
} from "@eduzim/ui";

export default function ParentsSetup() {
  const { refresh } = useSetup();
  const [invites, setInvites] = useState<InviteRow[]>([]);
  const [outbox, setOutbox] = useState<InviteOutboxRow[]>([]);
  const [showCode, setShowCode] = useState<Set<string>>(new Set());

  const load = () => {
    onboardingApi.listInviteRequests({ role: "Parent" })
      .then((r) => setInvites(r.data));
    onboardingApi.listInviteOutbox()
      .then((r) => setOutbox(r.data.filter((x) => x.channel === "manual" || x.status === "manual_pending")));
  };

  useEffect(load, []);

  // Match outbox rows to invite-request rows via identity_invitation_id.
  const codeByInvitation = new Map<string, string>(
    outbox.map((o) => [o.invitation_id, o.manual_code ?? ""]),
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Parent invitations</CardTitle>
        </CardHeader>
        <CardContent>
          {invites.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No parent invites yet. Upload students with parent contact info
              to populate this list.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4">Parent</th>
                    <th className="py-2 pr-4">Contact</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Manual code</th>
                  </tr>
                </thead>
                <tbody>
                  {invites.map((p) => {
                    const code = p.identity_invitation_id
                      ? codeByInvitation.get(p.identity_invitation_id)
                      : undefined;
                    const revealed = showCode.has(p.id);
                    return (
                      <tr key={p.id} className="border-b last:border-0">
                        <td className="py-2 pr-4">{p.full_name}</td>
                        <td className="py-2 pr-4 text-xs">
                          {p.contact_phone || p.contact_email || "—"}
                        </td>
                        <td className="py-2 pr-4">
                          <InvitationStatusPill
                            status={
                              p.request_status === "dispatched"
                                ? "sent"
                                : p.request_status === "failed"
                                  ? "failed"
                                  : "queued"
                            }
                          />
                        </td>
                        <td className="py-2 pr-4">
                          {code ? (
                            revealed ? (
                              <span className="font-mono text-base font-bold">
                                {code}
                              </span>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setShowCode(
                                    new Set([...showCode, p.id]),
                                  );
                                }}
                              >
                                Show
                              </Button>
                            )
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              —
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
