"""Invoke the deployed IDS endpoint with one raw row from official KDDTest+."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.sagemaker_preprocess import NSL_KDD_COLUMNS, NUMERIC_COLS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="capstone-dev")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--account-id", default="101728439989")
    parser.add_argument("--allow-root", action="store_true")
    parser.add_argument("--endpoint-name", default="bigdata-ids-dev-rf")
    parser.add_argument("--row-index", type=int, default=0)
    parser.add_argument("--test-file", type=Path, default=Path("data/KDDTest+.txt"))
    args = parser.parse_args()
    if args.row_index < 0:
        parser.error("--row-index must be non-negative")

    os.environ["AWS_SDK_UA_APP_ID"] = "AWSSkill-SageMaker"
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != args.account_id or (
        identity["Arn"].endswith(":root") and not args.allow_root
    ):
        raise RuntimeError(f"Unexpected AWS identity: {identity['Arn']}")

    with args.test_file.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for index, row in enumerate(reader):
            if index == args.row_index:
                break
        else:
            raise IndexError(f"No row {args.row_index} in {args.test_file}")
    if len(row) != 43:
        raise ValueError(f"Expected 43 NSL-KDD columns, got {len(row)}")
    record = dict(zip(NSL_KDD_COLUMNS, row[:42]))
    expected = 0 if record.pop("label").lower() == "normal" else 1
    for name in NUMERIC_COLS:
        record[name] = float(record[name])
    result = session.client("sagemaker-runtime").invoke_endpoint(
        EndpointName=args.endpoint_name,
        ContentType="application/json",
        Accept="application/json",
        Body=json.dumps({"record": record}).encode("utf-8"),
    )
    prediction = json.loads(result["Body"].read())
    print(json.dumps({
        "endpoint": args.endpoint_name,
        "test_row_index": args.row_index,
        "expected_binary_label": expected,
        "result": prediction,
    }))


if __name__ == "__main__":
    main()
