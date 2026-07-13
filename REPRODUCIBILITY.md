# Reproducibility Guide

The submitted results are already present in `results_paper_final/`. Verification
and manuscript-data extraction are read-only; a full rerun is optional and may
require substantial computation.

## Paper-to-result mapping

| Paper item | Experiment/config | Existing result directory | Processing script |
| --- | --- | --- | --- |
| Fig. 4: signature-width sensitivity | SGCT; five EPC structures; `d` = 4, 6, 8, 10; caps = 256, 256, 256, 1024 | `results_paper_final/formal_sgct_signature_sensitivity` | `generate_paper_tables.py` → `fig4_signature_width_data.csv` |
| Fig. 5(a),(b): population scaling | Seven protocols; 96-bit IDs; 1,000–10,000 tags | `results_paper_final/formal_main_scalability_uniform` | `generate_paper_tables.py` → `fig5_population_scaling_data.csv` |
| Fig. 5(c),(d): ID-length scaling | Seven protocols; 10,000 tags; 20, 40, 60, 80, 96, 128, 160, 192, 256 bits | `results_paper_final/formal_id_length_sweep` | `generate_paper_tables.py` → `fig5_id_length_data.csv` |
| Fig. 6: eight EPC structures | Seven protocols; 10,000 tags; 96-bit IDs | `results_paper_final/formal_experiment10_algorithm_comparison` | `generate_paper_tables.py` → `fig6_epc_structure_data.csv` |
| Table III: average performance | Arithmetic mean across the same eight structures | `results_paper_final/formal_experiment10_algorithm_comparison` | `generate_paper_tables.py` → `table_iii_average_performance.csv` |
| Table IV: paired bootstrap intervals | 10,000 resamples over 400 matched structure/run observations | `results_paper_final/formal_experiment10_algorithm_comparison` | `compute_paper_ci.py`, called by `generate_paper_tables.py` |
| Fig. 7: end-to-end ablation | SGCT, SGCT without marker pruning, SGCT without local short-ID; eight structures | `results_paper_final/formal_experiment13_sgct_signature_grouping` | `generate_paper_tables.py` → `fig7_ablation_data.csv` |

The archived ID-length CSV also contains a historical 100-bit point, and the
archived main-comparison CSV contains historical rows outside the seven-protocol
paper set. They remain byte-for-byte unchanged and are excluded only by the
processing layer.

## Matched populations and seeds

Each paper scenario point uses 50 runs. A stable point seed generates one tag
population, which is reused by every compared protocol. Algorithm-specific seeds
are then derived from the point seed and protocol key. The main structure
comparison therefore contains 400 matched observations per protocol: eight EPC
structures multiplied by 50 runs.

The eight structures are random, fixed 48-bit prefix, fixed 64-bit prefix, fixed
72-bit prefix, fixed 80-bit prefix, dispersed, sequential, and eight clusters with
64-bit prefixes.

## Verify without rerunning

```bash
python formal_experiment.py --list-paper-experiments
python formal_experiment.py --validate-paper-config
python generate_paper_tables.py --check-only
python validate_paper_repository.py
pytest -q
```

Generate derived manuscript data outside the immutable tree:

```bash
python generate_paper_tables.py --output-dir paper_outputs
```

The validator reads `paper_results_manifest.json` and checks the relative path,
byte count, and SHA-256 of every existing file in the five paper-result
directories.

## Full rerun

```bash
python formal_experiment.py --paper-only --runs 50 --output-root reproduced_results
```

For one experiment:

```bash
python formal_experiment.py --experiment formal_experiment10_algorithm_comparison --runs 50 --output-root reproduced_results
```

The default base seed is `20260524`. Rerun outputs are intentionally separated
from the archived evidence. Do not compare CSV bytes between reruns and the
archive; compare selected metrics and configurations after accounting for the
recorded software environment.

## Evaluation scope

The study is a protocol-level evaluation with an ideal channel and static or
quasi-static tag population. Tags are committed only after terminal EPC
verification. No hardware measurements are included.
