/**
 * My Classes page — 10B-1C1.
 * Search/filter, click to navigate to class detail.
 */

"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Card, CardContent, Button, Input } from "@eduzim/ui";
import { BookOpen, Users, Search, ChevronRight } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { teacher } from "@/lib/api";
import type { TeacherClass } from "@eduzim/api-client";

export default function ClassesPage() {
  const t = useTranslations("classes");
  const tCommon = useTranslations("common");
  const [search, setSearch] = useState("");

  const { data: classes, isLoading } = useApiQuery<TeacherClass[]>(
    () => teacher.getMyClasses(),
    []
  );

  const filtered = useMemo(() => {
    if (!classes) return [];
    if (!search.trim()) return classes;
    const q = search.toLowerCase();
    return classes.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.section.toLowerCase().includes(q)
    );
  }, [classes, search]);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        {classes && classes.length > 0 && (
          <span className="text-sm text-muted-foreground">
            {classes.length} {classes.length === 1 ? "class" : "classes"}
          </span>
        )}
      </div>

      {/* Search */}
      {classes && classes.length > 2 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder={tCommon("search")}
            value={search}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-4">
                <div className="h-5 w-24 bg-muted rounded mb-2" />
                <div className="h-4 w-16 bg-muted rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {filtered.map((cls) => (
            <Link key={cls.id} href={`/classes/${cls.id}`}>
              <Card className="cursor-pointer hover:border-primary/40 transition-colors h-full">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        <BookOpen className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <h3 className="font-semibold">{cls.name}</h3>
                        <p className="text-xs text-muted-foreground">
                          {t("section", { section: cls.section })}
                          {cls.capacity ? ` · ${t("capacity", { count: String(cls.capacity) })}` : ""}
                        </p>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-muted-foreground shrink-0 mt-1" />
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Link
                      href={`/classes/${cls.id}?tab=attendance&date=${new Date().toISOString().slice(0, 10)}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button variant="outline" size="sm" className="text-xs">
                        {t("markAttendance")}
                      </Button>
                    </Link>
                    <Link
                      href={`/classes/${cls.id}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button variant="ghost" size="sm" className="text-xs">
                        {t("viewClass")}
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      ) : search ? (
        <Card>
          <CardContent className="p-6 text-center text-sm text-muted-foreground">
            {tCommon("noResults")}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-6 text-center text-sm text-muted-foreground">
            {t("noClasses")}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
