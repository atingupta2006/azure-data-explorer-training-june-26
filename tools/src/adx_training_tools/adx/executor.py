"""Execute individual KQL statements against ADX."""

from __future__ import annotations

import os
import re
import time
from typing import Any

from dotenv import load_dotenv

from adx_training_tools.adx.client import AdxClient
from adx_training_tools.adx.kql_parser import KqlStatement, apply_env_substitutions
from adx_training_tools.azure_cli import apply_ingest_blob_sas
from adx_training_tools.config import tools_root

_CREATE_DB = re.compile(r"^\.create\s+database\s+(\S+)", re.IGNORECASE)


def load_run_config() -> dict[str, str | int | bool | None]:
    load_dotenv(tools_root() / ".env")
    return {
        "storage_account": os.getenv("ADX_STORAGE_ACCOUNT", "").strip() or None,
        "use_fallback": os.getenv("ADX_USE_STREAMING_FALLBACK", "true").lower() != "false",
        "mv_wait_seconds": int(os.getenv("ADX_MV_WAIT_SECONDS", "45")),
        "ingest_wait_seconds": int(os.getenv("ADX_INGEST_WAIT_SECONDS", "45")),
        "ingest_use_managed_identity": os.getenv(
            "ADX_INGEST_USE_MANAGED_IDENTITY", "true"
        ).strip().lower()
        not in ("false", "0", "no"),
    }


def execute_statement(
    client: AdxClient,
    stmt: KqlStatement,
    database: str,
    storage_account: str | None,
) -> dict[str, Any]:
    text = apply_env_substitutions(stmt.text, database, storage_account)
    text = apply_ingest_blob_sas(text, storage_account)
    if stmt.has_placeholder and "<storage-account>" in text and not storage_account:
        return {
            "pass": True,
            "skipped": "ADX_STORAGE_ACCOUNT not set — .ingest skipped",
            "statement_index": stmt.index,
            "kind": stmt.kind.value,
        }
    create_match = _CREATE_DB.match(text.strip())
    if create_match:
        db_name = create_match.group(1).strip("'\"[]")
        try:
            exists = client.scalar(
                f".show databases | where DatabaseName == '{db_name}' | count",
                "Count",
            )
            if exists and int(exists) > 0:
                return {
                    "pass": True,
                    "skipped": f"database {db_name} already exists",
                    "statement_index": stmt.index,
                    "kind": stmt.kind.value,
                }
        except Exception:
            pass
    try:
        rows = client.execute(text)
        out: dict[str, Any] = {
            "pass": True,
            "statement_index": stmt.index,
            "kind": stmt.kind.value,
            "row_count": len(rows),
            "sample": rows[:2],
        }
        if text.lstrip().lower().startswith(".ingest"):
            wait = int(os.getenv("ADX_INGEST_WAIT_SECONDS", "45"))
            time.sleep(wait)
            out["ingest_wait_seconds"] = wait
        return out
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        if (
            stmt.text.lstrip().lower().startswith(".create database")
            and "already exists" in err.lower()
        ):
            return {
                "pass": True,
                "skipped": "database already exists",
                "statement_index": stmt.index,
                "kind": stmt.kind.value,
            }
        return {
            "pass": False,
            "statement_index": stmt.index,
            "kind": stmt.kind.value,
            "error": err,
            "query_preview": text[:200],
        }
