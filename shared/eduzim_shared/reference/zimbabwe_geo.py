"""Zimbabwe geography reference data.

Single source of truth for the 10 provinces and 63 administrative districts of
Zimbabwe. Used by:
- ``scripts/build_master_dataset.py`` to generate the master mock workbook
- ``scripts/import_master.py`` to seed the school-service database
- ``scripts/regen_mock_data.py`` to refresh the frontend mock store

Province codes follow MoPSE / ZimStat conventions (3-letter codes).
District codes are short (max 8 chars) lowercase-ish identifiers stable across regenerations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Province:
    code: str            # 3-letter MoPSE province code
    name: str            # Full name as commonly written
    region: str          # Loose geographic grouping
    capital: str         # Provincial capital / administrative HQ


@dataclass(frozen=True)
class District:
    code: str            # short stable code
    name: str
    province_code: str   # FK -> Province.code


ZIMBABWE_PROVINCES: List[Province] = [
    Province("BYO", "Bulawayo Metropolitan", "Matabeleland",     "Bulawayo"),
    Province("HRE", "Harare Metropolitan",   "Mashonaland",      "Harare"),
    Province("MAN", "Manicaland",            "Eastern Highlands", "Mutare"),
    Province("MCE", "Mashonaland Central",   "Mashonaland",      "Bindura"),
    Province("MEA", "Mashonaland East",      "Mashonaland",      "Marondera"),
    Province("MWE", "Mashonaland West",      "Mashonaland",      "Chinhoyi"),
    Province("MAS", "Masvingo",              "Southern",         "Masvingo"),
    Province("MTN", "Matabeleland North",    "Matabeleland",     "Lupane"),
    Province("MTS", "Matabeleland South",    "Matabeleland",     "Gwanda"),
    Province("MID", "Midlands",              "Central",          "Gweru"),
]


# 63 districts mapped to their parent province. Codes are stable identifiers.
_DISTRICTS_RAW: List[Tuple[str, str, str]] = [
    # ─── Bulawayo Metropolitan ───
    ("byo-cn", "Bulawayo Central",  "BYO"),
    ("byo-mp", "Mpopoma-Pelandaba", "BYO"),
    ("byo-nk", "Nkulumane",         "BYO"),
    ("byo-im", "Imbizo",            "BYO"),
    ("byo-rg", "Reigate",           "BYO"),
    ("byo-tj", "Tshabalala",        "BYO"),

    # ─── Harare Metropolitan ───
    ("hre-cn", "Harare Central",    "HRE"),
    ("hre-cb", "Chitungwiza",       "HRE"),
    ("hre-ep", "Epworth",           "HRE"),
    ("hre-mb", "Mbare-Hatfield",    "HRE"),
    ("hre-gw", "Glen View-Mufakose","HRE"),
    ("hre-kk", "Kuwadzana-Warren",  "HRE"),
    ("hre-hg", "Highfield",         "HRE"),

    # ─── Manicaland (7) ───
    ("man-mtc", "Mutare City",      "MAN"),
    ("man-mtr", "Mutare Rural",     "MAN"),
    ("man-bua", "Buhera",           "MAN"),
    ("man-chm", "Chimanimani",      "MAN"),
    ("man-chp", "Chipinge",         "MAN"),
    ("man-mks", "Makoni",           "MAN"),
    ("man-mut", "Mutasa",           "MAN"),
    ("man-nyg", "Nyanga",           "MAN"),

    # ─── Mashonaland Central (8) ───
    ("mce-bnd", "Bindura",          "MCE"),
    ("mce-cnt", "Centenary",        "MCE"),
    ("mce-gku", "Guruve",           "MCE"),
    ("mce-mke", "Mazowe",           "MCE"),
    ("mce-mbi", "Mbire",            "MCE"),
    ("mce-mtk", "Mt Darwin",        "MCE"),
    ("mce-rsh", "Rushinga",         "MCE"),
    ("mce-shm", "Shamva",           "MCE"),

    # ─── Mashonaland East (9) ───
    ("mea-mrn", "Marondera",        "MEA"),
    ("mea-chk", "Chikomba",         "MEA"),
    ("mea-grr", "Goromonzi",        "MEA"),
    ("mea-htf", "Hwedza",           "MEA"),
    ("mea-mds", "Mudzi",            "MEA"),
    ("mea-msh", "Murehwa",          "MEA"),
    ("mea-mtk", "Mutoko",           "MEA"),
    ("mea-syp", "Seke",             "MEA"),
    ("mea-uzm", "Uzumba-Maramba",   "MEA"),

    # ─── Mashonaland West (7) ───
    ("mwe-chn", "Chinhoyi",         "MWE"),
    ("mwe-chg", "Chegutu",          "MWE"),
    ("mwe-hrr", "Hurungwe",         "MWE"),
    ("mwe-krb", "Kariba",           "MWE"),
    ("mwe-mkd", "Makonde",          "MWE"),
    ("mwe-mhd", "Mhondoro-Ngezi",   "MWE"),
    ("mwe-zvm", "Zvimba",           "MWE"),

    # ─── Masvingo (7) ───
    ("mas-msv", "Masvingo",         "MAS"),
    ("mas-bks", "Bikita",           "MAS"),
    ("mas-cdz", "Chiredzi",         "MAS"),
    ("mas-civ", "Chivi",            "MAS"),
    ("mas-grj", "Gutu",             "MAS"),
    ("mas-mhk", "Mwenezi",          "MAS"),
    ("mas-ndg", "Zaka",             "MAS"),

    # ─── Matabeleland North (7) ───
    ("mtn-lpe", "Lupane",           "MTN"),
    ("mtn-bbk", "Binga",            "MTN"),
    ("mtn-bbg", "Bubi",             "MTN"),
    ("mtn-hwg", "Hwange",           "MTN"),
    ("mtn-nkb", "Nkayi",            "MTN"),
    ("mtn-tsh", "Tsholotsho",       "MTN"),
    ("mtn-umg", "Umguza",           "MTN"),

    # ─── Matabeleland South (7) ───
    ("mts-gwd", "Gwanda",           "MTS"),
    ("mts-bei", "Beitbridge",       "MTS"),
    ("mts-bmb", "Bulilima",         "MTS"),
    ("mts-imk", "Insiza",           "MTS"),
    ("mts-mgw", "Mangwe",           "MTS"),
    ("mts-mtb", "Matobo",           "MTS"),
    ("mts-uzg", "Umzingwane",       "MTS"),

    # ─── Midlands (8) ───
    ("mid-gwr", "Gweru",            "MID"),
    ("mid-czi", "Chirumhanzu",      "MID"),
    ("mid-gkw", "Gokwe North",      "MID"),
    ("mid-gks", "Gokwe South",      "MID"),
    ("mid-kwk", "Kwekwe",           "MID"),
    ("mid-mbr", "Mberengwa",        "MID"),
    ("mid-shr", "Shurugwi",         "MID"),
    ("mid-zvi", "Zvishavane",       "MID"),
]


ZIMBABWE_DISTRICTS: List[District] = [District(code, name, prov) for code, name, prov in _DISTRICTS_RAW]


# ─── Convenient lookups ───
PROVINCE_BY_CODE: Dict[str, Province] = {p.code: p for p in ZIMBABWE_PROVINCES}

DISTRICTS_BY_PROVINCE_CODE: Dict[str, List[District]] = {}
for _d in ZIMBABWE_DISTRICTS:
    DISTRICTS_BY_PROVINCE_CODE.setdefault(_d.province_code, []).append(_d)


# Sanity check at import time — catches typos in province codes early.
_orphans = [d for d in ZIMBABWE_DISTRICTS if d.province_code not in PROVINCE_BY_CODE]
if _orphans:
    raise RuntimeError(
        f"zimbabwe_geo: {len(_orphans)} district(s) reference unknown province codes: "
        + ", ".join(f"{d.code}->{d.province_code}" for d in _orphans)
    )
