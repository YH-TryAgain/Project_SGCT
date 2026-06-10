import argparse
from pathlib import Path
from typing import Iterable, List

import pandas as pd
from tqdm import tqdm

from formal_experiment import (
    DEFAULT_BASE_SEED,
    RESULTS_BASE_DIR,
    algorithm_library_for_experiment,
    build_paired_tasks,
    run_formal_task_for_experiment,
    save_formal_outputs,
    selected_experiments,
)
from Tool import SimulationAnalytics


def discover_targets(requested: Iterable[str]) -> List[str]:
    root = Path(RESULTS_BASE_DIR)
    known = {experiment["name"] for experiment in selected_experiments([])}
    requested = list(requested)
    if requested:
        return requested

    targets = []
    for raw_path in sorted(root.glob("*/raw_runs.csv")):
        name = raw_path.parent.name
        if name not in known:
            continue
        df = pd.read_csv(raw_path, usecols=["algorithm_name"])
        names = set(df["algorithm_name"])
        if "DRCT" in names or "DRCT_strict" in names:
            targets.append(name)
    return targets


def refresh_one(experiment_name: str, processes: int) -> None:
    root = Path(RESULTS_BASE_DIR)
    experiments = {experiment["name"]: experiment for experiment in selected_experiments([])}
    if experiment_name not in experiments:
        raise ValueError(f"Unknown experiment: {experiment_name}")

    experiment = experiments[experiment_name]
    output_dir = root / experiment_name
    raw_path = output_dir / "raw_runs.csv"
    old_df = pd.read_csv(raw_path)
    runs = int(old_df["run_id"].max()) + 1
    kept_df = old_df[~old_df["algorithm_name"].isin(["DRCT", "DRCT_strict"])].copy()
    old_drct = int((old_df["algorithm_name"] == "DRCT").sum())
    old_strict = int((old_df["algorithm_name"] == "DRCT_strict").sum())

    tasks = build_paired_tasks(experiment, ["DRCT"], runs, DEFAULT_BASE_SEED)
    print(
        f"{experiment_name}: old DRCT={old_drct}, old DRCT_strict={old_strict}, "
        f"new DRCT tasks={len(tasks)}, kept rows={len(kept_df)}",
        flush=True,
    )

    analytics = SimulationAnalytics()
    analytics.results_data = kept_df.to_dict("records")
    if processes <= 1:
        iterator = map(run_formal_task_for_experiment, tasks)
        for result_tuple in tqdm(iterator, total=len(tasks), desc=f"{experiment_name}:DRCT"):
            analytics.add_run_result(*result_tuple)
    else:
        import multiprocessing

        with multiprocessing.Pool(processes=processes) as pool:
            for result_tuple in tqdm(
                pool.imap_unordered(run_formal_task_for_experiment, tasks),
                total=len(tasks),
                desc=f"{experiment_name}:DRCT",
            ):
                analytics.add_run_result(*result_tuple)

    save_formal_outputs(
        analytics,
        experiment,
        str(output_dir),
        algorithm_library_for_experiment(experiment_name),
    )

    new_df = pd.read_csv(raw_path, usecols=["algorithm_name"])
    print(
        f"{experiment_name}: saved rows={len(new_df)}, "
        f"DRCT={int((new_df['algorithm_name'] == 'DRCT').sum())}, "
        f"DRCT_strict={int((new_df['algorithm_name'] == 'DRCT_strict').sum())}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace DRCT rows with DRCT_final results.")
    parser.add_argument("--experiment", action="append", default=[])
    parser.add_argument("--processes", type=int, default=2)
    args = parser.parse_args()

    for experiment_name in discover_targets(args.experiment):
        refresh_one(experiment_name, args.processes)


if __name__ == "__main__":
    main()
