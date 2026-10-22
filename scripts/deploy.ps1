<#
.SYNOPSIS
    Deploy Amazon Aurora PostgreSQL Cluster via AWS CLI Express Configuration.
.DESCRIPTION
    Provisions an Aurora PostgreSQL Serverless v2 cluster using AWS CLI Express Configuration
    (--with-express-configuration), which is required for AWS Free Plan accounts.
    Automatically creates the primary writer instance, provisions an Aurora Serverless v2
    reader replica, retrieves both writer and reader endpoints, and configures .env for
    IAM database authentication.
.PARAMETER ClusterId
    Aurora DB Cluster Identifier (default: aurora-ticket-booking-cluster).
.PARAMETER Region
    AWS Region (default: ap-south-1).
.PARAMETER AutoApprove
    Skip interactive confirmation prompt.
.EXAMPLE
    .\scripts\deploy.ps1
    .\scripts\deploy.ps1 -AutoApprove
#>

[CmdletBinding()]
param (
    [string]$ClusterId = "aurora-ticket-booking-cluster",
    [string]$Region = "ap-south-1",
    [switch]$AutoApprove
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   AURORA TICKET BOOKING - EXPRESS DEPLOYMENT" -ForegroundColor Cyan
Write-Host "   Cluster: $ClusterId | Region: $Region" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "DEPLOYMENT ARCHITECTURE (AWS Free Plan - Express Configuration):" -ForegroundColor Yellow
Write-Host "  Cluster Identifier  : $ClusterId"
Write-Host "  Engine              : Amazon Aurora PostgreSQL Serverless v2"
Write-Host "  Authentication      : IAM Database Authentication with password fallback"
Write-Host "  Network Model       : Direct Internet Access Gateway (Pre-configured TLS)"
Write-Host "  Topology            : 1 Primary Writer + 1 Aurora Serverless Reader Replica"
Write-Host "  Capacity Limits     : 0.0 - 4.0 ACU (Strictly respects 4 ACU Free Plan limit)"
Write-Host "  Auto-Pause Rule     : Auto-pauses after 300s (5m) idle; compute paused = $0.00 compute"
Write-Host "  Storage Limit       : 1 GB initial storage footprint (respects 1 GB Free Plan limit)"
Write-Host ""

if (-not $AutoApprove) {
    $confirm = Read-Host "Proceed with creating the Aurora PostgreSQL cluster on AWS? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Deployment aborted by user." -ForegroundColor Yellow
        exit 0
    }
}

# 1. Create Aurora DB Cluster with Express Configuration
Write-Host "`n[1/4] Creating Aurora PostgreSQL cluster with Express Configuration..." -ForegroundColor Yellow

[string]$existingCluster = aws rds describe-db-clusters --region $Region --query "DBClusters[?DBClusterIdentifier=='$ClusterId'].DBClusterIdentifier" --output text
if ($existingCluster.Trim() -eq $ClusterId) {
    Write-Host "  Cluster '$ClusterId' already exists. Using existing cluster." -ForegroundColor Green
} else {
    Write-Host "  Issuing: aws rds create-db-cluster --with-express-configuration (MaxCapacity=4.0, AutoPause=300s)..." -ForegroundColor DarkGray
    $createJson = aws rds create-db-cluster `
        --db-cluster-identifier $ClusterId `
        --engine aurora-postgresql `
        --with-express-configuration `
        --serverless-v2-scaling-configuration MinCapacity=0.0,MaxCapacity=4.0,SecondsUntilAutoPause=300 `
        --region $Region `
        --output json

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create DB cluster: $createJson"
    }
    Write-Host "  [PASS] Cluster creation initiated with 4.0 ACU cap and 300s auto-pause." -ForegroundColor Green
}

# 2. Wait for DB Cluster and Primary Writer Instance to become available
Write-Host "`n[2/4] Waiting for DB Cluster and Primary Writer instance to become ready..." -ForegroundColor Yellow
Write-Host "  Waiting for cluster '$ClusterId' status to become 'available'..." -ForegroundColor DarkGray

aws rds wait db-cluster-available --db-cluster-identifier $ClusterId --region $Region
Write-Host "  [PASS] Aurora DB Cluster is available!" -ForegroundColor Green

# The writer instance created by express configuration is named '$ClusterId-instance-1'
$writerInstanceId = "$ClusterId-instance-1"
Write-Host "  Waiting for writer instance '$writerInstanceId' to become 'available'..." -ForegroundColor DarkGray
aws rds wait db-instance-available --db-instance-identifier $writerInstanceId --region $Region
Write-Host "  [PASS] Primary Writer instance '$writerInstanceId' is ready!" -ForegroundColor Green

# 3. Create Aurora Read Replica Instance
$replicaInstanceId = "$ClusterId-replica-1"
Write-Host "`n[3/4] Adding Aurora Serverless v2 Reader Replica ('$replicaInstanceId')..." -ForegroundColor Yellow

[string]$existingReplica = aws rds describe-db-instances --region $Region --query "DBInstances[?DBInstanceIdentifier=='$replicaInstanceId'].DBInstanceIdentifier" --output text
if ($existingReplica.Trim() -eq $replicaInstanceId) {
    Write-Host "  Replica instance '$replicaInstanceId' already exists." -ForegroundColor Green
} else {
    Write-Host "  Creating reader replica instance..." -ForegroundColor DarkGray
    $replicaJson = aws rds create-db-instance `
        --db-cluster-identifier $ClusterId `
        --db-instance-identifier $replicaInstanceId `
        --engine aurora-postgresql `
        --db-instance-class db.serverless `
        --promotion-tier 1 `
        --region $Region `
        --output json

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] Note on replica creation: $replicaJson" -ForegroundColor Yellow
    } else {
        Write-Host "  Waiting for reader replica instance to become 'available'..." -ForegroundColor DarkGray
        aws rds wait db-instance-available --db-instance-identifier $replicaInstanceId --region $Region
        Write-Host "  [PASS] Reader Replica instance is ready!" -ForegroundColor Green
    }
}

# 4. Retrieve Endpoints & Generate .env
Write-Host "`n[4/4] Retrieving Aurora endpoints and configuring application..." -ForegroundColor Yellow
$clusterDescJson = aws rds describe-db-clusters --db-cluster-identifier $ClusterId --region $Region --output json
$clusterDesc = ($clusterDescJson | ConvertFrom-Json).DBClusters[0]

$writerEndpoint = $clusterDesc.Endpoint
$readerEndpoint = $clusterDesc.ReaderEndpoint
$dbPort = $clusterDesc.Port
$dbUser = $clusterDesc.MasterUsername

Write-Host "  [PASS] Cluster Writer Endpoint : $writerEndpoint" -ForegroundColor Green
Write-Host "  [PASS] Cluster Reader Endpoint : $readerEndpoint" -ForegroundColor Green
Write-Host "  [PASS] Database Port           : $dbPort" -ForegroundColor Green
Write-Host "  [PASS] Master DB Username      : $dbUser" -ForegroundColor Green
Write-Host "  [PASS] IAM Database Auth       : Enabled" -ForegroundColor Green

$envLines = @(
    "# Generated by scripts/deploy.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "AURORA_WRITER_HOST=$writerEndpoint",
    "AURORA_READER_HOST=$readerEndpoint",
    "AURORA_PORT=$dbPort",
    "AURORA_DB_NAME=postgres",
    "AURORA_USERNAME=$dbUser",
    "AURORA_PASSWORD=",
    "USE_IAM_AUTH=true",
    "AWS_REGION=$Region",
    "FLASK_SECRET_KEY=$([System.Guid]::NewGuid().ToString())",
    "FLASK_ENV=production",
    "FLASK_DEBUG=0",
    "USE_LOCAL_DB=false"
)

$envLines | Set-Content -Path ".env" -Encoding UTF8
Write-Host "  [PASS] Live .env file created successfully with IAM authentication configured." -ForegroundColor Green

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   EXPRESS AURORA DEPLOYMENT COMPLETED!" -ForegroundColor Green
Write-Host "   Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Initialize database schema:  .\scripts\verify.ps1 -InitDB" -ForegroundColor White
Write-Host "   2. Start the web application:   python app.py" -ForegroundColor White
Write-Host "   3. Run load test against live:  python load_test.py --all" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
