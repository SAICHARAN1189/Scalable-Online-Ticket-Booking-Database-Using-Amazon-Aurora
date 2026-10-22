# AWS Infrastructure Cleanup Guide

**Project:** Scalable Online Ticket Booking Database Using Amazon Aurora  
**Stack Name:** `aurora-ticket-booking-stack`  
**Region:** `ap-south-1` (Mumbai)  

---

## 1. Quick Teardown (Recommended)

Run the included automated cleanup script from your PowerShell prompt:

```powershell
.\scripts\cleanup.ps1
```

The script will:
1. Prompt for confirmation (`type 'DELETE'`).
2. Delete the CloudFormation stack `aurora-ticket-booking-stack`.
3. Wait for full deletion of the Aurora cluster, writer instance, and reader replica.
4. Clean up the AWS Secrets Manager secret.
5. Offer to remove the local `.env` and SQLite test databases.

---

## 2. CLI Teardown (Alternative)

If you prefer executing direct AWS CLI commands:

```bash
# 1. Delete CloudFormation stack
aws cloudformation delete-stack \
    --stack-name aurora-ticket-booking-stack \
    --region ap-south-1

# 2. Wait until deletion completes (takes 5-10 minutes)
aws cloudformation wait stack-delete-complete \
    --stack-name aurora-ticket-booking-stack \
    --region ap-south-1

# 3. Verify zero clusters remain
aws rds describe-db-clusters \
    --region ap-south-1 \
    --query "DBClusters[].DBClusterIdentifier" \
    --output table
```

---

## 3. Web Console Teardown (GUI Alternative)

1. Log in to the [AWS Management Console](https://console.aws.amazon.com/).
2. In the top-right navigation bar, set your Region to **Asia Pacific (Mumbai) ap-south-1**.
3. Navigate to **CloudFormation** > **Stacks**.
4. Select `aurora-ticket-booking-stack` and click **Delete**.
5. Confirm deletion. CloudFormation will delete:
   - Aurora Read Replica Instance (`aurora-ticket-booking-stack-replica-1`)
   - Aurora Writer Instance (`aurora-ticket-booking-stack-writer`)
   - Aurora DB Cluster (`aurora-ticket-booking-stack-cluster`)
   - RDS DB Subnet Group
   - EC2 Security Group
   - AWS Secrets Manager Secret

---

## 4. Verification Checklist (Ensure Zero Ongoing Billing)

After deletion, run these read-only checks to guarantee that no billed resources remain:

| Resource Type | AWS CLI Verification Command | Expected Clean Output |
|---|---|---|
| **Aurora DB Clusters** | `aws rds describe-db-clusters --region ap-south-1 --query "DBClusters[]" --output json` | `[]` |
| **RDS DB Instances** | `aws rds describe-db-instances --region ap-south-1 --query "DBInstances[]" --output json` | `[]` |
| **Secrets Manager** | `aws secretsmanager list-secrets --region ap-south-1 --query "SecretList[?contains(Name, 'aurora')].Name" --output json` | `[]` |
| **Manual Snapshots** | `aws rds describe-db-cluster-snapshots --region ap-south-1 --query "DBClusterSnapshots[]" --output json` | `[]` |

---

## 5. Local State Cleanup

To return your local development workspace to a clean offline state:

```powershell
# Remove generated live credentials
Remove-Item -Force .env -ErrorAction SilentlyContinue

# Reset local mock database
Remove-Item -Force local_ticket_booking.db -ErrorAction SilentlyContinue

# Run validation to verify offline functionality
.\scripts\validate.ps1
```
