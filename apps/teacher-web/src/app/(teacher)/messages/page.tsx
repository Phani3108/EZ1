/**
 * Messages inbox — Phase 11b / T-011.
 *
 * Lists every parent-teacher thread the current teacher participates in,
 * sorted by `last_message_at` descending. Unread threads get a count
 * badge. Clicking a row navigates to the thread page where the teacher
 * sees the full message log and can send replies.
 *
 * Creating a NEW thread from scratch (teacher → parent) is wired here
 * too: the teacher picks a parent from a child's roster (a future
 * iteration); for now this MVP relies on parent-initiated threads OR
 * the teacher knowing the parent's user_id. A parent picker is a
 * Phase 11b polish item.
 */

"use client";

import React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@eduzim/ui";
import { MessageCircle, ChevronRight } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { comm } from "@/lib/api";
import { useAuth } from "@eduzim/auth";
import type { MessageThread } from "@eduzim/api-client";

export default function MessagesInboxPage() {
  const t = useTranslations("messages");
  const { user } = useAuth();

  const { data: threads, isLoading } = useApiQuery<MessageThread[]>(
    () => comm.listThreads(),
    [],
  );

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-3">
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        {[1, 2, 3].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-4">
              <div className="h-4 w-48 bg-muted rounded mb-2" />
              <div className="h-3 w-32 bg-muted rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <span className="text-sm text-muted-foreground">
          {threads?.length ?? 0} {t("threadsCount")}
        </span>
      </div>

      {(!threads || threads.length === 0) && (
        <Card>
          <CardContent className="p-8 text-center">
            <MessageCircle className="mx-auto h-12 w-12 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground">{t("noThreads")}</p>
            <p className="text-xs text-muted-foreground mt-2 max-w-sm mx-auto">
              {t("noThreadsHint")}
            </p>
          </CardContent>
        </Card>
      )}

      <ul className="space-y-2" data-testid="messages-thread-list">
        {threads?.map((thread) => {
          // The "other party" is whichever id isn't ours.
          const otherId =
            user?.id === thread.teacher_user_id
              ? thread.parent_user_id
              : thread.teacher_user_id;
          return (
            <li key={thread.id}>
              <Link href={`/messages/${thread.id}`}>
                <Card
                  className="hover:bg-muted/30 transition-colors cursor-pointer"
                  data-testid={`messages-thread-${thread.id}`}
                >
                  <CardContent className="flex items-center gap-3 p-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <MessageCircle className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium truncate">
                          {t("threadWithParent", { id: otherId.slice(0, 8) })}
                        </p>
                        {thread.unread_count > 0 && (
                          <span
                            className="rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground"
                            data-testid="thread-unread-badge"
                          >
                            {thread.unread_count}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {thread.last_message_at
                          ? new Date(thread.last_message_at).toLocaleString()
                          : t("noMessagesYet")}
                      </p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </CardContent>
                </Card>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
