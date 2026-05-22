# Pipeline-failure fix — remaining deploy steps

## Status

- [x] **Code fix applied** to working tree: `backend/app/services/pipeline_service.py:768-769` — `(item.get("vertical") or "")` / `(item.get("sub_vertical") or "")` now coerces `None → ""` before `.lower()`. Unblocks ~75% of failing runs once deployed.
- [x] **IAM policy patched** (already live, no deploy needed): added `arn:aws:bedrock:*::foundation-model/amazon.titan-embed-*` to the `bedrock-invoke` inline policy on role `qlgen-ecs-task`. Existing ECS tasks may still hit `AccessDeniedException` because the SSM/STS creds inside the running container were cached at task start — they refresh automatically within ~1 hour, OR are refreshed immediately by a new task. Forcing a new deployment (step 5 below) picks up new creds right away.
- [ ] **Build, push, deploy backend** — steps below.
- [ ] **Investigate JSON parse failure** for run `db915f0f-a8a8-40d9-a944-6d40d8129495` (line 1498 col 7) — sample the failing payload from `pipeline_logs` once a fresh run completes.

---

## 1. Build the image (needs sudo for docker)

```bash
cd /home/sreejith-k/ql-generator/ql-generator/qlgen
sudo docker build --platform linux/amd64 -t qlgen-backend backend/
```

Takes ~2-3 min. Expect ~772 MB image.

## 2. Save to tar and chmod (crane needs to read it)

```bash
sudo docker save qlgen-backend:latest -o /tmp/qlgen-backend.tar
sudo chmod 644 /tmp/qlgen-backend.tar
```

## 3. Push to ECR via crane

(Docker push direct to ECR fails with TLS handshake timeout on this box — use crane.)

```bash
ECR_PASS=$(aws ecr get-login-password --region us-east-1)
crane auth login 879381242481.dkr.ecr.us-east-1.amazonaws.com -u AWS -p "$ECR_PASS"
crane push /tmp/qlgen-backend.tar 879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:latest
sudo rm -f /tmp/qlgen-backend.tar
```

> Note: the current task definition (revision 13) references a specific tagged image (e.g. `deploy-20260519-115155`), **not** `:latest`. Verify with:
> ```bash
> aws ecs describe-task-definition --task-definition qlgen-backend --region us-east-1 \
>   --query 'taskDefinition.containerDefinitions[0].image' --output text
> ```
> If the output is **NOT** `…/qlgen-backend:latest`, you must also push to that specific tag:
> ```bash
> crane push /tmp/qlgen-backend.tar 879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:<TAG_FROM_TASK_DEF>
> ```
> OR register a new task definition revision that points to `:latest` (recommended for one-off fixes). See DEPLOYMENT.md §1.

## 4. (Conditional) Register new task def revision pointing at :latest

Only if step 3's image tag is NOT `:latest`. Easier than juggling deploy-tags.

```bash
aws ecs describe-task-definition --task-definition qlgen-backend --region us-east-1 \
  --query 'taskDefinition' --output json \
  | jq 'del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)' \
  | jq '.containerDefinitions[0].image = "879381242481.dkr.ecr.us-east-1.amazonaws.com/qlgen-backend:latest"' \
  > /tmp/qlgen-task-def.json

aws ecs register-task-definition --cli-input-json file:///tmp/qlgen-task-def.json --region us-east-1 \
  --query 'taskDefinition.{family:family,revision:revision}'
# Note the new revision number → use as :N in step 5
```

## 5. Force new ECS deployment

If you kept the existing task def (image tag matches):

```bash
aws ecs update-service --cluster qlgen-cluster --service qlgen-backend \
  --force-new-deployment --enable-execute-command --region us-east-1
```

If you registered a new revision in step 4 (replace `:N` with the new revision):

```bash
aws ecs update-service --cluster qlgen-cluster --service qlgen-backend \
  --task-definition qlgen-backend:N --force-new-deployment \
  --enable-execute-command --region us-east-1
```

## 6. Watch deployment + verify

```bash
# Watch rollout (run repeatedly until only PRIMARY remains with rollout=COMPLETED)
aws ecs describe-services --cluster qlgen-cluster --services qlgen-backend --region us-east-1 \
  --query 'services[0].deployments[*].{status:status,taskDef:taskDefinition,desired:desiredCount,running:runningCount,rollout:rolloutState}'

# Tail logs for errors during rollout
aws logs tail /ecs/qlgen-backend --region us-east-1 --since 5m --follow

# Health check
curl -s https://qlgen.gadgeon.com/api/v1/health
# Expected: {"status":"healthy","service":"qlGen API"}
```

## 7. Validate the fix end-to-end

1. Trigger a pipeline run from https://qlgen.gadgeon.com/dashboard (any ICP that previously failed).
2. Watch logs:
   ```bash
   aws logs tail /ecs/qlgen-backend --region us-east-1 --since 10m --follow --filter-pattern 'pipeline_service'
   ```
3. Confirm: NO `AttributeError: 'NoneType' object has no attribute 'lower'` lines, NO `AccessDeniedException` lines on `amazon.titan-embed-text-v2:0`.
4. Pipeline should advance past Stage 2 (firmographic fit) — previously it died right at that boundary.

## 8. Once stable, commit and tidy

The code edit is local-only on branch `signalreasearch`:

```bash
git diff backend/app/services/pipeline_service.py
git add backend/app/services/pipeline_service.py
git commit -m "fix(pipeline): coerce None vertical/sub_vertical before .lower()

quick_firmographic_filter crashed with AttributeError when ICP
industry_types items have explicit null values for vertical or
sub_vertical (dict.get default only fires for missing keys, not
null values). Caused ~75% of production pipeline failures."
```

Don't push without your usual review.

---

## Rollback (if anything goes wrong)

```bash
# Roll backend back one revision
aws ecs list-task-definitions --family-prefix qlgen-backend --region us-east-1 --sort DESC --max-items 5
aws ecs update-service --cluster qlgen-cluster --service qlgen-backend \
  --task-definition qlgen-backend:PREVIOUS --force-new-deployment \
  --enable-execute-command --region us-east-1
```

The IAM change is additive (added one resource ARN); to revert:

```bash
aws iam put-role-policy --role-name qlgen-ecs-task --policy-name bedrock-invoke --policy-document '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream","bedrock:Converse","bedrock:ConverseStream"],
    "Resource": [
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4*",
      "arn:aws:bedrock:*:*:inference-profile/us.anthropic.claude-sonnet-4*"
    ]
  }]
}'
```
