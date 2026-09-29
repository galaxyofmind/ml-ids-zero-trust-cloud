# Model pipelines: local experiments and AWS training

This guide compares the five-model local experiment code with the two AWS training paths implemented in this repository. It describes **code behavior at commit `e73a22f`** and separates that behavior from the AWS results recorded in [AWS deployment status](aws-deployment-status.md) on 25 September 2026. The AWS state can change; the recorded results are evidence of those runs, not a live status check. The high accuracy figures in the [README](../README.md) are inherited research claims, not results reproduced by this fork.

## The three routes at a glance

```text
Local experiment (five models)
KDDTrain+ downloaded by src/preprocess.py
  -> one-hot encoding, scaling, SMOTE, RFECV, then stratified split
  -> saved 25-feature NumPy arrays
  -> Random Forest | SVM | LSTM | Autoencoder | XGBoost
  -> intended MLflow runs, local model files, local FastAPI service
  [the training driver currently stops at a missing import; see Limitations]

AWS classical (Random Forest, SVM, XGBoost)
KDDTrain+ and KDDTest+ in raw S3
  -> SageMaker preprocessing: stratified train/validation split; fit on train
  -> one selected classifier; optional stratified training-row limit
  -> validation metrics -> official KDDTest+ flow-level evaluation
  -> F1 >= 0.70 gate -> pending Model Registry package
  -> manual approval -> SageMaker Serverless endpoint -> one raw-flow request

AWS LSTM
The same raw S3 files
  -> SageMaker preprocessing: ordered train/validation split; fit on train
  -> non-overlapping 20-flow windows, labeled by the last flow
  -> TensorFlow Processing training and validation
  -> official KDDTest+ window-level evaluation and SavedModel
  -> separate manual registration as a pending TensorFlow package
  -> manual approval -> SageMaker Serverless endpoint -> one 20x25 tensor
```

The AWS model pipelines consume **raw NSL-KDD files directly from S3**. The [Glue ETL](../glue/nsl_kdd_etl.py) and Athena curated-Parquet branch supports analytics; neither training pipeline reads that Glue table. UNSW-NB15 has an ETL/analytics branch but does not feed these NSL-KDD models. See the [classical pipeline](../pipelines/register_pipeline.py#L87-L105) and [LSTM pipeline](../pipelines/register_lstm_pipeline.py#L31-L46).

## Stage-by-stage differences

| Stage | Shared local experiment | AWS classical path | AWS LSTM path |
|---|---|---|---|
| Input | Downloads `KDDTrain+.txt` from a GitHub mirror if `data/X_train.npy` is absent. It does not use the independent `KDDTest+` file in this path. | Reads `KDDTrain+.txt` and independent `KDDTest+.txt` from the raw S3 prefix. | Reads the same two S3 files. |
| Split | Applies scaling, binary SMOTE and RFECV to the full downloaded dataset **before** a stratified 80/20 split. Re-fits a scaler after feature selection. | Stratified 80/20 split of `KDDTrain+` (`random_state=42`); leaves `KDDTest+` untouched. | File-row-order 80/20 split of `KDDTrain+`; leaves `KDDTest+` untouched. |
| Transform | `pd.get_dummies`, MinMax scaling, SMOTE, random-forest RFECV with five folds, then 25 selected features. | Fits MinMaxScaler, OneHotEncoder and a random-forest importance selector **only on training rows**; selects 25 features and applies the fitted objects to validation/test. No SMOTE or RFECV. | Same fitted transform and 25-feature selection as AWS classical, with `--ordered-split`. No SMOTE or RFECV. |
| Fit | One trainer per selected model, intended to run through `src/train_mlflow.py`. | `src/sagemaker_train.py` selects Random Forest, SVM or XGBoost and optionally subsamples the training split by class. | `src/sagemaker_lstm.py` turns rows into non-overlapping windows and trains one two-layer LSTM. |
| Evaluation unit | Individual rows for RF, SVM, XGBoost and Autoencoder; **windows** for LSTM, labeled using the **first** row of each window after the local split. | Individual flows from untouched official `KDDTest+`. | 20-flow windows from untouched official `KDDTest+`, labeled using the **last** row. |
| Evaluation/report | The local driver intends to log accuracy, precision, recall, F1 and FPR to MLflow. RF/XGBoost also request 10-fold CV. The separate `src/evaluate.py` can write `results/metrics.csv`, but the driver does not call that CSV function. | Validation accuracy/F1 go into the model archive; official-test accuracy, positive-class precision/recall/F1, FPR and confusion counts go into `evaluation.json`. | Validation F1 and official-test window metrics are written together to `evaluation.json`, including counts of flows and windows used. |
| Release | MLflow logging calls request named registered models. No automatic promotion call exists in the driver. | Pipeline registers a pending package **only when official-test F1 is at least 0.70**. | Pipeline ends after training/evaluation. A separate script registers a pending package after a successful execution; there is no automatic F1 gate. |
| Serving | Local FastAPI loads model files from `results/models/` and expects preprocessed 25-feature vectors. | SageMaker Scikit-learn inference hook accepts one raw 41-feature NSL-KDD record and applies the packaged preprocessor. | TensorFlow Serving accepts an already preprocessed `20 x 25` tensor; the client must apply the package's preprocessor. |

The local sequence is defined in [preprocess.py](../src/preprocess.py#L403-L491) and [train_mlflow.py](../src/train_mlflow.py#L55-L70). AWS preprocessing is in [sagemaker_preprocess.py](../src/sagemaker_preprocess.py#L64-L136). The split and metric units matter more than the model names when comparing results.

## Local five-model experiment

### Shared data and tracking

`python src/train_mlflow.py` selects all five trainers in order: Random Forest, SVM, LSTM, Autoencoder, XGBoost. `--model <name>` selects one. The driver loads four arrays (`X_train`, `X_test`, `y_train`, `y_test`) from `data/`; if `X_train.npy` is missing, it calls the local preprocessor. It sets MLflow to a local `mlruns/` file store and experiment `ids-zero-trust`. Each trainer opens its own run, logs model-specific parameters and metrics, saves a file in `results/models/`, logs that file, and calls an MLflow model logger with a registered model name. The all-model loop catches trainer exceptions and continues; the single-model branch does not. See [train_mlflow.py](../src/train_mlflow.py#L47-L70) and [its dispatch](../src/train_mlflow.py#L280-L328).

The local preprocessor maps `normal` to 0 and recognized attacks to 1, with unrecognized labels also mapped to attack. It also derives five-class labels for saved auxiliary arrays. It one-hot encodes three categorical fields, first scales all rows, runs binary SMOTE and random-forest RFECV on the resulting full dataset, splits 80/20, then fits a second scaler on selected training features and transforms the selected test features. Saved outputs are `data/{X,y}_{train,test}.npy`, multiclass label arrays, and `results/models/{scaler.pkl,rfecv_selector.pkl,selected_features.csv}`. See [preprocess.py](../src/preprocess.py#L135-L155) and [run_pipeline](../src/preprocess.py#L403-L491).

| Model | Local fitting and target | Local evaluation/logging and saved file |
|---|---|---|
| **Random Forest** | 200 trees, Gini, unrestricted depth, `random_state=42`; binary row classification. | Holdout predictions/probabilities, intended common metrics and 10-fold stratified CV; `random_forest.pkl` plus an MLflow scikit-learn model. |
| **SVM** | Probabilistic RBF SVC, `C=10`, `gamma=0.001`; binary row classification. | Holdout predictions/probabilities and intended common metrics; `svm.pkl` plus an MLflow scikit-learn model. No CV call in this trainer. |
| **LSTM** | Two 128-unit LSTM layers, dropout 0.3, dense 64, sigmoid binary output; 20-row windows, **first-row** target. Up to 50 epochs, batch 256, 10% validation split, early stopping patience 5 and learning-rate reduction. | Holdout window predictions, intended common metrics and per-epoch loss logging; `lstm.h5` plus an MLflow Keras model. Incomplete final windows are discarded. |
| **Autoencoder** | Dense encoder `input_dim -> 32 -> 16 -> 8` with symmetric decoder; fits **normal rows only** for up to 50 epochs. The 95th percentile of normal training reconstruction error is the attack threshold. | Holdout anomaly labels and intended common metrics; `autoencoder.h5` and `autoencoder_threshold.pkl` plus an MLflow Keras model. Its normalized reconstruction score is a heuristic score, not a calibrated attack probability. |
| **XGBoost** | 500 estimators, learning rate 0.05, depth 6, row subsample 0.8, column subsample 0.8; binary row classification. | Holdout predictions/probabilities, intended common metrics and 10-fold stratified CV; `xgboost.pkl` plus an MLflow XGBoost model. |

These parameters come from [models.py](../src/models.py#L62-L422) and the trainer calls in [train_mlflow.py](../src/train_mlflow.py#L73-L277). The Autoencoder trainer logs an architecture string starting with `41`, while its constructed input dimension is `X_train.shape[1]` (normally 25 after selection); the actual model is determined by that input dimension.

### Local serving contract

[api/serve.py](../api/serve.py#L65-L89) defaults to `lstm`, lazily loads named `.pkl` or `.h5` artifacts, and exposes `/health`, `/models`, `/predict` and `/predict/single`. Requests carry **already processed 25-feature vectors**; this service does not accept the 41 raw NSL-KDD fields used by the AWS classical endpoint. Its model metadata contains inherited research accuracy/FPR values, not measurements from a local run. The LSTM wrapper groups 20 input rows into one prediction, so the single-row endpoint and batch response semantics do not fit that model as written. See [batch prediction](../api/serve.py#L209-L256), [single prediction](../api/serve.py#L259-L283), and [LSTM reshape](../src/models.py#L204-L255).

## AWS path 1: Random Forest, SVM and XGBoost

1. [Ingestion](../scripts/ingest-nsl-kdd.ps1) uploads the 125,973-row `KDDTrain+` and 22,544-row `KDDTest+` files to the NSL-KDD v1 raw S3 prefix with a checksum manifest. These row counts are recorded in [AWS deployment status](aws-deployment-status.md).
2. [PreprocessNSLKDD](../pipelines/register_pipeline.py#L89-L106) loads both files. It stratifies `KDDTrain+` 80/20, fits scaling/encoding and an 80-tree importance selector on the 100,778 training rows, selects 25 columns, and produces train, validation, untouched test and preprocessor outputs. The recorded validation split has 25,195 rows. See [preprocessing source](../src/sagemaker_preprocess.py#L72-L135).
3. [TrainClassicalOnProcessing or TrainClassical](../pipelines/register_pipeline.py#L111-L169) selects `random_forest`, `svm` or `xgboost` and instantiates the same model classes and hyperparameters listed in the local table. The default is SageMaker **Processing** on `ml.t3.large`; the code also defines a Training Job mode on `ml.m5.large`. The 25 September deployment used Processing because the account's `ml.m5.large` quota was zero. The trainer may take a stratified subset (`TrainRows`): recorded runs used 30,000 RF rows, 8,000 SVM rows and 30,000 XGBoost rows. XGBoost ensures `xgboost-cpu==2.1.4`. The trainer saves `model.pkl`, `preprocessor.joblib`, `validation_metrics.json` and, for the Processing route with an inference script, `model.tar.gz`. See [training source](../src/sagemaker_train.py#L29-L90).
4. [EvaluateOnOfficialTest](../pipelines/register_pipeline.py#L171-L192) loads that archive and scores all 22,544 untouched `KDDTest+` flows. [sagemaker_evaluate.py](../src/sagemaker_evaluate.py#L17-L63) writes `evaluation.json` with accuracy, binary positive-class precision/recall/F1, FPR and confusion counts. The official test is separate from the training/validation split.
5. [GateOfficialTestF1](../pipelines/register_pipeline.py#L194-L235) registers the model only if the official-test F1 is **at least 0.70**. Its package includes the model archive, a separately packaged inference module, and the evaluation report; the package starts as `PendingManualApproval`. RF and SVM share the `bigdata-ids-dev-train` pipeline and classical package group; XGBoost defaults to its own pipeline and package group. See [pipeline selection](../pipelines/register_pipeline.py#L252-L307).
6. After a human approves a completed package, [deploy-endpoint.py](../scripts/deploy-endpoint.py#L28-L123) can create a Serverless endpoint. It checks AWS identity, package status and existing resource compatibility. It **does not update an existing endpoint** that points at a different config. The [inference hook](../inference/ids_inference.py#L13-L56) requires JSON `{"record": {...}}` with exactly 41 raw feature fields, applies the packaged scaler/encoder/feature indices, and returns `prediction`, `attack_probability`, `dataset_id` and `dataset_version`. [smoke-endpoint.py](../scripts/smoke-endpoint.py#L18-L64) sends one official-test row.

The [manual GitHub workflow](../.github/workflows/aws-train.yml#L1-L78) checks OIDC identity and an existing pipeline by default. With `start_training=true`, it starts the selected pipeline with RF/XGBoost 30,000 rows or SVM 8,000 rows. It does not deploy a new definition, wait for completion, approve a package or change an endpoint.

## AWS path 2: LSTM

1. [PreprocessOrderedNSLKDD](../pipelines/register_lstm_pipeline.py#L28-L47) reads the same raw S3 files but uses `--ordered-split`: the first 80% of `KDDTrain+` rows become training and the remaining 20% validation. It fits the same 25-feature transform on training rows only and keeps all official `KDDTest+` rows for evaluation.
2. [TrainAndEvaluateLSTM](../pipelines/register_lstm_pipeline.py#L52-L74) is a TensorFlow **Processing** step, not a SageMaker Training Job. [make_windows](../src/sagemaker_lstm.py#L22-L30) groups each split into non-overlapping windows of 20 rows and labels each window using its **last** row. The recorded run limited training to 40,000 flows (2,000 windows). Official `KDDTest+` contributed 22,540 flows (1,127 windows); four leftover rows were dropped. NSL-KDD file order has not been shown to be network time order, so this is a file-order sequence experiment.
3. [sagemaker_lstm.py](../src/sagemaker_lstm.py#L50-L131) reuses the two-layer LSTM architecture from `LSTMIDS`, trains for up to 12 epochs with batch size 256 and early stopping patience 3, scores validation and official-test windows, and writes one `evaluation.json`. It saves `model.keras`, TensorFlow SavedModel directory `1/`, `preprocessor.joblib`, `training_metadata.json` and `model.tar.gz`.
4. The pipeline itself stops there. After a successful execution, [register-lstm-package.py](../scripts/register-lstm-package.py#L28-L94) locates the model and evaluation S3 outputs, verifies they exist, and creates a **separate** TensorFlow package with `PendingManualApproval`. There is no automatic F1 threshold. The script checks the most recent 20 packages for the same model URI before creating another.
5. After approval, the same [endpoint deployment script](../scripts/deploy-endpoint.py#L28-L123) can create a Serverless endpoint with an LSTM-specific name and memory setting. TensorFlow Serving expects JSON `{"instances": [<one 20 x 25 tensor>]}`. [smoke-lstm-endpoint.py](../scripts/smoke-lstm-endpoint.py#L24-L89) fetches `preprocessor.joblib` from the selected package, transforms 20 official-test rows on the client, invokes the endpoint and compares the result with the last row's label. It retries only a specific no-response `ModelError`, up to four attempts. The recorded deployment noted intermittent no-response errors, so the endpoint demonstrates inference but not production reliability.

The [manual GitHub workflow](../.github/workflows/aws-train.yml#L52-L78) starts an already deployed LSTM pipeline with 40,000 maximum training flows and 12 epochs when `start_training=true`; it does not register or approve the resulting package.

## Recorded AWS results and comparison rules

The table below reproduces the completed runs documented in [AWS deployment status](aws-deployment-status.md#model-evidence), last reported on **25 September 2026**. It is not a live AWS query.

| Model | Fit input in recorded run | Official-test unit | Accuracy | F1 | FPR | Recorded serving status |
|---|---:|---|---:|---:|---:|---|
| Random Forest | 30,000 training flows | 22,544 flows | 0.776836 | 0.762453 | 0.028009 | RF Serverless endpoint `InService` |
| SVM | 8,000 training flows | 22,544 flows | 0.726623 | 0.706118 | 0.075584 | Approved package; no dedicated SVM endpoint recorded |
| XGBoost | 30,000 training flows | 22,544 flows | 0.783046 | 0.770881 | 0.029451 | XGBoost Serverless endpoint `InService` |
| LSTM | 40,000 training flows / 2,000 windows | 1,127 windows | 0.740018 | 0.718540 | 0.057377 | LSTM Serverless endpoint `InService` |
| Autoencoder | No AWS training path | — | — | — | — | Local code only |

Compare RF, SVM and XGBoost on the same **flow-level official test** with their training-row limits shown. LSTM metrics use **window-level labels**, so its F1/FPR are not directly comparable with flow-level scores. The local experiment uses a different source/split/transform and, for LSTM, the opposite window label rule. Do not substitute local holdout results or README research figures for these AWS measurements. These differences are documented in [deployment status](aws-deployment-status.md) and visible in [the two preprocess modes](../src/sagemaker_preprocess.py#L72-L103).

## Verified code limits and documentation traps

- **The local five-model driver does not currently start.** [train_mlflow.py](../src/train_mlflow.py#L38) imports `compute_all_metrics` from `evaluate.py`, but [evaluate.py](../src/evaluate.py#L56-L149) defines `evaluate_model` and related functions, not `compute_all_metrics`. Python raises an import error before data loading or training. The pipeline above describes the intended calls, not a verified successful local run.
- **The local holdout is not leakage-safe.** Its first scaling fit, SMOTE and RFECV happen before the 80/20 split. Re-fitting a second scaler after the split does not undo information already used by oversampling or feature selection. Use the independent AWS `KDDTest+` results for the recorded capstone evaluation. See [run_pipeline](../src/preprocess.py#L430-L477).
- **The local auxiliary multiclass labels need separate validation.** [run_pipeline](../src/preprocess.py#L442-L460) runs SMOTE again on five-class labels and then indexes those labels with indices from the binary-resampled feature matrix. Those separately generated samples are not guaranteed to align; the four arrays loaded by the MLflow driver are the binary arrays only.
- **Local LSTM labels and API semantics differ from AWS.** [LSTMIDS.train](../src/models.py#L211-L241) takes the first label of each reshaped window; AWS [make_windows](../src/sagemaker_lstm.py#L22-L30) takes the last. Local preprocessing has also shuffled rows before constructing windows. The FastAPI default is LSTM but `/predict/single` supplies only one row; the wrapper requires a complete 20-row window. `/predict` returns one prediction per complete window rather than one per submitted row.
- **Comments and metadata are not measurements.** The `train_mlflow.py` header mentions automatic best-model promotion, but the driver has no promotion step. Its Autoencoder parameter string begins with `41` although the constructed input dimension comes from the selected feature array. The FastAPI model metadata and README high accuracy figures are inherited research values. See [driver](../src/train_mlflow.py#L10-L20), [Autoencoder trainer](../src/train_mlflow.py#L201-L210), and [API metadata](../api/serve.py#L65-L75).
- **AWS status is dated.** The documented AWS runs and endpoints were checked on 25 September 2026. This guide does not assert their current state. The classical code has a Training Job branch, but the recorded fits used SageMaker Processing because of the account quota. The AWS LSTM and Autoencoder are not the same deployment story: LSTM has a Processing pipeline, package and endpoint; Autoencoder has no AWS path here.
