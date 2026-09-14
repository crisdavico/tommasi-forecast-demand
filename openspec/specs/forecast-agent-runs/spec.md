# Forecast Agent Runs Specification

## Purpose

Queue company-scoped forecast invokes so managers enqueue without waiting on HTTP.

## Requirements

### Requirement: Enqueue Without Prompt or HTTP Wait

Run Forecast MUST create a `tommasi.forecast.agent.run` from the current company's active config without a prompt field. The user request MUST NOT wait on outbound HTTP. Missing active config MUST raise a user error.

#### Scenario: Manager enqueues

- GIVEN an active config for the current company
- WHEN a manager runs forecast
- THEN the system SHALL create a queued run
- AND the browser HTTP response MUST complete without waiting on the edge invoke

#### Scenario: Missing config

- GIVEN no active config for the current company
- WHEN a manager runs forecast
- THEN the system MUST raise a user error
- AND MUST NOT create a run

### Requirement: Run Lifecycle States

A run MUST use states `queued`, `running`, `retry`, `completed`, and `failed`. An idempotency key MUST be set at create and MUST NOT change.

#### Scenario: Success path

- GIVEN a queued run
- WHEN the worker completes a successful invoke
- THEN the run SHALL be `completed`

#### Scenario: Retry then fail

- GIVEN a running invoke classified retryable
- WHEN attempts remain
- THEN the run SHALL enter `retry`
- AND when attempts are exhausted or the status is terminal the run MUST be `failed`

### Requirement: Cron Claim and Stale Running Recovery

The scheduled worker MUST claim due `queued` and `retry` runs so two workers MUST NOT process the same run. Eligibility SHALL use next-attempt time. A `running` run that exceeds the timeout budget plus grace MUST be recovered for retry or failure per remaining attempts.

#### Scenario: Claim queued run

- GIVEN a queued run whose next attempt is due
- WHEN the worker claims it
- THEN the run SHALL become `running`
- AND another worker MUST NOT claim the same run

#### Scenario: Stale running recovered

- GIVEN a run stuck `running` beyond timeout times attempts plus grace
- WHEN the worker scans for recovery
- THEN the run SHALL be eligible for retry or failure per remaining attempts

### Requirement: Guarded Retry and Cancel

Cancel MUST apply only to `queued`, `running`, or `retry` and MUST stop further invokes, leaving the run `failed`. Operator retry MUST apply only to `failed` runs that still have an active company config. `completed` runs MUST NOT be retried or cancelled.

#### Scenario: Cancel queued

- GIVEN a `queued` or `retry` run
- WHEN a manager cancels
- THEN further invokes MUST NOT occur
- AND the run MUST become `failed`

#### Scenario: Retry completed rejected

- GIVEN a `completed` run
- WHEN a manager retries or cancels
- THEN the system MUST reject the action

### Requirement: Manager Diagnostics Isolation and Sanitized Payloads

Only `llm.group_llm_manager` MUST access runs. Forms MUST present status, output, timing, and diagnostics as read-only. Search and read MUST be company-scoped. Listing MUST NOT introduce a pagination contract. Stored payloads MUST be sanitized and MUST NOT include secrets.

#### Scenario: Manager views run

- GIVEN a run for the manager's company
- WHEN they open the form
- THEN they SHALL see read-only status, output, timing, and sanitized diagnostics
- AND stored payloads MUST omit secrets

#### Scenario: Other company and non-manager

- GIVEN a run for company B or a non-manager user
- WHEN they search or read
- THEN the system MUST deny access or return empty
