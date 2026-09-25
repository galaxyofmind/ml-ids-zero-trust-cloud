"""Deploy an approved NSL-KDD model package to a small SageMaker serverless endpoint."""

from __future__ import annotations

import argparse
import json
import os
import time

import boto3
from botocore.exceptions import ClientError


def stack_outputs(client, name: str) -> dict[str, str]:
    stack = client.describe_stacks(StackName=name)["Stacks"][0]
    return {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}


def describe_or_none(method, **kwargs):
    try:
        return method(**kwargs)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ValidationException":
            return None
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="capstone-dev")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--account-id", default="101728439989")
    parser.add_argument("--allow-root", action="store_true")
    parser.add_argument("--package-arn", required=True)
    parser.add_argument("--endpoint-name", default="bigdata-ids-dev-rf")
    parser.add_argument("--memory-mb", type=int, default=2048)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()

    os.environ["AWS_SDK_UA_APP_ID"] = "AWSSkill-SageMaker"
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != args.account_id or (
        identity["Arn"].endswith(":root") and not args.allow_root
    ):
        raise RuntimeError(f"Unexpected AWS identity: {identity['Arn']}")

    sm = session.client("sagemaker")
    package = sm.describe_model_package(ModelPackageName=args.package_arn)
    if package["ModelApprovalStatus"] != "Approved" or package["ModelPackageStatus"] != "Completed":
        raise RuntimeError("Model package must be Completed and Approved")
    if package["ModelPackageArn"].split(":")[4] != args.account_id:
        raise RuntimeError("Model package is from a different account")

    role = stack_outputs(session.client("cloudformation"), "bigdata-ids-dev-foundation")[
        "SageMakerRoleArn"
    ]
    version = args.package_arn.rsplit("/", 1)[-1]
    model_name = f"{args.endpoint_name}-v{version}"
    config_name = f"{args.endpoint_name}-v{version}-serverless"
    tags = [{"Key": "Project", "Value": "bigdata-ids-capstone"}]

    model = describe_or_none(sm.describe_model, ModelName=model_name)
    if model is None:
        sm.create_model(
            ModelName=model_name,
            PrimaryContainer={"ModelPackageName": args.package_arn},
            ExecutionRoleArn=role,
            Tags=tags,
        )
    elif model["PrimaryContainer"].get("ModelPackageName") != args.package_arn:
        raise RuntimeError(f"Existing model {model_name} refers to another package")

    config = describe_or_none(sm.describe_endpoint_config, EndpointConfigName=config_name)
    if config is None:
        sm.create_endpoint_config(
            EndpointConfigName=config_name,
            ProductionVariants=[{
                "VariantName": "AllTraffic",
                "ModelName": model_name,
                "ServerlessConfig": {
                    "MemorySizeInMB": args.memory_mb,
                    "MaxConcurrency": args.max_concurrency,
                },
            }],
            Tags=tags,
        )
    else:
        variant = config["ProductionVariants"][0]
        if variant["ModelName"] != model_name or variant["ServerlessConfig"] != {
            "MemorySizeInMB": args.memory_mb,
            "MaxConcurrency": args.max_concurrency,
        }:
            raise RuntimeError(f"Existing endpoint config {config_name} differs from request")

    endpoint = describe_or_none(sm.describe_endpoint, EndpointName=args.endpoint_name)
    if endpoint is None:
        sm.create_endpoint(
            EndpointName=args.endpoint_name,
            EndpointConfigName=config_name,
            Tags=tags,
        )
    elif endpoint["EndpointConfigName"] != config_name:
        raise RuntimeError(f"Existing endpoint {args.endpoint_name} uses another config")

    if args.wait:
        for _ in range(60):
            endpoint = sm.describe_endpoint(EndpointName=args.endpoint_name)
            status = endpoint["EndpointStatus"]
            print(json.dumps({"endpoint": args.endpoint_name, "status": status}))
            if status == "InService":
                break
            if status in {"Failed", "OutOfService"}:
                raise RuntimeError(endpoint.get("FailureReason", status))
            time.sleep(20)
        else:
            raise TimeoutError("Endpoint did not become InService within 20 minutes")
    else:
        endpoint = sm.describe_endpoint(EndpointName=args.endpoint_name)
        print(json.dumps({"endpoint": args.endpoint_name,
                          "status": endpoint["EndpointStatus"],
                          "model_package": args.package_arn}))


if __name__ == "__main__":
    main()
