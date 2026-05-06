from __future__ import annotations
from typing import Optional
import boto3
from botocore.exceptions import ClientError
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

CATEGORY_RUNBOOK_MAP = {
    "CI/CD": "runbooks/cicd_runbook.md",
    "Data/ETL": "runbooks/data_runbook.md",
    "Infrastructure": "runbooks/infra_runbook.md",
    "Access/IAM": "runbooks/access_runbook.md",
    "Network": "runbooks/network_runbook.md",
}

def get_runbook(category, s3_client=None):
    key = CATEGORY_RUNBOOK_MAP.get(category)
    if not key:
        return None
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=config.REGION)
    try:
        r = s3_client.get_object(Bucket=config.RUNBOOK_BUCKET, Key=key)
        return r["Body"].read().decode("utf-8")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "NoSuchBucket"):
            return None
        raise
