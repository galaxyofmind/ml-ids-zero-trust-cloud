# Deployment report — capstone Big Data + MLOps + Cybersecurity

**Ảnh chụp trạng thái:** 25-09-2026, khoảng 20:25 ICT. **Repository:** [galaxyofmind/ml-ids-zero-trust-cloud](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud), commit kiểm tra ban đầu `a851ed3`. **AWS:** account `101728439989`, Region `ap-southeast-1`. Báo cáo phân biệt kết quả đã kiểm tra trực tiếp, kết quả được ghi trong artifact/log của lần triển khai trước và hạng mục chưa triển khai. Hướng dẫn phát triển và vận hành xem [Developer guide](DEVELOPER_GUIDE.md) và [Operations runbook](OPERATIONS_RUNBOOK.md).

## 1. Phạm vi đã triển khai

| Thành phần | Tài nguyên / trạng thái tại thời điểm kiểm tra | Bằng chứng và chức năng |
|---|---|---|
| Foundation | `bigdata-ids-dev-foundation` `CREATE_COMPLETE` | S3 data/artifact và service roles. |
| Big Data | `bigdata-ids-dev-data` `UPDATE_COMPLETE` | Glue jobs, Catalog, Athena workgroup; batch S3 → Glue → Parquet → Athena. |
| GitHub OIDC | `bigdata-ids-dev-github-oidc` `UPDATE_COMPLETE` | GitHub `master` được assume role chỉ để Describe/Start ba pipeline. |
| Monitoring | `bigdata-ids-dev-monitoring` `CREATE_COMPLETE` | CloudWatch alarm PSI; tại lúc kiểm tra `OK`. |
| SageMaker Pipelines | `bigdata-ids-dev-train`, `bigdata-ids-dev-xgboost`, `bigdata-ids-dev-lstm` tồn tại | RF/SVM/XGBoost/LSTM đã có execution `Succeeded`. |
| SageMaker Model Registry | RF `/4`, SVM classical `/4`, XGBoost `/1`, LSTM `/1` `Completed`/`Approved` | Package chứa artifact và thông tin đánh giá. GitHub SVM classical `/5` còn `PendingManualApproval`. |
| Online inference | `bigdata-ids-dev-rf`, `bigdata-ids-dev-xgboost`, `bigdata-ids-dev-lstm` đều `InService` | Serverless; RF/XGB 2048 MB, LSTM 3072 MB, concurrency 1. |

Kiểm tra trực tiếp bằng AWS CLI profile `default` ngày 25-09-2026 đã xác nhận account/ARN root, bốn trạng thái CloudFormation, ba endpoint `InService`, execution XGBoost `4ixfq9dbl2vq`, LSTM `yjxa2d63nyic`, RF `w53s4k21lvg6`, GitHub SVM `c5kl0f3eaypx` là `Succeeded`; package RF, SVM `/4`, XGB, LSTM đang `Approved`, SVM `/5` còn `PendingManualApproval`, alarm đang `OK`, và quota request ở `CASE_OPENED`. Đây là **trạng thái tức thời**, không phải cam kết liên tục; dùng [runbook](OPERATIONS_RUNBOOK.md#1-trước-mỗi-buổi-demo--kiểm-tra-không-tạo-job) để kiểm tra lại trước demo.

## 2. Dataset và Big Data

| Dataset | Raw train / test | Pipeline dữ liệu AWS | Phạm vi ML AWS |
|---|---:|---|---|
| NSL-KDD v1 | 125.973 / 22.544 flow | Raw S3 → Glue `bigdata-ids-dev-data-nsl-kdd-etl` → `bigdata_ids_dev.flows_nsl_kdd` → Athena | RF, SVM, XGBoost, LSTM. |
| UNSW-NB15 v1 | 175.341 / 82.332 hàng | Raw S3 → Glue `bigdata-ids-dev-data-unsw-nb15-etl` → `bigdata_ids_dev.flows_unsw_nb15` → Athena | **Chưa** dùng train/inference trên AWS. |

Data bucket: `bigdata-ids-dev-foundation-databucket-y4img8enauch`; artifact bucket: `bigdata-ids-dev-foundation-artifactbucket-vlvklecfav5s`. Cả hai private, versioning, mặc định SSE-S3. NSL-KDD raw `KDDTrain+.txt` SHA-256 `1b86d2f957b33082081bba410fe129b475efebcc13c9014c3f447c8271aadf95`, `KDDTest+.txt` SHA-256 `fa46b0935342616aa83b7c2578db355b6a7aaabbc492248172c7a1e8b7ab8f84`; manifest lưu cùng prefix raw. UNSW train SHA-256 `bec7dd5ec88dc2a0ccc7a07879d338395ed7421750f675fd0339e07dfe0648fa`, test `734fe6642edf758f7c94d7d9149426b49d202fe8e7bf0bef47392489c3c0a559`.

Glue NSL-KDD run `jr_c72f74e817958313aaa8ca4a39d3da808648bf7c965baf94163b3756b89c5b96` thành công; Athena query `d762e729-54c1-4ca9-8725-283203f89420` cho 58.630 attack và 67.343 normal trong train. Glue UNSW run `jr_3159af64dd9a9d1da1caf03c404ce26567f8f5656a75005539d1b78c2b5a8076` thành công; Athena query `e3cb4685-5268-4df6-8290-1b346102b805` cho 175.341 hàng train và 10 loại class, quét 59.013 byte. Athena workgroup `bigdata-ids-dev-data-athena`.

Kinesis Data Firehose **chưa hoạt động**: AWS từ chối tạo stream với thông báo account cần subscription cho dịch vụ; `EnableFirehose=false` là mặc định của template. Demo Big Data hiện chứng minh xử lý batch và truy vấn, chưa có streaming thực.

## 3. MLOps, CI và phương pháp đánh giá

Pipeline RF/SVM/XGB fit encoder/scaler/selector 25 đặc trưng trên phần train của KDDTrain+; stratified 80/20 cho 100.778 train, 25.195 validation. KDDTest+ 22.544 hàng được giữ riêng để báo cáo cuối. RF dùng 30.000 hàng fit, SVM 8.000, XGB 30.000. Pipeline cổ điển có gate F1 official test `>=0,70`, sau đó tạo model package `PendingManualApproval`. Những package đang phục vụ đã được duyệt sau khi xem metrics/artifact.

LSTM dùng 80/20 theo thứ tự hàng file, 40.000 flow train tạo 2.000 cửa sổ không chồng lấn, mỗi cửa sổ 20×25; nhãn lấy từ flow cuối. `KDDTest+` tạo 1.127 cửa sổ từ 22.540 flow, bỏ 4 flow cuối không đủ cửa sổ. **Không có chứng cứ hàng NSL-KDD theo thời gian mạng thực**, nên đây là minh hoạ mô hình chuỗi trên thứ tự file. Pipeline LSTM chưa có gate F1 tự động; package được đăng ký riêng sau khi execution thành công. Model dùng kiến trúc upstream hai tầng LSTM 128 units, dropout 0,3, tối đa 12 epoch; train TensorFlow CPU 2.16.2, serve TensorFlow Serving CPU 2.16.1.

Account có quota `ml.m5.large` bằng 0 cho SageMaker Training/Processing; các lần fit AWS ở đây dùng **SageMaker Processing `ml.t3.large`**, không phải SageMaker Training Job. Quota request Training 1 instance `8cc761a8777747418dc8700669703768fnbeVUWS` lúc kiểm tra còn `CASE_OPENED`. Serverless memory tối đa 3072 MB đã quan sát được ở account; đề nghị LSTM 4096 MB bị từ chối.

GitHub Actions `CI` chạy compile Python và `cfn-lint`; [run 36136512665](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136512665) thành công trên mã trước bộ tài liệu này. [AWS OIDC smoke run 36097779782](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36097779782) thành công; [GitHub SVM start run 36126420273](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36126420273) đã khởi động execution `c5kl0f3eaypx`, execution đó thành công. [XGBoost dry run 36136376488](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136376488) và [LSTM dry run 36136379149](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136379149) thành công với `start_training=false`, không tạo job train từ các run dry này. Workflow GitHub không đợi pipeline hoàn thành hoặc phát hành endpoint.

## 4. Kết quả mô hình AWS

Các số dưới đây là kết quả của execution SageMaker trên official KDDTest+, **không** lấy từ README tác giả upstream. F1/FPR làm tròn 6 chữ số thập phân.

| Model | Execution ID | Đơn vị test | Mẫu fit | Mẫu test | Accuracy | F1 | FPR | Confusion TN/FP/FN/TP |
|---|---|---|---:|---:|---:|---:|---:|---|
| Random Forest | `w53s4k21lvg6` | flow | 30.000 | 22.544 | 0,776836 | 0,762453 | 0,028009 | 9439 / 272 / 4759 / 8074 |
| SVM | `bao44h4fqvdk` | flow | 8.000 | 22.544 | 0,726623 | 0,706118 | 0,075584 | 8977 / 734 / 5429 / 7404 |
| XGBoost | `4ixfq9dbl2vq` | flow | 30.000 | 22.544 | 0,783046 | 0,770881 | 0,029451 | 9425 / 286 / 4605 / 8228 |
| LSTM | `yjxa2d63nyic` | **cửa sổ** | 2.000 cửa sổ | 1.127 cửa sổ | 0,740018 | 0,718540 | 0,057377 | 460 / 28 / 265 / 374 |

LSTM F1 theo cửa sổ **không so trực tiếp** với F1 theo flow của ba model còn lại. Validation F1 LSTM khoảng `0,969388`, khác xa official test F1; báo cáo phải ưu tiên official test và nêu split. Số `98,1%` LSTM và `97,3%` XGBoost trong README gốc là **kết quả tác giả công bố, chưa tái lập trong capstone**. Local preliminary XGBoost F1 `0,771514` cũng không phải số AWS.

RF evaluation JSON được lưu tại `s3://bigdata-ids-dev-foundation-artifactbucket-vlvklecfav5s/bigdata-ids-dev-train/w53s4k21lvg6/EvaluateOnOfficialTest/output/evaluation/evaluation.json`; SVM tại prefix execution `bao44h4fqvdk`, GitHub SVM tại `c5kl0f3eaypx`. XGBoost JSON ở `s3://bigdata-ids-dev-foundation-artifactbucket-vlvklecfav5s/bigdata-ids-dev-xgboost/4ixfq9dbl2vq/EvaluateOnOfficialTest/output/evaluation/evaluation.json`; LSTM JSON ở `s3://bigdata-ids-dev-foundation-artifactbucket-vlvklecfav5s/bigdata-ids-dev-lstm/yjxa2d63nyic/TrainAndEvaluateLSTM/output/evaluation/evaluation.json`. Hai JSON XGB/LSTM đã được đọc lại trực tiếp từ S3 ngày 25-09-2026 và khớp bảng trên. Với execution mới, dùng `list-pipeline-execution-steps` rồi `describe-processing-job` để lấy output URI; xem [runbook](OPERATIONS_RUNBOOK.md#3-xem-pipeline-metrics-và-package). Các ARN execution cùng có dạng `arn:aws:sagemaker:ap-southeast-1:101728439989:pipeline/<pipeline-name>/execution/<id>`.

## 5. Inference và giám sát đã kiểm chứng

RF package `/4` đã khắc phục lỗi đóng gói inference của các version 1–3 (bị `Rejected`); model weight và metrics đánh giá không đổi. RF smoke trên KDDTest+ hàng 0 trả `prediction=1`, `attack_probability=1,0`; XGB trả `prediction=1`, `attack_probability=0,999985`. Payload thiếu trường bị từ chối qua `ModelError`/HTTP 424. LSTM smoke trên cửa sổ hàng 0–19 trả `prediction=1`, `attack_probability=0,995140`, khớp nhãn hàng cuối. Các kết quả này là **smoke test**, không phải thước đo aggregate.

LSTM Serverless từng trả `ModelError` “could not get a response” ngắt quãng trước khi application log ghi request; cùng payload gọi lại thành công. Smoke script retry có giới hạn. Vì vậy endpoint chứng minh được demo suy luận, **chưa chứng minh độ tin cậy production**.

`src/aws_drift_demo.py` tính max PSI `0,006151` cho mẫu ổn định, `20,649132` cho dữ liệu dịch chuyển **giả lập**, `0,251246` cho KDDTest+. Script đăng báo cáo S3 và metric `Capstone/IDS/MaxPSI`; alarm ngưỡng `>0,25` từng lên `ALARM` khi phát shift, hiện `OK` tại 20:25 ICT. Chưa có lịch tự động, SNS/email hay SageMaker Model Monitor cho endpoint Serverless. PSI không phải classifier tấn công.

## 6. Giới hạn, rủi ro và việc còn lại

| Hạng mục | Trạng thái / tác động | Hành động kế tiếp |
|---|---|---|
| Streaming Firehose | Chưa có do lỗi subscription; kiến trúc batch vẫn hoạt động. | Nếu rubric bắt buộc streaming, chủ account làm việc với AWS Support rồi bật template có kiểm soát. |
| SageMaker Training Job | Chưa dùng vì quota 0; đang dùng Processing để fit. | Theo dõi quota request; chỉ chuyển mode sau khi được cấp quota và thử lại. |
| MLflow/AWS, Autoencoder/AWS, scheduled drift, SNS | Chưa triển khai. | Chỉ thêm nếu mục tiêu học phần yêu cầu; không trình bày như đã có. |
| LSTM serving | Có lỗi không phản hồi ngắt quãng. | Ghi log/request ID, điều tra giới hạn Serverless/image trước khi dùng ngoài demo. |
| Security/credentials | Chủ account yêu cầu dùng root profile để triển khai; một access key IAM đã xuất hiện trong chat. | Chủ account xoay vòng key đó, kiểm tra quyền/Billing; thay bằng quyền tối thiểu khi hoàn tất demo. Không đưa key vào GitHub. |
| Chi phí | Glue, Processing, endpoint invocation, Athena, S3/CloudWatch có thể tính phí. | Xem Billing/Budgets, tránh chạy lại job khi chỉ cần đọc; xoá endpoint sau demo nếu không dùng. |

**Kết luận phạm vi:** Hệ thống đã chứng minh data lake/ETL/query cho hai dataset, MLOps Pipeline/Registry trên AWS cho bốn thuật toán NSL-KDD, ba endpoint serverless, GitHub Actions OIDC và PSI alarm. Các giới hạn ở bảng trên phải đi cùng bất kỳ slide hoặc demo nào trích báo cáo này.
