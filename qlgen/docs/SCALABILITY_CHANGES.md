# Scalability Changes for Multi-User Rollout

**Date:** 2026-03-17
**Branch:** `search_enhancements`
**Context:** Preparing qlGen for rollout to a 20-30 person sales team. A scalability audit identified three must-fix items to support parallel pipeline runs across multiple ECS tasks and uvicorn workers.

---

## Summary of Changes

| Fix | What Changed | Why |
|-----|-------------|-----|
| Redis event store | In-memory SSE state replaced with Redis | Enables cross-process and cross-task event delivery |
| Bedrock model upgrade | Sonnet 4 -> Sonnet 4.5 | 50x RPM increase (200 -> 10,000) at same per-token cost |
| Uvicorn workers | 1 worker -> 2 workers in production | Doubles thread pool capacity per ECS task |

---

## Fix 1: Redis-Backed Event Store

### Problem

Pipeline SSE events and cancellation state were stored in process-local Python dicts (`pipeline.py:31-33`):

```python
pipeline_events: dict[str, list] = {}
cancelled_runs: set[str] = set()
```

With multiple ECS tasks behind an ALB (or multiple uvicorn workers), a pipeline started on Task A would write events to Task A's memory. If the SSE `/stream` request routed to Task B, the user would see zero events. Cancellation requests on a different task/worker would also be lost.

### Solution

A new Redis-backed event store module (`app/services/event_store.py`) replaces the in-memory dicts. It provides:

- **Async API** for FastAPI route handlers (SSE generator, pipeline start/cancel/delete)
- **Sync API** for the agent callback handler running in thread-pool threads
- **In-memory fallback** for local development without Redis

### Files Changed

| File | Change |
|------|--------|
| `backend/app/services/event_store.py` | **New file.** Redis-backed event store with async + sync APIs, TTL-based auto-expiry (2 hours), and in-memory fallback. |
| `backend/app/api/pipeline.py` | Removed `pipeline_events` dict and `cancelled_runs` set. All SSE event read/write and cancellation now goes through `event_store`. The SSE `event_generator` reads from Redis via `event_store.get_events()`. |
| `backend/app/services/pipeline_service.py` | `_emit_event()` changed from sync dict-append to `async` Redis push via `event_store.push_event()`. Removed `events` and `cancelled_runs` parameters from `execute_pipeline()`, `resume_after_firmographic()`, `resume_after_first_signal()`, `resume_after_signals()`, `_run_signal_research()`, and `_handle_pipeline_error()`. Cancellation cleanup uses `event_store.clear_cancelled()`. |
| `backend/app/agent/lead_gen_agent.py` | `create_pipeline_callback_handler()` no longer accepts `events` dict or `cancelled_runs` set. The `_emit()` inner function uses `event_store.push_event_sync()` (sync Redis). Cancellation check uses `event_store.is_cancelled_sync()`. |
| `backend/app/config.py` | Added `REDIS_URL` setting (default: `redis://localhost:6379/0`). |
| `backend/requirements.txt` | Added `redis[hiredis]==5.2.1`. |

### Redis Key Schema

| Key Pattern | Type | TTL | Purpose |
|-------------|------|-----|---------|
| `pipeline:{run_id}:events` | List | 2 hours | Ordered SSE events for a pipeline run |
| `pipeline:cancelled` | Set | 1 hour | Run IDs that have been cancelled |

### Fallback Behavior

If Redis is unavailable at startup, the module logs a warning and falls back to process-local dicts (identical to the old behavior). This means:
- Local development works without Redis
- Production requires Redis for cross-task SSE delivery

---

## Fix 2: Bedrock Model Upgrade (Sonnet 4 -> Sonnet 4.5)

### Problem

Claude Sonnet 4 (`us.anthropic.claude-sonnet-4-20250514-v1:0`) has a rate limit of **200 RPM**. Each pipeline run makes ~42 LLM calls (for 20 companies), so only 4-5 concurrent pipeline runs could execute before hitting throttling.

### Solution

Switched to Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`) which has **10,000 RPM** -- 50x more headroom at the same per-token price ($3/MTok input, $15/MTok output).

### Files Changed

| File | Change |
|------|--------|
| `backend/app/config.py` | Default `BEDROCK_MODEL_ID` changed to `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `infra/modules/backend-ecs/main.tf` | `BEDROCK_MODEL_ID` env var updated to Sonnet 4.5. Added `REDIS_URL` env var. Added Sonnet 4.5 ARN to Bedrock IAM policy. |

---

## Fix 3: Uvicorn Workers (1 -> 2)

### Problem

Each ECS task ran a single uvicorn worker with a default thread pool of 6 threads (Python's `min(32, cpu_count + 4)` on 2-vCPU Fargate tasks). Each active pipeline stage occupies 1 thread, limiting concurrent pipeline runs per task.

### Solution

Added `--workers 2` to the production uvicorn command in `entrypoint.sh`. This doubles thread pool capacity per ECS task (12 threads instead of 6). The Redis event store (Fix 1) was a prerequisite since multiple workers are separate processes that cannot share in-memory state.

### Files Changed

| File | Change |
|------|--------|
| `backend/entrypoint.sh` | Changed `uvicorn app.main:app --host 0.0.0.0 --port 8000` to `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2` |

### Note on Local Development

The `make dev-backend` command uses `uvicorn --reload` (single worker) and is unaffected. The `--workers 2` change only applies in production Docker containers via `entrypoint.sh`.

---

## Infrastructure Changes (Terraform)

### New Module: `infra/modules/redis/`

ElastiCache Redis (single-node, `cache.t4g.micro`) for SSE event storage.

| File | Purpose |
|------|---------|
| `modules/redis/main.tf` | `aws_elasticache_subnet_group` (private subnets) + `aws_elasticache_cluster` (Redis 7.1, cache.t4g.micro, port 6379) |
| `modules/redis/variables.tf` | Inputs: `project_name`, `private_subnet_ids`, `redis_security_group_id` |
| `modules/redis/outputs.tf` | Outputs: `endpoint` (address), `port` |

### Modified Infrastructure Files

| File | Change |
|------|--------|
| `infra/modules/networking/main.tf` | Added `aws_security_group.redis` (port 6379/TCP ingress from ECS SG) |
| `infra/modules/networking/outputs.tf` | Added `redis_security_group_id` output |
| `infra/modules/backend-ecs/main.tf` | Added `REDIS_URL` env var (`redis://${var.redis_endpoint}:6379/0`), updated `BEDROCK_MODEL_ID` to Sonnet 4.5, added Sonnet 4.5 ARN to Bedrock IAM resource policy |
| `infra/modules/backend-ecs/variables.tf` | Added `redis_endpoint` variable |
| `infra/main.tf` | Added `module "redis"` block wired to networking outputs; passes `redis_endpoint` to `backend_ecs` module |
| `infra/outputs.tf` | Added `redis_endpoint` output |

### Deployment Order

1. `terraform apply` -- provisions ElastiCache Redis + security group + updates ECS task definition
2. Build and push backend Docker image (includes new `redis` Python dependency)
3. Force new ECS deployment to pick up new task definition (REDIS_URL, BEDROCK_MODEL_ID) and new image

---

## Database Migration

A pending migration was also applied during local testing:

| Revision | Description |
|----------|-------------|
| `704565025b67` | `Add asset_value to companies` -- adds `BigInteger` column `asset_value` to `companies` table |

This migration runs automatically in production via `entrypoint.sh` (`alembic upgrade head` before uvicorn starts).

---

## Cost Impact

| Item | Additional Monthly Cost |
|------|------------------------|
| ElastiCache Redis (cache.t4g.micro) | ~$12 |
| Bedrock model switch (same per-token price) | $0 |
| Uvicorn workers (config change) | $0 |
| **Total infrastructure delta** | **~$12/month** |

Bedrock costs will scale with user adoption (more pipeline runs = more tokens), estimated at $2,500-$8,000/month for 20-30 active users depending on usage intensity.

---

## Capacity After Changes

| Resource | Before | After |
|----------|--------|-------|
| Bedrock RPM | 200 (Sonnet 4) | 10,000 (Sonnet 4.5) |
| Concurrent pipeline runs (Bedrock limit) | ~4-5 | ~200+ |
| Thread pool per ECS task | 6 (1 worker) | 12 (2 workers) |
| SSE cross-task delivery | Broken (in-memory only) | Working (Redis-backed) |
| Cancellation cross-task | Broken | Working |
| Max concurrent pipeline runs (compute) | ~12 (2 tasks x 6 threads) | ~48 (4 tasks x 12 threads, with auto-scaling) |
