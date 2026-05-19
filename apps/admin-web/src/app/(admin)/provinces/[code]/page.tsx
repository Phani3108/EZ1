/**
 * Province detail page — drills into a single province.
 * Shows: KPI band · districts table · schools table.
 *
 * Permission: authenticated (or guest). Data sourced from the master
 * mock dataset bundled into @eduzim/api-client.
 */

"use client";

import React, { use, useMemo, useState } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getProvinceByCode,
  getProvinceBreakdown,
  getDistrictsByProvince,
  getSchoolsByProvince,
  type MockSchoolNational,
} from "@eduzim/api-client";
import {
  FlagHeader,
  MinistryStatCard,
  OfficialBadge,
  ExportMenu,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Badge,
} from "@eduzim/ui";
import {
  Users, School, ClipboardCheck, DollarSign, ChevronLeft,
} from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";

const usd = (n: number) => `$${Math.round(n).toLocaleString()}`;
const pct = (n: number) => `${n.toFixed(1)}%`;

interface PageProps {
  params: Promise<{ code: string }>;
}

export default function ProvinceDetailPage({ params }: PageProps) {
  const { code } = use(params);
  const province = getProvinceByCode(code);
  const breakdown = getProvinceBreakdown(code);
  if (!province || !breakdown) return notFound();

  const districts = getDistrictsByProvince(code);
  const schools = getSchoolsByProvince(code);

  const [schoolSearch, setSchoolSearch] = useState("");
  const filteredSchools = useMemo<MockSchoolNational[]>(() => {
    if (!schoolSearch) return schools;
    const q = schoolSearch.toLowerCase();
    return schools.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.code.toLowerCase().includes(q) ||
        s.district_code.toLowerCase().includes(q),
    );
  }, [schools, schoolSearch]);

  const schoolsPerDistrict = useMemo(() => {
    const map = new Map<string, MockSchoolNational[]>();
    for (const s of schools) {
      if (!map.has(s.district_code)) map.set(s.district_code, []);
      map.get(s.district_code)!.push(s);
    }
    return map;
  }, [schools]);

  return (
    <div className="space-y-6">
      <FlagHeader
        title={breakdown.province_name}
        subtitle={`${breakdown.region} · Capital: ${breakdown.capital} · ${breakdown.schools_count} schools · ${districts.length} districts`}
        actions={
          <>
            <Link
              href="/provinces"
              className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-accent"
            >
              <ChevronLeft className="h-4 w-4" /> Provinces
            </Link>
            <OfficialBadge variant="mopse" label="MoPSE" />
          </>
        }
        stripe="thick"
        className="rounded-lg"
      />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MinistryStatCard
          label="Students"
          value={breakdown.total_students.toLocaleString()}
          icon={Users}
          accent="green"
          source={`${breakdown.boys.toLocaleString()} boys · ${breakdown.girls.toLocaleString()} girls`}
        />
        <MinistryStatCard
          label="Schools"
          value={breakdown.schools_count.toLocaleString()}
          icon={School}
          accent="gold"
          source={`${breakdown.total_teachers.toLocaleString()} teachers (1:${breakdown.student_teacher_ratio})`}
        />
        <MinistryStatCard
          label="Attendance"
          value={pct(breakdown.average_attendance_rate)}
          icon={ClipboardCheck}
          accent="green"
          source="Weighted by enrollment"
        />
        <MinistryStatCard
          label="Fee Collection"
          value={pct(breakdown.collection_rate)}
          icon={DollarSign}
          accent={breakdown.collection_rate >= 70 ? "green" : "red"}
          source={`${usd(breakdown.collected_usd)} of ${usd(breakdown.billed_usd)}`}
        />
      </div>

      {/* Districts */}
      <section className="space-y-3">
        <PageHeader
          title="Districts"
          description={`${districts.length} districts in ${breakdown.province_name}`}
        >
          <ExportMenu
            filename={`districts-${province.code.toLowerCase()}`}
            title={`Districts — ${breakdown.province_name}`}
            columns={[
              { key: "code", label: "Code" },
              { key: "name", label: "District" },
              { key: (d) => schoolsPerDistrict.get(d.code)?.length ?? 0, label: "Schools" },
              { key: (d) => (schoolsPerDistrict.get(d.code) ?? []).reduce((acc, s) => acc + s.total_students, 0), label: "Students" },
            ]}
            rows={districts}
          />
        </PageHeader>
        <div className="rounded-lg border bg-card shadow-card overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>District</TableHead>
                <TableHead>Code</TableHead>
                <TableHead className="text-right">Schools</TableHead>
                <TableHead className="text-right">Students</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {districts.map((d) => {
                const dSchools = schoolsPerDistrict.get(d.code) ?? [];
                const dStudents = dSchools.reduce((a, s) => a + s.total_students, 0);
                return (
                  <TableRow key={d.code}>
                    <TableCell className="font-medium">{d.name}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{d.code}</TableCell>
                    <TableCell className="text-right tabular-nums">{dSchools.length}</TableCell>
                    <TableCell className="text-right tabular-nums">{dStudents.toLocaleString()}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* Schools */}
      <section className="space-y-3">
        <PageHeader
          title="Schools"
          description={`${schools.length} schools across ${breakdown.province_name}`}
        >
          <ExportMenu
            filename={`schools-${province.code.toLowerCase()}`}
            title={`Schools — ${breakdown.province_name}`}
            subtitle={`${filteredSchools.length} of ${schools.length} schools`}
            columns={[
              { key: "code", label: "Code", width: 14 },
              { key: "name", label: "School", width: 28 },
              { key: "type", label: "Type", width: 10 },
              { key: "district_code", label: "District", width: 12 },
              { key: "total_students", label: "Students", width: 10 },
              { key: "total_teachers", label: "Teachers", width: 10 },
              { key: (s: MockSchoolNational) => pct(s.attendance_rate), label: "Attendance" },
              { key: (s: MockSchoolNational) => pct(s.pass_rate), label: "Pass rate" },
              { key: (s: MockSchoolNational) => usd(s.outstanding_usd), label: "Outstanding $" },
            ]}
            rows={filteredSchools}
          />
        </PageHeader>
        <div className="flex items-center gap-3">
          <SearchInput value={schoolSearch} onChange={setSchoolSearch} placeholder="Search school name or code…" className="sm:w-72" />
          <span className="text-sm text-muted-foreground">
            {filteredSchools.length} of {schools.length}
          </span>
        </div>
        <div className="rounded-lg border bg-card shadow-card overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>School</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Students</TableHead>
                <TableHead className="text-right">Teachers</TableHead>
                <TableHead className="text-right">Attendance</TableHead>
                <TableHead className="text-right">Pass rate</TableHead>
                <TableHead className="text-right">Outstanding</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredSchools.map((s) => (
                <TableRow key={s.id} className="hover:bg-muted/40">
                  <TableCell>
                    <Link href={`/schools/${s.id}`} className="font-medium hover:underline">
                      {s.name}
                    </Link>
                    <div className="text-xs text-muted-foreground">{s.code}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{s.type}</Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{s.total_students}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.total_teachers}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(s.attendance_rate)}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(s.pass_rate)}</TableCell>
                  <TableCell className="text-right tabular-nums">{usd(s.outstanding_usd)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}
