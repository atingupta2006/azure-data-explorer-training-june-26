"""Generate Day 01 PracticeSecurityEvents seed KQL from profile counts."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from adx_training_tools.config import Profile, find_gh_root, load_profile

SEED = 20260610

EVENT_TYPES = [
    ("AuthFailure", "High", "Failed login after 3 attempts"),
    ("AuthSuccess", "Low", "Login successful"),
    ("FirewallDeny", "Medium", "Blocked inbound TCP/22"),
    ("FirewallAllow", "Low", "Allowed HTTPS to API gateway"),
    ("VPNLogin", "Low", "VPN session started"),
    ("ConfigChange", "High", "Firewall rule modified"),
    ("PrivilegeEscalation", "Critical", "sudo to root on SCADA host"),
    ("VPNLogout", "Low", "VPN session ended"),
]

FACILITIES = ["Substation-A", "Substation-B", "Corporate-VPN", "DMZ-Firewall", "SCADA-Gateway"]


def _build_rows(profile: Profile) -> list[tuple]:
    rng = random.Random(SEED + profile.scale_factor)
    base = datetime(2026, 6, 10, 8, 0, 0, tzinfo=timezone.utc)
    n = profile.counts.practice_security_events
    rows: list[tuple] = []

    quotas = {
        "AuthFailure": profile.counts.auth_failure_day1,
        "FirewallDeny": profile.counts.firewall_deny_day1,
    }
    assigned = sum(quotas.values())
    remaining = max(0, n - assigned)
    per_other = max(1, remaining // max(1, len(EVENT_TYPES) - 2))

    type_counts: dict[str, int] = dict(quotas)
    for et, _, _ in EVENT_TYPES:
        if et not in type_counts:
            type_counts[et] = 0
    for et, _, _ in EVENT_TYPES:
        if et not in quotas:
            type_counts[et] = per_other

    # Normalize to exact n
    total = sum(type_counts.values())
    while total > n:
        for k in list(type_counts):
            if type_counts[k] > 1 and total > n:
                type_counts[k] -= 1
                total -= 1
    while total < n:
        type_counts["AuthSuccess"] = type_counts.get("AuthSuccess", 0) + 1
        total += 1

    i = 0
    for et, sev, msg in EVENT_TYPES:
        for _ in range(type_counts.get(et, 0)):
            ts = base + timedelta(minutes=i, seconds=rng.randint(0, 59))
            ip = f"10.20.{1 + (i % 5)}.{1 + (i % 200)}"
            host = "scada-gw.utility.local" if i % 3 else "vpn.utility.local"
            user = "operator@utility.com" if i % 2 else "field@utility.com"
            fac = FACILITIES[i % len(FACILITIES)]
            rows.append(
                (
                    f'datetime({ts.strftime("%Y-%m-%dT%H:%M:%SZ")})',
                    f'"{et}"',
                    f'"{ip}"',
                    f'"{host}"',
                    f'"{user}"',
                    f'"{sev}"',
                    f'"{msg}"',
                    f'"{fac}"',
                )
            )
            i += 1

    return rows[:n]


def generate_practice_seed(profile: Profile | None = None) -> Path:
    profile = profile or load_profile("lab")
    rows = _build_rows(profile)
    n = len(rows)
    out = find_gh_root() / "day-01" / "queries" / "03-seed-practice-data.kql"

    lines = [
        f"// Day 01 — Seed practice data ({n} rows)",
        "// Database: LogsDB_u01 (select in Web UI before running)",
        f"// .set-or-replace reloads all rows — re-run for a clean {n}-row dataset",
        "",
        ".set-or-replace PracticeSecurityEvents <|",
        "datatable(Timestamp:datetime, EventType:string, SourceIP:string, DestinationHost:string, UserPrincipal:string, Severity:string, Message:string, Facility:string)",
        "[",
    ]
    for r in rows:
        lines.append(f"    {r[0]}, {r[1]}, {r[2]}, {r[3]}, {r[4]}, {r[5]}, {r[6]}, {r[7]},")
    lines[-1] = lines[-1].rstrip(",")
    lines.extend(
        [
            "]",
            "",
            "// Verification",
            "PracticeSecurityEvents",
            "| summarize RowCount = count(), EventTypes = dcount(EventType) by EventType",
            "| order by EventType asc",
            "",
            "PracticeSecurityEvents",
            "| count",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
