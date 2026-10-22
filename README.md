# Scalable Online Ticket Booking Database Using Amazon Aurora

[![Validation Suite](https://img.shields.io/badge/Validation-5%2F5%20Passed-brightgreen.svg)]()
[![Database](https://img.shields.io/badge/Database-Amazon%20Aurora%20PostgreSQL%2016.8-blue.svg)]()
[![Backend](https://img.shields.io/badge/Backend-Python%20Flask-orange.svg)]()
[![Region](https://img.shields.io/badge/AWS%20Region-ap--south--1%20(Mumbai)-ff9900.svg)]()

A complete, production-grade academic project demonstrating how **Amazon Aurora PostgreSQL Replicas** scale database read traffic while mutating operations (bookings, cancellations, inventory modifications) are strictly directed to the **Aurora Primary Writer endpoint**.

---

## 🌟 Key Features

1. **Dual-Endpoint Routing Architecture:**
   - **Primary Writer Endpoint:** Handles transaction-safe bookings, cancellations, and inventory updates.
   - **Aurora Reader Endpoint:** Load-balances read queries (event browsing, catalog search, user booking lookups, telemetry metrics) across Aurora Read Replicas.
2. **Transaction-Safe Concurrency & Overselling Prevention:**
   - Atomic row-level locking (`SELECT ... FOR UPDATE`) prevents overselling even when tens of users attempt to purchase the final seat concurrently.
   - Schema check constraints (`available_tickets >= 0`) provide defense in depth.
3. **Rich Frontend Application:**
   - Modern, glassmorphic UI with dynamic event cards, category filtering, search, and ticket count indicators.
   - Interactive booking and cancellation modal with validation and instant booking confirmation cards.
   - **Live Database Telemetry Dashboard:** Real-time visibility into query routing, endpoint latency, read vs. write request distributions, and Aurora cluster health.
4. **Repeatable Load Testing Suite (`load_test.py`):**
   - Configurable concurrent read workloads comparing Writer vs. Reader latency.
   - Concurrency stress testing with multi-worker threads attempting to trigger race conditions.
   - Automated performance exports to CSV and JSON formats.
5. **Cost-Aware Infrastructure as Code:**
   - AWS CloudFormation template (`infra/template.yaml`) provisioning Aurora Serverless v2 (0.5 – 2.0 ACU) for minimal idle costs (~$0.12/hr for 1 Writer + 1 Replica).
   - Automated lifecycle scripts: `inspect_aws.ps1`, `validate.ps1`, `deploy.ps1`, `verify.ps1`, and `cleanup.ps1`.

---

## 🏗 System Architecture

```
                             [ Web Browser / Load Test Client ]
                                             |
                                             v
                               [ Flask Web Application Backend ]
                                /                             \
                (POST: /api/book, /api/cancel)          (GET: /api/events, /api/stats)
                              /                                 \
                             v                                   v
               +---------------------------+       +---------------------------+
               |  Aurora Cluster Writer    |       |   Aurora Cluster Reader   |
               |         Endpoint          |       |         Endpoint          |
               +---------------------------+       +---------------------------+
                             |                                   |
                             v                                   v
               +---------------------------+       +---------------------------+
               |  Primary DB Instance      |       |  Aurora Read Replica      |
               |     (PromotionTier: 0)    |       |     (PromotionTier: 1)    |
               +---------------------------+       +---------------------------+
                             \                                   /
                              \                                 /
                   +-------------------------------------------------+
                   | Amazon Aurora Shared Distributed Storage Volume |
                   |     (6-way replication across 3 AZs)            |
                   +-------------------------------------------------+
```

For full architectural details, consult [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 📂 Project Organization

```
aurora-ticket-booking/
├── app.py                     # Main Flask application with dual-endpoint routing
├── load_test.py               # Configurable workload generator & benchmark tool
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variables template
├── database/
│   ├── schema.sql             # PostgreSQL 3NF normalized schema with constraints
│   ├── seed.sql               # Realistic sample event data and ticket inventory
│   └── migrations/
│       └── 001_initial_schema.sql  # Database migration runner
├── infra/
│   └── template.yaml          # AWS CloudFormation template for Aurora Serverless v2
├── scripts/
│   ├── inspect_aws.ps1        # Read-only AWS environment & permissions audit
│   ├── validate.ps1           # 5-stage local validation suite (Code, SQL, Tests)
│   ├── deploy.ps1             # CloudFormation deployment & .env generator
│   ├── verify.ps1             # Post-deployment health, schema & routing verification
│   └── cleanup.ps1            # Safe teardown of AWS resources to stop charges
├── static/
│   ├── app.js                 # Frontend application logic & live telemetry polling
│   └── style.css              # Glassmorphic, modern CSS design system
├── templates/
│   └── index.html             # Responsive single-page application layout
├── tests/
│   └── test_app.py            # 23 automated unit & integration tests
├── ARCHITECTURE.md            # Deep dive into Aurora routing and concurrency
├── COST_ESTIMATE.md           # Itemized AWS cost breakdown & budget controls
├── CLEANUP.md                 # Teardown guide ensuring zero idle AWS charges
└── README.md                  # Project overview & execution guide
```

---

## 🚀 Quick Start Guide

### Option A: Run Locally (Offline Mock Mode — $0.00 Cost)

The application includes an embedded SQLite mock mode replicating Aurora behavior, allowing immediate development and testing without provisioning AWS resources.

1. **Clone and enter the workspace:**
   ```powershell
   cd "c:\MY PROJECTS\aurora-ticket-booking"
   ```

2. **Run the local validation suite:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\validate.ps1
   ```

3. **Start the Flask application:**
   ```powershell
   python app.py
   ```
   Open your browser to: [http://127.0.0.1:5000](http://127.0.0.1:5000)

4. **Execute the automated test suite:**
   ```powershell
   python -m unittest tests/test_app.py
   ```

5. **Run the load test tool:**
   ```powershell
   python load_test.py --base-url http://127.0.0.1:5000 --all
   ```

---

### Option B: Deploy to Amazon Web Services (Live Aurora Cluster)

> [!IMPORTANT]
> Ensure you have reviewed [COST_ESTIMATE.md](COST_ESTIMATE.md) before provisioning live resources.
> Minimum running cost is approximately **~$0.12 / hour**. Always run `cleanup.ps1` when finished.

1. **Inspect your AWS environment:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\inspect_aws.ps1
   ```

2. **Deploy the CloudFormation stack:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1
   ```
   *Note: This provisions Aurora Serverless v2 (1 Writer + 1 Replica) and automatically populates `.env` with the cluster endpoints and Secrets Manager credentials.*

3. **Initialize the database schema and seed data:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\verify.ps1 -InitDB
   ```

4. **Launch the application connected to Aurora:**
   ```powershell
   python app.py
   ```

5. **Execute the live performance & concurrency benchmark:**
   ```powershell
   python load_test.py --base-url http://127.0.0.1:5000 --all
   ```

6. **Tear down resources after demonstration:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\cleanup.ps1
   ```

---

## 🧪 Testing & Verification

The project includes 23 automated unit and integration tests covering:
- Event listing and detail retrieval
- Successful booking flow and reference generation
- Input validation (invalid emails, missing fields, non-positive ticket counts)
- Duplicate cancellation prevention
- Inventory restitution on cancellation
- Multi-threaded booking concurrency (overselling prevention)
- Telemetry stats recording

Run all tests anytime:
```powershell
python -m unittest tests/test_app.py -v
```

---

## 🔒 Security Best Practices

- **Strict Port Ingress:** PostgreSQL port 5432 is restricted to the caller's specific CIDR block. Ingress from `0.0.0.0/0` is strictly rejected.
- **AWS Secrets Manager:** Master database passwords are generated with 24 high-entropy characters and resolved dynamically in CloudFormation without being exposed in console outputs or templates.
- **Git Protection:** Credentials, `.env` files, and local SQLite databases are protected in `.gitignore`.
- **Encrypted Storage & Transit:** All cluster data is KMS-encrypted at rest and requires SSL/TLS (`sslmode=require`) in transit.

---

## 📚 Documentation Reference

- **[ARCHITECTURE.md](ARCHITECTURE.md):** In-depth technical specifications, sequence diagrams, and routing mechanics.
- **[COST_ESTIMATE.md](COST_ESTIMATE.md):** Itemized breakdown of AWS costs and idle charge warnings.
- **[CLEANUP.md](CLEANUP.md):** Step-by-step AWS resource destruction procedures.
