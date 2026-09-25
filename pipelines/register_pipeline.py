"""Create a managed SageMaker pipeline for NSL-KDD classical IDS baselines."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

import boto3
from botocore.exceptions import ClientError
from sagemaker.inputs import TrainingInput
from sagemaker.model import Model
from sagemaker.model_metrics import MetricsSource, ModelMetrics
from sagemaker.processing import ProcessingInput, ProcessingOutput
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.workflow.functions import Join, JsonGet
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import PipelineSession
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.step_collections import RegisterModel
from sagemaker.workflow.steps import ProcessingStep, TrainingStep


PIPELINE_NAME = "bigdata-ids-dev-train"
PACKAGE_GROUP = "bigdata-ids-dev-classical"
INFERENCE_SCRIPT = Path(__file__).resolve().parents[1] / "inference" / "ids_inference.py"
INFERENCE_SETUP = (
    b"from setuptools import setup\n"
    b"setup(name='capstone-ids-inference', version='1.0.0', "
    b"py_modules=['ids_inference'])\n"
)


def inference_code_uri(bucket: str) -> str:
    digest = hashlib.sha256(INFERENCE_SCRIPT.read_bytes() + INFERENCE_SETUP).hexdigest()
    return f"s3://{bucket}/code/inference/ids-inference-{digest}.tar.gz"


def upload_inference_code(boto_session: boto3.Session, bucket: str) -> str:
    source = INFERENCE_SCRIPT.read_bytes()
    uri = inference_code_uri(bucket)
    key = uri.split(f"s3://{bucket}/", 1)[1]
    s3 = boto_session.client("s3")
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return uri
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"404", "NoSuchKey"}:
            raise
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, body in (("ids_inference.py", source), ("setup.py", INFERENCE_SETUP)):
            info = tarfile.TarInfo(name)
            info.size = len(body)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(body))
    s3.put_object(
        Bucket=bucket, Key=key, Body=buffer.getvalue(), ServerSideEncryption="AES256"
    )
    return uri


def stack_outputs(client, name: str) -> dict[str, str]:
    response = client.describe_stacks(StackName=name)
    return {item["OutputKey"]: item["OutputValue"] for item in response["Stacks"][0]["Outputs"]}


def build_pipeline(boto_session: boto3.Session, data_bucket: str, artifact_bucket: str,
                   role_arn: str, compute_mode: str, code_uri: str) -> Pipeline:
    session = PipelineSession(boto_session=boto_session, default_bucket=artifact_bucket)
    model_parameter = ParameterString(name="ModelName", default_value="random_forest")
    rows_parameter = ParameterString(name="TrainRows", default_value="30000")
    raw_uri = f"s3://{data_bucket}/raw/dataset=nsl-kdd/version=v1/"

    preprocess = SKLearnProcessor(
        framework_version="1.4-2",
        role=role_arn,
        instance_count=1,
        instance_type="ml.t3.large" if compute_mode == "processing" else "ml.m5.large",
        base_job_name="bigdata-ids-preprocess",
        max_runtime_in_seconds=1800,
        sagemaker_session=session,
    )
    preprocess_args = preprocess.run(
        code="src/sagemaker_preprocess.py",
        inputs=[ProcessingInput(source=raw_uri, destination="/opt/ml/processing/input")],
        outputs=[
            ProcessingOutput(output_name=name, source=f"/opt/ml/processing/output/{name}")
            for name in ("train", "validation", "test", "preprocessor")
        ],
    )
    process_step = ProcessingStep(name="PreprocessNSLKDD", step_args=preprocess_args)

    def processed(name: str):
        return process_step.properties.ProcessingOutputConfig.Outputs[name].S3Output.S3Uri

    if compute_mode == "processing":
        trainer = SKLearnProcessor(
            framework_version="1.4-2",
            role=role_arn,
            instance_count=1,
            instance_type="ml.t3.large",
            base_job_name="bigdata-ids-classical-processing",
            max_runtime_in_seconds=1800,
            env={"PYTHONPATH": "/opt/ml/processing/code"},
            sagemaker_session=session,
        )
        train_args = trainer.run(
            code="src/sagemaker_train.py",
            inputs=[
                ProcessingInput(source=processed(name), destination=f"/opt/ml/processing/{name}")
                for name in ("train", "validation", "preprocessor")
            ] + [
                ProcessingInput(source="src/models.py", destination="/opt/ml/processing/code"),
                ProcessingInput(source="inference/ids_inference.py",
                                destination="/opt/ml/processing/inference"),
            ],
            outputs=[ProcessingOutput(output_name="model", source="/opt/ml/processing/model")],
            arguments=[
                "--model-name", model_parameter,
                "--max-train-rows", rows_parameter,
                "--train-dir", "/opt/ml/processing/train",
                "--validation-dir", "/opt/ml/processing/validation",
                "--preprocessor-dir", "/opt/ml/processing/preprocessor",
                "--model-dir", "/opt/ml/processing/model",
                "--inference-script", "/opt/ml/processing/inference/ids_inference.py",
            ],
        )
        train_step = ProcessingStep(name="TrainClassicalOnProcessing", step_args=train_args)
        model_artifact = Join(on="/", values=[
            train_step.properties.ProcessingOutputConfig.Outputs["model"].S3Output.S3Uri,
            "model.tar.gz",
        ])
    else:
        estimator = SKLearn(
            entry_point="sagemaker_train.py",
            source_dir="src",
            dependencies=["inference"],
            framework_version="1.4-2",
            py_version="py3",
            role=role_arn,
            instance_type="ml.m5.large",
            instance_count=1,
            base_job_name="bigdata-ids-classical",
            max_run=3600,
            hyperparameters={"model-name": model_parameter, "max-train-rows": rows_parameter,
                             "inference-script": "inference/ids_inference.py"},
            sagemaker_session=session,
        )
        train_args = estimator.fit(
            inputs={name: TrainingInput(s3_data=processed(name), input_mode="File")
                    for name in ("train", "validation", "preprocessor")}
        )
        train_step = TrainingStep(name="TrainClassical", step_args=train_args)
        model_artifact = train_step.properties.ModelArtifacts.S3ModelArtifacts

    evaluation = SKLearnProcessor(
        framework_version="1.4-2",
        role=role_arn,
        instance_count=1,
        instance_type="ml.t3.large" if compute_mode == "processing" else "ml.m5.large",
        base_job_name="bigdata-ids-evaluate",
        max_runtime_in_seconds=1200,
        sagemaker_session=session,
    )
    evaluation_args = evaluation.run(
        code="src/sagemaker_evaluate.py",
        inputs=[
            ProcessingInput(source=model_artifact,
                            destination="/opt/ml/processing/model"),
            ProcessingInput(source=processed("test"), destination="/opt/ml/processing/test"),
        ],
        outputs=[ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation")],
    )
    report = PropertyFile(name="EvaluationReport", output_name="evaluation", path="evaluation.json")
    evaluation_step = ProcessingStep(
        name="EvaluateOnOfficialTest", step_args=evaluation_args, property_files=[report]
    )

    evaluation_uri = evaluation_step.properties.ProcessingOutputConfig.Outputs["evaluation"].S3Output.S3Uri
    metrics = ModelMetrics(
        model_statistics=MetricsSource(
            s3_uri=Join(on="/", values=[evaluation_uri, "evaluation.json"]),
            content_type="application/json",
        )
    )
    image_uri = preprocess.image_uri
    model = Model(
        image_uri=image_uri,
        model_data=model_artifact,
        role=role_arn,
        env={"SAGEMAKER_PROGRAM": "ids_inference.py",
             "SAGEMAKER_SUBMIT_DIRECTORY": code_uri,
             "PYTHONPATH": "/opt/ml/code:/opt/ml/model/code"},
        sagemaker_session=session,
    )
    register = RegisterModel(
        name="RegisterClassicalIDSModel",
        model=model,
        model_package_group_name=PACKAGE_GROUP,
        content_types=["application/json"],
        response_types=["application/json"],
        inference_instances=["ml.m5.large"],
        transform_instances=["ml.m5.large"],
        approval_status="PendingManualApproval",
        model_metrics=metrics,
    )
    gate = ConditionStep(
        name="GateOfficialTestF1",
        conditions=[ConditionGreaterThanOrEqualTo(
            left=JsonGet(step_name=evaluation_step.name, property_file=report, json_path="f1"),
            right=0.70,
        )],
        if_steps=[register],
        else_steps=[],
    )
    return Pipeline(
        name=PIPELINE_NAME,
        parameters=[model_parameter, rows_parameter],
        steps=[process_step, train_step, evaluation_step, gate],
        sagemaker_session=session,
    )


def ensure_package_group(client) -> None:
    try:
        client.describe_model_package_group(ModelPackageGroupName=PACKAGE_GROUP)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ValidationException":
            raise
        client.create_model_package_group(
            ModelPackageGroupName=PACKAGE_GROUP,
            ModelPackageGroupDescription="NSL-KDD classical IDS model candidates",
            Tags=[{"Key": "Project", "Value": "bigdata-ids-capstone"}],
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="capstone-dev")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--account-id", default="101728439989")
    parser.add_argument("--allow-root", action="store_true")
    parser.add_argument("--compute-mode", choices=["processing", "training"], default="processing")
    parser.add_argument("--model-name", choices=["random_forest", "svm"],
                        default="random_forest")
    parser.add_argument("--train-rows", type=int, default=30000)
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()
    if args.start and not args.deploy:
        parser.error("--start requires --deploy")

    os.environ["AWS_SDK_UA_APP_ID"] = "AWSSkill-SageMaker"
    os.environ["SAGEMAKER_SUPPRESS_V2_WARNING"] = "1"
    boto_session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = boto_session.client("sts").get_caller_identity()
    if identity["Account"] != args.account_id or (identity["Arn"].endswith(":root") and not args.allow_root):
        raise RuntimeError(f"Unexpected AWS identity: {identity['Arn']}")
    cfn = boto_session.client("cloudformation")
    foundation = stack_outputs(cfn, "bigdata-ids-dev-foundation")
    code_uri = (upload_inference_code(boto_session, foundation["ArtifactBucketName"])
                if args.deploy else inference_code_uri(foundation["ArtifactBucketName"]))
    pipeline = build_pipeline(
        boto_session,
        foundation["DataBucketName"],
        foundation["ArtifactBucketName"],
        foundation["SageMakerRoleArn"],
        args.compute_mode,
        code_uri,
    )
    definition = json.loads(pipeline.definition())
    print(json.dumps({"pipeline": PIPELINE_NAME, "steps": [s["Name"] for s in definition["Steps"]]}))
    if args.deploy:
        client = boto_session.client("sagemaker")
        ensure_package_group(client)
        result = pipeline.upsert(role_arn=foundation["SageMakerRoleArn"],
                                 tags=[{"Key": "Project", "Value": "bigdata-ids-capstone"}])
        print(json.dumps({"pipeline_arn": result["PipelineArn"]}))
    if args.start:
        execution = pipeline.start(
            parameters={"ModelName": args.model_name, "TrainRows": str(args.train_rows)},
            execution_display_name=f"NSL-KDD-{args.model_name}-baseline",
        )
        print(json.dumps({"execution_arn": execution.arn}))


if __name__ == "__main__":
    main()
