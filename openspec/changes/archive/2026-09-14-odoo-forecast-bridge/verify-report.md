```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:a9f6a945afef441c86a97365c6680983ce396cc55afc2dd4615a4fa631bfd165
verdict: pass
blockers: 0
critical_findings: 0
requirements: 16/16
scenarios: 32/32
test_command: cd /home/crisd/projects/tommasi/odoo/tommasi && invoke test --modules=tommasi_forecast_demand
test_exit_code: 0
test_output_hash: sha256:f4a01e93c49e2e8a17cbfb3c918ef4e9a9676439117ea5db6baae784d04b764b
build_command: python3 -m compileall -q /home/crisd/projects/tommasi/odoo/tommasi/odoo/custom/src/otros/tommasi_forecast_demand
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: odoo-forecast-bridge
**Version**: 15.0.5.0.0
**Mode**: Standard

Authoritative heading recount from the three delta specs is **16 `### Requirement:` / 32 `#### Scenario:`** (config 6/12, invoke 5/10, runs 5/10). Envelope totals use this recount.

CodeGraph MCP (`codegraph_explore` on `tommasi_forecast_demand`) was blocked by auto-review in this run. Implementation and tests were read from disk. Live signed E2E was not required. Coverage command is unavailable; threshold is 0.

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 20 |
| Tasks complete | 20 |
| Tasks incomplete | 0 |

All 20 implementation tasks in `openspec/changes/odoo-forecast-bridge/tasks.md` are checked `[x]`. `apply-progress.md` reports phases 1–5 complete, including the post-fail HMAC log/timestamp remediation. Full verification proceeded.

### Build & Tests Execution
**Build**: ✅ Passed (empty stdout+stderr; `compileall -q` success)
```text
Command: python3 -m compileall -q /home/crisd/projects/tommasi/odoo/tommasi/odoo/custom/src/otros/tommasi_forecast_demand
Exit code: 0
Output bytes: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

**Tests**: ✅ 49 passed / ❌ 0 failed / ⚠️ 0 skipped
```text
Command: cd /home/crisd/projects/tommasi/odoo/tommasi && invoke test --modules=tommasi_forecast_demand
Exit code: 0
Result: 49 post-tests in 15.68s; 0 failed, 0 error(s) of 49 tests when loading database 'devel'
MCP module TestSoldStorableProducts ran alongside forecast-agent TransactionCase tests.
Doodba prints a Spanish FALLO banner during module load; it is unrelated to the runner result.
Live signed E2E was not run (out of scope).
Covering tests that started and did not fail include TestForecastAgentHmac.test_retryable_failure_logs_omit_secrets and TestForecastAgentHmac.test_retry_reuses_idempotency_not_nonce.
test_output_hash: sha256:f4a01e93c49e2e8a17cbfb3c918ef4e9a9676439117ea5db6baae784d04b764b
```

**Coverage**: N/A / threshold: 0% → ➖ Not available

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| One Config Row Per Company | Create company config | `tests/test_forecast_agent_config.py > test_http_allowed_under_test_enable`; `tests/test_forecast_agent_acl.py > test_manager_crud_allowed` | ✅ COMPLIANT |
| One Config Row Per Company | Duplicate company rejected | `tests/test_forecast_agent_config.py > test_duplicate_company_rejected` | ✅ COMPLIANT |
| Secrets Stay Private | Secrets persist for invoke | `tests/test_forecast_agent_config.py > test_http_allowed_under_test_enable`; HMAC tests use stored secrets | ✅ COMPLIANT |
| Secrets Stay Private | Copy and export omit secrets | `tests/test_forecast_agent_config.py > test_copy_omits_secrets`; `tests/test_forecast_agent_acl.py > test_secrets_absent_from_export_data` | ✅ COMPLIANT |
| HTTPS Except Devel Test and Test Enable | Production rejects HTTP | `tests/test_forecast_agent_config.py > test_http_save_rejected_when_https_required` | ✅ COMPLIANT |
| HTTPS Except Devel Test and Test Enable | Devel or test allows HTTP | `tests/test_forecast_agent_config.py > test_http_allowed_under_test_enable` | ✅ COMPLIANT |
| Store-Only Assistant Identifier | Optional assistant_id | `tests/test_forecast_agent_config.py > test_assistant_id_is_optional` | ✅ COMPLIANT |
| Store-Only Assistant Identifier | Stored identifier stays on config | `tests/test_forecast_agent_config.py > test_assistant_id_is_optional` | ✅ COMPLIANT |
| Manager-Only Access | Manager CRUD | `tests/test_forecast_agent_acl.py > test_manager_crud_allowed` | ✅ COMPLIANT |
| Manager-Only Access | Non-manager denied | `tests/test_forecast_agent_acl.py > test_non_manager_denied` | ✅ COMPLIANT |
| Other Company Isolation | Same-company listing | `tests/test_forecast_agent_acl.py > test_other_company_isolated` | ✅ COMPLIANT |
| Other Company Isolation | Foreign company hidden | `tests/test_forecast_agent_acl.py > test_other_company_isolated` | ✅ COMPLIANT |
| Exact-Byte HMAC Canonical String | Sign transmitted bytes | `tests/test_forecast_agent_hmac.py > test_signed_bytes_match_posted_body` | ✅ COMPLIANT |
| Exact-Byte HMAC Canonical String | Reserialize mismatch forbidden | `tests/test_forecast_agent_hmac.py > test_signed_bytes_match_posted_body` | ✅ COMPLIANT |
| Headers Idempotency and Fresh Nonce | First attempt headers | `tests/test_forecast_agent_hmac.py > test_signed_bytes_match_posted_body` | ✅ COMPLIANT |
| Headers Idempotency and Fresh Nonce | Retry reuses key not nonce | `tests/test_forecast_agent_hmac.py > test_retry_reuses_idempotency_not_nonce` | ✅ COMPLIANT |
| Fixed Stateless Sync Body | Happy invoke body | `tests/test_forecast_agent_hmac.py > test_fixed_trigger_body_omits_assistant_id` | ✅ COMPLIANT |
| Fixed Stateless Sync Body | Config assistant_id not in JSON | `tests/test_forecast_agent_hmac.py > test_fixed_trigger_body_omits_assistant_id` | ✅ COMPLIANT |
| Retryable Versus Terminal Statuses | Retryable status | `tests/test_forecast_agent_hmac.py > test_503_retryable_versus_401_terminal`; `tests/test_forecast_agent_run.py > test_process_run_patched_post` | ✅ COMPLIANT |
| Retryable Versus Terminal Statuses | Terminal status | `tests/test_forecast_agent_hmac.py > test_503_retryable_versus_401_terminal`; `tests/test_forecast_agent_run.py > test_process_run_patched_post` | ✅ COMPLIANT |
| Credential-Safe Errors | Failed invoke | `tests/test_forecast_agent_hmac.py > test_errors_omit_secrets` | ✅ COMPLIANT |
| Credential-Safe Errors | Logged failure | `tests/test_forecast_agent_hmac.py > test_retryable_failure_logs_omit_secrets` | ✅ COMPLIANT |
| Enqueue Without Prompt or HTTP Wait | Manager enqueues | `tests/test_forecast_agent_run.py > test_enqueue_does_not_call_http` | ✅ COMPLIANT |
| Enqueue Without Prompt or HTTP Wait | Missing config | `tests/test_forecast_agent_run.py > test_missing_config_raises_user_error` | ✅ COMPLIANT |
| Run Lifecycle States | Success path | `tests/test_forecast_agent_run.py > test_process_run_patched_post` | ✅ COMPLIANT |
| Run Lifecycle States | Retry then fail | `tests/test_forecast_agent_run.py > test_process_run_patched_post`; `test_stale_running_recovered` | ✅ COMPLIANT |
| Cron Claim and Stale Running Recovery | Claim queued run | `tests/test_forecast_agent_run.py > test_claim_queued_run` | ✅ COMPLIANT |
| Cron Claim and Stale Running Recovery | Stale running recovered | `tests/test_forecast_agent_run.py > test_stale_running_recovered` | ✅ COMPLIANT |
| Guarded Retry and Cancel | Cancel queued | `tests/test_forecast_agent_run.py > test_cancel_queued` | ✅ COMPLIANT |
| Guarded Retry and Cancel | Retry completed rejected | `tests/test_forecast_agent_run.py > test_reject_completed_retry_and_cancel` | ✅ COMPLIANT |
| Manager Diagnostics Isolation and Sanitized Payloads | Manager views run | `tests/test_forecast_agent_acl.py > test_manager_run_form_sanitized`; `tests/test_forecast_agent_run.py > test_sanitize_payloads` | ✅ COMPLIANT |
| Manager Diagnostics Isolation and Sanitized Payloads | Other company and non-manager | `tests/test_forecast_agent_acl.py > test_run_other_company_and_non_manager_denied` | ✅ COMPLIANT |

**Compliance summary**: 32/32 scenarios compliant (32 COMPLIANT, 0 PARTIAL, 0 UNTESTED, 0 FAILING)

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| One Config Row Per Company | ✅ Implemented | `UNIQUE(company_id)` plus create/write guards; no inactive-history rows |
| Secrets Stay Private | ✅ Implemented | `copy=False`; `export_data` blanks secrets; no `mail.thread`; HMAC `_redact` on errors and constant transport/HTTP log lines |
| HTTPS Except Devel Test and Test Enable | ✅ Implemented | HTTPS unless `test_enable` or `DOODBA_ENVIRONMENT` in `devel`/`test`; userinfo rejected |
| Store-Only Assistant Identifier | ✅ Implemented | Optional Char; invoke payload omits `assistant_id` |
| Manager-Only Access | ✅ Implemented | ACL `llm.group_llm_manager` CRUD; menus/actions grouped |
| Other Company Isolation | ✅ Implemented | `ir.rule` `[('company_id','in',company_ids)]`; no pagination contract |
| Exact-Byte HMAC Canonical String | ✅ Implemented | Compact UTF-8 once; `data=body`; canonical `POST\n/v1/agent/invoke\n...` |
| Headers Idempotency and Fresh Nonce | ✅ Implemented | New nonce/signature/request-id per attempt; retry test pins distinct unix `X-Timestamp` via patched `time.time` |
| Fixed Stateless Sync Body | ✅ Implemented | Fixed `Run demand forecast.`; omit `session_id`; metadata only source/trace_id/client_version |
| Retryable Versus Terminal Statuses | ✅ Implemented | Retry 202/429/502/503/504/transport; other statuses including 401/403/409/422 terminal |
| Credential-Safe Errors | ✅ Implemented | Errors redact secrets; non-200 logs `Forecast agent HTTP %s` (status only); transport logs a constant string; covering log test passed |
| Enqueue Without Prompt or HTTP Wait | ✅ Implemented | `action_run_forecast` inserts queued run; no `requests.post` |
| Run Lifecycle States | ✅ Implemented | queued/running/retry/completed/failed; idempotency key set at create and write-protected |
| Cron Claim and Stale Running Recovery | ✅ Implemented | `FOR UPDATE SKIP LOCKED LIMIT 5`; stale `read_timeout+60s` as transport failure |
| Guarded Retry and Cancel | ✅ Implemented | Cancel queued/running/retry → failed; retry only failed with active config; completed rejected |
| Manager Diagnostics Isolation and Sanitized Payloads | ✅ Implemented | Manager ACL + company rule; form readonly diagnostics; `_sanitize_text` |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Run + `ir.cron` SKIP LOCKED, no `queue_job` | ✅ Yes | Side cursor `_claim_due_runs_committed`; tests use in-memory `_claim_due_runs` / `_process_run` |
| README compose snippet; no parent `devel.yaml` | ✅ Yes | `tommasi-forecast-edge` / `streaming_allowed=FALSE` / rotation documented |
| Store-only `assistant_id`; unique `company_id` | ✅ Yes | |
| Odoo 15 APIs (`_sql_constraints`, `tree`) | ✅ Yes | No `privilege_id` / `@api.private` / `models.Constraint` |
| Manifest `15.0.5.0.0`; MCP/`schema_version`/pagination unchanged | ✅ Yes | `tests/__init__.py` still imports MCP tests; MCP cases ran in this suite |
| Menu `stock.menu_warehouse_report` | ✅ Yes | Asserted in `test_manager_run_form_sanitized` |
| `verify=True`, `allow_redirects=False`, compact JSON once | ✅ Yes | |
| 429 MAY honor `Retry-After` | ⚠️ No | Exponential backoff only; allowed by MAY, not a spec break |

### Issues Found
**CRITICAL**: None
**WARNING**: None
**SUGGESTION**:
- Design optional `Retry-After` on 429 is unimplemented; bounded exponential backoff is used instead.
- CodeGraph MCP was blocked in this run; re-index remains a maintainer choice (not performed here).

### Verdict
PASS
32/32 scenarios have passing covering tests; this executor's invoke suite was 0 failed of 49 tests and compileall produced empty success output.
