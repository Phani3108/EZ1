/**
 * National Provinces overview — sovereign theme.
 * Shows all 10 Zimbabwe provinces with aggregated KPIs sourced from
 * the master mock dataset (`MOCK_PROVINCE_BREAKDOWN`).
 *
 * Permission: authenticated (or guest). No backend dependency — the
 * data is bundled into the api-client package via the workbook regen pipeline.
 */

"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import {
  MOCK_PROVINCE_BREAKDOWN,
  MOCK_NATIONAL_KPIS,
  type MockProvinceBreakdown,
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
  Users, GraduationCap, ClipboardCheck, DollarSign, Map, School, ArrowRight,
} from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { SearchInput } from "@/components/search-input";

const usd = (n: number) => `$${Math.round(n).toLocaleString()}`;
const pct = (n: number) => `${n.toFixed(1)}%`;

export default function ProvincesPage() {
  const [search, setSearch] = useState("");

  const filtered = useMemo<MockProvinceBreakdown[]>(() => {
    if (!search) return MOCK_PROVINCE_BREAKDOWN;
    const q = search.toLowerCase();
    return MOCK_PROVINCE_BREAKDOWN.filter(
      (p) =>
        p.province_name.toLowerCase().includes(q) ||
        p.region.toLowerCase().includes(q) ||
        p.capital.toLowerCase().includes(q),
    );
  }, [search]);

  return (
    <div className="space-y-6">
      <FlagHeader
        title="National Provinces"
        subtitle="Zimbabwe · 10 provinces · 74 districts"
        actions={
          <>
            <OfficialBadge variant="mopse" label="MoPSE" />
            <OfficialBadge variant="vision2030" label="Vision 2030" />
          </>
        }
        stripe="thick"
        className="rounded-lg"
      />

      {/* National rollup band */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MinistryStatCard
          label="Students Nationwide"
          value={MOCK_NATIONAL_KPIS.total_students.toLocaleString()}
          icon={Users}
          accent="green"
          source={`${MOCK_NATIONAL_KPIS.total_boys.toLocaleString()} boys · ${MOCK_NATIONAL_KPIS.total_girls.toLocaleString()} girls`}
        />
        <MinistryStatCard
          label="Schools Reporting"
          value={MOCK_NATIONAL_KPIS.total_schools.toLocaleString()}
          icon={School}
          accent="gold"
          source={`${MOCK_NATIONAL_KPIS.total_classes.toLocaleString()} classes`}
        />
        <MinistryStatCard
          label="National Attendance"
          value={pct(MOCK_NATIONAL_KPIS.average_attendance_rate)}
          icon={ClipboardCheck}
          accent="green"
          source="Source: attendance-service · 30-day rolling"
        />
        <MinistryStatCard
          label="Fee Collection"
          value={pct(MOCK_NATIONAL_KPIS.collection_rate)}
          icon={DollarSign}
          accent="green"
          source={`${usd(MOCK_NATIONAL_KPIS.collected_usd)} of ${usd(MOCK_NATIONAL_KPIS.billed_usd)}`}
        />
      </div>

      <PageHeader
        title="Provincial Breakdown"
        description="Aggregated performance metrics per province. Click a row to drill into districts and schools."
      >
        <ExportMenu
          filename="zimbabwe-provinces"
          title="Zimbabwe — Provincial Breakdown"
          subtitle="All 10 provinces · current term aggregates"
          meta={[
            ["Total students", MOCK_NATIONAL_KPIS.total_students],
            ["Total schools", MOCK_NATIONAL_KPIS.total_schools],
            ["Total teachers", MOCK_NATIONAL_KPIS.total_teachers],
            ["National attendance", pct(MOCK_NATIONAL_KPIS.average_attendance_rate)],
            ["National pass rate", pct(MOCK_NATIONAL_KPIS.average_pass_rate)],
          ]}
          columns={[
            { key: "province_code", label: "Code", width: 8 },
            { key: "province_name", label: "Province", width: 24 },
            { key: "region", label: "Region", width: 16 },
            { key: "capital", label: "Capital", width: 14 },
            { key: "schools_count", label: "Schools", width: 8 },
            { key: "total_students", label: "Students", width: 10 },
            { key: "total_teachers", label: "Teachers", width: 10 },
            { key: (r: MockProvinceBreakdown) => r.student_teacher_ratio, label: "S:T ratio", width: 10 },
            { key: (r: MockProvinceBreakdown) => pct(r.average_attendance_rate), label: "Attendance", width: 12 },
            { key: (r: MockProvinceBreakdown) => pct(r.average_pass_rate), label: "Pass rate", width: 12 },
            { key: (r: MockProvinceBreakdown) => usd(r.billed_usd), label: "Billed", width: 14 },
            { key: (r: MockProvinceBreakdown) => usd(r.collected_usd), label: "Collected", width: 14 },
            { key: (r: MockProvinceBreakdown) => pct(r.collection_rate), label: "Collection %", width: 12 },
          ]}
          rows={filtered}
        />
      </PageHeader>

      <div className="flex items-center gap-3">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search province, region, capital…"
          className="sm:w-80"
        />
        <span className="text-sm text-muted-foreground">
          Showing {filtered.length} of {MOCK_PROVINCE_BREAKDOWN.length} provinces
        </span>
      </div>

      <div className="rounded-lg border bg-card shadow-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Province</TableHead>
              <TableHead className="text-right">Schools</TableHead>
              <TableHead className="text-right">Students</TableHead>
              <TableHead className="text-right">Teachers</TableHead>
              <TableHead className="text-right">S:T ratio</TableHead>
              <TableHead className="text-right">Attendance</TableHead>
              <TableHead className="text-right">Pass rate</TableHead>
              <TableHead className="text-right">Collection</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((p) => (
              <TableRow key={p.province_code} className="hover:bg-muted/40">
                <TableCell>
                  <div className="flex flex-col">
                    <Link
                      href={`/provinces/${p.province_code}`}
                      className="font-medium text-foreground hover:underline"
                    >
                      {p.province_name}
                    </Link>
                    <span className="text-xs text-muted-foreground">
                      {p.region} · {p.capital}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">{p.schools_count}</TableCell>
                <TableCell className="text-right tabular-nums">{p.total_students.toLocaleString()}</TableCell>
                <TableCell className="text-right tabular-nums">{p.total_teachers.toLocaleString()}</TableCell>
                <TableCell className="text-right tabular-nums">{p.student_teacher_ratio}</TableCell>
                <TableCell className="text-right tabular-nums">
                  <Badge variant={p.average_attendance_rate >= 85 ? "default" : "secondary"}>
                    {pct(p.average_attendance_rate)}
                  </Badge>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <Badge variant={p.average_pass_rate >= 60 ? "default" : "secondary"}>
                    {pct(p.average_pass_rate)}
                  </Badge>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <span className={p.collection_rate >= 70 ? "text-emerald-700" : "text-amber-700"}>
                    {pct(p.collection_rate)}
                  </span>
                </TableCell>
                <TableCell>
                  <Link
                    href={`/provinces/${p.province_code}`}
                    aria-label={`Open ${p.province_name}`}
                    className="inline-flex h-7 w-7 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
                  >
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <p className="text-xs text-muted-foreground">
        Source: master mock dataset (deterministic). Run{" "}
        <code className="rounded bg-muted px-1.5 py-0.5">python scripts/build_master_dataset.py</code>{" "}
        to regenerate.
      </p>
    </div>
  );
}
