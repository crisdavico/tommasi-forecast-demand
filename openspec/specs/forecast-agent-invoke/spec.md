# Forecast Agent Invoke Specification

## Purpose

Company-scoped signed `POST /v1/agent/invoke` using stored config secrets, without sending `assistant_id` or a session.

## Requirements

### Requirement: Exact-Byte HMAC Canonical String

The system MUST compact the JSON body to UTF-8 once and MUST transmit those same bytes. The HMAC canonical string MUST be exactly `POST\n/v1/agent/invoke\n{timestamp}\n{nonce}\n{sha256_hex(body)}`, where the digest is SHA-256 of those body bytes. Credentials MUST come from the run's company config.

#### Scenario: Sign transmitted bytes

- GIVEN company config secrets and a built invoke body
- WHEN the client signs and posts
- THEN the signature SHALL cover the exact body bytes on the wire

#### Scenario: Reserialize mismatch forbidden

- GIVEN a signed body
- WHEN the client would emit JSON bytes different from those hashed
- THEN the system MUST NOT send that request

### Requirement: Headers Idempotency and Fresh Nonce

Each attempt MUST send `X-API-Key`, `X-Timestamp`, `X-Nonce`, `X-Signature`, per-run `X-Idempotency-Key`, and `X-Request-Id`. Retries MUST reuse the idempotency key and MUST use a new timestamp, nonce, and signature.

#### Scenario: First attempt headers

- GIVEN a new invoke attempt
- WHEN the request is sent
- THEN all required headers SHALL be present
- AND the idempotency key SHALL identify that run

#### Scenario: Retry reuses key not nonce

- GIVEN a retryable prior attempt for the same run
- WHEN the client retries
- THEN `X-Idempotency-Key` MUST be unchanged
- AND timestamp, nonce, and signature MUST be new

### Requirement: Fixed Stateless Sync Body

`input` MUST be the fixed trigger value with no prompt field. The JSON MUST omit `session_id`. `response_mode` MUST be `sync`. `metadata` MUST contain only `source`, `trace_id`, and `client_version`. The JSON MUST NOT include `assistant_id`.

#### Scenario: Happy invoke body

- GIVEN an enqueue from the current company config
- WHEN the client builds the body
- THEN `input` SHALL be the fixed trigger
- AND `session_id` MUST be omitted
- AND `metadata` SHALL contain only `source`, `trace_id`, and `client_version`

#### Scenario: Config assistant_id not in JSON

- GIVEN stored `assistant_id` on the company config
- WHEN the client builds invoke JSON
- THEN the body MUST NOT contain `assistant_id` or a user prompt

### Requirement: Retryable Versus Terminal Statuses

The client MUST treat HTTP 202, 429, 502, 503, 504, and transport failure as retryable. The client MUST treat HTTP 401, 403, 409, and 422 as terminal. Classification MUST NOT depend on calendar date.

#### Scenario: Retryable status

- GIVEN an invoke returns 503
- WHEN the client classifies the response
- THEN the attempt SHALL be retryable

#### Scenario: Terminal status

- GIVEN an invoke returns 401
- WHEN the client classifies the response
- THEN the attempt MUST be terminal
- AND the client MUST NOT retry that classification

### Requirement: Credential-Safe Errors

User-visible errors and logs MUST NOT include `api_key`, `hmac_secret`, or HMAC secret material.

#### Scenario: Failed invoke

- GIVEN a terminal or transport failure
- WHEN the error is recorded
- THEN the message SHALL omit secrets

#### Scenario: Logged failure

- GIVEN a retryable failure
- WHEN logs are written
- THEN logs MUST NOT contain secrets
