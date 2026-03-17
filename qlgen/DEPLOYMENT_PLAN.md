# qlGen AWS Deployment

## Application URL

**https://d7i11fjilnvbr.cloudfront.net**

| Endpoint | URL |
|----------|-----|
| Frontend | https://d7i11fjilnvbr.cloudfront.net |
| API (via CloudFront) | https://d7i11fjilnvbr.cloudfront.net/api/v1/health |
| API (direct ALB) | http://qlgen-alb-950991417.us-east-1.elb.amazonaws.com/api/v1/health |
| API Docs | http://qlgen-alb-950991417.us-east-1.elb.amazonaws.com/docs |

---

## Deployment Architecture

```
                              Internet
                                 |
                                 v
                 CloudFront (HTTPS) - CDN + API Proxy
                 d7i11fjilnvbr.cloudfront.net
                 Distribution ID: EDR89QBSQMRDD
                        /                \
                       /                  \
              / (static files)         /api/*
                    |                     |
                    v                     v
              S3 Bucket              ALB (HTTP:80)
          qlgen-frontend-prod     qlgen-alb-950991417.us-east-1.elb.amazonaws.com
           (React 19 build)        idle timeout: 600s
                                      |
                                      v
                              ECS Fargate Cluster
                              qlgen-cluster
                              Service: qlgen-backend
                              Task: 0.5 vCPU, 1 GB RAM
                              Image: 879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:latest
                                      |
                                      v
                              RDS PostgreSQL 16.6
                              qlgen-db.c5q8k2oiqu20.us-east-1.rds.amazonaws.com
                              db.t4g.micro, 20 GB gp3
                              (private subnet, ECS-only access)
```

### Networking

| Component | Resource ID | Details |
|-----------|------------|---------|
| VPC | `vpc-016d9d605d6072f68` | CIDR `10.0.0.0/16` |
| Public Subnet 1 | `subnet-0ebb3d7cf5e036f14` | ALB + ECS tasks |
| Public Subnet 2 | `subnet-032e0a5ca2449aa6a` | ALB + ECS tasks |
| Private Subnet 1 | `subnet-070e15615a51e11bf` | RDS |
| Private Subnet 2 | `subnet-0a690cdcc4796a7b0` | RDS |
| ALB Security Group | `sg-02682b888f309679f` | Inbound: 80, 443 from 0.0.0.0/0 |
| ECS Security Group | `sg-04500725bf843b16d` | Inbound: 8000 from ALB SG only |
| RDS Security Group | `sg-0ea02caca08c49450` | Inbound: 5432 from ECS SG only |

---

## AWS Account & Permissions

| Field | Value |
|-------|-------|
| Account ID | `879381242481` |
| IAM User | `sreejith.kalapurakkal@gadgeon.com` |
| IAM Group | `Fine-Tuners` (`AdministratorAccess`) |
| Region | `us-east-1` |
| AWS CLI Profile | `default` (credentials in `~/.aws/credentials`) |

---

## Deployed Resources

| Resource | Name / ID | Status |
|----------|-----------|--------|
| ECR Repository | `879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend` | Image pushed (`latest`) |
| ECS Cluster | `qlgen-cluster` | Active |
| ECS Service | `qlgen-backend` | Active, 1/1 tasks running |
| ECS Task Definition | `qlgen-backend:1` | 512 CPU, 1024 MB, Fargate |
| ALB | `qlgen-alb` | Active, health checks passing |
| RDS | `qlgen-db` | Available, private, not publicly accessible |
| S3 Bucket | `qlgen-frontend-prod` | 11 files deployed |
| CloudFront | `EDR89QBSQMRDD` | Enabled, cache invalidated |
| Secrets Manager | `qlgen/api-keys`, `qlgen/db-password` | Active |
| CloudWatch Logs | `/ecs/qlgen-backend` | 14-day retention |
| IAM Execution Role | `qlgen-ecs-execution` | ECR pull + Secrets Manager access |
| IAM Task Role | `qlgen-ecs-task` | Bedrock InvokeModel access |
| Bedrock Model | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Active |

---

## Deployment Verification (2026-03-03)

| Check | Result |
|-------|--------|
| ECS Service | **ACTIVE** — 1/1 tasks running, deployment COMPLETED |
| DB Migrations | Both ran: `initial_schema_with_pgvector` + `add_pipeline_logs_and_bant_sources` |
| Backend Health (ALB) | `HTTP 200` — `{"status":"healthy","service":"qlGen API"}` |
| Backend Health (CloudFront) | `HTTP 200` — API proxied correctly via `/api/*` |
| Frontend (CloudFront) | `HTTP 200` — React app served from S3 |
| ICP API (`/api/v1/icp`) | `HTTP 200` — returns `[]` (fresh database) |
| Pipeline API (`/api/v1/pipeline/history/list`) | `HTTP 200` — returns `[]` (fresh database) |

---

## What Was Done During Deployment

1. **Created `backend/entrypoint.sh`** — Docker entrypoint that runs `alembic upgrade head` then starts uvicorn
2. **Fixed AWS credentials** — Removed stale env vars for account `176608609252` from `~/.bashrc`; CLI now uses `~/.aws/credentials` for account `879381242481`
3. **Built and pushed backend Docker image** to ECR (`qlgen-backend:latest`, 721 MB)
4. **Imported existing RDS** into Terraform state (was running but not tracked)
5. **Ran `terraform apply`** — Created ECS task definition + service; secured RDS (disabled public access, restricted security group to ECS-only)
6. **Fixed TypeScript build error** in `DashboardPage.tsx` (table column type mismatch)
7. **Built frontend** (`tsc -b && vite build`) with `VITE_API_BASE_URL=""` so CloudFront proxies API calls
8. **Deployed frontend to S3** (`aws s3 sync dist/ s3://qlgen-frontend-prod/`)
9. **Invalidated CloudFront cache** (`/*`)

---

## Redeployment Commands

### Backend (after code changes)

```bash
# Build and push new image
cd backend
docker build -t qlgen-backend .
docker tag qlgen-backend:latest 879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:latest
docker push 879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:latest

# Force ECS to pull the new image
aws ecs update-service --cluster qlgen-cluster --service qlgen-backend \
  --force-new-deployment --region us-east-1
```

### Frontend (after code changes)

```bash
cd frontend
VITE_API_BASE_URL="" npm run build
aws s3 sync dist/ s3://qlgen-frontend-prod/ --delete --region us-east-1
aws cloudfront create-invalidation --distribution-id EDR89QBSQMRDD --paths "/*"
```

### Infrastructure (after Terraform changes)

```bash
cd infra
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

---

## Monitoring & Debugging

```bash
# Tail backend logs
aws logs tail /ecs/qlgen-backend --follow --region us-east-1

# Check ECS service status
aws ecs describe-services --cluster qlgen-cluster --services qlgen-backend \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount,rollout:deployments[0].rolloutState}' \
  --region us-east-1

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-east-1:879381242481:targetgroup/qlgen-backend-tg/8f224cf4ebae979b \
  --region us-east-1

# Check RDS status
aws rds describe-db-instances --db-instance-identifier qlgen-db \
  --query 'DBInstances[0].DBInstanceStatus' --region us-east-1
```

---

## Estimated Monthly Cost

| Service | Spec | ~Cost/month |
|---------|------|-------------|
| ECS Fargate | 0.5 vCPU, 1 GB, 1 task 24/7 | ~$15 |
| RDS PostgreSQL | db.t4g.micro, 20 GB gp3 | ~$15 |
| ALB | 1 load balancer, minimal traffic | ~$16 |
| CloudFront | Minimal traffic | ~$1 |
| S3 | Static assets < 2 MB | < $1 |
| Secrets Manager | 2 secrets | < $1 |
| ECR | 1 image, ~721 MB | < $1 |
| CloudWatch Logs | Minimal | < $1 |
| **Total** | | **~$48/month** |

---

## Security Notes

- `infra/terraform.tfvars` contains **plaintext API keys and database password** tracked in git. Consider adding it to `.gitignore`.
- The ALB uses **HTTP only** (port 80). For production, add an ACM certificate and HTTPS listener.
- RDS is in **private subnets** with access restricted to the ECS security group only.
- CloudFront serves the frontend over **HTTPS** and proxies `/api/*` to the ALB.
- API keys are stored in **AWS Secrets Manager** and injected into the ECS container at runtime.

---

## Rollback

| Scenario | Action |
|----------|--------|
| Bad backend deploy | Check logs: `aws logs tail /ecs/qlgen-backend --region us-east-1`. Fix and re-push image. |
| Broken frontend | Re-deploy previous build or fix and re-run `aws s3 sync`. |
| Terraform drift | Run `terraform plan` to see diff. Fix and re-apply. |
| Full teardown | `cd infra && terraform destroy -var-file=terraform.tfvars` — removes all resources including RDS data. |

---

## Terraform State

- **State file**: `infra/terraform.tfstate` (local)
- **Provider**: AWS `~> 5.0` (v5.100.0 installed)
- **Terraform version**: 1.9.8
- **Last apply**: 2026-03-03 (this deployment)
- **Managed resources**: 28 (VPC, subnets, IGW, route tables, security groups, RDS, ECS cluster/service/task, ECR, ALB, CloudFront, S3, Secrets Manager, IAM roles, CloudWatch Logs)
