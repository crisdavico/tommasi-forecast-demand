# Forecast Agent Config Specification

## Purpose

Per-company, manager-only settings for the forecast agent edge client.

## Requirements

### Requirement: One Config Row Per Company

The system MUST persist exactly one `tommasi.forecast.agent.config` per `company_id`. `company_id` SHALL be required. The system MUST NOT keep a second row for the same company, including inactive history. A saved config SHALL apply from successful save until the next successful write and MUST NOT expire by calendar date.

#### Scenario: Create company config

- GIVEN a company with no forecast agent config
- WHEN a manager creates a config for that company
- THEN the system SHALL store one row scoped to that company

#### Scenario: Duplicate company rejected

- GIVEN a company already has a config
- WHEN a manager creates another config for that company
- THEN the system MUST reject the create

### Requirement: Secrets Stay Private

`api_key` and `hmac_secret` MUST NOT be copied on duplicate, tracked, written to chatter, included in export data, or emitted in logs or error messages.

#### Scenario: Secrets persist for invoke

- GIVEN a manager saves `api_key` and `hmac_secret`
- WHEN the config is stored
- THEN the secrets SHALL be available for later signed invoke
- AND they MUST NOT appear in logs or user-visible errors

#### Scenario: Copy and export omit secrets

- GIVEN a config that stores secrets
- WHEN a user duplicates or exports the record
- THEN the copy and export MUST omit `api_key` and `hmac_secret`

### Requirement: HTTPS Except Devel Test and Test Enable

The edge URL MUST be HTTPS unless `test_enable` is active or `DOODBA_ENVIRONMENT` is `devel` or `test`.

#### Scenario: Production rejects HTTP

- GIVEN production without `test_enable`
- WHEN a manager saves a non-HTTPS edge URL
- THEN the system MUST reject the save

#### Scenario: Devel or test allows HTTP

- GIVEN `DOODBA_ENVIRONMENT` is `devel` or `test`, or `test_enable` is active
- WHEN a manager saves an HTTP edge URL
- THEN the system SHALL accept the URL

### Requirement: Store-Only Assistant Identifier

The config MAY store `assistant_id`. A config without `assistant_id` MUST remain valid. This capability MUST NOT require transmitting `assistant_id` on invoke.

#### Scenario: Optional assistant_id

- GIVEN a manager creates a config
- WHEN they omit `assistant_id`
- THEN the system SHALL accept the record

#### Scenario: Stored identifier stays on config

- GIVEN a config with `assistant_id`
- WHEN the config is saved
- THEN `assistant_id` SHALL remain on that company config only

### Requirement: Manager-Only Access

Only members of `llm.group_llm_manager` MUST create, write, or unlink config records. Members of `tommasi_forecast_demand.group_tommasi_forecast` MAY read non-secret config fields so they can queue runs from Inventory. `api_key` and `hmac_secret` MUST remain readable only by `llm.group_llm_manager`.

#### Scenario: Manager CRUD

- GIVEN a user in `llm.group_llm_manager`
- WHEN they manage config for an allowed company
- THEN they SHALL create, read, write, and unlink that company's row

#### Scenario: Forecast operator read-only

- GIVEN a user in `tommasi_forecast_demand.group_tommasi_forecast` and not in `llm.group_llm_manager`
- WHEN they search or read config
- THEN they SHALL read non-secret fields for allowed companies
- AND they MUST NOT write config
- AND they MUST NOT read `api_key` or `hmac_secret`

#### Scenario: Non-manager denied

- GIVEN a user not in `llm.group_llm_manager` or `tommasi_forecast_demand.group_tommasi_forecast`
- WHEN they search or read config
- THEN the system MUST deny access

### Requirement: Other Company Isolation

Config search and read MUST be limited to companies the user may access. Another company's config MUST NOT be returned. Listing MUST NOT introduce a pagination contract.

#### Scenario: Same-company listing

- GIVEN configs for company A and company B
- WHEN a manager scoped to company A searches
- THEN the result SHALL contain only company A's config

#### Scenario: Foreign company hidden

- GIVEN a config for company B
- WHEN a manager without access to B reads that record
- THEN the system MUST deny access or return empty
