# Formal Experiment Protocol

This project now provides a paired-seed formal experiment runner in
`formal_experiment.py`. It is intended for paper-level comparisons where every
algorithm must process the same tag population at the same scenario point.

## Design

- Tags are generated once for each `(experiment, parameter value, run_id)`.
- The generated tag IDs are reused by every algorithm at that point.
- Each run records both `point_seed` and `algorithm_seed`.
- Raw run data and confidence intervals are saved in addition to the legacy KPI
  pivot CSV files.
- The paper-oriented default follows the revision framework: 50 paired runs per
  point, 10000 tags for main tables, and the selected reproduced baseline set.
- The main comparison table uses `SGCT`, `DRCT`, `LAPCT`,
  `DQTA(k_max=3)`, `EMDT`, `NLHQT(n=2)`, `EAQ_CBB`, and `HT_EEAC`.
  `HLCT-Base` is retained only for internal evolution and ablation studies.

## Formal Experiment Groups

- `formal_main_scalability_uniform`
  - `TOTAL_TAGS = 1000, 2000, ..., 10000`
  - `BINARY_LENGTH = 96`
  - `id_distribution = random`

- `formal_id_length_sweep`
  - `TOTAL_TAGS = 10000`
  - `BINARY_LENGTH = 20, 40, 60, 80, 96, 100, 128, 160, 192, 256`
  - `id_distribution = random`

- `formal_distribution_robustness`
  - `TOTAL_TAGS = 5000`
  - `BINARY_LENGTH = 96`
  - `id_distribution = random, prefixed, sequential, dispersed`

- `formal_common_prefix_sweep`
  - `TOTAL_TAGS = 1000, 2000, 5000, 10000`
  - `BINARY_LENGTH = 96`
  - `id_distribution = prefixed`
  - `prefix_length = 0, 16, 32, 48, 64, 72, 80`

- `formal_inspect_window_sensitivity`
  - `TOTAL_TAGS = 5000`
  - `BINARY_LENGTH = 96`
  - `id_distribution = prefixed`
  - `prefix_length = 64`
  - `inspect_window_bits = 4, 8, 16, 24, 32, 96`

- `formal_fcw_window_sensitivity`
  - validates FCW window size for FCW-SGCT
  - `TOTAL_TAGS = 5000`
  - `BINARY_LENGTH = 96`
  - `scenario_label = random, prefixed, prefix64, prefix72, prefix80,
    dispersed, sequential, clustered`
  - `fused_window_bits = 0, 2, 4, 6, 8, 12, 16`
  - `scenario_label=prefix64/72/80` maps to `id_distribution=prefixed`
    with the corresponding `prefix_length`
  - `scenario_label=clustered` maps to a batch-like multi-prefix EPC
    population
  - `enable_adaptive_fcw=False` so the sweep measures the raw window size

- `formal_ovg_stress_ablation`
  - validates the independent contribution of OVG in hard skew scenarios
  - `TOTAL_TAGS = 5000`
  - `BINARY_LENGTH = 96`
  - `scenario_label = prefix64, prefix72, prefix80, dispersed, clustered`
  - uses the OCG ablation library so `HLCT-Base`, `HLCT-Base(no_ovg)`,
    and `HLCT-Base(no_prefix_stagnation)` can be compared on p95 latency,
    fallback ratio, peak stack depth, OVG trigger count, and bit metrics

- `formal_check_gating_ablation`
  - validates the contribution of FCW and Check-Gated EPC Verification
  - `TOTAL_TAGS = 5000`
  - `BINARY_LENGTH = 96`
  - `scenario_label = random, prefixed, prefix80, dispersed, sequential,
    clustered`
  - uses the OCG ablation library, including `no_fused_check`,
    `no_check_gating`, `fixed_8bit_check`, `no_check_escalation`,
    `lock_only`, and `cbit_only`

- `formal_full_algorithm_comparison`
  - runs the extended algorithm comparison under paired seeds
  - `TOTAL_TAGS = 5000`
  - `BINARY_LENGTH = 96`
  - `scenario_label = random, prefixed, prefix64, prefix72, prefix80,
    dispersed, sequential, clustered`
  - default algorithms are loaded from `ALGORITHMS_TO_TEST`, including
    `ICT`, `SD-CGQT`, and `SUBF-CGDFSA`
  - use this experiment when the paper needs a broader comparison beyond the
    core EMDT/NLHQT/DRCT/LAPCT/DQTA baseline set

- `formal_experiment10_algorithm_comparison`
  - runs the requested paper comparison set only
  - `TOTAL_TAGS = 10000`
  - `BINARY_LENGTH = 96`
  - `scenario_label = random, prefixed, prefix64, prefix72, prefix80,
    dispersed, sequential, clustered`
  - default algorithms are `SGCT`, `DRCT`, `LAPCT`,
    `DQTA(k_max=3)`, `EMDT`, `NLHQT(n=2)`, `EAQ_CBB`, and `HT_EEAC`

- `formal_experiment11_hlct_improvement`
  - ablates the Experiment 11 HLCT improvements
  - `TOTAL_TAGS = 5000`
  - `BINARY_LENGTH = 96`
  - `scenario_label = random, prefixed, prefix80, dispersed, clustered`
  - compares `HLCT-Base`, `HLCT-Base(prev_R2)`, `HLCT-Base(no_ovg)`,
    `HLCT-Base(adaptive_fcw)`, and `HLCT-Base(no_prefix_stagnation)`

- `formal_experiment12_hlct_feedback`
  - ablates the Experiment 12 feedback-driven split improvements
  - `TOTAL_TAGS = 5000`
  - `BINARY_LENGTH = 96`
  - `scenario_label = random, prefixed, prefix64, prefix80, dispersed,
    sequential, clustered`
  - compares `HLCT-Base`, `HLCT-Base(no_adaptive_cbit)`,
    `HLCT-Base(no_multibit_fallback)`, `HLCT-Base(prev_R2)`,
    `HLCT-Base(no_ovg)`, and `HLCT-Base(adaptive_fcw)`

- `formal_experiment13_sgct_signature_grouping`
  - formal SG comparison and module ablation
  - `TOTAL_TAGS = 10000`
  - `BINARY_LENGTH = 96`
  - `scenario_label = random, prefixed, prefix64, prefix72, prefix80,
    dispersed, sequential, clustered`
  - compares `SGCT`, old `HLCT-Base`,
    `SGCT(no_signature_grouping)`,
    `SGCT(no_local_short_id)`,
    `SGCT(no_suffix_extension)`,
    `SGCT(no_low_d_fallback)`, `SGCT(d4)`,
    `SGCT(d6)`, `SGCT(d8)`, `SGCT(d10)`, `EMDT`, `NLHQT(n=2)`,
    `DRCT`, `LAPCT`, and `DQTA(k_max=3)`

- `formal_sgct_scalability`
  - SG scalability under the most important distributions
  - `TOTAL_TAGS = 1000, 2000, 3000, 5000, 7000, 10000`
  - `scenario_label = random, prefixed, clustered, sequential`
  - default algorithms are the paper baseline set including `SGCT`

- `formal_sgct_prefix_sweep`
  - SG sensitivity to common-prefix length
  - `TOTAL_TAGS = 100, 1000, 10000`
  - `prefix_length = 0, 16, 32, 48, 64, 72, 80, 88`
  - infeasible 88-bit prefix points with too many tags are filtered before
    execution because a 96-bit EPC leaves only 256 suffix IDs

- `formal_sgct_signature_sensitivity`
  - SG sensitivity to sparse signature width and slot cap
  - `scenario_label = random, prefix80, dispersed, sequential, clustered`
  - `TOTAL_TAGS = 10000`
  - `sgct_d_target = 4, 6, 8, 10`
  - `signature_slot_cap = 256, 512, 1024`

- `formal_sgct_ber_robustness`
  - SG robustness under non-zero BER
  - `TOTAL_TAGS = 10000`
  - `scenario_label = random, prefix80, clustered, dispersed, sequential`
  - `ber = 0, 1e-5, 1e-4, 1e-3`

- `formal_sgct_id_length_structured`
  - SG and baseline robustness to EPC length under structured populations
  - `TOTAL_TAGS = 10000`
  - `BINARY_LENGTH = 64, 96, 128, 160`
  - `scenario_label = random, medium-prefix, long-prefix, clustered`
  - compares `SGCT`, `NLHQT(n=2)`, `EMDT`, `DQTA(k_max=3)`, `DRCT`, and
    `LAPCT`

- `formal_sgct_energy_sensitivity`
  - SG and baseline sensitivity to alternative reader/tag/listening energy
    models
  - `TOTAL_TAGS = 10000`
  - `BINARY_LENGTH = 96`
  - `scenario_label = random, prefix80, dispersed, clustered`
  - `energy_profile = baseline, tag-expensive, reader-expensive,
    listen-expensive, balanced-high`
  - compares `SGCT`, `NLHQT(n=2)`, `EMDT`, and `DQTA(k_max=3)`

- `formal_sgct_resource_queue_cost`
  - derived from existing formal run-level data; it does not rerun
    simulations
  - summarizes reader-side resource and queue-cost indicators such as
    `peak_stack_depth`, `total_steps`, `total_slots`, verification count, and
    SG diagnostic counters with 95% confidence intervals

- `formal_extended_baseline_screen`
  - optional appendix screen with additional reproduced baselines
  - `TOTAL_TAGS = 10000`
  - default algorithms are the main comparison set plus `ICT`, `SD-CGQT`,
    and `SUBF-CGDFSA`

- `formal_sequential_scalability`
  - `TOTAL_TAGS = 1000, 2000, ..., 5000`
  - `BINARY_LENGTH = 96`
  - `id_distribution = sequential`

- `formal_ocg_ablation`
  - compares `HLCT-Base`, `HLCT-Base(no_ovg)`,
    `HLCT-Base(no_check_escalation)`, `HLCT-Base(fixed_8bit_check)`,
    `HLCT-Base(no_fused_check)`, `HLCT-Base(no_prefix_stagnation)`,
    `HLCT-Base(lock_only)`, and `HLCT-Base(cbit_only)`
  - also includes `HLCT-Base(no_check_gating)` to measure direct EPC
    response without short Check-Gated Response

## Recommended Commands

Run the full default formal suite with 50 paired runs per point. The runner
defaults to one worker process for desktop stability; use `--processes 2` only
when the machine remains responsive.

```bash
python formal_experiment.py --paper-only --runs 50 --processes 1 --resume-existing --checkpoint-interval 100
```

Use `--paper-only` for the SGCT paper suite. It runs only:
`formal_experiment10_algorithm_comparison`, `formal_sgct_scalability`,
`formal_sgct_prefix_sweep`, `formal_experiment13_sgct_signature_grouping`,
and `formal_sgct_ber_robustness`.

Run a pilot before the full suite:

```bash
python formal_experiment.py --experiment formal_main_scalability_uniform --runs 5 --algorithm HLCT-Base --algorithm DRCT
```

Run the HLCT-Base ablation:

```bash
python formal_experiment.py --experiment formal_ocg_ablation --runs 100 --processes 1
```

`--processes 1` is recommended for ablation because it uses a local variant
library rather than the default global algorithm registry.

Run the common-prefix OVG stress test:

```bash
python formal_experiment.py --experiment formal_common_prefix_sweep --runs 100
```

Run the inspect-window sensitivity test:

```bash
python formal_experiment.py --experiment formal_inspect_window_sensitivity --runs 50 --algorithm HLCT-Base
```

Run the FCW window sensitivity test:

```bash
python formal_experiment.py --experiment formal_fcw_window_sensitivity --runs 50 --algorithm HLCT-Base --processes 1
```

Run the OVG stress ablation:

```bash
python formal_experiment.py --experiment formal_ovg_stress_ablation --runs 100 --processes 1
```

Run the Check-Gating / FCW ablation:

```bash
python formal_experiment.py --experiment formal_check_gating_ablation --runs 100 --processes 1
```

Run the full extended baseline comparison:

```bash
python formal_experiment.py --experiment formal_full_algorithm_comparison --runs 100
```

Run the Experiment 10 main comparison set:

```bash
python formal_experiment.py --experiment formal_experiment10_algorithm_comparison --runs 50 --processes 1
```

Run the Experiment 11 HLCT improvement ablation:

```bash
python formal_experiment.py --experiment formal_experiment11_hlct_improvement --runs 100 --processes 1
```

Run the Experiment 12 feedback-driven HLCT ablation:

```bash
python formal_experiment.py --experiment formal_experiment12_hlct_feedback --runs 100 --processes 1
```

Run the SG formal comparison and ablation:

```bash
python formal_experiment.py --experiment formal_experiment13_sgct_signature_grouping --runs 50 --processes 1 --resume-existing --checkpoint-interval 100
```

Run the SG ablation only, including all SG module variants:

```bash
python formal_experiment.py --experiment formal_experiment13_sgct_signature_grouping --runs 50 --processes 1 --resume-existing --checkpoint-interval 100 --algorithm SGCT --algorithm HLCT-Base --algorithm "SGCT(no_signature_grouping)" --algorithm "SGCT(no_local_short_id)" --algorithm "SGCT(no_suffix_extension)" --algorithm "SGCT(no_low_d_fallback)" --algorithm "SGCT(d4)" --algorithm "SGCT(d6)" --algorithm "SGCT(d8)" --algorithm "SGCT(d10)"
```

Run the SG paper experiment family:

```bash
python formal_experiment.py --experiment formal_sgct_scalability --runs 50 --processes 1
python formal_experiment.py --experiment formal_sgct_prefix_sweep --runs 50 --processes 1
python formal_experiment.py --experiment formal_sgct_signature_sensitivity --runs 50 --algorithm SGCT --processes 1
python formal_experiment.py --experiment formal_sgct_ber_robustness --runs 50 --processes 1
python formal_experiment.py --experiment formal_sgct_id_length_structured --runs 50 --processes 1 --resume-existing --checkpoint-interval 100
python formal_experiment.py --experiment formal_sgct_energy_sensitivity --runs 50 --processes 1 --resume-existing --checkpoint-interval 100
```

Run the extended baseline comparison with additional reproduced algorithms:

```bash
python formal_experiment.py --experiment formal_extended_baseline_screen --runs 50 --processes 1
```

## Outputs

Each experiment writes to:

```text
results_paper_final/<experiment_name>/
```

Important files:

- `raw_runs.csv`: all run-level records.
- `run_manifest.csv`: seeds and run identity for reproducibility.
- `summary_ci95.csv`: mean, standard deviation, p95, and 95% confidence interval.
- `paired_significance.csv`: paired SG comparisons when `SGCT`
  and matching baselines are present.
- `<metric>.csv`: legacy mean pivot tables by algorithm.
- `<experiment_name>_plot.png`: combined KPI plot.

Communication outputs include `total_bits.csv` and `avg_total_bits.csv`, in
addition to reader/tag bit tables.

FCW-SGCT outputs also include `fcw_cache_created_count`,
`fcw_cache_hit_count`, `fcw_cache_hit_ratio`, and `inspect_collision_count`
when resource monitoring is enabled.

Experiment 9 adds OVG diagnostic outputs: `ovg_success_count`,
`post_ovg_singleton_count`, `ovg_fallback_avoid_count`,
`prefix_stag_score_trigger_count`, and `repeated_pattern_trigger_count`.
These are included in `summary_ci95.csv` when present.

Experiment 10 also exposes Adaptive FCW diagnostics: `fcw_fast_path_count`,
`fcw_width_up_count`, and `fcw_width_down_count`. Adaptive FCW is implemented
but not enabled in the formal default configuration because smoke tests showed
slightly higher total bits and mean time under the current simulator settings.

Experiment 11 changes the formal HLCT-Base default from `R_OVG=2` to
`R_OVG=1`, keeping OVG available while preventing repeated hash recovery from
becoming a long default path.

Experiment 12 adds guarded Adaptive CBIT Width and multi-bit fallback
diagnostics: `adaptive_cbit_r4_count` and `multibit_fallback_count`. The
default only uses `CBIT r=4` on clean dense-collision nodes; nodes with prior
skew, no-progress, verification-fail, OVG retry, prefix-stagnation, or repeated
collision feedback fall back to the conservative `r=3` cap. Fallback nodes can
use two collision positions instead of one when enough collision bits are
observable.

SG experiments add diagnostics for `progressive_probe_count`,
`signature_grouping_trigger_count`, `local_short_id_trigger_count`,
`signature_groups_pruned`, `sparse_signature_groups`,
`signature_collision_groups`, `signature_singleton_groups`,
`signature_marker_tag_bits`,
`low_d_fallback_count`, `suffix_signature_trigger_count`,
`hash_short_id_round_count`, `hash_short_id_split_count`,
`hash_short_id_collision_groups`, `hash_short_id_singleton_groups`,
`max_signature_d`, `epc_verification_count`, `verify_fail_count`, and
`avg_tag_responses`.

SG protocol modeling follows terminal-verification discipline: no tag is added
to `identified_tags` unless it passes an EPC verification step. Low-d fallback
and no-position fallback enqueue terminal groups for verification instead of
committing them for free. The formal default uses a bounded local short-ID
response budget for non-terminal signature children and re-enqueues unresolved
children for further observable resolution. The hash short-ID path remains
implemented for separate diagnostic runs, but it is not part of the default
formal SG ablation set because it adds measurable overhead in clustered cases.

The non-observable small-cluster guard is disabled in the formal default
configuration. It remains available as a simulator safety knob for tiny
diagnostic cases, but paper experiments should use observation-driven SG
behavior and report `small_cluster_guard_count=0`.

The signature marker accounting is split into two quantities. `signature_marker_tag_bits`
tracks the communication cost charged to tag responses, while
`signature_non_idle_marker_count` counts non-empty signature groups. This keeps the
communication model and occupancy summary separate.

For paired significance output, normal-approximation p-values are only reported
when at least five paired runs are available. Smaller pilot runs still report
means, improvement, effect direction, and win rate, but leave the approximate
p-value blank to avoid overstating statistical evidence.



