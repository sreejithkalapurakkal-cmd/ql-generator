---
name: deploy
description: Deploy qlGen application to AWS (account 879381242481). Handles backend (ECS Fargate), frontend (S3 + CloudFront), and database migrations. Use when ready to deploy code changes to production.
disable-model-invocation: true
allowed-tools:
  - Bash(aws *)
  - Bash(docker *)
  - Bash(crane *)
  - Bash(curl *)
  - Bash(npm *)
  - Bash(rm *)
  - Bash(chmod *)
  - Bash(du *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Read
  - Edit
  - Glob
  - Grep
arguments: [target]
---

# qlGen Production Deployment

Deploy qlGen to AWS account `879381242481` (region `us-east-1`).

**Target**: `$ARGUMENTS` (default: `full` if empty. Options: `full`, `backend`, `frontend`)

Refer to `DEPLOYMENT.md` at the project root for detailed reference. Do NOT use Terraform.

---

## Infrastructure Reference

| Component | Resource | Details |
|-----------|----------|---------|
| Backend | ECS Fargate | Cluster: `qlgen-cluster`, Service: `qlgen-backend`, Port 8000 |
| Frontend | S3 + CloudFront | Bucket: `qlgen-frontend-prod`, Distribution: `EDR89QBSQMRDD` |
| Database | RDS PostgreSQL 16 | Private subnet, not directly accessible. Migrations run via `entrypoint.sh` |
| Container Registry | ECR | `879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend` |
| DNS | CloudFront | `https://qlgen.gadgeon.com` |

---

## Execution Steps

Execute these steps in order. Use task tracking to show progress. Report results clearly after each step.

### Step 1: Pre-flight Checks

Run these checks in parallel:

1. **AWS credentials**: `aws sts get-caller-identity` — must show account `879381242481`
2. **crane installed**: `crane version` — required for ECR push (Docker push has TLS issues)
3. **ECS current state**: Query service status, task definition revision, running task count, rollout state
4. **Health check**: `curl -s https://qlgen.gadgeon.com/api/v1/health` — confirm currently healthy

If any check fails, stop and report the issue.

### Step 2: Analyze Schema Changes

1. Read `DEPLOYMENT.md` "Current Deployment State" section to get the current Alembic HEAD revision
2. List all Alembic migration files in `backend/alembic/versions/`
3. Identify NEW migrations (revisions after the current HEAD)
4. For each new migration, read the file and summarize:
   - Tables created
   - Columns added/modified
   - Whether changes are additive (safe) or destructive (risky)
5. Report the migration chain and risk assessment

### Step 3: Check Task Definition

1. Fetch the current ECS task definition and list its environment variables
2. Check if the new code requires any NEW environment variables by scanning:
   - `backend/app/config.py` for new settings
   - New service/API files for references to `settings.*` or `os.environ`
3. If new env vars are needed:
   - Extract current task definition, strip AWS fields, add new vars
   - Register new task definition revision
   - Note the new revision number for Step 6
4. If no new env vars needed: proceed with current revision

### Step 4: Build Backend Docker Image

```bash
docker build --platform linux/amd64 -t qlgen-backend <project-root>/backend/
```

**After build, verify:**
1. Check new/modified files are present in the image:
   ```bash
   docker run --rm --entrypoint ls qlgen-backend:latest <paths-to-key-new-files>
   ```
2. Check Python 3.11 compatibility (the image uses `python:3.11-slim`):
   ```bash
   docker run --rm --entrypoint python qlgen-backend:latest -c "
   import ast, sys, pathlib
   errors = []
   for p in pathlib.Path('/app').rglob('*.py'):
       try: ast.parse(p.read_text())
       except SyntaxError as e: errors.append(f'{p}: {e}')
   if errors:
       for e in errors: print(e, file=sys.stderr)
       sys.exit(1)
   else: print('All .py files parse OK')
   "
   ```

**Known issue**: Python 3.11 does NOT allow backslash characters inside f-string expressions. If the syntax check fails, fix the offending file before proceeding.

### Step 5: Push to ECR via Crane

**Do NOT use `docker push`** — it fails with TLS handshake timeouts.

```bash
docker save qlgen-backend:latest -o /tmp/qlgen-backend.tar
chmod 644 /tmp/qlgen-backend.tar
crane auth login 879381242481.dkr.ecr.us-east-1.amazonaws.com -u AWS -p "$(aws ecr get-login-password --region us-east-1)"
crane push /tmp/qlgen-backend.tar 879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:latest
rm -f /tmp/qlgen-backend.tar
```

### Step 6: Deploy Backend to ECS

If task definition was updated (Step 3), include `--task-definition qlgen-backend:N`:
```bash
aws ecs update-service --cluster qlgen-cluster --service qlgen-backend \
  --task-definition qlgen-backend:N \
  --force-new-deployment --enable-execute-command --region us-east-1
```

If no task definition change, omit `--task-definition`:
```bash
aws ecs update-service --cluster qlgen-cluster --service qlgen-backend \
  --force-new-deployment --enable-execute-command --region us-east-1
```

**Always pass `--enable-execute-command`** or you lose ECS exec capability.

### Step 7: Monitor Backend Deployment

Poll deployment status every 30-60 seconds until PRIMARY shows `rolloutState: COMPLETED` with only one deployment remaining:

```bash
aws ecs describe-services --cluster qlgen-cluster --services qlgen-backend \
  --region us-east-1 \
  --query 'services[0].deployments[*].{status:status,desired:desiredCount,running:runningCount,rollout:rolloutState}'
```

Typical deployment takes 2-3 minutes.

**While waiting, start the frontend build (Step 8) in parallel if this is a full deployment.**

### Step 8: Verify Migrations

After at least one new task is running, check CloudWatch logs:

```bash
# Find newest log streams
aws logs describe-log-streams --log-group-name /ecs/qlgen-backend --region us-east-1 \
  --order-by LastEventTime --descending --limit 3 \
  --query 'logStreams[*].logStreamName' --output json

# Read startup logs (shows alembic output)
aws logs get-log-events --log-group-name /ecs/qlgen-backend \
  --log-stream-name "ecs/backend/<TASK_ID>" \
  --region us-east-1 --start-from-head --limit 25 \
  --query 'events[*].message' --output text
```

**What to look for:**
- `Running upgrade X -> Y, description` — one line per applied migration (success)
- Only `Context impl PostgresqlImpl` with no `Running upgrade` lines — DB was already at HEAD (also success)
- Any `Error`, `Traceback`, or `SyntaxError` — deployment problem, investigate immediately

Also search for errors:
```bash
aws logs filter-log-events --log-group-name /ecs/qlgen-backend --region us-east-1 \
  --filter-pattern "\"500\" OR \"Error\" OR \"Traceback\" OR \"UndefinedTable\"" \
  --start-time $(date -d '5 minutes ago' +%s000) --limit 20 \
  --query 'events[*].message' --output text
```

### Step 9: Build Frontend

```bash
cd <project-root>/frontend
npm install
VITE_API_BASE_URL="" \
VITE_GOOGLE_CLIENT_ID="1096888171910-q1a8ihfqvdbqopbj1d3c1unnhphc6sma.apps.googleusercontent.com" \
npm run build
```

**Critical**: `VITE_API_BASE_URL` MUST be empty string (`""`) for production. CloudFront routes `/api/*` to the ALB. Setting it to a URL causes CORS issues.

If TypeScript errors occur, fix them before proceeding. The build runs `tsc -b` (strict checking) before `vite build`.

### Step 10: Deploy Frontend to S3 + CloudFront

```bash
aws s3 sync <project-root>/frontend/dist/ s3://qlgen-frontend-prod/ --delete --region us-east-1
aws cloudfront create-invalidation --distribution-id EDR89QBSQMRDD --paths "/*" --region us-east-1
```

CloudFront invalidation takes 1-2 minutes.

### Step 11: End-to-End Verification

Run all of these:

1. **Health check**: `curl -s https://qlgen.gadgeon.com/api/v1/health` — expect `{"status":"healthy"}`
2. **New API routes**: Check each new route returns 401 (auth required) not 404 (missing):
   ```bash
   curl -s -o /dev/null -w "%{http_code}" https://qlgen.gadgeon.com/api/v1/<new-route>
   ```
3. **Frontend**: `curl -s https://qlgen.gadgeon.com/` — expect 200, verify the JS bundle hash matches build output
4. **CloudFront invalidation**: Check status is `Completed`
5. **Error check**: Search recent logs for 500 errors or tracebacks
6. **CloudWatch tail**: `aws logs tail /ecs/qlgen-backend --region us-east-1 --since 2m --format short | tail -10`

Report all results in a summary table.

### Step 12: Update DEPLOYMENT.md

After successful deployment, update `DEPLOYMENT.md`:

1. **Current Deployment State** section:
   - ECS Task Definition revision
   - Alembic Revision (HEAD) with description
   - Git Branch Deployed
   - Database Tables list (add any new tables)
   - Migration Chain (add new entries)

2. **Deployment History** section — add new entry at the top:
   ```
   ### YYYY-MM-DD — <brief description>
   
   **Changes deployed**: <summary of what was deployed>
   
   **Migrations applied** (N new, from `old_head` to `new_head`):
   - `revision` — description
   
   **Task definition**: <revision change or "no changes">
   
   **Issues encountered**: <any problems and how they were resolved, or "None">
   ```

---

## Conditional Execution

- If `$ARGUMENTS` is `backend`: Execute Steps 1-8 only (skip frontend steps 9-10)
- If `$ARGUMENTS` is `frontend`: Execute Steps 1, 9-11 only (skip backend steps)
- If `$ARGUMENTS` is `full` or empty: Execute all steps

---

## Troubleshooting

### Docker build needs sudo but password isn't available
Try without sudo first: `docker info`. If Docker works without sudo, use `docker` directly.

### crane not installed
```bash
curl -sL "https://github.com/google/go-containerregistry/releases/latest/download/go-containerregistry_Linux_x86_64.tar.gz" \
  -o /tmp/crane.tar.gz && tar -xzf /tmp/crane.tar.gz -C /usr/local/bin crane
```

### Python 3.11 SyntaxError in f-strings
Extract expressions containing backslashes to variables before the f-string. Example:
```python
# Bad (Python 3.11)
f'{"\"key\": 1" if x else ""}'
# Good
val = '"key": 1' if x else ""
f'{val}'
```

### ECS exec hangs / times out
ECS exec is unreliable in non-TTY environments. Use CloudWatch Logs instead:
```bash
aws logs filter-log-events --log-group-name /ecs/qlgen-backend --region us-east-1 \
  --filter-pattern "<search-term>" --start-time $(date -d '1 hour ago' +%s000) \
  --limit 20 --query 'events[*].message' --output text
```

### Deployment stuck / tasks failing
Check CloudWatch for startup errors. If the container crashes after running migrations, the migrations are already applied. Fix the code issue and redeploy.

### Frontend shows stale content
Verify CloudFront invalidation completed. Check the JS bundle hash in the HTML matches your build output.

### Rollback
**Backend**: `aws ecs update-service --cluster qlgen-cluster --service qlgen-backend --task-definition qlgen-backend:PREVIOUS_REVISION --force-new-deployment --enable-execute-command --region us-east-1`
**Frontend**: Rebuild from previous git commit and re-deploy to S3.
**Database**: Rolling back the container does NOT undo migrations. New tables/columns from additive migrations won't interfere with old code.
