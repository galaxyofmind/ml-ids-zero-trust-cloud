"""Deploy a managed SageMaker Processing pipeline for the NSL-KDD LSTM demo."""

from __future__ import annotations

import argparse
import json
import os

import boto3
from sagemaker.processing import ProcessingInput, ProcessingOutput
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.tensorflow import TensorFlowProcessor
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import PipelineSession
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.steps import ProcessingStep


PIPELINE_NAME = "bigdata-ids-dev-lstm"


def stack_outputs(client, name: str) -> dict[str, str]:
    response = client.describe_stacks(StackName=name)
    return {item["OutputKey"]: item["OutputValue"] for item in response["Stacks"][0]["Outputs"]}


def build_pipeline(boto_session: boto3.Session, data_bucket: str,
                   artifact_bucket: str, role_arn: str) -> Pipeline:
    session = PipelineSession(boto_session=boto_session, default_bucket=artifact_bucket)
    train_flows = ParameterString(name="MaxTrainFlows", default_value="40000")
    epochs = ParameterString(name="Epochs", default_value="12")
    raw_uri = f"s3://{data_bucket}/raw/dataset=nsl-kdd/version=v1/"

    preprocess = SKLearnProcessor(
        framework_version="1.4-2", role=role_arn, instance_count=1,
        instance_type="ml.t3.large", base_job_name="bigdata-ids-lstm-preprocess",
        max_runtime_in_seconds=1800, sagemaker_session=session,
    )
    preprocess_args = preprocess.run(
        code="src/sagemaker_preprocess.py",
        inputs=[ProcessingInput(source=raw_uri, destination="/opt/ml/processing/input")],
        outputs=[ProcessingOutput(output_name=name, source=f"/opt/ml/processing/output/{name}")
                 for name in ("train", "validation", "test", "preprocessor")],
        arguments=["--ordered-split"],
    )
    preprocess_step = ProcessingStep(name="PreprocessOrderedNSLKDD", step_args=preprocess_args)

    def processed(name: str):
        return preprocess_step.properties.ProcessingOutputConfig.Outputs[name].S3Output.S3Uri

    trainer = TensorFlowProcessor(
        framework_version="2.16.2", py_version="py310", role=role_arn,
        instance_count=1, instance_type="ml.t3.large",
        base_job_name="bigdata-ids-lstm-processing", max_runtime_in_seconds=3600,
        env={"PYTHONPATH": "/opt/ml/processing/code", "TF_CPP_MIN_LOG_LEVEL": "2"},
        sagemaker_session=session,
    )
    train_args = trainer.run(
        code="src/sagemaker_lstm.py",
        inputs=[ProcessingInput(source=processed(name), destination=f"/opt/ml/processing/{name}")
                for name in ("train", "validation", "test", "preprocessor")]
        + [ProcessingInput(source="src/models.py", destination="/opt/ml/processing/code")],
        outputs=[
            ProcessingOutput(output_name="model", source="/opt/ml/processing/model"),
            ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation"),
        ],
        arguments=["--max-train-flows", train_flows, "--epochs", epochs],
    )
    report = PropertyFile(name="LstmEvaluation", output_name="evaluation", path="evaluation.json")
    train_step = ProcessingStep(name="TrainAndEvaluateLSTM", step_args=train_args,
                                property_files=[report])
    return Pipeline(name=PIPELINE_NAME, parameters=[train_flows, epochs],
                    steps=[preprocess_step, train_step], sagemaker_session=session)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="capstone-dev")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--account-id", default="101728439989")
    parser.add_argument("--allow-root", action="store_true")
    parser.add_argument("--max-train-flows", type=int, default=40000)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()
    if args.start and not args.deploy:
        parser.error("--start requires --deploy")
    if args.max_train_flows < 2000 or args.epochs < 1:
        parser.error("need at least 2000 flows and one epoch")

    os.environ["AWS_SDK_UA_APP_ID"] = "AWSSkill-SageMaker"
    os.environ["SAGEMAKER_SUPPRESS_V2_WARNING"] = "1"
    boto_session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = boto_session.client("sts").get_caller_identity()
    if identity["Account"] != args.account_id or (identity["Arn"].endswith(":root") and not args.allow_root):
        raise RuntimeError(f"Unexpected AWS identity: {identity['Arn']}")
    foundation = stack_outputs(boto_session.client("cloudformation"), "bigdata-ids-dev-foundation")
    pipeline = build_pipeline(boto_session, foundation["DataBucketName"],
                              foundation["ArtifactBucketName"], foundation["SageMakerRoleArn"])
    definition = json.loads(pipeline.definition())
    print(json.dumps({"pipeline": PIPELINE_NAME,
                      "steps": [step["Name"] for step in definition["Steps"]]}))
    if args.deploy:
        result = pipeline.upsert(role_arn=foundation["SageMakerRoleArn"],
                                 tags=[{"Key": "Project", "Value": "bigdata-ids-capstone"}])
        print(json.dumps({"pipeline_arn": result["PipelineArn"]}))
    if args.start:
        execution = pipeline.start(
            parameters={"MaxTrainFlows": str(args.max_train_flows), "Epochs": str(args.epochs)},
            execution_display_name="NSL-KDD-LSTM-file-order-demo",
        )
        print(json.dumps({"execution_arn": execution.arn}))


if __name__ == "__main__":
    main()
