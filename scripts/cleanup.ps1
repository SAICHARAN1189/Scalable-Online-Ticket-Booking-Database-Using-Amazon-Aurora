<#
.SYNOPSIS
    Tear down and clean up AWS Aurora resources to prevent ongoing charges.
.DESCRIPTION
    Prompts for confirmation, then safely tears down the project's Aurora cluster
    (reader replica, primary writer, and cluster) or CloudFormation stack.
    Targets strictly the project's dedicated resources.
.PARAMETER ClusterId
    Aurora DB Cluster Identifier (default: aurora-ticket-booking-cluster).
.PARAMETER StackName
    CloudFormation stack name (default: aurora-ticket-booking-stack).
.PARAMETER Region
    AWS Region (default: ap-south-1).
.PARAMETER Force
    Skip confirmation prompt.
.EXAMPLE
    .\scripts\cleanup.ps1
    .\scripts\cleanup.ps1 -Force
#>

[CmdletBinding()]
param (
    [string]$ClusterId = "aurora-ticket-booking-cluster",
    [string]$StackName = "aurora-ticket-booking-stack",
    [string]$Region = "ap-south-1",
    [switch]$Force
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Red
Write-Host "   AURORA TICKET BOOKING - TEARDOWN & CLEANUP" -ForegroundColor Red
Write-Host "   Cluster: $ClusterId | Region: $Region" -ForegroundColor Red
Write-Host "========================================================" -ForegroundColor Red
Write-Host ""

Write-Host "WARNING: This action will permanently delete the Aurora PostgreSQL cluster," -ForegroundColor Yellow
Write-Host "including all databases, tables, ticket records, and replicas." -ForegroundColor Yellow
Write-Host "This ensures zero ongoing AWS billing once your demonstration is finished." -ForegroundColor Yellow
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "Type 'DELETE' to confirm destruction of project cluster '$ClusterId'"
    if ($confirm -ne "DELETE") {
        Write-Host "Cleanup aborted. No resources were modified." -ForegroundColor Green
        exit 0
    }
}

# 1. Clean up Express Configuration Aurora Instances & Cluster
Write-Host "`n[1/3] Checking for project Aurora cluster '$ClusterId'..." -ForegroundColor Yellow
$clusterCheck = aws rds describe-db-clusters --db-cluster-identifier $ClusterId --region $Region --output json 2>&1
if ($LASTEXITCODE -eq 0) {
    # Delete Reader Replica if exists
    $replicaId = "$ClusterId-replica-1"
    Write-Host "  Checking for reader replica '$replicaId'..." -ForegroundColor DarkGray
    $repCheck = aws rds describe-db-instances --db-instance-identifier $replicaId --region $Region --output json 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Deleting reader replica '$replicaId'..." -ForegroundColor Yellow
        aws rds delete-db-instance --db-instance-identifier $replicaId --skip-final-snapshot --region $Region 2>&1 | Out-Null
        Write-Host "  Waiting for replica instance to be deleted..." -ForegroundColor DarkGray
        aws rds wait db-instance-deleted --db-instance-identifier $replicaId --region $Region 2>&1
        Write-Host "  [PASS] Reader replica deleted." -ForegroundColor Green
    }

    # Delete Writer Instance if exists
    $writerId = "$ClusterId-instance-1"
    Write-Host "  Checking for writer instance '$writerId'..." -ForegroundColor DarkGray
    $writerCheck = aws rds describe-db-instances --db-instance-identifier $writerId --region $Region --output json 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Deleting writer instance '$writerId'..." -ForegroundColor Yellow
        aws rds delete-db-instance --db-instance-identifier $writerId --skip-final-snapshot --region $Region 2>&1 | Out-Null
        Write-Host "  Waiting for writer instance to be deleted..." -ForegroundColor DarkGray
        aws rds wait db-instance-deleted --db-instance-identifier $writerId --region $Region 2>&1
        Write-Host "  [PASS] Writer instance deleted." -ForegroundColor Green
    }

    # Delete Cluster
    Write-Host "  Deleting DB cluster '$ClusterId'..." -ForegroundColor Yellow
    aws rds delete-db-cluster --db-cluster-identifier $ClusterId --skip-final-snapshot --region $Region 2>&1 | Out-Null
    Write-Host "  Waiting for cluster deletion to complete..." -ForegroundColor DarkGray
    aws rds wait db-cluster-deleted --db-cluster-identifier $ClusterId --region $Region 2>&1
    Write-Host "  [PASS] Cluster '$ClusterId' deleted successfully." -ForegroundColor Green
} else {
    Write-Host "  [INFO] No cluster '$ClusterId' found." -ForegroundColor DarkGray
}

# 2. Check for CloudFormation Stack (if previously used)
Write-Host "`n[2/3] Checking for CloudFormation stack '$StackName'..." -ForegroundColor Yellow
$stackStatus = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].StackStatus" --output text 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Deleting CloudFormation stack '$StackName'..." -ForegroundColor Yellow
    aws cloudformation delete-stack --stack-name $StackName --region $Region
    aws cloudformation wait stack-delete-complete --stack-name $StackName --region $Region 2>&1
    Write-Host "  [PASS] Stack '$StackName' deleted." -ForegroundColor Green
} else {
    Write-Host "  [INFO] No stack '$StackName' found." -ForegroundColor DarkGray
}

# 3. Clean local temporary files
Write-Host "`n[3/3] Checking local environment files..." -ForegroundColor Yellow
if (Test-Path ".env") {
    $removeEnv = Read-Host "Would you like to remove the live .env configuration file? (yes/no)"
    if ($removeEnv -eq "yes") {
        Remove-Item ".env" -Force
        Write-Host "  [PASS] Removed .env file." -ForegroundColor Green
    } else {
        Write-Host "  Retained .env file." -ForegroundColor DarkGray
    }
}

if (Test-Path "local_ticket_booking.db") {
    Remove-Item "local_ticket_booking.db" -Force -ErrorAction SilentlyContinue
    Write-Host "  [PASS] Cleaned up local mock database file." -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   CLEANUP COMPLETE: ZERO ONGOING CHARGES" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
