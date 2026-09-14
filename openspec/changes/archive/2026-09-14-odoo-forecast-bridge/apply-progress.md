# Apply Progress: odoo-forecast-bridge

**Change**: odoo-forecast-bridge
**Mode**: Standard (`strict_tdd: false`)
**Work unit**: phase-5-docs-verify-import (tasks 5.1–5.2)
**Delivery**: exception-ok / size-exception (maintainer accepted)
**Attempt token**: sha256:7b8bc5578a26cec85508bd16c12efd6f547fd542befdb258996c3cc98e417dd3 (parent acquire; not settled here)
**Request-id**: f4c7c35e-4efa-434c-93f7-6866d8976739

## Remediation after failed verify (2026-09-14)

Independent verify failed because `Logged failure` was UNTESTED. Follow-up:

- HMAC `_post_invoke` now logs a constant `Forecast agent HTTP %s` on non-200 (status only; no body/secrets).
- `tests/test_forecast_agent_hmac.py > test_retryable_failure_logs_omit_secrets` captures WARNING logs on transport and HTTP 503 with leaky exception/body text.
- Retry test now pins distinct unix timestamps via `time.time` so `X-Timestamp` changes per attempt.

Focused result: `invoke test --modules=tommasi_forecast_demand` → 0 failed, 0 error(s) of 49 tests.

## Completed Tasks

- [x] 1.1 RED `tests/test_forecast_agent_config.py`: HTTP save rejected when HTTPS required; HTTP allowed under `test_enable`.
- [x] 1.2 RED `tests/test_forecast_agent_acl.py`: secrets absent from `UserError`, `export_data`, and logs.
- [x] 1.3 Create `models/forecast_agent_config.py`: unique `company_id` `_sql_constraints`; `copy=False` secrets; optional `assistant_id`; HTTPS unless `test_enable` or DOODBA_ENVIRONMENT devel/test; timeout bounds.
- [x] 1.4 Create `security/ir.model.access.csv` and `security/forecast_agent_security.xml`: `llm.group_llm_manager` CRUD; company rules.
- [x] 1.5 Register config in `models/__init__.py`; add security to `__manifest__.py` data; bump 15.0.5.0.0.
- [x] 1.6 GREEN unique reject, optional `assistant_id`, copy omits secrets, manager CRUD vs deny, company isolation in those tests.
- [x] 1.7 Import new tests in `tests/__init__.py`; keep importing existing MCP tests.
- [x] 2.1 RED `tests/test_forecast_agent_hmac.py`: `verify=True`; `allow_redirects=False` on mock 301.
- [x] 2.2 Create `models/forecast_agent_hmac.py` AbstractModel `_` helpers: compact UTF-8 once; canonical POST invoke HMAC string; headers; omit `assistant_id`; timeout=(connect,read).
- [x] 2.3 Register HMAC in `models/__init__.py`.
- [x] 2.4 Tests in `tests/test_forecast_agent_hmac.py`: signed bytes; retry reuses idempotency not nonce; fixed body; 503 retry / 401 terminal; errors omit secrets.
- [x] 3.1 Create `models/forecast_agent_run.py`: enqueue without HTTP; five states; SKIP LOCKED LIMIT 5; stale running; cancel/retry; sanitize payloads.
- [x] 3.2 Create `data/ir_cron_forecast_agent.xml` (1 min, `noupdate`, `numbercall=-1`); add to `__manifest__.py`; register run in `models/__init__.py`.
- [x] 3.3 Extend `security/ir.model.access.csv` and `security/forecast_agent_security.xml` for run CRUD and company rules.
- [x] 3.4 Tests in `tests/test_forecast_agent_run.py`: enqueue no HTTP; missing config `UserError`; claim; stale; cancel; reject completed; sanitize; `_process_run` patched POST.
- [x] 4.1 Create `views/forecast_agent_views.xml`: Odoo 15 `tree`/`form`; no prompt; Run Forecast; read-only diagnostics; menu `stock.menu_warehouse_report` fallback `stock.menu_stock_root`; group `llm.group_llm_manager`.
- [x] 4.2 Add views to `__manifest__.py` data.
- [x] 4.3 Tests in `tests/test_forecast_agent_acl.py`: manager form sanitized; other company/non-manager denied.
- [x] 5.1 Update `README.rst`: tommasi-forecast-edge snippet, `streaming_allowed=FALSE`, secret rotation; do not edit parent doodba devel.yaml.
- [x] 5.2 Confirm `tests/__init__.py` still imports MCP tests; prove with invoke test --modules=tommasi_forecast_demand from doodba parent.

## Files Changed

### Phase 1 (prior batch)

| File | Action | What Was Done |
|------|--------|---------------|
| `tests/test_forecast_agent_config.py` | Created | Threat-matrix HTTPS RED tests plus GREEN unique/optional/copy |
| `tests/test_forecast_agent_acl.py` | Created | Threat-matrix secret redaction RED tests plus GREEN manager ACL/isolation |
| `models/forecast_agent_config.py` | Created | Per-company config, `_sql_constraints`, secret `copy=False`, HTTPS pin, timeout bounds, `export_data` strip |
| `security/ir.model.access.csv` | Created | Manager CRUD via `llm.group_llm_manager` |
| `security/forecast_agent_security.xml` | Created | Company record rule `[('company_id', 'in', company_ids)]` |
| `models/__init__.py` | Modified | Register `forecast_agent_config` |
| `__manifest__.py` | Modified | Version `15.0.5.0.0`; security XML then CSV in `data` |
| `tests/__init__.py` | Modified | Import new tests; keep MCP `test_sold_storable_products` |

### Phase 2 (prior batch)

| File | Action | What Was Done |
|------|--------|---------------|
| `tests/test_forecast_agent_hmac.py` | Created | RED 2.1 TLS/redirect flags; GREEN 2.4 signed bytes, retry nonce, fixed body, 503/401, redaction |
| `models/forecast_agent_hmac.py` | Created | AbstractModel HMAC client: compact UTF-8 once, canonical POST string, headers, omit `assistant_id` |
| `models/__init__.py` | Modified | Register `forecast_agent_hmac` |
| `tests/__init__.py` | Modified | Import `test_forecast_agent_hmac`; keep MCP tests |

### Phase 3 (prior batch)

| File | Action | What Was Done |
|------|--------|---------------|
| `models/forecast_agent_run.py` | Created | Queue model: enqueue without HTTP, SKIP LOCKED LIMIT 5, stale recovery, cancel/retry, sanitize, `_process_run` |
| `data/ir_cron_forecast_agent.xml` | Created | 1-minute cron, `noupdate`, `numbercall=-1`, superuser worker |
| `security/ir.model.access.csv` | Modified | Manager CRUD for `tommasi.forecast.agent.run` |
| `security/forecast_agent_security.xml` | Modified | Company record rule on runs |
| `models/forecast_agent_hmac.py` | Modified | Include `response_text` in helper result dict for strict JSON + sanitize |
| `models/__init__.py` | Modified | Register `forecast_agent_run` |
| `__manifest__.py` | Modified | Add cron XML to `data` |
| `tests/__init__.py` | Modified | Import `test_forecast_agent_run`; keep MCP tests |
| `tests/test_forecast_agent_run.py` | Created | Enqueue, missing config, claim, stale, cancel, completed reject, sanitize, patched POST |

### Phase 4 (prior batch)

| File | Action | What Was Done |
|------|--------|---------------|
| `views/forecast_agent_views.xml` | Created | Odoo 15 `tree`/`form` for config and run; Run Forecast server action; read-only run diagnostics; no prompt/input; menus under `stock.menu_warehouse_report` with `groups="llm.group_llm_manager"` |
| `__manifest__.py` | Modified | Add `views/forecast_agent_views.xml` after security/cron in `data` |
| `tests/test_forecast_agent_acl.py` | Modified | Manager form sanitized + other-company/non-manager denied for runs |

Left untouched: `models/product_product.py`, `tests/test_sold_storable_products.py`, parent `devel.yaml`, MCP files.

### Phase 5 (this batch)

| File | Action | What Was Done |
|------|--------|---------------|
| `README.rst` | Modified | Added English RST Forecast agent bridge section: Chatwoot-modeled `tommasi-forecast-edge` snippet, local `http://edge-api:8080`, production HTTPS hostname, `streaming_allowed=FALSE`, secret rotation, plaintext-at-rest, clock sync, retry/idempotency. Preserved existing MCP/README dirty diffs. No credentials. |
| `tests/__init__.py` | Unchanged | Still imports `test_sold_storable_products` plus forecast-agent tests |

Parent doodba `devel.yaml` was not edited.

## Work Unit Evidence

### Phase 1 (prior)

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd /home/crisd/projects/tommasi/odoo/tommasi && invoke test --modules=tommasi_forecast_demand` → exit 0; `0 failed, 0 error(s) of 32 tests when loading database 'devel'` |
| Runtime harness command/scenario and exact result | N/A: Phase 1 has no live outbound HTTP; threat-matrix HTTPS/secret cases run in TransactionCase with patched `_https_required` and no `requests.post` |
| Rollback boundary | Revert `models/forecast_agent_config.py`, `security/`, config/acl tests, and Phase 1 edits to `__manifest__.py`, `models/__init__.py`, `tests/__init__.py`. Do not revert MCP files. |

### Phase 2 (prior)

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd /home/crisd/projects/tommasi/odoo/tommasi && invoke test --modules=tommasi_forecast_demand` → exit 0; `0 failed, 0 error(s) of 38 tests when loading database 'devel'` (32 prior + 6 HMAC) |
| Runtime harness command/scenario and exact result | N/A: no live outbound HTTP; `requests.post` is patched. Threat-matrix 301/`verify=True` exercised in `test_post_verify_true_and_301_not_followed`. |
| Rollback boundary | Revert `models/forecast_agent_hmac.py`, `tests/test_forecast_agent_hmac.py`, and the HMAC import lines in `models/__init__.py` and `tests/__init__.py`. Leave Phase 1 config/ACL and MCP files in place. |

### Phase 3 (prior)

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd /home/crisd/projects/tommasi/odoo/tommasi && invoke test --modules=tommasi_forecast_demand` → exit 0; `0 failed, 0 error(s) of 46 tests when loading database 'devel'` (38 prior + 8 run/cron) |
| Runtime harness command/scenario and exact result | N/A: no live outbound HTTP. Browser/UI enqueue never calls HTTP (`test_enqueue_does_not_call_http`). Cron commit-before-HTTP uses a side cursor (`_claim_due_runs_committed`); tests call `_claim_due_runs` / `_process_run` on the TransactionCase cursor with `requests.post` patched. |
| Rollback boundary | Revert `models/forecast_agent_run.py`, `data/ir_cron_forecast_agent.xml`, `tests/test_forecast_agent_run.py`, run ACL/rule lines, cron/run imports in `__manifest__.py` / `models/__init__.py` / `tests/__init__.py`, and the HMAC `response_text` addition. Leave Phase 1–2 config/HMAC and MCP files in place. |

### Phase 4 (prior)

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd /home/crisd/projects/tommasi/odoo/tommasi && invoke test --modules=tommasi_forecast_demand` → exit 0; `0 failed, 0 error(s) of 48 tests when loading database 'devel'` (46 prior + 2 UI ACL). Views loaded: `tommasi_forecast_demand/views/forecast_agent_views.xml`. |
| Runtime harness command/scenario and exact result | N/A: no browser E2E in this work unit (tasks table). Form arch and ACL are asserted in TransactionCase via `fields_view_get` plus search/read denials. No live outbound HTTP. |
| Rollback boundary | Revert `views/forecast_agent_views.xml`, the views line in `__manifest__.py` `data`, and the two new methods plus helpers in `tests/test_forecast_agent_acl.py`. Leave Phase 1–3 models, security, cron, and MCP files in place. |

### Phase 5 (this unit)

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd /home/crisd/projects/tommasi/odoo/tommasi && invoke test --modules=tommasi_forecast_demand` → exit 0; `0 failed, 0 error(s) of 48 tests when loading database 'devel'`; `48 post-tests in 16.17s`. MCP module `test_sold_storable_products` ran (`TestSoldStorableProducts.*`). `tests/__init__.py` still has `from . import test_sold_storable_products`. |
| Runtime harness command/scenario and exact result | N/A: Phase 5 is docs plus import verification. No live signed E2E; no browser path; parent `devel.yaml` remains unedited so `http://edge-api:8080` is not attached at runtime. |
| Rollback boundary | Revert only the new `Forecast agent bridge` section in `README.rst` (keep pre-existing MCP README dirty diffs). Do not revert Phase 1–4 models, views, tests, or MCP files. Do not touch parent `devel.yaml`. |

## Deviations from Design

None — implementation matches design. README documents the compose snippet only; parent `devel.yaml` was not edited. MCP envelope, `schema_version`, and pagination text were left as already present.

## Issues Found

None for Phase 5. Doodba still logs a Spanish `FALLO` banner during module load; unrelated to the test runner result (`0 failed, 0 error(s)`). Local Docker attach of `tommasi-forecast-edge` still needs a later doodba grant.

## Remaining Tasks

None. All phases 1–5 are complete.

## Workload / PR Boundary

- Mode: size:exception (single PR exception-ok)
- Current work unit: Phase 5 Docs and Verify Import
- Boundary: README forecast-bridge section plus invoke-test proof that MCP tests still import; no `devel.yaml` edit
- Estimated review budget impact: ~130 authored README lines this slice. Overall change remains High 400-line risk; maintainer accepted size:exception.
