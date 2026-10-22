# Amazon Aurora PostgreSQL — Cost Estimate & Financial Plan

**Project:** Scalable Online Ticket Booking Database Using Amazon Aurora  
**AWS Region:** `ap-south-1` (Mumbai)  
**Date:** October 2026  
**Account:** `953652928989` (`arn:aws:iam::953652928989:user/24BCE1720_SAICHARAN`)

---

## 1. Executive Summary

This project implements a multi-node Amazon Aurora PostgreSQL architecture comprising **one Primary Writer** and **one Aurora Read Replica** to demonstrate read-scaling and write routing. To minimize costs while meeting academic and architectural requirements, we utilize **Aurora Serverless v2** configured at the absolute minimum capacity of **0.5 ACU** (Aurora Capacity Units) up to **2.0 ACU** during peak load.

Running the Flask application **locally** and connecting over TLS eliminates EC2/ECS hosting costs, reducing ongoing infrastructure spending to purely database compute, storage, and secret storage.

---

## 2. Itemized Cost Breakdown (`ap-south-1` Mumbai)

| Component | Specification / Quantity | Rate (ap-south-1) | Hourly Cost | Monthly Cost (if left running) |
|---|---|---|---|---|
| **Aurora Serverless v2 (Writer)** | 0.5 ACU (baseline idle) | $0.12 / ACU-hr | **$0.060 / hr** | $43.80 / mo |
| **Aurora Serverless v2 (Reader Replica)** | 0.5 ACU (baseline idle) | $0.12 / ACU-hr | **$0.060 / hr** | $43.80 / mo |
| **Aurora Standard Storage** | 10 GB provisioned / used | $0.10 / GB-month | $0.0014 / hr | $1.00 / mo |
| **Database I/O Operations** | ~100,000 I/O requests per test session | $0.20 / 1M requests | Negligible (~$0.02 per run) | ~$0.20 / mo |
| **AWS Secrets Manager** | 1 Secret (Master credentials) | $0.40 / secret / mo | $0.0006 / hr | $0.40 / mo |
| **Data Transfer (Intra-Region / AZ)** | Cross-AZ Replication (~1 GB) | $0.01 / GB | Negligible | ~$0.05 / mo |
| **Application Hosting** | Local Machine (Flask) | $0.00 | **$0.00** | **$0.00** |
| **CloudFormation & VPC** | Core orchestration | Free | $0.00 | $0.00 |

---

## 3. Cost Scenarios for Academic Demonstration

| Demonstration Scenario | Duration | Estimated Total Cost (USD) | Estimated Total Cost (INR) |
|---|---|---|---|
| **Typical Academic Presentation** | **2 Hours** | **~$0.25** | **~₹21** |
| **Extended Workshop / Testing** | **6 Hours** | **~$0.75** | **~₹63** |
| **Full Day Development Session** | **24 Hours** | **~$2.95** | **~₹245** |
| **Forgotten / Left Running for 1 Month** | **730 Hours** | **~$89.00** | **~₹7,400** |

> [!CAUTION]
> **Services That Incur Charges While Idle:**
> 1. **Aurora Serverless v2 Compute:** Both the writer and reader instances maintain minimum capacity (0.5 ACU each = $0.12/hr total) even when no queries are being executed.
> 2. **Aurora Storage:** Storage is billed for high-water mark volume until cluster deletion.
> 3. **AWS Secrets Manager:** Secrets are billed at $0.40/month prorated daily until deleted.
>
> **Action Required:** Always run `.\scripts\cleanup.ps1` immediately after completing your demonstration or lab testing.

---

## 4. Alternative Architectural Comparison

| Architecture | Nodes | Supported in ap-south-1 | Hourly Cost | Feasibility / Recommendation |
|---|---|---|---|---|
| **Aurora Serverless v2 (0.5–2 ACU)** *(Chosen)* | 1 Writer + 1 Replica | **Yes (Engine 16.8)** | **~$0.12 / hr** | **Recommended.** Lowest cost for genuine Aurora cluster with live read replica. |
| **Aurora Provisioned `db.t4g.medium`** | 1 Writer + 1 Replica | Restricted / Not Orderable in 16.8 | ~$0.096 / hr | Not available in current CLI catalog for 16.8 in ap-south-1. |
| **Aurora Provisioned `db.r6g.large`** | 1 Writer + 1 Replica | Yes | ~$0.52 / hr ($380/mo) | Too expensive for academic project ($0.26/hr per node). |
| **RDS PostgreSQL (Non-Aurora)** | 1 Primary + 1 Read Replica | Yes | ~$0.08 / hr | **Rejected.** Does not fulfill prompt requirement for Amazon Aurora and Aurora Reader endpoint. |

---

## 5. Cost-Aware Deployment Safety Checklist

1. **Explicit Confirmation:** `scripts/deploy.ps1` requires typing confirmation before initiating any CloudFormation creation.
2. **Resource Tagging:** All provisioned resources carry `Project=AuroraTicketBooking` tags for granular AWS Cost Explorer filtering.
3. **Automated Teardown:** `scripts/cleanup.ps1` automates full stack destruction in a single command (`aws cloudformation delete-stack`).
4. **Local Fallback:** For development and regression testing, set `USE_LOCAL_DB=true` in `.env` or environment to run completely free of AWS charges.
