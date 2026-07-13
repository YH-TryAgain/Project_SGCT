"""Paired-seed experiments used by the submitted SGCT manuscript.

The two validation commands are strictly read-only. Full reruns write to
``reproduced_results`` by default and never overwrite the immutable paper CSVs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd
from tqdm import tqdm

from Framework import Tag, generate_scenario, run_simulation_with_tags
from algorithm_base_config import ALGORITHM_LIBRARY, PAPER_ALGORITHMS


DEFAULT_BASE_SEED = 20260524
DEFAULT_RUNS_PER_POINT = 50
DEFAULT_PROCESSES = 1
DEFAULT_OUTPUT_ROOT = Path("reproduced_results")

PAPER_EXPERIMENTS: Dict[str, Dict[str, Any]] = {
    "formal_sgct_signature_sensitivity": {
        "name": "formal_sgct_signature_sensitivity",
        "description": "Signature-width sensitivity across five EPC structures.",
        "scenario_config": {"TOTAL_TAGS": 10000, "BINARY_LENGTH": 96},
        "parameter_points": [
            {"scenario_label": label}
            for label in ("random", "prefix80", "dispersed", "sequential", "clustered")
        ],
        "algorithm_parameter_points": [
            {"sgct_d_target": 4, "signature_slot_cap": 256},
            {"sgct_d_target": 6, "signature_slot_cap": 256},
            {"sgct_d_target": 8, "signature_slot_cap": 256},
            {"sgct_d_target": 10, "signature_slot_cap": 1024},
        ],
        "algorithm_specific_config": {"enable_resource_monitoring": True},
    },
    "formal_main_scalability_uniform": {
        "name": "formal_main_scalability_uniform",
        "description": "Seven-protocol population scaling under uniform IDs.",
        "scenario_config": {"BINARY_LENGTH": 96, "id_distribution": "random"},
        "parameter_points": [
            {"TOTAL_TAGS": value} for value in range(1000, 10001, 1000)
        ],
        "algorithm_specific_config": {"enable_resource_monitoring": True},
    },
    "formal_id_length_sweep": {
        "name": "formal_id_length_sweep",
        "description": "Seven-protocol ID-length sensitivity at 10,000 tags.",
        "scenario_config": {"TOTAL_TAGS": 10000, "id_distribution": "random"},
        "parameter_points": [
            {"BINARY_LENGTH": value}
            for value in (20, 40, 60, 80, 96, 128, 160, 192, 256)
        ],
        "algorithm_specific_config": {"enable_resource_monitoring": True},
    },
    "formal_experiment10_algorithm_comparison": {
        "name": "formal_experiment10_algorithm_comparison",
        "description": "Seven-protocol comparison across eight EPC structures.",
        "scenario_config": {"TOTAL_TAGS": 10000, "BINARY_LENGTH": 96},
        "parameter_points": [
            {"scenario_label": label}
            for label in (
                "random",
                "prefixed",
                "prefix64",
                "prefix72",
                "prefix80",
                "dispersed",
                "sequential",
                "clustered",
            )
        ],
        "algorithm_specific_config": {"enable_resource_monitoring": True},
    },
    "formal_experiment13_sgct_signature_grouping": {
        "name": "formal_experiment13_sgct_signature_grouping",
        "description": "End-to-end SGCT marker-pruning and local short-ID ablation.",
        "scenario_config": {"TOTAL_TAGS": 10000, "BINARY_LENGTH": 96},
        "parameter_points": [
            {"scenario_label": label}
            for label in (
                "random",
                "prefixed",
                "prefix64",
                "prefix72",
                "prefix80",
                "dispersed",
                "sequential",
                "clustered",
            )
        ],
        "algorithm_specific_config": {"enable_resource_monitoring": True},
    },
}

PAPER_EXPERIMENT_RESULT_DIRS = {
    name: f"results_paper_final/{name}" for name in PAPER_EXPERIMENTS
}

SCENARIO_PRESETS = {
    "random": {"id_distribution": "random"},
    "prefixed": {"id_distribution": "prefixed", "prefix_length": 48},
    "prefix64": {"id_distribution": "prefixed", "prefix_length": 64},
    "prefix72": {"id_distribution": "prefixed", "prefix_length": 72},
    "prefix80": {"id_distribution": "prefixed", "prefix_length": 80},
    "dispersed": {"id_distribution": "dispersed"},
    "sequential": {"id_distribution": "sequential"},
    "clustered": {
        "id_distribution": "clustered",
        "cluster_count": 8,
        "cluster_prefix_length": 64,
    },
}

ABLATION_CONFIGS = {
    "SGCT(no_signature_grouping)": {"enable_signature_grouping": False},
    "SGCT(no_local_short_id)": {"enable_local_short_id": False},
}


@dataclass(frozen=True)
class FormalTask:
    experiment_name: str
    algorithm_name: str
    scenario_config: Dict[str, Any]
    algorithm_specific_config: Dict[str, Any]
    run_id: int
    point_seed: int
    algorithm_seed: int
    tag_ids: List[str]
    scenario_point: str


def stable_seed(*parts: Any) -> int:
    payload = json.dumps(parts, sort_keys=True, default=str).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:16], 16) % (2**32)


def apply_scenario_label(config: Dict[str, Any]) -> None:
    label = config.get("scenario_label")
    if label is None:
        return
    if label not in SCENARIO_PRESETS:
        raise ValueError(f"Unknown scenario label: {label}")
    config.update(SCENARIO_PRESETS[label])
    if config.get("id_distribution") == "clustered":
        clusters = max(1, int(config.get("cluster_count", 8)))
        per_cluster = math.ceil(int(config["TOTAL_TAGS"]) / clusters)
        suffix_bits = math.ceil(math.log2(max(1, per_cluster)))
        maximum = max(0, int(config["BINARY_LENGTH"]) - suffix_bits)
        config["cluster_prefix_length"] = min(
            int(config.get("cluster_prefix_length", maximum)), maximum
        )


def generate_tag_ids_for_point(config: Dict[str, Any], seed: int) -> List[str]:
    tags = generate_scenario(config, rng=random.Random(seed))
    return sorted(tag.id for tag in tags)


def _point_label(values: Dict[str, Any]) -> str:
    return ",".join(f"{key}={value}" for key, value in values.items())


def algorithms_for_experiment(
    experiment_name: str, requested: Sequence[str]
) -> List[str]:
    if experiment_name == "formal_sgct_signature_sensitivity":
        available = ["SGCT"]
    elif experiment_name == "formal_experiment13_sgct_signature_grouping":
        available = ["SGCT", *ABLATION_CONFIGS]
    else:
        available = list(PAPER_ALGORITHMS)
    if not requested:
        return available
    unknown = sorted(set(requested).difference(available))
    if unknown:
        raise ValueError(
            f"Algorithms not available for {experiment_name}: {', '.join(unknown)}"
        )
    return [name for name in available if name in requested]


def selected_experiments(
    names: Sequence[str], paper_only: bool = False
) -> List[Dict[str, Any]]:
    if paper_only and names:
        raise ValueError("--paper-only cannot be combined with --experiment")
    if paper_only:
        return list(PAPER_EXPERIMENTS.values())
    if not names:
        return []
    unknown = sorted(set(names).difference(PAPER_EXPERIMENTS))
    if unknown:
        raise ValueError(f"Unknown paper experiments: {', '.join(unknown)}")
    return [PAPER_EXPERIMENTS[name] for name in names]


def build_paired_tasks(
    experiment: Dict[str, Any],
    algorithms: Sequence[str],
    runs_per_point: int,
    base_seed: int = DEFAULT_BASE_SEED,
) -> List[FormalTask]:
    tasks: List[FormalTask] = []
    algorithm_points = experiment.get("algorithm_parameter_points", [{}])
    for point in experiment["parameter_points"]:
        scenario_config = {**experiment["scenario_config"], **point}
        apply_scenario_label(scenario_config)
        scenario_point = _point_label(point)
        for run_id in range(runs_per_point):
            point_seed = stable_seed(
                base_seed, experiment["name"], scenario_config, run_id
            )
            tag_ids = generate_tag_ids_for_point(scenario_config, point_seed)
            for algorithm_name in algorithms:
                for algorithm_point in algorithm_points:
                    config = {
                        **experiment.get("algorithm_specific_config", {}),
                        **algorithm_point,
                    }
                    task_name = algorithm_name
                    if algorithm_point:
                        task_name = algorithm_name
                    tasks.append(
                        FormalTask(
                            experiment_name=experiment["name"],
                            algorithm_name=task_name,
                            scenario_config=dict(scenario_config),
                            algorithm_specific_config=config,
                            run_id=run_id,
                            point_seed=point_seed,
                            algorithm_seed=stable_seed(
                                point_seed, algorithm_name, algorithm_point
                            ),
                            tag_ids=tag_ids,
                            scenario_point=_point_label({**point, **algorithm_point}),
                        )
                    )
    return tasks


def _algorithm_info(name: str) -> Dict[str, Any]:
    if name in ABLATION_CONFIGS:
        base = ALGORITHM_LIBRARY["SGCT"]
        return {
            **base,
            "config": {**base["config"], **ABLATION_CONFIGS[name]},
            "display_name": name,
        }
    return ALGORITHM_LIBRARY[name]


def run_formal_task(task: FormalTask):
    random.seed(task.algorithm_seed)
    np.random.seed(task.algorithm_seed)
    info = _algorithm_info(task.algorithm_name)
    config = {**info["config"], **task.algorithm_specific_config}
    if "sgct_d_target" in config:
        target = config.pop("sgct_d_target")
        config.update(
            d_target_dense=target,
            d_target_normal=target,
            signature_d_max=target,
        )
    result = run_simulation_with_tags(
        [Tag(identity) for identity in task.tag_ids], info["class"], config
    )
    return {
        **task.scenario_config,
        **task.algorithm_specific_config,
        **result,
        "experiment_name": task.experiment_name,
        "scenario_point": task.scenario_point,
        "point_seed": task.point_seed,
        "algorithm_seed": task.algorithm_seed,
        "algorithm_name": task.algorithm_name,
        "run_id": task.run_id,
    }


def _numeric_metric_columns(frame: pd.DataFrame) -> Iterable[str]:
    excluded = {
        "run_id",
        "point_seed",
        "algorithm_seed",
        "TOTAL_TAGS",
        "BINARY_LENGTH",
    }
    for column in frame.select_dtypes(include=[np.number]).columns:
        if column not in excluded:
            yield column


def calculate_summary_ci(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (point, algorithm), group in frame.groupby(
        ["scenario_point", "algorithm_name"], dropna=False
    ):
        for metric in _numeric_metric_columns(group):
            values = group[metric].dropna().astype(float)
            if values.empty:
                continue
            std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
            rows.append(
                {
                    "scenario_point": point,
                    "algorithm_name": algorithm,
                    "metric": metric,
                    "n": len(values),
                    "mean": float(values.mean()),
                    "std": std,
                    "ci95": 1.96 * std / math.sqrt(len(values)),
                    "p50": float(values.quantile(0.5)),
                    "p95": float(values.quantile(0.95)),
                    "min": float(values.min()),
                    "max": float(values.max()),
                }
            )
    return pd.DataFrame(rows)


def _assert_safe_output_root(output_root: Path) -> Path:
    root = output_root.resolve()
    immutable = [Path(path).resolve() for path in PAPER_EXPERIMENT_RESULT_DIRS.values()]
    if any(root == item or root.is_relative_to(item) or item.is_relative_to(root) for item in immutable):
        raise ValueError("Rerun output must not overlap immutable paper-result directories")
    return root


def run_experiment(
    experiment: Dict[str, Any],
    algorithms: Sequence[str],
    runs_per_point: int,
    base_seed: int,
    processes: int,
    output_root: Path,
) -> None:
    root = _assert_safe_output_root(output_root)
    output_dir = root / experiment["name"]
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = build_paired_tasks(experiment, algorithms, runs_per_point, base_seed)
    print(f"Experiment: {experiment['name']}")
    print(f"Algorithms: {', '.join(algorithms)}")
    print(f"Runs per point: {runs_per_point}; tasks: {len(tasks)}")
    started = time.time()
    if processes == 1:
        rows = [run_formal_task(task) for task in tqdm(tasks, desc=experiment["name"])]
    else:
        with multiprocessing.Pool(processes=processes) as pool:
            rows = list(
                tqdm(
                    pool.imap(run_formal_task, tasks),
                    total=len(tasks),
                    desc=experiment["name"],
                )
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "raw_runs.csv", index=False, encoding="utf-8")
    calculate_summary_ci(frame).to_csv(
        output_dir / "summary_ci95.csv", index=False, encoding="utf-8"
    )
    print(f"Saved rerun outputs to {output_dir} in {time.time() - started:.2f}s")


def validate_paper_config() -> List[str]:
    errors = []
    if len(PAPER_ALGORITHMS) != 7:
        errors.append("paper algorithm count is not seven")
    if list(ALGORITHM_LIBRARY) != PAPER_ALGORITHMS:
        errors.append("algorithm registry order differs from PAPER_ALGORITHMS")
    if set(PAPER_EXPERIMENTS) != set(PAPER_EXPERIMENT_RESULT_DIRS):
        errors.append("paper experiment/result mapping differs")
    for name, relative in PAPER_EXPERIMENT_RESULT_DIRS.items():
        directory = Path(relative)
        if not directory.is_dir():
            errors.append(f"missing result directory for {name}: {relative}")
        elif not (directory / "raw_runs.csv").is_file():
            errors.append(f"missing raw_runs.csv for {name}")
    return errors


def _list_paper_experiments() -> None:
    for name, experiment in PAPER_EXPERIMENTS.items():
        print(f"{name}\t{PAPER_EXPERIMENT_RESULT_DIRS[name]}\t{experiment['description']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", action="append", default=[])
    parser.add_argument("--algorithm", action="append", default=[])
    parser.add_argument("--paper-only", action="store_true")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS_PER_POINT)
    parser.add_argument("--base-seed", type=int, default=DEFAULT_BASE_SEED)
    parser.add_argument("--processes", type=int, default=DEFAULT_PROCESSES)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--list-paper-experiments", action="store_true")
    parser.add_argument("--validate-paper-config", action="store_true")
    args = parser.parse_args()

    if args.list_paper_experiments:
        _list_paper_experiments()
        return
    if args.validate_paper_config:
        errors = validate_paper_config()
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            raise SystemExit(1)
        print("PASS: 7 paper algorithms and 5 paper experiments are valid.")
        return

    experiments = selected_experiments(args.experiment, args.paper_only)
    if not experiments:
        parser.error("select --paper-only or at least one --experiment")
    for experiment in experiments:
        algorithms = algorithms_for_experiment(experiment["name"], args.algorithm)
        run_experiment(
            experiment,
            algorithms,
            args.runs,
            args.base_seed,
            args.processes,
            args.output_root,
        )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
