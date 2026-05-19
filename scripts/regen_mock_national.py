#!/usr/bin/env python3
"""Regenerate the frontend national mock store from the master workbook.

Reads ``scripts/data/eduzim_master.xlsx`` and writes
``packages/api-client/src/mock-national.ts`` containing:

  - MOCK_PROVINCES                  (10 rows, with aggregated KPIs)
  - MOCK_DISTRICTS                  (74 rows, with aggregated KPIs)
  - MOCK_SCHOOLS_NATIONAL           (60 rows, with rich KPIs)
  - MOCK_NATIONAL_KPIS              (single object — national rollup)
  - MOCK_PROVINCE_BREAKDOWN         (per-province deep stats)
  - MOCK_TOP_SCHOOLS                (10 best-performing schools)
  - getProvinceById / getSchoolById helpers

This file is *additive* — it does not replace existing single-school
mock data in ``mock-data.ts``. The 30-student "Harare Central"
demo school remains the deep view for student/parent/teacher pages;
this new file unlocks national + multi-province dashboards.

CI guard: ``--check`` flag verifies the file is up-to-date with the
workbook (refuses to write, exits non-zero on drift).

Usage:
    python scripts/regen_mock_national.py
    python scripts/regen_mock_national.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "scripts/data/eduzim_master.xlsx"
OUT_TS = ROOT / "packages/api-client/src/mock-national.ts"


def _load_workbook() -> Dict[str, List[Dict]]:
    from openpyxl import load_workbook

    if not WORKBOOK.exists():
        raise SystemExit(
            f"Workbook missing: {WORKBOOK}\nRun: python scripts/build_master_dataset.py"
        )
    wb = load_workbook(WORKBOOK, read_only=True, data_only=True)
    out: Dict[str, List[Dict]] = {}
    for ws in wb.worksheets:
        name = ws.title
        if name.startswith("_"):
            continue
        rows = ws.iter_rows(values_only=True)
        try:
            header = list(next(rows))
        except StopIteration:
            out[name] = []
            continue
        records: List[Dict] = []
        for row in rows:
            if row is None or all(v is None for v in row):
                continue
            records.append(dict(zip(header, row)))
        out[name] = records
    return out


def _agg_school(data: Dict[str, List[Dict]], school_id: str) -> Dict:
    students = [s for s in data["Students"] if s["school_id"] == school_id]
    invoices = [i for i in data["Invoices"] if i["school_id"] == school_id]
    payments = [p for p in data["Payments"] if p["school_id"] == school_id]
    attendance = [a for a in data["Attendance"] if a["school_id"] == school_id]
    marks = [m for m in data["Marks"] if m["school_id"] == school_id and m["marks"] is not None]
    teachers = [t for t in data["Teachers"] if t["school_id"] == school_id]
    classes = [c for c in data["Classes"] if c["school_id"] == school_id]

    total_billed = sum(float(i["total_amount"]) for i in invoices)
    total_paid = sum(float(i["paid_amount"]) for i in invoices)
    outstanding = round(total_billed - total_paid, 2)
    collection_rate = round((total_paid / total_billed * 100) if total_billed else 0, 1)

    present = sum(1 for a in attendance if a["status"] == "P")
    late = sum(1 for a in attendance if a["status"] == "L")
    absent = sum(1 for a in attendance if a["status"] == "A")
    att_total = max(1, present + late + absent)
    attendance_rate = round(((present + late) / att_total) * 100, 1)

    avg_mark = round(sum(int(m["marks"]) for m in marks) / max(1, len(marks)), 1) if marks else 0.0
    pass_rate = round(sum(1 for m in marks if int(m["marks"]) >= 50) / max(1, len(marks)) * 100, 1)

    boys = sum(1 for s in students if s["gender"] == "M")
    girls = sum(1 for s in students if s["gender"] == "F")

    return {
        "total_students": len(students),
        "boys": boys,
        "girls": girls,
        "total_teachers": len(teachers),
        "total_classes": len(classes),
        "student_teacher_ratio": round(len(students) / max(1, len(teachers)), 1),
        "attendance_rate": attendance_rate,
        "average_mark": avg_mark,
        "pass_rate": pass_rate,
        "billed_usd": round(total_billed, 2),
        "collected_usd": round(total_paid, 2),
        "outstanding_usd": outstanding,
        "collection_rate": collection_rate,
        "payments_count": len(payments),
    }


def build_payload(data: Dict[str, List[Dict]]) -> Dict:
    provinces_raw = data["Provinces"]
    districts_raw = data["Districts"]
    schools_raw = data["Schools"]

    # Schools with KPIs
    schools = []
    for s in schools_raw:
        agg = _agg_school(data, s["id"])
        schools.append({
            "id": s["id"],
            "code": s["code"],
            "name": s["name"],
            "province_code": s["province_code"],
            "district_code": s["district_code"],
            "type": s["type"],
            "address": s["address"],
            "phone": s["phone"],
            "email": s["email"],
            "founded_year": s["founded_year"],
            "principal_name": s["principal_name"],
            **agg,
        })

    # Aggregate per province
    province_breakdown = []
    for p in provinces_raw:
        prov_schools = [s for s in schools if s["province_code"] == p["code"]]
        total_students = sum(s["total_students"] for s in prov_schools)
        total_teachers = sum(s["total_teachers"] for s in prov_schools)
        billed = sum(s["billed_usd"] for s in prov_schools)
        collected = sum(s["collected_usd"] for s in prov_schools)
        att_weighted = sum(s["attendance_rate"] * s["total_students"] for s in prov_schools)
        pass_weighted = sum(s["pass_rate"] * s["total_students"] for s in prov_schools)
        district_codes = sorted({s["district_code"] for s in prov_schools})
        province_breakdown.append({
            "province_code": p["code"],
            "province_name": p["name"],
            "region": p["region"],
            "capital": p["capital"],
            "schools_count": len(prov_schools),
            "districts_with_schools": len(district_codes),
            "total_students": total_students,
            "total_teachers": total_teachers,
            "student_teacher_ratio": round(total_students / max(1, total_teachers), 1),
            "boys": sum(s["boys"] for s in prov_schools),
            "girls": sum(s["girls"] for s in prov_schools),
            "average_attendance_rate": round(att_weighted / max(1, total_students), 1),
            "average_pass_rate": round(pass_weighted / max(1, total_students), 1),
            "billed_usd": round(billed, 2),
            "collected_usd": round(collected, 2),
            "outstanding_usd": round(billed - collected, 2),
            "collection_rate": round((collected / billed * 100) if billed else 0, 1),
        })

    # National rollup
    national = {
        "total_provinces": len(provinces_raw),
        "total_districts": len(districts_raw),
        "total_schools": len(schools),
        "total_students": sum(s["total_students"] for s in schools),
        "total_boys": sum(s["boys"] for s in schools),
        "total_girls": sum(s["girls"] for s in schools),
        "total_teachers": sum(s["total_teachers"] for s in schools),
        "total_classes": sum(s["total_classes"] for s in schools),
        "average_attendance_rate": round(
            sum(s["attendance_rate"] * s["total_students"] for s in schools)
            / max(1, sum(s["total_students"] for s in schools)),
            1,
        ),
        "average_pass_rate": round(
            sum(s["pass_rate"] * s["total_students"] for s in schools)
            / max(1, sum(s["total_students"] for s in schools)),
            1,
        ),
        "billed_usd": round(sum(s["billed_usd"] for s in schools), 2),
        "collected_usd": round(sum(s["collected_usd"] for s in schools), 2),
        "outstanding_usd": round(sum(s["outstanding_usd"] for s in schools), 2),
        "collection_rate": round(
            (sum(s["collected_usd"] for s in schools) / sum(s["billed_usd"] for s in schools) * 100)
            if sum(s["billed_usd"] for s in schools) else 0,
            1,
        ),
    }

    top_schools = sorted(schools, key=lambda s: (s["pass_rate"], s["average_mark"]), reverse=True)[:10]

    return {
        "provinces": provinces_raw,
        "districts": districts_raw,
        "schools": schools,
        "province_breakdown": province_breakdown,
        "national": national,
        "top_schools": [{
            "id": s["id"], "name": s["name"], "code": s["code"],
            "province_code": s["province_code"], "district_code": s["district_code"],
            "pass_rate": s["pass_rate"], "average_mark": s["average_mark"],
            "attendance_rate": s["attendance_rate"], "total_students": s["total_students"],
        } for s in top_schools],
    }


HEADER = '''/**
 * EduZim — National Mock Data
 * =============================
 * AUTO-GENERATED from scripts/data/eduzim_master.xlsx by
 * scripts/regen_mock_national.py. Do not edit by hand.
 *
 * Provides multi-province / multi-school aggregates used by the
 * sovereign (admin) dashboards. Single-school deep mock data lives
 * in ``mock-data.ts``.
 */

'''


TS_TYPES = '''
export interface MockProvince {
    id: string;
    code: string;
    name: string;
    region: string;
    capital: string;
}

export interface MockDistrict {
    id: string;
    code: string;
    name: string;
    province_code: string;
}

export interface MockSchoolNational {
    id: string;
    code: string;
    name: string;
    province_code: string;
    district_code: string;
    type: "PRIMARY" | "SECONDARY";
    address: string;
    phone: string;
    email: string;
    founded_year: number;
    principal_name: string;
    total_students: number;
    boys: number;
    girls: number;
    total_teachers: number;
    total_classes: number;
    student_teacher_ratio: number;
    attendance_rate: number;
    average_mark: number;
    pass_rate: number;
    billed_usd: number;
    collected_usd: number;
    outstanding_usd: number;
    collection_rate: number;
    payments_count: number;
}

export interface MockProvinceBreakdown {
    province_code: string;
    province_name: string;
    region: string;
    capital: string;
    schools_count: number;
    districts_with_schools: number;
    total_students: number;
    total_teachers: number;
    student_teacher_ratio: number;
    boys: number;
    girls: number;
    average_attendance_rate: number;
    average_pass_rate: number;
    billed_usd: number;
    collected_usd: number;
    outstanding_usd: number;
    collection_rate: number;
}

export interface MockNationalKpis {
    total_provinces: number;
    total_districts: number;
    total_schools: number;
    total_students: number;
    total_boys: number;
    total_girls: number;
    total_teachers: number;
    total_classes: number;
    average_attendance_rate: number;
    average_pass_rate: number;
    billed_usd: number;
    collected_usd: number;
    outstanding_usd: number;
    collection_rate: number;
}

export interface MockTopSchool {
    id: string;
    name: string;
    code: string;
    province_code: string;
    district_code: string;
    pass_rate: number;
    average_mark: number;
    attendance_rate: number;
    total_students: number;
}
'''


def emit_ts(payload: Dict) -> str:
    def dumps(obj) -> str:
        return json.dumps(obj, indent=4, sort_keys=False, ensure_ascii=False)

    parts = [HEADER, TS_TYPES]
    parts.append("export const MOCK_PROVINCES: MockProvince[] = " + dumps(payload["provinces"]) + ";\n\n")
    parts.append("export const MOCK_DISTRICTS: MockDistrict[] = " + dumps(payload["districts"]) + ";\n\n")
    parts.append("export const MOCK_SCHOOLS_NATIONAL: MockSchoolNational[] = " + dumps(payload["schools"]) + ";\n\n")
    parts.append("export const MOCK_PROVINCE_BREAKDOWN: MockProvinceBreakdown[] = " + dumps(payload["province_breakdown"]) + ";\n\n")
    parts.append("export const MOCK_NATIONAL_KPIS: MockNationalKpis = " + dumps(payload["national"]) + ";\n\n")
    parts.append("export const MOCK_TOP_SCHOOLS: MockTopSchool[] = " + dumps(payload["top_schools"]) + ";\n\n")
    parts.append("""\
export function getProvinceByCode(code: string): MockProvince | undefined {
    return MOCK_PROVINCES.find((p) => p.code === code);
}

export function getProvinceBreakdown(code: string): MockProvinceBreakdown | undefined {
    return MOCK_PROVINCE_BREAKDOWN.find((p) => p.province_code === code);
}

export function getDistrictsByProvince(code: string): MockDistrict[] {
    return MOCK_DISTRICTS.filter((d) => d.province_code === code);
}

export function getSchoolsByProvince(code: string): MockSchoolNational[] {
    return MOCK_SCHOOLS_NATIONAL.filter((s) => s.province_code === code);
}

export function getSchoolsByDistrict(code: string): MockSchoolNational[] {
    return MOCK_SCHOOLS_NATIONAL.filter((s) => s.district_code === code);
}

export function getSchoolById(id: string): MockSchoolNational | undefined {
    return MOCK_SCHOOLS_NATIONAL.find((s) => s.id === id);
}
""")
    return "".join(parts)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="Verify file is up-to-date; exit 1 on drift.")
    args = ap.parse_args(argv)

    data = _load_workbook()
    payload = build_payload(data)
    rendered = emit_ts(payload)

    if args.check:
        if not OUT_TS.exists():
            print(f"✗ {OUT_TS} does not exist", file=sys.stderr)
            return 1
        existing = OUT_TS.read_text(encoding="utf-8")
        if existing != rendered:
            print(f"✗ {OUT_TS} is out of date — rerun: python scripts/regen_mock_national.py", file=sys.stderr)
            return 1
        print(f"✓ {OUT_TS.relative_to(ROOT)} is up to date")
        return 0

    OUT_TS.parent.mkdir(parents=True, exist_ok=True)
    OUT_TS.write_text(rendered, encoding="utf-8")
    size_kb = OUT_TS.stat().st_size // 1024
    print(f"✓ Wrote {OUT_TS.relative_to(ROOT)} ({size_kb} KiB)")
    print(f"  provinces={len(payload['provinces'])} districts={len(payload['districts'])} schools={len(payload['schools'])}")
    print(f"  national: students={payload['national']['total_students']} teachers={payload['national']['total_teachers']} schools={payload['national']['total_schools']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
