/**
 * Events calendar — Phase 12d / P-010.
 *
 * Read-only feed of school events that the school admin published
 * with `visible_to_parents=true`. Hidden ones never reach the parent.
 */

"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@eduzim/ui";
import { CalendarRange, GraduationCap, Trophy, PartyPopper, Users } from "lucide-react";
import { fetchJson } from "@/lib/api-helpers";


interface Event {
  id: string;
  title: string;
  description: string | null;
  start_at: string | null;
  end_at: string | null;
  kind: string;
  visible_to_parents: boolean;
}


function kindIcon(kind: string) {
  switch (kind) {
    case "exam": return GraduationCap;
    case "sports": return Trophy;
    case "holiday": return PartyPopper;
    case "meeting": return Users;
    default: return CalendarRange;
  }
}


export default function EventsPage() {
  const t = useTranslations("parentEvents");
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetchJson<Event[]>("/api/v1/school-events");
        setEvents(r.data);
      } catch {
        setEvents([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <CalendarRange className="h-5 w-5" />
          {t("title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">{t("loading")}</p>
      ) : events.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            {t("empty")}
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-2">
          {events.map((e) => {
            const Icon = kindIcon(e.kind);
            return (
              <li key={e.id}>
                <Card>
                  <CardContent className="flex items-start gap-3 p-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{e.title}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {e.start_at && new Date(e.start_at).toLocaleString()}
                        {e.end_at && ` — ${new Date(e.end_at).toLocaleString()}`}
                      </p>
                      {e.description && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {e.description}
                        </p>
                      )}
                      <span className="inline-block text-xs rounded-full bg-muted px-2 py-0.5 mt-2">
                        {e.kind}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
