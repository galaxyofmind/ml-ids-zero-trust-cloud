param(
    [string]$Profile = 'capstone-dev',
    [string]$Region = 'ap-southeast-1',
    [string]$AccountId = '101728439989',
    [string]$FoundationStack = 'bigdata-ids-dev-foundation',
    [string]$DataStack = 'bigdata-ids-dev-data',
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

$foundationJson = aws cloudformation describe-stacks `
    --stack-name $FoundationStack --profile $Profile --region $Region --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read foundation stack.' }
$outputs = @{}
foreach ($output in (($foundationJson | ConvertFrom-Json).Stacks[0].Outputs)) {
    $outputs[$output.OutputKey] = $output.OutputValue
}
foreach ($required in @('DataBucketName', 'ArtifactBucketName', 'GlueRoleArn', 'FirehoseRoleArn')) {
    if (-not $outputs.ContainsKey($required)) { throw "Missing foundation output: $required" }
}

$scriptPath = Join-Path $repoRoot 'glue/nsl_kdd_etl.py'
$templatePath = Join-Path $repoRoot 'infra/data.yaml'
aws s3 cp $scriptPath "s3://$($outputs.ArtifactBucketName)/code/glue/nsl_kdd_etl.py" `
    --only-show-errors --profile $Profile --region $Region
if ($LASTEXITCODE -ne 0) { throw 'Glue script upload failed.' }
$unswScriptPath = Join-Path $repoRoot 'glue/unsw_etl.py'
aws s3 cp $unswScriptPath "s3://$($outputs.ArtifactBucketName)/code/glue/unsw_etl.py" `
    --only-show-errors --profile $Profile --region $Region
if ($LASTEXITCODE -ne 0) { throw 'UNSW Glue script upload failed.' }
aws cloudformation validate-template --template-body "file://$templatePath" `
    --profile $Profile --region $Region | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Data template validation failed.' }

$parameters = @(
    "DataBucketName=$($outputs.DataBucketName)",
    "ArtifactBucketName=$($outputs.ArtifactBucketName)",
    "GlueRoleArn=$($outputs.GlueRoleArn)",
    "FirehoseRoleArn=$($outputs.FirehoseRoleArn)"
)
aws cloudformation deploy `
    --template-file $templatePath `
    --stack-name $DataStack `
    --parameter-overrides $parameters `
    --no-fail-on-empty-changeset `
    --profile $Profile `
    --region $Region
if ($LASTEXITCODE -ne 0) { throw 'Data stack deploy failed. Review stack events.' }

aws cloudformation describe-stacks `
    --stack-name $DataStack `
    --query 'Stacks[0].{Status:StackStatus,Outputs:Outputs}' `
    --profile $Profile `
    --region $Region `
    --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read data stack outputs.' }
