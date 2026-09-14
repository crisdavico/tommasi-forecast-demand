# Design: Odoo Forecast Agent Bridge

UI enqueues; `ir.cron` HMAC-POSTs `/v1/agent/invoke`. MCP demand/stock unchanged. Specs missing; uses proposal + exploration. **Odoo 15** (`_name`, `_sql_constraints`, `tree`, `_` methods; no `privilege_id` / `@api.private` / `models.Constraint`).

## Technical Approach

`tommasi.forecast.agent.config` (unique `company_id`), AbstractModel HMAC helper, `tommasi.forecast.agent.run`. Reuse `llm.group_llm_manager`. Sign compact UTF-8 JSON once; canonical `POST\n/v1/agent/invoke\n{ts}\n{nonce}\n{sha256_hex(raw_body)}`. Store `assistant_id`; never send (`extra=forbid`). No `queue_job`; no HTTP in the user request.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Run + `ir.cron` SKIP LOCKED | Claim/commit vs TransactionCase | **Chosen** — no extra depend |
| `queue_job` / blocking POST | Missing depend / worker timeout | Rejected |
| README compose snippet | Local E2E needs later grant | **Chosen** — `devel.yaml` out of roots |
| Send `assistant_id` | Companion 422 | Store-only |
| `UNIQUE(company_id)` | No history rows | **Chosen** |
| Side cursor before HTTP | Extra cursor | **Chosen** — tests call `_process_run` |

## Data Flow

**ORM/ACL/query:** Enqueue = 1 config search + 1 insert. Cron = `SELECT … FOR UPDATE SKIP LOCKED LIMIT 5` (parameterized) + claim UPDATE + HTTP + result UPDATE. SUPERUSER cron bypasses rules. UI: manager CRUD + `[('company_id','in',company_ids)]`. Secrets `copy=False`; strip from `export_data`/logs/errors. `_` worker/HMAC. Demand/stock SQL unchanged.

```mermaid
sequenceDiagram
    participant U as Manager UI
    participant C as Config
    participant R as Run
    participant Cron as ir.cron
    participant H as HMAC
    participant E as Edge invoke
    U->>C: action_run_forecast
    C->>R: queued + idempotency_key
    U-->>U: open run (no HTTP)
    Cron->>R: SKIP LOCKED → running, attempt+=1, commit
    Cron->>H: compact JSON; new ts/nonce/sig
    H->>E: post verify=True redirects=False
    alt 200
        E-->>R: completed
    else 202/429/502/503/504/transport
        E-->>R: retry or failed if max
    else 401/403/409/422/other
        E-->>R: failed
    end
```

Stale `running` (`started_at` older than `read_timeout+60s`) = transport failure of that attempt.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `models/forecast_agent_config.py` | Create | Per-company config |
| `models/forecast_agent_hmac.py` | Create | Sign + POST helper |
| `models/forecast_agent_run.py` | Create | Queue + cron worker |
| `security/ir.model.access.csv` | Create | Manager CRUD |
| `security/forecast_agent_security.xml` | Create | Company rules |
| `data/ir_cron_forecast_agent.xml` | Create | 1 min, `noupdate`, `numbercall=-1` |
| `views/forecast_agent_views.xml` | Create | `tree`/`form`; Reporting; `llm.group_llm_manager`; parent `stock.menu_warehouse_report` |
| `tests/test_forecast_agent_{hmac,config,run,acl}.py` | Create | HMAC, HTTPS, queue, ACL |
| `__manifest__.py` | Modify | `15.0.5.0.0` + `data` |
| `models/__init__.py` | Modify | Register models |
| `tests/__init__.py` | Modify | Import tests; keep MCP |
| `README.rst` | Modify | Compose snippet + rotation |
| `models/product_product.py`, MCP tests | Unchanged | — |

## Interfaces / Contracts

| Knob | Default | Bounds |
|------|---------|--------|
| `connect_timeout` | 5s | 1–30 |
| `read_timeout` | 120s | 5–300 |
| `max_attempts` | 5 | 1–10 |
| `retry_backoff_seconds` | 30 | 5–300; delay `min(300, base*2^(attempt-1))`; 429 may use `Retry-After` 1–300 |
| Stale grace | `read_timeout+60s` | — |
| Cron | 1 min, batch 5 | Odoo 15 minutes |
| Nonce | `uuid.uuid4().hex` | per attempt; ≤128 |
| Idempotency | `odoo-tfd-{uuid4}` at create | reuse every attempt |
| `X-Request-Id` | uuid4 per attempt | persist last |
| Trigger `input` | `Run demand forecast.` | constant; no UI field |
| HTTPS | required | except `test_enable` or `DOODBA_ENVIRONMENT` in `devel`/`test` |

Fixed key order; omit `session_id`, `attachments`, `command`, `timeout`, `assistant_id`:

```json
{"input":"Run demand forecast.","response_mode":"sync","metadata":{"source":"odoo.tommasi_forecast_demand","trace_id":"<idempotency_key>","client_version":"15.0.5.0.0"}}
```

Compact once: `json.dumps(..., separators=(',', ':'), ensure_ascii=False).encode('utf-8')`. URL `edge_url.rstrip('/')+'/v1/agent/invoke'`. Headers: `Content-Type: application/json`, `X-API-Key`, `X-Timestamp` (unix int string), `X-Nonce`, `X-Signature` (hex HMAC-SHA256), `X-Idempotency-Key`, `X-Request-Id`. `timeout=(connect,read)`, `verify=True`, `allow_redirects=False`.

**Config:** unique `company_id`, `active`, `edge_url`, optional `assistant_id`, `api_key`, `hmac_secret`, timeout/attempt/backoff. **States:** `queued`→`running`→`completed`|`retry`|`failed`. Cancel queued/retry → failed. Retry failed (attempts left) → queued. 200 = complete (strict JSON, sanitize). Retry 202/429/502/503/504/transport. Terminal 401/403/409/422/other/exhausted.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit-in-case | Canonical string, signature, nonce≠idempotency | Frozen time/nonce; no live HTTP |
| Integration | HTTPS, unique company, ACL, claim, matrix, stale, redaction | `TransactionCase` `post_install,-at_install`; `patch('requests.post')` |
| E2E | Live signed invoke | Out of scope |

Keep importing existing MCP tests.

## Threat Matrix

Worker outbound HTTPS is process/network integration. Docs/git/commit/push/PR rows: **N/A** (no those boundaries).

| Boundary | Applicability | Design response | Planned RED tests |
|----------|---------------|-----------------|-------------------|
| Process/network (HTTPS) | **Applicable** | Stored URL; HTTPS unless devel/test/`test_enable`; `verify=True`; no redirects/userinfo; secrets not in errors/logs/`export_data` | HTTP rejected when HTTPS required; HTTP allowed under `test_enable`; mock 301 not followed; `verify=True`; secrets absent from `UserError`/`export_data`/logs |

## Migration / Rollout

Upgrade `15.0.4.0.0`→`15.0.5.0.0` adds tables/ACL/cron/views. No data migration. Uninstall drops new models. README `tommasi-forecast-edge` snippet; `streaming_allowed=FALSE`. Rotate secrets after edge (plaintext at rest).

## Open Questions

- [ ] Confirm `stock.menu_warehouse_report` at apply; fallback `stock.menu_stock_root`.
- [ ] None else — HMAC/bounds locked to companion source.
