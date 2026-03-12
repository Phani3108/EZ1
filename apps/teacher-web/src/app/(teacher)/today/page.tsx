/**
 * Today Page — Teacher cockpit
 * Shows: My Classes Today cards, Quick Actions, Recent Announcements
 */

"use client";

import React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useAuth } from "@eduzim/auth";
import { Card, CardHeader, CardTitle, CardContent, Button } from "@eduzim/ui";
import { BookOpen, Megaphone, Search, Users, ChevronRight } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { teacher, comm } from "@/lib/api";
import type { TeacherClass, Announcement } from "@eduzim/api-client";

export default function TodayPage() {
  const { user } = useAuth();
  const t = useTranslations("today");

  const { data: classes, isLoading: classesLoading } = useApiQuery<TeacherClass[]>(
    () => teacher.getMyClasses(),
    []
  );

  const { data: announcements, isLoading: announcementsLoading } = useApiQuery<Announcement[]>(
    () => comm.getFeed({ limit: "5" }),
    []
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("welcome", { name: user?.full_name || "" })}
        </h1>
        <p className="text-muted-foreground text-sm">{t("title")}</p>
      </div>

      {/* My Classes Today */}
      <section>
        <h2 className="text-lg font-semibold mb-3">{t("myClassesToday")}</h2>
        {classesLoading ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {[1, 2].map((i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="p-4">
                  <div className="h-5 w-24 bg-muted rounded mb-2" />
                  <div className="h-4 w-16 bg-muted rounded" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : classes && classes.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {classes.map((cls) => (
              <ClassCard key={cls.id} cls={cls} />
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="p-6 text-center">
              <BookOpen className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
              <p className="font-medium text-foreground">{t("noClasses")}</p>
              <p className="text-sm text-muted-foreground mt-1">{t("noClassesHint")}</p>
            </CardContent>
          </Card>
        )}
      </section>

      {/* Quick Actions */}
      <section>
        <h2 className="text-lg font-semibold mb-3">{t("quickActions")}</h2>
        <div className="grid gap-3 grid-cols-2">
          <Link href="/announcements">
            <Card className="cursor-pointer hover:border-primary/40 transition-colors">
              <CardContent className="flex items-center gap-3 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Megaphone className="h-5 w-5 text-primary" />
                </div>
                <span className="text-sm font-medium">{t("sendAnnouncement")}</span>
              </CardContent>
            </Card>
          </Link>
          <Link href="/classes">
            <Card className="cursor-pointer hover:border-primary/40 transition-colors">
              <CardContent className="flex items-center gap-3 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary/10">
                  <Search className="h-5 w-5 text-secondary" />
                </div>
                <span className="text-sm font-medium">{t("searchStudent")}</span>
              </CardContent>
            </Card>
          </Link>
        </div>
      </section>

      {/* Recent Announcements */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">{t("recentAnnouncements")}</h2>
          <Link href="/announcements" className="text-sm text-primary hover:underline">
            {t("viewAll")}
          </Link>
        </div>
        {announcementsLoading ? (
          <Card className="animate-pulse">
            <CardContent className="p-4">
              <div className="h-4 w-48 bg-muted rounded mb-2" />
              <div className="h-3 w-32 bg-muted rounded" />
            </CardContent>
          </Card>
        ) : announcements && announcements.length > 0 ? (
          <div className="space-y-2">
            {announcements.map((a) => (
              <Card key={a.id}>
                <CardContent className="flex items-start gap-3 p-4">
                  <Megaphone className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">{a.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {a.audience_type} &middot; {new Date(a.created_at).toLocaleDateString()}
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
      </section>
    </div>
  );
}

function ClassCard({ cls }: { cls: TeacherClass }) {
  const t = useTranslations("today");

  return (
    <Card className="hover:border-primary/40 transition-colors">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-semibold text-foreground">{cls.name}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Section {cls.section}
            </p>
            {cls.capacity && (
              <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
                <Users className="h-3.5 w-3.5" />
                <span>{t("students", { count: String(cls.capacity) })}</span>
              </div>
            )}
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
            <BookOpen className="h-4 w-4 text-primary" />
          </div>
        </div>
        <div className="mt-3">
          <Link href={`/classes/${cls.id}?tab=attendance&date=${new Date().toISOString().slice(0, 10)}`}>
            <Button variant="outline" size="sm" className="w-full text-xs">
              {t("markAttendance")} &middot; {new Date().toLocaleDateString()}
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
