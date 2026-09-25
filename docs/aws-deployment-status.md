# AWS deployment status — 25 September 2026

This is the current state of the fork in AWS account `101728439989`, Region `ap-southeast-1`. The deployed infrastructure and CLI scripts live in this repository. The three parent capstone documents describe the wider target architecture; this page records what actually exists.

## Deployed and verified

| Area | AWS resource or evidence | State |
|---|---|---|
| Foundation | CloudFormation `bigdata-ids-dev-foundation` | `CREATE_COMPLETE` |
| Data lake | `bigdata-ids-dev-foundation-databucket-y4img8enauch` | Private, SSE-S3, versioned; raw train/test and manifest uploaded |
| Artifacts | `bigdata-ids-dev-foundation-artifactbucket-vlvklecfav5s` | Private, SSE-S3, versioned |
| Data services | CloudFormation `bigdata-ids-dev-data` | `UPDATE_COMPLETE`; two Glue ETL jobs/tables, Catalog, Athena workgroup |
| Glue | `bigdata-ids-dev-data-nsl-kdd-etl` | Run `jr_c72f74e817958313aaa8ca4a39d3da808648bf7c965baf94163b3756b89c5b96` succeeded |
| Athena | `bigdata_ids_dev.flows_nsl_kdd` via workgroup `bigdata-ids-dev-data-athena` | Query `d762e729-54c1-4ca9-8725-283203f89420` succeeded |
| UNSW-NB15 | Glue run `jr_3159af64dd9a9d1da1caf03c404ce26567f8f5656a75005539d1b78c2b5a8076`; Athena `e3cb4685-5268-4df6-8290-1b346102b805` | `flows_unsw_nb15` ready; 175,341 train rows and 10 classes; 59,013 bytes scanned |
| GitHub auth | CloudFormation `bigdata-ids-dev-github-oidc` | `UPDATE_COMPLETE`; immutable fork/`master` subject; role can only Describe/Start the three named IDS pipelines |
| GitHub CI | [run 36136328787](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136328787) | Success on XGBoost/LSTM implementation commit `e3f54f9` |
| GitHub AWS smoke | [run 36097779782](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36097779782) | Success; OIDC role assumption |
| GitHub training workflow | [read-only run 36106066752](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36106066752), [SVM start run 36126420273](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36126420273) | Both GitHub jobs succeeded; the SVM pipeline execution `c5kl0f3eaypx` also `Succeeded` |
| GitHub extended dry runs | [XGBoost run 36136376488](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136376488), [LSTM run 36136379149](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136379149) | Both succeeded with `start_training=false`; no extra Processing jobs |
| SageMaker Pipeline | `bigdata-ids-dev-train` | RF run `w53s4k21lvg6`, local CLI SVM run `bao44h4fqvdk` and GitHub SVM run `c5kl0f3eaypx` all `Succeeded` |
| XGBoost Pipeline | `bigdata-ids-dev-xgboost` | CPU-only run `4ixfq9dbl2vq` `Succeeded`; official KDDTest+ F1 `0.770881` |
| LSTM Pipeline | `bigdata-ids-dev-lstm` | TensorFlow run `yjxa2d63nyic` `Succeeded`; 20-flow file-order window F1 `0.718540` |
| Model Registry | `bigdata-ids-dev-rf/4`, `bigdata-ids-dev-classical/4`, `bigdata-ids-dev-classical/5` | RF/SVM v4 packages `Completed` and `Approved`; new GitHub SVM v5 `Completed`, `PendingManualApproval`; v1–v3 packages `Rejected` after inference boot failures |
| New model packages | `bigdata-ids-dev-xgboost/1`, `bigdata-ids-dev-lstm/1` | Both `Completed` and `Approved` after artifact/metric review |
| Online inference | `bigdata-ids-dev-rf` | `InService` on RF v4 Serverless 2048 MB/concurrency 1; valid and invalid request smoke tests passed |
| XGBoost inference | `bigdata-ids-dev-xgboost` | `InService` on Serverless 2048 MB; KDDTest+ row 0 attack smoke test passed |
| LSTM inference | `bigdata-ids-dev-lstm` | `InService` on Serverless 3072 MB; 20-flow KDDTest+ window smoke test predicted attack correctly |
| Drift | CloudFormation `bigdata-ids-dev-monitoring` | `CREATE_COMPLETE`; PSI report on S3; CloudWatch alarm reached `ALARM` on synthetic shift |

The raw mirror files are `KDDTrain+.txt` (125,973 rows, SHA-256 `1b86d2f957b33082081bba410fe129b475efebcc13c9014c3f447c8271aadf95`) and `KDDTest+.txt` (22,544 rows, SHA-256 `fa46b0935342616aa83b7c2578db355b6a7aaabbc492248172c7a1e8b7ab8f84`). The Athena query returned 58,630 attack and 67,343 normal rows from the curated training data, scanning 16,454 bytes.

UNSW-NB15 has separate raw train/test files (175,341/82,332 rows), schema, Glue table and manifest. Train SHA-256: `bec7dd5ec88dc2a0ccc7a07879d338395ed7421750f675fd0339e07dfe0648fa`; test SHA-256: `734fe6642edf758f7c94d7d9149426b49d202fe8e7bf0bef47392489c3c0a559`. The [official dataset page](https://research.unsw.edu.au/projects/unsw-nb15-dataset) allows free academic research use; the public mirror URL is recorded in the S3 manifest. Do not feed UNSW rows into the NSL-KDD model.

## Constraints found in this account

- Firehose delivery stream creation returned `The AWS Access Key Id needs a subscription for the service`. `infra/data.yaml` therefore defaults `EnableFirehose` to `false`; batch S3 → Glue → Athena works. The Firehose execution role exists but is idle.
- SageMaker `ml.m5.large` quota is 0 for Processing and Training. `ml.t3.large` Processing quota is 4, so the pipeline uses a managed Processing job for preprocessing, model fitting and evaluation. This is a quota workaround; it is not a SageMaker Training Job.
- Serverless endpoint memory is capped at 3072 MB in this account. LSTM uses 3072 MB and XGBoost 2048 MB; a 4096 MB LSTM endpoint request was rejected before creation.
- A quota request for one `ml.m5.large` Training instance was submitted with request ID `8cc761a8777747418dc8700669703768fnbeVUWS`; latest observed status `CASE_OPENED`. Check it before switching the pipeline to `--compute-mode training`.
- The IAM user `capstone-admin` authenticated but lacked CloudFormation and IAM read permissions. The user explicitly directed this deployment to use the already configured `default` root profile. Keep `--allow-root` explicit and verify the account in each script. Do not put AWS keys into source control or GitHub Actions. An access key was exposed in chat and should be rotated by the account owner.

## Model evidence

The classical preprocessing fits encoding, scaling and 25-feature selection on training data only. It splits `KDDTrain+` into 100,778 train and 25,195 validation rows. The untouched official `KDDTest+` contains 22,544 rows. RF, SVM and XGBoost below are **completed AWS SageMaker Pipeline results**:

| Model | Execution | Rows used to fit | Official test accuracy | Official test F1 | Official test FPR |
|---|---|---:|---:|---:|---:|
| Random Forest | AWS Pipeline `w53s4k21lvg6` | 30,000 | 0.776836 | 0.762453 | 0.028009 |
| SVM | AWS Pipeline `bao44h4fqvdk` | 8,000 | 0.726623 | 0.706118 | 0.075584 |
| XGBoost | AWS Pipeline `4ixfq9dbl2vq` | 30,000 | 0.783046 | 0.770881 | 0.029451 |

The earlier XGBoost local preliminary F1 was `0.771514`; it is not the AWS result. The LSTM metric has a **different unit**: 40,000 training flows formed 2,000 non-overlapping 20-flow windows; official KDDTest+ formed 1,127 windows from 22,540 flows (4 leftover). LSTM window accuracy `0.740018`, F1 `0.718540`, FPR `0.057377`; confusion matrix TN 460, FP 28, FN 265, TP 374. The target label is the last flow of each file-order window. NSL-KDD does not verify that file row order reflects network time, so this is a sequence-model demonstration, not a temporal intrusion claim. Its window F1 is not directly comparable with flow-level RF/SVM/XGBoost F1. See [extended model guide](lstm-xgboost-aws.md).

RF AWS confusion matrix is TN 9,439, FP 272, FN 4,759, TP 8,074; precision 0.967410 and recall 0.629159. SVM confusion matrix is TN 8,977, FP 734, FN 5,429, TP 7,404; precision 0.909806 and recall 0.576950. The RF evaluation artifact is `s3://bigdata-ids-dev-foundation-artifactbucket-vlvklecfav5s/bigdata-ids-dev-train/w53s4k21lvg6/EvaluateOnOfficialTest/output/evaluation/evaluation.json`; SVM uses the corresponding `bao44h4fqvdk` prefix. The independent SVM run launched from GitHub produced the same metrics on 22,544 official test rows; its JSON is at `s3://bigdata-ids-dev-foundation-artifactbucket-vlvklecfav5s/bigdata-ids-dev-train/c5kl0f3eaypx/EvaluateOnOfficialTest/output/evaluation/evaluation.json`. Its new package `bigdata-ids-dev-classical/5` remains pending approval; no endpoint was replaced.

Package v1 used `code/sagemaker_inference.py`, which shadowed the framework's own `sagemaker_inference` module; CloudWatch showed `ImportError: cannot import name 'content_types'`. `scripts/repair-inference-artifact.py` renamed it to `ids_inference.py` in v2, but the container then reported `No module named 'ids_inference'`. Version 3 used an S3 source tar, yet the generated setup metadata still failed import. Version 4 adds explicit `setup.py` with `py_modules=['ids_inference']` and `PYTHONPATH`; the source tar installed/imported in a local packaging check and the SageMaker endpoint reached `InService`. The model weights and original evaluation metrics did **not** change; v1–v3 packages were rejected. New pipeline runs upload a hash-named source tar automatically. Failed endpoint config/model metadata v1–v3 was deleted; Model Registry history remains.

Online smoke test: `scripts/smoke-endpoint.py --row-index 0` read raw KDDTest+ row 0 (attack label 1), and the endpoint returned `prediction=1`, `attack_probability=1.0`, `dataset_id=nsl-kdd`, `dataset_version=v1`. An invalid payload `{"record":{}}` was rejected with HTTP 424 `ModelError`. This confirms schema rejection, although the managed container surfaces it as a generic model error rather than HTTP 400.

The upstream README's LSTM/XGBoost metrics remain author-reported claims. The new AWS runs above are separate capstone measurements with explicit splits and training limits. The official test distribution is harder than a holdout from `KDDTrain+`; report the split and row counts beside every metric.

XGBoost endpoint smoke test on KDDTest+ row 0 returned `prediction=1`, `attack_probability=0.999985`, matching attack label 1. LSTM TensorFlow Serving smoke test on rows 0–19 returned `prediction=1`, `attack_probability=0.995140`, matching the last flow's attack label. The LSTM endpoint expects a preprocessed `20×25` tensor; `scripts/smoke-lstm-endpoint.py` applies the package's own preprocessor on the client. Some LSTM Serverless invocations returned intermittent `ModelError` (server error 0) before an application request appeared in its CloudWatch log; subsequent identical requests succeeded. The smoke script retries that specific no-response error up to four times. Treat this endpoint as a demo, and investigate capacity/platform behavior before claiming reliable production serving.

## Drift evidence

`src/aws_drift_demo.py` produced max PSI 0.006151 for a stable sample, 20.649132 for a deliberately shifted feature, and 0.251246 for official KDDTest+. The synthetic shift is **not a real intrusion**. `scripts/publish-drift.ps1` uploads all reports to S3 and publishes `Capstone/IDS` `MaxPSI` with dimension `DatasetId=nsl-kdd`. The CloudWatch alarm crossed `>0.25` and reached **ALARM** from the 20.649132 datapoint. It uses five-minute periods, with missing data treated as non-breaching. SNS/email and a scheduled drift job are not yet configured.

## Resume commands (PowerShell 7)

Run from this repository root. The scripts default to `capstone-dev`, but the current account requires the explicit root option shown here. Do not paste credentials into commands.

```powershell
aws sts get-caller-identity --profile default --region ap-southeast-1
aws cloudformation describe-stacks --stack-name bigdata-ids-dev-foundation --profile default --region ap-southeast-1 --query 'Stacks[0].StackStatus'
aws sagemaker describe-pipeline-execution --pipeline-execution-arn arn:aws:sagemaker:ap-southeast-1:101728439989:pipeline/bigdata-ids-dev-train/execution/w53s4k21lvg6 --profile default --region ap-southeast-1 --query '{Status:PipelineExecutionStatus,Failure:FailureReason}'
aws sagemaker list-pipeline-execution-steps --pipeline-execution-arn arn:aws:sagemaker:ap-southeast-1:101728439989:pipeline/bigdata-ids-dev-train/execution/w53s4k21lvg6 --profile default --region ap-southeast-1
aws sagemaker describe-pipeline-execution --pipeline-execution-arn arn:aws:sagemaker:ap-southeast-1:101728439989:pipeline/bigdata-ids-dev-train/execution/bao44h4fqvdk --profile default --region ap-southeast-1 --query '{Status:PipelineExecutionStatus,Failure:FailureReason}'
aws sagemaker describe-endpoint --endpoint-name bigdata-ids-dev-rf --profile default --region ap-southeast-1 --query '{Status:EndpointStatus,Failure:FailureReason}'
aws cloudwatch describe-alarms --alarm-names bigdata-ids-dev-monitoring-nsl-kdd-psi-critical --profile default --region ap-southeast-1 --query 'MetricAlarms[].StateValue'
aws service-quotas get-requested-service-quota-change --request-id 8cc761a8777747418dc8700669703768fnbeVUWS --profile default --region ap-southeast-1
```

To repeat foundation/data setup, use `./scripts/deploy-foundation.ps1 -Profile default -AllowRoot`, `./scripts/ingest-nsl-kdd.ps1 -Profile default -AllowRoot`, `./scripts/ingest-unsw.ps1 -Profile default -AllowRoot`, then `./scripts/deploy-data.ps1 -Profile default -AllowRoot`. Re-running Glue costs money; only start it when needed. To build/start a new SVM pipeline execution, install `sagemaker==2.257.5`, `botocore[crt]`, `scikit-learn==1.4.2`, and run `./.venv/Scripts/python.exe pipelines/register_pipeline.py --profile default --allow-root --compute-mode processing --model-name svm --train-rows 8000 --deploy --start`. Do not rerun merely to inspect the existing execution.

To use GitHub instead of local CLI for the deployed pipeline definitions, open **Actions → AWS train (manual) → Run workflow** on `master`. Leave `start_training=false` to verify OIDC and the selected pipeline without creating compute jobs. Set it to `true` only when a new billable Processing run is intended; choices are RF (30,000 flows), SVM (8,000), XGBoost (30,000) and LSTM (40,000 flows, 12 epochs). It starts an existing pipeline but does not update its definition or promote a model package. See [extended model guide](lstm-xgboost-aws.md) for commands and input contracts.

After endpoint state is `InService`, smoke test one raw official test row with `./.venv/Scripts/python.exe scripts/smoke-endpoint.py --profile default --allow-root --row-index 0`. To recreate the endpoint from the approved package, run `./.venv/Scripts/python.exe scripts/deploy-endpoint.py --profile default --allow-root --package-arn arn:aws:sagemaker:ap-southeast-1:101728439989:model-package/bigdata-ids-dev-rf/4 --wait`. For a drift demo, run `./scripts/publish-drift.ps1 -Profile default -AllowRoot` and wait for CloudWatch metric/alarm propagation. These actions can incur charges.

## Manual work still needed

1. Rotate/deactivate the access key that appeared in the chat, then update local profile credentials without sending them to anyone.
2. Review AWS Billing/Budgets after the Glue and SageMaker jobs. Retained S3 objects and idle model metadata remain after jobs stop.
3. Check the training quota request. If approved, rerun the pipeline in `training` mode and compare actual managed Training Job metrics.
4. If the course requires streaming ingestion, resolve the Firehose service subscription issue with AWS Support before enabling `EnableFirehose=true`.
5. Decide whether the rubric truly requires MLflow, scheduled drift, Autoencoder on AWS or Batch Transform; these are not yet deployed. RF, SVM, XGBoost and LSTM have now run on AWS, although SVM has no dedicated endpoint.
6. Delete the serverless endpoints after the live demo if no longer needed: `aws sagemaker delete-endpoint --endpoint-name bigdata-ids-dev-rf --profile default --region ap-southeast-1`, and similarly `bigdata-ids-dev-xgboost`/`bigdata-ids-dev-lstm`. Model Registry and S3 artifacts remain available for recreation.
