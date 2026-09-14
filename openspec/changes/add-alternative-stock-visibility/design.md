# Design: Add Alternative Stock Visibility

Additive nested field on `get_sold_storable_products`. Spec: `sold-storable-alternatives`. Eligibility, pagination, and `SCHEMA_VERSION = 1` stay in `models/product_product.py`. Agent consumer is a sibling apply after this ships.

## Technical Approach

After the page recordset exists, resolve directional templates, skip self, dedupe, collect active storable variants, call `_qty_available_at` once, attach lists in `_product_envelope_row`. Same `as_of_dt` and `company_ids` already used for primary live stock (`res.company.search([]).ids`). Do not "fix" company isolation.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Reverse + directional | Extra templates, non-deterministic extras | Directional `alternative_product_ids` only |
| Variant-level rows vs template aggregation | Sheet noise | One dict per template: `{id, name, skus, qty_available}` |
| New stock helper vs reuse | Scope drift vs primary | Reuse `_qty_available_at(variants, as_of_dt, company_ids)` |
| Per-row vs batch | N+1 qty reads | Batch per page |
| Schema bump vs additive | Breaks old agent | Keep `schema_version` 1 |
| Auto-install vs direct `website_sale` | Hidden field | Direct depend; bump `15.0.6.0.0` |

Published agent `Company Scope Isolation` still disagrees with this producer. This change keeps **same scope as primary live stock**.

## Data Flow

```mermaid
sequenceDiagram
  participant T as get_sold_storable_products
  participant P as page products
  participant A as alternative templates
  participant V as active storable variants
  participant Q as _qty_available_at
  participant R as _product_envelope_row
  T->>P: eligibility slice
  T->>A: mapped product_tmpl_id.alternative_product_ids
  A->>A: skip primary tmpl; dedupe
  A->>V: active type==product variants
  T->>Q: variants, as_of_dt, company_ids
  Q-->>R: per-variant frozen qty
  R-->>T: alternative_products list per row
```

**ORM / query:** one M2M read on page templates; one variant browse; one `_qty_available_at` (sudo + `to_date` + `allowed_company_ids`, same as primary). No per-row `qty_available` RPC.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `__manifest__.py` | Modify | `depends` += `website_sale`; version `15.0.6.0.0` |
| `models/product_product.py` | Modify | Batch helper; pass list into `_product_envelope_row` |
| `tests/test_sold_storable_products.py` | Modify | Empty, aggregate, directional/skip/dedupe, SKU-less, same-scope |
| `README.rst` | Modify | Nested field; informational consumer |
| Agent `src/` | Out of roots | Sibling change |

## Interfaces / Contracts

```python
SCHEMA_VERSION = 1  # unchanged

def _alternative_products_by_product(self, page, as_of_dt, company_ids):
    """Return {product.id: [ {id, name, skus, qty_available}, ... ]}."""
```

`skus`: sorted unique non-empty trimmed `default_code`. Empty list when no templates remain. Do not nest periods.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Integration | Empty, two-variant sum, reverse omitted, self skipped, M2M dedupe, SKU-less qty, inactive skipped, `to_date` freeze | `TransactionCase` `post_install,-at_install`; reuse `FROZEN_AS_OF` |
| Query volume | Not one `_qty_available_at` per product | Patch/spy helper call count vs page size |
| E2E | Live MCP | Out of scope |

`strict_tdd: false` — tests with behavior, not mandatory RED-first.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

Odoo first (old agent ignores unknown keys). Then agent (required field). Rollback agent first, Odoo second. Reinstall/upgrade pulls `website_sale`.

## Open Questions

- None — product decisions confirmed.
