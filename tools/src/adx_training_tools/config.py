"""Paths and profile loading for ADX training repo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def find_gh_root(start: Path | None = None) -> Path:
    """Walk up from tools/ to GH/ (contains data/ and day-01/)."""
    current = (start or Path(__file__)).resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").is_dir() and (parent / "day-01").is_dir():
            return parent
        if parent.name == "GH" and (parent / "data").is_dir():
            return parent
    raise FileNotFoundError("Could not locate GH root (expected data/ and day-01/)")


def tools_root() -> Path:
    return find_gh_root() / "tools"


class ProfileCounts(BaseModel):
    practice_security_events: int = 20
    auth_failure_day1: int = 4
    firewall_deny_day1: int = 5
    bronze_json: int = 15
    bronze_csv: int = 10
    bronze_batch: int = 25
    eventhub: int = 5
    iot: int = 5
    bronze_total: int = 35
    silver: int = 35
    auth_failure_silver: int = 7
    source_systems: int = 4
    threat_intel: int = 8
    gold_sum_event_count: int = 35
    environment_ref: int = 4
    rls_demo: int = 10


class AuthFailureBreakdown(BaseModel):
    batch_json: int = 3
    batch_csv: int = 2
    eventhub: int = 2
    iot: int = 0


class Profile(BaseModel):
    name: str
    description: str = ""
    scale_factor: int = 1
    data_dir: str = "data"
    base_profile: str | None = None
    paths: dict[str, str] = Field(default_factory=dict)
    counts: ProfileCounts
    auth_failure_breakdown: AuthFailureBreakdown = Field(default_factory=AuthFailureBreakdown)
    eventhub_event_types: dict[str, int] = Field(default_factory=dict)
    json_event_types: dict[str, int] = Field(default_factory=dict)

    @property
    def data_path(self) -> Path:
        return find_gh_root() / self.data_dir

    def file_path(self, key: str) -> Path:
        rel = self.paths.get(key)
        if not rel:
            raise KeyError(f"Unknown path key: {key}")
        return self.data_path / rel


def load_profile(name: str = "lab") -> Profile:
    path = tools_root() / "profiles" / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Profile not found: {path}")
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Profile.model_validate(raw)


def reports_dir() -> Path:
    d = tools_root() / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def write_json_report(name: str, payload: dict[str, Any]) -> Path:
    out = reports_dir() / name
    out.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    return out
