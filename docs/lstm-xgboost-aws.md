# Triển khai XGBoost và LSTM trên AWS

Hai thuật toán này dùng **NSL-KDD v1** trong `ap-southeast-1`. Cả hai chạy bằng SageMaker Processing vì quota SageMaker Training Job `ml.m5.large` của account đang bằng 0. Đây là job AWS thực, không phải số liệu từ README của tác giả repo tham khảo.

## Kết quả đã đo

| Model | Pipeline execution | Đơn vị đánh giá | Số mẫu test | Accuracy | F1 | FPR |
|---|---|---|---:|---:|---:|---:|
| XGBoost | `bigdata-ids-dev-xgboost/4ixfq9dbl2vq` | Flow trong KDDTest+ | 22.544 | 0,783046 | 0,770881 | 0,029451 |
| LSTM | `bigdata-ids-dev-lstm/yjxa2d63nyic` | Cửa sổ 20 flow trong KDDTest+ | 1.127 | 0,740018 | 0,718540 | 0,057377 |

XGBoost dùng 30.000 hàng train, giữ class `XGBoostIDS` và cấu hình 500 cây của repo. Job dùng `xgboost-cpu==2.1.4` để tránh tải gói GPU không cần thiết. Pipeline gồm preprocessing → train → đánh giá trên official KDDTest+ → cổng F1 ≥ 0,70 → Model Registry. Package đầu tiên là `bigdata-ids-dev-xgboost/1`.

LSTM giữ kiến trúc của `LSTMIDS` trong repo: hai tầng LSTM 128 units, dropout 0,3 và đầu ra sigmoid. Bản demo huấn luyện tối đa 12 epoch trên 40.000 flow đầu của phần train (2.000 cửa sổ), batch size 256, early stopping patience 3. Mỗi cửa sổ gồm 20 hàng liên tiếp trong **thứ tự file** và nhãn là hàng cuối cùng. Cách gán nhãn này thay quy tắc lấy nhãn hàng đầu của mã upstream; nó cần được nêu rõ khi trình bày. `KDDTest+` có 22.544 hàng: 22.540 hàng tạo 1.127 cửa sổ, 4 hàng cuối không đủ cửa sổ. **NSL-KDD không xác nhận thứ tự hàng là thời gian mạng thực**, nên kết quả LSTM là minh họa mô hình chuỗi trên thứ tự file. F1 theo cửa sổ không so trực tiếp với F1 theo flow của RF, SVM và XGBoost.

LSTM Pipeline dùng preprocessing với split 80/20 giữ thứ tự hàng của KDDTrain+, fit scaler/encoder/feature selector trên phần train, rồi chạy TensorFlow Processing `2.16.2-cpu-py310`. Job xuất `model.keras`, TensorFlow SavedModel trong thư mục `1/`, preprocessor, `model.tar.gz` và `evaluation.json` lên S3. Package Registry `bigdata-ids-dev-lstm/1` dùng image TensorFlow Serving `2.16.1-cpu`. Image phục vụ khác bản training ở patch version; SavedModel đã được kiểm tra trong archive trước khi đăng ký.

## Chạy lại bằng PowerShell 7

Chỉ chạy khi thật sự muốn tạo job mới; mỗi execution có phí. Kiểm tra profile trước. Các lệnh hiện tại dùng profile `default` là root theo yêu cầu của chủ account; script yêu cầu `--allow-root`. Không đưa access key vào lệnh hoặc GitHub.

```powershell
aws sts get-caller-identity --profile default --region ap-southeast-1

.\.venv\Scripts\python.exe pipelines/register_pipeline.py `
  --profile default --allow-root --compute-mode processing `
  --model-name xgboost --train-rows 30000 --deploy --start

.\.venv\Scripts\python.exe pipelines/register_lstm_pipeline.py `
  --profile default --allow-root --max-train-flows 40000 `
  --epochs 12 --deploy --start
```

Khi LSTM Pipeline mới `Succeeded`, đăng ký artifact của **execution mới** với ARN in ra từ lệnh trên:

```powershell
.\.venv\Scripts\python.exe scripts/register-lstm-package.py `
  --profile default --allow-root --execution-arn <LSTM_PIPELINE_EXECUTION_ARN>
```

Script đăng ký tạo package `PendingManualApproval`; xem `evaluation.json` rồi mới duyệt phiên bản muốn dùng. Workflow **AWS train (manual)** trên GitHub có bốn lựa chọn RF/SVM/XGBoost/LSTM. `start_training=false` chỉ kiểm tra OIDC/pipeline; hai lượt [XGBoost](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136376488) và [LSTM](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136379149) đã thành công. `true` tạo job. Workflow chỉ khởi động pipeline đã có, không tự duyệt package hay cập nhật endpoint.

## Suy luận

XGBoost endpoint `bigdata-ids-dev-xgboost` dùng cùng hợp đồng JSON raw-flow của RF. Một smoke test:

```powershell
.\.venv\Scripts\python.exe scripts/smoke-endpoint.py `
  --profile default --allow-root `
  --endpoint-name bigdata-ids-dev-xgboost --row-index 0
```

LSTM endpoint `bigdata-ids-dev-lstm` dùng TensorFlow Serving. API nhận `{"instances": [<một tensor 20×25>]}`; **nó không nhận một raw flow**. Script smoke test tải preprocessor từ đúng model package, biến đổi 20 hàng KDDTest+ rồi gọi endpoint:

```powershell
.\.venv\Scripts\python.exe scripts/smoke-lstm-endpoint.py `
  --profile default --allow-root `
  --package-arn arn:aws:sagemaker:ap-southeast-1:101728439989:model-package/bigdata-ids-dev-lstm/1 `
  --row-index 0
```

Endpoint đã `InService`; cửa sổ KDDTest+ hàng 0–19 trả `prediction=1`, xác suất attack `0,995140`, khớp nhãn hàng cuối. Một số lần gọi Serverless trả `ModelError` với thông báo không nhận phản hồi dù container TensorFlow đã load model; cùng request ở lần khác thành công. Script chỉ retry có giới hạn cho đúng lỗi không phản hồi này. Đây là giới hạn độ ổn định cần nhắc khi demo, không phải bằng chứng model dự đoán sai.

Account giới hạn bộ nhớ mỗi Serverless endpoint ở 3.072 MB; endpoint LSTM dùng mức này, XGBoost dùng 2.048 MB. Xóa endpoint sau demo nếu không cần duy trì; metadata Model Registry và artifact S3 vẫn còn để tạo lại:

```powershell
aws sagemaker delete-endpoint --endpoint-name bigdata-ids-dev-lstm --profile default --region ap-southeast-1
aws sagemaker delete-endpoint --endpoint-name bigdata-ids-dev-xgboost --profile default --region ap-southeast-1
```
