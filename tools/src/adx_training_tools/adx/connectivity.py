"""ADX connectivity probe with actionable errors."""

from __future__ import annotations

import socket
from typing import Any
from urllib.parse import urlparse


def _cluster_host_unreachable(cluster_uri: str) -> str | None:
    host = urlparse(cluster_uri).hostname
    if not host:
        return "ADX_CLUSTER_URI is missing a hostname"
    try:
        socket.getaddrinfo(host, 443)
    except OSError:
        return host
    return None


def test_adx_connection() -> dict[str, Any]:
    try:
        from adx_training_tools.adx.client import AdxClient
        from adx_training_tools.azure_cli import ensure_subscription, load_subscription_id

        sub_info: dict[str, Any] = {}
        if load_subscription_id():
            try:
                sub_info = ensure_subscription()
            except Exception as sub_exc:  # noqa: BLE001
                return {
                    "pass": False,
                    "error": str(sub_exc),
                    "hint": "Run adx-tools azure-login then adx-tools azure-set-subscription <id>",
                }

        from adx_training_tools.adx.client import AdxConfig

        config = AdxConfig.from_env()
        unreachable = _cluster_host_unreachable(config.cluster_uri)
        if unreachable:
            return {
                "pass": False,
                "error": f"Cannot resolve cluster hostname: {unreachable}",
                "cluster": config.cluster_uri,
                "hint": (
                    "The ADX cluster is not provisioned yet, or ADX_CLUSTER_URI is wrong. "
                    "Create the cluster in Azure Portal (see GH/docs/adx-workspace-setup.md), "
                    "wait until status is Running, then update .env with the correct URI."
                ),
            }

        client = AdxClient(config)
        info = client.test_connection()
        out: dict[str, Any] = {"pass": True, **info}
        if sub_info:
            out["subscription"] = {
                "name": sub_info.get("name"),
                "id": sub_info.get("id"),
            }
        return out
    except ValueError as exc:
        return {
            "pass": False,
            "error": str(exc),
            "hint": "Copy GH/tools/.env.example to GH/tools/.env and set ADX_CLUSTER_URI.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "pass": False,
            "error": str(exc),
            "hint": (
                "Sign in to Azure (az login, VS Code Azure Account, or set "
                "AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET). "
                "Confirm cluster exists and your account has query permission."
            ),
        }
