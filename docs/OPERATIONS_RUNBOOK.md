# Operations runbook — sử dụng và vận hành IDS demo

**Môi trường:** AWS account `101728439989`, `ap-southeast-1`, PowerShell 7, AWS CLI v2; repo fork `galaxyofmind/ml-ids-zero-trust-cloud`. Tài liệu này dùng cho buổi demo và xử lý sự cố. Trạng thái chụp ngày 25-09-2026 xem [deployment report](DEPLOYMENT_REPORT.md). Các lệnh có nhãn **đọc** không tạo job; lệnh **ghi/chạy** có thể phát sinh phí.

## 1. Trước mỗi buổi demo — kiểm tra không tạo job

Chạy tại repo root. Profile `default` đã được xác nhận là root trong đợt triển khai; profile khác dùng được nếu có quyền tương ứng. Không đặt khóa truy cập trong script/terminal history.

```powershell
$awsProfile = 'default'
$awsRegion = 'ap-southeast-1'
$expectedAccount = '101728439989'
$identity = aws sts get-caller-identity --profile $awsProfile --region $awsRegion --output json | ConvertFrom-Json
if ($identity.Account -ne $expectedAccount) { throw "Sai account: $($identity.Account)" }
$identity.Arn

@('bigdata-ids-dev-foundation','bigdata-ids-dev-data','bigdata-ids-dev-github-oidc','bigdata-ids-dev-monitoring') | ForEach-Object {
  aws cloudformation describe-stacks --stack-name $_ --profile $awsProfile --region $awsRegion --query 'Stacks[0].{Name:StackName,Status:StackStatus}'
}
@('bigdata-ids-dev-rf','bigdata-ids-dev-xgboost','bigdata-ids-dev-lstm') | ForEach-Object {
  aws sagemaker describe-endpoint --endpoint-name $_ --profile $awsProfile --region $awsRegion --query '{Name:EndpointName,Status:EndpointStatus,Failure:FailureReason}'
}
aws cloudwatch describe-alarms --alarm-names bigdata-ids-dev-monitoring-nsl-kdd-psi-critical --profile $awsProfile --region $awsRegion --query 'MetricAlarms[].{State:StateValue,Updated:StateUpdatedTimestamp}'
```

Kỳ vọng: bốn stack `*_COMPLETE`, ba endpoint `InService`. Alarm thường `OK`; nó có thể trở lại `OK` khi điểm dữ liệu dịch chuyển đã hết hiệu lực vì missing data được coi là không vi phạm. `ALARM` trong demo PSI chưa chứng minh có tấn công mạng.

## 2. Xem dữ liệu Big Data và bằng chứng ETL

**Đọc.** Dataset raw nằm ở `s3://bigdata-ids-dev-foundation-databucket-y4img8enauch/raw/`; curated Parquet ở `curated/nsl-kdd/v1/` và `curated/unsw-nb15/v1/`. Hai dataset có schema/bảng riêng.

```powershell
$dataBucket = 'bigdata-ids-dev-foundation-databucket-y4img8enauch'
aws s3 ls "s3://$dataBucket/raw/" --recursive --profile $awsProfile --region $awsRegion
aws s3 ls "s3://$dataBucket/curated/" --recursive --profile $awsProfile --region $awsRegion
aws glue get-job-run --job-name bigdata-ids-dev-data-nsl-kdd-etl --run-id jr_c72f74e817958313aaa8ca4a39d3da808648bf7c965baf94163b3756b89c5b96 --profile $awsProfile --region $awsRegion --query 'JobRun.{State:JobRunState,Error:ErrorMessage}'
aws glue get-job-run --job-name bigdata-ids-dev-data-unsw-nb15-etl --run-id jr_3159af64dd9a9d1da1caf03c404ce26567f8f5656a75005539d1b78c2b5a8076 --profile $awsProfile --region $awsRegion --query 'JobRun.{State:JobRunState,Error:ErrorMessage}'
aws athena get-query-results --query-execution-id d762e729-54c1-4ca9-8725-283203f89420 --profile $awsProfile --region $awsRegion --query 'ResultSet.Rows'
aws athena get-query-results --query-execution-id e3cb4685-5268-4df6-8290-1b346102b805 --profile $awsProfile --region $awsRegion --query 'ResultSet.Rows'
```

Kết quả đã lưu: NSL-KDD train 125.973 hàng, gồm 58.630 attack/67.343 normal; UNSW-NB15 train 175.341 hàng/10 nhóm class. Nếu muốn **tạo truy vấn mới** trong Athena Console, chọn workgroup `bigdata-ids-dev-data-athena`, database `bigdata_ids_dev`, rồi chạy ví dụ sau (Athena tính phí theo dữ liệu quét):

```sql
SELECT binary_label, count(*) AS flows
FROM bigdata_ids_dev.flows_nsl_kdd
GROUP BY binary_label
ORDER BY binary_label;

SELECT attack_cat, count(*) AS flows
FROM bigdata_ids_dev.flows_unsw_nb15
GROUP BY attack_cat
ORDER BY flows DESC;
```

Muốn chạy **lại ETL** (có phí), dùng `aws glue start-job-run --job-name ...`; job hiện ghi đè đường dẫn curated v1, nên kiểm tra dữ liệu và người đang demo trước khi chạy.

## 3. Xem pipeline, metrics và package

**Đọc.** Ba pipeline là `bigdata-ids-dev-train` (RF/SVM), `bigdata-ids-dev-xgboost`, `bigdata-ids-dev-lstm`. Lấy execution mới nhất bằng `list-pipeline-executions`; không suy luận thành công từ trạng thái GitHub job vì workflow chỉ khởi động pipeline.

```powershell
@('bigdata-ids-dev-train','bigdata-ids-dev-xgboost','bigdata-ids-dev-lstm') | ForEach-Object {
  aws sagemaker list-pipeline-executions --pipeline-name $_ --max-results 5 --profile $awsProfile --region $awsRegion --query 'PipelineExecutionSummaries[].{Arn:PipelineExecutionArn,Status:PipelineExecutionStatus,Started:StartTime}'
}
$executionArn = 'arn:aws:sagemaker:ap-southeast-1:101728439989:pipeline/bigdata-ids-dev-xgboost/execution/4ixfq9dbl2vq'
aws sagemaker describe-pipeline-execution --pipeline-execution-arn $executionArn --profile $awsProfile --region $awsRegion --query '{Status:PipelineExecutionStatus,Failure:FailureReason}'
aws sagemaker list-pipeline-execution-steps --pipeline-execution-arn $executionArn --profile $awsProfile --region $awsRegion --query 'PipelineExecutionSteps[].{Step:StepName,Status:StepStatus,Failure:FailureReason}'
```

Khi có `Failed`, đọc step thất bại, tìm Processing Job ARN trong `list-pipeline-execution-steps`, rồi `aws sagemaker describe-processing-job --processing-job-name '<tên-job>' ...`. Log nhóm `/aws/sagemaker/ProcessingJobs`; dùng `aws logs describe-log-streams`/`aws logs get-log-events` theo tên job. Không khởi động lại trước khi biết lỗi và tác động chi phí.

Các package triển khai hiện tại: RF `bigdata-ids-dev-rf/4`, XGBoost `bigdata-ids-dev-xgboost/1`, LSTM `bigdata-ids-dev-lstm/1`; SVM `bigdata-ids-dev-classical/4` đã Approved nhưng chưa có endpoint riêng. Kiểm tra một package:

```powershell
$packageArn = 'arn:aws:sagemaker:ap-southeast-1:101728439989:model-package/bigdata-ids-dev-xgboost/1'
aws sagemaker describe-model-package --model-package-name $packageArn --profile $awsProfile --region $awsRegion --query '{Status:ModelPackageStatus,Approval:ModelApprovalStatus,Metrics:ModelMetrics}'
```

## 4. Gọi thử endpoint và đọc log

**Ghi/chạy:** mỗi `invoke_endpoint` có thể phát sinh phí. Cần file local `data/KDDTest+.txt`; kiểm tra file đúng NSL-KDD. Script RF/XGBoost tự dựng payload raw và in nhãn đúng để đối chiếu:

```powershell
.\.venv\Scripts\python.exe scripts/smoke-endpoint.py --profile $awsProfile --allow-root --endpoint-name bigdata-ids-dev-rf --row-index 0
.\.venv\Scripts\python.exe scripts/smoke-endpoint.py --profile $awsProfile --allow-root --endpoint-name bigdata-ids-dev-xgboost --row-index 0
.\.venv\Scripts\python.exe scripts/smoke-lstm-endpoint.py --profile $awsProfile --allow-root --package-arn arn:aws:sagemaker:ap-southeast-1:101728439989:model-package/bigdata-ids-dev-lstm/1 --row-index 0
```

LSTM smoke test lấy đúng preprocessor từ package, chuyển 20 flow thành tensor 20×25 và so nhãn flow cuối. Mỗi lệnh cần xem `expected_*_label`, `prediction`, `attack_probability`; một lần đúng không chứng minh độ chính xác chung. Nếu profile không phải root, bỏ `--allow-root`.

```powershell
aws logs tail '/aws/sagemaker/Endpoints/bigdata-ids-dev-lstm' --since 30m --profile $awsProfile --region $awsRegion
```

LSTM Serverless đã có lần trả `ModelError` kiểu “could not get a response” trước khi thấy request ở application log; cùng payload gọi lại thành công. Smoke script retry lỗi này tối đa bốn lần. Nếu vẫn lỗi, ghi thời điểm, endpoint status, log và request ID; trình bày demo bằng kết quả Pipeline/evaluation thay vì diễn giải lỗi hạ tầng là dự đoán sai. Với RF/XGBoost, lỗi payload thiếu trường bị container trả `ModelError`/HTTP 424; kiểm tra JSON raw 41 trường, `Content-Type`, đúng package và log endpoint.

## 5. Phát hành và quay lại model

1. Đọc `evaluation.json`, so với mục tiêu F1/FPR và đúng dataset/split. `Succeeded` chỉ nói pipeline chạy xong. Phiên bản mới từ pipeline thường `PendingManualApproval`; LSTM đăng ký riêng bằng `scripts/register-lstm-package.py` sau khi pipeline thành công.
2. Chỉ duyệt package sau khi xác nhận artifact, metrics và hợp đồng input. Dùng `aws sagemaker update-model-package --model-package-arn $newPackageArn --model-approval-status Approved ...` (**ghi**) nếu chủ dự án quyết định phát hành.
3. `scripts/deploy-endpoint.py` (**ghi**) tạo model/config/endpoint từ package Approved. Ví dụ tạo endpoint **mới** để kiểm thử phiên bản mới:

   ```powershell
   .\.venv\Scripts\python.exe scripts/deploy-endpoint.py --profile $awsProfile --allow-root --package-arn $newPackageArn --endpoint-name bigdata-ids-dev-candidate --memory-mb 2048 --max-concurrency 1 --wait
   ```

   Với LSTM đặt `--memory-mb 3072`. Account đang giới hạn mức này. Script cố ý báo lỗi nếu endpoint cùng tên đang dùng config/package khác; không tự cập nhật endpoint đang phục vụ. Nếu cần chuyển traffic, tạo endpoint config mới và dùng `aws sagemaker update-endpoint` sau khi đã xác nhận candidate; lưu lại tên endpoint config trước đó để rollback bằng `update-endpoint --endpoint-config-name '<config-cũ>'`. Đợi `InService` và smoke test sau mỗi lần chuyển.
4. Nếu package mới lỗi, dừng chuyển traffic hoặc quay lại endpoint config/package Approved cũ. Không xoá package/artifact cũ trước khi hoàn tất rollback.

## 6. Drift PSI và phản ứng

**Đọc:** alarm `bigdata-ids-dev-monitoring-nsl-kdd-psi-critical`, metric `Capstone/IDS` / `MaxPSI`, dimension `DatasetId=nsl-kdd`, ngưỡng `>0,25` trong kỳ 5 phút. Báo cáo JSON nằm ở artifact bucket `drift/nsl-kdd/v1/`. `stable` từng cho `0,006151`, `synthetic_shift` cho `20,649132`, `official_test` cho `0,251246`. Shift là dữ liệu giả lập, không phải bằng chứng xâm nhập.

```powershell
$artifactBucket = 'bigdata-ids-dev-foundation-artifactbucket-vlvklecfav5s'
aws s3 ls "s3://$artifactBucket/drift/nsl-kdd/v1/" --profile $awsProfile --region $awsRegion
aws cloudwatch describe-alarms --alarm-names bigdata-ids-dev-monitoring-nsl-kdd-psi-critical --profile $awsProfile --region $awsRegion --query 'MetricAlarms[].{State:StateValue,Reason:StateReason,Updated:StateUpdatedTimestamp}'
```

Để lặp lại demo (**ghi/chạy**, phát metric và ghi đè ba báo cáo), dùng `.\scripts\publish-drift.ps1 -Profile $awsProfile -AllowRoot`. Script phát lần lượt cả stable, synthetic shift, official test; CloudWatch cần thời gian tổng hợp. Không có lịch tự động, SNS/email hoặc SageMaker Model Monitor trong bản triển khai này. Khi alarm thực sự xuất hiện, đọc báo cáo, kiểm tra nguồn dữ liệu/schema, so với baseline rồi mới quyết định retrain.

## 7. Lỗi thường gặp và dừng demo

| Triệu chứng | Kiểm tra và xử lý |
|---|---|
| `NoCredentials` / profile không tìm thấy | `aws configure list-profiles`; mở phiên PowerShell có profile cục bộ; không dán secret vào GitHub/chat. |
| `AccessDenied` | Xem ARN trong STS; IAM user `capstone-admin` trước đây thiếu CloudFormation/IAM. Dùng quyền đã được chủ account cấp; không nới OIDC role cho mọi resource. |
| Processing `ResourceLimitExceeded` | Kiểm tra quota loại instance trong Region; hiện dùng `ml.t3.large` Processing. Quota `ml.m5.large` Training đang chờ xử lý. |
| Firehose tạo thất bại | Account từng trả lỗi cần subscription. Giữ `EnableFirehose=false`; demo batch S3 → Glue → Athena. |
| Endpoint `Failed` | `describe-endpoint` lấy `FailureReason`, xem CloudWatch log; đối chiếu model package, mã inference và bộ nhớ. |
| LSTM `ModelError` không phản hồi | Kiểm tra endpoint/log; retry có giới hạn như smoke script. Ghi rõ tính không ổn định của demo. |
| Alarm PSI đổi trạng thái | Xem timestamp/nguồn datapoint; synthetic shift chỉ là bài kiểm tra alarm. |

**Sau demo:** kiểm tra Billing/Budgets và các job còn chạy. Endpoint Serverless không có instance luôn bật, nhưng invocation, S3 và CloudWatch vẫn có thể phát sinh phí. Nếu không cần phục vụ, có thể xoá ba endpoint bằng `aws sagemaker delete-endpoint --endpoint-name '<tên>' --profile $awsProfile --region $awsRegion` (**ghi/xoá**); giữ Model Registry và S3 để tái tạo. Kiểm tra kỹ tên endpoint trước khi xoá. Access key từng xuất hiện trong chat cần được chủ account xoay vòng; không ghi lại key trong báo cáo. Xem [developer guide](DEVELOPER_GUIDE.md) để thay đổi mã và pipeline.
