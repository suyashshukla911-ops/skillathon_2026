# V13 Change Log

## Demand allocator structural sensitivity

V13 adds a configurable demand-allocation method:

- `udyam_employment` - district Udyam employment share (default)
- `udyam_units` - district Udyam enterprise-unit share using the June 2026 Udyam district totals
- `blend` - 50/50 average of the two normalized shares

A new CLI flag is available:

`--demand-allocation-method`

The default model run writes `demand_allocator_rank_stability.csv`, which contains district rank under every allocator, rank range, top-5 flags, and a `top5_all_methods` robustness flag.

This structural allocator sensitivity is separate from the 0.35 lognormal within-allocator demand uncertainty prior.

## Scenario runs

`run_demand_scenarios.py` runs both supply modes under all three demand allocators and writes:

- `out/scenarios/proxy_udyam_employment/`
- `out/scenarios/proxy_udyam_units/`
- `out/scenarios/proxy_blend/`
- `out/scenarios/dgt_share_udyam_employment/`
- `out/scenarios/dgt_share_udyam_units/`
- `out/scenarios/dgt_share_blend/`

The policy gate remains conservative: all currently bundled public-data scenarios are `NEEDS DATA`.

## Documentation

The README, method memo, GUI judge instructions, and 10-page PDF now state that district priority is robust only when it remains high across the demand allocator alternatives.
