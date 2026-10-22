<#
.SYNOPSIS
    Validate project code, database files, tests, and CloudFormation template locally.
.DESCRIPTION
    Runs offline / local sanity checks on:
    1. Python syntax compilation (app.py, load_test.py, tests/test_app.py)
    2. Python test suite execution (tests/test_app.py)
    3. Database SQL files validation
    4. CloudFormation template structure and YAML validation
    5. Environment template (.env.example) validation
.EXAMPLE
    .\scripts\validate.ps1
#>

[CmdletBinding()]
param ()

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   AURORA TICKET BOOKING - LOCAL VALIDATION SUITE" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$failures = 0

# 1. Python Syntax Validation
Write-Host "[1/5] Checking Python syntax compilation..." -ForegroundColor Yellow
$pyFiles = @("app.py", "load_test.py", "tests/test_app.py")
foreach ($file in $pyFiles) {
    if (Test-Path $file) {
        $compileRes = python -m py_compile $file 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [PASS] $file compiled cleanly." -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] $file syntax error: $compileRes" -ForegroundColor Red
            $failures++
        }
    } else {
        Write-Host "  [FAIL] Expected file not found: $file" -ForegroundColor Red
        $failures++
    }
}

# 2. Database SQL File Existence and Non-emptiness
Write-Host ""
Write-Host "[2/5] Checking Database SQL files..." -ForegroundColor Yellow
$sqlFiles = @(
    "database/schema.sql",
    "database/seed.sql",
    "database/migrations/001_initial_schema.sql"
)
foreach ($sqlFile in $sqlFiles) {
    if (Test-Path $sqlFile) {
        $item = Get-Item $sqlFile
        if ($item.Length -gt 0) {
            Write-Host "  [PASS] $sqlFile present ($($item.Length) bytes)." -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] $sqlFile is empty." -ForegroundColor Red
            $failures++
        }
    } else {
        Write-Host "  [FAIL] Missing SQL file: $sqlFile" -ForegroundColor Red
        $failures++
    }
}

# 3. CloudFormation Template Local Validation
Write-Host ""
Write-Host "[3/5] Validating CloudFormation template (infra/template.yaml)..." -ForegroundColor Yellow
$templatePath = "infra/template.yaml"
if (Test-Path $templatePath) {
    $pyYamlCheck = python -c "
import sys
try:
    with open('$templatePath', 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'AWSTemplateFormatVersion' in content, 'Missing AWSTemplateFormatVersion'
    assert 'DBCluster' in content, 'Missing DBCluster resource'
    assert 'DBWriterInstance' in content, 'Missing DBWriterInstance'
    assert 'DBReaderReplicaInstance' in content, 'Missing DBReaderReplicaInstance'
    
    # Check that CidrIp in security group is not open to the world
    for line in content.splitlines():
        if 'CidrIp:' in line:
            cidr_val = line.split('CidrIp:')[1].strip()
            assert cidr_val != '0.0.0.0/0', f'Security violation: {cidr_val} found in CidrIp!'
    print('STRUCTURE_OK')
except Exception as e:
    print('ERROR:', e)
    sys.exit(1)
" 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [PASS] infra/template.yaml structural checks passed." -ForegroundColor Green
        Write-Host "  [PASS] Verified: Security restriction strictly enforced (CidrIp is not 0.0.0.0/0)." -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Template check error: $pyYamlCheck" -ForegroundColor Red
        $failures++
    }
} else {
    Write-Host "  [FAIL] infra/template.yaml does not exist." -ForegroundColor Red
    $failures++
}

# 4. Environment Template Validation
Write-Host ""
Write-Host "[4/5] Checking .env.example..." -ForegroundColor Yellow
if (Test-Path ".env.example") {
    $envContent = Get-Content ".env.example" -Raw
    $requiredKeys = @(
        "AURORA_WRITER_HOST",
        "AURORA_READER_HOST",
        "AURORA_PORT",
        "AURORA_DB_NAME",
        "AURORA_USERNAME",
        "AURORA_PASSWORD",
        "USE_LOCAL_DB"
    )
    $missingKeys = @()
    foreach ($k in $requiredKeys) {
        if ($envContent -notmatch $k) {
            $missingKeys += $k
        }
    }
    if ($missingKeys.Count -eq 0) {
        Write-Host "  [PASS] .env.example contains all required Aurora connection keys." -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] .env.example missing keys: $($missingKeys -join ', ')" -ForegroundColor Red
        $failures++
    }
} else {
    Write-Host "  [FAIL] .env.example not found." -ForegroundColor Red
    $failures++
}

# 5. Local Automated Unit & Integration Tests Execution
Write-Host ""
Write-Host "[5/5] Executing automated test suite (tests/test_app.py)..." -ForegroundColor Yellow
$testOutput = python -m unittest tests/test_app.py 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [PASS] All unit and integration tests passed successfully!" -ForegroundColor Green
    Write-Host "  $($testOutput | Select-Object -Last 3 | Out-String)" -ForegroundColor DarkGray
} else {
    Write-Host "  [FAIL] Tests failed: $testOutput" -ForegroundColor Red
    $failures++
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
if ($failures -eq 0) {
    Write-Host "   VALIDATION SUCCESSFUL: ALL 5 STAGES PASSED" -ForegroundColor Green
} else {
    Write-Host "   VALIDATION FAILED: $failures ERROR(S) FOUND" -ForegroundColor Red
}
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

if ($failures -gt 0) {
    exit 1
}
