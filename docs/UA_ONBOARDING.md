# Onboarding guide: ml-ids-zero-trust-cloud

This Python project detects suspicious network traffic with machine learning and connects the models to a Zero Trust cloud workflow. It includes research notebooks, local MLflow experiments, a FastAPI prediction service, and AWS paths for data preparation, SageMaker training, deployment, and drift monitoring. The main supporting tools are Docker, GitHub Actions, CloudFormation, Glue, and SageMaker.

**Start with the evidence distinction:** the research results described in the [README](../README.md) are inherited from upstream. Use the [AWS deployment status](aws-deployment-status.md) and [deployment report](DEPLOYMENT_REPORT.md) for measurements and resource state verified in this fork.

## Architecture layers

| Layer | Responsibility |
|---|---|
| Inference API and monitoring UI | Serve predictions and display drift reports. |
| Detection and drift logic | Define models, experiments, evaluation, and drift calculations. |
| Data preparation and ETL | Turn benchmark data into local features and curated AWS data. |
| SageMaker training pipelines | Train, evaluate, gate, and register candidate models. |
| Deployment and operations scripts | Provision resources, deploy endpoints, publish metrics, and run smoke checks. |
| Cloud infrastructure and container | Define AWS resources and package the inference API. |
| CI and AWS workflows | Validate changes and provide manually triggered AWS operations. |
| Documentation and system design | Explain the research, architecture, deployment evidence, and operations. |
| Research notebooks | Explore data and reproduce model and Zero Trust visuals. |
| Project setup and dependencies | Define Python dependencies and package metadata. |

## Key concepts

- **Two preprocessing paths:** [src/preprocess.py](../src/preprocess.py) supports the legacy research workflow; [src/sagemaker_preprocess.py](../src/sagemaker_preprocess.py) prepares train, validation, and official test data for SageMaker.
- **Separate model paths:** [src/models.py](../src/models.py) defines the shared detector wrappers. SageMaker has distinct classical-model and LSTM training paths.
- **Evaluation before release:** the classical pipeline evaluates on KDDTest+, applies an F1 gate, and registers a pending model package. Endpoint deployment uses an approved package.
- **Operational drift:** feature PSI, prediction shifts, and optional performance changes feed reports, a Streamlit view, and CloudWatch metrics.
- **Zero Trust framing:** [docs/ZTA_Framework.md](ZTA_Framework.md) maps detection work to the five Zero Trust pillars and an adoption roadmap.

## Guided tour

1. Read the [README](../README.md) and [Zero Trust framework](ZTA_Framework.md) for the project's purpose.
2. Trace a prediction from the [FastAPI entry point](../api/serve.py) into the [model wrappers](../src/models.py).
3. Use the [dataset guide](../data/README.md) and [exploration notebook](../notebooks/01_data_exploration.ipynb) to understand the inputs.
4. Compare [local preprocessing](../src/preprocess.py), [SageMaker preprocessing](../src/sagemaker_preprocess.py), and the [NSL-KDD Glue job](../glue/nsl_kdd_etl.py).
5. Follow [MLflow training](../src/train_mlflow.py) into [evaluation](../src/evaluate.py).
6. Read the [classical training job](../src/sagemaker_train.py), [official-test evaluator](../src/sagemaker_evaluate.py), and [LSTM job](../src/sagemaker_lstm.py).
7. Inspect the [classical pipeline](../pipelines/register_pipeline.py) and [LSTM pipeline](../pipelines/register_lstm_pipeline.py) to see how jobs connect.
8. Trace hosted predictions through the [SageMaker inference hooks](../inference/ids_inference.py), [endpoint deployment](../scripts/deploy-endpoint.py), and [smoke check](../scripts/smoke-endpoint.py).
9. Read the [foundation](../infra/foundation.yaml) and [data stack](../infra/data.yaml) templates before the deployment scripts.
10. Review [GitHub OIDC](../infra/github-oidc.yaml) and the [training workflow](../.github/workflows/aws-train.yml) for AWS access and manual triggers.
11. Follow [drift calculation](../src/drift_monitor.py), [metric publishing](../scripts/publish-drift.ps1), and the [dashboard](../dashboard/drift_app.py).
12. Finish with the [deployment status](aws-deployment-status.md) and [operations runbook](OPERATIONS_RUNBOOK.md).

## File map for day-to-day work

| Area | Files to keep close |
|---|---|
| Prediction and monitoring | [api/serve.py](../api/serve.py), [inference/ids_inference.py](../inference/ids_inference.py), [dashboard/drift_app.py](../dashboard/drift_app.py) |
| Models and metrics | [src/models.py](../src/models.py), [src/evaluate.py](../src/evaluate.py), [src/drift_monitor.py](../src/drift_monitor.py) |
| Data | [src/sagemaker_preprocess.py](../src/sagemaker_preprocess.py), [glue/nsl_kdd_etl.py](../glue/nsl_kdd_etl.py), [glue/unsw_etl.py](../glue/unsw_etl.py) |
| Cloud operations | [infra/foundation.yaml](../infra/foundation.yaml), [infra/data.yaml](../infra/data.yaml), [scripts/deploy-endpoint.py](../scripts/deploy-endpoint.py) |
| Team guidance | [developer guide](DEVELOPER_GUIDE.md), [operations runbook](OPERATIONS_RUNBOOK.md), [deployment report](DEPLOYMENT_REPORT.md) |

## Complexity hotspots

Approach [src/models.py](../src/models.py) and [api/serve.py](../api/serve.py) together: model compatibility, loading, and API prediction behavior meet there. Changes to [src/preprocess.py](../src/preprocess.py) or [pipelines/register_pipeline.py](../pipelines/register_pipeline.py) can affect feature contracts and evaluation gates. Review [src/drift_monitor.py](../src/drift_monitor.py) with its reports and dashboard. For AWS changes, read the [foundation](../infra/foundation.yaml) and [data](../infra/data.yaml) templates alongside the runbook.

This guide was generated from the saved knowledge graph at commit `e73a22f`. An uncommitted README command edit was absent from that graph when the guide was generated.
