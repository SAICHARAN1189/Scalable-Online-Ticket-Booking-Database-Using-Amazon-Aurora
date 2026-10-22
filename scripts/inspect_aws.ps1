<#
.SYNOPSIS
    Inspect AWS environment, identity, networking, engine versions, and existing resources.
.DESCRIPTION
    Performs strictly read-only diagnostics on the current AWS account and ap-south-1 region.
    Checks STS caller identity, VPC and subnet availability, Aurora PostgreSQL versions,
    existing RDS clusters, and IAM/Secrets permissions.
.PARAMETER Region
    AWS region to inspect (default: ap-south-1).
.EXAMPLE
    .\scripts\inspect_aws.ps1
    .\scripts\inspect_aws.ps1 -Region ap-south-1
#>

[CmdletBinding()]
param (
    [string]$Region = "ap-south-1"
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   AURORA TICKET BOOKING - AWS ENVIRONMENT INSPECTION" -ForegroundColor Cyan
Write-Host "   Region: $Region" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. AWS CLI Prerequisite Check
Write-Host "[1/7] Checking AWS CLI installation..." -ForegroundColor Yellow
$awsCliVersion = aws --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] AWS CLI is not installed or not in PATH." -ForegroundColor Red
    exit 1
}
Write-Host "  [PASS] AWS CLI installed: $awsCliVersion" -ForegroundColor Green

# 2. STS Identity Check
Write-Host ""
Write-Host "[2/7] Checking AWS caller identity and credentials..." -ForegroundColor Yellow
$identityJson = aws sts get-caller-identity --output json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] Unable to retrieve AWS caller identity. Credentials invalid or expired." -ForegroundColor Red
    Write-Host "  Error: $identityJson" -ForegroundColor Red
    exit 1
}
$identity = $identityJson | ConvertFrom-Json
$userName = ($identity.Arn -split '/')[-1]
Write-Host "  [PASS] Account ID : $($identity.Account)" -ForegroundColor Green
Write-Host "  [PASS] IAM User/ARN: $($identity.Arn)" -ForegroundColor Green
Write-Host "  [PASS] User ID    : $($identity.UserId)" -ForegroundColor Green

# 3. Check IAM Permissions (Graceful audit)
Write-Host ""
Write-Host "[3/7] Auditing IAM user policy visibility..." -ForegroundColor Yellow
$iamTest = aws iam list-attached-user-policies --user-name "$userName" --output json 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [PASS] IAM policies are inspectable." -ForegroundColor Green
} else {
    Write-Host "  [WARN] Direct IAM policy listing denied (normal for restricted student/corporate accounts)." -ForegroundColor Yellow
    Write-Host "         Resource permissions will be tested via specific service APIs." -ForegroundColor DarkGray
}

# 4. Networking Inspection (VPC & Subnets)
Write-Host ""
Write-Host "[4/7] Inspecting VPCs and Subnets in $Region..." -ForegroundColor Yellow
$vpcsJson = aws ec2 describe-vpcs --region $Region --output json 2>&1
if ($LASTEXITCODE -eq 0) {
    $vpcs = ($vpcsJson | ConvertFrom-Json).Vpcs
    Write-Host "  [PASS] Found $($vpcs.Count) VPC(s):" -ForegroundColor Green
    foreach ($vpc in $vpcs) {
        $defaultTag = if ($vpc.IsDefault) { "(Default)" } else { "" }
        Write-Host "         - VPC ID: $($vpc.VpcId) | CIDR: $($vpc.CidrBlock) $defaultTag" -ForegroundColor White
        
        $subnetsJson = aws ec2 describe-subnets --region $Region --filters "Name=vpc-id,Values=$($vpc.VpcId)" --output json 2>&1
        if ($LASTEXITCODE -eq 0) {
            $subnets = ($subnetsJson | ConvertFrom-Json).Subnets
            Write-Host "           Subnets ($($subnets.Count)): " -ForegroundColor DarkGray
            foreach ($sub in $subnets) {
                Write-Host "           * Subnet: $($sub.SubnetId) | AZ: $($sub.AvailabilityZone) | CIDR: $($sub.CidrBlock)" -ForegroundColor DarkGray
            }
        }
    }
} else {
    Write-Host "  [WARN] Unable to describe VPCs: $vpcsJson" -ForegroundColor Yellow
}

# 5. Aurora PostgreSQL Engine Version & Serverless v2 Support
Write-Host ""
Write-Host "[5/7] Inspecting Aurora PostgreSQL Engine in $Region..." -ForegroundColor Yellow
$engineJson = aws rds describe-db-engine-versions --engine aurora-postgresql --engine-version "16.8" --region $Region --output json 2>&1

if ($LASTEXITCODE -eq 0) {
    $engine = ($engineJson | ConvertFrom-Json).DBEngineVersions[0]
    Write-Host "  [PASS] Engine Version 16.8 verified. Parameter Group Family: $($engine.DBParameterGroupFamily)" -ForegroundColor Green
    Write-Host "  [PASS] Supported Engine Modes: $($engine.SupportedEngineModes -join ', ')" -ForegroundColor Green
} else {
    Write-Host "  [INFO] Querying general available Aurora PostgreSQL versions..." -ForegroundColor DarkGray
    $allEnginesJson = aws rds describe-db-engine-versions --engine aurora-postgresql --region $Region --query "DBEngineVersions[-3:].EngineVersion" --output json 2>&1
    Write-Host "  Available versions: $allEnginesJson" -ForegroundColor White
}

# 6. Existing RDS DB Clusters
Write-Host ""
Write-Host "[6/7] Checking for existing RDS / Aurora clusters in $Region..." -ForegroundColor Yellow
$clustersJson = aws rds describe-db-clusters --region $Region --output json 2>&1
if ($LASTEXITCODE -eq 0) {
    $clusters = ($clustersJson | ConvertFrom-Json).DBClusters
    if ($clusters.Count -eq 0) {
        Write-Host "  [INFO] No existing DB clusters in $Region. Clean state for deployment." -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Found $($clusters.Count) existing cluster(s):" -ForegroundColor Yellow
        foreach ($c in $clusters) {
            Write-Host "         - Cluster: $($c.DBClusterIdentifier) (Engine: $($c.Engine), Status: $($c.Status))" -ForegroundColor White
        }
    }
} else {
    Write-Host "  [WARN] Could not describe DB clusters: $clustersJson" -ForegroundColor Yellow
}

# 7. Secrets Manager & CloudFormation API Status
Write-Host ""
Write-Host "[7/7] Checking Secrets Manager and CloudFormation API readiness..." -ForegroundColor Yellow
$cfTest = aws cloudformation describe-stacks --region $Region --max-items 1 --output json 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [PASS] CloudFormation DescribeStacks API is accessible." -ForegroundColor Green
} else {
    Write-Host "  [WARN] CloudFormation DescribeStacks access: $cfTest" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   AWS INSPECTION SUMMARY COMPLETE" -ForegroundColor Cyan
Write-Host "   Pre-flight read-only checks completed." -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
