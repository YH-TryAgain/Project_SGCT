# Formal Paper Experiments

All experiments use paired tag populations, stable seeds, and 50 runs per point.
Existing paper results are immutable. Reruns must use an output root outside
`results_paper_final/`.

## Common protocol set

The main comparisons use SGCT, DRCT, LAPCT, EMDT, DQTA, EAQ-CBB, and NLHQT(n=2).
The default ID length is 96 bits and the default tag population is 10,000 unless
an experiment varies that dimension.

## Signature-width sensitivity

- **Purpose:** evaluate the SGCT signature-width tradeoff used in Fig. 4.
- **Parameters:** `d` = 4, 6, 8, 10 with slot caps 256, 256, 256, 1024.
- **Structures:** random, fixed 80-bit prefix, dispersed, sequential, clustered.
- **Algorithms:** SGCT only.
- **Output directory:** `formal_sgct_signature_sensitivity`.
- **Paper item:** Fig. 4.
- **Read-only check:** `python formal_experiment.py --validate-paper-config`.
- **Rerun:** `python formal_experiment.py --experiment formal_sgct_signature_sensitivity --runs 50 --output-root reproduced_results`.

## Population scalability

- **Purpose:** compare identification time and communication cost as population grows.
- **Parameters:** 1,000 through 10,000 tags in increments of 1,000; 96-bit random IDs.
- **Algorithms:** the seven-paper-protocol set.
- **Output directory:** `formal_main_scalability_uniform`.
- **Paper item:** Fig. 5(a),(b).
- **Read-only check:** `python generate_paper_tables.py --check-only`.
- **Rerun:** `python formal_experiment.py --experiment formal_main_scalability_uniform --runs 50 --output-root reproduced_results`.

## ID-length sensitivity

- **Purpose:** compare response-length scaling at 10,000 tags.
- **Parameters:** 20, 40, 60, 80, 96, 128, 160, 192, and 256 bits.
- **Algorithms:** the seven-paper-protocol set.
- **Output directory:** `formal_id_length_sweep`.
- **Paper item:** Fig. 5(c),(d).
- **Read-only check:** `python generate_paper_tables.py --check-only`.
- **Rerun:** `python formal_experiment.py --experiment formal_id_length_sweep --runs 50 --output-root reproduced_results`.

The immutable raw CSV contains an additional historical 100-bit point. It is
retained for file integrity and excluded only when paper data are selected.

## Eight-structure comparison

- **Purpose:** compare the seven protocols across controlled EPC structures.
- **Parameters:** 10,000 tags, 96-bit IDs, eight structures listed in `REPRODUCIBILITY.md`.
- **Algorithms:** the seven-paper-protocol set.
- **Output directory:** `formal_experiment10_algorithm_comparison`.
- **Paper items:** Fig. 6, Table III, Table IV.
- **Read-only check:** `python compute_paper_ci.py --raw-csv results_paper_final/formal_experiment10_algorithm_comparison/raw_runs.csv --check-only`.
- **Rerun:** `python formal_experiment.py --experiment formal_experiment10_algorithm_comparison --runs 50 --output-root reproduced_results`.

Historical raw rows outside the seven-protocol paper set remain unchanged and are
filtered only during processing.

## SGCT mechanism ablation

- **Purpose:** quantify marker pruning and local short-ID assessment.
- **Parameters:** 10,000 tags, 96-bit IDs, eight controlled structures.
- **Algorithms:** SGCT, SGCT without marker pruning, SGCT without local short-ID.
- **Output directory:** `formal_experiment13_sgct_signature_grouping`.
- **Paper item:** Fig. 7.
- **Read-only check:** `python generate_paper_tables.py --check-only`.
- **Rerun:** `python formal_experiment.py --experiment formal_experiment13_sgct_signature_grouping --runs 50 --output-root reproduced_results`.

## Run every paper experiment

```bash
python formal_experiment.py --paper-only --runs 50 --output-root reproduced_results
```

Formal reruns are intentionally excluded from unit tests and continuous checks.
