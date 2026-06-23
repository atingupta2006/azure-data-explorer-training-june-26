"""Orchestrate full data generation and manifest."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adx_training_tools.config import Profile, load_profile
from adx_training_tools.generators.bronze import generate_bronze
from adx_training_tools.generators.events import generate_eventhub, generate_iot
from adx_training_tools.generators.practice import generate_practice_seed


def _count_ndjson_event_types(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not path.is_file():
        return counts
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        counts[obj.get("EventType", "UNKNOWN")] += 1
    return counts


def generate_all(profile_name: str = "heavy-10x") -> dict[str, Any]:
    profile = load_profile(profile_name)
    profile.data_path.mkdir(parents=True, exist_ok=True)

    paths = {
        "iot": str(generate_iot(profile)),
        "eventhub": str(generate_eventhub(profile)),
    }
    paths.update({k: str(v) for k, v in generate_bronze(profile).items()})
    paths["practice_seed"] = str(generate_practice_seed(profile))

    iot_path = profile.file_path("iot")
    eh_path = profile.file_path("eventhub")
    json_path = profile.file_path("bronze_json")
    ndjson_path = profile.file_path("bronze_ndjson") if "bronze_ndjson" in profile.paths else None

    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile_name,
        "scale_factor": profile.scale_factor,
        "paths": paths,
        "counts": {
            "iot": profile.counts.iot,
            "eventhub": profile.counts.eventhub,
            "bronze_json": profile.counts.bronze_json,
            "bronze_csv": profile.counts.bronze_csv,
            "bronze_ndjson": profile.counts.bronze_csv,
            "bronze_batch": profile.counts.bronze_batch,
            "bronze_total": profile.counts.bronze_total,
            "practice_security_events": profile.counts.practice_security_events,
        },
        "file_sizes_mb": {
            k: round(Path(v).stat().st_size / (1024 * 1024), 2)
            for k, v in paths.items()
            if Path(v).is_file()
        },
        "event_type_breakdown": {
            "iot": dict(_count_ndjson_event_types(iot_path)),
            "eventhub": dict(_count_ndjson_event_types(eh_path)),
            "bronze_json": dict(_count_ndjson_event_types(json_path)),
        },
    }

    manifest_path = profile.data_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest
