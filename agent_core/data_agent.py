from __future__ import annotations
import re, boto3, json, os
from botocore.exceptions import ClientError
from agent_core.base_agent import BaseSubAgent, _call_nova
from tools.models import FixSuggestion

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

# ANSI
R="\033[0m"; B="\033[1m"; GR="\033[92m"; YL="\033[93m"; RD="\033[91m"; CY="\033[96m"


class DataETLAgent(BaseSubAgent):
    domain = "Data/ETL"
    category = "Data/ETL"

    def investigate(self, ticket_id, description, category, severity,
                    s3_client=None, bedrock_client=None):
        # Run base investigation (AI fix suggestion)
        fix = super().investigate(ticket_id, description, category, severity,
                                  s3_client, bedrock_client)

        # Try to extract and re-run a Glue job mentioned in the ticket
        job_name = _extract_glue_job(description)
        if job_name:
            print(f"\n  {CY}🔍 Glue job detected:{R} {B}{job_name}{R}")
            status = _get_job_status(job_name)
            print(f"  {CY}Last run status:{R} {_status_badge(status)}")

            if status in ("FAILED", "ERROR", "TIMEOUT", "STOPPED", "UNKNOWN"):
                print(f"  {YL}⚡ Attempting automatic re-run...{R}")
                run_id, error = _rerun_glue_job(job_name)
                if run_id:
                    print(f"  {GR}✓ Glue job re-triggered{R}")
                    print(f"  {GR}  Job Run ID: {B}{run_id}{R}")
                    fix.remediation_steps = (
                        f"[AUTO-ACTION] Glue job '{job_name}' re-triggered automatically.\n"
                        f"Job Run ID: {run_id}\n\n"
                        + (fix.remediation_steps if isinstance(fix.remediation_steps, str) else "\n".join(fix.remediation_steps))
                    )
                    fix.aws_resources = list(set(fix.aws_resources + [f"glue:job:{job_name}"]))
                else:
                    print(f"  {RD}✗ Re-run failed: {error}{R}")
                    fix.remediation_steps = (
                        f"[MANUAL ACTION REQUIRED] Could not auto-restart Glue job '{job_name}': {error}\n\n"
                        + (fix.remediation_steps if isinstance(fix.remediation_steps, str) else "")
                    )
            elif status == "RUNNING":
                print(f"  {GR}✓ Job is already running — no action needed{R}")
            else:
                print(f"  {GR}✓ Last run succeeded — investigating root cause only{R}")

        return fix


def _extract_glue_job(description: str) -> str | None:
    """Extract a Glue job name from ticket description."""
    # Match patterns like: "Glue job daily_claims_load", "job: etl_pipeline", etc.
    patterns = [
        r"glue\s+job\s+['\"]?([a-zA-Z0-9_\-]+)['\"]?",
        r"job\s+['\"]?([a-zA-Z0-9_\-]+)['\"]?\s+failed",
        r"['\"]([a-zA-Z0-9_\-]*(?:glue|etl|load|pipeline|job)[a-zA-Z0-9_\-]*)['\"]",
    ]
    for pat in patterns:
        m = re.search(pat, description, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _get_job_status(job_name: str) -> str:
    """Get the last run status of a Glue job."""
    try:
        client = boto3.client("glue", region_name=config.REGION)
        r = client.get_job_runs(JobName=job_name, MaxResults=1)
        runs = r.get("JobRuns", [])
        return runs[0]["JobRunState"] if runs else "NO_RUNS"
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "EntityNotFoundException":
            return "NOT_FOUND"
        return f"ERROR: {code}"
    except Exception:
        return "UNKNOWN"


def _rerun_glue_job(job_name: str) -> tuple[str | None, str | None]:
    """Trigger a new Glue job run. Returns (run_id, error)."""
    try:
        client = boto3.client("glue", region_name=config.REGION)
        r = client.start_job_run(JobName=job_name)
        return r["JobRunId"], None
    except ClientError as e:
        return None, e.response["Error"]["Message"]
    except Exception as e:
        return None, str(e)


def _status_badge(status: str) -> str:
    if status in ("SUCCEEDED",):
        return f"{GR}{B}{status}{R}"
    elif status in ("FAILED", "ERROR", "TIMEOUT"):
        return f"{RD}{B}{status}{R}"
    elif status == "RUNNING":
        return f"{CY}{B}{status}{R}"
    else:
        return f"{YL}{B}{status}{R}"
