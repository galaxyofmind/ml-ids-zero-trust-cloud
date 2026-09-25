"""Send one 20-flow NSL-KDD window to a TensorFlow Serving LSTM endpoint."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import time

import boto3
import joblib
import pandas as pd
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.sagemaker_preprocess import CATEGORICAL_COLS, NSL_KDD_COLUMNS, NUMERIC_COLS, transform


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="capstone-dev")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--account-id", default="101728439989")
    parser.add_argument("--allow-root", action="store_true")
    parser.add_argument("--package-arn", required=True)
    parser.add_argument("--endpoint-name", default="bigdata-ids-dev-lstm")
    parser.add_argument("--test-file", type=Path, default=Path("data/KDDTest+.txt"))
    parser.add_argument("--row-index", type=int, default=0,
                        help="First row of a 20-flow window; use a multiple of 20")
    args = parser.parse_args()
    if args.row_index < 0 or args.row_index % 20:
        parser.error("--row-index must be a non-negative multiple of 20")
    os.environ["AWS_SDK_UA_APP_ID"] = "AWSSkill-SageMaker"
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != args.account_id or (identity["Arn"].endswith(":root") and not args.allow_root):
        raise RuntimeError(f"Unexpected AWS identity: {identity['Arn']}")
    package = session.client("sagemaker").describe_model_package(ModelPackageName=args.package_arn)
    uri = package["InferenceSpecification"]["Containers"][0]["ModelDataUrl"]
    bucket, key = uri.removeprefix("s3://").split("/", 1)
    buffer = io.BytesIO()
    session.client("s3").download_fileobj(bucket, key, buffer)
    buffer.seek(0)
    with tarfile.open(fileobj=buffer, mode="r:gz") as archive:
        preprocessor_file = archive.extractfile("preprocessor.joblib")
        if preprocessor_file is None:
            raise RuntimeError("preprocessor.joblib missing from LSTM artifact")
        preprocessor = joblib.load(io.BytesIO(preprocessor_file.read()))

    with args.test_file.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))[args.row_index: args.row_index + 20]
    if len(rows) != 20 or any(len(row) != 43 for row in rows):
        raise ValueError("need exactly 20 valid KDDTest+ rows")
    frame = pd.DataFrame(rows, columns=NSL_KDD_COLUMNS + ["difficulty"])
    expected = 0 if frame.iloc[-1]["label"].lower() == "normal" else 1
    for name in NUMERIC_COLS:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
    for name in CATEGORICAL_COLS:
        frame[name] = frame[name].astype(str)
    features = transform(frame, preprocessor["scaler"], preprocessor["encoder"],
                         preprocessor["selected_indices"])
    body = json.dumps({"instances": [features.tolist()]}).encode("utf-8")
    runtime = session.client("sagemaker-runtime")
    for attempt in range(1, 5):
        try:
            response = runtime.invoke_endpoint(
                EndpointName=args.endpoint_name, ContentType="application/json",
                Accept="application/json", Body=body,
            )
            break
        except ClientError as exc:
            error = exc.response.get("Error", {})
            transient = error.get("Code") == "ModelError" and "could not get a response" in error.get("Message", "").lower()
            if not transient or attempt == 4:
                raise
            time.sleep(5 * attempt)
    result = json.loads(response["Body"].read())
    probability = float(result["predictions"][0][0])
    if not 0.0 <= probability <= 1.0:
        raise ValueError("TensorFlow Serving returned an invalid probability")
    print(json.dumps({"endpoint": args.endpoint_name, "test_rows": [args.row_index,
                     args.row_index + 19], "expected_last_flow_label": expected,
                     "prediction": int(probability >= 0.5),
                     "attack_probability": probability, "attempts": attempt}))


if __name__ == "__main__":
    main()
