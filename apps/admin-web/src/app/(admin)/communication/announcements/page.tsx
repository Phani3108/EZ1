/**
 * Announcements — list + create sheet with ALL/CLASS/ROLE audience.
 * UX: Institutional tone, no playful elements.
 * Permission: comm:read (list), comm:write (create)
 */

"use client";

import React, { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  Button, Badge, Select,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { Announcement, SchoolClass } from "@eduzim/api-client";
import { comm, school } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Megaphone, Plus } from "lucide-react";

function audienceBadge(type: string) {
  switch (type) {
    case "ALL": return "default" as const;
    case "CLASS": return "secondary" as const;
    case "ROLE": return "outline" as const;
    default: return "outline" as const;
  }
}

export default function AnnouncementsPage() {
  const t = useTranslations("comm");
  const [sheetOpen, setSheetOpen] = useState(false);

  // Form state
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [audienceType, setAudienceType] = useState("ALL");
  const [classId, setClassId] = useState("");
  const [role, setRole] = useState("");
  const [channelInApp, setChannelInApp] = useState(true);
  const [channelSMS, setChannelSMS] = useState(false);

  // Data
  const { data: announcements, isLoading, error, refetch } = useApiQuery(
    () => comm.listAnnouncements(),
    [],
  );
  const { data: classes } = useApiQuery(() => school.listClasses(), []);

  const classOptions = useMemo(() => {
    if (!classes) return [];
    return classes.map((c: SchoolClass) => ({
      value: c.id,
      label: c.name,
    }));
  }, [classes]);

  const roleOptions = [
    { value: "principal", label: t("rolePrincipal") },
    { value: "teacher", label: t("roleTeacher") },
    { value: "parent", label: t("roleParent") },
  ];

  const { mutate: createAnn, isSubmitting, error: createError } = useApiMutation(
    (data: Record<string, unknown>) => comm.createAnnouncement(data),
    {
      onSuccess: () => {
        setSheetOpen(false);
        setTitle("");
        setBody("");
        setAudienceType("ALL");
        setClassId("");
        setRole("");
        setChannelInApp(true);
        setChannelSMS(false);
        refetch();
      },
    },
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !body) return;

    const channels: string[] = [];
    if (channelInApp) channels.push("IN_APP");
    if (channelSMS) channels.push("SMS");
    if (channels.length === 0) return;

    const audience: Record<string, unknown> = { type: audienceType };
    if (audienceType === "CLASS" && classId) audience.class_id = classId;
    if (audienceType === "ROLE" && role) audience.role = role;

    createAnn({ title, body, audience, channels });
  };

  const canSubmit =
    title &&
    body &&
    (channelInApp || channelSMS) &&
    (audienceType === "ALL" || (audienceType === "CLASS" && classId) || (audienceType === "ROLE" && role));

  return (
    <RouteGuard permissions={["comm:read"]} onUnauthenticated={() => { }}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <PageHeader title={t("announcements")} />
          <Button size="sm" onClick={() => setSheetOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            {t("createAnnouncement")}
          </Button>
        </div>

        {/* Create sheet */}
        <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} width="max-w-lg">
          <SheetHeader>
            <SheetTitle>{t("createAnnouncement")}</SheetTitle>
            <SheetDescription>{t("createAnnouncementDescription")}</SheetDescription>
          </SheetHeader>
          <SheetBody>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Title */}
              <div className="space-y-1">
                <label className="text-sm font-medium">{t("announcementTitle")}</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  placeholder={t("titlePlaceholder")}
                  maxLength={500}
                  required
                />
              </div>

              {/* Body */}
              <div className="space-y-1">
                <label className="text-sm font-medium">{t("announcementBody")}</label>
                <textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-[100px] resize-y"
                  placeholder={t("bodyPlaceholder")}
                  required
                />
                {channelSMS && body.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {body.length}/160 characters (SMS)
                  </p>
                )}
              </div>

              {/* Audience */}
              <div className="space-y-1">
                <label className="text-sm font-medium">{t("audienceType")}</label>
                <Select
                  options={[
                    { value: "ALL", label: t("audienceAll") },
                    { value: "CLASS", label: t("audienceClass") },
                    { value: "ROLE", label: t("audienceRole") },
                  ]}
                  value={audienceType}
                  onChange={(e) => {
                    setAudienceType(e.target.value);
                    setClassId("");
                    setRole("");
                  }}
                />
              </div>

              {/* Conditional: Class selector */}
              {audienceType === "CLASS" && (
                <div className="space-y-1">
                  <label className="text-sm font-medium">{t("audienceClass")}</label>
                  <Select
                    options={classOptions}
                    placeholder={t("selectClass")}
                    value={classId}
                    onChange={(e) => setClassId(e.target.value)}
                  />
                </div>
              )}

              {/* Conditional: Role selector */}
              {audienceType === "ROLE" && (
                <div className="space-y-1">
                  <label className="text-sm font-medium">{t("audienceRole")}</label>
                  <Select
                    options={roleOptions}
                    placeholder={t("selectRole")}
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  />
                </div>
              )}

              {/* Channels */}
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("channels")}</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={channelInApp}
                      onChange={(e) => setChannelInApp(e.target.checked)}
                      className="rounded border"
                    />
                    {t("channelInApp")}
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={channelSMS}
                      onChange={(e) => setChannelSMS(e.target.checked)}
                      className="rounded border"
                    />
                    {t("channelSMS")}
                  </label>
                </div>
              </div>

              {createError && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {createError.message}
                </div>
              )}

              <Button type="submit" className="w-full" disabled={!canSubmit || isSubmitting}>
                {isSubmitting ? t("creating") : t("createAnnouncement")}
              </Button>
            </form>
          </SheetBody>
        </Sheet>

        {error && <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />}

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-muted" />)}
          </div>
        ) : !announcements || announcements.length === 0 ? (
          <EmptyState
            icon={Megaphone}
            title={t("noAnnouncements")}
            description={t("noAnnouncementsDescription")}
          />
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("announcementTitle")}</TableHead>
                  <TableHead>{t("audienceLabel")}</TableHead>
                  <TableHead>{t("channels")}</TableHead>
                  <TableHead>{t("createdBy")}</TableHead>
                  <TableHead>{t("createdAt")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {announcements.map((ann: Announcement) => (
                  <TableRow key={ann.id}>
                    <TableCell>
                      <div>
                        <div className="font-medium">{ann.title}</div>
                        <div className="text-xs text-muted-foreground line-clamp-1">{ann.body}</div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={audienceBadge(ann.audience_type)}>
                        {ann.audience_type}
                      </Badge>
                      {ann.audience_class_id && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          {ann.audience_class_id.slice(0, 8)}
                        </span>
                      )}
                      {ann.audience_role && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          {ann.audience_role}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Badge variant="outline">IN_APP</Badge>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {ann.created_by.slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(ann.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </RouteGuard>
  );
}
