/**
 * Child detail page — tabbed view: Overview, Attendance, Fees, Announcements.
 * Parents see real data from attendance-service, fees-service, communication-service.
 */

"use client";

import React, { useMemo, useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Badge,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  StatCard,
} from "@eduzim/ui";
import {
  ArrowLeft,
  User,
  Loader2,
  AlertCircle,
  Calendar,
  Hash,
  Bell,
  CheckCircle,
  XCircle,
  Clock,
  GraduationCap,
} from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { useCachedQuery } from "@/hooks/use-cached-query";
import { useOffline, CacheTTL } from "@/lib/offline-provider";
import { student, attendance, fees, comm, assessment, school } from "@/lib/api";
import type { Student, AttendanceStudentTrend, Invoice, Announcement, StudentSubjectMarks, Term, Subject } from "@eduzim/api-client";

// ───── Date Helpers ─────

function thirtyDaysAgo(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-ZW", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatCurrency(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-ZW", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

// ───── Main Page ─────

export default function ChildDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  // Load children list and find this child
  const { data: children, isLoading, error } = useApiQuery<Student[]>(
    () => student.getMyChildren(),
    []
  );

  const child = children?.find((c) => c.id === id) ?? null;

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={() => router.push("/home")}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to My Children
      </button>

      {isLoading && (
        <div className="flex items-center justify-center p-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error.message}</span>
        </div>
      )}

      {!isLoading && !error && !child && (
        <div className="rounded-lg border bg-muted/30 p-8 text-center text-muted-foreground">
          Child not found. They may not be linked to your account.
        </div>
      )}

      {child && (
        <>
          {/* Header */}
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <User className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">
                {child.first_name} {child.last_name}
              </h1>
              <p className="text-sm text-muted-foreground">
                <span
                  className={
                    child.status === "ACTIVE"
                      ? "text-green-600"
                      : "text-muted-foreground"
                  }
                >
                  {child.status}
                </span>
              </p>
            </div>
          </div>

          {/* Tabs */}
          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="attendance">Attendance</TabsTrigger>
              <TabsTrigger value="fees">Fees</TabsTrigger>
              <TabsTrigger value="performance">Performance</TabsTrigger>
              <TabsTrigger value="announcements">Announcements</TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              <OverviewTab child={child} />
            </TabsContent>

            <TabsContent value="attendance">
              <AttendanceTab studentId={id} />
            </TabsContent>

            <TabsContent value="fees">
              <FeesTab studentId={id} />
            </TabsContent>

            <TabsContent value="performance">
              <PerformanceTab studentId={id} />
            </TabsContent>

            <TabsContent value="announcements">
              <AnnouncementsTab studentId={id} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}

// ───── Overview Tab ─────

function OverviewTab({ child }: { child: Student }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Student Information</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <InfoRow
          icon={<Hash className="h-4 w-4" />}
          label="Admission Number"
          value={child.admission_number ?? child.student_code ?? "—"}
        />
        <InfoRow
          icon={<User className="h-4 w-4" />}
          label="Gender"
          value={child.gender ?? "—"}
        />
        <InfoRow
          icon={<Calendar className="h-4 w-4" />}
          label="Date of Birth"
          value={child.dob ? formatDate(child.dob) : (child.date_of_birth ?? "—")}
        />
      </CardContent>
    </Card>
  );
}

// ───── Attendance Tab ─────

function AttendanceTab({ studentId }: { studentId: string }) {
  const from = useMemo(thirtyDaysAgo, []);
  const to = useMemo(today, []);

  const { data: trend, isLoading, error, fromCache } = useCachedQuery<AttendanceStudentTrend>(
    `attendance:trend:${studentId}`,
    () => attendance.studentTrend({ student_id: studentId, from, to }),
    CacheTTL.LONG,
    [studentId],
  );

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={error.message} />;
  if (!trend) return <EmptyState message="No attendance data available." />;

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Present" value={trend.present} />
        <StatCard label="Absent" value={trend.absent} />
        <StatCard label="Late" value={trend.late} />
        <StatCard
          label="Rate"
          value={`${Math.round(trend.attendance_rate)}%`}
        />
      </div>

      {/* Daily breakdown */}
      {trend.days && trend.days.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Last 30 Days</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trend.days.map((day) => (
                  <TableRow key={day.date}>
                    <TableCell>{formatDate(day.date)}</TableCell>
                    <TableCell>
                      <StatusBadge status={day.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ───── Fees Tab ─────

function FeesTab({ studentId }: { studentId: string }) {
  const { data: invoices, isLoading, error, fromCache } = useCachedQuery<Invoice[]>(
    `fees:invoices:${studentId}`,
    () => fees.listInvoices({ student_id: studentId }),
    CacheTTL.LONG,
    [studentId],
  );

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={error.message} />;
  if (!invoices || invoices.length === 0)
    return <EmptyState message="No fee invoices found." />;

  const totalOwed = invoices.reduce((sum, inv) => sum + (inv.balance ?? 0), 0);
  const totalPaid = invoices.reduce((sum, inv) => sum + (inv.paid_amount ?? 0), 0);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Total Paid" value={formatCurrency(totalPaid)} />
        <StatCard label="Outstanding" value={formatCurrency(totalOwed)} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Invoices</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Due Date</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Paid</TableHead>
                <TableHead>Balance</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell>{formatDate(inv.due_date)}</TableCell>
                  <TableCell>{formatCurrency(inv.total_amount)}</TableCell>
                  <TableCell>{formatCurrency(inv.paid_amount)}</TableCell>
                  <TableCell>{formatCurrency(inv.balance)}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        inv.status === "PAID"
                          ? "default"
                          : inv.status === "OVERDUE"
                            ? "destructive"
                            : "secondary"
                      }
                    >
                      {inv.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

// ───── Announcements Tab ─────

function AnnouncementsTab({ studentId }: { studentId: string }) {
  const { data: announcements, isLoading, error, fromCache } = useCachedQuery<Announcement[]>(
    `announcements:feed:${studentId}`,
    () => comm.getFeed({ student_id: studentId }),
    CacheTTL.MEDIUM,
    [studentId],
  );

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={error.message} />;
  if (!announcements || announcements.length === 0)
    return <EmptyState message="No announcements yet." />;

  return (
    <div className="space-y-3">
      {announcements.map((ann) => (
        <Card key={ann.id}>
          <CardContent className="pt-4">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-3">
                <Bell className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                <div>
                  <h3 className="font-medium text-sm">{ann.title}</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    {ann.body}
                  </p>
                </div>
              </div>
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {formatDate(ann.created_at)}
              </span>
            </div>
            <div className="mt-2 flex gap-1">
              <Badge variant="secondary" className="text-xs">
                {ann.audience_type}
              </Badge>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ───── Performance Tab ─────

function PerformanceTab({ studentId }: { studentId: string }) {
  const [selectedTermId, setSelectedTermId] = useState<string>("");

  const { data: terms } = useApiQuery<Term[]>(
    () => school.listTerms(),
    []
  );

  const { data: subjects } = useApiQuery<Subject[]>(
    () => school.listSubjects(),
    []
  );

  // Auto-select current term
  useEffect(() => {
    if (terms && terms.length > 0 && !selectedTermId) {
      const current = terms.find((tm) => tm.is_current);
      setSelectedTermId(current?.id ?? terms[0].id);
    }
  }, [terms, selectedTermId]);

  const { data: marksData, isLoading, error, fromCache } = useCachedQuery<StudentSubjectMarks[]>(
    `marks:student:${studentId}:${selectedTermId}`,
    () =>
      selectedTermId
        ? assessment.studentMarks(studentId, { term_id: selectedTermId })
        : Promise.resolve({ data: [] as StudentSubjectMarks[] }),
    CacheTTL.LONG,
    [studentId, selectedTermId],
  );

  const subjectMap = useMemo(() => {
    const m = new Map<string, string>();
    subjects?.forEach((s) => m.set(s.id, s.name));
    return m;
  }, [subjects]);

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={error.message} />;

  return (
    <div className="space-y-4">
      {/* Term selector */}
      <div className="flex items-center gap-3">
        <select
          value={selectedTermId}
          onChange={(e) => setSelectedTermId(e.target.value)}
          className="rounded-md border bg-background px-3 py-2 text-sm"
        >
          {terms?.map((tm) => (
            <option key={tm.id} value={tm.id}>
              {tm.name}
            </option>
          ))}
        </select>
      </div>

      {!marksData || marksData.length === 0 ? (
        <div className="rounded-lg border bg-muted/30 p-8 text-center">
          <GraduationCap className="mx-auto h-10 w-10 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">
            No assessment data available.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {marksData.map((subj) => (
            <Card key={subj.subject_id}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    {subjectMap.get(subj.subject_id) ?? subj.subject_id}
                  </CardTitle>
                  {subj.average_pct != null && (
                    <Badge variant={subj.average_pct < 60 ? "destructive" : "default"}>
                      Average: {subj.average_pct.toFixed(1)}%
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Assessment</TableHead>
                      <TableHead className="text-right">Score</TableHead>
                      <TableHead className="text-right">Percentage</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {subj.assessments.map(({ assessment: a, mark }) => (
                      <TableRow key={a.id}>
                        <TableCell>
                          <span className="font-medium">{a.name}</span>
                          <span className="ml-2 text-xs text-muted-foreground">
                            {formatDate(a.date)}
                          </span>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {mark.is_absent
                            ? "Absent"
                            : mark.marks != null
                              ? `${mark.marks} / ${a.max_marks}`
                              : "—"}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {mark.is_absent
                            ? "—"
                            : mark.marks != null
                              ? `${((mark.marks / a.max_marks) * 100).toFixed(1)}%`
                              : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ───── Shared Components ─────

function InfoRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-muted-foreground">{icon}</span>
      <span className="text-muted-foreground w-36">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "P":
      return (
        <Badge variant="default" className="gap-1">
          <CheckCircle className="h-3 w-3" /> Present
        </Badge>
      );
    case "A":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" /> Absent
        </Badge>
      );
    case "L":
      return (
        <Badge variant="secondary" className="gap-1">
          <Clock className="h-3 w-3" /> Late
        </Badge>
      );
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center p-8">
      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
      <AlertCircle className="h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border bg-muted/30 p-8 text-center text-muted-foreground">
      {message}
    </div>
  );
}
