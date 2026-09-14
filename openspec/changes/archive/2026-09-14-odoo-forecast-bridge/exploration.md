## Exploration: odoo-forecast-bridge

Odoo-owned half of the secure forecast-agent bridge: manager-only configuration, exact HMAC invoke, durable queued runs, manager UI, local network documentation, and tests. The existing LangGraph-to-Odoo MCP demand tool stays unchanged.

### Current State

`tommasi_forecast_demand` (Odoo 15, version `15.0.4.0.0`) is a small addon: `product.product.get_sold_storable_products` via `@llm_tool`, plus `tests/test_sold_storable_products.py` (`TransactionCase`, `@tagged("post_install", "-at_install")`). Manifest depends on `llm_tool`, `llm_mcp_server`, and `sale_stock`. There are no `data`/`security`/`views` files, no config models, no cron, no outbound HTTP, and no HMAC code.

OpenSpec is initialized (`strict_tdd: false`, no main specs). Tests import through `tests/__init__.py`. Verify command lives outside this git root: `invoke test --modules=tommasi_forecast_demand` from the doodba project.

Companion edge (`docker-compose-tommasi-forecast-agent`, read-only) already implements the invoke contract Odoo must match:

- `POST /v1/agent/invoke` (router prefix `/v1` + `/agent` + `/invoke`).
- Canonical HMAC string: `{METHOD}\n{path}\n{timestamp}\n{nonce}\n{sha256_hex(raw_body)}` with path `/v1/agent/invoke`; hex HMAC-SHA256 in `X-Signature`; timestamp Unix epoch as string; nonce unique (max 128 chars) with Redis anti-replay.
- Headers: `X-API-Key`, `X-Timestamp`, `X-Nonce`, `X-Signature`; optional sync `X-Idempotency-Key`; `X-Request-Id` accepted or generated.
- Public body is `InvokeRequest` with `extra=forbid`. There is **no** `assistant_id` field today. Stateless runs omit `session_id`; edge maps assistant to `EDGE` `default_assistant_id`.
- Status matrix: `401` auth/signature, `403` authorization, `409` idempotency conflict, `422` validation, `429` rate limit, `202` in-progress idempotency, `502`/`503`/`504` upstream. `scopes` is stored and documented as reserved; `streaming_allowed` must be `FALSE` for a sync-only client.
- Compose files do **not** yet declare network `tommasi-forecast-edge`. That is a companion-plan deliverable, not present in current YAML.

Sibling `llm_tool_tommasi` (different git root) is the local manager-ACL pattern: `security/ir.model.access.csv` bound to `llm.group_llm_manager`, menu `groups="llm.group_llm_manager"`, no extra `res.groups` in the addon. Config there is a **database singleton**, not per-company, and has no secrets.

Parent doodba `devel.yaml` (different git repo) already joins Odoo to an **external** network for Chatwoot (`chatwoot_compose` / `chatwoot-compose_default`). Default network is internal (`DOODBA_NETWORK_INTERNAL`). There is no `tommasi-forecast-edge` attachment yet. This SDD `allowedEditRoots` is the addon only, so `devel.yaml` cannot be edited here.

Odoo 15 vs injected Odoo 19 skill guides: implement Odoo 15 APIs (`_name` required, `_sql_constraints`, `tree` views, `_` private methods, no `privilege_id` / `@api.private` / `models.Constraint`). Reuse `llm.group_llm_manager` from `llm_tool`; do not invent a new group.

### Affected Areas

- `models/product_product.py` — **do not change** (MCP demand tool).
- `tests/test_sold_storable_products.py` — **do not change** contract tests; keep importing them.
- `__manifest__.py` — add `data` files (security, cron, views); version bump for new models (suggested `15.0.5.0.0`); keep existing depends (`llm_tool` already pulls `llm.group_llm_manager`; `sale_stock` pulls Inventory menus).
- `models/__init__.py` — register config, HMAC helper, run/worker models.
- `tests/__init__.py` — import new test modules.
- **New** `models/forecast_agent_config.py` — `tommasi.forecast.agent.config`: per-company, secrets, URL/credential validation, HTTPS except devel/test.
- **New** `models/forecast_agent_hmac.py` — abstract signer/client: compact UTF-8 JSON once, sign exact bytes, `requests` with verify, bounded timeouts, `allow_redirects=False`, redaction.
- **New** `models/forecast_agent_run.py` — `tommasi.forecast.agent.run` queue + guarded retry/cancel + cron claim/process.
- **New** `security/ir.model.access.csv` + `security/forecast_agent_security.xml` — manager-only ACL + company record rules.
- **New** `data/ir_cron_forecast_agent.xml` — short-interval worker; `noupdate` as usual for cron.
- **New** `views/` + menus under Inventory/Reporting (`stock.menu_warehouse_report` is the Odoo 15 parent to confirm at apply time).
- `README.rst` — local `http://edge-api:8080` + external network snippet; plaintext-at-rest / rotation; no credentials.
- Parent `devel.yaml` — **out of edit authority**; document snippet only unless a later grant is given.
- Companion edge repo — **read-only**; Odoo must match current HMAC/path/headers and stay compatible with the planned network, sync-only client, optional `assistant_id` / `assistant:<id>` scope.

### Approaches

1. **Durable run model + `ir.cron` worker (no `queue_job`)** — Create `tommasi.forecast.agent.run` with states queued/running/retry/completed/failed. UI only enqueues. Cron claims with `FOR UPDATE SKIP LOCKED`, commits the claim (or uses a side cursor) before HTTP, recovers stale `running` after `timeout * attempts + grace`.
   - Pros: stays inside this addon; matches “do not hold the browser”; testable with mocked `requests`; no extra Odoo dependency.
   - Cons: must handle commit/cursor carefully so TransactionCase still rolls back; concurrency tests need an extra cursor, not two browsers.
   - Effort: Medium

2. **OCA `queue_job` / `base.automation` HTTP from the form** — Job queue or a blocking `action_run` that POSTs in the user request.
   - Pros: queue_job has retry/isolation; blocking is simpler to code.
   - Cons: `queue_job` is not a current depend and may be absent in doodba; blocking HTTP violates the product rule and dies on worker limits.
   - Effort: High (queue_job) / Low-but-invalid (blocking)

3. **Local Compose attachment**
   - **3a. Document-only snippet in addon README** (default under current edit roots): copy-paste `odoo.networks` + `networks.tommasi_forecast_edge.external.name: tommasi-forecast-edge`, URL `http://edge-api:8080`, modeled on existing `chatwoot_compose`. Production stays HTTPS hostname.
   - **3b. Later edit-authority grant** to the doodba repo to apply the same snippet in `devel.yaml`.
   - **3c. Overlay file in the addon** that doodba will not load unless the parent compose includes it — dead without a parent edit.
   - Pros of 3a: legal under `allowedEditRoots`; unblocks proposal/spec. Cons: local E2E still needs a human (or later grant) to edit `devel.yaml`. Companion must actually create network `tommasi-forecast-edge` (not in current companion YAML).
   - Effort: Low (3a) / Medium (3b, different repo)

4. **Optional `assistant_id` on config vs invoke body**
   - Store on `tommasi.forecast.agent.config` (confirmed). **Do not** put `assistant_id` on the JSON body while companion `InvokeRequest` uses `extra=forbid` (would `422`). Current mapper always uses `settings.default_assistant_id`. Provisioned client scopes `invoke` and optional `assistant:<id>` are an edge-side concern; README should tell operators to set `streaming_allowed=FALSE` and matching scopes.
   - If companion later adds a dedicated field, a small follow-up can send it. Do not stuff it into `metadata` hoping to select the assistant (edge ignores that for routing).
   - Effort: Low if store-and-document; High/wrong if sent as extra JSON now

5. **Per-company uniqueness**
   - **5a.** `unique(company_id)` plus `active` boolean (one row per company).
   - **5b.** Partial unique index “one active per company” allowing history rows.
   - 5a fits Odoo 15 `_sql_constraints` and the sibling singleton pattern; 5b needs custom SQL. Prefer 5a unless historical configs are required (they are not).
   - Effort: Low (5a) / Medium (5b)

### Recommendation

Implement **Approach 1 + 3a + store-only assistant_id + 5a** inside this addon:

1. **Config** `tommasi.forecast.agent.config`: `company_id` required, `_sql_constraints` unique per company, `active`, `edge_url`, optional `assistant_id`, `api_key`, `hmac_secret`, bounded `connect_timeout` / `read_timeout` / `max_attempts` / `retry_backoff` fields. Validate URL (https required unless `test_enable` or `DOODBA_ENVIRONMENT` in `devel`/`test`). Secrets: `copy=False`, no `tracking`, no `mail.thread`, omit from `export_data` / error strings / logs / chatter. Document plaintext-at-rest in Odoo/Postgres backups and rotation in README.
2. **HMAC service** as an AbstractModel plus pure helpers: `json.dumps(..., separators=(',', ':'), ensure_ascii=False).encode('utf-8')` **once**; SHA-256 those bytes; sign canonical `POST\n/v1/agent/invoke\n{timestamp}\n{nonce}\n{hexdigest}` with the plaintext HMAC secret; send **those same bytes** as the body. Headers: `X-API-Key`, `X-Timestamp`, `X-Nonce`, `X-Signature`, stable per-run `X-Idempotency-Key`, correlation `X-Request-Id`. Reuse idempotency key; new timestamp/nonce/signature every attempt (edge rejects reused nonces). `requests.post(..., timeout=(connect, read), verify=True, allow_redirects=False)`. Strict JSON parse of success bodies; sanitize/redact before storing or logging.
3. **Body (stateless sync):** `input` = fixed module constant (no UI field); omit `session_id`, `attachments`, `command`; `response_mode` = `"sync"`; `metadata` only `source`, `trace_id`, `client_version`.
4. **Run** `tommasi.forecast.agent.run`: immutable idempotency key at create; states queued/running/retry/completed/failed; attempts, next-attempt, edge request id, HTTP status, sanitized payloads, timing. Retry `202`/`429`/transport/`502`/`503`/`504` with bounded backoff; terminal `401`/`403`/`409`/`422`. Guarded `action_retry` / `action_cancel`. Cron every minute; claim `SKIP LOCKED`; recover stale `running`; never wait on HTTP in the browser request.
5. **ACL/UI:** `ir.model.access.csv` CRUD only for `llm.group_llm_manager`; company record rules on both models; menus under Inventory/Reporting with `groups="llm.group_llm_manager"`. “Run Forecast” creates a queued run from the current-company active config (UserError if missing). Forms are read-only for status/output/timing/sanitized diagnostics. Non-managers and other companies must not search/read records (`AccessError` / empty search).
6. **Compose:** README snippet only in this change. Production URL is HTTPS hostname. Do not put `devel.yaml` on a tasks checkbox without `(read-only)` or a later grant — native status would `blocked(edit_authority_missing)`.
7. **Tests:** new TransactionCase modules imported from `tests/__init__.py`, same post_install/-at_install tags. Cover signing (canonical bytes), config validation, ACL/company isolation, queue claim/status matrix, mocked HTTP, and assert secrets never appear in exceptions, logs captured in-test, or `export_data`. Do not require a live signed E2E to close the suite. Leave MCP tests intact.

### Risks

- **Edit authority:** attaching `tommasi-forecast-edge` requires editing parent `devel.yaml` (other git root). This change can only document the snippet. Local HTTP E2E stays post-companion and post-grant.
- **Companion drift:** current edge has no `tommasi-forecast-edge` network, does not enforce `scopes`, and does not accept `assistant_id` on invoke. Odoo must match **today’s** HMAC/path/body and treat network/scopes/assistant routing as companion deliverables documented in README.
- **Doodba internal network:** without the external network, Odoo cannot resolve `http://edge-api:8080` even if config is correct.
- **Secrets at rest:** Odoo fields are plaintext in Postgres and backups; Fernet exists only on the edge `hmac_secret` column. Rotation and access to `llm.group_llm_manager` are the real controls.
- **HMAC byte identity:** re-serializing JSON between sign and send (pretty-print, key reorder, `ensure_ascii` mismatch) yields `401`. Tests must use the same bytes.
- **Nonce vs idempotency:** reusing nonce on retry is a `401` replay; reusing idempotency key is required. Easy to get backwards.
- **Cron + tests:** `cr.commit()` in the worker breaks TransactionCase unless production commit is isolated (side cursor / `registry.cursor()`) and tests call `_process_run` in-memory with mocks.
- **Odoo 15 vs Odoo 19 skill text:** following 19-only APIs (`list` views, `privilege_id`, `@api.private`) would fail on this stack.
- **Review budget:** new models + security + views + several test modules will likely exceed 400 authored lines; tasks phase should forecast chained PRs.

### Ready for Proposal

Yes. Product decisions are confirmed and fit the current addon (MCP left untouched, new models/files only). Companion HMAC canonical string, headers, invoke path, idempotency `202`, and error status codes are verified in edge source. Propose next: lock the config/run field list, trigger `input` constant, retry/backoff bounds, stale-running grace, HTTPS exception rules, README compose snippet, and the test matrix. Do not start spec/design in this phase.
