# Proposal: Odoo Forecast Agent Bridge

## Intent

Add a manager-only queued HMAC client so Inventory managers can enqueue sync `POST /v1/agent/invoke` without blocking the browser or changing `get_sold_storable_products`.

## Scope

### In Scope

- `tommasi.forecast.agent.config`: unique `company_id`, secrets, URL/HTTPS, stored `assistant_id`
- HMAC client: compact UTF-8 JSON once; headers; retry vs terminal statuses
- `tommasi.forecast.agent.run` plus `ir.cron` (claim, retry, cancel)
- Inventory/Reporting UI; Run Forecast with no prompt field
- README doodba `tommasi-forecast-edge` snippet and secret rotation
- New TransactionCase tests with mocked HTTP

### Out of Scope

- `queue_job`; blocking HTTP in the user request; editing parent `devel.yaml`
- Sending `assistant_id` on invoke JSON; historical inactive config rows
- MCP tool/tests, `schema_version`, or pagination changes
- Live signed E2E; companion network/scope work

## Capabilities

### New Capabilities

- `forecast-agent-config`: one row per company; secrets; URL/HTTPS; store-only `assistant_id`
- `forecast-agent-invoke`: HMAC client, headers, stateless sync body, status handling
- `forecast-agent-runs`: queue, cron claim, retry/cancel, manager UI, company rules

### Modified Capabilities

None. `openspec/specs/` is empty. MCP demand requirements stay unchanged.

## Approach

- Unique `company_id`; `copy=False` secrets; no tracking/chatter; HTTPS except `test_enable` or `DOODBA_ENVIRONMENT` `devel`/`test`
- Sign transmitted bytes; canonical `POST\n/v1/agent/invoke\n{timestamp}\n{nonce}\n{sha256_hex(body)}`; reuse idempotency key; fresh timestamp/nonce/signature
- Fixed trigger `input`; omit `session_id`; `response_mode=sync`; metadata `source`, `trace_id`, `client_version` only
- UI enqueues; cron `SKIP LOCKED`; retry 202/429/transport/502/503/504; terminate 401/403/409/422
- Reuse `llm.group_llm_manager`; Odoo 15 APIs only; MCP envelope, `schema_version` (1), and pagination unchanged

## Affected Areas

| Area | Impact |
|------|--------|
| `models/product_product.py`, MCP tests | Unchanged |
| `__manifest__.py`, model/test `__init__.py`, `README.rst` | Modified (bump `15.0.5.0.0`) |
| `models/forecast_agent_{config,hmac,run}.py`, `security/`, cron XML, `views/` | New |
| parent `devel.yaml` | Out of authority; document only |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| No parent Compose attach | High | README snippet; no `devel.yaml` task without `(read-only)` |
| Companion drift; HMAC/nonce 401 | Med | Match today's HMAC/path/body; new nonce; reuse idempotency key |
| Cron commit vs TransactionCase | Med | Side cursor; in-memory `_process_run` tests |
| Plaintext secrets; >400-line review | High | Redact/docs; chained-PR forecast in tasks |

## Rollback Plan

MCP/`schema_version`/pagination are unchanged. Uninstall or downgrade to drop new models, views, ACL, and cron.

## Dependencies

`llm_tool` (`llm.group_llm_manager`), `sale_stock`, companion HMAC as implemented today, `requests`, later doodba grant for `tommasi-forecast-edge`.

## Success Criteria

- [ ] One config per company; enqueue with no prompt field
- [ ] Browser never waits on HTTP; cron processes the queue
- [ ] Tests cover HMAC bytes, status matrix, secret redaction, and company/ACL isolation
- [ ] MCP tests pass unchanged; no live signed E2E required
