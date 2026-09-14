# Proposal: Add Alternative Stock Visibility

## Intent

The forecast Sheet needs on-hand of website_sale alternative templates beside primary stock. Emit an additive nested list on each `get_sold_storable_products` row so the agent can show reference stock without changing buy math.

## Scope

### In Scope

- Direct `website_sale` depend; bump `__manifest__.py` version
- Directional `product_tmpl_id.alternative_product_ids` only; no reverse M2M
- One record per alternative template: `{id, name, skus, qty_available}`
- Active storable variants; empty SKUs omitted from `skus` but qty still counts
- Frozen qty via existing `_qty_available_at` at the same `as_of` and same all-company scope as primary live stock
- Batch-resolve per page; empty list when none; `schema_version` stays `1`
- TransactionCase coverage in `tests/test_sold_storable_products.py`

### Out of Scope

Eligibility/pagination rewrite; company-isolation "fix"; reverse relations; nesting periods on alternatives; agent/Sheet work; LLM; merging published `openspec/specs/`.

## Capabilities

> sdd-spec contract. Addon has no published sold-storable envelope spec.

### New Capabilities

- `sold-storable-alternatives`: additive `alternative_products` on each product row

### Modified Capabilities

- None

## Approach

After page products are known, collect directional templates, skip self, dedupe, gather active storable variants, one `_qty_available_at` call, attach lists in `_product_envelope_row`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `__manifest__.py` | Modified | `website_sale`; version `15.0.6.0.0` |
| `models/product_product.py` | Modified | Batch alternatives; reuse `_qty_available_at` |
| `tests/test_sold_storable_products.py` | Modified | Empty, aggregate, skip/dedupe, SKU-less, frozen scope |
| `README.rst` | Modified | Nested field note |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Per-row stock queries | Med | One variant browse + one `_qty_available_at` per page |
| Reverse M2M included | Med | Read `alternative_product_ids` only |
| Company-scope drift vs agent spec | Low | Same helper/ids as primary; document, do not "fix" |

## Rollback Plan

Revert addon to `15.0.5.0.0` without `website_sale` and without the nested field. `schema_version` stays 1 so old agents keep working. Roll back the agent first if it already requires the field.

## Dependencies

`website_sale` (Odoo 15 `product.template.alternative_product_ids`). Agent change `add-alternative-stock-visibility` consumes this after Odoo ships.

## Success Criteria

- [ ] Every product row has `alternative_products` (list)
- [ ] Empty / aggregate / skip-self / SKU-less / same-scope tests pass
- [ ] `schema_version` remains 1; pagination unchanged
- [ ] `inv test --modules=tommasi_forecast_demand --mode=update` passes
