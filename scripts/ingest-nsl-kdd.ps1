param(
    [string]$Profile = 'capstone-dev',
    [string]$Region = 'ap-southeast-1',
    [string]$AccountId = '101728439989',
    [string]$StackName = 'bigdata-ids-dev-foundation',
    [string]$DatasetPath = 'data/KDDTrain+.txt',
    [string]$TestDatasetPath = 'data/KDDTest+.txt',
    [switch]$AllowRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$dataset = (Resolve-Path (Join-Path $repoRoot $DatasetPath)).Path
$testDataset = (Resolve-Path (Join-Path $repoRoot $TestDatasetPath)).Path
$identityJson = aws sts get-caller-identity --profile $Profile --region $Region --output json
if ($LASTEXITCODE -ne 0) { throw 'AWS identity check failed.' }
$identity = $identityJson | ConvertFrom-Json
if ($identity.Account -ne $AccountId -or (($identity.Arn -match ':root$') -and -not $AllowRoot)) {
    throw "Unexpected AWS identity: $($identity.Arn)"
}

$bucket = aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query 'Stacks[0].Outputs[?OutputKey==`DataBucketName`].OutputValue | [0]' `
    --output text --profile $Profile --region $Region
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($bucket) -or $bucket -eq 'None') {
    throw 'Data bucket output not found.'
}

$checksum = (Get-FileHash -Algorithm SHA256 -Path $dataset).Hash.ToLowerInvariant()
$lineCount = (Get-Content -Path $dataset | Measure-Object -Line).Lines
if ($lineCount -ne 125973) { throw "Unexpected NSL-KDD row count: $lineCount" }
$testChecksum = (Get-FileHash -Algorithm SHA256 -Path $testDataset).Hash.ToLowerInvariant()
$testLineCount = (Get-Content -Path $testDataset | Measure-Object -Line).Lines
if ($testLineCount -ne 22544) { throw "Unexpected NSL-KDD test row count: $testLineCount" }
$file = Get-Item -LiteralPath $dataset
$testFile = Get-Item -LiteralPath $testDataset
$manifest = [ordered]@{
    dataset_id = 'nsl-kdd'
    dataset_version = 'v1'
    source_url = 'https://github.com/defcom17/NSL_KDD'
    source_attribution = 'NSL-KDD, University of New Brunswick; defcom17 GitHub mirror'
    train = @{ file_name = $file.Name; sha256 = $checksum; bytes = $file.Length; rows = $lineCount }
    test = @{ file_name = $testFile.Name; sha256 = $testChecksum; bytes = $testFile.Length; rows = $testLineCount }
    ingested_at_utc = (Get-Date).ToUniversalTime().ToString('o')
}
$manifestPath = Join-Path $repoRoot 'data/nsl-kdd-manifest.json'
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8
$prefix = "s3://$bucket/raw/dataset=nsl-kdd/version=v1"

aws s3 cp $dataset "$prefix/KDDTrain+.txt" --profile $Profile --region $Region --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Dataset upload failed.' }
aws s3 cp $testDataset "$prefix/KDDTest+.txt" --profile $Profile --region $Region --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Test dataset upload failed.' }
aws s3 cp $manifestPath "$prefix/manifest.json" --profile $Profile --region $Region --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Manifest upload failed.' }

Write-Output "Data URI: $prefix/KDDTrain+.txt"
Write-Output "Train: $lineCount rows, SHA256 $checksum"
Write-Output "Test: $testLineCount rows, SHA256 $testChecksum"
