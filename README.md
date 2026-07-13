# SGCT: Sparse-Grouping Collision Tree

This repository contains the protocol-level simulation code and immutable result
files for the submitted IEEE Sensors Journal manuscript **“Tag Identification
Protocol Based on Sparse Collision Signatures for Large-Scale Battery-Less RFID
Sensor Systems.”**

## Overview

SGCT performs complete identification of a static or quasi-static tag population.
It uses reader-observable slot states and collision positions, sparse-signature
marker feedback, local short-ID assessment, and terminal EPC verification. The
evaluation uses an ideal channel and a shared event-level timing and bit-accounting
model.

The repository does not claim hardware validation or native, unmodified EPC C1G2
compatibility. Its scope is protocol-level comparison under the conditions stated
in the manuscript.

## Paper comparison set

The paper-facing registry contains exactly seven protocols:

1. SGCT
2. DRCT
3. LAPCT
4. EMDT
5. DQTA
6. EAQ-CBB
7. NLHQT(n=2)

Historical names present inside immutable CSV files are translated only when data
are displayed. The CSV files themselves are never rewritten.

## Repository structure

- `SGCT.py`: proposed protocol.
- `DRCT.py`, `LAPCT.py`, `EMDT.py`, `DQTA.py`, `EAQ_CBB.py`, `NLHQT.py`: paper baselines.
- `Framework.py`: shared simulation interface and timing model.
- `Tool.py`: result aggregation utilities.
- `algorithm_base_config.py`: seven-protocol registry and display-name mapping.
- `formal_experiment.py`: paired-seed paper experiment runner and read-only configuration checks.
- `generate_paper_tables.py`: manuscript table and figure-data extraction.
- `compute_paper_ci.py`: paired confidence-interval calculation.
- `validate_paper_repository.py`: static repository and result-integrity validation.
- `results_paper_final/`: the five immutable result directories used by the paper.
- `paper_results_manifest.json`: byte counts and SHA-256 values for every immutable result file.
- `tests/`: lightweight unit, regression, configuration, and reproducibility tests.

## Environment

The repository is validated with Python 3.11.

```bash
git clone https://github.com/YH-TryAgain/Project_SGCT.git
cd Project_SGCT
python -m pip install -r requirements.txt
```

## Reproduce from existing results

These commands do not run formal simulations or modify retained result files:

```bash
python formal_experiment.py --list-paper-experiments
python formal_experiment.py --validate-paper-config
python generate_paper_tables.py --check-only
python compute_paper_ci.py --raw-csv results_paper_final/formal_experiment10_algorithm_comparison/raw_runs.csv --check-only
python validate_paper_repository.py
```

To regenerate manuscript-facing tables and plotted data in a separate directory:

```bash
python generate_paper_tables.py --output-dir paper_outputs
```

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for the complete paper-to-result
mapping.

## Run experiments

Full reruns are computationally expensive and are not required to verify the
archived paper results. Reruns use matched tag populations and write outside the
immutable result tree:

```bash
python formal_experiment.py --paper-only --runs 50 --output-root reproduced_results
```

One experiment can be selected with repeated `--experiment` and `--algorithm`
arguments. The runner rejects output paths that overlap the immutable paper-result
directories.

## Metrics

- **Identification time:** complete protocol duration from inventory start until
  every tag is terminally verified.
- **Communication cost:** total reader-command and tag-response bits divided by
  the number of verified tag updates.
- **Bit accounting:** includes reader commands and cumulative tag responses at
  each protocol event, using the shared model in `Framework.py`.

## Tests

```bash
python -m compileall -q .
pytest -q
python validate_paper_repository.py
```

The formal simulations are intentionally excluded from the test suite.

## Code and result scope

Only the retained source files and five directories under `results_paper_final/`
correspond to the submitted manuscript. The checked-in SHA-256 manifest provides
an independent post-clone integrity check.
