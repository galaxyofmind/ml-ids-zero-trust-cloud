# Runbook triển khai AWS: Big Data + MLOps + Cybersecurity

**Phiên bản:** 1.0 — 25/09/2026  
**Trạng thái:** hướng dẫn triển khai, **chưa thực thi trên tài khoản AWS**  
**Tài liệu kiến trúc:** [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md)  
**Hướng dẫn cho người mới:** [BEGINNER_AWS_GITHUB_GUIDE.md](./BEGINNER_AWS_GITHUB_GUIDE.md)  
**Môi trường làm việc:** Windows, PowerShell 7, AWS CLI v2; một AWS account và một Region cho bản demo.

## 1. Cách dùng tài liệu và phân công

Runbook này chốt đường ngắn nhất để có demo đầu cuối, sau đó mở rộng. Dịch vụ được tạo bằng **AWS CloudFormation**; các bước dữ liệu/ML được chạy bằng script Python và SageMaker Pipelines; PowerShell/AWS CLI v2 dùng để điều khiển và kiểm tra. Region mặc định đề xuất là `ap-southeast-1` (Singapore), được [AWS liệt kê là Region hỗ trợ MLflow App](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow.html). Quota, quyền tài khoản và giá thực tế vẫn phải kiểm tra trước khi tạo tài nguyên.

**Ký hiệu phân công:**

- **Bạn — thủ công:** việc gắn với danh tính, thanh toán, MFA, email, lựa chọn học thuật hoặc chấp nhận chi phí. Tôi có thể hướng dẫn và kiểm tra kết quả, nhưng bạn phải tự hoàn tất bước tương tác.
- **Tôi — tự động được:** đọc/sửa repo, viết IaC/script/test, kiểm tra cấu hình, và sau khi có AWS session hợp lệ thì chạy CLI để tạo tài nguyên/job, đọc log, sửa lỗi và thu bằng chứng. Khả năng thao tác AWS phụ thuộc quyền của session hiện có; tài liệu này **không ngụ ý đã có quyền hoặc đã triển khai**.
- **Phối hợp:** tôi chuẩn bị thay đổi/lệnh và kết quả kiểm tra; bạn cung cấp quyết định hoặc xác nhận email/MFA. Khi triển khai thật, mọi resource tạo ra có thể phát sinh chi phí.

### 1.1 Các việc bạn bắt buộc làm thủ công

| Mã | Việc của bạn | Cần hoàn tất trước | Đầu ra giao lại cho tôi |
|---|---|---|---|
| U01 | Có AWS account hoạt động, phương thức thanh toán và người quản trị Billing; bật MFA cho danh tính quản trị. | Bước 2 | Account ID (12 số), không gửi mật khẩu/MFA code. |
| U02 | Cấp cho nhóm một IAM Identity Center permission set hoặc quyền triển khai tương đương; đăng nhập qua browser/MFA bằng `aws sso login`. | Bước 2 | Tên AWS CLI profile, Region, kết quả `sts get-caller-identity` đã che thông tin không cần thiết. |
| U03 | Chốt **mức ngân sách thực tế**, người nhận cảnh báo, thời hạn giữ tài nguyên; tạo hoặc cho phép tạo AWS Budget. Budget là cảnh báo theo dữ liệu Billing, **không phải trần cứng tức thời**. | Trước khi chạy job có phí | Con số ngân sách, email nhận cảnh báo, ngày dọn tài nguyên. [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/create-cost-budget.html), [tần suất cập nhật](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html). |
| U04 | Chọn repo GitHub của nhóm và quyền truy cập; nếu dùng repo tham khảo thì giữ thông tin bản quyền/nguồn. | Bước 3 | URL repo của nhóm hoặc xác nhận dùng workspace local. |
| U05 | Chấp nhận điều kiện sử dụng dataset, tải dataset nếu trang nguồn yêu cầu thao tác người dùng; xác nhận dataset thứ hai là UNSW-NB15. | Bước 5, 10 | File nguồn/đường dẫn hoặc URL được phép tải, citation cần ghi. |
| U06 | Chốt tiêu chí học thuật **trước khi xem test**: recall/FPR mục tiêu, attack class ưu tiên, seed/split, mức dataset thứ hai. | Trước bước 7 | Một bảng tiêu chí và ngưỡng. |
| U07 | Xác nhận đăng ký email SNS/Budget bằng link trong hộp thư. | Bước 4, 9 | Trạng thái `Confirmed`. |
| U08 | Nếu muốn bật GitHub Actions deploy: chấp nhận GitHub OIDC/GitHub Environment, branch được deploy và quy tắc review của nhóm. | Bước 11 | Owner/repo/branch/environment cụ thể. |
| U09 | Quyết định lưu hay xóa dataset, model, log và bucket sau buổi bảo vệ; việc xóa dữ liệu là quyết định sở hữu của nhóm. | Bước 13 | Danh sách cần giữ và ngày xóa. |

**Không gửi access key, secret key, mật khẩu, token hay MFA code trong chat hoặc commit Git.** Nếu bạn chỉ có IAM user key, chuyển sang session ngắn hạn/SSO khi tài khoản cho phép. [AWS CLI IAM Identity Center](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).

### 1.2 Những việc tôi có thể tự động hóa

| Mã | Việc tôi làm được | Điều kiện | Bằng chứng đầu ra |
|---|---|---|---|
| A01 | Import/audit repo tham khảo; tách mã preprocessing, train, evaluate, inference và drift; giữ LICENSE/citation. | Có quyền đọc repo. | Commit, bảng khác biệt, test local. |
| A02 | Viết CloudFormation cho S3, IAM, Glue, Athena, Firehose, SageMaker, EventBridge, SNS, CloudWatch; validate và xem change set. | Có thông số Region/account/naming. | Template, kết quả validate/change set. |
| A03 | Viết script PowerShell 7 để deploy, upload data, start job, poll trạng thái, xuất evidence và cleanup. | AWS CLI v2, session hợp lệ khi chạy cloud. | Script và log chạy. |
| A04 | Viết Glue ETL, schema/manifest, kiểm tra chất lượng, truy vấn Athena; chạy sau khi có quyền. | Dataset + AWS role. | Parquet, Catalog, SQL result. |
| A05 | Đóng gói năm model vào SageMaker Processing/Training/Pipelines, MLflow App và Model Registry; chạy thử và sửa lỗi. | Quota, role, budget, U06. | Pipeline execution ARN, MLflow run, Model Package ARN, metric tự đo. |
| A06 | Tạo một endpoint serverless, Batch Transform, script kiểm thử payload/latency; rollback khi có lỗi. | Model đã được duyệt, quota. | Endpoint status, prediction, batch output. |
| A07 | Tạo pipeline drift, EventBridge Scheduler, metric/alarm; kiểm thử cảnh báo. | Email U07 đã xác nhận để nhận được thông báo. | Drift report, alarm/event. |
| A08 | Viết GitHub Actions dùng OIDC, chạy kiểm tra CI và deploy từ branch cho phép. | U04/U08 và quyền sửa repo/AWS IAM. | Workflow run, IAM trust policy đã giới hạn. |
| A09 | Thu log, chi phí thực, ảnh minh chứng, bảng kết quả và runbook vận hành. | Các job đã chạy. | Báo cáo có ARN/Region/run ID/số liệu tái lập. |

## 2. Giá trị cấu hình dùng xuyên suốt

Tạo `configs/dev.psd1` hoặc một file cấu hình tương đương **không chứa secret**. Các tên sau là ví dụ và sẽ được đổi theo account/Region. Không tạo thủ công các bucket/role có cùng tên với CloudFormation.

| Biến | Ví dụ | Ghi chú |
|---|---|---|
| `Project` | `bigdata-ids` | Prefix và tag. |
| `Environment` | `dev` | Chỉ một môi trường cho MVP. |
| `Region` | `ap-southeast-1` | Kiểm tra dịch vụ/quota trong account. |
| `Profile` | `capstone-dev` | CLI profile SSO; không lưu key trong file dự án. |
| `BudgetAmount` | *bạn điền* | Đơn vị tiền tệ theo AWS Budget. |
| `NotificationEmail` | *bạn điền* | Người nhận tự xác nhận subscription. |
| `DatasetVersion` | `nsl-kdd-v1` | Gắn vào manifest/MLflow/Registry. |
| `GitSha` | commit SHA | Cố định mã của từng run. |

Tất cả tài nguyên gắn tag `Project`, `Environment`, `Owner`, `ExpiresOn`; tên vật lý nên do CloudFormation sinh hoặc có account/Region để tránh trùng. Stack tách thành `foundation`, `data`, `ml`, `monitoring`, giúp cập nhật/cleanup theo phụ thuộc.

## 3. Trình tự triển khai chi tiết

### Bước 0 — Chốt phạm vi demo và cổng chi phí

**Chủ trì:** bạn (U03, U06); tôi có thể lập bảng lựa chọn và ước tính.  
**Làm:** chốt Region, ngân sách, email, ngày dọn, dataset thứ hai, ngưỡng metric và một mô hình online. Mặc định triển khai RF/XGBoost trước, chọn một trong hai sau benchmark; năm mô hình đều phải được huấn luyện/đánh giá trên NSL-KDD. Chạy UNSW-NB15 qua ETL/Athena và train baseline riêng; không gộp feature với NSL-KDD.  
**Xong khi:** `configs/dev.psd1` có đủ giá trị không bí mật; `docs/acceptance-criteria.md` ghi các ngưỡng trước khi chạy test; ngân sách được tạo và người nhận đã biết cách xử lý cảnh báo.

### Bước 1 — Chuẩn bị Windows và xác minh danh tính AWS

**Bạn thủ công:** U01/U02 và đăng nhập browser/MFA. **Tôi tự động:** kiểm tra phiên bản, Region, quyền đọc cơ bản; ghi lại checklist thiếu quyền.

Trong PowerShell 7:

```powershell
pwsh --version
aws --version
git --version
python --version
aws configure sso --profile capstone-dev   # chạy một lần; nhập SSO URL/account/role của bạn
aws sso login --profile capstone-dev        # mở browser, bạn tự hoàn tất MFA
$env:AWS_PROFILE = "capstone-dev"
$env:AWS_DEFAULT_REGION = "ap-southeast-1"
aws sts get-caller-identity
```

`aws --version` trên máy hiện tại đã được kiểm tra là **AWS CLI 2.37.3**; chưa kiểm tra đăng nhập hay quyền AWS của tài khoản. SSO có thể do quản trị viên tổ chức cấu hình. Nếu account không có Identity Center, dùng phương thức session ngắn hạn được quản trị viên cho phép; không đưa static key vào repo. [AWS CLI SSO](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).

**Kiểm tra:** `Account` đúng, `Arn` không phải root, Region đúng; thử liệt kê CloudFormation/S3/SageMaker và quota liên quan. Nếu `AccessDenied`, ghi chính xác action/resource thiếu để người quản trị cấp quyền có phạm vi, không cấp `AdministratorAccess` cho job runtime.

### Bước 2 — Dựng source và các file triển khai

**Tôi tự động:** A01/A03. Clone hoặc import mã repo tham khảo vào repo của nhóm, giữ MIT LICENSE, pin dependency; bổ sung `configs/`, `infra/`, `src/data/`, `src/ml/`, `src/monitoring/`, `pipelines/`, `scripts/`, `.github/workflows/`. Tạo unit test cho hợp đồng feature/label và smoke test container. Dùng một cấu trúc package Python thống nhất để script local và SageMaker job gọi cùng hàm lõi.

**Kiểm tra bắt buộc trước port:** xác nhận đầu vào Autoencoder (README mô tả 41 feature ở kiến trúc nhưng 25 feature ở API), thứ tự feature cho cả năm model, cách tạo sequence của LSTM, phân tách train/test trước OHE/scaler/RFECV/SMOTE, và dữ liệu test không dùng để chọn hyperparameter. Mỗi lỗi được ghi thành issue/ADR; không đưa kết quả README vào báo cáo capstone như số tự đo. [Repo tham khảo](https://github.com/machetheDM/ml-ids-zero-trust-cloud).

**Xong khi:** test local chạy được, có `requirements.lock`/version pin, schema JSON của request và manifest mẫu; vẫn chưa cần AWS resource.

### Bước 3 — CloudFormation foundation: lưu trữ, quyền, audit, budget

**Tôi tự động:** A02; **bạn thủ công:** ngân sách U03 và quyền IAM/CloudFormation nếu account do người khác quản trị. CloudFormation tạo bucket data/artifact và Athena result (có thể cùng bucket với prefix riêng), S3 Block Public Access, mã hóa, versioning, bucket policy chỉ TLS, log group/retention, IAM role riêng cho Firehose, Glue, SageMaker Processing/Training/Pipeline, endpoint, Scheduler, CI. Bật CloudTrail/GuardDuty **chỉ sau khi kiểm tra** account/organization đã quản lý sẵn; tránh tạo bản trùng và chi phí ngoài dự kiến. Budget tạo qua IaC/API khi principal có Billing permission, nếu không bạn tạo trong Billing console.

Policy cần giới hạn S3 prefix và `iam:PassRole` theo role ARN/service. Trust policy service role thêm `aws:SourceAccount`/`aws:SourceArn` khi dịch vụ hỗ trợ; GitHub OIDC giới hạn `aud`, owner/repo/branch/environment. [AWS IAM role guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html), [GitHub OIDC trust](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html).

Sau khi tôi tạo file `infra/foundation.yaml`, chạy từ PowerShell:

```powershell
aws cloudformation validate-template --template-body file://infra/foundation.yaml
aws cloudformation deploy --template-file infra/foundation.yaml --stack-name bigdata-ids-dev-foundation --capabilities CAPABILITY_IAM --parameter-overrides Project=bigdata-ids Environment=dev
aws cloudformation describe-stacks --stack-name bigdata-ids-dev-foundation --query "Stacks[0].Outputs"
```

Lệnh deploy phía trên là **mẫu cho file sẽ được tạo ở bước này**, không chạy được trước khi có template và parameter tương ứng. Nếu template đặt tên role cố định, dùng `CAPABILITY_NAMED_IAM`. Trước deploy phải xem change set; không chạy Express mode cho resource cần trạng thái sẵn sàng ngay. [CloudFormation CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli_cloudformation_code_examples.html).

**Xong khi:** stack `CREATE_COMPLETE`/`UPDATE_COMPLETE`, output có bucket/role ARN, S3 public access bị chặn, budget alert hoạt động hoặc có bằng chứng bạn đã tạo Budget trong console.

### Bước 4 — Nạp dữ liệu gốc và tạo manifest

**Bạn thủ công:** U05 (nguồn và điều kiện sử dụng); **tôi tự động:** tải nếu nguồn cho phép, tính checksum, upload S3, tạo manifest. NSL-KDD là dataset chính. Với UNSW-NB15, sử dụng file train/test chính thức hoặc subset có seed và ghi tỷ lệ lấy mẫu. [Nguồn UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset).

Ví dụ PowerShell sau khi đã có file và bucket output từ stack:

```powershell
$bucketName = "ten-bucket-tu-stack-output"
$datasetFile = ".\data\KDDTrain+.txt"
Get-FileHash -Algorithm SHA256 -Path $datasetFile
aws s3 cp $datasetFile "s3://$bucketName/raw/dataset=nsl-kdd/version=v1/KDDTrain+.txt"
aws s3 ls "s3://$bucketName/raw/dataset=nsl-kdd/version=v1/"
```

Manifest `manifest.json` chứa nguồn, citation/license, checksum, byte size, số record sau parse, schema/label mapping, ngày ingest, `dataset_version`, `git_sha`. Giữ file raw bất biến; lỗi parse vào `quarantine/` kèm lý do. Không truyền nhãn vào input suy luận.

**Xong khi:** checksum local/manifest khớp, S3 có đúng file và metadata, không upload `mlruns/`, virtualenv, key hay log nhạy cảm.

### Bước 5 — Data lake: Firehose, Glue, Catalog, Athena

**Tôi tự động:** A02/A04. Stack `data` tạo Firehose Direct PUT → S3 `raw/replay/`, Glue database và ETL job, Athena workgroup/result location. Script replay trên Windows chuyển **một tập con flow lịch sử** thành JSON Lines, thêm `flow_id`, `dataset_id`, `ingest_time`, rồi gọi `PutRecordBatch`. Xử lý `FailedPutCount` và retry đúng các record thất bại; dùng `flow_id` khử trùng lặp ở ETL vì retry có thể sinh bản sao. Firehose chỉ dùng cho demo ingest streaming, upload bulk vẫn đi thẳng S3. [AWS Firehose PutRecordBatch](https://docs.aws.amazon.com/cli/latest/reference/firehose/put-record-batch.html).

Glue ETL đọc từng dataset bằng schema riêng, chuẩn hóa label, tách bản ghi lỗi, xuất Parquet sang `curated/dataset=<id>/year=.../month=.../day=.../`; cập nhật Data Catalog. Không chạy crawler trên một root chứa lẫn schema NSL-KDD và UNSW-NB15. [Athena/Glue crawler](https://docs.aws.amazon.com/athena/latest/ug/schema-crawlers.html), [Athena partitions](https://docs.aws.amazon.com/athena/latest/ug/partitions.html).

Lệnh vận hành sau khi tôi đã tạo job/bảng:

```powershell
$jobName = "bigdata-ids-dev-etl-nsl"
$jobRunId = aws glue start-job-run --job-name $jobName --query JobRunId --output text
aws glue get-job-run --job-name $jobName --run-id $jobRunId --query "JobRun.{State:JobRunState,Error:ErrorMessage}"
aws glue get-tables --database-name bigdata_ids_dev --query "TableList[].Name"
```

Kiểm tra Athena bằng query `COUNT(*)`, phân bố `binary_label`, `COUNT(DISTINCT flow_id)`, số dòng null/lỗi, ngày partition và lượng dữ liệu quét. **Xong khi:** Glue `SUCCEEDED`, hai table không trộn schema, query theo partition đọc được Parquet, report đối chiếu số record raw/curated/quarantine.

### Bước 6 — SageMaker Processing và split có thể tái lập

**Tôi tự động:** A05; **bạn thủ công:** U06 đã phải chốt metric trước. Processing job đọc curated NSL-KDD và manifest; tạo train/validation/test cố định. Fit encoder, scaler, selector và SMOTE **chỉ trên train**; áp dụng đúng object/feature order cho validation/test. Lưu `preprocessor`, label map, feature names, seed, split manifest và báo cáo leakage/duplicates trên S3. UNSW-NB15 có nhánh preprocessing riêng.

**Xong khi:** có URI cho từng split, kiểm tra train/val/test không giao nhau theo `flow_id` hoặc session key phù hợp, vector feature đồng nhất với hợp đồng của từng model, transform thử một record mới thành công. Nếu LSTM không có chuỗi thời gian được xác định hợp lệ, không mô tả nó như phát hiện hành vi theo thời gian.

### Bước 7 — Pipeline huấn luyện, MLflow và Model Registry

**Tôi tự động:** A05. Stack `ml` tạo artifact locations/role và MLflow App **nếu quota/Region cho phép**. Dùng API `CreateMlflowApp`, không dùng legacy Tracking Server. Mã train log `dataset_version`, `git_sha`, seed, package versions, hyperparameters, metrics, artifact URI. Model Registry lưu version gắn evaluation report và preprocessor. [AWS MLflow App](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow-app-setup.html), [CLI `create-mlflow-app`](https://docs.aws.amazon.com/cli/latest/reference/sagemaker/create-mlflow-app.html).

SageMaker Pipeline chính gồm:

1. `ProcessingStep`: split/preprocess và ghi manifest.
2. `TrainingStep`: ban đầu RF và XGBoost; sau đó SVM, LSTM, Autoencoder (sequential hoặc parallel theo quota).
3. `ProcessingStep`: evaluate từng model trên test khóa; xuất JSON và confusion matrix.
4. `ConditionStep`: so metric với ngưỡng U06; không đạt thì dừng trước Registry.
5. `RegisterModel`: lưu các bản đạt gate với `PendingManualApproval` hoặc trạng thái tương đương; chỉ bản được duyệt mới deploy.

Lệnh chạy/kiểm tra sau khi `pipelines/register_pipeline.py` đã tạo pipeline:

```powershell
$pipelineName = "bigdata-ids-dev-train"
$runArn = aws sagemaker start-pipeline-execution --pipeline-name $pipelineName --query PipelineExecutionArn --output text
aws sagemaker describe-pipeline-execution --pipeline-execution-arn $runArn --query "{Status:PipelineExecutionStatus,Failure:FailureReason}"
aws sagemaker list-pipeline-execution-steps --pipeline-execution-arn $runArn
```

**Xong khi:** run thành công, MLflow run và Model Package ARN liên kết đúng version/dataset/commit; có metric **do capstone chạy lại**. Số trong README repo chỉ nằm ở cột tham khảo riêng. Nếu MLflow App chưa sẵn có, pipeline/Registry vẫn chạy; ghi rõ thiếu chức năng tracking UI và không giả vờ đã tích hợp.

### Bước 8 — Suy luận tương tác và batch

**Tôi tự động:** A06; **bạn thủ công:** chọn champion từ bảng đánh giá/chi phí sau bước 7. Đóng gói `model + preprocessor + schema` thành artifact cố định. Tạo một SageMaker Serverless endpoint cho RF hoặc XGBoost đã đo kích thước/cold start. Dùng Batch Transform cho đủ năm mô hình, không giữ năm endpoint trực tuyến. Các model lớn hoặc cần GPU không bị ép lên serverless. SageMaker Serverless không có data capture/Model Monitor tích hợp; tự ghi request/prediction có kiểm soát vào S3. [AWS hosting options](https://docs.aws.amazon.com/sagemaker/latest/dg/hosting-faqs.html), [feature matrix](https://docs.aws.amazon.com/sagemaker/latest/dg/model-deploy-feature-matrix.html).

Lệnh smoke test sau khi tôi đã tạo `configs/sample-request.json` và endpoint:

```powershell
$endpointName = "bigdata-ids-dev-champion"
aws sagemaker describe-endpoint --endpoint-name $endpointName --query "EndpointStatus"
aws sagemaker-runtime invoke-endpoint --endpoint-name $endpointName --content-type application/json --body fileb://configs/sample-request.json .\prediction.json
Get-Content .\prediction.json
```

Thử thêm payload sai schema, thiếu feature, NaN và model version không khớp; phản hồi phải từ chối rõ. Batch output gồm `flow_id`, label/score, model version, dataset/split và run ID để so sánh. **Xong khi:** endpoint `InService`, một prediction đúng, một request sai bị từ chối, năm batch result có thể nối với nhãn test.

### Bước 9 — Drift, cảnh báo và an ninh tài khoản

**Tôi tự động:** A07/A09; **bạn thủ công:** U07 xác nhận email. Pipeline drift riêng lấy cửa sổ input/prediction S3, so với reference **cùng dataset/schema/preprocessor**, tính PSI và tỷ lệ nhãn dự đoán; performance drift chỉ tính khi có nhãn thật. EventBridge Scheduler gọi `StartPipelineExecution` theo lịch; job ghi metric CloudWatch, alarm gửi SNS. Ngưỡng PSI của repo (`0,10`/`0,25`) chỉ là khởi điểm demo, hiệu chỉnh theo mẫu. [AWS schedule pipeline](https://docs.aws.amazon.com/sagemaker/latest/dg/pipeline-eventbridge.html).

CloudWatch alarm khác theo dõi lỗi endpoint, lỗi Glue/Pipeline và log; CloudTrail/GuardDuty là bằng chứng bảo vệ **tài khoản AWS**, không phải nhãn xâm nhập của dataset. Không tạo cảnh báo GuardDuty giả rồi gọi đó là độ chính xác IDS. Nếu account mới, không dựa vào SageMaker Model Monitor: AWS hiện ghi dịch vụ này [không mở cho khách hàng mới](https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor-data-capture-endpoint.html); pipeline PSI riêng vẫn đáp ứng mục tiêu.

**Xong khi:** có một cửa sổ stable và một cửa sổ drift giả lập; report S3 + metric CloudWatch + email đã nhận; nhóm ghi rõ người xử lý và không auto deploy lại model.

### Bước 10 — Dataset thứ hai và chứng minh Big Data

**Bạn thủ công:** xác nhận quyền dùng UNSW-NB15 và kích thước/subset; **tôi tự động:** A04/A05. Upload raw, checksum/manifest, Glue ETL/Parquet/Catalog, Athena query phân bố nhãn và thời gian scan. Huấn luyện RF/XGBoost baseline **mới** trên schema UNSW-NB15 hoặc làm thí nghiệm độc lập; không nạp 49 feature UNSW vào model NSL-KDD 25 feature. Nếu có thời gian, thêm CIC-IDS2017 CSV và so sánh đặc trưng/khối lượng. [UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset), [CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html).

**Xong khi:** báo cáo có số record/GB thực, thời gian ETL/SQL/Training, lỗi dữ liệu và chi phí theo job. Ghi rõ dataset nhỏ không tự chứng minh throughput production.

### Bước 11 — CI/CD và tái triển khai

**Tôi tự động:** A08; **bạn thủ công:** U04/U08. Workflow CI chạy lint/test/schema check/CloudFormation validation khi PR; workflow deploy chạy từ branch/environment được cho phép, dùng GitHub OIDC assume AWS role, không có static access key. Chỉ deploy IaC/code; dữ liệu/model release đi qua Pipeline/Registry và bước duyệt. GitHub OIDC role phải giới hạn `token.actions.githubusercontent.com:sub` cho đúng owner/repo/branch hoặc environment. [AWS IAM OIDC](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html).

**Xong khi:** một PR lỗi test bị chặn; một run hợp lệ cho thấy commit → artifact → pipeline/model version; role OIDC không assume được từ nhánh ngoài phạm vi.

### Bước 12 — Diễn tập demo, thu bằng chứng và rollback

**Tôi tự động:** A09; **bạn thủ công:** trình bày/đánh giá kết quả, chọn nội dung đưa vào báo cáo. Diễn tập đúng thứ tự: S3 raw → Glue/Parquet → Athena → Pipeline/MLflow/Registry → một request serverless → batch năm model → drift/cảnh báo → CloudTrail/GuardDuty → dashboard chi phí. Mọi ảnh/log ghi Region, account (che khi chia sẻ công khai), UTC timestamp, resource name, run ID, dataset/commit version.

Rollback: giữ Model Package/endpoint config trước; nếu model mới lỗi thì cập nhật endpoint về package đã duyệt, chạy lại smoke test; nếu stack lỗi thì xem CloudFormation events và sửa template, tránh sửa tay resource do stack quản lý. Kiểm tra backup/manifest trước mọi thao tác xóa.

**Xong khi:** có bảng kết quả tự đo và tài liệu `docs/results.md`, `docs/cost.md`, `docs/demo-script.md`, `docs/operations.md`; lặp lại demo bằng script được.

### Bước 13 — Dừng và dọn tài nguyên

**Bạn thủ công:** U09 quyết định dữ liệu nào giữ. **Tôi tự động:** liệt kê resource/tag, tính phụ thuộc, dừng lịch và xóa compute theo quyết định, kiểm tra resource còn lại. Dọn theo thứ tự: disable EventBridge Scheduler → xóa endpoint → xóa endpoint config/model không còn dùng → xóa MLflow App nếu không cần tracking UI/metadata → CloudFormation monitoring/ml/data/foundation theo thứ tự ngược → xử lý S3 retained objects sau khi bạn chốt. Xóa endpoint **không tự xóa** endpoint config/model; xóa MLflow App không đồng nghĩa xóa artifact S3. [AWS endpoint cleanup](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints-delete-resources.html).

Không chạy `aws s3 rm --recursive` hoặc xóa bucket trước khi kiểm tra bucket/stack/manifest và U09. Giữ bằng chứng học thuật ở vị trí bạn chọn, sau đó đối chiếu Billing/Cost Explorer cho ngày chạy. **Xong khi:** không còn endpoint/app/schedule/job chạy hoặc cảnh báo phát sinh ngoài dự kiến; danh sách tài nguyên retained được bàn giao.

## 4. Bản đồ artifact cần được tạo khi triển khai

**Các file dưới đây là bản đồ mục tiêu.** Một phần đã được triển khai trong repo fork; đối chiếu [trạng thái AWS thực tế](./ml-ids-zero-trust-cloud/docs/aws-deployment-status.md) trước khi chạy lệnh hoặc giả định một artifact đã tồn tại.

```text
configs/dev.psd1
configs/sample-request.json
configs/datasets/nsl-kdd.yaml
configs/datasets/unsw-nb15.yaml
infra/foundation.yaml
infra/data.yaml
infra/ml.yaml
infra/monitoring.yaml
scripts/deploy.ps1
scripts/ingest.ps1
scripts/run-demo.ps1
scripts/collect-evidence.ps1
scripts/cleanup.ps1
src/data/manifest.py
src/data/etl.py
src/ml/preprocess.py
src/ml/train.py
src/ml/evaluate.py
src/ml/inference.py
src/monitoring/drift.py
pipelines/register_pipeline.py
pipelines/register_drift_pipeline.py
docs/acceptance-criteria.md
docs/results.md
docs/cost.md
docs/demo-script.md
docs/operations.md
```

## 5. Cổng kiểm tra trước mỗi lần chạy có phí

1. `aws sts get-caller-identity` và Region đúng; SSO session chưa hết hạn.
2. Budget và email cảnh báo đã được cấu hình; biết job nào có thể chạy lâu.
3. CloudFormation change set, IAM role và S3 prefix đã được xem; không có resource ngoài phạm vi.
4. Dataset manifest/checksum, seed/split, schema và metric gate đã cố định.
5. Chỉ chạy **một** thử nghiệm nhỏ trước; đọc log/cost rồi mới tăng dataset hoặc thêm model.
6. Có script dừng/cleanup, người chịu trách nhiệm và thời hạn `ExpiresOn`.

## 6. Rủi ro cần ghi thẳng trong báo cáo

| Rủi ro | Cách xử lý/bằng chứng |
|---|---|
| Chênh lệch số liệu so với README tác giả | Ghi phiên bản dữ liệu, split, seed, preprocessing, thư viện, instance; trình bày kết quả capstone riêng. |
| Leakage từ preprocessing hoặc record trùng | Split trước fit/SMOTE/RFECV; kiểm tra giao nhau theo flow/session; giữ test khóa. |
| LSTM không có chuỗi thời gian thật | Chỉ gọi là temporal khi sequence construction và split theo phiên/thời gian được chứng minh. |
| Khác schema giữa NSL-KDD và UNSW-NB15 | ETL/model branch riêng; không gọi kết quả trên UNSW là zero-shot của model NSL nếu chưa có feature mapping hợp lệ. |
| Serverless cold start/bộ nhớ | Benchmark RF/XGBoost, giữ Batch Transform làm đường demo chắc chắn. |
| Budget cảnh báo chậm | Theo dõi tài nguyên chạy trực tiếp; đặt timeout/job limit; dọn endpoint/app ngay sau demo. |
| IAM/quota/Region chặn deployment | Kiểm tra từ bước 1; báo chính xác quyền/quota thiếu; đổi Region chỉ sau khi đánh giá dữ liệu và chi phí. |

## 7. Nguồn AWS chính dùng cho runbook

- [AWS CLI Identity Center](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html), [CloudFormation CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli_cloudformation_code_examples.html), [IAM OIDC cho GitHub](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html).
- [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/create-cost-budget.html), [Budgets best practices](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html).
- [SageMaker Pipelines](https://docs.aws.amazon.com/sagemaker/latest/dg/pipelines-overview.html), [MLflow App](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow-app-setup.html), [schedule pipeline](https://docs.aws.amazon.com/sagemaker/latest/dg/pipeline-eventbridge.html), [hosting options](https://docs.aws.amazon.com/sagemaker/latest/dg/hosting-faqs.html), [feature matrix](https://docs.aws.amazon.com/sagemaker/latest/dg/model-deploy-feature-matrix.html).
- [AWS Glue StartJobRun](https://docs.aws.amazon.com/cli/latest/reference/glue/start-job-run.html), [Firehose PutRecordBatch](https://docs.aws.amazon.com/cli/latest/reference/firehose/put-record-batch.html), [Athena partitions](https://docs.aws.amazon.com/athena/latest/ug/partitions.html).
