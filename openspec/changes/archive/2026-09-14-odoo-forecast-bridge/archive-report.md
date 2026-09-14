# Archive Report: odoo-forecast-bridge

**Change**: odoo-forecast-bridge  
**Archived on**: 2026-09-14  
**Artifact store**: OpenSpec only (Engram MCP was unavailable; no observation IDs)  
**Delivery strategy**: `exception-ok` (size-exception; already applied; not reopened)  
**Phase at close**: archive  

## Final State at Close

The change is complete. All **20/20** implementation tasks in `tasks.md` are checked `[x]` (phases 1–5). Independent verification **passed**: **16/16** requirements, **32/32** scenarios, and `invoke test --modules=tommasi_forecast_demand` reported **0 failed, 0 error(s) of 49 tests**. There are **no CRITICAL** findings.

This report describes the state **at close**. Intermediate snapshots (`apply-progress.md`, `verify-report.md`) remain historical records of earlier moments in the cycle.

## Verification History (historical, then final)

The archived `verify-report.md` is the **passing** report (verdict `pass`, `critical_findings: 0`, requirements `16/16`, scenarios `32/32`).

Earlier in the cycle, an independent verify **failed once** because a logged-failure scenario was untested. That failure is not the close state. The subsequent fix landed in product HMAC logging and tests:

- Non-200 HMAC responses log only `Forecast agent HTTP {status}` (no secrets).
- `test_retryable_failure_logs_omit_secrets` was added.
- The retry test asserts a fresh `X-Timestamp` on the retry attempt.

Re-verify then passed and is the terminal verification evidence. Cite `verify-report.md` in this archive folder as the passing close report, and as historical context that an earlier fail was remediated before archive.

## Spec Sync

Main specs did not exist (`openspec/specs/` contained only `.gitkeep`). Each delta was a full spec and was copied mechanically into a new main spec (no `sdd-archive-compose`; no canonical main spec to merge into).

`openspec/config.yaml` `rules.archive` requires a warning before merging destructive or breaking contract deltas. This archive is **ADDED-only** for three new domains. No existing main-spec requirements were modified, removed, or renamed. The merge is not destructive.

| Domain | Action | Requirements created |
|--------|--------|----------------------|
| forecast-agent-config | Created main spec | 6 (One Config Row Per Company; Secrets Stay Private; HTTPS Except Devel Test and Test Enable; Store-Only Assistant Identifier; Manager-Only Access; Other Company Isolation) |
| forecast-agent-invoke | Created main spec | 5 (Exact-Byte HMAC Canonical String; Headers Idempotency and Fresh Nonce; Fixed Stateless Sync Body; Retryable Versus Terminal Statuses; Credential-Safe Errors) |
| forecast-agent-runs | Created main spec | 5 (Enqueue Without Prompt or HTTP Wait; Run Lifecycle States; Cron Claim and Stale Running Recovery; Guarded Retry and Cancel; Manager Diagnostics Isolation and Sanitized Payloads) |

## OpenSpec Locators

No Engram observation IDs. Filesystem locators at close:

**Archived change** (`openspec/changes/archive/2026-09-14-odoo-forecast-bridge/`):

- `proposal.md`
- `specs/forecast-agent-config/spec.md`
- `specs/forecast-agent-invoke/spec.md`
- `specs/forecast-agent-runs/spec.md`
- `design.md`
- `tasks.md`
- `apply-progress.md`
- `verify-report.md`
- `state.yaml`
- `archive-report.md` (this file)

**Main specs (source of truth after archive)**:

- `openspec/specs/forecast-agent-config/spec.md`
- `openspec/specs/forecast-agent-invoke/spec.md`
- `openspec/specs/forecast-agent-runs/spec.md`

## Scope Notes at Close

- **Size-exception delivery**: Review-budget risk was High; chained PRs were recommended; the accepted strategy was `exception-ok` / size-exception as a single delivery. That decision was already applied and was not reopened at archive.
- **doodba `devel.yaml`**: Not edited. README documents a tommasi-forecast-edge snippet only. Parent doodba `devel.yaml` remained outside this change.
- **Live signed E2E**: Out of scope. Suite close used mock HTTP; live signed end-to-end was not required.
- **Existing MCP demand tool**: Left as pre-existing dirty work, not part of this change. MCP tests continued to run alongside the new forecast-agent TransactionCase tests.

## SDD Cycle

The change has been planned, implemented, verified, and archived. Main specs now reflect the shipped forecast-agent config, invoke, and run behavior.
