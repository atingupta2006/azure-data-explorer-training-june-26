"""Azure Data Explorer query client."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from azure.identity import AzureCliCredential, ChainedTokenCredential, DefaultAzureCredential
    from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
except ImportError as exc:  # pragma: no cover
    raise ImportError("Install azure-kusto-data and azure-identity") from exc


def _adx_credential():
    """Prefer `az login` (system CLI); fallback excludes shared MSA token cache."""
    from adx_training_tools.azure_cli import ensure_az_on_path

    ensure_az_on_path()
    return ChainedTokenCredential(
        AzureCliCredential(),
        DefaultAzureCredential(
            exclude_cli_credential=True,
            exclude_shared_token_cache_credential=True,
            exclude_interactive_browser_credential=False,
        ),
    )


@dataclass
class AdxConfig:
    cluster_uri: str
    database: str

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "AdxConfig":
        tools = Path(__file__).resolve().parents[3]
        load_dotenv(tools / ".env")
        if env_path:
            load_dotenv(env_path)
        uri = os.getenv("ADX_CLUSTER_URI", "").strip()
        db = os.getenv("ADX_DATABASE", "LogsDB_u01").strip()
        if not uri:
            raise ValueError(
                "ADX_CLUSTER_URI not set. Copy tools/.env.example to tools/.env and configure."
            )
        return cls(cluster_uri=uri, database=db)


class AdxClient:
    def __init__(self, config: AdxConfig | None = None) -> None:
        self.config = config or AdxConfig.from_env()
        credential = _adx_credential()
        kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
            self.config.cluster_uri,
            credential,
        )
        self._client = KustoClient(kcsb)

    def test_connection(self) -> dict[str, Any]:
        """Lightweight connectivity check (no lab tables required)."""
        rows = self.execute(".show tables | project TableName | take 5")
        return {
            "cluster": self.config.cluster_uri,
            "database": self.config.database,
            "sample_tables": [r.get("TableName") for r in rows],
            "ok": True,
        }

    def execute(self, query: str) -> list[dict[str, Any]]:
        """Run KQL and return primary result as list of row dicts."""
        response = self._client.execute(self.config.database, query)
        table = response.primary_results[0]
        columns = [c.column_name for c in table.columns]
        rows: list[dict[str, Any]] = []
        for row in table:
            rows.append(dict(zip(columns, row)))
        return rows

    def scalar(self, query: str, column: str | None = None) -> Any:
        rows = self.execute(query)
        if not rows:
            return None
        if column:
            return rows[0].get(column)
        return next(iter(rows[0].values()))
