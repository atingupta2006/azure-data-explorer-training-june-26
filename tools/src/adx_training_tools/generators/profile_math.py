"""Scale a baseline profile by factor or target file size."""

from __future__ import annotations

from adx_training_tools.config import AuthFailureBreakdown, Profile, ProfileCounts, load_profile


def scale_profile(baseline_name: str, factor: int) -> Profile:
    """Return a new Profile with all counts scaled by factor (event-type quotas too)."""
    base = load_profile(baseline_name)
    c = base.counts

    def mul(n: int) -> int:
        return n * factor

    counts = ProfileCounts(
        practice_security_events=min(mul(c.practice_security_events), 5000),
        auth_failure_day1=mul(c.auth_failure_day1),
        firewall_deny_day1=mul(c.firewall_deny_day1),
        bronze_json=mul(c.bronze_json),
        bronze_csv=mul(c.bronze_csv),
        bronze_batch=mul(c.bronze_batch),
        eventhub=mul(c.eventhub),
        iot=mul(c.iot),
        bronze_total=mul(c.bronze_total),
        silver=mul(c.silver),
        auth_failure_silver=mul(c.auth_failure_silver),
        source_systems=c.source_systems,
        threat_intel=c.threat_intel,
        gold_sum_event_count=mul(c.gold_sum_event_count),
        rls_demo=c.rls_demo,
    )
    af = base.auth_failure_breakdown
    breakdown = AuthFailureBreakdown(
        batch_json=mul(af.batch_json),
        batch_csv=mul(af.batch_csv),
        eventhub=mul(af.eventhub),
        iot=mul(af.iot),
    )
    return base.model_copy(
        update={
            "name": f"scaled-{factor}x",
            "scale_factor": factor,
            "counts": counts,
            "auth_failure_breakdown": breakdown,
            "eventhub_event_types": {k: mul(v) for k, v in base.eventhub_event_types.items()},
            "json_event_types": {k: mul(v) for k, v in base.json_event_types.items()},
        }
    )


def profile_from_target_json_rows(
    baseline_name: str,
    json_rows: int,
    *,
    name: str = "custom",
    data_dir: str = "data-heavy",
) -> Profile:
    """Build profile preserving baseline ratios with json_rows as bronze_json count."""
    base = load_profile(baseline_name)
    factor = max(1, json_rows // base.counts.bronze_json)
    p = scale_profile(baseline_name, factor)
    return p.model_copy(update={"name": name, "data_dir": data_dir})
