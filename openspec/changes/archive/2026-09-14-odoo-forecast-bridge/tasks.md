# Tasks: Odoo Forecast Agent Bridge

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 900–1400 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | single PR (size-exception) |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: size-exception
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Config + ACL | single (size-exception) | invoke test --modules=tommasi_forecast_demand | N/A: mock HTTP | config, security, tests |
| 2 | HMAC client | same | same | same | HMAC helper + tests |
| 3 | Run + cron | same | same | same | run, cron, tests |
| 4 | UI + README | same | same | N/A: no browser E2E | views, README |

## Phase 1: Config and Security

- [x] 1.1 RED `tests/test_forecast_agent_config.py`: HTTP save rejected when HTTPS required; HTTP allowed under `test_enable`.
- [x] 1.2 RED `tests/test_forecast_agent_acl.py`: secrets absent from `UserError`, `export_data`, and logs.
- [x] 1.3 Create `models/forecast_agent_config.py`: unique `company_id` `_sql_constraints`; `copy=False` secrets; optional `assistant_id`; HTTPS unless `test_enable` or DOODBA_ENVIRONMENT devel/test; timeout bounds.
- [x] 1.4 Create `security/ir.model.access.csv` and `security/forecast_agent_security.xml`: `llm.group_llm_manager` CRUD; company rules.
- [x] 1.5 Register config in `models/__init__.py`; add security to `__manifest__.py` data; bump 15.0.5.0.0.
- [x] 1.6 GREEN unique reject, optional `assistant_id`, copy omits secrets, manager CRUD vs deny, company isolation in those tests.
- [x] 1.7 Import new tests in `tests/__init__.py`; keep importing existing MCP tests.

## Phase 2: HMAC Client

- [x] 2.1 RED `tests/test_forecast_agent_hmac.py`: `verify=True`; `allow_redirects=False` on mock 301.
- [x] 2.2 Create `models/forecast_agent_hmac.py` AbstractModel `_` helpers: compact UTF-8 once; canonical POST invoke HMAC string; headers; omit `assistant_id`; timeout=(connect,read).
- [x] 2.3 Register HMAC in `models/__init__.py`.
- [x] 2.4 Tests in `tests/test_forecast_agent_hmac.py`: signed bytes; retry reuses idempotency not nonce; fixed body; 503 retry / 401 terminal; errors omit secrets.

## Phase 3: Run and Cron

- [x] 3.1 Create `models/forecast_agent_run.py`: enqueue without HTTP; five states; SKIP LOCKED LIMIT 5; stale running; cancel/retry; sanitize payloads.
- [x] 3.2 Create `data/ir_cron_forecast_agent.xml` (1 min, `noupdate`, `numbercall=-1`); add to `__manifest__.py`; register run in `models/__init__.py`.
- [x] 3.3 Extend `security/ir.model.access.csv` and `security/forecast_agent_security.xml` for run CRUD and company rules.
- [x] 3.4 Tests in `tests/test_forecast_agent_run.py`: enqueue no HTTP; missing config `UserError`; claim; stale; cancel; reject completed; sanitize; `_process_run` patched POST.

## Phase 4: Inventory UI

- [x] 4.1 Create `views/forecast_agent_views.xml`: Odoo 15 `tree`/`form`; no prompt; Run Forecast; read-only diagnostics; menu `stock.menu_warehouse_report` fallback `stock.menu_stock_root`; group `llm.group_llm_manager`.
- [x] 4.2 Add views to `__manifest__.py` data.
- [x] 4.3 Tests in `tests/test_forecast_agent_acl.py`: manager form sanitized; other company/non-manager denied.

## Phase 5: Docs and Verify Import

- [x] 5.1 Update `README.rst`: tommasi-forecast-edge snippet, `streaming_allowed=FALSE`, secret rotation; do not edit parent doodba devel.yaml.
- [x] 5.2 Confirm `tests/__init__.py` still imports MCP tests; prove with invoke test --modules=tommasi_forecast_demand from doodba parent.
