"""MCP server exposing ADX training maintainer tools."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from adx_training_tools.config import load_profile, write_json_report
from adx_training_tools.generators.orchestrator import generate_all
from adx_training_tools.validators.data_files import validate_data_files
from adx_training_tools.validators.kql_inventory import validate_kql_inventory
from adx_training_tools.validators.materials import validate_materials

mcp = FastMCP(
    "adx-training-tools",
    instructions=(
        "Tools for Azure Data Explorer TCS training: validate materials, "
        "run live lab KQL on ADX, checkpoints, and full course dry-run."
    ),
)


@mcp.tool()
def validate_all_materials(day: int | None = None) -> str:
    """Run materials + KQL inventory validators. Optional day 1-5."""
    results = {
        "materials": validate_materials(day=day),
        "kql": validate_kql_inventory(day=day),
    }
    results["pass"] = results["materials"]["pass"] and results["kql"]["pass"]
    write_json_report("mcp-validate-materials.json", results)
    return json.dumps(results, indent=2)


@mcp.tool()
def validate_day(day: int) -> str:
    """Validate README, labs.md, and query references for one day (1-5)."""
    if day < 1 or day > 5:
        return json.dumps({"pass": False, "error": "day must be 1-5"})
    results = {
        "materials": validate_materials(day=day),
        "kql": validate_kql_inventory(day=day),
        "data_lab": validate_data_files("lab"),
    }
    results["pass"] = all(
        results[k]["pass"] for k in ("materials", "kql", "data_lab")
    )
    return json.dumps(results, indent=2)


@mcp.tool()
def generate_data(profile: str = "heavy-10x") -> str:
    """Regenerate dataset files (default heavy-10x = 10x lab scale)."""
    manifest = generate_all(profile)
    return json.dumps(manifest, indent=2)


@mcp.tool()
def verify_data_profile(profile: str = "lab") -> str:
    """Verify on-disk data file row counts match profile YAML."""
    result = validate_data_files(profile)
    return json.dumps(result, indent=2)


@mcp.tool()
def list_checkpoints(profile: str = "lab") -> str:
    """Return locked checkpoint count expectations for a profile."""
    p = load_profile(profile)
    return json.dumps(
        {
            "profile": profile,
            "scale_factor": p.scale_factor,
            "counts": p.counts.model_dump(),
            "eventhub_event_types": p.eventhub_event_types,
            "json_event_types": p.json_event_types,
        },
        indent=2,
    )


@mcp.tool()
def lab_plan_inventory() -> str:
    """List all lab steps in execution order (static, no Azure)."""
    from adx_training_tools.adx.lab_runner import lab_plan_inventory as inventory

    return json.dumps(inventory(), indent=2)


@mcp.tool()
def azure_login(use_device_code: bool = True) -> str:
    """Azure login via device code (recommended) or browser. Uses subscription from .env."""
    from adx_training_tools.azure_cli import azure_login as do_login

    do_login(use_device_code=use_device_code)
    return json.dumps({"pass": True, "message": "Login complete"})


@mcp.tool()
def azure_list_subscriptions() -> str:
    """List Azure subscriptions and current account."""
    from adx_training_tools.azure_cli import subscription_report

    result = subscription_report()
    write_json_report("mcp-azure-subscriptions.json", result)
    return json.dumps(result, indent=2)


@mcp.tool()
def azure_set_subscription(subscription_id: str) -> str:
    """Set active Azure subscription."""
    from adx_training_tools.azure_cli import set_subscription

    account = set_subscription(subscription_id)
    return json.dumps(account, indent=2)


@mcp.tool()
def adx_test_connection() -> str:
    """Test ADX connectivity (.show databases). Needs .env + Azure login."""
    from adx_training_tools.adx.connectivity import test_adx_connection

    result = test_adx_connection()
    write_json_report("mcp-adx-connection.json", result)
    return json.dumps(result, indent=2)


@mcp.tool()
def adx_reset_database() -> str:
    """Drop lab tables (clean state) using 00-reset-logsdb.kql."""
    from adx_training_tools.adx.lab_runner import run_reset

    result = run_reset()
    write_json_report("mcp-adx-reset.json", result)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def adx_run_checkpoints(profile: str = "lab", day: int | None = None) -> str:
    """Execute ADX checkpoint KQL vs profile."""
    from adx_training_tools.adx.dry_run import run_checkpoints

    result = run_checkpoints(profile_name=profile, day=day)
    write_json_report("mcp-adx-checkpoints.json", result)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def adx_dry_run_day(day: int) -> str:
    """Run all KQL statements in every query file for a training day."""
    from adx_training_tools.adx.dry_run import dry_run_day_queries

    result = dry_run_day_queries(day=day)
    write_json_report(f"mcp-adx-dry-run-day{day:02d}.json", result)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def adx_run_lab_file(file_path: str) -> str:
    """Execute all KQL statements in one lab .kql file."""
    from pathlib import Path

    from adx_training_tools.adx.lab_runner import run_lab_file

    result = run_lab_file(Path(file_path))
    write_json_report("mcp-adx-run-lab-file.json", result)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def adx_run_full_course(
    day: int | None = None,
    reset_first: bool = False,
    profile: str = "lab",
) -> str:
    """Run ordered lab plan (all days or one day) with per-day checkpoints."""
    from adx_training_tools.adx.lab_runner import run_lab_plan

    result = run_lab_plan(
        day=day,
        profile_name=profile,
        reset_first=reset_first,
        checkpoint_after_day=True,
    )
    write_json_report(
        f"mcp-adx-run-course-{'day'+str(day) if day else 'full'}.json", result
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def search_ms_learn_docs(query: str, topic: str | None = None, n_results: int = 8) -> str:
    """Semantic search Microsoft Learn ADX/Kusto docs (requires docs index crawl)."""
    from adx_training_tools.docs.search import search_docs

    return json.dumps(search_docs(query, n_results=n_results, topic=topic), indent=2)


@mcp.tool()
def verify_student_learn_links(day: int | None = None) -> str:
    """Verify learn.microsoft.com links in student hands-on markdown (HTTP check)."""
    from adx_training_tools.docs.verify_links import verify_markdown_links

    result = verify_markdown_links(day=day)
    write_json_report("mcp-docs-verify-links.json", result)
    return json.dumps(result, indent=2)


@mcp.tool()
def crawl_ms_learn_docs(reset: bool = False, max_pages: int = 120) -> str:
    """Crawl curated Learn seeds into ChromaDB vector index (maintainer)."""
    from adx_training_tools.docs.index import build_index

    manifest = build_index(reset=reset, max_pages=max_pages)
    write_json_report("mcp-docs-crawl.json", manifest)
    return json.dumps(manifest, indent=2)


def run_server() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
