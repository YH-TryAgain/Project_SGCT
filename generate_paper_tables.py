"""Build manuscript tables and figure data from immutable paper results."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd

from algorithm_base_config import DISPLAY_NAMES, PAPER_ALGORITHMS
from compute_paper_ci import compute_ci_table, read_csv_dedup


RESULT_ROOT = Path("results_paper_final")
RAW_SOURCES = {
    "signature": RESULT_ROOT / "formal_sgct_signature_sensitivity" / "raw_runs.csv",
    "population": RESULT_ROOT / "formal_main_scalability_uniform" / "raw_runs.csv",
    "id_length": RESULT_ROOT / "formal_id_length_sweep" / "raw_runs.csv",
    "comparison": RESULT_ROOT / "formal_experiment10_algorithm_comparison" / "raw_runs.csv",
    "ablation": RESULT_ROOT / "formal_experiment13_sgct_signature_grouping" / "raw_runs.csv",
}

PAPER_RAW_ALGORITHMS = {
    "SGCT": "SGCT",
    "DRCT": "DRCT",
    "LAPCT": "LAPCT",
    "EMDT": "EMDT",
    "DQTA": "DQTA(k_max=3)",
    "EAQ-CBB": "EAQ_CBB",
    "NLHQT(n=2)": "NLHQT(n=2)",
}
RAW_TO_PAPER = {raw: display for display, raw in PAPER_RAW_ALGORITHMS.items()}
PAPER_RAW_SET = set(PAPER_RAW_ALGORITHMS.values())
PAPER_ID_LENGTHS = (20, 40, 60, 80, 96, 128, 160, 192, 256)


def validate_input_sources() -> list[str]:
    errors = []
    common = {"algorithm_name", "total_protocol_time_ms", "avg_total_bits", "run_id"}
    for name, path in RAW_SOURCES.items():
        if not path.is_file():
            errors.append(f"missing {name} source: {path.as_posix()}")
            continue
        columns = set(pd.read_csv(path, nrows=0).columns)
        missing = common.difference(columns)
        if missing:
            errors.append(f"{name} source lacks columns: {', '.join(sorted(missing))}")
    return errors


def _paper_algorithms(frame: pd.DataFrame) -> pd.DataFrame:
    selected = frame[frame["algorithm_name"].isin(PAPER_RAW_SET)].copy()
    selected["Algorithm"] = selected["algorithm_name"].map(RAW_TO_PAPER)
    selected["Algorithm"] = pd.Categorical(
        selected["Algorithm"], categories=PAPER_ALGORITHMS, ordered=True
    )
    return selected


def _mean_metrics(
    frame: pd.DataFrame, group_columns: Iterable[str]
) -> pd.DataFrame:
    grouped = (
        frame.groupby(list(group_columns), observed=True, sort=False)[
            ["total_protocol_time_ms", "avg_total_bits"]
        ]
        .mean()
        .reset_index()
        .rename(
            columns={
                "total_protocol_time_ms": "Identification time (s)",
                "avg_total_bits": "Communication cost (bits/update)",
            }
        )
    )
    grouped["Identification time (s)"] /= 1000.0
    return grouped


def _fig4_data() -> pd.DataFrame:
    frame = read_csv_dedup(RAW_SOURCES["signature"])
    valid_pairs = {(4, 256), (6, 256), (8, 256), (10, 1024)}
    mask = [
        (int(d), int(cap)) in valid_pairs
        for d, cap in zip(frame["sgct_d_target"], frame["signature_slot_cap"])
    ]
    selected = frame.loc[mask].copy()
    return _mean_metrics(selected, ["sgct_d_target"]).rename(
        columns={"sgct_d_target": "d"}
    )


def _fig5_population_data() -> pd.DataFrame:
    frame = _paper_algorithms(read_csv_dedup(RAW_SOURCES["population"]))
    return _mean_metrics(frame, ["TOTAL_TAGS", "Algorithm"]).rename(
        columns={"TOTAL_TAGS": "Number of tags"}
    )


def _fig5_id_length_data() -> pd.DataFrame:
    frame = _paper_algorithms(read_csv_dedup(RAW_SOURCES["id_length"]))
    frame = frame[frame["BINARY_LENGTH"].isin(PAPER_ID_LENGTHS)]
    return _mean_metrics(frame, ["BINARY_LENGTH", "Algorithm"]).rename(
        columns={"BINARY_LENGTH": "ID length (bits)"}
    )


def _fig6_data() -> pd.DataFrame:
    frame = _paper_algorithms(read_csv_dedup(RAW_SOURCES["comparison"]))
    return _mean_metrics(frame, ["scenario_label", "Algorithm"]).rename(
        columns={"scenario_label": "EPC structure"}
    )


def _table_iii() -> pd.DataFrame:
    frame = _paper_algorithms(read_csv_dedup(RAW_SOURCES["comparison"]))
    table = _mean_metrics(frame, ["Algorithm"])
    table["Algorithm"] = table["Algorithm"].astype("object")
    order = {name: index for index, name in enumerate(PAPER_ALGORITHMS)}
    return table.sort_values("Algorithm", key=lambda values: values.map(order)).reset_index(drop=True)


def _fig7_data() -> pd.DataFrame:
    frame = read_csv_dedup(RAW_SOURCES["ablation"])
    keys = ["SGCT", "SGCT(no_signature_grouping)", "SGCT(no_local_short_id)"]
    means = frame[frame["algorithm_name"].isin(keys)].groupby("algorithm_name")[[
        "total_protocol_time_ms",
        "avg_total_bits",
    ]].mean()
    baseline = means.loc["SGCT"]
    rows = []
    for key in keys[1:]:
        rows.append(
            {
                "Variant": DISPLAY_NAMES[key],
                "Identification-time increase (%)": 100.0
                * (means.loc[key, "total_protocol_time_ms"] / baseline["total_protocol_time_ms"] - 1.0),
                "Communication-cost increase (%)": 100.0
                * (means.loc[key, "avg_total_bits"] / baseline["avg_total_bits"] - 1.0),
            }
        )
    return pd.DataFrame(rows)


def _table_iv(bootstrap_samples: int) -> pd.DataFrame:
    baselines = [PAPER_RAW_ALGORITHMS[name] for name in PAPER_ALGORITHMS if name != "SGCT"]
    frames = []
    for metric, display in (
        ("total_protocol_time_ms", "Identification time"),
        ("avg_total_bits", "Communication cost"),
    ):
        table = compute_ci_table(
            RAW_SOURCES["comparison"],
            candidate="SGCT",
            baselines=baselines,
            metric=metric,
            bootstrap_samples=bootstrap_samples,
        )
        table = table[
            table["method"] == "paired_bootstrap_aggregate_mean_reduction"
        ].copy()
        table["Baseline"] = table["baseline"].map(DISPLAY_NAMES)
        table["Metric"] = display
        frames.append(
            table[
                [
                    "Baseline",
                    "Metric",
                    "n",
                    "mean_reduction_pct",
                    "ci95_low_pct",
                    "ci95_high_pct",
                ]
            ].rename(
                columns={
                    "mean_reduction_pct": "Mean reduction (%)",
                    "ci95_low_pct": "CI95 low (%)",
                    "ci95_high_pct": "CI95 high (%)",
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def build_paper_outputs(
    output_dir: Path, bootstrap_samples: int = 10000
) -> Dict[str, pd.DataFrame]:
    errors = validate_input_sources()
    if errors:
        raise ValueError("; ".join(errors))
    outputs = {
        "fig4_signature_width_data.csv": _fig4_data(),
        "fig5_population_scaling_data.csv": _fig5_population_data(),
        "fig5_id_length_data.csv": _fig5_id_length_data(),
        "fig6_epc_structure_data.csv": _fig6_data(),
        "fig7_ablation_data.csv": _fig7_data(),
        "table_iii_average_performance.csv": _table_iii(),
        "table_iv_paired_bootstrap_ci.csv": _table_iv(bootstrap_samples),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, table in outputs.items():
        table.to_csv(output_dir / filename, index=False, encoding="utf-8", float_format="%.6f")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    args = parser.parse_args()

    errors = validate_input_sources()
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        raise SystemExit(1)
    if args.check_only:
        print("PASS: all five immutable paper-result sources are readable.")
        return
    if args.output_dir is None:
        parser.error("--output-dir is required unless --check-only is used")
    build_paper_outputs(args.output_dir, args.bootstrap_samples)
    print(f"Generated manuscript outputs in {args.output_dir}")


if __name__ == "__main__":
    main()
