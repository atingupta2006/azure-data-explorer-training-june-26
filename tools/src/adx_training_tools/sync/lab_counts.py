"""Sync locked lab counts in student materials from a data profile."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from adx_training_tools.config import Profile, find_gh_root, load_profile


def _af(profile: Profile) -> dict[str, int]:
    return profile.auth_failure_breakdown.model_dump()


def build_count_map(baseline: Profile, target: Profile) -> dict[int, int]:
    bc, tc = baseline.counts, target.counts
    baf, taf = _af(baseline), _af(target)
    mapping: dict[int, int] = {}
    for field in bc.model_fields:
        bv = getattr(bc, field)
        tv = getattr(tc, field)
        if bv != tv:
            mapping[bv] = tv
    for key in baf:
        if baf[key] != taf[key]:
            mapping[baf[key]] = taf[key]
    mapping[bc.bronze_batch + bc.eventhub] = tc.bronze_batch + tc.eventhub
    return mapping


def apply_bold_count_map(text: str, count_map: dict[int, int]) -> str:
    def repl(match: re.Match[str]) -> str:
        n = int(match.group(1))
        if n in count_map:
            return f"**{count_map[n]}**"
        return match.group(0)

    return re.sub(r"\*\*(\d+)\*\*", repl, text)


def apply_plain_count_phrases(text: str, baseline: Profile, target: Profile) -> str:
    """Replace known baseline phrases with target counts (exact strings only)."""
    bc, tc = baseline.counts, target.counts
    pairs: list[tuple[str, str]] = [
        (f"PracticeSecurityEvents | count` = **{bc.practice_security_events}**",
         f"PracticeSecurityEvents | count` = **{tc.practice_security_events}**"),
        (f"Load **{bc.practice_security_events}** synthetic", f"Load **{tc.practice_security_events}** synthetic"),
        (f"AuthFailure = **{bc.auth_failure_silver}**", f"AuthFailure = **{tc.auth_failure_silver}**"),
        (f"JSON rows = **{bc.bronze_json}**", f"JSON rows = **{tc.bronze_json}**"),
        (f"CSV rows = **{bc.bronze_csv}**", f"CSV rows = **{tc.bronze_csv}**"),
        (f"Total Bronze = **{bc.bronze_batch}**", f"Total Bronze = **{tc.bronze_batch}**"),
        (f"Bronze = **{bc.bronze_total}**", f"Bronze = **{tc.bronze_total}**"),
        (f"Silver = **{bc.silver}**", f"Silver = **{tc.silver}**"),
        (f"EventHub = **{bc.eventhub}**", f"EventHub = **{tc.eventhub}**"),
        (f"sum(EventCount) = **{bc.gold_sum_event_count}**", f"sum(EventCount) = **{tc.gold_sum_event_count}**"),
        (f"SecLogsRaw ({bc.bronze_batch} batch rows)", f"SecLogsRaw ({tc.bronze_batch} batch rows)"),
        (f"+{bc.eventhub} Event Hub stream", f"+{tc.eventhub} Event Hub stream"),
        (f"+{bc.iot} IoT Hub stream", f"+{tc.iot} IoT Hub stream"),
        (f"**+{bc.eventhub + bc.iot}** streaming rows", f"**+{tc.eventhub + bc.iot}** streaming rows"),
        (f"**{bc.source_systems}** values, rows sum **{bc.silver}**",
         f"**{tc.source_systems}** values, rows sum **{tc.silver}**"),
    ]
    for old, new in pairs:
        if old != new:
            text = text.replace(old, new)
    c = tc
    text = re.sub(
        r"expected: total \d+, IoT \d+",
        f"expected: total {c.bronze_total}, IoT {c.iot}",
        text,
    )
    return text


def _sync_layout_comments(text: str, target: Profile) -> str:
    c = target.counts
    subs = [
        ("# 15 NDJSON", f"# {c.bronze_json} NDJSON"),
        ("# 1500 NDJSON", f"# {c.bronze_json} NDJSON"),
        ("# 10 rows + header", f"# {c.bronze_csv} rows + header"),
        ("# 1000 rows + header", f"# {c.bronze_csv} rows + header"),
        ("# same 10 rows", f"# same {c.bronze_csv} rows"),
        ("# same 1000 rows", f"# same {c.bronze_csv} rows"),
        ("# 5 NDJSON — Day 3 Lab 2", f"# {c.eventhub} NDJSON — Day 3 Lab 2"),
        ("# 500 NDJSON — Day 3 Lab 2", f"# {c.eventhub} NDJSON — Day 3 Lab 2"),
        ("# 5 NDJSON — Day 3 Lab 3", f"# {c.iot} NDJSON — Day 3 Lab 3"),
        ("# 500 NDJSON — Day 3 Lab 3", f"# {c.iot} NDJSON — Day 3 Lab 3"),
    ]
    for old, new in subs:
        text = text.replace(old, new)
    text = re.sub(
        r"\*\*\d+\*\* rows \(\d+ JSON \+ \d+ CSV",
        f"**{c.bronze_batch}** rows ({c.bronze_json} JSON + {c.bronze_csv} CSV",
        text,
        count=1,
    )
    return text


def _glob_targets(root: Path) -> list[Path]:
    patterns = [
        "data/README.md",
        "day-*/labs.md",
        "day-*/README.md",
    ]
    files: list[Path] = []
    for pat in patterns:
        files.extend(root.glob(pat))
    return sorted(set(files))


def _transform_file(path: Path, count_map: dict[int, int], baseline: Profile, target: Profile) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    text = apply_bold_count_map(text, count_map)
    text = apply_plain_count_phrases(text, baseline, target)
    if path.name == "README.md" and "data" in path.parts:
        text = _sync_layout_comments(text, target)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def sync_lab_counts(
    target_profile: str = "heavy-100x",
    baseline_profile: str = "lab-baseline",
) -> dict[str, Any]:
    baseline = load_profile(baseline_profile)
    target = load_profile(target_profile)
    count_map = build_count_map(baseline, target)
    root = find_gh_root()
    updated: list[str] = []

    for path in _glob_targets(root):
        if _transform_file(path, count_map, baseline, target):
            updated.append(str(path.relative_to(root)))

    lab_yaml = root / "tools" / "profiles" / "lab.yaml"
    if lab_yaml.is_file():
        import yaml

        data = yaml.safe_load(lab_yaml.read_text(encoding="utf-8"))
        data["counts"] = target.counts.model_dump()
        data["auth_failure_breakdown"] = target.auth_failure_breakdown.model_dump()
        data["json_event_types"] = target.json_event_types
        data["eventhub_event_types"] = target.eventhub_event_types
        data["scale_factor"] = target.scale_factor
        data.setdefault("paths", {})["bronze_ndjson"] = "bronze/sec-web-logs.ndjson"
        lab_yaml.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        updated.append(str(lab_yaml.relative_to(root)))

    return {
        "baseline": baseline_profile,
        "target": target_profile,
        "count_map": {str(k): v for k, v in count_map.items()},
        "files_updated": len(updated),
        "updated_paths": updated,
        "counts": target.counts.model_dump(),
    }


def promote_data(
    source_profile: str = "heavy-100x",
    dest_dir: str = "data",
) -> dict[str, Any]:
    """Copy generated files from profile data_dir to student data/."""
    import shutil

    source = load_profile(source_profile)
    dest_root = find_gh_root() / dest_dir
    copied: list[str] = []

    for key in ("bronze_json", "bronze_csv", "bronze_ndjson", "eventhub", "iot"):
        if key not in source.paths:
            continue
        src = source.file_path(key)
        if not src.is_file():
            continue
        rel = source.paths[key]
        dst = dest_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)

    return {"source_profile": source_profile, "dest": str(dest_root), "copied": copied}
