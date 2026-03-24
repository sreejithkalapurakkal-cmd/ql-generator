# qlGen Production Deployment Guide

Reference for deploying qlGen to AWS (account `879381242481`, region `us-east-1`).

---

## Architecture Overview

| Component | Service | Details |
|-----------|---------|---------|
| Backend | ECS Fargate | Cluster: `qlgen-cluster`, Service: `qlgen-backend`, Port 8000, 2 tasks |
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

### Current Environment Variables (Task Def, revision 4)

| Category | Variables |
|----------|-----------|
| Database | `DATABASE_URL`, `DATABASE_URL_SYNC` |
| AWS | `AWS_REGION`, `BEDROCK_MODEL_ID` |
| CORS | `CORS_ALLOWED_ORIGINS` |
| API Base URLs | `APOLLO_BASE_URL`, `EXA_BASE_URL`, `HUNTER_BASE_URL`, `LUSHA_BASE_URL`, `CLAY_BASE_URL`, `TAVILY_BASE_URL` |
| Auth | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `ALLOWED_EMAIL_DOMAIN`, `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, `COOKIE_SECURE` |
| Secrets (from Secrets Manager) | `APOLLO_API_KEY`, `EXA_API_KEY`, `HUNTER_API_KEY`, `LUSHA_API_KEY`, `TAVILY_API_KEY`, `CLAY_API_KEY` |

### Variables NOT in Task Def (use defaults)

These are defined in `backend/app/config.py` with sensible defaults. Add them to the task definition only if you need non-default values:

| Variable | Default | Notes |
|----------|---------|-------|
| `REDIS_URL` | `redis://localhost:6379/0` | Falls back to in-memory event store if Redis unavailable |
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

The image is ~772MB. The Dockerfile runs on `python:3.11-slim` and the entrypoint (`entrypoint.sh`) automatically runs `alembic upgrade head` before starting uvicorn with 2 workers.

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

Last updated: 2026-03-23

| Item | Value |
|------|-------|
| ECS Task Definition | `qlgen-backend:4` |
| ECS Desired Count | 2 |
| Alembic Revision (HEAD) | `k1l2m3n4o5p6` (add tool priority and auto-disable) |
| Docker Base Image | `python:3.11-slim` |
| Bedrock Model | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Git Branch Deployed | `development` |

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
