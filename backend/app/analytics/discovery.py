"""
Data Discovery — query shift_types, map absence codes, validate data.

Run before building sick leave cubes to determine if absence data exists.
Outputs: CTXE/discovery_report.json
"""

import json
import re
from datetime import datetime
from pathlib import Path

from app.analytics.connection import get_conn, fetchall


# Standard absence type mappings — regex patterns on shift_type.name
_ABSENCE_PATTERNS = [
    ("egenmelding", re.compile(r"egenmelding|egen\s*meld", re.IGNORECASE)),
    ("sykemelding", re.compile(r"sykemeld|sykefrav|syke\s*frav", re.IGNORECASE)),
    ("child_sick", re.compile(r"barn|sykt\s*barn|barns?\s*syk", re.IGNORECASE)),
    ("vacation", re.compile(r"ferie|permisjon|fri", re.IGNORECASE)),
    ("other_absence", re.compile(r"syk(?!e)|fraværs?|absence|leave|permitt", re.IGNORECASE)),
]


def _find_ctxe_dir() -> Path:
    """Find the CTXE directory relative to the project root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "CTXE"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Cannot find CTXE/ directory")


def discover_shift_types() -> dict:
    """Query planday.shift_types and map to standard absence categories."""
    print("Discovery: querying shift_types...")

    shift_types = fetchall("""
        SELECT st.id, st.name, st.pay_percentage, st.portal_name,
               COUNT(s.id) AS shift_count,
               MIN(s.start_date_time) AS earliest_shift,
               MAX(s.start_date_time) AS latest_shift
        FROM planday.shift_types st
        LEFT JOIN planday.shifts s
            ON s.shift_type_id = st.id AND s.portal_name = st.portal_name
        GROUP BY st.id, st.name, st.pay_percentage, st.portal_name
        ORDER BY shift_count DESC
    """)

    if not shift_types:
        print("Discovery: no shift_types found!")
        return {"shift_types": [], "absence_mapping": {}, "has_absence_data": False}

    print(f"Discovery: found {len(shift_types)} shift types")

    # Map each shift type to an absence category
    absence_mapping = {}
    mapped_types = []

    for st in shift_types:
        name = st.get("name", "")
        mapped_category = None
        for category, pattern in _ABSENCE_PATTERNS:
            if pattern.search(name):
                mapped_category = category
                break

        if mapped_category:
            absence_mapping[str(st["id"])] = {
                "name": name,
                "category": mapped_category,
                "portal_name": st.get("portal_name"),
                "shift_count": st.get("shift_count", 0),
            }
            mapped_types.append({
                "shift_type_id": st["id"],
                "name": name,
                "category": mapped_category,
                "shift_count": st.get("shift_count", 0),
            })

    has_absence_data = any(
        m["shift_count"] > 0 for m in absence_mapping.values()
    )

    return {
        "shift_types": [
            {
                "id": st["id"],
                "name": st.get("name"),
                "pay_percentage": st.get("pay_percentage"),
                "portal_name": st.get("portal_name"),
                "shift_count": st.get("shift_count", 0),
                "earliest_shift": str(st.get("earliest_shift", "")),
                "latest_shift": str(st.get("latest_shift", "")),
            }
            for st in shift_types
        ],
        "absence_mapping": absence_mapping,
        "mapped_types": mapped_types,
        "has_absence_data": has_absence_data,
    }


def discover_absence_shifts() -> dict:
    """Check if absence-type shifts have matching punchclock entries."""
    print("Discovery: checking absence shifts vs punchclock...")

    result = fetchall("""
        SELECT
            st.name AS shift_type_name,
            COUNT(s.id) AS total_shifts,
            COUNT(pc.id) AS clocked_shifts,
            COUNT(s.id) - COUNT(pc.id) AS unclocked_shifts
        FROM planday.shifts s
        JOIN planday.shift_types st
            ON s.shift_type_id = st.id AND s.portal_name = st.portal_name
        LEFT JOIN planday.punchclock_shifts pc
            ON pc.employee_id = s.employee_id
            AND pc.date = CAST(s.start_date_time AS DATE)
            AND pc.portal_name = s.portal_name
        WHERE st.name ILIKE '%syk%'
           OR st.name ILIKE '%egenmelding%'
           OR st.name ILIKE '%fravær%'
           OR st.name ILIKE '%barn%'
           OR st.name ILIKE '%ferie%'
           OR st.name ILIKE '%permisjon%'
        GROUP BY st.name
        ORDER BY total_shifts DESC
    """)

    return {
        "absence_vs_punchclock": [
            {
                "shift_type": r.get("shift_type_name"),
                "total_shifts": r.get("total_shifts", 0),
                "clocked_shifts": r.get("clocked_shifts", 0),
                "unclocked_shifts": r.get("unclocked_shifts", 0),
            }
            for r in result
        ]
    }


def discover_employee_groups() -> dict:
    """List employee groups for role-based labor analysis."""
    print("Discovery: querying employee_groups...")

    groups = fetchall("""
        SELECT eg.id, eg.name, eg.portal_name,
               COUNT(DISTINCT pc.employee_id) AS employee_count,
               SUM(pc.hours_worked) AS total_hours
        FROM planday.employee_groups eg
        LEFT JOIN planday.punchclock_shifts pc
            ON pc.employee_group_id = eg.id AND pc.portal_name = eg.portal_name
        GROUP BY eg.id, eg.name, eg.portal_name
        ORDER BY total_hours DESC NULLS LAST
    """)

    return {
        "employee_groups": [
            {
                "id": g["id"],
                "name": g.get("name"),
                "portal_name": g.get("portal_name"),
                "employee_count": g.get("employee_count", 0),
                "total_hours": float(g.get("total_hours") or 0),
            }
            for g in groups
        ]
    }


def discover_pay_rates() -> dict:
    """Check pay rate coverage."""
    print("Discovery: checking pay rate coverage...")

    coverage = fetchall("""
        WITH pc_employees AS (
            SELECT DISTINCT employee_id, employee_group_id, portal_name
            FROM planday.punchclock_shifts
        ),
        rate_match AS (
            SELECT pe.*,
                   pr.hourly_rate IS NOT NULL AS has_pay_rate,
                   sal.effective_hourly_rate IS NOT NULL AS has_salary
            FROM pc_employees pe
            LEFT JOIN planday.pay_rates pr
                ON pr.employee_id = pe.employee_id
                AND pr.employee_group_id = pe.employee_group_id
                AND pr.portal_name = pe.portal_name
            LEFT JOIN planday.salaries sal
                ON sal.employee_id = pe.employee_id
                AND sal.portal_name = pe.portal_name
        )
        SELECT
            COUNT(*) AS total_employee_group_combos,
            SUM(CASE WHEN has_pay_rate THEN 1 ELSE 0 END) AS with_pay_rate,
            SUM(CASE WHEN has_salary THEN 1 ELSE 0 END) AS with_salary,
            SUM(CASE WHEN has_pay_rate OR has_salary THEN 1 ELSE 0 END) AS with_any_rate,
            SUM(CASE WHEN NOT has_pay_rate AND NOT has_salary THEN 1 ELSE 0 END) AS without_rate
        FROM rate_match
    """)

    return coverage[0] if coverage else {}


def run_discovery() -> dict:
    """Run full discovery and save report."""
    print("=" * 60)
    print("ANALYTICS DATA DISCOVERY")
    print("=" * 60)

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "status": "completed",
    }

    try:
        report["shift_types"] = discover_shift_types()
        report["absence_shifts"] = discover_absence_shifts()
        report["employee_groups"] = discover_employee_groups()
        report["pay_rate_coverage"] = discover_pay_rates()

        # Summary
        has_absence = report["shift_types"].get("has_absence_data", False)
        mapped_count = len(report["shift_types"].get("mapped_types", []))
        report["summary"] = {
            "has_absence_data": has_absence,
            "absence_types_found": mapped_count,
            "recommendation": (
                "Absence data found — sick leave cubes can be populated."
                if has_absence
                else "No absence data in shifts — sick leave cubes will be created empty."
            ),
        }

        print(f"\nSummary: {'Absence data FOUND' if has_absence else 'No absence data'}")
        print(f"  Mapped {mapped_count} shift types to absence categories")

    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)
        print(f"Discovery failed: {e}")

    # Save report
    ctxe_dir = _find_ctxe_dir()
    report_path = ctxe_dir / "discovery_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to {report_path}")

    return report


def load_discovery_report() -> dict | None:
    """Load existing discovery report, or None if not found."""
    try:
        ctxe_dir = _find_ctxe_dir()
        report_path = ctxe_dir / "discovery_report.json"
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def has_absence_data() -> bool:
    """Check if discovery found absence data."""
    report = load_discovery_report()
    if report is None:
        return False
    return report.get("summary", {}).get("has_absence_data", False)
