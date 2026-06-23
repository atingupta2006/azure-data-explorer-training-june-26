"""Azure CLI helpers — uses az from the active venv when available."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from adx_training_tools.config import tools_root


def _venv_az() -> Path | None:
    root = tools_root()
    for name in ("az.bat", "az.cmd", "az.exe", "az"):
        candidate = root / ".venv" / "Scripts" / name
        if candidate.is_file():
            return candidate
    candidate = root / ".venv" / "bin" / "az"
    if candidate.is_file():
        return candidate
    return None


def _system_az_dir() -> Path | None:
    """Prefer Microsoft Azure CLI2 install over venv shim (consistent login tokens)."""
    for candidate in (
        Path(r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"),
        Path(r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin"),
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ):
        for name in ("az.cmd", "az"):
            if (candidate / name).is_file():
                return candidate
    return None


def ensure_az_on_path() -> None:
    """Put Azure CLI on PATH so AzureCliCredential finds a working az."""
    az_dir: str | None = None
    system = _system_az_dir()
    if system:
        az_dir = str(system)
    else:
        venv_az = _venv_az()
        if venv_az:
            az_dir = str(venv_az.parent)
    if not az_dir:
        return
    path = os.environ.get("PATH", "")
    if az_dir.casefold() not in {p.casefold() for p in path.split(os.pathsep) if p}:
        os.environ["PATH"] = az_dir + os.pathsep + path


def az_executable() -> str:
    venv_az = _venv_az()
    if venv_az:
        return str(venv_az)
    system = shutil.which("az")
    if system:
        return system
    raise FileNotFoundError(
        "Azure CLI not found. Run: cd GH/tools && pip install -e .  (installs azure-cli in .venv)"
    )


def run_az(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [az_executable(), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def load_subscription_id() -> str | None:
    load_dotenv(tools_root() / ".env")
    return os.getenv("AZURE_SUBSCRIPTION_ID", "").strip() or None


def list_subscriptions() -> list[dict[str, Any]]:
    result = run_az("account", "list", "--output", "json")
    return json.loads(result.stdout or "[]")


def show_account() -> dict[str, Any]:
    result = run_az("account", "show", "--output", "json")
    return json.loads(result.stdout or "{}")


def set_subscription(subscription_id: str) -> dict[str, Any]:
    run_az("account", "set", "--subscription", subscription_id)
    return show_account()


def azure_login(
    *,
    use_device_code: bool = False,
    subscription_id: str | None = None,
) -> None:
    """Login via browser or device code. Pass subscription to skip the picker."""
    sub = subscription_id or load_subscription_id()
    cmd = [az_executable(), "login"]
    if use_device_code:
        cmd.append("--use-device-code")
    if sub:
        cmd.extend(["--subscription", sub])
    # Inherit stdin/stdout so device-code prompts work in the terminal
    subprocess.run(cmd, check=True)


def ensure_subscription() -> dict[str, Any]:
    """Set subscription from .env if present; return current account."""
    sub = load_subscription_id()
    if sub:
        return set_subscription(sub)
    return show_account()


_BLOB_INGEST_URI = re.compile(
    r"h'https://([^.]+)\.blob\.core\.windows\.net/([^'?]+)'"
)
_MANAGED_IDENTITY_SUFFIX = re.compile(r";managed_identity=[^;'\"]+", re.IGNORECASE)


def blob_sas_uri(storage_account: str, blob_path: str, *, expiry_hours: int = 8) -> str:
    """Return a read-only SAS URI for a blob (maintainer dry-run when cluster MI is not trusted)."""
    meta = json.loads(
        run_az(
            "storage", "account", "show",
            "--name", storage_account,
            "--query", "{rg:resourceGroup}",
            "-o", "json",
        ).stdout
        or "{}"
    )
    rg = meta.get("rg")
    if not rg:
        raise RuntimeError(f"Storage account not found: {storage_account}")
    key = run_az(
        "storage", "account", "keys", "list",
        "--account-name", storage_account,
        "--resource-group", rg,
        "--query", "[0].value",
        "-o", "tsv",
    ).stdout.strip()
    container, _, blob_name = blob_path.partition("/")
    expiry = (datetime.now(timezone.utc) + timedelta(hours=expiry_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return run_az(
        "storage", "blob", "generate-sas",
        "--account-name", storage_account,
        "--account-key", key,
        "--container-name", container,
        "--name", blob_name,
        "--permissions", "r",
        "--expiry", expiry,
        "--full-uri",
        "-o", "tsv",
    ).stdout.strip()


def ingest_use_managed_identity() -> bool:
    """When true, keep ;managed_identity=system on .ingest URIs (student lab path)."""
    load_dotenv(tools_root() / ".env")
    val = os.getenv("ADX_INGEST_USE_MANAGED_IDENTITY", "true").strip().lower()
    return val not in ("false", "0", "no")


def apply_ingest_blob_sas(text: str, storage_account: str | None) -> str:
    """Attach SAS tokens to blob URIs in .ingest commands for maintainer dry-runs."""
    if ingest_use_managed_identity():
        return text
    if not storage_account or ".ingest" not in text.lower():
        return text

    def _replace(match: re.Match[str]) -> str:
        account, blob_path = match.group(1), match.group(2)
        if account.casefold() != storage_account.casefold():
            return match.group(0)
        blob_path = _MANAGED_IDENTITY_SUFFIX.sub("", blob_path)
        sas = blob_sas_uri(storage_account, blob_path)
        return f"h'{sas}'"

    return _BLOB_INGEST_URI.sub(_replace, text)


def subscription_report() -> dict[str, Any]:
    try:
        accounts = list_subscriptions()
    except subprocess.CalledProcessError as exc:
        return {
            "pass": False,
            "error": (exc.stderr or exc.stdout or str(exc)).strip(),
            "hint": "Run: adx-tools azure-login  (interactive browser login)",
        }
    except FileNotFoundError as exc:
        return {"pass": False, "error": str(exc)}

    current: dict[str, Any] | None = None
    try:
        current = show_account()
    except subprocess.CalledProcessError:
        current = None

    configured = load_subscription_id()
    return {
        "pass": True,
        "az_path": az_executable(),
        "configured_subscription_id": configured,
        "current_account": current,
        "subscriptions": [
            {
                "name": a.get("name"),
                "id": a.get("id"),
                "state": a.get("state"),
                "isDefault": a.get("isDefault"),
            }
            for a in accounts
        ],
    }
