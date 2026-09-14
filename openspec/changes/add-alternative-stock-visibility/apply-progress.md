# Apply Progress: add-alternative-stock-visibility

**Change**: add-alternative-stock-visibility
**Mode**: Standard (`strict_tdd: false`)
**Delivery**: single-pr (400-line risk Medium; Decision needed: No)
**Schema**: SCHEMA_VERSION remains `1`
**Batches**: (1) envelope + tests 1.1–1.6; (2) docs 2.1; 2.2 not re-run (Docker unavailable)

## Work Unit Evidence

| Unit | Focused test command and exact result | Runtime harness | Rollback boundary |
|---|---|---|---|
| 1 Envelope + tests | `inv test --modules=tommasi_forecast_demand --mode=update` from `/home/crisd/projects/tommasi/odoo/tommasi` → exit 0; `0 failed, 0 error(s) of 58 tests when loading database 'devel'` (58 post-tests; 9 new alternative-product cases plus existing suite) | Same doodba TransactionCase run | `__manifest__.py`, `models/product_product.py`, `tests/test_sold_storable_products.py` |
| 2 Docs + verify | README.rst updated this batch. `inv test` not re-invoked: `docker info` → DOCKER_UNAVAILABLE. Cited unit-1 result. | N/A — no live MCP | `README.rst` only for this unit |

Threat matrix: N/A.

## Completed Tasks

- [x] 1.1 In `__manifest__.py` add direct `website_sale` depend and bump version to `15.0.6.0.0`.
- [x] 1.2 In `models/product_product.py` add a page-batch helper: directional `product_tmpl_id.alternative_product_ids`, skip primary template, dedupe, active `type == 'product'` variants, reuse `_qty_available_at(..., as_of_dt, company_ids)`.
- [x] 1.3 Attach `alternative_products` in `_product_envelope_row`; empty list when none; no nested periods; keep `SCHEMA_VERSION` 1. Do not per-row stock queries.
- [x] 1.4 In `tests/test_sold_storable_products.py` assert empty `[]`; two-variant template sum; reverse M2M omitted; self skipped; M2M dedupe. Specs: Empty list; Two storable variants; Directional only; Skip self and duplicates.
- [x] 1.5 Same test module: SKU-less variant qty counts and empty code omitted; inactive/non-storable ignored. Specs: SKU-less variant counts qty; Inactive or non-storable skipped.
- [x] 1.6 Same test module: alternative qty uses frozen `as_of` via `_qty_available_at`; helper not called once per product row. Specs: Same helper and as_of; Batched per page.
- [x] 2.1 Update `README.rst`: nested field, directional templates, same stock scope as primary, informational consumer.

## Remaining Tasks

- [ ] 2.2 Run `inv test --modules=tommasi_forecast_demand --mode=update` from doodba. Keep importing existing MCP and forecast-agent tests in `tests/__init__.py`. Skipped this batch: Docker unavailable. Prior apply already passed 58 tests.

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `__manifest__.py` | Modified | Direct `website_sale` depend; version `15.0.6.0.0` |
| `models/product_product.py` | Modified | `_alternative_products_by_product` page-batch helper; attach `alternative_products` in `_product_envelope_row`; one extra `_qty_available_at` for alt variants |
| `tests/test_sold_storable_products.py` | Modified | Key-set includes `alternative_products`; nine new TransactionCase tests |
| `README.rst` | Modified | Nested `alternative_products`, directional templates, same `_qty_available_at` scope, informational consumer, `website_sale`, version `15.0.6.0.0` |

## Deviations from Design

None — implementation matches design. Duplicate M2M coverage seeds a duplicated id tuple in the Odoo 15 field cache because `product_alternative_rel` uses `PRIMARY KEY(src_id, dest_id)` and cannot store a second SQL row.

## Issues Found

None remaining on envelope code. Verify batch could not re-run `inv test` (Docker unavailable).

## Workload / PR Boundary

- Mode: single PR
- Current work unit: docs (2.1) complete; 2.2 pending Docker
- Boundary: manifest/helper/tests + README.rst. Do not edit sibling agent `src/` from this repo.
- Estimated review budget impact: Medium (within the 220–320 forecast; tests dominate)
