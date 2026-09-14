```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:81a8a9a686d32a9536133822897ce2f3f18d70c2c60e90b30cb6bc8e8d81f679
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 4/4
scenarios: 9/9
test_command: inv test --modules=tommasi_forecast_demand --mode=update
test_exit_code: 0
test_output_hash: sha256:0cd73edbf6020209b1a909a05ad8debb9f80bd3b032e8126e3ec8544e43e2307
build_command: true
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: add-alternative-stock-visibility
**Version**: 15.0.6.0.0 (addon; published `openspec/specs/` not merged)
**Mode**: Standard (`strict_tdd: false`)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 8 |
| Tasks complete | 7 |
| Tasks incomplete | 1 |

Phase 1 tasks 1.1–1.6 and Phase 2 task 2.1 are `[x]`. Task 2.2 (`inv test` re-run) stays `[ ]` because Docker was unavailable in this verify batch. Prior apply already recorded the same command at exit 0 with 58 tests. Treated as cleanup re-run, not unimplemented work.

### Build & Tests Execution
**Build**: ➖ No addon linter/type-checker in `openspec/config.yaml` (`build_command` empty). Ran `true` (exit 0) as a no-op quality command.
```text
true
```

**Tests**: ⚠️ Cited prior run; not re-invoked this batch
```text
inv test --modules=tommasi_forecast_demand --mode=update
(from /home/crisd/projects/tommasi/odoo/tommasi, prior apply 2026-09-14)
exit 0
0 failed, 0 error(s) of 58 tests when loading database 'devel'
This verify batch did not re-invoke; docker info → DOCKER_UNAVAILABLE.
test_output_hash is SHA-256 of that cited record.
```

**Coverage**: N/A / threshold: 0% → ➖ Not available

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Alternative Products List | Empty list when none exist | `tests/test_sold_storable_products.py` > `test_alternative_products_empty_when_none` | ✅ COMPLIANT |
| Alternative Products List | No nested periods | `tests/test_sold_storable_products.py` > `test_alternative_products_sums_two_storable_variants` (item keys `id`/`name`/`skus`/`qty_available`) | ✅ COMPLIANT |
| Directional Template Set | Directional only | `tests/test_sold_storable_products.py` > `test_alternative_products_omits_reverse_m2m` | ✅ COMPLIANT |
| Directional Template Set | Skip self and duplicates | `tests/test_sold_storable_products.py` > `test_alternative_products_skips_primary_template` / `test_alternative_products_dedupes_duplicate_m2m` | ✅ COMPLIANT |
| Template Aggregation | Two storable variants | `tests/test_sold_storable_products.py` > `test_alternative_products_sums_two_storable_variants` | ✅ COMPLIANT |
| Template Aggregation | SKU-less variant counts qty | `tests/test_sold_storable_products.py` > `test_alternative_products_sku_less_variant_counts_qty` | ✅ COMPLIANT |
| Template Aggregation | Inactive or non-storable skipped | `tests/test_sold_storable_products.py` > `test_alternative_products_ignores_inactive_and_non_storable` | ✅ COMPLIANT |
| Same Frozen Stock Scope as Primary | Same helper and as_of | `tests/test_sold_storable_products.py` > `test_alternative_products_qty_uses_frozen_as_of` | ✅ COMPLIANT |
| Same Frozen Stock Scope as Primary | Batched per page | `tests/test_sold_storable_products.py` > `test_alternative_products_qty_is_batched_per_page` | ✅ COMPLIANT |

**Compliance summary**: 9/9 scenarios COMPLIANT against prior 58-test run (not re-executed this batch)

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Alternative Products List | ✅ Implemented | `_product_envelope_row` attaches list; `SCHEMA_VERSION` 1; README documents nested field |
| Directional Template Set | ✅ Implemented | `product_tmpl_id.alternative_product_ids` only |
| Template Aggregation | ✅ Implemented | One dict per template; SKU-less qty still counts |
| Same Frozen Stock Scope as Primary | ✅ Implemented | Reuses `_qty_available_at(..., as_of_dt, company_ids)`; batched per page |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Direct `website_sale` depend; version `15.0.6.0.0` | ✅ Yes | `__manifest__.py` and README Depends |
| Directional M2M only | ✅ Yes | No reverse follow |
| Template aggregation `{id, name, skus, qty_available}` | ✅ Yes | README JSON example |
| Reuse `_qty_available_at` same scope as primary | ✅ Yes | Documented; not a company-isolation fix |
| Batch per page | ✅ Yes | Design helper |
| `schema_version` 1 additive | ✅ Yes | |
| Informational consumer | ✅ Yes | README states agent must not change buy/`Stock final` |

### Issues Found
**CRITICAL**: None
**WARNING**:
1. Task 2.2 not marked complete: Docker was unavailable (`docker info` failed), so this batch did not re-run `inv test`. Prior apply evidence: 58 passed, 0 failed, 0 errors.
2. `build_command` is a no-op (`true`) because the addon `openspec/config.yaml` has an empty verify build command and no linter.
**SUGGESTION**: Re-run `inv test --modules=tommasi_forecast_demand --mode=update` when doodba Docker is available.

### Verdict
PASS WITH WARNINGS
Envelope implementation and README match the spec; runtime evidence is the prior 58-test apply run because Docker was unavailable for a re-invoke.
