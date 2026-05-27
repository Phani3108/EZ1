/**
 * Thread detail — Phase 11b / T-011.
 *
 * Shows the message log for one thread (oldest first), with a compose
 * row at the bottom. On mount the page POSTs /read to clear the
 * teacher's unread counter for this thread.
 *
 * Redacted messages render as a plain "[redacted]" placeholder so the
 * thread structure stays intact.
 */

"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Card, CardContent, Button } from "@eduzim/ui";
import { ArrowLeft, Send, MessageCircle } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { comm } from "@/lib/api";
import { useAuth } from "@eduzim/auth";
import type { ChatMessage, MessageThread } from "@eduzim/api-client";

interface ThreadResponse {
  thread: MessageThread;
  messages: ChatMessage[];
}

export default function ThreadPage() {
  const params = useParams();
  const threadId = params.id as string;
  const t = useTranslations("messages");
  const { user } = useAuth();
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, refetch } = useApiQuery<ThreadResponse>(
    () => comm.getThread(threadId),
    [threadId],
  );

  // Mark thread read on mount + on every successful refetch — the
  // teacher is looking at the thread, so any messages from the parent
  // counted as unread shouldn't stay that way. Failure is silent (a
  // false unread count is harmless).
  useEffect(() => {
    if (!data) return;
    comm.markThreadRead(threadId).catch(() => {
      /* non-fatal */
    });
  }, [data, threadId]);

  // Auto-scroll to the bottom whenever the message list changes.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [data?.messages.length]);

  const handleSend = async () => {
    const body = draft.trim();
    if (!body || isSending) return;
    setIsSending(true);
    try {
      await comm.sendMessage(threadId, body);
      setDraft("");
      refetch();
    } catch {
      // Keep the draft so the teacher can retry; surface a toast in a
      // future iteration.
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center gap-3">
        <Link
          href="/messages"
          className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <h1 className="text-xl font-bold tracking-tight flex-1">
          {t("threadDetailTitle")}
        </h1>
      </div>

      <Card>
        <CardContent className="p-0">
          <div
            className="max-h-[60vh] overflow-y-auto p-4 space-y-3"
            data-testid="messages-log"
          >
            {isLoading && (
              <p className="text-sm text-muted-foreground text-center py-8">
                {t("loading")}
              </p>
            )}
            {!isLoading && (data?.messages.length ?? 0) === 0 && (
              <div className="text-center py-8">
                <MessageCircle className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  {t("noMessagesYet")}
                </p>
              </div>
            )}
            {data?.messages.map((m) => {
              const mine = m.sender_user_id === user?.id;
              return (
                <div
                  key={m.id}
                  data-testid={`message-${m.id}`}
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
                        mine ? "text-primary-foreground/70" : "text-muted-foreground"
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
          data-testid="messages-compose-input"
          onKeyDown={(e) => {
            // Enter sends; Shift+Enter inserts a newline.
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        <Button
          onClick={handleSend}
          disabled={isSending || draft.trim().length === 0}
          data-testid="messages-send-button"
          className="flex items-center gap-1"
        >
          <Send className="h-4 w-4" />
          {t("send")}
        </Button>
      </div>
    </div>
  );
}
