param(
    [string]$Profile = 'capstone-dev',
    [string]$Region = 'ap-southeast-1',
    [string]$AccountId = '101728439989',
    [string]$StackName = 'bigdata-ids-dev-foundation',
    [switch]$AllowRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$template = Join-Path $repoRoot 'infra/foundation.yaml'

$identityJson = aws sts get-caller-identity --profile $Profile --region $Region --output json
if ($LASTEXITCODE -ne 0) { throw 'AWS identity check failed.' }
$identity = $identityJson | ConvertFrom-Json
if ($identity.Account -ne $AccountId -or (($identity.Arn -match ':root$') -and -not $AllowRoot)) {
    throw "Unexpected AWS identity: $($identity.Arn)"
}

aws cloudformation validate-template --template-body "file://$template" --profile $Profile --region $Region | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'CloudFormation template validation failed.' }

aws cloudformation deploy `
    --template-file $template `
    --stack-name $StackName `
    --capabilities CAPABILITY_IAM `
    --no-fail-on-empty-changeset `
    --profile $Profile `
    --region $Region
if ($LASTEXITCODE -ne 0) { throw 'CloudFormation deploy failed. Review stack events.' }

aws cloudformation describe-stacks `
    --stack-name $StackName `
    --query 'Stacks[0].{Status:StackStatus,Outputs:Outputs}' `
    --profile $Profile `
    --region $Region `
    --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read stack outputs.' }
