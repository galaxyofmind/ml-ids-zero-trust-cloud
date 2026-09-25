param(
    [string]$Profile = 'capstone-dev',
    [string]$Region = 'ap-southeast-1',
    [string]$AccountId = '101728439989',
    [string]$StackName = 'bigdata-ids-dev-foundation',
    [switch]$AllowRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$train = (Resolve-Path (Join-Path $repoRoot 'data/UNSW_NB15_training-set.csv')).Path
$test = (Resolve-Path (Join-Path $repoRoot 'data/UNSW_NB15_testing-set.csv')).Path
$identityJson = aws sts get-caller-identity --profile $Profile --region $Region --output json
if ($LASTEXITCODE -ne 0) { throw 'AWS identity check failed.' }
$identity = $identityJson | ConvertFrom-Json
if ($identity.Account -ne $AccountId -or (($identity.Arn -match ':root$') -and -not $AllowRoot)) {
    throw "Unexpected AWS identity: $($identity.Arn)"
}

$stackJson = aws cloudformation describe-stacks --stack-name $StackName --profile $Profile --region $Region --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read foundation stack.' }
$bucket = (($stackJson | ConvertFrom-Json).Stacks[0].Outputs | Where-Object OutputKey -eq 'DataBucketName').OutputValue
if (-not $bucket) { throw 'Data bucket output missing.' }

$trainRows = (Get-Content $train | Measure-Object -Line).Lines - 1
$testRows = (Get-Content $test | Measure-Object -Line).Lines - 1
if ($trainRows -ne 175341 -or $testRows -ne 82332) {
    throw "Unexpected UNSW-NB15 split counts: train=$trainRows test=$testRows"
}
$manifest = [ordered]@{
    dataset_id = 'unsw-nb15'
    dataset_version = 'v1'
    original_source = 'https://research.unsw.edu.au/projects/unsw-nb15-dataset'
    mirror_source = 'https://github.com/Nir-J/ML-Projects/tree/master/UNSW-Network_Packet_Classification'
    license_note = 'UNSW permits free academic research use; cite Moustafa and Slay as requested by the source.'
    train = @{ file_name = 'UNSW_NB15_training-set.csv'; rows = $trainRows; bytes = (Get-Item $train).Length; sha256 = (Get-FileHash -Algorithm SHA256 $train).Hash.ToLowerInvariant() }
    test = @{ file_name = 'UNSW_NB15_testing-set.csv'; rows = $testRows; bytes = (Get-Item $test).Length; sha256 = (Get-FileHash -Algorithm SHA256 $test).Hash.ToLowerInvariant() }
    ingested_at_utc = (Get-Date).ToUniversalTime().ToString('o')
}
$manifestPath = Join-Path $repoRoot 'data/unsw-nb15-manifest.json'
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8
$prefix = "s3://$bucket/raw/dataset=unsw-nb15/version=v1"

aws s3 cp $train "$prefix/UNSW_NB15_training-set.csv" --only-show-errors --profile $Profile --region $Region
if ($LASTEXITCODE -ne 0) { throw 'UNSW train upload failed.' }
aws s3 cp $test "$prefix/UNSW_NB15_testing-set.csv" --only-show-errors --profile $Profile --region $Region
if ($LASTEXITCODE -ne 0) { throw 'UNSW test upload failed.' }
aws s3 cp $manifestPath "$prefix/manifest.json" --only-show-errors --profile $Profile --region $Region
if ($LASTEXITCODE -ne 0) { throw 'UNSW manifest upload failed.' }

Write-Output "UNSW-NB15 uploaded to $prefix"
Write-Output "Train rows: $trainRows; test rows: $testRows"
