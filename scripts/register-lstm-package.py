"""Register a completed LSTM Pipeline artifact as a pending TensorFlow model package."""

from __future__ import annotations

import argparse
import json
import os

import boto3
from botocore.exceptions import ClientError
from sagemaker import image_uris


PACKAGE_GROUP = "bigdata-ids-dev-lstm"


def output_uris(sm, execution_arn: str) -> dict[str, str]:
    steps = sm.list_pipeline_execution_steps(PipelineExecutionArn=execution_arn)["PipelineExecutionSteps"]
    step = next(item for item in steps if item["StepName"] == "TrainAndEvaluateLSTM")
    if step["StepStatus"] != "Succeeded":
        raise RuntimeError(f"LSTM step is {step['StepStatus']}")
    job_name = step["Metadata"]["ProcessingJob"]["Arn"].rsplit("/", 1)[-1]
    job = sm.describe_processing_job(ProcessingJobName=job_name)
    return {output["OutputName"]: output["S3Output"]["S3Uri"].rstrip("/")
            for output in job["ProcessingOutputConfig"]["Outputs"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="capstone-dev")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--account-id", default="101728439989")
    parser.add_argument("--allow-root", action="store_true")
    parser.add_argument("--execution-arn", required=True)
    args = parser.parse_args()
    os.environ["AWS_SDK_UA_APP_ID"] = "AWSSkill-SageMaker"
    os.environ["SAGEMAKER_SUPPRESS_V2_WARNING"] = "1"
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != args.account_id or (identity["Arn"].endswith(":root") and not args.allow_root):
        raise RuntimeError(f"Unexpected AWS identity: {identity['Arn']}")
    sm = session.client("sagemaker")
    execution = sm.describe_pipeline_execution(PipelineExecutionArn=args.execution_arn)
    if execution["PipelineExecutionStatus"] != "Succeeded":
        raise RuntimeError(f"Pipeline is {execution['PipelineExecutionStatus']}")
    uris = output_uris(sm, args.execution_arn)
    model_uri = f"{uris['model']}/model.tar.gz"
    evaluation_uri = f"{uris['evaluation']}/evaluation.json"
    s3 = session.client("s3")
    for uri in (model_uri, evaluation_uri):
        bucket, key = uri.removeprefix("s3://").split("/", 1)
        s3.head_object(Bucket=bucket, Key=key)

    try:
        sm.describe_model_package_group(ModelPackageGroupName=PACKAGE_GROUP)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ValidationException":
            raise
        sm.create_model_package_group(
            ModelPackageGroupName=PACKAGE_GROUP,
            ModelPackageGroupDescription="NSL-KDD LSTM file-order sequence candidates",
            Tags=[{"Key": "Project", "Value": "bigdata-ids-capstone"}],
        )
    existing = sm.list_model_packages(ModelPackageGroupName=PACKAGE_GROUP,
                                      SortBy="CreationTime", SortOrder="Descending", MaxResults=20)
    for summary in existing.get("ModelPackageSummaryList", []):
        package = sm.describe_model_package(ModelPackageName=summary["ModelPackageArn"])
        containers = package.get("InferenceSpecification", {}).get("Containers", [])
        if containers and containers[0].get("ModelDataUrl") == model_uri:
            print(json.dumps({"package_arn": summary["ModelPackageArn"], "existing": True,
                              "model_uri": model_uri, "evaluation_uri": evaluation_uri}))
            return

    image = image_uris.retrieve("tensorflow", args.region, version="2.16.1",
                                py_version="py310", image_scope="inference",
                                instance_type="ml.m5.large")
    result = sm.create_model_package(
        ModelPackageGroupName=PACKAGE_GROUP,
        ModelPackageDescription=("Two-layer LSTM; NSL-KDD file-order 20-row windows; "
                                 "accepts preprocessed 20x25 JSON tensors"),
        InferenceSpecification={
            "Containers": [{"Image": image, "ModelDataUrl": model_uri}],
            "SupportedContentTypes": ["application/json"],
            "SupportedResponseMIMETypes": ["application/json"],
            "SupportedRealtimeInferenceInstanceTypes": ["ml.m5.large"],
            "SupportedTransformInstanceTypes": ["ml.m5.large"],
        },
        ModelApprovalStatus="PendingManualApproval",
        ModelMetrics={"ModelQuality": {"Statistics": {
            "ContentType": "application/json", "S3Uri": evaluation_uri,
        }}},
    )
    print(json.dumps({"package_arn": result["ModelPackageArn"], "existing": False,
                      "model_uri": model_uri, "evaluation_uri": evaluation_uri}))


if __name__ == "__main__":
    main()
