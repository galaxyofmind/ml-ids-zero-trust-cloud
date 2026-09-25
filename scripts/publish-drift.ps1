param(
    [string]$Profile = 'capstone-dev',
    [string]$Region = 'ap-southeast-1',
    [string]$AccountId = '101728439989',
    [switch]$AllowRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$identityJson = aws sts get-caller-identity --profile $Profile --region $Region --output json
if ($LASTEXITCODE -ne 0) { throw 'AWS identity check failed.' }
$identity = $identityJson | ConvertFrom-Json
if ($identity.Account -ne $AccountId -or (($identity.Arn -match ':root$') -and -not $AllowRoot)) {
    throw "Unexpected AWS identity: $($identity.Arn)"
}
$python = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) { throw 'Local .venv Python missing; install the AWS requirements first.' }
Push-Location $repoRoot
try {
    & $python src/aws_drift_demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Drift calculation failed.' }
    $foundationJson = aws cloudformation describe-stacks --stack-name bigdata-ids-dev-foundation `
        --profile $Profile --region $Region --output json
    if ($LASTEXITCODE -ne 0) { throw 'Could not read foundation stack.' }
    $bucket = (($foundationJson | ConvertFrom-Json).Stacks[0].Outputs | Where-Object OutputKey -eq 'ArtifactBucketName').OutputValue
    if (-not $bucket) { throw 'Artifact bucket output missing.' }
    foreach ($window in @('stable', 'synthetic_shift', 'official_test')) {
        $path = Join-Path $repoRoot "data/aws-processed/drift/$window.json"
        $result = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        aws s3 cp $path "s3://$bucket/drift/nsl-kdd/v1/$window.json" --only-show-errors `
            --profile $Profile --region $Region
        if ($LASTEXITCODE -ne 0) { throw "Upload failed for $window" }
        aws cloudwatch put-metric-data --namespace 'Capstone/IDS' --metric-name 'MaxPSI' `
            --dimensions DatasetId=nsl-kdd --value $result.max_psi --unit None `
            --profile $Profile --region $Region
        if ($LASTEXITCODE -ne 0) { throw "CloudWatch metric publish failed for $window" }
        Write-Output "$window MaxPSI=$($result.max_psi)"
    }
} finally {
    Pop-Location
}
