# Tasks: Add Alternative Stock Visibility

Plan mapping: todo 1 = this envelope; todos 2–3 = sibling agent; todo 4 = verify. Do not edit `openspec/changes/archive/` (read-only). Do not implement agent `src/` from this repo.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 220–320 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | single PR |
| Delivery strategy | single-pr |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Envelope + tests | single | `inv test --modules=tommasi_forecast_demand --mode=update` | doodba Odoo TransactionCase | `__manifest__.py`, `models/product_product.py`, MCP tests |
| 2 | Docs + verify | same | same invoke | N/A — no live MCP | `README.rst` |

Threat matrix N/A. Sibling agent `src/agent/forecast/odoo_fetch.py` (read-only).

## Phase 1: Envelope + tests (plan todo 1)

- [x] 1.1 In `__manifest__.py` add direct `website_sale` depend and bump version to `15.0.6.0.0`.
- [x] 1.2 In `models/product_product.py` add a page-batch helper: directional `product_tmpl_id.alternative_product_ids`, skip primary template, dedupe, active `type == 'product'` variants, reuse `_qty_available_at(..., as_of_dt, company_ids)`.
- [x] 1.3 Attach `alternative_products` in `_product_envelope_row`; empty list when none; no nested periods; keep `SCHEMA_VERSION` 1. Do not per-row stock queries.
- [x] 1.4 In `tests/test_sold_storable_products.py` assert empty `[]`; two-variant template sum; reverse M2M omitted; self skipped; M2M dedupe. Specs: Empty list; Two storable variants; Directional only; Skip self and duplicates.
- [x] 1.5 Same test module: SKU-less variant qty counts and empty code omitted; inactive/non-storable ignored. Specs: SKU-less variant counts qty; Inactive or non-storable skipped.
- [x] 1.6 Same test module: alternative qty uses frozen `as_of` via `_qty_available_at`; helper not called once per product row. Specs: Same helper and as_of; Batched per page.

## Phase 2: Docs + verify (plan todo 4)

- [x] 2.1 Update `README.rst`: nested field, directional templates, same stock scope as primary, informational consumer.
- [ ] 2.2 Run `inv test --modules=tommasi_forecast_demand --mode=update` from doodba. Keep importing existing MCP and forecast-agent tests in `tests/__init__.py`.
