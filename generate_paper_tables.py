# -*- coding: utf-8 -*-
"""Generate paper-ready tables from existing formal experiment CSV files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

from compute_paper_ci import compute_ci_table, read_csv_dedup


RESULT_ROOT = Path("results_paper_final")
OUTPUT_DIR = RESULT_ROOT / "generated_tables"

TABLE_SOURCES = {
    "table_iii_main_algorithm_comparison": RESULT_ROOT / "formal_experiment10_algorithm_comparison",
    "table_iv_paired_bootstrap_ci": RESULT_ROOT / "formal_experiment10_algorithm_comparison",
    "table_v_pruning_diagnostics": RESULT_ROOT / "formal_experiment13_sgct_signature_grouping",
    "table_vi_ablation_results": RESULT_ROOT / "formal_experiment13_sgct_signature_grouping",
    "table_vii_ber_robustness": RESULT_ROOT / "formal_sgct_ber_robustness",
}

MAIN_ALGORITHMS = ["SGCT", "DRCT", "LAPCT", "DQTA(k_max=3)", "EMDT", "NLHQT(n=2)", "EAQ_CBB", "HT_EEAC"]
ABLATION_ALGORITHMS = [
    "SGCT",
    "SGCT(no_signature_grouping)",
    "SGCT(no_local_short_id)",
    "SGCT(no_suffix_extension)",
    "SGCT(no_low_d_fallback)",
    "SGCT(d4)",
    "SGCT(d6)",
    "SGCT(d8)",
    "SGCT(d10)",
]
MAIN_METRICS = [
    "total_protocol_time_ms",
    "throughput_tags_per_sec",
    "system_efficiency",
    "total_bits",
    "avg_total_bits",
    "total_energy_uj",
]
DIAGNOSTIC_METRICS = [
    "progressive_probe_count",
    "signature_grouping_trigger_count",
    "local_short_id_trigger_count",
    "signature_groups_pruned",
    "sparse_signature_groups",
    "signature_collision_groups",
    "signature_singleton_groups",
    "low_d_fallback_count",
    "suffix_signature_trigger_count",
    "max_signature_d",
]


def load_summary(experiment_dir: Path) -> pd.DataFrame:
    path = experiment_dir / "summary_ci95.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return read_csv_dedup(path)


def metric_table(
    summary: pd.DataFrame,
    algorithms: Iterable[str],
    metrics: Iterable[str],
    scenario_filter: str | None = None,
) -> pd.DataFrame:
    df = summary[
        summary["algorithm_name"].isin(list(algorithms))
        & summary["metric"].isin(list(metrics))
    ].copy()
    if scenario_filter is not None:
        df = df[df["scenario_point"].astype(str).str.contains(scenario_filter, regex=False)]
    df["mean_ci95"] = df.apply(lambda row: f"{row['mean']:.4f} +/- {row['ci95']:.4f}", axis=1)
    return df[
        ["scenario_point", "algorithm_name", "metric", "mean", "ci95", "p95", "n", "mean_ci95"]
    ].sort_values(["scenario_point", "metric", "algorithm_name"])


def add_gamma_b(raw_path: Path, output_path: Path) -> None:
    df = read_csv_dedup(raw_path)
    required = {"throughput_tags_per_sec", "avg_total_bits"}
    if not required.issubset(df.columns):
        return
    df["gamma_B_run"] = df["throughput_tags_per_sec"] / df["avg_total_bits"].replace(0, pd.NA)
    summary = (
        df.groupby(["scenario_point", "algorithm_name"], dropna=False)
        .agg(
            gamma_B_run_mean=("gamma_B_run", "mean"),
            gamma_B_run_std=("gamma_B_run", "std"),
            throughput_mean=("throughput_tags_per_sec", "mean"),
            avg_total_bits_mean=("avg_total_bits", "mean"),
            n=("gamma_B_run", "count"),
        )
        .reset_index()
    )
    summary["gamma_B_run_ci95"] = 1.96 * summary["gamma_B_run_std"].fillna(0.0) / summary["n"].pow(0.5)
    summary["gamma_B_aggregate"] = summary["throughput_mean"] / summary["avg_total_bits_mean"]
    summary.to_csv(output_path, index=False, encoding="utf-8-sig", float_format="%.6f")


def compact_algorithm_table(raw_path: Path, algorithms: Iterable[str]) -> pd.DataFrame:
    df = read_csv_dedup(raw_path)
    df = df[df["algorithm_name"].isin(list(algorithms))].copy()
    required = {
        "algorithm_name",
        "total_protocol_time_ms",
        "throughput_tags_per_sec",
        "avg_total_bits",
        "system_efficiency",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns for compact table: {', '.join(sorted(missing))}")
    df["gamma_B_run"] = df["throughput_tags_per_sec"] / df["avg_total_bits"].replace(0, pd.NA)
    grouped = (
        df.groupby("algorithm_name", dropna=False)
        .agg(
            time_ms_mean=("total_protocol_time_ms", "mean"),
            time_ms_sd=("total_protocol_time_ms", "std"),
            throughput_mean=("throughput_tags_per_sec", "mean"),
            bits_per_tag_mean=("avg_total_bits", "mean"),
            gamma_B_run_mean=("gamma_B_run", "mean"),
            efficiency_mean=("system_efficiency", "mean"),
            n=("total_protocol_time_ms", "count"),
        )
        .reset_index()
        .rename(columns={"algorithm_name": "Algorithm"})
    )
    grouped["gamma_B_aggregate"] = grouped["throughput_mean"] / grouped["bits_per_tag_mean"]
    grouped["Rank"] = grouped["time_ms_mean"].rank(method="min").astype(int)
    return grouped[
        [
            "Algorithm",
            "time_ms_mean",
            "time_ms_sd",
            "throughput_mean",
            "bits_per_tag_mean",
            "gamma_B_aggregate",
            "gamma_B_run_mean",
            "efficiency_mean",
            "Rank",
            "n",
        ]
    ].sort_values(["Rank", "Algorithm"])


def compact_ci_table(ci: pd.DataFrame) -> pd.DataFrame:
    table = ci[
        ci["method"] == "paired_bootstrap_aggregate_mean_reduction"
    ][["baseline", "mean_reduction_pct", "ci95_low_pct", "ci95_high_pct", "n"]].copy()
    table = table.rename(
        columns={
            "baseline": "Baseline",
            "mean_reduction_pct": "Aggregate time reduction pct",
            "ci95_low_pct": "CI95 low pct",
            "ci95_high_pct": "CI95 high pct",
        }
    )
    return table.sort_values("Aggregate time reduction pct", ascending=False)


def compact_diagnostics_table(summary: pd.DataFrame) -> pd.DataFrame:
    df = summary[
        (summary["algorithm_name"] == "SGCT")
        & summary["metric"].isin(DIAGNOSTIC_METRICS)
    ].copy()
    return (
        df.groupby("metric", dropna=False)
        .agg(
            mean=("mean", "mean"),
            ci95=("ci95", "mean"),
            max_p95=("p95", "max"),
            scenario_count=("scenario_point", "nunique"),
        )
        .reset_index()
        .rename(columns={"metric": "Diagnostic"})
        .sort_values("Diagnostic")
    )


def compact_ber_table(raw_path: Path) -> pd.DataFrame:
    df = read_csv_dedup(raw_path)
    required = {"algorithm_name", "scenario_label", "ber", "total_protocol_time_ms", "avg_total_bits", "system_efficiency"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns for BER compact table: {', '.join(sorted(missing))}")
    df = df[df["algorithm_name"] == "SGCT"].copy()
    return (
        df.groupby(["scenario_label", "ber"], dropna=False)
        .agg(
            time_ms_mean=("total_protocol_time_ms", "mean"),
            time_ms_sd=("total_protocol_time_ms", "std"),
            bits_per_tag_mean=("avg_total_bits", "mean"),
            efficiency_mean=("system_efficiency", "mean"),
            n=("total_protocol_time_ms", "count"),
        )
        .reset_index()
        .sort_values(["scenario_label", "ber"])
    )


def write_table(df: pd.DataFrame, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_dir / f"{stem}.csv", index=False, encoding="utf-8-sig", float_format="%.6f")
    with open(output_dir / f"{stem}.md", "w", encoding="utf-8") as handle:
        columns = list(df.columns)
        handle.write("| " + " | ".join(columns) + " |\n")
        handle.write("| " + " | ".join(["---"] * len(columns)) + " |\n")
        for _, row in df.iterrows():
            values = [str(row[col]).replace("|", "\\|") for col in columns]
            handle.write("| " + " | ".join(values) + " |\n")


def generate_tables(
    output_dir: Path = OUTPUT_DIR,
    bootstrap_samples: int = 10000,
    compact_only: bool = False,
) -> None:
    main_summary = load_summary(TABLE_SOURCES["table_iii_main_algorithm_comparison"])
    ablation_summary = load_summary(TABLE_SOURCES["table_vi_ablation_results"])
    ber_summary = load_summary(TABLE_SOURCES["table_vii_ber_robustness"])
    main_raw = TABLE_SOURCES["table_iii_main_algorithm_comparison"] / "raw_runs.csv"
    ablation_raw = TABLE_SOURCES["table_vi_ablation_results"] / "raw_runs.csv"
    ber_raw = TABLE_SOURCES["table_vii_ber_robustness"] / "raw_runs.csv"

    if not compact_only:
        write_table(
            metric_table(main_summary, MAIN_ALGORITHMS, MAIN_METRICS),
            output_dir,
            "table_iii_main_algorithm_comparison",
        )

    ci = compute_ci_table(
        main_raw,
        baselines=["DRCT", "LAPCT", "DQTA(k_max=3)", "EMDT", "NLHQT(n=2)", "EAQ_CBB", "HT_EEAC"],
        bootstrap_samples=bootstrap_samples,
    )
    ci = ci[ci["method"] == "paired_bootstrap_aggregate_mean_reduction"].copy()
    if not compact_only:
        write_table(ci, output_dir, "table_iv_paired_bootstrap_ci")
        write_table(
            metric_table(ablation_summary, ["SGCT"], DIAGNOSTIC_METRICS),
            output_dir,
            "table_v_pruning_diagnostics",
        )
        write_table(
            metric_table(ablation_summary, ABLATION_ALGORITHMS, MAIN_METRICS),
            output_dir,
            "table_vi_ablation_results",
        )
        write_table(
            metric_table(ber_summary, ["SGCT", "DRCT", "LAPCT", "DQTA(k_max=3)", "EMDT", "NLHQT(n=2)"], MAIN_METRICS),
            output_dir,
            "table_vii_ber_robustness",
        )

    write_table(compact_algorithm_table(main_raw, MAIN_ALGORITHMS), output_dir, "paper_table_iii_compact")
    write_table(compact_ci_table(ci), output_dir, "paper_table_iv_compact")
    write_table(compact_diagnostics_table(ablation_summary), output_dir, "paper_table_v_compact")
    write_table(compact_algorithm_table(ablation_raw, ABLATION_ALGORITHMS), output_dir, "paper_table_vi_compact")
    write_table(compact_ber_table(ber_raw), output_dir, "paper_table_vii_compact")
    add_gamma_b(main_raw, output_dir / "derived_gamma_b.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paper tables from formal result CSVs.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--compact-only", action="store_true")
    args = parser.parse_args()
    generate_tables(
        output_dir=args.output_dir,
        bootstrap_samples=args.bootstrap_samples,
        compact_only=args.compact_only,
    )
    print(f"Generated paper tables in {args.output_dir}")


if __name__ == "__main__":
    main()
