/**
 * School profile — single school detail view.
 * Shows the full KPI card and quick metadata. Sourced from the master
 * mock dataset.
 */

"use client";

import React, { use } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getSchoolById,
  getProvinceByCode,
  type MockSchoolNational,
} from "@eduzim/api-client";
import {
  FlagHeader,
  MinistryStatCard,
  OfficialBadge,
  ExportMenu,
} from "@eduzim/ui";
import {
  Users, GraduationCap, ClipboardCheck, DollarSign, ChevronLeft, MapPin, Mail, Phone, Calendar, BookOpen,
} from "lucide-react";

const usd = (n: number) => `$${Math.round(n).toLocaleString()}`;
const pct = (n: number) => `${n.toFixed(1)}%`;

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function SchoolDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const school = getSchoolById(id);
  if (!school) return notFound();
  const province = getProvinceByCode(school.province_code);

  // Single-row export of the full profile for portability
  const profileRow: MockSchoolNational = school;

  return (
    <div className="space-y-6">
      <FlagHeader
        title={school.name}
        subtitle={`${school.code} · ${school.type} · ${province?.name ?? school.province_code}`}
        actions={
          <>
            <Link
              href={`/provinces/${school.province_code}`}
              className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-accent"
            >
              <ChevronLeft className="h-4 w-4" /> {province?.name ?? "Province"}
            </Link>
            <OfficialBadge variant="mopse" label="MoPSE" />
            <ExportMenu
              filename={`school-${school.code.toLowerCase()}-profile`}
              title={`${school.name} — Profile`}
              subtitle={`${school.code} · ${province?.name ?? school.province_code}`}
              columns={[
                { key: "name", label: "School" },
                { key: "code", label: "Code" },
                { key: "type", label: "Type" },
                { key: "province_code", label: "Province" },
                { key: "district_code", label: "District" },
                { key: "address", label: "Address" },
                { key: "phone", label: "Phone" },
                { key: "email", label: "Email" },
                { key: "founded_year", label: "Founded" },
                { key: "principal_name", label: "Principal" },
                { key: "total_students", label: "Students" },
                { key: "boys", label: "Boys" },
                { key: "girls", label: "Girls" },
                { key: "total_teachers", label: "Teachers" },
                { key: "total_classes", label: "Classes" },
                { key: "student_teacher_ratio", label: "S:T ratio" },
                { key: (s: MockSchoolNational) => pct(s.attendance_rate), label: "Attendance" },
                { key: (s: MockSchoolNational) => pct(s.pass_rate), label: "Pass rate" },
                { key: "average_mark", label: "Average mark" },
                { key: (s: MockSchoolNational) => usd(s.billed_usd), label: "Billed" },
                { key: (s: MockSchoolNational) => usd(s.collected_usd), label: "Collected" },
                { key: (s: MockSchoolNational) => usd(s.outstanding_usd), label: "Outstanding" },
                { key: (s: MockSchoolNational) => pct(s.collection_rate), label: "Collection %" },
              ]}
              rows={[profileRow]}
            />
          </>
        }
        stripe="thick"
        className="rounded-lg"
      />

      {/* Profile metadata */}
      <section className="grid gap-4 md:grid-cols-2 rounded-lg border bg-card p-6 shadow-card">
        <div className="space-y-2">
          <h2 className="text-base font-semibold">Profile</h2>
          <div className="flex items-start gap-2 text-sm">
            <BookOpen className="mt-0.5 h-4 w-4 text-muted-foreground" />
            <span>Principal: <span className="font-medium">{school.principal_name}</span></span>
          </div>
          <div className="flex items-start gap-2 text-sm">
            <Calendar className="mt-0.5 h-4 w-4 text-muted-foreground" />
            <span>Founded in {school.founded_year}</span>
          </div>
          <div className="flex items-start gap-2 text-sm">
            <MapPin className="mt-0.5 h-4 w-4 text-muted-foreground" />
            <span>{school.address}</span>
          </div>
        </div>
        <div className="space-y-2">
          <h2 className="text-base font-semibold">Contact</h2>
          <div className="flex items-start gap-2 text-sm">
            <Phone className="mt-0.5 h-4 w-4 text-muted-foreground" />
            <span>{school.phone}</span>
          </div>
          <div className="flex items-start gap-2 text-sm">
            <Mail className="mt-0.5 h-4 w-4 text-muted-foreground" />
            <a href={`mailto:${school.email}`} className="hover:underline">{school.email}</a>
          </div>
        </div>
      </section>

      {/* KPI grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MinistryStatCard
          label="Students"
          value={school.total_students.toLocaleString()}
          icon={Users}
          accent="green"
          source={`${school.boys} boys · ${school.girls} girls`}
        />
        <MinistryStatCard
          label="Teachers"
          value={school.total_teachers.toLocaleString()}
          icon={GraduationCap}
          accent="gold"
          source={`Ratio 1:${school.student_teacher_ratio} · ${school.total_classes} classes`}
        />
        <MinistryStatCard
          label="Attendance"
          value={pct(school.attendance_rate)}
          icon={ClipboardCheck}
          accent={school.attendance_rate >= 85 ? "green" : "red"}
          source="30-day rolling average"
        />
        <MinistryStatCard
          label="Pass rate"
          value={pct(school.pass_rate)}
          icon={GraduationCap}
          accent={school.pass_rate >= 60 ? "green" : "red"}
          source={`Average mark ${school.average_mark}/100`}
        />
        <MinistryStatCard
          label="Billed"
          value={usd(school.billed_usd)}
          icon={DollarSign}
          accent="black"
          source="Current term"
        />
        <MinistryStatCard
          label="Collected"
          value={usd(school.collected_usd)}
          icon={DollarSign}
          accent="green"
          source={`${school.payments_count} payments`}
        />
        <MinistryStatCard
          label="Outstanding"
          value={usd(school.outstanding_usd)}
          icon={DollarSign}
          accent="red"
          source={`Collection ${pct(school.collection_rate)}`}
        />
      </div>

      <p className="text-xs text-muted-foreground">
        Data sourced from the master mock dataset (deterministic).
      </p>
    </div>
  );
}
