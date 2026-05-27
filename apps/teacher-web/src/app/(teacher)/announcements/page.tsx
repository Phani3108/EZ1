/**
 * Announcements page — 10B-1D + 10B-4A offline queue.
 * Teacher can view feed and send class-scoped announcements.
 */

"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle, Button, Input } from "@eduzim/ui";
import { Megaphone, ChevronRight, Send, Plus, X } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { useSync } from "@/lib/sync-provider";
import { comm } from "@/lib/api";
import type { Announcement } from "@eduzim/api-client";

export default function AnnouncementsPage() {
  const t = useTranslations("announcements");
  const tCommon = useTranslations("common");
  const [showForm, setShowForm] = useState(false);

  const { data: announcements, isLoading, refetch } = useApiQuery<Announcement[]>(
    () => comm.getFeed({ limit: "20" }),
    []
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <Button
          size="sm"
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5"
        >
          {showForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showForm ? tCommon("cancel") : t("send")}
        </Button>
      </div>

      {showForm && (
        <SendAnnouncementForm
          onSuccess={() => {
            setShowForm(false);
            refetch();
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-4">
                <div className="h-4 w-48 bg-muted rounded mb-2" />
                <div className="h-3 w-32 bg-muted rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : announcements && announcements.length > 0 ? (
        <div className="space-y-2">
          {announcements.map((a) => (
            <Card key={a.id}>
              <CardContent className="flex items-start gap-3 p-4">
                <Megaphone className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{a.title}</p>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {a.body}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {a.audience_type}
                    {a.audience_class_id ? " · Class" : ""}
                    {" · "}
                    {new Date(a.created_at).toLocaleDateString()}
                  </p>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="p-6 text-center text-sm text-muted-foreground">
            {t("noAnnouncements")}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SendAnnouncementForm({
  onSuccess,
  onCancel,
}: {
  onSuccess: () => void;
  onCancel: () => void;
}) {
  // RULE-4 (Phase 11b): the teacher-side announcement form no longer
  // shows an audience picker. Every send goes to `TEACHER_CLASSES`,
  // which the backend resolver expands to "all parents of the
  // teacher's classes". That is the only audience a teacher should be
  // able to address — if a teacher needs to reach all-school, that's
  // an admin-only action via the admin web, not the teacher app.
  const t = useTranslations("announcements");
  const tCommon = useTranslations("common");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { enqueueOffline } = useSync();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim()) return;

    setIsSending(true);
    setError(null);

    // RULE-4: hardcoded audience — no picker.
    const payload = {
      title: title.trim(),
      body: body.trim(),
      audience: { type: "TEACHER_CLASSES" },
      channels: ["IN_APP"],
    };

    try {
      await enqueueOffline({
        type: "ANNOUNCEMENT",
        schoolId: "",
        userId: "",
        deviceId: `teacher-web:ann`,
        payload,
        syncBatchId: `ann-${Date.now()}`,
      });
      onSuccess();
    } catch {
      setError(t("sendFailed"));
    } finally {
      setIsSending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("newAnnouncement")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4" data-testid="teacher-announcement-form">
          <div>
            <label className="text-sm font-medium mb-1 block">
              {t("announcementTitle")}
            </label>
            <Input
              value={title}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTitle(e.target.value)}
              placeholder={t("titlePlaceholder")}
              required
            />
          </div>

          <div>
            <label className="text-sm font-medium mb-1 block">
              {t("announcementBody")}
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("bodyPlaceholder")}
              className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[80px] resize-y"
              required
            />
          </div>

          {/* RULE-4: the audience picker is gone. We show a small
              read-only confirmation instead so the teacher knows
              exactly where the message is going. */}
          <div
            className="rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground"
            data-testid="teacher-announcement-audience-hint"
          >
            {t("audienceHintTeacherClasses")}
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <div className="flex gap-2">
            <Button type="submit" disabled={isSending} className="flex items-center gap-1.5">
              <Send className="h-4 w-4" />
              {isSending ? tCommon("loading") : t("send")}
            </Button>
            <Button type="button" variant="outline" onClick={onCancel}>
              {tCommon("cancel")}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
