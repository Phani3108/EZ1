/**
 * Student 360 — single source of truth for a student.
 * Tabs: Overview · Guardians · Enrollment · Attendance · Fees · Communications · Subjects (Phase 2)
 */

"use client";

import React, { useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Card, CardContent, CardHeader, CardTitle,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Badge, Button, Label, Select,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Sheet, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter,
} from "@eduzim/ui";
import { RouteGuard } from "@eduzim/auth";
import type { Student, Parent, Enrollment, Invoice, Announcement, AcademicYear, SchoolClass, StudentSubjectMarks, Term, Subject } from "@eduzim/api-client";
import { student as studentApi, school, fees, attendance, comm, reports, assessment } from "@/lib/api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { ErrorAlert } from "@/components/error-alert";
import { DetailHeader } from "@/components/detail-header";
import { EmptyState } from "@/components/empty-state";
import { RiskBadge } from "@/components/risk-badge";
import { DropoutDrawer } from "@/components/dropout-drawer";
import {
  User, Users, BookOpen, ClipboardCheck, DollarSign, Megaphone,
  GraduationCap, Calendar, Phone, Mail, Plus, AlertCircle,
} from "lucide-react";

export default function StudentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const studentId = params.id;
  const [riskDrawerOpen, setRiskDrawerOpen] = useState(false);

  const { data: student, isLoading, error } = useApiQuery(
    () => studentApi.get(studentId),
    [studentId],
  );

  const { data: riskDetail } = useApiQuery(
    () => reports.dropoutStudentDetail(studentId),
    [studentId],
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded bg-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <DetailHeader backHref="/students" backLabel="Students" title="Student" />
        <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />
      </div>
    );
  }

  if (!student) return null;

  return (
    <RouteGuard permissions={["student:read"]} onUnauthenticated={() => { }}>
      <div className="space-y-6">
        <DetailHeader
          backHref="/students"
          backLabel="Students"
          title={`${student.first_name} ${student.last_name}`}
          subtitle={student.admission_number ? `Admission #${student.admission_number}` : undefined}
          badges={[
            {
              label: student.is_active ? "Active" : "Inactive",
              variant: student.is_active ? "default" : "secondary",
            },
          ]}
        >
          {riskDetail && (
            <RiskBadge
              score={riskDetail.risk_score}
              band={riskDetail.risk_band}
              onClick={() => setRiskDrawerOpen(true)}
            />
          )}
          <Button variant="outline" onClick={() => router.push(`/students`)}>
            Edit
          </Button>
        </DetailHeader>

        <Tabs defaultValue="overview">
          <TabsList className="flex flex-wrap">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="guardians">Guardians</TabsTrigger>
            <TabsTrigger value="enrollment">Enrollment</TabsTrigger>
            <TabsTrigger value="attendance">Attendance</TabsTrigger>
            <TabsTrigger value="fees">Fees</TabsTrigger>
            <TabsTrigger value="communications">Communications</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <OverviewTab student={student} />
          </TabsContent>
          <TabsContent value="guardians">
            <GuardiansTab studentId={studentId} />
          </TabsContent>
          <TabsContent value="enrollment">
            <EnrollmentTab studentId={studentId} />
          </TabsContent>
          <TabsContent value="attendance">
            <AttendanceTab studentId={studentId} />
          </TabsContent>
          <TabsContent value="fees">
            <FeesTab studentId={studentId} />
          </TabsContent>
          <TabsContent value="communications">
            <CommunicationsTab />
          </TabsContent>
          <TabsContent value="performance">
            <PerformanceTab studentId={studentId} />
          </TabsContent>
        </Tabs>

        <DropoutDrawer
          studentId={studentId}
          studentName={student ? `${student.first_name} ${student.last_name}` : ""}
          open={riskDrawerOpen}
          onClose={() => setRiskDrawerOpen(false)}
        />
      </div>
    </RouteGuard>
  );
}

// ─── Overview Tab ───

function OverviewTab({ student }: { student: Student }) {
  const fields = [
    { label: "First Name", value: student.first_name },
    { label: "Last Name", value: student.last_name },
    { label: "Admission #", value: student.admission_number || "—" },
    { label: "Gender", value: student.gender || "—" },
    { label: "Date of Birth", value: student.date_of_birth || "—" },
    { label: "Status", value: student.is_active ? "Active" : "Inactive" },
    { label: "Created", value: new Date(student.created_at).toLocaleDateString() },
    { label: "Updated", value: new Date(student.updated_at).toLocaleDateString() },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <User className="h-5 w-5" /> Student Information
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {fields.map((f) => (
            <div key={f.label}>
              <dt className="text-sm font-medium text-muted-foreground">{f.label}</dt>
              <dd className="mt-1 text-sm capitalize">{f.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

// ─── Guardians Tab ───

function GuardiansTab({ studentId }: { studentId: string }) {
  const { data: parents, isLoading, error } = useApiQuery(
    () => studentApi.getStudentParents(studentId),
    [studentId],
  );

  if (isLoading) return <div className="h-32 animate-pulse rounded bg-muted" />;
  if (error) return <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />;

  if (!parents || parents.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="No guardians linked"
        description="Link a parent or guardian to this student from the Parents directory."
      />
    );
  }

  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Relationship</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {parents.map((p) => (
            <TableRow key={p.id}>
              <TableCell className="font-medium">
                <a href={`/parents/${p.id}`} className="text-primary hover:underline">
                  {p.first_name} {p.last_name}
                </a>
              </TableCell>
              <TableCell>
                <span className="inline-flex items-center gap-1"><Phone className="h-3 w-3" />{p.phone}</span>
              </TableCell>
              <TableCell>
                {p.email ? (
                  <span className="inline-flex items-center gap-1"><Mail className="h-3 w-3" />{p.email}</span>
                ) : "—"}
              </TableCell>
              <TableCell className="capitalize">{p.relationship || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// ─── Enrollment Tab ───

const enrollSchema = z.object({
  academic_year_id: z.string().min(1, "Academic year is required"),
  class_id: z.string().min(1, "Class is required"),
});

type EnrollFormData = z.infer<typeof enrollSchema>;

function EnrollmentTab({ studentId }: { studentId: string }) {
  const t = useTranslations("enrollment");
  const [sheetOpen, setSheetOpen] = useState(false);

  const { data: enrollments, isLoading, error, refetch } = useApiQuery(
    () => studentApi.getStudentEnrollments(studentId),
    [studentId],
  );

  // Fetch academic years and classes for name resolution & enroll form
  const { data: years } = useApiQuery(() => school.listAcademicYears(), []);
  const { data: classes } = useApiQuery(() => school.listClasses(), []);

  const yearMap = React.useMemo(() => {
    const m = new Map<string, string>();
    years?.forEach((y: AcademicYear) => m.set(y.id, y.name));
    return m;
  }, [years]);

  const classMap = React.useMemo(() => {
    const m = new Map<string, string>();
    classes?.forEach((c: SchoolClass) => m.set(c.id, c.name));
    return m;
  }, [classes]);

  // Find current year: is_current=true first, then latest by start_date
  const currentYear = React.useMemo(() => {
    if (!years || years.length === 0) return undefined;
    const current = years.find((y: AcademicYear) => y.is_current);
    if (current) return current;
    return [...years].sort(
      (a: AcademicYear, b: AcademicYear) =>
        new Date(b.start_date).getTime() - new Date(a.start_date).getTime()
    )[0];
  }, [years]);

  const handleSaved = useCallback(() => {
    setSheetOpen(false);
    refetch();
  }, [refetch]);

  if (isLoading) return <div className="h-32 animate-pulse rounded bg-muted" />;
  if (error) return <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">{t("title")}</h3>
        <Button onClick={() => setSheetOpen(true)} size="sm">
          <Plus className="mr-2 h-4 w-4" />
          {t("enrollStudent")}
        </Button>
      </div>

      {!enrollments || enrollments.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title={t("noEnrollments")}
          description={t("noEnrollmentsDescription")}
        />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("class")}</TableHead>
                <TableHead>{t("academicYear")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead>{t("enrolledAt")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {enrollments.map((e: Enrollment) => (
                <TableRow key={e.id}>
                  <TableCell className="font-medium">
                    <a
                      href={`/classes/${e.class_id}`}
                      className="text-primary hover:underline"
                    >
                      {classMap.get(e.class_id) || e.class_id}
                    </a>
                  </TableCell>
                  <TableCell>{yearMap.get(e.academic_year_id) || e.academic_year_id}</TableCell>
                  <TableCell>
                    <Badge variant={e.status === "active" ? "default" : "secondary"}>
                      {e.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{new Date(e.enrolled_at).toLocaleDateString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <EnrollSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        studentId={studentId}
        years={years || []}
        classes={classes || []}
        defaultYearId={currentYear?.id}
        onSaved={handleSaved}
      />
    </div>
  );
}

// ─── Enroll Sheet ───

function EnrollSheet({
  open,
  onClose,
  studentId,
  years,
  classes,
  defaultYearId,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  studentId: string;
  years: AcademicYear[];
  classes: SchoolClass[];
  defaultYearId?: string;
  onSaved: () => void;
}) {
  const t = useTranslations("enrollment");

  const { register, handleSubmit, formState: { errors }, reset } = useForm<EnrollFormData>({
    resolver: zodResolver(enrollSchema),
    defaultValues: {
      academic_year_id: defaultYearId || "",
      class_id: "",
    },
  });

  React.useEffect(() => {
    if (open) {
      reset({
        academic_year_id: defaultYearId || "",
        class_id: "",
      });
    }
  }, [open, defaultYearId, reset]);

  const mutation = useApiMutation(
    (data: EnrollFormData) =>
      studentApi.createEnrollment({
        student_id: studentId,
        academic_year_id: data.academic_year_id,
        class_id: data.class_id,
      }),
    { onSuccess: onSaved }
  );

  const onSubmit = handleSubmit((data) => {
    mutation.mutate(data);
  });

  const yearOptions = years.map((y) => ({ value: y.id, label: y.name }));
  const classOptions = classes.map((c) => ({ value: c.id, label: `${c.name} (Grade ${c.grade_level})` }));

  return (
    <Sheet open={open} onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col h-full">
        <SheetHeader>
          <SheetTitle>{t("enrollStudent")}</SheetTitle>
          <SheetDescription>{t("enrollStudentDescription")}</SheetDescription>
        </SheetHeader>

        <SheetBody className="space-y-4">
          {mutation.error && (
            <ErrorAlert
              message={mutation.error.message}
              requestId={mutation.error.requestId}
              details={mutation.error.details}
              onDismiss={mutation.clearError}
            />
          )}

          <div className="space-y-2">
            <Label htmlFor="academic_year_id" required>{t("academicYear")}</Label>
            <Select
              id="academic_year_id"
              options={yearOptions}
              placeholder={t("selectYear")}
              error={errors.academic_year_id?.message}
              {...register("academic_year_id")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="class_id" required>{t("class")}</Label>
            <Select
              id="class_id"
              options={classOptions}
              placeholder={t("selectClass")}
              error={errors.class_id?.message}
              {...register("class_id")}
            />
          </div>
        </SheetBody>

        <SheetFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={mutation.isSubmitting}>
            {mutation.isSubmitting ? t("enrolling") : t("enrollStudent")}
          </Button>
        </SheetFooter>
      </form>
    </Sheet>
  );
}

// ─── Attendance Tab ───

type DateRange = "30" | "90" | "custom";

function AttendanceTab({ studentId }: { studentId: string }) {
  const t = useTranslations("attendance");
  const [range, setRange] = useState<DateRange>("30");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const { from, to } = React.useMemo(() => {
    if (range === "custom" && customFrom && customTo) {
      return { from: customFrom, to: customTo };
    }
    const now = new Date();
    const toDate = now.toISOString().split("T")[0];
    const days = range === "90" ? 90 : 30;
    const fromDate = new Date(now.getTime() - days * 86400000).toISOString().split("T")[0];
    return { from: fromDate, to: toDate };
  }, [range, customFrom, customTo]);

  const { data: trend, isLoading, error } = useApiQuery(
    () => attendance.studentTrend({ student_id: studentId, from, to }),
    [studentId, from, to],
  );

  if (isLoading) return <div className="h-32 animate-pulse rounded bg-muted" />;
  if (error) return <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />;

  const statusBadge = (status: string) => {
    switch (status) {
      case "P": return "default" as const;
      case "L": return "secondary" as const;
      case "A": return "destructive" as const;
      default: return "secondary" as const;
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case "P": return t("present");
      case "A": return t("absent");
      case "L": return t("late");
      default: return status;
    }
  };

  return (
    <div className="space-y-4">
      {/* Date range selector */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-48">
          <Select
            options={[
              { value: "30", label: t("last30Days") },
              { value: "90", label: t("last90Days") },
              { value: "custom", label: t("custom") },
            ]}
            value={range}
            onChange={(e) => setRange(e.target.value as DateRange)}
          />
        </div>
        {range === "custom" && (
          <>
            <input
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="rounded-md border bg-background px-3 py-2 text-sm"
            />
            <span className="text-muted-foreground">→</span>
            <input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              className="rounded-md border bg-background px-3 py-2 text-sm"
            />
          </>
        )}
      </div>

      {/* Summary card */}
      {trend && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ClipboardCheck className="h-5 w-5" /> {t("trend")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
              <div>
                <p className="text-sm text-muted-foreground">{t("trendRate")}</p>
                <p className="text-2xl font-bold">{trend.attendance_rate}%</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("totalDays")}</p>
                <p className="text-2xl font-bold">{trend.total_days}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("present")}</p>
                <p className="text-2xl font-bold text-emerald-600">{trend.present}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("absent")}</p>
                <p className="text-2xl font-bold text-red-600">{trend.absent}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{t("late")}</p>
                <p className="text-2xl font-bold text-amber-600">{trend.late}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Day-by-day table */}
      {!trend || !trend.days || trend.days.length === 0 ? (
        <EmptyState
          icon={ClipboardCheck}
          title={t("noRecords")}
          description={t("noRecordsDescription")}
        />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("date")}</TableHead>
                <TableHead>{t("status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trend.days.map((day) => (
                <TableRow key={day.date}>
                  <TableCell>{day.date}</TableCell>
                  <TableCell>
                    <Badge variant={statusBadge(day.status)}>
                      {statusLabel(day.status)}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

// ─── Fees Tab ───

function FeesTab({ studentId }: { studentId: string }) {
  const t = useTranslations("fees");
  const [payingInvoice, setPayingInvoice] = useState<Invoice | null>(null);
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("CASH");
  const [payRef, setPayRef] = useState("");

  const { data: invoices, isLoading, error, refetch } = useApiQuery(
    () => fees.listInvoices({ student_id: studentId }),
    [studentId],
  );

  const { mutate: recordPay, isSubmitting: payPending, error: payError } = useApiMutation(
    (data: Record<string, unknown>) => fees.recordPayment(data),
    {
      onSuccess: () => {
        setPayingInvoice(null);
        setPayAmount("");
        setPayMethod("CASH");
        setPayRef("");
        refetch();
      },
    },
  );

  const handlePay = (e: React.FormEvent) => {
    e.preventDefault();
    if (!payingInvoice || !payAmount) return;
    recordPay({
      invoice_id: payingInvoice.id,
      amount: parseFloat(payAmount),
      method: payMethod,
      reference: payRef || undefined,
    });
  };

  if (isLoading) return <div className="h-32 animate-pulse rounded bg-muted" />;
  if (error) return <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />;

  if (!invoices || invoices.length === 0) {
    return (
      <EmptyState
        icon={DollarSign}
        title={t("noInvoices")}
        description={t("noInvoicesDescription")}
      />
    );
  }

  const statusVariant = (status: string) => {
    switch (status) {
      case "PAID": return "default" as const;
      case "PARTIAL": return "secondary" as const;
      case "OVERDUE": return "destructive" as const;
      default: return "outline" as const;
    }
  };

  return (
    <div className="space-y-4">
      {/* Invoices table */}
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Invoice</TableHead>
              <TableHead className="text-right">{t("amount")}</TableHead>
              <TableHead className="text-right">{t("paid")}</TableHead>
              <TableHead className="text-right">{t("balance")}</TableHead>
              <TableHead>{t("status")}</TableHead>
              <TableHead>{t("dueDate")}</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invoices.map((inv: Invoice) => (
              <TableRow key={inv.id}>
                <TableCell className="font-mono text-xs">{inv.id.slice(0, 8)}</TableCell>
                <TableCell className="text-right font-mono">${inv.total_amount.toFixed(2)}</TableCell>
                <TableCell className="text-right font-mono">${inv.paid_amount.toFixed(2)}</TableCell>
                <TableCell className="text-right font-mono font-medium">
                  ${inv.balance.toFixed(2)}
                </TableCell>
                <TableCell>
                  <Badge variant={statusVariant(inv.status)}>{inv.status}</Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{inv.due_date}</TableCell>
                <TableCell>
                  {inv.status !== "PAID" && (
                    <Button size="sm" variant="outline" onClick={() => setPayingInvoice(inv)}>
                      {t("recordPayment")}
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Record Payment Sheet */}
      <Sheet
        open={!!payingInvoice}
        onClose={() => setPayingInvoice(null)}
        width="max-w-md"
      >
        <SheetHeader>
          <SheetTitle>{t("recordPayment")}</SheetTitle>
          <SheetDescription>{t("recordPaymentDescription")}</SheetDescription>
        </SheetHeader>
        <SheetBody>
          {payingInvoice && (
            <form onSubmit={handlePay} className="space-y-4">
              {/* Balance context */}
              <div className="rounded-md border bg-muted/30 px-4 py-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">{t("balance")}</span>
                  <span className="font-mono font-medium">${payingInvoice.balance.toFixed(2)}</span>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium">{t("paymentAmount")}</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={payingInvoice.balance}
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  placeholder="0.00"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium">{t("paymentMethod")}</label>
                <Select
                  options={[
                    { value: "CASH", label: t("methodCash") },
                    { value: "MOBILE", label: t("methodMobile") },
                    { value: "BANK", label: t("methodBank") },
                  ]}
                  value={payMethod}
                  onChange={(e) => setPayMethod(e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium">{t("reference")}</label>
                <input
                  type="text"
                  value={payRef}
                  onChange={(e) => setPayRef(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  placeholder={t("referencePlaceholder")}
                />
              </div>

              {payError && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {payError.message}
                </div>
              )}

              <Button
                type="submit"
                className="w-full"
                disabled={!payAmount || parseFloat(payAmount) <= 0 || payPending}
              >
                {payPending ? t("recording") : t("recordPayment")}
              </Button>
            </form>
          )}
        </SheetBody>
      </Sheet>
    </div>
  );
}

// ─── Performance Tab ───

function PerformanceTab({ studentId }: { studentId: string }) {
  const t = useTranslations("performance");
  const [selectedTermId, setSelectedTermId] = useState<string>("");

  const { data: terms } = useApiQuery(() => school.listTerms(), []);
  const { data: subjects } = useApiQuery(() => school.listSubjects(), []);

  // Auto-select current term
  React.useEffect(() => {
    if (terms && terms.length > 0 && !selectedTermId) {
      const current = (terms as Term[]).find((tm) => tm.is_current);
      setSelectedTermId(current?.id ?? terms[0].id);
    }
  }, [terms, selectedTermId]);

  const { data: marksData, isLoading, error } = useApiQuery<StudentSubjectMarks[]>(
    () =>
      selectedTermId
        ? assessment.studentMarks(studentId, { term_id: selectedTermId })
        : Promise.resolve({ data: [] as StudentSubjectMarks[] }),
    [studentId, selectedTermId],
  );

  const subjectMap = React.useMemo(() => {
    const m = new Map<string, string>();
    (subjects as Subject[] | null)?.forEach((s) => m.set(s.id, s.name));
    return m;
  }, [subjects]);

  // Global average across all subjects
  const globalAvg = React.useMemo(() => {
    if (!marksData || marksData.length === 0) return null;
    const withAvg = marksData.filter((s) => s.average_pct != null);
    if (withAvg.length === 0) return null;
    return withAvg.reduce((sum, s) => sum + (s.average_pct ?? 0), 0) / withAvg.length;
  }, [marksData]);

  if (isLoading) return <div className="h-32 animate-pulse rounded bg-muted" />;
  if (error) return <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />;

  return (
    <div className="space-y-4">
      {/* Term selector + risk badge */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-48">
          <Select
            value={selectedTermId}
            onChange={(e) => setSelectedTermId(e.target.value)}
          >
            {(terms as Term[] | null)?.map((tm) => (
              <option key={tm.id} value={tm.id}>
                {tm.name}
              </option>
            ))}
          </Select>
        </div>
        {globalAvg != null && globalAvg < 60 && (
          <Badge variant="destructive" className="flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            {t("atRisk")}
          </Badge>
        )}
        {globalAvg != null && (
          <span className="text-sm text-muted-foreground">
            {t("average")}: {globalAvg.toFixed(1)}%
          </span>
        )}
      </div>

      {/* Per-subject breakdown */}
      {!marksData || marksData.length === 0 ? (
        <EmptyState
          icon={GraduationCap}
          title={t("noData")}
          description=""
        />
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
                      {t("average")}: {subj.average_pct.toFixed(1)}%
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("assessment")}</TableHead>
                        <TableHead className="text-right">{t("score")}</TableHead>
                        <TableHead className="text-right">{t("percentage")}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {subj.assessments.map(({ assessment: a, mark }) => (
                        <TableRow key={a.id}>
                          <TableCell>
                            <div>
                              <span className="font-medium">{a.name}</span>
                              <span className="ml-2 text-xs text-muted-foreground">
                                {new Date(a.date).toLocaleDateString()}
                              </span>
                            </div>
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
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Communications Tab ───

function CommunicationsTab() {
  const t = useTranslations("comm");

  const { data: announcements, isLoading, error } = useApiQuery(
    () => comm.listAnnouncements(),
    [],
  );

  if (isLoading) return <div className="h-32 animate-pulse rounded bg-muted" />;
  if (error) return <ErrorAlert message={error.message} requestId={error.requestId} details={error.details} />;

  if (!announcements || announcements.length === 0) {
    return (
      <EmptyState
        icon={Megaphone}
        title={t("schoolAnnouncements")}
        description={t("noCommsDescription")}
      />
    );
  }

  return (
    <div className="space-y-3">
      {announcements.map((ann: Announcement) => (
        <div key={ann.id} className="rounded-lg border p-4">
          <div className="flex items-start justify-between">
            <div>
              <h4 className="font-medium">{ann.title}</h4>
              <p className="mt-1 text-sm text-muted-foreground">{ann.body}</p>
            </div>
            <Badge variant={ann.audience_type === "ALL" ? "default" : "secondary"}>
              {ann.audience_type}
            </Badge>
          </div>
          <div className="mt-2 text-xs text-muted-foreground">
            {new Date(ann.created_at).toLocaleDateString()}
          </div>
        </div>
      ))}
    </div>
  );
}
