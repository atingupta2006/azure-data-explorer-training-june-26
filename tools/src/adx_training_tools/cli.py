"""Command-line interface for ADX training tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from adx_training_tools.config import load_profile, reports_dir, write_json_report
from adx_training_tools.generators.orchestrator import generate_all
from adx_training_tools.validators.data_files import validate_data_files
from adx_training_tools.validators.kql_inventory import validate_kql_inventory
from adx_training_tools.validators.materials import validate_materials


@click.group()
def main() -> None:
    """ADX Training Tools — data, validation, ADX dry-run."""


@main.command("generate")
@click.option("--profile", default="heavy-100x", help="Profile name (lab | heavy-100x | training-2gb)")
def generate_cmd(profile: str) -> None:
    """Generate data files for the given profile."""
    manifest = generate_all(profile)
    click.echo(json.dumps(manifest, indent=2))
    click.echo(f"\nWrote manifest: {manifest['manifest_path']}")


@main.command("sync-lab-counts")
@click.option("--profile", default="heavy-100x", help="Target profile counts for labs/materials")
@click.option("--baseline", default="lab-baseline", show_default=True)
def sync_lab_counts_cmd(profile: str, baseline: str) -> None:
    """Update labs, READMEs, KQL comments, and lab.yaml from profile counts."""
    from adx_training_tools.sync.lab_counts import sync_lab_counts

    result = sync_lab_counts(target_profile=profile, baseline_profile=baseline)
    click.echo(json.dumps(result, indent=2))


@main.command("promote-data")
@click.option("--profile", default="heavy-100x", help="Source profile (data_dir to copy from)")
@click.option("--dest", default="data", show_default=True, help="Destination under GH/")
def promote_data_cmd(profile: str, dest: str) -> None:
    """Copy generated profile files into student data/ folder."""
    from adx_training_tools.sync.lab_counts import promote_data

    result = promote_data(source_profile=profile, dest_dir=dest)
    click.echo(json.dumps(result, indent=2))


@main.command("build-training-data")
@click.option(
    "--profile",
    default="heavy-100x",
    show_default=True,
    help="heavy-100x (~3.5k rows) or training-2gb (multi-GB batch files)",
)
@click.option("--baseline", default="lab-baseline", show_default=True)
@click.option("--no-promote", is_flag=True, help="Generate only; do not copy to data/")
@click.option("--no-sync", is_flag=True, help="Skip lab/material count updates")
def build_training_data_cmd(profile: str, baseline: str, no_promote: bool, no_sync: bool) -> None:
    """Generate data, sync lab counts, and promote to GH/data/."""
    from adx_training_tools.sync.lab_counts import promote_data, sync_lab_counts

    click.echo(f"Generating profile: {profile}")
    manifest = generate_all(profile)
    click.echo(json.dumps({k: manifest[k] for k in ("profile", "counts", "file_sizes_mb")}, indent=2))

    if not no_sync:
        click.echo("\nSyncing lab counts...")
        sync_result = sync_lab_counts(target_profile=profile, baseline_profile=baseline)
        click.echo(f"Updated {sync_result['files_updated']} files")

    if not no_promote:
        click.echo("\nPromoting to GH/data/ ...")
        promo = promote_data(source_profile=profile, dest_dir="data")
        click.echo(json.dumps(promo, indent=2))

    click.echo("\nDone. Run: adx-tools validate data --profile lab")


@main.command("validate")
@click.argument("target", type=click.Choice(["materials", "data", "kql", "all"]))
@click.option("--profile", default="lab", help="Data profile for data validation")
@click.option("--day", type=int, default=None, help="Limit to day N (1-7)")
@click.option("--report", is_flag=True, help="Write JSON report to tools/reports/")
def validate_cmd(target: str, profile: str, day: int | None, report: bool) -> None:
    """Run static validators."""
    results: dict = {"target": target, "checks": []}

    if target in ("materials", "all"):
        r = validate_materials(day=day)
        results["checks"].append(r)
        _print_result(r)

    if target in ("data", "all"):
        r = validate_data_files(profile)
        results["checks"].append(r)
        _print_result(r)

    if target in ("kql", "all"):
        r = validate_kql_inventory(day=day)
        results["checks"].append(r)
        _print_result(r)

    overall = all(c.get("pass") for c in results["checks"])
    results["pass"] = overall

    if report:
        path = write_json_report(f"validate-{target}-{profile}.json", results)
        click.echo(f"Report: {path}")

    sys.exit(0 if overall else 1)


@main.command("checkpoints")
@click.option("--profile", default="lab")
def checkpoints_cmd(profile: str) -> None:
    """Print locked checkpoint counts for a profile."""
    p = load_profile(profile)
    click.echo(json.dumps(p.counts.model_dump(), indent=2))


@main.command("adx-checkpoints")
@click.option("--profile", default="lab")
@click.option("--day", type=int, default=None)
@click.option("--report", is_flag=True)
def adx_checkpoints_cmd(profile: str, day: int | None, report: bool) -> None:
    """Run live ADX checkpoint queries (requires Azure login)."""
    from adx_training_tools.adx.dry_run import run_checkpoints

    result = run_checkpoints(profile_name=profile, day=day)
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        write_json_report("adx-checkpoints.json", result)
    sys.exit(0 if result["pass"] else 1)


@main.command("adx-dry-run")
@click.argument("day", type=int)
@click.option("--report", is_flag=True)
def adx_dry_run_cmd(day: int, report: bool) -> None:
    """Execute all KQL files for a day against ADX."""
    from adx_training_tools.adx.dry_run import dry_run_day_queries

    result = dry_run_day_queries(day=day)
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        write_json_report(f"adx-dry-run-day{day:02d}.json", result)
    sys.exit(0 if result["pass"] else 1)


@main.command("azure-login")
@click.option(
    "--device-code",
    is_flag=True,
    help="Use device code flow (best for Cursor/Git Bash — no hanging picker)",
)
@click.option(
    "--subscription",
    default=None,
    help="Subscription ID (default: AZURE_SUBSCRIPTION_ID from .env)",
)
def azure_login_cmd(device_code: bool, subscription: str | None) -> None:
    """Azure login via browser or device code. Uses az from .venv."""
    from adx_training_tools.azure_cli import azure_login, az_executable, load_subscription_id

    sub = subscription or load_subscription_id()
    click.echo(f"Using: {az_executable()}")
    if device_code:
        click.echo("Device code login — open the URL shown below and enter the code.")
    else:
        click.echo("Browser login — if the subscription picker hangs, Ctrl+C and retry with --device-code")
    if sub:
        click.echo(f"Subscription: {sub}")
    azure_login(use_device_code=device_code, subscription_id=sub)
    click.echo("Login complete. Run: adx-tools azure-subscriptions")


@main.command("azure-subscriptions")
@click.option("--report", is_flag=True)
def azure_subscriptions_cmd(report: bool) -> None:
    """List Azure subscriptions and show current account."""
    from adx_training_tools.azure_cli import subscription_report

    result = subscription_report()
    click.echo(json.dumps(result, indent=2))
    if report:
        write_json_report("azure-subscriptions.json", result)
    sys.exit(0 if result.get("pass") else 1)


@main.command("azure-set-subscription")
@click.argument("subscription_id", required=False)
def azure_set_subscription_cmd(subscription_id: str | None) -> None:
    """Set active subscription (arg or AZURE_SUBSCRIPTION_ID in .env)."""
    from adx_training_tools.azure_cli import load_subscription_id, set_subscription

    sub = subscription_id or load_subscription_id()
    if not sub:
        click.echo("Provide subscription ID or set AZURE_SUBSCRIPTION_ID in GH/tools/.env")
        sys.exit(1)
    account = set_subscription(sub)
    click.echo(json.dumps(account, indent=2))
    click.echo(f"\nActive subscription: {account.get('name')} ({account.get('id')})")


@main.command("adx-test")
def adx_test_cmd() -> None:
    """Test ADX cluster connectivity."""
    from adx_training_tools.adx.connectivity import test_adx_connection

    result = test_adx_connection()
    click.echo(json.dumps(result, indent=2))
    sys.exit(0 if result.get("pass") else 1)


@main.command("run-all")
@click.option("--profile", default="lab")
def run_all_cmd(profile: str) -> None:
    """Generate heavy data, validate lab + heavy profiles, write report."""
    from adx_training_tools.adx.connectivity import test_adx_connection

    manifest = generate_all("heavy-10x")
    checks = [
        validate_materials(),
        validate_kql_inventory(),
        validate_data_files(profile),
        validate_data_files("heavy-10x"),
    ]
    adx = test_adx_connection()
    payload = {
        "heavy_manifest": manifest,
        "validation": checks,
        "adx_connection": adx,
        "pass": all(c["pass"] for c in checks) and adx.get("pass", False) is not False,
    }
    # ADX optional for static pass
    static_pass = all(c["pass"] for c in checks)
    payload["static_pass"] = static_pass
    payload["pass"] = static_pass
    path = write_json_report("run-all.json", payload)
    click.echo(json.dumps(payload, indent=2, default=str))
    click.echo(f"\nReport: {path}")
    if not adx.get("pass"):
        click.echo("\nNote: ADX connection not verified — configure Azure when cluster is live.")
    sys.exit(0 if static_pass else 1)


@main.command("lab-plan")
def lab_plan_cmd() -> None:
    """List ordered lab execution steps (no Azure required)."""
    from adx_training_tools.adx.lab_runner import lab_plan_inventory

    click.echo(json.dumps(lab_plan_inventory(), indent=2))


@main.command("adx-reset")
@click.option("--report", is_flag=True)
def adx_reset_cmd(report: bool) -> None:
    """Drop lab tables on test database (00-reset-logsdb.kql)."""
    from adx_training_tools.adx.lab_runner import run_reset

    result = run_reset()
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        write_json_report("adx-reset.json", result)
    sys.exit(0 if result.get("pass") else 1)


@main.command("adx-run-lab")
@click.argument("path", type=click.Path(exists=True))
@click.option("--report", is_flag=True)
def adx_run_lab_cmd(path: str, report: bool) -> None:
    """Execute all KQL statements in one lab file."""
    from adx_training_tools.adx.executor import load_run_config
    from adx_training_tools.adx.lab_runner import run_lab_file

    cfg = load_run_config()
    result = run_lab_file(Path(path), storage_account=cfg.get("storage_account"))
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        write_json_report("adx-run-lab.json", result)
    sys.exit(0 if result.get("pass") else 1)


@main.command("adx-send-streaming")
@click.argument(
    "kind",
    type=click.Choice(["eventhub", "iot", "both"]),
    default="both",
    required=False,
)
@click.option("--report", is_flag=True)
def adx_send_streaming_cmd(kind: str, report: bool) -> None:
    """Send Day 3 sample payloads to Event Hub and/or IoT Hub."""
    from adx_training_tools.streaming_sender import send_streaming_samples

    result = send_streaming_samples(kind)  # type: ignore[arg-type]
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        write_json_report(f"adx-send-streaming-{kind}.json", result)
    sys.exit(0 if result.get("pass") else 1)


@main.command("adx-run-course")
@click.option("--day", type=int, default=None, help="Limit to day 1-7")
@click.option("--profile", default="lab")
@click.option("--reset", is_flag=True, help="Reset database before run")
@click.option("--no-checkpoint", is_flag=True)
@click.option("--report", is_flag=True)
def adx_run_course_cmd(
    day: int | None, profile: str, reset: bool, no_checkpoint: bool, report: bool
) -> None:
    """Run full lab plan (or one day) with checkpoints."""
    from adx_training_tools.adx.lab_runner import run_lab_plan

    result = run_lab_plan(
        day=day,
        profile_name=profile,
        reset_first=reset,
        checkpoint_after_day=not no_checkpoint,
    )
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        name = f"adx-run-course-day{day:02d}.json" if day else "adx-run-course-full.json"
        write_json_report(name, result)
    sys.exit(0 if result.get("pass") else 1)


@main.group("docs")
def docs_group() -> None:
    """Microsoft Learn crawl, vector index, and link verification."""


@docs_group.command("crawl")
@click.option("--reset", is_flag=True, help="Rebuild Chroma collection")
@click.option("--max-depth", type=int, default=None)
@click.option("--max-pages", type=int, default=120)
@click.option("--report", is_flag=True)
def docs_crawl_cmd(reset: bool, max_depth: int | None, max_pages: int, report: bool) -> None:
    """Crawl curated Learn seeds (+1 hop) and index into ChromaDB."""
    from adx_training_tools.docs.index import build_index

    manifest = build_index(max_depth=max_depth, max_pages=max_pages, reset=reset)
    click.echo(json.dumps(manifest, indent=2))
    if report:
        write_json_report("docs-crawl.json", manifest)
    sys.exit(0 if not manifest.get("failed_urls") else 1)


@docs_group.command("search")
@click.argument("query")
@click.option("--topic", default=None, help="Filter: fundamentals, ingestion, event-hub-iot, ...")
@click.option("-n", "n_results", default=8, show_default=True)
def docs_search_cmd(query: str, topic: str | None, n_results: int) -> None:
    """Semantic search over indexed Microsoft Learn pages."""
    from adx_training_tools.docs.search import search_docs

    click.echo(json.dumps(search_docs(query, n_results=n_results, topic=topic), indent=2))


@docs_group.command("verify-links")
@click.option("--day", type=int, default=None, help="Limit to day 1-7")
@click.option("--report", is_flag=True)
def docs_verify_links_cmd(day: int | None, report: bool) -> None:
    """HTTP-check learn.microsoft.com links in student markdown."""
    from adx_training_tools.docs.verify_links import verify_markdown_links

    result = verify_markdown_links(day=day)
    click.echo(json.dumps(result, indent=2))
    if report:
        write_json_report("docs-verify-links.json", result)
    sys.exit(0 if result["pass"] else 1)


@main.command("init-develop")
@click.option(
    "--from-ref",
    default="HEAD",
    show_default=True,
    help="Git ref to snapshot as the full local course (usually HEAD on develop edits)",
)
def init_develop_cmd(from_ref: str) -> None:
    """Create/update local develop branch (full course — never push to GitHub)."""
    from adx_training_tools.publish.student_release import init_develop_branch

    click.echo(init_develop_branch(from_ref))


@main.command("publish-student-day")
@click.argument("day", type=click.IntRange(1, 5))
@click.option(
    "--push/--no-push",
    default=False,
    help="Push main to origin after commit (use --push before each class session)",
)
@click.option("--source", default="develop", show_default=True, help="Local branch with full course")
@click.option("--target", default="main", show_default=True, help="Student-facing branch on GitHub")
def publish_student_day_cmd(day: int, push: bool, source: str, target: str) -> None:
    """Publish cumulative Days 1..N from develop to main (incremental student release)."""
    from adx_training_tools.publish.student_release import publish_student_day

    result = publish_student_day(day, push=push, source=source, target=target)
    click.echo(
        json.dumps(
            {
                "day": result.day,
                "branch": result.branch,
                "committed": result.committed,
                "pushed": result.pushed,
                "message": result.message,
            },
            indent=2,
        )
    )
    if push and result.pushed:
        click.echo(f"\nStudents: share https://github.com/<org>/<repo> (branch: {target})")


@main.command("mcp")
def mcp_cmd() -> None:
    """Start MCP server (stdio transport for Cursor)."""
    from adx_training_tools.mcp_server import run_server

    run_server()


@main.group("aws")
def aws_group() -> None:
    """AWS credentials and Day 7 CloudTrail to ADLS sync."""


@aws_group.command("configure-env")
@click.option("--region", default="ap-south-1", show_default=True)
@click.option("--bucket", default=None, help="Optional CloudTrail S3 bucket")
@click.option("--prefix", default="AWSLogs/", show_default=True)
def aws_configure_env_cmd(region: str, bucket: str | None, prefix: str) -> None:
    """Save AWS access keys to tools/.env (prompted — not echoed)."""
    from adx_training_tools.aws.config import update_env_file

    access_key = click.prompt("AWS Access Key ID", hide_input=False)
    secret_key = click.prompt("AWS Secret Access Key", hide_input=True)
    session_token = click.prompt(
        "AWS Session Token (leave blank if not using STS)",
        default="",
        show_default=False,
        hide_input=True,
    )
    path = update_env_file(
        access_key_id=access_key.strip(),
        secret_access_key=secret_key.strip(),
        session_token=session_token.strip() or None,
        region=region,
        cloudtrail_s3_bucket=bucket,
        cloudtrail_s3_prefix=prefix,
    )
    click.echo(f"Wrote AWS settings to {path}")
    click.echo("Run: adx-tools aws verify")


@aws_group.command("verify")
def aws_verify_cmd() -> None:
    """Test AWS credentials (STS GetCallerIdentity)."""
    from adx_training_tools.aws.cloudtrail import verify_aws
    from adx_training_tools.aws.config import AwsConfig

    try:
        result = verify_aws(AwsConfig.from_env())
    except Exception as exc:  # noqa: BLE001
        cfg = AwsConfig.from_env()
        click.echo(
            json.dumps(
                {"pass": False, "error": str(exc), "hint": cfg.credential_hint()},
                indent=2,
            )
        )
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))
    sys.exit(0 if result.get("pass") else 1)


@aws_group.command("pull-cloudtrail")
@click.option(
    "--source",
    type=click.Choice(["auto", "s3", "lookup"]),
    default="auto",
    show_default=True,
)
@click.option("--max-records", type=int, default=None)
@click.option(
    "--output",
    default="cloudtrail-events-live.ndjson",
    show_default=True,
    help="Filename under GH/data/aws/ (use cloudtrail-events-sample.ndjson only for lab sample)",
)
@click.option("--report", is_flag=True)
def aws_pull_cloudtrail_cmd(source: str, max_records: int | None, output: str, report: bool) -> None:
    """Pull CloudTrail events with AWS keys and write NDJSON locally."""
    from adx_training_tools.aws.cloudtrail import pull_cloudtrail_ndjson, verify_aws, write_ndjson
    from adx_training_tools.aws.config import AwsConfig
    from adx_training_tools.config import find_gh_root, write_json_report

    config = AwsConfig.from_env()
    identity = verify_aws(config)
    lines, used = pull_cloudtrail_ndjson(config, source=source, max_records=max_records)
    out_path = find_gh_root() / "data" / "aws" / output
    write_ndjson(lines, out_path)
    result = {
        "pass": bool(lines),
        "identity": identity,
        "source": used,
        "record_count": len(lines),
        "local_path": str(out_path),
    }
    click.echo(json.dumps(result, indent=2))
    if report:
        write_json_report("aws-pull-cloudtrail.json", result)
    sys.exit(0 if result["pass"] else 1)


@aws_group.command("live-demo")
@click.option(
    "--source",
    type=click.Choice(["auto", "s3", "lookup"]),
    default="lookup",
    show_default=True,
)
@click.option("--max-records", type=int, default=80, show_default=True)
@click.option("--sample", is_flag=True, help="Use locked lab NDJSON instead of live AWS pull")
@click.option("--try-upload", is_flag=True, help="Attempt ADLS blob upload (needs Storage Blob Data Contributor)")
@click.option("--pull-only", is_flag=True, help="Pull to data/aws/ only — skip ADX ingest")
@click.option("--report", is_flag=True)
def aws_live_demo_cmd(
    source: str,
    max_records: int,
    sample: bool,
    try_upload: bool,
    pull_only: bool,
    report: bool,
) -> None:
    """Verify AWS → pull CloudTrail → ingest into ADX (one command for Day 6/7 live demo)."""
    from adx_training_tools.aws.config import AwsConfig
    from adx_training_tools.aws.live_demo import run_live_aws_demo
    from adx_training_tools.config import write_json_report

    result = run_live_aws_demo(
        AwsConfig.from_env(),
        source=source,
        max_records=max_records,
        use_sample=sample,
        try_adls_upload=try_upload,
        run_ingest=not pull_only,
    )
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        write_json_report("aws-live-demo.json", result)
    sys.exit(0 if result.get("pass") else 1)


@aws_group.command("ingest-inline")
@click.option(
    "--file",
    "file_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="NDJSON file (default: data/aws/cloudtrail-events-live.ndjson)",
)
@click.option("--sample", is_flag=True, help="Use locked lab sample (80 rows, 20 failures)")
@click.option("--no-setup", is_flag=True, help="Skip table/mapping creation (02–03)")
@click.option("--no-clear", is_flag=True, help="Do not clear AwsCloudTrailRaw before ingest")
@click.option("--report", is_flag=True)
def aws_ingest_inline_cmd(
    file_path: str | None, sample: bool, no_setup: bool, no_clear: bool, report: bool
) -> None:
    """Ingest CloudTrail NDJSON directly into ADX (live AWS demo — no ADLS required)."""
    from adx_training_tools.aws.ingest_inline import ingest_cloudtrail_inline
    from adx_training_tools.config import find_gh_root, write_json_report

    name = "cloudtrail-events-sample.ndjson" if sample else "cloudtrail-events-live.ndjson"
    path = Path(file_path) if file_path else find_gh_root() / "data" / "aws" / name
    result = ingest_cloudtrail_inline(
        path,
        setup_table=not no_setup,
        clear_first=not no_clear,
        source_file_label=path.name,
    )
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        write_json_report("aws-ingest-inline.json", result)
    sys.exit(0 if result.get("pass") else 1)


@aws_group.command("upload-lab-samples")
@click.option("--report", is_flag=True)
def aws_upload_lab_samples_cmd(report: bool) -> None:
    """Upload Day 7 CloudWatch + CloudTrail sample NDJSON to ADLS (maintainer preflight)."""
    from adx_training_tools.aws.sync import sync_lab_samples_to_adls
    from adx_training_tools.config import write_json_report

    result = sync_lab_samples_to_adls()
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        write_json_report("aws-upload-lab-samples.json", result)
    sys.exit(0 if result.get("pass") else 1)


@aws_group.command("sync-to-adls")
@click.option(
    "--source",
    type=click.Choice(["auto", "s3", "lookup"]),
    default="auto",
    show_default=True,
)
@click.option("--max-records", type=int, default=None)
@click.option("--no-upload", is_flag=True, help="Pull only — skip Azure Blob upload")
@click.option("--ingest", is_flag=True, help="Run Day 7 .ingest after upload")
@click.option("--report", is_flag=True)
def aws_sync_to_adls_cmd(
    source: str, max_records: int | None, no_upload: bool, ingest: bool, report: bool
) -> None:
    """AWS CloudTrail to GH/data/aws to ADLS (optional ADX ingest)."""
    from adx_training_tools.aws.config import AwsConfig
    from adx_training_tools.aws.sync import sync_cloudtrail_to_adls
    from adx_training_tools.config import write_json_report

    result = sync_cloudtrail_to_adls(
        AwsConfig.from_env(),
        source=source,
        max_records=max_records,
        upload=not no_upload,
        run_ingest=ingest,
    )
    click.echo(json.dumps(result, indent=2, default=str))
    if report:
        write_json_report("aws-sync-to-adls.json", result)
    sys.exit(0 if result.get("pass") else 1)


def _print_result(r: dict) -> None:
    name = r.get("validator", "check")
    status = "PASS" if r.get("pass") else "FAIL"
    click.echo(f"\n[{status}] {name}")
    if r.get("issues"):
        for issue in r["issues"]:
            click.echo(f"  - {issue}")
    if r.get("checks"):
        for c in r["checks"]:
            mark = "ok" if c["pass"] else "FAIL"
            click.echo(f"  {mark}: {c['name']} expected={c['expected']} actual={c['actual']}")


if __name__ == "__main__":
    main()
