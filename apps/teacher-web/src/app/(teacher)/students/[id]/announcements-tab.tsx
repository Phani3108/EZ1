/**
 * Announcements Tab — Class announcements relevant to this student.
 */

"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@eduzim/ui";
import { Megaphone } from "lucide-react";
import type { Announcement } from "@eduzim/api-client";

interface StudentAnnouncementsTabProps {
  announcements: Announcement[] | null | undefined;
  isLoading: boolean;
}

export function StudentAnnouncementsTab({
  announcements,
  isLoading,
}: StudentAnnouncementsTabProps) {
  const t = useTranslations("students");

  if (isLoading) {
    return (
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
    );
  }

  if (!announcements || announcements.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center">
          <Megaphone className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">
            {t("noAnnouncements")}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
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
                {new Date(a.created_at).toLocaleDateString()}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
