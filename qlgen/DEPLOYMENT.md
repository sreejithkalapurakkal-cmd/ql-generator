# qlGen Production Deployment Guide

Reference for deploying qlGen to AWS (account `879381242481`, region `us-east-1`).

---

## Architecture Overview

| Component | Service | Details |
|-----------|---------|---------|
| Backend | ECS Fargate | Cluster: `qlgen-cluster`, Service: `qlgen-backend`, Port 8000 |
| Frontend | S3 + CloudFront | Bucket: `qlgen-frontend-prod`, Distribution: `EDR89QBSQMRDD` |
| Database | RDS PostgreSQL 16 | Host: `qlgen-db.c5q8k2oiqu20.us-east-1.rds.amazonaws.com` (private subnet, not directly accessible) |
| Container Registry | ECR | `879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend` |
| DNS | CloudFront alias | `https://qlgen.gadgeon.com` |

CloudFront routes `/api/*` to the ALB (backend) and everything else to S3 (frontend). SPA routing is handled by CloudFront custom error responses (403/404 -> `/index.html`).

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

### Current Environment Variables (Task Def)

| Category | Variables |
|----------|-----------|
| Database | `DATABASE_URL`, `DATABASE_URL_SYNC` |
| AWS | `AWS_REGION`, `BEDROCK_MODEL_ID` |
| CORS | `CORS_ALLOWED_ORIGINS` |
| API Base URLs | `APOLLO_BASE_URL`, `EXA_BASE_URL`, `HUNTER_BASE_URL`, `LUSHA_BASE_URL`, `CLAY_BASE_URL`, `TAVILY_BASE_URL` |
| Auth | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `ALLOWED_EMAIL_DOMAIN`, `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, `COOKIE_SECURE` |
| Secrets (from Secrets Manager) | `APOLLO_API_KEY`, `EXA_API_KEY`, `HUNTER_API_KEY`, `LUSHA_API_KEY`, `TAVILY_API_KEY`, `CLAY_API_KEY` |

---

## 2. Build and Push Backend Image

### Build

```bash
sudo docker build --platform linux/amd64 -t qlgen-backend /path/to/qlgen/backend
```

The image is ~757MB. The Dockerfile runs on `python:3.11-slim` and the entrypoint (`entrypoint.sh`) automatically runs `alembic upgrade head` before starting uvicorn.

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

If `npm run build` fails with TypeScript errors, fix them before deploying. The build runs `tsc -b` (strict type checking) before `vite build`. Common pattern: Ant Design Table's `rowClassName` callback types `record` as `unknown` - cast to `any` if needed.

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
