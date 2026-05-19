/**
 * National Schools directory — all 60 schools across 10 provinces.
 *
 * Permission: authenticated (or guest). Data is bundled from the master
 * mock dataset (`MOCK_SCHOOLS_NATIONAL`).
 */

"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import {
  MOCK_SCHOOLS_NATIONAL,
  MOCK_PROVINCES,
  MOCK_NATIONAL_KPIS,
  type MockSchoolNational,
} from "@eduzim/api-client";
import {
  FlagHeader,
  MinistryStatCard,
  OfficialBadge,
  ExportMenu,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  Badge,
  Select,
} from "@eduzim/ui";
import { School, Users, ClipboardCheck, DollarSign } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";

const usd = (n: number) => `$${Math.round(n).toLocaleString()}`;
const pct = (n: number) => `${n.toFixed(1)}%`;

export default function SchoolsDirectoryPage() {
  const [search, setSearch] = useState("");
  const [province, setProvince] = useState<string>("all");
  const [type, setType] = useState<"all" | "PRIMARY" | "SECONDARY">("all");

  const filtered = useMemo<MockSchoolNational[]>(() => {
    let list = MOCK_SCHOOLS_NATIONAL;
    if (province !== "all") list = list.filter((s) => s.province_code === province);
    if (type !== "all") list = list.filter((s) => s.type === type);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.code.toLowerCase().includes(q) ||
          s.principal_name.toLowerCase().includes(q),
      );
    }
    return list;
  }, [search, province, type]);

  return (
    <div className="space-y-6">
      <FlagHeader
        title="National Schools Directory"
        subtitle="Every school enrolled on the EduZim platform"
        actions={<OfficialBadge variant="mopse" label="MoPSE" />}
        stripe="thick"
        className="rounded-lg"
      />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MinistryStatCard
          label="Schools"
          value={MOCK_NATIONAL_KPIS.total_schools.toLocaleString()}
          icon={School}
          accent="green"
          source={`${MOCK_NATIONAL_KPIS.total_provinces} provinces · ${MOCK_NATIONAL_KPIS.total_districts} districts`}
        />
        <MinistryStatCard
          label="Students"
          value={MOCK_NATIONAL_KPIS.total_students.toLocaleString()}
          icon={Users}
          accent="gold"
          source={`${MOCK_NATIONAL_KPIS.total_classes.toLocaleString()} classes`}
        />
        <MinistryStatCard
          label="Attendance"
          value={pct(MOCK_NATIONAL_KPIS.average_attendance_rate)}
          icon={ClipboardCheck}
          accent="green"
        />
        <MinistryStatCard
          label="Outstanding"
          value={usd(MOCK_NATIONAL_KPIS.outstanding_usd)}
          icon={DollarSign}
          accent="red"
          source={`Collection ${pct(MOCK_NATIONAL_KPIS.collection_rate)}`}
        />
      </div>

      <PageHeader title="All Schools" description="Filter, search and export the full national directory.">
        <ExportMenu
          filename="schools-national"
          title="National Schools Directory"
          subtitle={`${filtered.length} of ${MOCK_SCHOOLS_NATIONAL.length} schools`}
          columns={[
            { key: "code", label: "Code", width: 14 },
            { key: "name", label: "School", width: 28 },
            { key: "type", label: "Type", width: 10 },
            { key: "province_code", label: "Province", width: 10 },
            { key: "district_code", label: "District", width: 12 },
            { key: "principal_name", label: "Principal", width: 22 },
            { key: "founded_year", label: "Founded", width: 10 },
            { key: "total_students", label: "Students", width: 10 },
            { key: "total_teachers", label: "Teachers", width: 10 },
            { key: (s: MockSchoolNational) => pct(s.attendance_rate), label: "Attendance" },
            { key: (s: MockSchoolNational) => pct(s.pass_rate), label: "Pass rate" },
            { key: (s: MockSchoolNational) => usd(s.outstanding_usd), label: "Outstanding $" },
            { key: "phone", label: "Phone", width: 14 },
            { key: "email", label: "Email", width: 26 },
          ]}
          rows={filtered}
        />
      </PageHeader>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <SearchInput value={search} onChange={setSearch} placeholder="Search school, code or principal…" className="sm:w-80" />
        <Select value={province} onChange={(e) => setProvince(e.target.value)} className="sm:w-56">
          <option value="all">All provinces</option>
          {MOCK_PROVINCES.map((p) => (
            <option key={p.code} value={p.code}>{p.name}</option>
          ))}
        </Select>
        <Select value={type} onChange={(e) => setType(e.target.value as "all" | "PRIMARY" | "SECONDARY")} className="sm:w-44">
          <option value="all">All types</option>
          <option value="PRIMARY">Primary</option>
          <option value="SECONDARY">Secondary</option>
        </Select>
        <span className="text-sm text-muted-foreground">
          {filtered.length} of {MOCK_SCHOOLS_NATIONAL.length} schools
        </span>
      </div>

      <div className="rounded-lg border bg-card shadow-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>School</TableHead>
              <TableHead>Province</TableHead>
              <TableHead>Type</TableHead>
              <TableHead className="text-right">Students</TableHead>
              <TableHead className="text-right">Teachers</TableHead>
              <TableHead className="text-right">Attendance</TableHead>
              <TableHead className="text-right">Pass rate</TableHead>
              <TableHead className="text-right">Outstanding</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((s) => (
              <TableRow key={s.id} className="hover:bg-muted/40">
                <TableCell>
                  <Link href={`/schools/${s.id}`} className="font-medium hover:underline">
                    {s.name}
                  </Link>
                  <div className="text-xs text-muted-foreground">{s.code} · {s.principal_name}</div>
                </TableCell>
                <TableCell>
                  <Link href={`/provinces/${s.province_code}`} className="text-sm hover:underline">
                    {s.province_code}
                  </Link>
                </TableCell>
                <TableCell><Badge variant="secondary">{s.type}</Badge></TableCell>
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
    </div>
  );
}
