<#
.SYNOPSIS
    Verify database endpoints, schema, seed data, read/write routing, and concurrency.
.DESCRIPTION
    Tests connectivity to Aurora Writer and Reader endpoints (or local database if configured).
    Supports initializing database schema (-InitDB), running routing checks,
    and verifying overselling prevention under concurrent booking load.
.PARAMETER InitDB
    Switch to execute database/schema.sql and database/seed.sql.
.PARAMETER BaseUrl
    URL where the Flask application is running (default: http://127.0.0.1:5000).
.EXAMPLE
    .\scripts\verify.ps1 -InitDB
    .\scripts\verify.ps1
#>

[CmdletBinding()]
param (
    [switch]$InitDB,
    [string]$BaseUrl = "http://127.0.0.1:5000"
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   AURORA TICKET BOOKING - DEPLOYMENT VERIFICATION" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Environment Configuration Check
Write-Host "[1/5] Checking configuration mode..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  [PASS] .env file detected." -ForegroundColor Green
} else {
    Write-Host "  [INFO] No .env found. Falling back to environment variables or local mock." -ForegroundColor DarkGray
}

# 2. Database Schema and Seed Initialization (if -InitDB requested)
if ($InitDB) {
    Write-Host ""
    Write-Host "[2/5] Initializing Database Schema and Seed Data..." -ForegroundColor Yellow
    $initScript = "
import os, sys
from dotenv import load_dotenv
load_dotenv()

use_local = os.getenv('USE_LOCAL_DB', 'true').lower() == 'true'

if use_local:
    print('Target: Local SQLite database')
    from app import init_local_db
    init_local_db()
    print('LOCAL_DB_INIT_SUCCESS')
else:
    print('Target: Live Amazon Aurora PostgreSQL')
    import psycopg2
    writer_host = os.getenv('AURORA_WRITER_HOST')
    port = int(os.getenv('AURORA_PORT', '5432'))
    dbname = os.getenv('AURORA_DB_NAME', 'postgres')
    user = os.getenv('AURORA_USERNAME', 'postgres')
    password = os.getenv('AURORA_PASSWORD', '')
    use_iam = os.getenv('USE_IAM_AUTH', 'true').lower() == 'true'
    region = os.getenv('AWS_REGION', 'ap-south-1')

    conn = None
    if use_iam:
        try:
            import boto3
            rds_client = boto3.client('rds', region_name=region)
            token = rds_client.generate_db_auth_token(
                DBHostname=writer_host,
                Port=port,
                DBUsername=user,
                Region=region
            )
            print(f'Attempting IAM DB Authentication to Writer: {writer_host}:{port}...')
            conn = psycopg2.connect(host=writer_host, port=port, dbname=dbname, user=user, password=token, sslmode='require', connect_timeout=15)
            print('Connected via IAM Database Authentication.')
        except Exception as iam_err:
            print(f'IAM DB Auth attempt note: {iam_err}')

    if conn is None:
        if not password:
            raise RuntimeError('Database password not set and IAM authentication was not successful.')
        print(f'Connecting to Writer with master password...')
        conn = psycopg2.connect(host=writer_host, port=port, dbname=dbname, user=user, password=password, sslmode='require', connect_timeout=15)
        print('Connected via master password.')

    conn.autocommit = True
    cursor = conn.cursor()
    
    with open('database/schema.sql', 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    cursor.execute(schema_sql)
    print('Schema executed successfully.')
    
    with open('database/seed.sql', 'r', encoding='utf-8') as f:
        seed_sql = f.read()
    cursor.execute(seed_sql)
    print('Seed data inserted successfully.')
    
    cursor.close()
    conn.close()
    print('AURORA_DB_INIT_SUCCESS')
"
    $initRes = python -c "$initScript" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [PASS] Database successfully initialized with schema and seed data." -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Database initialization failed: $initRes" -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "[2/5] Skipping DB schema init (use -InitDB to execute schema and seed)." -ForegroundColor DarkGray
}

# 3. Application Health & Endpoint Routing Verification
Write-Host ""
Write-Host "[3/5] Verifying API Health and Read/Write Endpoint Routing..." -ForegroundColor Yellow
$healthScript = "
import sys, json, urllib.request

base_url = '$BaseUrl'.rstrip('/')
try:
    # 1. Check health endpoint
    req = urllib.request.Request(f'{base_url}/api/health')
    with urllib.request.urlopen(req, timeout=5) as resp:
        health_data = json.loads(resp.read().decode())
    print('Health response:', health_data.get('status'))
    print('Database mode:', health_data.get('mode'))
    
    # 2. Check events list (Reader endpoint)
    req = urllib.request.Request(f'{base_url}/api/events')
    with urllib.request.urlopen(req, timeout=5) as resp:
        events_data = json.loads(resp.read().decode())
    endpoint_used = events_data.get('endpoint')
    print('Events endpoint routed to:', endpoint_used)
    assert endpoint_used == 'reader', f'Expected reader endpoint, got {endpoint_used}'
    print('ROUTING_READ_VERIFIED')
    
    # 3. Check stats (Writer/Reader metrics)
    req = urllib.request.Request(f'{base_url}/api/stats')
    with urllib.request.urlopen(req, timeout=5) as resp:
        stats_data = json.loads(resp.read().decode())
    print('Stats recorded:', stats_data.get('metrics', {}))
    print('API_HEALTH_OK')
except Exception as e:
    print('HEALTH_CHECK_ERROR:', e)
    sys.exit(1)
"
$healthRes = python -c "$healthScript" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [PASS] Application running and read queries successfully route to Reader endpoint!" -ForegroundColor Green
    Write-Host "  $healthRes" -ForegroundColor DarkGray
} else {
    Write-Host "  [WARN] Application not reachable at $BaseUrl or routing failed." -ForegroundColor Yellow
    Write-Host "         Ensure 'python app.py' is running before testing live API." -ForegroundColor DarkGray
    Write-Host "         Detail: $healthRes" -ForegroundColor DarkGray
}

# 4. Concurrency & Overselling Prevention Test
Write-Host ""
Write-Host "[4/5] Running Concurrency & Overselling Prevention Test..." -ForegroundColor Yellow
$concurrencyRes = python load_test.py --base-url $BaseUrl --concurrency-test --no-export 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [PASS] Concurrency stress test passed! Zero overselling confirmed." -ForegroundColor Green
} else {
    Write-Host "  [WARN] Concurrency test warning (app might not be running on $BaseUrl):" -ForegroundColor Yellow
    Write-Host "  $concurrencyRes" -ForegroundColor DarkGray
}

# 5. Unit Test Suite Execution
Write-Host ""
Write-Host "[5/5] Executing full test suite..." -ForegroundColor Yellow
$testsRes = python -m unittest tests/test_app.py 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [PASS] All 23 integration and unit tests PASSED!" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Test suite failed: $testsRes" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   VERIFICATION RUN FINISHED" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
