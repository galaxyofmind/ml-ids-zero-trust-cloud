Theo mã và báo cáo triển khai hiện có, tôi **không thể xác nhận kế hoạch tiếp theo của agent chính**, nhưng hệ thống trên AWS hiện mới chạy và đánh giá **Random Forest và SVM**. Pipeline AWS chỉ nhận hai mô hình này. XGBoost mới có kết quả thử nghiệm local; LSTM và Autoencoder chưa có kết quả huấn luyện trên AWS. Xem [trạng thái triển khai](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/docs/aws-deployment-status.md>) và [mã pipeline](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/pipelines/register_pipeline.py>).

**Bạn nên tự kiểm tra và ghi nhận kết quả, nhưng chưa cần tự chạy lại toàn bộ năm mô hình.** Chạy lại lúc này sẽ tốn phí và có thể đụng pipeline mà agent chính đang cấu hình. Hơn nữa, script local chạy năm mô hình dùng cách tiền xử lý có nguy cơ rò rỉ dữ liệu giữa tập train và test, nên không nên dùng kết quả đó làm bảng so sánh chính thức.

Để kiểm tra thủ công hai lần chạy AWS đã có, trong PowerShell 7:

```powershell
aws sagemaker list-pipeline-executions `
  --pipeline-name bigdata-ids-dev-train `
  --profile default `
  --region ap-southeast-1
```

Sau đó đọc báo cáo đánh giá trên tập **KDDTest+**:

```powershell
aws s3 cp `
  s3://bigdata-ids-dev-foundation-artifactbucket-vlvklecfav5s/bigdata-ids-dev-train/w53s4k21lvg6/EvaluateOnOfficialTest/output/evaluation/evaluation.json `
  - --profile default --region ap-southeast-1
```

Lệnh trên đọc kết quả Random Forest. Với SVM, thay `w53s4k21lvg6` bằng `bao44h4fqvdk`. Nếu profile AWS của bạn là `capstone-dev`, thay `--profile default` tương ứng.

Khi lập bảng đánh giá, ghi **accuracy, precision, recall, F1, false positive rate, confusion matrix, số dòng train, tên tập test và mã lần chạy**. Với hệ thống phát hiện xâm nhập, hãy chú ý *recall* vì nó phản ánh tỷ lệ tấn công được phát hiện.

Nếu mục tiêu capstone là chứng minh đủ năm thuật toán, hãy yêu cầu agent chính mở rộng pipeline và chạy từng mô hình trên **cùng quy trình chia dữ liệu, cùng KDDTest+ và cùng bộ chỉ số**. Chỉ ghi “đã tái lập trên AWS” cho mô hình có job, artifact và báo cáo đánh giá thực tế; số liệu trong README của repo gốc là kết quả tác giả công bố.