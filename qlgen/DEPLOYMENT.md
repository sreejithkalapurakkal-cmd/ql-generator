# qlGen Production Deployment Guide

Reference for deploying qlGen to AWS (account `879381242481`, region `us-east-1`).

---

## Architecture Overview

```
                          Internet
                             |
                             v
             CloudFront (HTTPS) ── qlgen.gadgeon.com
             Distribution: EDR89QBSQMRDD
             d7i11fjilnvbr.cloudfront.net
                    /               \
                   /                 \
          / (static)              /api/*
              |                      |
              v                      v
         S3 Bucket              ALB (HTTP:80)
     qlgen-frontend-prod     qlgen-alb-950991417.us-east-1.elb.amazonaws.com
                                    |
                                    v
                            ECS Fargate (x2-8 tasks, autoscaling)
                            qlgen-cluster / qlgen-backend
                            4 vCPU, 8 GB RAM per task
                            Port 8000, 4 uvicorn workers
                                   / \
                                  /   \
                                 v     v
                  RDS PostgreSQL 16.6   ElastiCache Redis 7.1
        qlgen-db.c5q8k2oiqu20...        qlgen-redis.pmodat.0001...
        db.t4g.small, 20 GB gp3        cache.t4g.micro
        (private subnet)               (private subnet)
```

CloudFront routes `/api/*` to the ALB (backend) and everything else to S3 (frontend). SPA routing is handled by CloudFront custom error responses (403/404 -> `/index.html`). SSL terminates at CloudFront; the ALB only listens on HTTP:80.

---

## Prerequisites

### Tools Required

```bash
# AWS CLI (must be configured with credentials for account 879381242481)
aws sts get-caller-identity

# crane (container image push tool - required because Docker daemon has TLS issues with ECR)
# Install if not present:
curl -sL "https://github.com/google/go-containerregistry/releases/latest/download/go-containerregistry_Linux_x86_64.tar.gz" \
  -o /tmp/crane.tar.gz && tar -xzf /tmp/crane.tar.gz -C /usr/local/bin crane

# SSM Session Manager plugin (required for ECS exec)
# Install if not present:
curl -s "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" \
  -o /tmp/session-manager-plugin.deb && sudo dpkg -i /tmp/session-manager-plugin.deb

# Node.js + npm (for frontend build)
node --version  # 18+

# Docker (for building images - needs sudo)
sudo docker info
```

### Known Issues & Workarounds

**Docker TLS handshake timeout with ECR**: The Docker daemon on local machines consistently fails TLS handshakes to ECR (`net/http: TLS handshake timeout`). The root cause is unclear (not MTU, not proxy). **Workaround**: Use `crane` to push images instead of `docker push`. See [Backend Deployment](#2-build-and-push-backend-image) below.

**Docker requires sudo**: The local user is not in the `docker` group. All docker commands need `sudo`. Use `echo '<password>' | sudo -S docker ...` for non-interactive scripts.

**RDS not directly accessible**: The database is in a private subnet. You cannot connect with `psql` from your local machine. Use ECS exec to run commands inside the container. See [Running Commands in Production](#running-commands-in-production-ecs-exec).

**Python 3.11 f-string limitations**: The Docker image uses `python:3.11-slim`. Python 3.11 does **not** allow backslash characters inside f-string expression parts (e.g., `f'{"\"key\": 1" if x else ""}'`). Python 3.12+ relaxed this restriction. If you develop locally with Python 3.12+, code that passes `python -c "import ast; ast.parse(...)"` locally may still produce `SyntaxError: f-string expression part cannot include a backslash` inside the container. **Fix**: Extract the expression containing backslashes to a variable before the f-string. This was encountered during the 2026-03-23 deployment in `agent/prompt_builder.py`.

**ECS exec unreliable in non-TTY environments**: Even with the `echo "" | timeout 30` pattern, ECS exec sessions frequently connect but hang without producing output in CI/scripting contexts. **Workaround for checking migration state**: Use CloudWatch Logs instead of ECS exec. See [Checking Migration State via Logs](#checking-migration-state-via-logs) below.

**Migrations run before app startup — even on crashes**: The `entrypoint.sh` runs `alembic upgrade head` before `uvicorn`. If the container crashes on startup (e.g., a SyntaxError during import), the migrations may have already been applied to the database. This means re-deploying a fixed image will see "no migrations to run" since they were applied by the crashed container. This is normally fine, but be aware during debugging.

---

## 1. Update ECS Task Definition (Environment Variables)

When adding new environment variables (e.g., new API keys, feature flags), update the ECS task definition via AWS CLI. Do NOT rely on Terraform for quick changes.

```bash
# Get current task definition, strip AWS-managed fields, modify, re-register
aws ecs describe-task-definition --task-definition qlgen-backend --region us-east-1 \
  --query 'taskDefinition' --output json | \
  jq 'del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)' | \
  jq '.containerDefinitions[0].environment += [
    {"name": "NEW_VAR_NAME", "value": "new_value"}
  ]' > /tmp/qlgen-task-def.json

# Register new revision
aws ecs register-task-definition \
  --cli-input-json file:///tmp/qlgen-task-def.json \
  --region us-east-1 \
  --query 'taskDefinition.{family:family,revision:revision}'

# Clean up
rm /tmp/qlgen-task-def.json
```

> **Important**: Also update `infra/modules/backend-ecs/main.tf` and `infra/terraform.tfvars` to keep Terraform in sync. If a variable is sensitive, add it to `infra/modules/backend-ecs/variables.tf`, `infra/variables.tf`, and `infra/main.tf` as well.

### Current Environment Variables (Task Def, revision 7)

| Category | Variables |
|----------|-----------|
| Database | `DATABASE_URL`, `DATABASE_URL_SYNC` |
| AWS | `AWS_REGION`, `BEDROCK_MODEL_ID` |
| CORS | `CORS_ALLOWED_ORIGINS` |
| Redis | `REDIS_URL` |
| API Base URLs | `APOLLO_BASE_URL`, `EXA_BASE_URL`, `HUNTER_BASE_URL`, `LUSHA_BASE_URL`, `CLAY_BASE_URL`, `TAVILY_BASE_URL` |
| Auth | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `ALLOWED_EMAIL_DOMAIN`, `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, `COOKIE_SECURE` |
| Secrets (from Secrets Manager) | `APOLLO_API_KEY`, `EXA_API_KEY`, `HUNTER_API_KEY`, `LUSHA_API_KEY`, `TAVILY_API_KEY`, `CLAY_API_KEY` |

### Variables NOT in Task Def (use defaults)

These are defined in `backend/app/config.py` with sensible defaults. Add them to the task definition only if you need non-default values:

| Variable | Default | Notes |
|----------|---------|-------|
| `REDIS_URL` | `redis://localhost:6379/0` | Production uses ElastiCache (configured in task def); falls back to in-memory if unavailable |
| `BEDROCK_EMBEDDING_MODEL_ID` | `amazon.titan-embed-text-v2:0` | Default is correct |
| `EMBEDDING_DIMENSION` | `1024` | Default is correct |
| `GOOGLE_PLACES_API_KEY` | `""` | Tool returns error message if missing |
| `SIMFIN_API_KEY` | `""` | Tool returns error message if missing |
| `FMP_API_KEY` | `""` | Tool returns error message if missing |
| `NEWS_API_KEY` | `""` | Tool returns error message if missing |
| `FRED_API_KEY` | `""` | Tool returns error message if missing |
| `COMPANIES_HOUSE_API_KEY` | `""` | UK Companies House (free) |
| `GITHUB_TOKEN` | `""` | 5000 req/hr with token, 60 without |
| `GOOGLE_CSE_API_KEY` / `GOOGLE_CSE_ID` | `""` | Google Custom Search |
| `PRODUCTHUNT_TOKEN` | `""` | ProductHunt API |

---

## 2. Build and Push Backend Image

### Build

```bash
sudo docker build --platform linux/amd64 -t qlgen-backend /path/to/qlgen/backend
```

The image is ~772MB. The Dockerfile runs on `python:3.11-slim` and the entrypoint (`entrypoint.sh`) automatically runs `alembic upgrade head` before starting uvicorn with 4 workers.

### Push to ECR (use crane, NOT docker push)

```bash
# Save image from Docker daemon to tar
sudo docker save qlgen-backend:latest -o /tmp/qlgen-backend.tar
sudo chmod 644 /tmp/qlgen-backend.tar

# Login to ECR via crane
ECR_PASS=$(aws ecr get-login-password --region us-east-1)
crane auth login 879381242481.dkr.ecr.us-east-1.amazonaws.com -u AWS -p "$ECR_PASS"

# Push
crane push /tmp/qlgen-backend.tar 879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:latest

# Clean up
sudo rm -f /tmp/qlgen-backend.tar
```

> **Why crane?** The Docker daemon's Go HTTP client consistently fails TLS handshakes to ECR from our local machines. `crane` uses its own HTTP client and works reliably. Install: `curl -sL "https://github.com/google/go-containerregistry/releases/latest/download/go-containerregistry_Linux_x86_64.tar.gz" | tar -xz -C /usr/local/bin crane`

---

## 3. Deploy Backend (ECS)

```bash
# Force new deployment (uses latest image + specified task definition revision)
# Replace :N with the task definition revision number from step 1
aws ecs update-service \
  --cluster qlgen-cluster \
  --service qlgen-backend \
  --task-definition qlgen-backend:N \
  --force-new-deployment \
  --enable-execute-command \
  --region us-east-1
```

> **Always pass `--enable-execute-command`**. Without it, you lose the ability to exec into the container.

### Monitor Deployment

```bash
# Watch deployment status (repeat until rollout shows COMPLETED with only PRIMARY deployment)
aws ecs describe-services \
  --cluster qlgen-cluster \
  --services qlgen-backend \
  --region us-east-1 \
  --query 'services[0].deployments[*].{status:status,taskDef:taskDefinition,desired:desiredCount,running:runningCount,rollout:rolloutState}'

# Tail logs for errors
aws logs tail /ecs/qlgen-backend --region us-east-1 --since 5m --follow
```

Typical deployment takes 2-3 minutes. The sequence is:
1. New task starts (PRIMARY, running=0)
2. New task becomes healthy (running=1)
3. Old task drains (DRAINING, running=0)
4. Old deployment disappears

### Verify

```bash
curl -s https://qlgen.gadgeon.com/api/v1/health
# Expected: {"status":"healthy","service":"qlGen API"}
```

### Checking Migration State via Logs

Since ECS exec is unreliable in non-TTY environments, the most reliable way to verify which migrations ran is through CloudWatch Logs. The `entrypoint.sh` runs `alembic upgrade head` at container startup, and Alembic logs each migration it applies.

```bash
# Find the newest task's log stream
aws logs describe-log-streams --log-group-name /ecs/qlgen-backend --region us-east-1 \
  --order-by LastEventTime --descending --limit 3 \
  --query 'logStreams[*].logStreamName' --output json

# Read the startup logs (first N events show alembic output)
aws logs get-log-events --log-group-name /ecs/qlgen-backend \
  --log-stream-name "ecs/backend/<TASK_ID>" \
  --region us-east-1 --start-from-head --limit 20 \
  --query 'events[*].message' --output text
```

**What to look for:**
- `INFO  [alembic.runtime.migration] Running upgrade X -> Y, description` — one line per applied migration
- If only `Context impl PostgresqlImpl. Will assume transactional DDL.` appears with no `Running upgrade` lines, the database was already at HEAD
- The last `Running upgrade ... -> Z` line tells you the new HEAD revision

You can also search across all log streams for migration activity:
```bash
aws logs filter-log-events --log-group-name /ecs/qlgen-backend --region us-east-1 \
  --filter-pattern "Running upgrade" \
  --start-time $(date -d '1 hour ago' +%s000) --limit 20 \
  --query 'events[*].message' --output text
```

---

## 4. Deploy Frontend

Frontend environment variables are **baked in at build time** (Vite replaces `import.meta.env.VITE_*` at compile time). They are NOT read at runtime.

### Build

```bash
cd frontend

VITE_API_BASE_URL="" \
VITE_GOOGLE_CLIENT_ID="1096888171910-q1a8ihfqvdbqopbj1d3c1unnhphc6sma.apps.googleusercontent.com" \
npm run build
```

| Variable | Production Value | Purpose |
|----------|-----------------|---------|
| `VITE_API_BASE_URL` | `""` (empty string) | Requests go to same origin; CloudFront routes `/api/*` to ALB |
| `VITE_GOOGLE_CLIENT_ID` | `1096888171910-q1a8...` | Google OAuth client ID for production |

> **`VITE_API_BASE_URL` must be empty** for production. The frontend Axios client prepends this to all API calls. With an empty string, requests go to `/api/v1/...` on the same origin, and CloudFront proxies them to the ALB. Setting it to a backend URL would cause CORS issues.

### Deploy to S3 + Invalidate CloudFront

```bash
# Sync build output to S3 (--delete removes old files)
aws s3 sync dist/ s3://qlgen-frontend-prod/ --delete --region us-east-1

# Invalidate CloudFront cache (required, otherwise users see stale content)
aws cloudfront create-invalidation \
  --distribution-id EDR89QBSQMRDD \
  --paths "/*" \
  --region us-east-1
```

CloudFront invalidation takes 1-2 minutes to propagate globally.

### TypeScript Build Errors

If `npm run build` fails with TypeScript errors, fix them before deploying. The build runs `tsc -b` (strict type checking) before `vite build`. Common patterns:
- Ant Design Table's `rowClassName` callback types `record` as `unknown` — cast to `any` if needed
- Property access on interfaces that don't define the property — check `types/index.ts` for the correct field names (e.g., `PipelineRun` has `started_at` but not `created_at`)

---

## Running Commands in Production (ECS Exec)

### Prerequisites

ECS exec requires three things to be in place:

1. **SSM Session Manager plugin** installed locally (see [Prerequisites](#tools-required))
2. **`ssmmessages` IAM policy** on the ECS task role (`qlgen-ecs-task`):
   ```json
   {
     "Effect": "Allow",
     "Action": [
       "ssmmessages:CreateControlChannel",
       "ssmmessages:CreateDataChannel",
       "ssmmessages:OpenControlChannel",
       "ssmmessages:OpenDataChannel"
     ],
     "Resource": "*"
   }
   ```
   If missing, add it:
   ```bash
   aws iam put-role-policy --role-name qlgen-ecs-task --policy-name ssm-exec --policy-document '{
     "Version": "2012-10-17",
     "Statement": [{"Effect":"Allow","Action":["ssmmessages:CreateControlChannel","ssmmessages:CreateDataChannel","ssmmessages:OpenControlChannel","ssmmessages:OpenDataChannel"],"Resource":"*"}]
   }'
   ```
   > **After adding the policy, you must force a new ECS deployment.** The SSM agent in the running container cached its credentials at startup. A new task is needed to pick up the new permissions.

3. **`--enable-execute-command`** was passed during the last `update-service` call.

### Running a Command

```bash
# Get the running task ARN
TASK_ARN=$(aws ecs list-tasks --cluster qlgen-cluster --service-name qlgen-backend \
  --region us-east-1 --query 'taskArns[0]' --output text)

# Run a command (pipe stdin to avoid hanging in non-TTY environments)
echo "" | timeout 30 aws ecs execute-command \
  --cluster qlgen-cluster \
  --task $TASK_ARN \
  --container backend \
  --command "python -u -m app.scripts.seed_admin user@example.com" \
  --region us-east-1 \
  --interactive
```

> **Critical patterns for non-TTY environments (e.g., Claude Code, scripts):**
> - Pipe `echo "" |` before the command to provide stdin (prevents hanging)
> - Wrap with `timeout 30` to prevent indefinite blocking
> - Use `python -u` for unbuffered Python output (otherwise output may not appear)
> - All three are required together for reliable output capture

### Common Commands

```bash
# Seed a super admin user
echo "" | timeout 30 aws ecs execute-command ... \
  --command "python -u -m app.scripts.seed_admin email@gadgeon.com"

# Check database tables
echo "" | timeout 30 aws ecs execute-command ... \
  --command "python -u -c 'import asyncio; from app.db.session import async_session; from app.models.user import User; from sqlalchemy import select; asyncio.run((lambda: None)())'"

# Interactive shell (only works in a real terminal, not scripts)
aws ecs execute-command ... --command "/bin/sh" --interactive

# Check environment variables
echo "" | timeout 15 aws ecs execute-command ... \
  --command "env" --interactive
```

### Troubleshooting ECS Exec

| Error | Cause | Fix |
|-------|-------|-----|
| `SessionManagerPlugin is not found` | SSM plugin not installed | Install the deb package (see Prerequisites) |
| `TargetNotConnectedException` | SSM agent can't connect (missing IAM policy or stale task) | Add ssmmessages policy to task role, then force new deployment |
| Session connects but no output | Output buffered / no stdin | Use `echo "" |` pipe + `timeout` + `python -u` |
| Session connects, hangs, timeout exits | SSM session established but command output never returned | This happens intermittently even with all workarounds applied. Use CloudWatch Logs instead (see [Checking Migration State via Logs](#checking-migration-state-via-logs)). For interactive debugging, try from a real terminal with `--interactive`. |
| `InvalidParameterException` | ECS exec not enabled on service | Re-deploy with `--enable-execute-command` |

---

## Google OAuth Configuration

Production OAuth client: `1096888171910-q1a8ihfqvdbqopbj1d3c1unnhphc6sma.apps.googleusercontent.com`
Google Cloud project: `gen-lang-client-0173529210`

### Required Google Cloud Console Settings

In [Google Cloud Console](https://console.cloud.google.com/) > APIs & Services > Credentials:

| Setting | Value |
|---------|-------|
| Authorized JavaScript origins | `https://qlgen.gadgeon.com` |
| Authorized redirect URIs | `https://qlgen.gadgeon.com/auth/callback` |

> **The redirect URI is critical.** The downloaded OAuth JSON file only contains `javascript_origins`, NOT `redirect_uris`. You must manually configure the redirect URI in the Cloud Console. Without it, users get "Access blocked: This app's request is invalid" when clicking Sign in.

### Auth Flow

1. Frontend redirects to Google with `redirect_uri=https://qlgen.gadgeon.com/auth/callback`
2. Google redirects back to `/auth/callback` with an auth code
3. CloudFront serves `index.html` (SPA routing via custom error responses)
4. React Router renders `AuthCallbackPage`, which POSTs the code to `/api/v1/auth/google/callback`
5. Backend exchanges code with Google, validates email domain (`@gadgeon.com`), checks user allowlist, issues JWT

### Auth-Related Environment Variables

| Variable | Production Value | Notes |
|----------|-----------------|-------|
| `GOOGLE_CLIENT_ID` | `1096888171910-q1a8...` | Also set as `VITE_GOOGLE_CLIENT_ID` at frontend build time |
| `GOOGLE_CLIENT_SECRET` | (in terraform.tfvars) | From prod OAuth JSON |
| `GOOGLE_REDIRECT_URI` | `https://qlgen.gadgeon.com/auth/callback` | Must match Cloud Console |
| `ALLOWED_EMAIL_DOMAIN` | `gadgeon.com` | Only `@gadgeon.com` emails allowed |
| `JWT_SECRET_KEY` | (in terraform.tfvars) | 64-char hex, generate with `openssl rand -hex 32` |
| `COOKIE_SECURE` | `true` | Must be `true` for HTTPS (production). `false` for local dev (HTTP) |

---

## Full Deployment Checklist

Use this when deploying code changes that touch both backend and frontend.

```
[ ] 1. Update ECS task definition if new env vars needed
      aws ecs describe-task-definition ... | jq ... > /tmp/task-def.json
      aws ecs register-task-definition --cli-input-json file:///tmp/task-def.json
      Note the new revision number.

[ ] 2. Build backend Docker image
      sudo docker build --platform linux/amd64 -t qlgen-backend backend/

[ ] 3. Push to ECR via crane
      sudo docker save qlgen-backend:latest -o /tmp/qlgen-backend.tar
      sudo chmod 644 /tmp/qlgen-backend.tar
      crane auth login 879381242481.dkr.ecr.us-east-1.amazonaws.com -u AWS -p "$(aws ecr get-login-password --region us-east-1)"
      crane push /tmp/qlgen-backend.tar 879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:latest

[ ] 4. Deploy backend
      aws ecs update-service --cluster qlgen-cluster --service qlgen-backend \
        --task-definition qlgen-backend:N --force-new-deployment \
        --enable-execute-command --region us-east-1

[ ] 5. Wait for deployment to stabilize
      Watch: aws ecs describe-services ... --query 'services[0].deployments'
      Verify: curl https://qlgen.gadgeon.com/api/v1/health

[ ] 6. Run any one-time commands (migrations run automatically via entrypoint.sh)
      echo "" | timeout 30 aws ecs execute-command ...

[ ] 7. Build frontend
      cd frontend
      VITE_API_BASE_URL="" VITE_GOOGLE_CLIENT_ID="1096888171910-q1a8ihfqvdbqopbj1d3c1unnhphc6sma.apps.googleusercontent.com" npm run build

[ ] 8. Deploy frontend
      aws s3 sync dist/ s3://qlgen-frontend-prod/ --delete --region us-east-1
      aws cloudfront create-invalidation --distribution-id EDR89QBSQMRDD --paths "/*"

[ ] 9. Verify
      curl https://qlgen.gadgeon.com/api/v1/health          # 200
      curl https://qlgen.gadgeon.com/api/v1/icp              # 401 (auth required)
      Visit https://qlgen.gadgeon.com                        # Frontend loads
      Check logs: aws logs tail /ecs/qlgen-backend --region us-east-1 --since 5m
```

---

## Backend-Only Deployment (no env var changes)

When deploying only backend code changes with no new environment variables:

```bash
# Build
sudo docker build --platform linux/amd64 -t qlgen-backend backend/

# Push via crane
sudo docker save qlgen-backend:latest -o /tmp/qlgen-backend.tar
sudo chmod 644 /tmp/qlgen-backend.tar
crane auth login 879381242481.dkr.ecr.us-east-1.amazonaws.com -u AWS -p "$(aws ecr get-login-password --region us-east-1)"
crane push /tmp/qlgen-backend.tar 879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:latest
sudo rm -f /tmp/qlgen-backend.tar

# Deploy (no --task-definition flag = reuse current revision, just pull new image)
aws ecs update-service --cluster qlgen-cluster --service qlgen-backend \
  --force-new-deployment --enable-execute-command --region us-east-1

# Verify
aws ecs describe-services --cluster qlgen-cluster --services qlgen-backend \
  --region us-east-1 --query 'services[0].deployments[*].{status:status,running:runningCount,rollout:rolloutState}'
curl -s https://qlgen.gadgeon.com/api/v1/health
```

---

## Frontend-Only Deployment

When deploying only frontend changes:

```bash
cd frontend

# Build with production env vars
VITE_API_BASE_URL="" \
VITE_GOOGLE_CLIENT_ID="1096888171910-q1a8ihfqvdbqopbj1d3c1unnhphc6sma.apps.googleusercontent.com" \
npm run build

# Deploy
aws s3 sync dist/ s3://qlgen-frontend-prod/ --delete --region us-east-1
aws cloudfront create-invalidation --distribution-id EDR89QBSQMRDD --paths "/*" --region us-east-1
```

---

## Rollback

### Backend Rollback

```bash
# List recent task definition revisions
aws ecs list-task-definitions --family-prefix qlgen-backend --region us-east-1 --sort DESC --max-items 5

# Roll back to a previous revision
aws ecs update-service --cluster qlgen-cluster --service qlgen-backend \
  --task-definition qlgen-backend:PREVIOUS_REVISION \
  --force-new-deployment --enable-execute-command --region us-east-1
```

> **Warning**: If the new code ran `alembic upgrade head` and added new DB columns/tables, rolling back the container won't undo the migration. Database rollback requires running `alembic downgrade -1` inside the container before switching task definitions.

### Frontend Rollback

There's no built-in rollback for S3. Options:
- Rebuild from the previous git commit and re-deploy
- Restore from S3 versioning if enabled on the bucket

---

## Current Deployment State

Last updated: 2026-03-25

### ECS Fargate — Compute

| Setting | Value |
|---------|-------|
| Cluster | `qlgen-cluster` |
| Service | `qlgen-backend` |
| Task Definition | `qlgen-backend:7` |
| Launch Type | Fargate |
| CPU | 4096 (4 vCPU) |
| Memory | 8192 MB (8 GB) |
| Desired / Running Tasks | 2 / 2 |
| Autoscaling | Min 2 / Max 8 tasks, CPU target 70% |
| Network Mode | awsvpc |
| Subnets | `subnet-0ebb3d7cf5e036f14`, `subnet-032e0a5ca2449aa6a` (public) |
| Assign Public IP | Enabled |
| ECS Exec | Enabled |
| Container Name | `backend` |
| Container Port | 8000 |
| Uvicorn Workers | 4 (configured in `entrypoint.sh`) |
| Docker Base Image | `python:3.11-slim` |
| Execution Role | `qlgen-ecs-execution` (ECR pull + Secrets Manager) |
| Task Role | `qlgen-ecs-task` (Bedrock InvokeModel + SSM messages) |

### ECR — Container Registry

| Setting | Value |
|---------|-------|
| Repository URI | `879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend` |
| Image Tag | `latest` |
| Image Size | ~297 MB (compressed) |
| Scan on Push | Enabled |

### RDS — Database

| Setting | Value |
|---------|-------|
| Engine | PostgreSQL 16.6 |
| Instance Class | `db.t4g.small` |
| Storage | 20 GB gp3 (auto-scales to 50 GB) |
| Endpoint | `qlgen-db.c5q8k2oiqu20.us-east-1.rds.amazonaws.com:5432` |
| Database Name | `qlgen` |
| Username | `qlgen` |
| Multi-AZ | No |
| Public Access | No (private subnet only) |
| Backup Retention | 7 days |
| Alembic Revision | `k1l2m3n4o5p6` (HEAD, 16 migrations) |

### ALB — Load Balancer

| Setting | Value |
|---------|-------|
| Name | `qlgen-alb` |
| DNS | `qlgen-alb-950991417.us-east-1.elb.amazonaws.com` |
| Scheme | Internet-facing |
| Listener | HTTP:80 only (no HTTPS — SSL terminates at CloudFront) |
| Target Group | `qlgen-backend-tg`, port 8000, HTTP |
| Health Check | `GET /api/v1/health`, interval 30s, timeout 5s, healthy 2, unhealthy 3 |
| Idle Timeout | 600s (for SSE streaming support) |
| Deregistration Delay | 300s |
| Target Group ARN | `arn:aws:elasticloadbalancing:us-east-1:879381242481:targetgroup/qlgen-backend-tg/8f224cf4ebae979b` |

### CloudFront — CDN

| Setting | Value |
|---------|-------|
| Distribution ID | `EDR89QBSQMRDD` |
| Domain | `d7i11fjilnvbr.cloudfront.net` |
| Custom Domain | `qlgen.gadgeon.com` |
| ACM Certificate | `arn:aws:acm:us-east-1:879381242481:certificate/602948e0-3a63-43e8-8684-d0625f4930e0` |
| Status | Deployed |
| HTTP Version | HTTP/2 |
| Price Class | PriceClass_100 (NA + Europe) |
| Default Root Object | `index.html` |
| Default Origin | `s3-frontend` → `qlgen-frontend-prod.s3.us-east-1.amazonaws.com` |
| API Behavior | `/api/*` → `alb-backend`, all HTTP methods, no caching, forwards all headers/cookies |
| Error Pages | 403 → `/index.html` (200), 404 → `/index.html` (200) — SPA routing |

### S3 — Frontend Hosting

| Setting | Value |
|---------|-------|
| Bucket | `qlgen-frontend-prod` |
| Access | CloudFront OAC only (block public access enabled) |
| Build Env | `VITE_API_BASE_URL=""`, `VITE_GOOGLE_CLIENT_ID="1096888171910-..."` |

### Security Groups

| Security Group | ID | Inbound Rules |
|---------------|----|---------------|
| `qlgen-alb-sg` | `sg-02682b888f309679f` | TCP 80 from `0.0.0.0/0`, TCP 443 from `0.0.0.0/0` |
| `qlgen-ecs-sg` | `sg-04500725bf843b16d` | TCP 8000 from `qlgen-alb-sg` only |
| `qlgen-rds-sg` | `sg-0ea02caca08c49450` | TCP 5432 from `qlgen-ecs-sg` only |
| `qlgen-redis-sg` | `sg-01f615465be219bbe` | TCP 6379 from `qlgen-ecs-sg` only |

### IAM Roles

| Role | Permissions |
|------|-------------|
| `qlgen-ecs-execution` | `AmazonECSTaskExecutionRolePolicy`, Secrets Manager read (`qlgen/api-keys`) |
| `qlgen-ecs-task` | Bedrock `InvokeModel` (`anthropic.claude-sonnet-4*`), SSM messages (for ECS exec) |

### Secrets Manager

Secret `qlgen/api-keys` (`arn:aws:secretsmanager:us-east-1:879381242481:secret:qlgen/api-keys-GM1XdJ`) contains:
`APOLLO_API_KEY`, `EXA_API_KEY`, `HUNTER_API_KEY`, `LUSHA_API_KEY`, `TAVILY_API_KEY`, `CLAY_API_KEY`

### CloudWatch Logs

| Setting | Value |
|---------|-------|
| Log Group | `/ecs/qlgen-backend` |
| Retention | 14 days |
| Log Driver | `awslogs` |
| Stream Prefix | `ecs/backend/<task-id>` |

### ElastiCache — Redis

| Setting | Value |
|---------|-------|
| Cluster ID | `qlgen-redis` |
| Endpoint | `qlgen-redis.pmodat.0001.use1.cache.amazonaws.com:6379` |
| Node Type | `cache.t4g.micro` |
| Engine | Redis 7.1.0 |
| Nodes | 1 |
| Subnet Group | `qlgen-redis-subnet-group` (private subnets, same as RDS) |
| Security Group | `qlgen-redis-sg` (`sg-01f615465be219bbe`) — TCP 6379 from ECS SG only |
| Purpose | SSE event store for cross-task pipeline event sharing |

### Bedrock Model

| Setting | Value |
|---------|-------|
| Model ID | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (Claude Sonnet 4.5) |
| Embedding Model | `amazon.titan-embed-text-v2:0` (default, not in task def) |
| Region | `us-east-1` |
| RPM Quota | 10,000 requests/min (cross-region inference profile) |
| TPM Quota | 5,000,000 tokens/min |

### Not Provisioned

- **Research API keys** (SIMFIN, FMP, NEWS, FRED, GOOGLE_PLACES, etc.) — not configured; tools gracefully degrade
- **HTTPS on ALB** — SSL terminates at CloudFront; ALB only listens on HTTP:80

### Capacity & Scalability

**Concurrent Users (browsing/UI):** ~50-100 active users comfortably, ~200+ passive. Static assets served via CloudFront (effectively unlimited). Backend API is the bottleneck — 4 uvicorn workers per task, 2-8 tasks = 8-32 async worker processes.

**Concurrent Pipeline Runs:** Up to **10 parallel pipelines** (enforced by application-level semaphore). Attempting to start an 11th pipeline returns HTTP 429. The semaphore gates all pipeline entry points: `execute_pipeline`, `resume_after_firmographic`, `resume_after_first_signal`, and `resume_after_signals`.

**Concurrent Co-pilot Chat Sessions:** ~20-30 without pipelines running, ~10-15 alongside 10 active pipelines. Each chat session uses 1-5 Bedrock calls and 1 SSE connection.

**Key resource limits at 10 concurrent pipelines:**

| Resource | Demand (10 pipelines) | Available | Headroom |
|----------|----------------------|-----------|----------|
| Bedrock RPM | ~500 peak burst | 10,000 | 95% free |
| Bedrock TPM | ~1.5M peak | 5,000,000 | 70% free |
| DB Connections | ~60-80 active | ~215 (db.t4g.small max) | OK |
| Memory | ~6 GB peak | 8 GB per task x 2-8 tasks | OK |
| CPU Threads | ~50 peak (Stage 4) | ~24/task x 2-8 tasks | OK |
| Redis | ~10K events | cache.t4g.micro | OK |

**Per-pipeline resource profile (100 companies):**
- ~1,100-1,600 Bedrock API calls over 60-95 minutes
- Peak 5 concurrent agent threads (Stage 4: Contact Discovery)
- ~8-12 DB connections at peak
- ~300-500 MB memory at peak

**Application-level protections:**
- Pipeline concurrency semaphore (`MAX_CONCURRENT_PIPELINES=10` in `pipeline_service.py`)
- Bedrock throttle retry with exponential backoff (3 retries, 2s/4s/8s delays) on all agent calls
- DB connection pool tuned: `pool_size=5, max_overflow=10, pool_recycle=1800, pool_pre_ping=True`
- DuckDuckGo global rate limiter: 3 tokens max, 60s cooldown on rate limit detection
- External API rate limit detection (429/402/403) with agent-level tool switching

**Autoscaling:** ECS scales from 2 to 8 tasks based on CPU utilization (target 70%, scale-out cooldown 60s, scale-in cooldown 300s). At current low utilization (~0.2% CPU), autoscaling will only trigger under sustained multi-pipeline load.

### Database Tables (16 migrations applied)

```
alembic_version          companies                 company_knowledge_base
company_stage_results    contacts                  chat_messages
chat_sessions            discovery_queries         icp_configs
pipeline_logs            pipeline_runs             tool_effectiveness
tool_registry            users                     audit_logs
```

`bant_scores` was dropped by migration `a1b2c3d4e5f6` (replaced by `company_stage_results`).

### Migration Chain

```
ad6870bc307f  Initial schema with pgvector
526a00746466  Add pipeline_logs and BANT sources
c3a1f8b9d2e4  Add co-pilot chat tables and embeddings
d4b2e9f1a3c7  Add promoted column to companies
e5f3a7b2c8d1  Add tool_registry table
f6a4b8c3d9e2  Add disqualification_stage column
a1b2c3d4e5f6  Five Stage Pipeline v2 (drops bant_scores, creates company_stage_results)
b7c5d9e2f4a8  Add rate_limit_info to tool_registry
c0b6b9bba9b6  Add users table + user_id FKs
704565025b67  Add asset_value to companies
g1a2b3c4d5e6  Add audit_logs table
g7h8i9j0k1l2  Add discovery_queries + tool_effectiveness tables
h8i9j0k1l2m3  Add recency/hotness columns to companies
i9j0k1l2m3n4  Add company_knowledge_base table
j0k1l2m3n4o5  Add carried_forward column to companies
k1l2m3n4o5p6  Add tool priority and auto-disable (HEAD)
```

---

## Deployment History

### 2026-03-25 — Infrastructure scale-up for 10 concurrent pipelines

**Goal**: Scale infrastructure and add application-level controls to support up to 10 concurrent pipeline runs.

**Infrastructure changes (AWS CLI, no Terraform):**

| Change | Before | After |
|--------|--------|-------|
| Bedrock model | `us.anthropic.claude-sonnet-4-20250514-v1:0` (200 RPM) | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (10,000 RPM) |
| ECS task CPU | 2048 (2 vCPU) | 4096 (4 vCPU) |
| ECS task memory | 4096 MB (4 GB) | 8192 MB (8 GB) |
| ECS autoscaling max | 4 tasks | 8 tasks |
| Redis | Not deployed (in-memory fallback) | ElastiCache `cache.t4g.micro`, Redis 7.1 |
| Task definition | Revision 4 | Revision 7 (5=model, 6=Redis, 7=CPU/memory) |

**Code changes:**
- `backend/entrypoint.sh` — uvicorn workers: 2 → 4
- `backend/app/db/session.py` — DB pool tuned: `pool_size=5, max_overflow=10`, added `pool_recycle=1800` and `pool_pre_ping=True` to prevent stale connections
- `backend/app/services/pipeline_service.py`:
  - Added `MAX_CONCURRENT_PIPELINES = 10` with `asyncio.Semaphore` gating all 4 pipeline entry points (`execute_pipeline`, `resume_after_firmographic`, `resume_after_first_signal`, `resume_after_signals`)
  - Added `run_agent_with_retry()` — retries Bedrock `ThrottlingException` with exponential backoff (3 retries, 2s/4s/8s delays); replaced all 9 `asyncio.to_thread(agent, prompt)` calls
- `backend/app/api/pipeline.py` — pre-check returns HTTP 429 immediately when all pipeline slots are full

**Task definition revisions:**
- Rev 5: Changed `BEDROCK_MODEL_ID` to Claude Sonnet 4.5
- Rev 6: Added `REDIS_URL=redis://qlgen-redis.pmodat.0001.use1.cache.amazonaws.com:6379/0`
- Rev 7: CPU 2048→4096, Memory 4096→8192

**Deployment**: Backend-only redeploy via crane. No migrations. No frontend changes.

### 2026-03-24 — Backend hotfix (NoneType .lower() in firmographic filter)

**Issue**: Pipeline runs failing with `'NoneType' object has no attribute 'lower'` in `quick_firmographic_filter()`.

**Root cause**: ICP config JSON contained `None` values in `countries` list or `vertical`/`sub_vertical` fields. The code called `.lower()` without guarding against `None`. Python's `dict.get("key", "")` returns `None` (not `""`) when the key exists with an explicit `None` value.

**Fix** (3 lines in `pipeline_service.py`):
- Line 764: Added `if c` filter to skip `None` entries in countries set comprehension
- Lines 768-769: Changed `item.get("vertical", "")` to `(item.get("vertical") or "")` to handle explicit `None` values

**Deployment**: Backend-only redeploy. No task definition or migration changes.

### 2026-03-23 — Full stack redeployment

**Changes deployed**: v2 pipeline code updates, Deal Hotness UI removal, Company Detail page tab reorder, import cleanup in pipeline_service.py, ToolsPage TypeScript fix, prompt_builder.py Python 3.11 syntax fix.

**Migrations applied** (6 new, from `704565025b67` to `k1l2m3n4o5p6`):
- `g1a2b3c4d5e6` — audit_logs table
- `g7h8i9j0k1l2` — discovery_queries + tool_effectiveness tables
- `h8i9j0k1l2m3` — recency/hotness columns on companies
- `i9j0k1l2m3n4` — company_knowledge_base table
- `j0k1l2m3n4o5` — carried_forward column on companies
- `k1l2m3n4o5p6` — tool priority/auto-disable on tool_registry

**Issues encountered and fixed during deployment**:
1. `SyntaxError` in `agent/prompt_builder.py:758` — f-string with backslash escapes (`\"`) incompatible with Python 3.11. Fixed by extracting expressions to variables before the f-string.
2. TypeScript error in `pages/ToolsPage.tsx:827` — `created_at` property referenced on `PipelineRun` interface which doesn't have it. Fixed by using `started_at` with a fallback string.
3. First deployment attempt crashed on startup (workers failed to import `prompt_builder.py`). Migrations applied successfully before the crash. Second deployment with the fix started cleanly.

**Task definition**: No changes (stayed at revision 4). No new env vars needed.

### 2026-03-16 — Backend deployment (auth + tools)

Previous deployment that brought the system to revision `704565025b67`. Added users table, auth, asset_value column.

### 2026-03-03 — Initial production deployment

First deployment via Terraform. Created all AWS infrastructure. Applied initial 2 migrations (`ad6870bc307f`, `526a00746466`).
