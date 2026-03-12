/**
 * Parent Announcements — school news and notices feed.
 */

"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@eduzim/ui";
import { Megaphone, Loader2, AlertCircle, BookOpen } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { comm } from "@/lib/api";
import type { Announcement } from "@eduzim/api-client";

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  if (days < 30) return `${Math.floor(days / 7)} week${Math.floor(days / 7) > 1 ? "s" : ""} ago`;
  return new Date(dateStr).toLocaleDateString("en-ZW", { day: "numeric", month: "short", year: "numeric" });
}

const AUDIENCE_MAP: Record<string, string> = {
  ALL: "All school",
  CLASS: "Class notice",
  ROLE: "Role-specific",
};

export default function ParentAnnouncementsPage() {
  const { data: announcements, isLoading, error } = useApiQuery<Announcement[]>(
    () => comm.getFeed({}),
    [],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Megaphone className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">Announcements</h1>
          <p className="text-sm text-muted-foreground">School notices and updates</p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error.message}</span>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center p-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {!isLoading && !error && announcements?.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <BookOpen className="h-10 w-10 text-muted-foreground/40" />
            <p className="font-medium text-muted-foreground">No announcements yet</p>
            <p className="text-sm text-muted-foreground">School notices will appear here.</p>
          </CardContent>
        </Card>
      )}

      {!isLoading && announcements && announcements.length > 0 && (
        <div className="space-y-3">
          {announcements.map((ann: Announcement) => (
            <Card key={ann.id} className="overflow-hidden">
              <div className="h-1 w-full bg-primary/20" />
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <h3 className="font-semibold text-base">{ann.title}</h3>
                  <span className="shrink-0 inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    {AUDIENCE_MAP[ann.audience_type] ?? ann.audience_type}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">{ann.body}</p>
                <p className="mt-3 text-xs text-muted-foreground/60">{timeAgo(ann.created_at)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

