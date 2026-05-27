/**
 * Phase 16g — HoD question-draft review (admin-web).
 *
 * Same shape as teacher-web's drafts page, lives in admin-web for HoDs
 * who do their reviews alongside other admin work.
 */
"use client";

import React, { useEffect, useState } from "react";
import { questionBankApi, type QuestionDraftRow } from "@/lib/curriculum-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Input, Alert, AlertTitle, AlertDescription, Badge,
} from "@eduzim/ui";

export default function HodReviewPage() {
  const [drafts, setDrafts] = useState<QuestionDraftRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  const load = () => {
    setLoading(true);
    questionBankApi
      .listDrafts("pending")
      .then((r) => setDrafts(r.data))
      .catch((e: any) => setError(e?.detail ?? String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleApprove = async (id: string) => {
    setError(null);
    try {
      await questionBankApi.approveDraft(id);
      load();
    } catch (e: any) {
      setError(e?.detail ?? String(e));
    }
  };

  const handleReject = async (id: string) => {
    if (!reason.trim()) return;
    setError(null);
    try {
      await questionBankApi.rejectDraft(id, reason.trim());
      setRejecting(null);
      setReason("");
      load();
    } catch (e: any) {
      setError(e?.detail ?? String(e));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Question-draft review</h1>
        <p className="text-sm text-muted-foreground">
          Teacher-submitted questions waiting for HoD approval.
          Rejection reasons are visible to the submitter (single audit
          free-text exception per ADR 018, 200-char cap).
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Action failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="h-48 animate-pulse rounded bg-muted" />
      ) : drafts.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No pending drafts.
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-3">
          {drafts.map((d) => (
            <li key={d.id}>
              <Card>
                <CardContent className="pt-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge>{d.question_type}</Badge>
                    <Badge variant="outline">Difficulty {d.difficulty}</Badge>
                    <span className="text-xs text-muted-foreground">
                      Submitted{" "}
                      {d.submitted_at
                        ? new Date(d.submitted_at).toLocaleString()
                        : "—"}
                    </span>
                  </div>
                  <div className="text-sm font-medium">{d.text}</div>
                  {d.options_json.length > 0 && (
                    <ol className="ml-4 space-y-1">
                      {d.options_json.map((o, i) => (
                        <li key={i} className="text-sm">
                          <span className="font-mono mr-2">{o.label}.</span>
                          <span className={o.is_correct ? "text-green-700 font-medium" : ""}>
                            {o.text}
                            {o.is_correct && " ✓"}
                          </span>
                        </li>
                      ))}
                    </ol>
                  )}
                  {d.correct_answer_text && d.question_type !== "MCQ" && (
                    <div className="text-xs text-green-700">
                      Expected: {d.correct_answer_text}
                    </div>
                  )}
                  {rejecting === d.id ? (
                    <div className="flex items-center gap-2">
                      <Input
                        autoFocus
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="Reason (max 200 chars)"
                        maxLength={200}
                      />
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleReject(d.id)}
                      >
                        Confirm reject
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => { setRejecting(null); setReason(""); }}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => handleApprove(d.id)}>
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setRejecting(d.id)}
                      >
                        Reject
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
