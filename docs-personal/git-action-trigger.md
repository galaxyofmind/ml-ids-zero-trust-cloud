Trong repo hiện tại, **GitHub Actions có ba workflow**:

| Workflow | Khi nào chạy | Làm gì |
|---|---|---|
| [CI](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/.github/workflows/ci.yml>) | Push lên `master`, mở/cập nhật pull request, hoặc bấm chạy thủ công | Kiểm tra cú pháp Python và các template CloudFormation bằng `cfn-lint`. Không huấn luyện mô hình. |
| [AWS smoke](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/.github/workflows/aws-smoke.yml>) | Chỉ khi bấm **Run workflow** trên nhánh `master` | Dùng GitHub OIDC để nhận quyền AWS tạm thời, rồi chạy `sts get-caller-identity` nhằm kiểm tra kết nối. |
| [AWS train](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/.github/workflows/aws-train.yml>) | Chỉ khi bấm **Run workflow** trên nhánh `master` | Kiểm tra danh tính AWS và SageMaker Pipeline. **Chỉ bắt đầu huấn luyện** khi chọn `start_training=true`; chọn được Random Forest hoặc SVM. Việc này tạo job có tính phí. |

Vì vậy, **push code không tự động train hoặc deploy model**. GitHub Actions hiện đóng vai trò kiểm tra mã, xác nhận kết nối AWS và cung cấp nút chạy pipeline huấn luyện có chủ đích.

**IaC (Infrastructure as Code)** ở đây là các file CloudFormation trong thư mục [infra](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/infra>). Chúng mô tả tài nguyên AWS để tạo và quản lý bằng mã:

- [foundation.yaml](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/infra/foundation.yaml>): tạo S3 bucket cho dữ liệu và artifact, cùng IAM role cho Glue, SageMaker và Firehose.
- [data.yaml](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/infra/data.yaml>): tạo Glue jobs/Catalog, bảng dữ liệu NSL-KDD và UNSW-NB15, Athena workgroup; Firehose là tùy chọn.
- [github-oidc.yaml](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/infra/github-oidc.yaml>): cho GitHub Actions nhận quyền AWS tạm thời, giới hạn vào việc xem và khởi chạy **một** SageMaker Pipeline.
- [monitoring.yaml](<D:/Knowledge base/University/SamSung/Bigdata-capstone/ml-ids-zero-trust-cloud/infra/monitoring.yaml>): tạo CloudWatch alarm cho tín hiệu drift PSI.

Hiểu ngắn gọn: **IaC dựng nền tảng AWS; GitHub Actions kiểm tra mã và gọi pipeline; SageMaker Pipeline thực hiện các bước xử lý, huấn luyện và đánh giá mô hình.** Các workflow hiện tại không tự triển khai toàn bộ CloudFormation stack mỗi khi bạn push.