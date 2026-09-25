"""Register a corrected model artifact while preserving the original evaluation link."""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse

import boto3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="capstone-dev")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--account-id", default="101728439989")
    parser.add_argument("--allow-root", action="store_true")
    parser.add_argument("--source-package-arn", required=True)
    parser.add_argument("--fixed-model-uri", required=True)
    parser.add_argument("--code-uri", required=True,
                        help="S3 URI of a tar.gz containing ids_inference.py at its root")
    args = parser.parse_args()

    os.environ["AWS_SDK_UA_APP_ID"] = "AWSSkill-SageMaker"
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != args.account_id or (
        identity["Arn"].endswith(":root") and not args.allow_root
    ):
        raise RuntimeError(f"Unexpected AWS identity: {identity['Arn']}")
    if args.source_package_arn.split(":")[4] != args.account_id:
        raise RuntimeError("Source package belongs to another account")

    location = urlparse(args.fixed_model_uri)
    if location.scheme != "s3" or not location.netloc or not location.path.endswith("/model.tar.gz"):
        parser.error("--fixed-model-uri must be an s3://.../model.tar.gz URI")
    session.client("s3").head_object(Bucket=location.netloc, Key=location.path.lstrip("/"))
    code_location = urlparse(args.code_uri)
    if (code_location.scheme != "s3" or not code_location.netloc
            or not code_location.path.endswith(".tar.gz")):
        parser.error("--code-uri must be an s3://...tar.gz URI")
    session.client("s3").head_object(Bucket=code_location.netloc,
                                     Key=code_location.path.lstrip("/"))

    sm = session.client("sagemaker")
    source = sm.describe_model_package(ModelPackageName=args.source_package_arn)
    old_container = source["InferenceSpecification"]["Containers"][0]
    if old_container["Environment"].get("SAGEMAKER_PROGRAM") not in {
        "sagemaker_inference.py", "ids_inference.py"
    }:
        raise RuntimeError("Source package does not have a known inference entry point")
    spec = source["InferenceSpecification"]
    result = sm.create_model_package(
        ModelPackageGroupName=source["ModelPackageGroupName"],
        ModelPackageDescription=(
            "Corrected inference code source tar; same trained model and official-test metrics "
            f"as {args.source_package_arn}"
        ),
        InferenceSpecification={
            "Containers": [{
                "Image": old_container["Image"],
                "ModelDataUrl": args.fixed_model_uri,
                "Environment": {
                    "SAGEMAKER_PROGRAM": "ids_inference.py",
                    "SAGEMAKER_SUBMIT_DIRECTORY": args.code_uri,
                },
            }],
            "SupportedContentTypes": spec["SupportedContentTypes"],
            "SupportedResponseMIMETypes": spec["SupportedResponseMIMETypes"],
            "SupportedRealtimeInferenceInstanceTypes": spec[
                "SupportedRealtimeInferenceInstanceTypes"
            ],
            "SupportedTransformInstanceTypes": spec["SupportedTransformInstanceTypes"],
        },
        ModelApprovalStatus="PendingManualApproval",
        ModelMetrics={
            "ModelQuality": {
                "Statistics": source["ModelMetrics"]["ModelQuality"]["Statistics"]
            }
        },
        CustomerMetadataProperties={
            "source_model_package": args.source_package_arn,
            "repair": "serve ids_inference.py from a separate source tar",
        },
    )
    print(json.dumps({"model_package_arn": result["ModelPackageArn"]}))


if __name__ == "__main__":
    main()
