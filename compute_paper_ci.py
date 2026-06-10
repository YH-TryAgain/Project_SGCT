# -*- coding: utf-8 -*-
"""Compute paired confidence intervals for paper tables.

The default CI is a paired bootstrap over scenario-run observations for the
aggregate mean reduction ratio:

    1 - mean(candidate_metric) / mean(baseline_metric)

For time-like metrics, positive values mean the candidate is lower/better.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


def read_csv_dedup(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    drop_columns = []
    for column in df.columns:
        if "." not in column:
            continue
        base, suffix = column.rsplit(".", 1)
        if suffix.isdigit() and base in df.columns and df[base].equals(df[column]):
            drop_columns.append(column)
    return df.drop(columns=drop_columns) if drop_columns else df


def paired_observations(
    df: pd.DataFrame,
    candidate: str,
    baseline: str,
    metric: str,
    group_cols: Sequence[str] = ("scenario_point", "run_id"),
) -> pd.DataFrame:
    required = set(group_cols) | {"algorithm_name", metric}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    pivot = df.pivot_table(
        index=list(group_cols),
        columns="algorithm_name",
        values=metric,
        aggfunc="mean",
    )
    if candidate not in pivot.columns or baseline not in pivot.columns:
        return pd.DataFrame(columns=[*group_cols, candidate, baseline])
    paired = pivot[[candidate, baseline]].dropna().reset_index()
    return paired


def run_level_reduction_ci(
    paired: pd.DataFrame,
    candidate: str,
    baseline: str,
) -> dict:
    reductions = 1.0 - paired[candidate] / paired[baseline]
    n = int(reductions.count())
    mean = float(reductions.mean()) if n else np.nan
    std = float(reductions.std(ddof=1)) if n > 1 else 0.0
    ci95 = float(1.96 * std / np.sqrt(n)) if n > 1 else 0.0
    return {
        "method": "paired_run_level_reduction",
        "n": n,
        "mean_reduction": mean,
        "ci95_low": mean - ci95 if n else np.nan,
        "ci95_high": mean + ci95 if n else np.nan,
        "ci95_half_width": ci95,
    }


def bootstrap_aggregate_reduction_ci(
    paired: pd.DataFrame,
    candidate: str,
    baseline: str,
    bootstrap_samples: int = 10000,
    seed: int = 20260601,
) -> dict:
    n = len(paired)
    if n == 0:
        return {
            "method": "paired_bootstrap_aggregate_mean_reduction",
            "n": 0,
            "mean_reduction": np.nan,
            "ci95_low": np.nan,
            "ci95_high": np.nan,
            "ci95_half_width": np.nan,
        }
    observed = 1.0 - float(paired[candidate].mean()) / float(paired[baseline].mean())
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, n, size=(bootstrap_samples, n))
    cand = paired[candidate].to_numpy(dtype=float)
    base = paired[baseline].to_numpy(dtype=float)
    sampled_candidate_mean = cand[indices].mean(axis=1)
    sampled_baseline_mean = base[indices].mean(axis=1)
    reductions = 1.0 - sampled_candidate_mean / sampled_baseline_mean
    low, high = np.quantile(reductions, [0.025, 0.975])
    return {
        "method": "paired_bootstrap_aggregate_mean_reduction",
        "n": n,
        "mean_reduction": observed,
        "ci95_low": float(low),
        "ci95_high": float(high),
        "ci95_half_width": float((high - low) / 2.0),
    }


def compute_ci_table(
    raw_csv: Path,
    candidate: str = "SGCT",
    baselines: Iterable[str] = ("DRCT", "LAPCT", "DQTA(k_max=3)", "EMDT", "NLHQT(n=2)"),
    metric: str = "total_protocol_time_ms",
    bootstrap_samples: int = 10000,
    seed: int = 20260601,
) -> pd.DataFrame:
    df = read_csv_dedup(raw_csv)
    rows = []
    for baseline in baselines:
        paired = paired_observations(df, candidate, baseline, metric)
        if paired.empty:
            continue
        for result in [
            run_level_reduction_ci(paired, candidate, baseline),
            bootstrap_aggregate_reduction_ci(paired, candidate, baseline, bootstrap_samples, seed),
        ]:
            rows.append(
                {
                    "raw_csv": str(raw_csv),
                    "candidate": candidate,
                    "baseline": baseline,
                    "metric": metric,
                    **result,
                    "mean_reduction_pct": 100.0 * result["mean_reduction"],
                    "ci95_low_pct": 100.0 * result["ci95_low"],
                    "ci95_high_pct": 100.0 * result["ci95_high"],
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute paired CI for formal paper results.")
    parser.add_argument("--raw-csv", type=Path, required=True)
    parser.add_argument("--candidate", default="SGCT")
    parser.add_argument("--baseline", action="append", default=[])
    parser.add_argument("--metric", default="total_protocol_time_ms")
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260601)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    baselines = args.baseline or ["DRCT", "LAPCT", "DQTA(k_max=3)", "EMDT", "NLHQT(n=2)"]
    table = compute_ci_table(
        raw_csv=args.raw_csv,
        candidate=args.candidate,
        baselines=baselines,
        metric=args.metric,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(args.output, index=False, encoding="utf-8-sig", float_format="%.6f")
    else:
        print(table.to_string(index=False))


if __name__ == "__main__":
    main()
