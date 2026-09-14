# Sold Storable Alternatives Specification

## Purpose

Additive `alternative_products` on each `get_sold_storable_products` product row. Eligibility, pagination, and `schema_version` `1` stay unchanged.

## Requirements

### Requirement: Alternative Products List

Each product row MUST include `alternative_products` as a list (possibly empty). `schema_version` MUST remain integer `1`. Alternatives MUST NOT nest `periods`.

Each item MUST be:

```
{
  "id": <int product.template id>,
  "name": <str template name>,
  "skus": [<str default_code of active storable variants, deterministic sorted>],
  "qty_available": <float, sum of frozen on-hand across those variants>
}
```

#### Scenario: Empty list when none exist

- GIVEN an eligible product with no directional alternative templates
- WHEN `get_sold_storable_products` returns
- THEN that row's `alternative_products` is `[]`
- AND `schema_version` is `1`

#### Scenario: No nested periods

- GIVEN one alternative template
- WHEN the item is built
- THEN it has `id`, `name`, `skus`, and `qty_available` only

### Requirement: Directional Template Set

The producer MUST follow `product.product.product_tmpl_id.alternative_product_ids` only. It MUST NOT follow reverse M2M. It MUST skip the primary product's own template. It MUST deduplicate templates if the M2M repeats.

#### Scenario: Directional only

- GIVEN template U lists the primary template as an alternative, and the primary does not list U
- WHEN the primary row is built
- THEN U is omitted

#### Scenario: Skip self and duplicates

- GIVEN the M2M contains T twice and the primary template once
- WHEN the row is built
- THEN T appears once
- AND the primary template is omitted

### Requirement: Template Aggregation

Each remaining template MUST appear once unless its frozen `qty_available` is `<= 0`; those templates MUST be omitted. `id` MUST be the `product.template` id. `name` MUST be the template name. `skus` MUST be trimmed non-empty `default_code` values of that template's active variants with `type == 'product'`, sorted deterministically. Variants without a valid non-empty trimmed `default_code` MUST still contribute `qty_available` when they are active storable, and MUST be omitted from `skus`. Inactive or non-storable variants MUST be ignored. `qty_available` MUST be the sum of frozen on-hand across those active storable variants.

#### Scenario: Two storable variants

- GIVEN template T with active storable SKU-A qty 4 and SKU-B qty 8
- WHEN the row is built
- THEN one item with sorted `skus` and `qty_available` 12.0

#### Scenario: SKU-less variant counts qty

- GIVEN an active storable variant with empty `default_code` qty 3 and coded variant qty 2
- WHEN the item is built
- THEN `qty_available` is 5.0
- AND `skus` omits the empty code

#### Scenario: Inactive or non-storable skipped

- GIVEN an inactive storable variant and an active service variant
- WHEN the item is built
- THEN neither contributes qty nor `skus`

#### Scenario: Zero on-hand omitted

- GIVEN directional templates T with frozen qty 0 and U with frozen qty 5
- WHEN the row is built
- THEN T is omitted
- AND U appears with `qty_available` 5.0

### Requirement: Same Frozen Stock Scope as Primary

Alternative `qty_available` MUST use the same frozen `as_of` and the same `_qty_available_at` company scope as primary live stock (today: all `res.company` ids). The producer MUST batch-resolve alternatives per page. It MUST NOT issue per-row stock queries.

#### Scenario: Same helper and as_of

- GIVEN primary live stock from `_qty_available_at(page, as_of_dt, company_ids)`
- WHEN alternatives are resolved
- THEN variant qty uses that helper, `as_of_dt`, and those `company_ids`

#### Scenario: Batched per page

- GIVEN a page of several products with alternatives
- WHEN the envelope is built
- THEN variant on-hand is loaded in batch, not once per product row
