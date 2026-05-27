/**
 * Connect — Phase 12e parent-side surfaces consolidated.
 *
 *   - Grievances (P-007): list own + submit new
 *   - Conference bookings (P-005): list available slots + book
 *   - Permission slips (P-006): list open slips + sign
 *
 * One page over three card sections — same compaction strategy as
 * teacher-web's /plan + /student-life pages.
 */

"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Card, CardContent, CardHeader, CardTitle, Button,
} from "@eduzim/ui";
import {
  HeartHandshake, MessageSquareWarning, CalendarClock, FileSignature, Plus,
} from "lucide-react";
import { useChild } from "@/lib/child-context";
import { fetchJson, postJson } from "@/lib/api-helpers";


interface Grievance {
  id: string; subject: string; body: string;
  status: string;
  created_at: string;
  resolution_notes: string | null;
}

interface Slot {
  id: string;
  teacher_user_id: string;
  starts_at: string;
  duration_minutes: number;
  is_booked: boolean;
}

interface Slip {
  id: string;
  title: string;
  description: string;
  deadline: string | null;
}


export default function ConnectPage() {
  const t = useTranslations("parentConnect");
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <HeartHandshake className="h-5 w-5" />
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>
      <GrievancesSection />
      <ConferencesSection />
      <PermissionSlipsSection />
    </div>
  );
}


// ─── Grievances ────────────────────────────────────────────────────


function GrievancesSection() {
  const t = useTranslations("parentConnect");
  const { selected } = useChild();
  const [list, setList] = useState<Grievance[]>([]);
  const [refresh, setRefresh] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetchJson<Grievance[]>("/api/v1/grievances");
        setList(r.data);
      } catch {
        setList([]);
      }
    })();
  }, [refresh]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !body.trim() || sending) return;
    setSending(true);
    try {
      const r = await postJson("/api/v1/grievances", {
        subject: subject.trim(),
        body: body.trim(),
        student_id: selected?.id,
      });
      if (r.ok) {
        setSubject("");
        setBody("");
        setShowForm(false);
        setRefresh((n) => n + 1);
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquareWarning className="h-4 w-4" /> {t("grievances.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button
          type="button"
          size="sm"
          onClick={() => setShowForm((v) => !v)}
        >
          <Plus className="h-3.5 w-3.5 mr-1" />
          {showForm ? t("cancel") : t("grievances.create")}
        </Button>

        {showForm && (
          <form onSubmit={submit} className="border rounded-md p-3 space-y-2 bg-muted/20">
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder={t("grievances.subjectPlaceholder")}
              className="w-full rounded-md border px-3 py-2 text-sm bg-background"
              required
            />
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("grievances.bodyPlaceholder")}
              className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[80px]"
              required
            />
            <Button type="submit" size="sm" disabled={sending}>
              {sending ? t("loading") : t("grievances.submit")}
            </Button>
          </form>
        )}

        {list.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("grievances.empty")}</p>
        ) : (
          <ul className="space-y-2">
            {list.map((g) => (
              <li key={g.id} className="border rounded-md p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{g.subject}</span>
                  <span
                    className={`text-xs rounded-full px-2 py-0.5 ${
                      g.status === "resolved"
                        ? "bg-green-100 text-green-700"
                        : g.status === "dismissed"
                        ? "bg-muted text-muted-foreground"
                        : g.status === "in_review"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    {g.status}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">{g.body}</p>
                {g.resolution_notes && (
                  <p className="text-xs text-green-700 mt-1">
                    {t("grievances.resolution", { notes: g.resolution_notes })}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


// ─── Conferences ───────────────────────────────────────────────────


function ConferencesSection() {
  const t = useTranslations("parentConnect");
  const { selected } = useChild();
  const [teacherId, setTeacherId] = useState("");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    if (!teacherId) {
      setSlots([]);
      return;
    }
    (async () => {
      try {
        const r = await fetchJson<Slot[]>(
          `/api/v1/conference-slots?teacher_user_id=${teacherId}&available_only=true`,
        );
        setSlots(r.data);
      } catch {
        setSlots([]);
      }
    })();
  }, [teacherId, refresh]);

  const book = async (slotId: string) => {
    if (!selected) return;
    const r = await postJson("/api/v1/conference-bookings", {
      slot_id: slotId,
      student_id: selected.id,
    });
    if (r.ok) setRefresh((n) => n + 1);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarClock className="h-4 w-4" /> {t("conferences.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">{t("conferences.hint")}</p>
        <input
          type="text"
          value={teacherId}
          onChange={(e) => setTeacherId(e.target.value)}
          placeholder={t("conferences.teacherIdPlaceholder")}
          className="w-full rounded-md border px-3 py-2 text-sm bg-background"
        />
        {teacherId && slots.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {t("conferences.noSlots")}
          </p>
        )}
        {slots.length > 0 && (
          <ul className="space-y-2">
            {slots.map((s) => (
              <li
                key={s.id}
                className="border rounded-md p-3 text-sm flex items-center justify-between"
              >
                <span>
                  {new Date(s.starts_at).toLocaleString()} · {s.duration_minutes}m
                </span>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => book(s.id)}
                  disabled={!selected || s.is_booked}
                >
                  {s.is_booked ? t("conferences.booked") : t("conferences.book")}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}


// ─── Permission slips ──────────────────────────────────────────────


function PermissionSlipsSection() {
  const t = useTranslations("parentConnect");
  const { selected } = useChild();
  const [slips, setSlips] = useState<Slip[]>([]);
  const [signing, setSigning] = useState<string | null>(null);
  const [signedName, setSignedName] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const r = await fetchJson<Slip[]>("/api/v1/permission-slips");
        setSlips(r.data);
      } catch {
        setSlips([]);
      }
    })();
  }, []);

  const sign = async (
    slip: Slip, decision: "approved" | "declined",
  ) => {
    if (!selected || !signedName.trim()) return;
    const r = await postJson(
      `/api/v1/permission-slips/${slip.id}/responses`,
      {
        student_id: selected.id,
        decision,
        signed_full_name: signedName.trim(),
      },
    );
    if (r.ok) {
      setSigning(null);
      setSignedName("");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileSignature className="h-4 w-4" /> {t("slips.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {slips.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("slips.empty")}</p>
        ) : (
          <ul className="space-y-2">
            {slips.map((p) => (
              <li key={p.id} className="border rounded-md p-3 text-sm">
                <div className="font-medium">{p.title}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {p.description}
                </p>
                {p.deadline && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {t("slips.deadline", { date: p.deadline })}
                  </p>
                )}
                {signing === p.id ? (
                  <div className="mt-2 space-y-2">
                    <input
                      type="text"
                      value={signedName}
                      onChange={(e) => setSignedName(e.target.value)}
                      placeholder={t("slips.namePlaceholder")}
                      className="w-full rounded-md border px-3 py-2 text-sm bg-background"
                    />
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => sign(p, "approved")}
                        disabled={!signedName.trim() || !selected}
                      >
                        {t("slips.approve")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => sign(p, "declined")}
                        disabled={!signedName.trim() || !selected}
                      >
                        {t("slips.decline")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setSigning(null)}
                      >
                        {t("cancel")}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => setSigning(p.id)}
                    className="mt-2"
                  >
                    {t("slips.respond")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
