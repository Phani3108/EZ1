/**
 * Phase 16h — Ministry-side National Curriculum publishing.
 *
 * Read view for plain Ministry users (audit-tracked).
 * Provisioner / EduZimOps see write actions (publish, +new) via the
 * `school:create` permission check.
 */
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@eduzim/auth";
import { curriculumApi, type NationalSubjectRow } from "@/lib/curriculum-api";
import { api } from "@/lib/api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Alert, AlertTitle, AlertDescription,
  Dialog, DialogHeader, DialogTitle, DialogFooter,
  Input, Label,
} from "@eduzim/ui";

export default function MinistryCurriculumPage() {
  const { hasPermission } = useAuth();
  const canPublish = hasPermission("school:create");

  const [subjects, setSubjects] = useState<NationalSubjectRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    curriculumApi
      .listNationalSubjects({ published_only: false })
      .then((r) => setSubjects(r.data))
      .catch((e: any) => setError(e?.detail ?? String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handlePublish = async (s: NationalSubjectRow) => {
    setBusyId(s.id);
    setError(null);
    try {
      await api.post(`/api/v1/ministry/national-curriculum/subjects/${s.id}/publish`);
      load();
    } catch (e: any) {
      setError(e?.detail ?? String(e));
    } finally {
      setBusyId(null);
    }
  };

  const published = subjects.filter((s) => s.ministry_published_at);
  const drafts = subjects.filter((s) => !s.ministry_published_at);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">National Curriculum</h1>
          <p className="text-sm text-muted-foreground">
            ZIMSEC reference subjects + units + topics. Schools click
            "Adopt" on published subjects to clone the tree into their
            own curriculum.
          </p>
        </div>
        {canPublish && (
          <div className="flex gap-2">
            <Button variant="outline">
              <Link href="/ministry/curriculum/import">Bulk import (CSV)</Link>
            </Button>
            <Button onClick={() => setShowNew(true)}>+ New subject</Button>
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="h-48 animate-pulse rounded bg-muted" />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Published ({published.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {published.length === 0 ? (
                <div className="text-sm text-muted-foreground">
                  Nothing published yet. Schools can't adopt any
                  subjects until published.
                </div>
              ) : (
                <ul className="divide-y">
                  {published.map((s) => (
                    <li key={s.id} className="py-2 flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium">{s.name}</div>
                        <div className="text-xs font-mono text-muted-foreground">
                          {s.country} · {s.code} · published{" "}
                          {s.ministry_published_at
                            ? new Date(s.ministry_published_at).toLocaleDateString()
                            : "—"}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Drafts ({drafts.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {drafts.length === 0 ? (
                <div className="text-sm text-muted-foreground">
                  No drafts.
                </div>
              ) : (
                <ul className="divide-y">
                  {drafts.map((s) => (
                    <li key={s.id} className="py-2 flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium">{s.name}</div>
                        <div className="text-xs font-mono text-muted-foreground">
                          {s.country} · {s.code}
                        </div>
                      </div>
                      {canPublish && (
                        <Button
                          size="sm"
                          onClick={() => handlePublish(s)}
                          disabled={busyId === s.id}
                        >
                          {busyId === s.id ? "Publishing…" : "Publish"}
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {showNew && (
        <NewNationalSubjectModal
          onClose={() => setShowNew(false)}
          onCreated={() => {
            setShowNew(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function NewNationalSubjectModal({
  onClose, onCreated,
}: { onClose: () => void; onCreated: () => void }) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/ministry/national-curriculum/subjects", {
        code, name, description,
      });
      onCreated();
    } catch (e: any) {
      setError(e?.detail ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={onClose}>
      <DialogHeader>
        <DialogTitle>New national subject</DialogTitle>
      </DialogHeader>
      <div className="space-y-3 p-4">
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Could not create</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="space-y-2">
          <Label htmlFor="code">Subject code</Label>
          <Input id="code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="ZIM-MATH-FRM1" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Subject name</Label>
          <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Form 1 Mathematics" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="description">Description</Label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded border bg-background p-2 text-sm"
            placeholder="Brief description of scope and grade level."
          />
        </div>
        <p className="text-xs text-muted-foreground">
          The subject is created in draft state. Click Publish on the
          previous screen when ready for schools to adopt.
        </p>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button onClick={submit} disabled={busy || !code.trim() || !name.trim()}>
          {busy ? "Creating…" : "Create draft"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
