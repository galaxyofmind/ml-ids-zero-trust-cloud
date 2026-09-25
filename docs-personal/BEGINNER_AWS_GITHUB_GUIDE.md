# Hướng dẫn triển khai cho người mới: AWS + GitHub Actions

**Đọc trước:** [thiết kế hệ thống](./SYSTEM_DESIGN.md) là sơ đồ và lựa chọn dịch vụ; [runbook triển khai](./DEPLOYMENT_RUNBOOK.md) là danh sách công việc đầy đủ. Tài liệu này giải thích **bạn thao tác ở đâu, nhập gì, thấy gì và xử lý lỗi ra sao** khi lần đầu dùng AWS/GitHub Actions. **Cập nhật 25/09/2026:** nhiều bước dưới đây đã được triển khai; xem [trạng thái AWS thực tế](./ml-ids-zero-trust-cloud/docs/aws-deployment-status.md) trước khi chạy lại lệnh có phí.

**Ngoại lệ của lần triển khai này:** profile `capstone-dev` đăng nhập được nhưng thiếu quyền CloudFormation/IAM; theo yêu cầu của bạn, các script đã chạy bằng profile `default` mang root ARN và yêu cầu cờ `-AllowRoot`/`--allow-root`. Sau demo, xoay vòng static key từng xuất hiện trong chat và chuyển về IAM user/role. Không gửi key mới qua chat.

## 1. Đường ngắn nhất để có demo

Không cần bật mọi dịch vụ cùng lúc. Đi theo bốn mốc và chỉ sang mốc tiếp theo khi mốc trước chạy được:

| Mốc | Dịch vụ | Kết quả nhìn thấy | Ai thao tác chính |
|---|---|---|---|
| 1. Chuẩn bị | AWS account, CLI, Billing Budget, GitHub repo | `aws sts get-caller-identity` trả đúng account; GitHub Actions CI xanh | Bạn đăng nhập/tạo repo/budget; tôi kiểm tra và viết CI |
| 2. Dữ liệu | S3, Glue, Athena | File raw trên S3; bảng Parquet; query `COUNT(*)` thành công | Tôi tạo code/IaC/chạy lệnh sau khi có quyền; bạn kiểm tra chi phí |
| 3. ML | SageMaker Processing/Pipelines, Model Registry; Training Job khi quota được cấp | Pipeline RF, SVM, XGBoost, LSTM thành công, có metric **tự đo** và model version | Tôi port/chạy/sửa mã; bạn chốt metric gate |
| 4. Demo hoàn chỉnh | Serverless Inference, CloudWatch, drift | RF/XGBoost/LSTM có prediction online; PSI report và alarm có bằng chứng | Tôi triển khai/kiểm thử; bạn xem Console và quyết định có cần Batch Transform/email cảnh báo không |

**GitHub Actions có hai vai trò khác nhau:** (1) CI kiểm tra code, không cần AWS credential; (2) deploy AWS, cần IAM role OIDC. Bật (1) ngay. Chỉ bật (2) khi deploy từ máy local đã thành công, để dễ xác định lỗi nằm ở AWS hay GitHub. [GitHub: Python CI](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), [GitHub: OIDC với AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).

### Thuật ngữ dùng trong hướng dẫn

| Từ | Hiểu ngắn gọn |
|---|---|
| **Account ID** | Mã 12 chữ số của tài khoản AWS; không phải mật khẩu. |
| **Region** | Vùng đặt tài nguyên. Dùng một Region cho cả demo; ví dụ `ap-southeast-1` (Singapore). |
| **AWS Console** | Trang web để xem/tạo tài nguyên. |
| **AWS CLI profile** | Tên cấu hình đăng nhập trên máy, ví dụ `capstone-dev`. |
| **IAM role** | Quyền tạm thời cho một người, dịch vụ AWS hoặc GitHub Actions; không phải access key. |
| **CloudFormation stack** | Một nhóm tài nguyên AWS được tạo/cập nhật từ file YAML; xóa stack có thể xóa tài nguyên trong nhóm. |
| **S3 bucket / prefix** | Nơi lưu file; prefix là đường dẫn trong bucket, ví dụ `raw/dataset=nsl-kdd/`. |
| **Job / pipeline / endpoint** | Job chạy rồi dừng; pipeline nối các job; endpoint nhận request suy luận. |
| **GitHub Actions workflow** | File YAML trong `.github/workflows/` quy định khi nào và bằng lệnh nào GitHub chạy CI/deploy. |

## 2. Bảo mật tối thiểu để triển khai nhanh

Ở bản demo, **không dựng nhiều AWS account, VPC riêng, NAT Gateway, KMS key riêng, WAF, Security Hub hay quy trình phê duyệt nhiều tầng**. Không bật GuardDuty mới chỉ để có ảnh demo nếu bạn chưa kiểm tra chi phí và trạng thái account. Dùng S3 SSE-S3 mặc định, role do template tạo, một Region và GitHub Actions CI trước.

Giữ bốn ranh giới tối thiểu này vì bỏ chúng không giúp triển khai nhanh hơn đáng kể:

1. **Không commit AWS access key/secret key** hoặc file `.aws/` lên GitHub. Trên máy dùng `aws login` hoặc SSO; GitHub dùng OIDC khi cần AWS. [AWS CLI login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html), [GitHub OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
2. **Không mở public S3 bucket.** Giữ bốn mục Block Public Access. [AWS S3 Block Public Access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html).
3. **Chuyển khỏi root sau giai đoạn bootstrap/demo.** Lần triển khai này tạm dùng root theo yêu cầu của chủ account vì `capstone-dev` thiếu quyền; các role của Glue, SageMaker và GitHub Actions vẫn tách riêng.
4. **Đặt Budget và ngày dọn tài nguyên.** Budget là cảnh báo, không chặn chi phí ngay lập tức; kiểm tra endpoint/app/job sau mỗi buổi làm. [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html).

## 3. Bước đầu tiên của bạn: tài khoản, ngân sách, đăng nhập

### 3.1 Tạo/kiểm tra tài khoản AWS — **bạn làm thủ công**

1. Mở AWS Console, đăng nhập account của bạn. Nếu đây là account mới, hoàn tất email, phương thức thanh toán và MFA theo hướng dẫn trên màn hình.
2. Ở góc phải Console, ghi lại **Account ID** (12 số) và Region đang chọn. Chuyển Region sang **Asia Pacific (Singapore) — `ap-southeast-1`**. AWS hiện liệt kê MLflow App ở Singapore; quota của account vẫn cần kiểm tra. [Danh sách Region MLflow](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow.html).
3. Nếu **account cá nhân mới chỉ có root**, tạo danh tính làm việc trước: trong **IAM → Users → Create user**, tạo `capstone-admin` có Console access, bật MFA, không tạo access key. Với một account sandbox dành riêng cho capstone, có thể cấp `AdministratorAccess` để dựng hạ tầng nhanh và `SignInLocalDevelopmentAccess` để dùng `aws login`; đây là quyền rộng cho giai đoạn bootstrap, nên không gán cho GitHub Actions hay SageMaker job. Đăng xuất root và đăng nhập lại bằng IAM user trước khi làm tiếp. [Tạo IAM user](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_create.html), [quyền cho `aws login`](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).
4. Nếu account do trường quản lý, dùng danh tính/SSO họ cấp; hỏi quản trị viên quyền chạy CloudFormation, S3, Glue, Athena, SageMaker, IAM PassRole và Billing Budget. Bạn không cần tự tạo IAM user/access key.

**Gửi cho tôi:** Account ID, Region và loại đăng nhập (account cá nhân hay IAM Identity Center). Không gửi ảnh có mật khẩu/MFA.

### 3.2 Tạo Budget qua Console — **bạn làm thủ công**

Vào **Billing and Cost Management → Budgets → Create budget → Use a template (simplified) → Monthly cost budget**. Nhập tên, số tiền tối đa nhóm chấp nhận, email nhận cảnh báo rồi chọn **Create budget**. Nếu giao diện khác, dùng mục **Cost budget** theo [hướng dẫn AWS](https://docs.aws.amazon.com/cost-management/latest/userguide/budget-templates.html). Mở email xác nhận nếu AWS yêu cầu. Budget không phải công tắc tự dừng mọi dịch vụ; dữ liệu Billing có độ trễ. [AWS Budgets best practices](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html).

**Kiểm tra:** Budget xuất hiện trong danh sách, đúng tiền tệ/chu kỳ/email. Ghi `BudgetAmount` và ngày muốn xóa resource vào file cấu hình không bí mật khi tôi tạo file đó.

### 3.3 Đăng nhập CLI từ PowerShell 7 — **bạn hoàn tất browser/MFA; tôi có thể chạy lệnh khi bạn yêu cầu**

Máy hiện có **AWS CLI 2.37.3**, đủ mới cho `aws login` (AWS yêu cầu tối thiểu 2.32.0). Với account cá nhân hoặc Console login thông thường, dùng:

```powershell
aws --version
aws login --profile capstone-dev
$env:AWS_PROFILE = "capstone-dev"
$env:AWS_DEFAULT_REGION = "ap-southeast-1"
aws sts get-caller-identity
```

`aws login` mở browser và tạo credential tạm thời; bạn tự đăng nhập/MFA. Tôi **chưa chạy lệnh đăng nhập này**. Nếu tôi thao tác đăng nhập thay bạn ở một lượt sau, skill AWS yêu cầu tôi hỏi trước khi gọi `aws login` vì đây là bước tương tác danh tính. [AWS CLI local login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).

Nếu trường đã cấp **IAM Identity Center (SSO)**, dùng đường thay thế dưới đây, **không chạy cả hai cách cho cùng một profile**:

```powershell
aws configure sso --profile capstone-dev
aws sso login --profile capstone-dev
$env:AWS_PROFILE = "capstone-dev"
$env:AWS_DEFAULT_REGION = "ap-southeast-1"
aws sts get-caller-identity
```

`get-caller-identity` phải in ra `Account`, `UserId`, `Arn` đúng account, và `Arn` không phải root. Khi đổi cửa sổ PowerShell, đặt lại hai biến `$env:` hoặc truyền `--profile capstone-dev --region ap-southeast-1` cho từng lệnh. [AWS CLI SSO](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).

## 4. GitHub cơ bản: repo và CI không đụng AWS

### 4.1 Tạo repo — **bạn làm thủ công**

Repo thực tế là fork [galaxyofmind/ml-ids-zero-trust-cloud](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud), nhánh mặc định `master`. Mã triển khai đã được thêm trong thư mục `ml-ids-zero-trust-cloud` của workspace. Không upload dataset lớn, artifact `.pkl`/`.h5`, `mlruns/`, `.env` hay AWS config vào GitHub.

**Kiểm tra:** repo hiện trong trang GitHub của bạn; fork thực tế đã được xác nhận và dùng trong workflow.

### 4.2 CI đầu tiên — **tôi tạo file, bạn xem trong tab Actions**

Tôi sẽ thêm `.github/workflows/ci.yml` khi import mã. Workflow mẫu dưới đây chỉ kiểm tra Python compile, **không cần AWS credential và không tạo chi phí AWS**:

```yaml
name: CI
on:
  pull_request:
  workflow_dispatch:
jobs:
  check-python:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: '3.11'
      - name: Check Python syntax
        run: python -m compileall src
```

Sau khi có test thật, thay/bổ sung lệnh bằng `pytest`; compile xanh **chưa chứng minh model đúng**. Khi file nằm trên nhánh mặc định, mở **repo → Actions → CI → Run workflow** để chạy thủ công; `workflow_dispatch` chỉ hiện nút khi workflow đã ở default branch. [GitHub Actions Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python), [chạy workflow thủ công](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

**Nếu không thấy tab Actions:** kiểm tra repo Settings → Actions → General và quyền của tổ chức. **Nếu CI đỏ:** bấm run → job `check-python` → bước màu đỏ, gửi tôi đoạn log lỗi (không gửi secret).

## 5. Triển khai AWS từ máy trước

Các template/script bước foundation, ingest, Glue/Athena và SageMaker đầu tiên đã có trong repo fork. Xem [trạng thái triển khai](./ml-ids-zero-trust-cloud/docs/aws-deployment-status.md) để biết bước nào đã chạy và lỗi quota nào còn tồn tại. Mỗi bước bên dưới vẫn có lệnh và dấu hiệu thành công để bạn học cách kiểm tra.

### 5.1 Hạ tầng nền: S3 và IAM role — **tôi tự động; bạn xem kết quả**

Tôi tạo `infra/foundation.yaml`: bucket data/artifact, Block Public Access, mã hóa mặc định, role cho Glue/SageMaker/Firehose. Trước khi deploy, kiểm tra template và danh sách tài nguyên dự kiến. Sau đó:

```powershell
aws cloudformation validate-template --template-body file://infra/foundation.yaml
aws cloudformation deploy --template-file infra/foundation.yaml --stack-name bigdata-ids-dev-foundation --capabilities CAPABILITY_IAM
aws cloudformation describe-stacks --stack-name bigdata-ids-dev-foundation --query "Stacks[0].{Status:StackStatus,Outputs:Outputs}"
```

**Thấy gì:** `CREATE_COMPLETE` hoặc `UPDATE_COMPLETE`; `Outputs` có bucket/role ARN. Trong Console mở **CloudFormation → Stacks → bigdata-ids-dev-foundation → Resources/Outputs** để xem từng dịch vụ được tạo. Nếu stack đỏ, mở tab **Events**; đừng xóa/sửa tay từng resource. [AWS CloudFormation CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli_cloudformation_code_examples.html).

### 5.2 Upload dữ liệu — **bạn cấp file/nguồn; tôi chạy và kiểm tra**

NSL-KDD là dữ liệu đầu tiên. Tôi tính SHA-256, lưu manifest rồi upload file raw. Ví dụ sau khi nhận bucket name từ stack:

```powershell
$bucketName = "ten-bucket-trong-stack-output"
$filePath = ".\data\KDDTrain+.txt"
Get-FileHash -Algorithm SHA256 -Path $filePath
aws s3 cp $filePath "s3://$bucketName/raw/dataset=nsl-kdd/version=v1/KDDTrain+.txt"
aws s3 ls "s3://$bucketName/raw/dataset=nsl-kdd/version=v1/"
```

**Thấy gì:** lệnh `cp` in `upload:`; lệnh `ls` liệt kê file. Trong Console vào **S3 → bucket → raw/dataset=nsl-kdd/version=v1** để kiểm tra. Không bật public access để xem file; dùng Console/CLI với tài khoản đã đăng nhập.

### 5.3 Glue và Athena — **tôi tạo/chạy; bạn đọc kết quả**

Tôi tạo Glue job để đọc raw, kiểm tra lỗi và ghi Parquet `curated/`, sau đó tạo bảng trong Glue Data Catalog. Mở **AWS Glue → ETL jobs → Runs** để xem trạng thái. Khi job `Succeeded`, mở **Athena → Query editor**, chọn database `bigdata_ids_dev`, chạy:

```sql
SELECT binary_label, COUNT(*) AS n
FROM flows_nsl_kdd
GROUP BY binary_label;
```

Trước query, Athena phải có **Query result location** do stack cấp; nếu báo chưa có, chọn S3 prefix `athena-results/` từ output. [Athena getting started](https://docs.aws.amazon.com/athena/latest/ug/getting-started.html). **Thấy gì:** hai nhóm normal/attack (tùy mapping), số dòng khớp báo cáo ETL. Nếu bảng chưa có, kiểm tra Glue job `Succeeded` và Data Catalog database/table đúng Region.

### 5.4 SageMaker Pipeline — **tôi đã chạy RF, SVM, XGBoost và LSTM; bạn kiểm tra run và metric**

Pipeline RF/SVM và XGBoost là Processing (preprocess) → Processing (fit) → Processing (evaluation) → condition F1 → Model Registry. LSTM có pipeline riêng: preprocessing giữ thứ tự file → TensorFlow Processing train/đánh giá; artifact SavedModel được đăng ký sau khi run thành công. Account có quota `ml.m5.large` Training Job bằng 0, nên đây là **Processing fallback**, chưa phải SageMaker Training Job. F1 KDDTest+ đo trên AWS: RF `0,762453`, SVM `0,706118`, XGBoost `0,770881` (đều theo flow); LSTM `0,718540` theo **cửa sổ 20 flow**, không so trực tiếp. Autoencoder chưa chạy trên AWS. Mở **SageMaker AI → Pipelines** để xem `bigdata-ids-dev-train`, `bigdata-ids-dev-xgboost` và `bigdata-ids-dev-lstm`; xem thêm [hướng dẫn hai model mới](./ml-ids-zero-trust-cloud/docs/lstm-xgboost-aws.md). CLI đọc trạng thái:

```powershell
$runArn = "arn:aws:sagemaker:ap-southeast-1:101728439989:pipeline/bigdata-ids-dev-train/execution/w53s4k21lvg6"
aws sagemaker describe-pipeline-execution --pipeline-execution-arn $runArn --profile default --region ap-southeast-1 --query "{Status:PipelineExecutionStatus,Failure:FailureReason}"
aws sagemaker list-pipeline-execution-steps --pipeline-execution-arn $runArn --profile default --region ap-southeast-1
```

**Thấy gì:** RF status `Succeeded`; Model Registry `bigdata-ids-dev-rf/4` đã được duyệt và có evaluation JSON. Các package v1–v3 bị từ chối vì lỗi đóng gói inference, không dùng để triển khai. Đừng chạy `start-pipeline-execution` chỉ để kiểm tra vì nó phát sinh job mới và chi phí. Số LSTM/XGBoost trong README repo tham khảo là **số tác giả công bố**. [SageMaker Pipelines](https://docs.aws.amazon.com/sagemaker/latest/dg/pipelines-overview.html).

### 5.5 Suy luận và theo dõi — **tôi đã tạo; bạn xem demo**

RF package version 4 và XGBoost package version 1 được duyệt; hai endpoint SageMaker Serverless đều `InService` và trả dự đoán đúng cho hàng KDDTest+ số 0. LSTM package version 1 và endpoint riêng cũng `InService`; smoke test với 20 hàng KDDTest+ trả dự đoán đúng cho nhãn hàng cuối. API LSTM cần tensor đã tiền xử lý `20×25`; dùng script trong [hướng dẫn hai model mới](./ml-ids-zero-trust-cloud/docs/lstm-xgboost-aws.md). Endpoint LSTM đôi khi trả `ModelError` không có phản hồi; script có retry giới hạn cho lỗi này. Đọc [trạng thái triển khai](./ml-ids-zero-trust-cloud/docs/aws-deployment-status.md). Drift demo đã ghi report S3 và metric CloudWatch; alarm đã chuyển `ALARM` với một cửa sổ **synthetic shift**. Chưa có Batch Transform, job PSI theo lịch hoặc SNS email. Trong Console xem **SageMaker AI → Inference → Endpoints**, **CloudWatch → Logs/Metrics/Alarms**. Serverless Inference không hỗ trợ Model Monitor tích hợp; drift demo dùng script riêng. [AWS feature matrix](https://docs.aws.amazon.com/sagemaker/latest/dg/model-deploy-feature-matrix.html).

**Điểm dừng an toàn:** sau khi pipeline/endpoint chạy được, kiểm tra Billing/Budget và xóa endpoint/app không cần dùng trước khi thêm UNSW-NB15 hoặc CIC-IDS2017.

## 6. Khi nào nối GitHub Actions với AWS

Chỉ sau khi mục 5 chạy tốt từ máy local. `aws login` **chỉ dùng trên máy bạn**, không dùng trong GitHub Actions. GitHub Actions cần OIDC IAM role; đây là phần cấu hình AWS bổ sung nhỏ nhưng tránh lưu access key trên GitHub. [GitHub OIDC hướng dẫn chính thức](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).

### 6.1 Tạo OIDC provider và role — **tôi viết trust policy; bạn cung cấp repo/branch**

1. Bạn gửi `OWNER/REPO` và branch cho phép deploy, ví dụ `main`.
2. Tôi tạo IAM OIDC provider `https://token.actions.githubusercontent.com`, audience `sts.amazonaws.com`, và role chỉ tin đúng repo/branch. Repo mới có thể dùng định dạng `sub` kèm GitHub organization/repository ID; vì vậy **không sao chép trust policy mẫu cũ nguyên xi**. Tôi sẽ tạo policy theo repo thực và kiểm tra với [tài liệu GitHub action hiện hành](https://github.com/aws-actions/configure-aws-credentials/blob/main/README.md). AWS yêu cầu điều kiện `sub` không được chỉ là wildcard. [AWS IAM GitHub OIDC](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html).
3. Role đã được thử assume thành công và hiện chỉ có `sagemaker:DescribePipeline`/`sagemaker:StartPipelineExecution` trên ba pipeline `bigdata-ids-dev-train`, `bigdata-ids-dev-xgboost`, `bigdata-ids-dev-lstm`. Nó không có quyền CloudFormation/S3 tổng quát. Workflow `AWS train (manual)` dùng role này để xem pipeline hoặc khởi động một run theo lựa chọn của bạn.

### 6.2 Workflow thử đăng nhập AWS — **đã chạy thành công**

`.github/workflows/aws-smoke.yml` chỉ in identity AWS. `AWS_ROLE_ARN` là ARN role, không phải secret; repository variable đã được đặt và [run 36097779782](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36097779782) thành công. Trigger thủ công tránh chi phí ngoài ý muốn.

```yaml
name: AWS smoke
on:
  workflow_dispatch:
permissions:
  id-token: write
  contents: read
jobs:
  identity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ap-southeast-1
      - run: aws sts get-caller-identity
```

Nếu làm lại từ đầu, vào GitHub **Settings → Secrets and variables → Actions → Variables**, đặt `AWS_ROLE_ARN` bằng output `AwsSmokeRoleArn` của stack OIDC. Mở **Actions → AWS smoke → Run workflow**; log phải in đúng `Account` và ARN của assumed role. Không tạo `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` secret. [GitHub OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws), [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials).

### 6.3 Khởi động pipeline từ GitHub — **chỉ khi muốn train lại**

Workflow `.github/workflows/aws-train.yml` đã có trên `master`; [run 36106066752](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36106066752) xác nhận OIDC và quyền đọc pipeline, còn [run 36126420273](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36126420273) đã khởi chạy SVM thành công. SageMaker execution `c5kl0f3eaypx` hoàn tất, đạt F1 `0,706118` trên KDDTest+ và tạo package `bigdata-ids-dev-classical/5` ở trạng thái chờ duyệt. Workflow hiện có thêm lựa chọn XGBoost và LSTM; [dry run XGBoost](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136376488) và [dry run LSTM](https://github.com/galaxyofmind/ml-ids-zero-trust-cloud/actions/runs/36136379149) đều xanh mà không tạo thêm job. IAM role chỉ được gọi ba pipeline đã đặt tên. Vào **Actions → AWS train (manual) → Run workflow**, giữ branch `master`.

1. Để kiểm tra kết nối mà **không tạo job có phí**, giữ `start_training=false` (mặc định), rồi bấm **Run workflow**. Log phải có `Account` và `PipelineStatus`.
2. Để chạy một lần huấn luyện mới, chọn `start_training=true`, chọn `random_forest`, `svm`, `xgboost` hoặc `lstm`, rồi bấm **Run workflow**. Workflow in ra `PipelineExecutionArn`; vào **SageMaker AI → Pipelines** để xem pipeline tương ứng. RF/XGBoost dùng 30.000 hàng train, SVM 8.000; LSTM dùng 40.000 flow tạo 2.000 cửa sổ và tối đa 12 epoch. Mỗi lần bấm `true` phát sinh Processing job mới và chi phí.
3. Workflow chỉ gọi pipeline **đã được triển khai từ máy**. Muốn đổi mã preprocessing/train hoặc template, tôi cập nhật định nghĩa pipeline từ repo local trước; workflow không tự deploy mọi file khi bạn push. Các package mới vào Model Registry với `PendingManualApproval` và phải xem metric trước khi duyệt.

## 7. Lỗi thường gặp: gửi tôi thông tin gì

| Triệu chứng | Kiểm tra trước | Gửi tôi |
|---|---|---|
| `Unable to locate credentials`/session hết hạn | Chạy lại `aws login --profile capstone-dev` hoặc `aws sso login --profile capstone-dev`. | Tên profile, lệnh lỗi, thông báo lỗi; không gửi token. |
| `aws login` báo thiếu quyền | IAM user/role cần `SignInLocalDevelopmentAccess`; nếu dùng SSO thì chuyển sang `aws sso login`. | Tên principal và thông báo lỗi; không gửi mật khẩu. |
| `AccessDenied` | Kiểm tra đúng account/role bằng `aws sts get-caller-identity`. | Action và resource ARN bị từ chối, request ID nếu có. |
| CloudFormation `CREATE_FAILED` | Mở stack → **Events**, lấy **Reason** của resource đỏ đầu tiên. | Stack name, resource logical ID, reason. |
| Glue `FAILED` | Mở Glue → Job runs → CloudWatch logs. | Job run ID và 20–30 dòng lỗi cuối, không gửi dữ liệu nhạy cảm. |
| SageMaker Pipeline `Failed` | Mở step đỏ và log Processing/Training tương ứng. | Pipeline execution ARN, step name, FailureReason. |
| Athena không thấy bảng | Kiểm tra Region, database, Glue job và Query result location. | Database/table name, screenshot lỗi/query. |
| GitHub workflow không hiện | File phải ở `.github/workflows/` trên default branch; Actions phải được bật. | Repo URL, branch, tên workflow. |
| GitHub `AssumeRoleWithWebIdentity` lỗi | Kiểm tra OIDC provider, audience, `sub` thực của repo/branch/environment, role ARN. | Bước lỗi trong run; không gửi credential. |
| Không nhận email cảnh báo | Kiểm tra subscription `PendingConfirmation` và spam. | Topic ARN, trạng thái subscription. |

## 8. Kết thúc buổi làm việc

Mỗi buổi: ghi lại stack/job/pipeline/endpoint đang chạy, kiểm tra Budget, dừng schedule thử nghiệm và xóa endpoint/app không cần dùng. Đừng xóa bucket raw/artifact khi chưa chốt dữ liệu cần giữ. Xóa SageMaker endpoint không tự xóa model, endpoint config hay artifact S3. [AWS cleanup](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints-delete-resources.html).

**Bước tiếp theo sau tài liệu:** bạn hoàn tất mục 3.1–3.3 và 4.1; tôi tạo các template/script ở mục 5 theo [runbook](./DEPLOYMENT_RUNBOOK.md). Tài liệu này không yêu cầu bạn tự viết CloudFormation hoặc sửa mã model.
