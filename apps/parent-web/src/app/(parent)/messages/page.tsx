/**
 * Parent-side messaging inbox + thread view — Phase 11b / T-011
 * + Phase 12 frontend coverage.
 *
 * Mirrors the teacher-web messaging UX. Parent picks a teacher to
 * thread with (or opens an existing thread from the list).
 */

"use client";

import React, { useEffect, useState, useRef, useMemo } from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent, Button } from "@eduzim/ui";
import { MessageCircle, Send, ChevronRight, ArrowLeft } from "lucide-react";
import { useAuth } from "@eduzim/auth";
import { fetchJson, postJson } from "@/lib/api-helpers";


interface Thread {
  id: string;
  teacher_user_id: string;
  parent_user_id: string;
  last_message_at: string | null;
  unread_count: number;
  created_at: string;
}

interface Msg {
  id: string;
  sender_user_id: string;
  sender_role: string;
  body: string;
  redacted: boolean;
  created_at: string;
}


export default function ParentMessagesPage() {
  const t = useTranslations("parentMessages");
  const { user } = useAuth();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThread, setActiveThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [teacherIdInput, setTeacherIdInput] = useState("");
  const [creating, setCreating] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const loadThreads = async () => {
    try {
      const r = await fetchJson<Thread[]>("/api/v1/comm/messages/threads");
      setThreads(r.data);
    } catch {
      setThreads([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadThreads();
  }, []);

  const openThread = async (thread: Thread) => {
    setActiveThread(thread);
    try {
      const r = await fetchJson<{ thread: Thread; messages: Msg[] }>(
        `/api/v1/comm/messages/threads/${thread.id}`,
      );
      setMessages(r.data.messages);
      // Mark read on open.
      await postJson(`/api/v1/comm/messages/threads/${thread.id}/read`, {});
      loadThreads();
    } catch {
      setMessages([]);
    }
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const handleSend = async () => {
    if (!activeThread || isSending || !draft.trim()) return;
    setIsSending(true);
    try {
      await postJson(
        `/api/v1/comm/messages/threads/${activeThread.id}/messages`,
        { body: draft.trim() },
      );
      setDraft("");
      const r = await fetchJson<{ thread: Thread; messages: Msg[] }>(
        `/api/v1/comm/messages/threads/${activeThread.id}`,
      );
      setMessages(r.data.messages);
    } finally {
      setIsSending(false);
    }
  };

  const handleStartThread = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!teacherIdInput.trim() || creating) return;
    setCreating(true);
    try {
      const r = await postJson("/api/v1/comm/messages/threads", {
        other_user_id: teacherIdInput.trim(),
        other_role: "Teacher",
      });
      if (r.ok) {
        await loadThreads();
        setTeacherIdInput("");
      }
    } finally {
      setCreating(false);
    }
  };

  if (activeThread) {
    return (
      <div className="mx-auto max-w-3xl space-y-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveThread(null)}
            className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <h2 className="text-lg font-bold">{t("threadTitle")}</h2>
        </div>
        <Card>
          <CardContent className="p-0">
            <div className="max-h-[60vh] overflow-y-auto p-4 space-y-3">
              {messages.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-6">
                  {t("noMessagesYet")}
                </p>
              )}
              {messages.map((m) => {
                const mine = m.sender_user_id === user?.id;
                return (
                  <div
                    key={m.id}
                    className={`flex ${mine ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                        mine
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-foreground"
                      } ${m.redacted ? "italic opacity-60" : ""}`}
                    >
                      <p className="break-words">{m.body}</p>
                      <p
                        className={`text-xs mt-1 ${
                          mine
                            ? "text-primary-foreground/70"
                            : "text-muted-foreground"
                        }`}
                      >
                        {new Date(m.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </div>
                );
              })}
              <div ref={endRef} />
            </div>
          </CardContent>
        </Card>
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={t("composePlaceholder")}
            rows={2}
            maxLength={4000}
            className="flex-1 rounded-md border px-3 py-2 text-sm bg-background resize-none"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <Button
            onClick={handleSend}
            disabled={isSending || draft.trim().length === 0}
          >
            <Send className="h-4 w-4 mr-1" />
            {t("send")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
      <p className="text-sm text-muted-foreground">{t("description")}</p>

      <Card>
        <CardContent className="p-4">
          <form
            onSubmit={handleStartThread}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={teacherIdInput}
              onChange={(e) => setTeacherIdInput(e.target.value)}
              placeholder={t("teacherIdPlaceholder")}
              className="flex-1 rounded-md border px-3 py-2 text-sm bg-background"
            />
            <Button type="submit" size="sm" disabled={creating}>
              {t("startThread")}
            </Button>
          </form>
        </CardContent>
      </Card>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">{t("loading")}</p>
      ) : threads.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <MessageCircle className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">{t("noThreads")}</p>
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-2">
          {threads.map((th) => (
            <li key={th.id}>
              <button
                type="button"
                onClick={() => openThread(th)}
                className="w-full text-left"
              >
                <Card className="hover:bg-muted/30 transition-colors">
                  <CardContent className="flex items-center gap-3 p-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <MessageCircle className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium">
                          {t("teacherN", { id: th.teacher_user_id.slice(0, 8) })}
                        </p>
                        {th.unread_count > 0 && (
                          <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
                            {th.unread_count}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {th.last_message_at
                          ? new Date(th.last_message_at).toLocaleString()
                          : t("noMessagesYet")}
                      </p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </CardContent>
                </Card>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
