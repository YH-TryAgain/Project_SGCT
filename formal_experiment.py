# -*- coding: utf-8 -*-
"""Paired-seed formal experiments for HLCT-Base comparisons."""

import argparse
import hashlib
import itertools
import json
import math
import multiprocessing
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd
from tqdm import tqdm

from Framework import Tag, generate_scenario, run_simulation_with_tags
from Tool import SimulationAnalytics
from algorithm_base_config import ALGORITHM_LIBRARY, ALGORITHMS_TO_TEST


RESULTS_BASE_DIR = "results_paper_final"
DEFAULT_BASE_SEED = 20260524
DEFAULT_RUNS_PER_POINT = 50
DEFAULT_PROCESSES = 1
PRIMARY_SG_ALGORITHM = "SGCT"
FORMAL_PAPER_EXPERIMENTS = [
    "formal_experiment10_algorithm_comparison",
    "formal_sgct_scalability",
    "formal_sgct_prefix_sweep",
    "formal_experiment13_sgct_signature_grouping",
    "formal_sgct_ber_robustness",
]
PAPER_BASELINE_ALGORITHMS = [
    PRIMARY_SG_ALGORITHM,
    "DRCT",
    "LAPCT",
    "DQTA(k_max=3)",
    "EMDT",
    "NLHQT(n=2)",
    "EAQ_CBB",
    "HT_EEAC",
]
EXTENDED_COMPARISON_ALGORITHMS = [
    *PAPER_BASELINE_ALGORITHMS,
    "ICT",
    "SD-CGQT",
    "SUBF-CGDFSA",
]
EXPERIMENT10_ALGORITHMS = [
    PRIMARY_SG_ALGORITHM,
    "DRCT",
    "LAPCT",
    "DQTA(k_max=3)",
    "EMDT",
    "NLHQT(n=2)",
    "EAQ_CBB",
    "HT_EEAC",
]
ENERGY_PROFILES = {
    "baseline": {
        "reader_tx_energy_per_bit_nj": 2.0,
        "tag_tx_energy_per_bit_nj": 0.5,
        "tag_listening_energy_per_us_nj": 0.1,
    },
    "tag-expensive": {
        "reader_tx_energy_per_bit_nj": 2.0,
        "tag_tx_energy_per_bit_nj": 1.0,
        "tag_listening_energy_per_us_nj": 0.1,
    },
    "reader-expensive": {
        "reader_tx_energy_per_bit_nj": 4.0,
        "tag_tx_energy_per_bit_nj": 0.5,
        "tag_listening_energy_per_us_nj": 0.1,
    },
    "listen-expensive": {
        "reader_tx_energy_per_bit_nj": 2.0,
        "tag_tx_energy_per_bit_nj": 0.5,
        "tag_listening_energy_per_us_nj": 0.2,
    },
    "balanced-high": {
        "reader_tx_energy_per_bit_nj": 3.0,
        "tag_tx_energy_per_bit_nj": 1.0,
        "tag_listening_energy_per_us_nj": 0.2,
    },
}


SCENARIO_PRESETS = {
    "random": {"id_distribution": "random"},
    "prefixed": {"id_distribution": "prefixed", "prefix_length": 48},
    "sequential": {"id_distribution": "sequential"},
    "dispersed": {"id_distribution": "dispersed"},
    "prefix64": {"id_distribution": "prefixed", "prefix_length": 64},
    "prefix72": {"id_distribution": "prefixed", "prefix_length": 72},
    "prefix80": {"id_distribution": "prefixed", "prefix_length": 80},
    "clustered": {"id_distribution": "clustered", "cluster_count": 8, "cluster_prefix_length": 64},
    "medium-prefix": {"id_distribution": "prefixed", "prefix_ratio": 0.5},
    "long-prefix": {"id_distribution": "prefixed", "prefix_ratio": 0.8},
}


FORMAL_EXPERIMENTS = [
    {
        "name": "formal_main_scalability_uniform",
        "description": "Main scalability comparison under uniform random IDs.",
        "varying_param_key": "TOTAL_TAGS",
        "varying_param_values": list(np.linspace(1000, 10000, 10, dtype=int)),
        "scenario_config": {
            "BINARY_LENGTH": 96,
            "id_distribution": "random",
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_id_length_sweep",
        "description": "Sensitivity to tag ID length.",
        "varying_param_key": "BINARY_LENGTH",
        "varying_param_values": [20, 40, 60, 80, 96, 100, 128, 160, 192, 256],
        "scenario_config": {
            "TOTAL_TAGS": 10000,
            "id_distribution": "random",
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_distribution_robustness",
        "description": "Robustness under representative ID distributions.",
        "varying_param_key": "id_distribution",
        "varying_param_values": ["random", "prefixed", "sequential", "dispersed"],
        "scenario_config": {
            "TOTAL_TAGS": 5000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_common_prefix_sweep",
        "description": "Common-prefix stress test for OVG under batch-like EPC skew.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "TOTAL_TAGS", "target": "scenario", "values": [1000, 2000, 5000, 10000]},
            {"key": "prefix_length", "target": "scenario", "values": [0, 16, 32, 48, 64, 72, 80]},
        ],
        "scenario_config": {
            "BINARY_LENGTH": 96,
            "id_distribution": "prefixed",
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_inspect_window_sensitivity",
        "description": "Sensitivity of HLCT-Base to bounded inspect window size.",
        "varying_param_key": "inspect_window_bits",
        "varying_param_target": "algorithm",
        "varying_param_values": [4, 8, 16, 24, 32, 96],
        "scenario_config": {
            "TOTAL_TAGS": 5000,
            "BINARY_LENGTH": 96,
            "id_distribution": "prefixed",
            "prefix_length": 64,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_fcw_window_sensitivity",
        "description": "Sensitivity of FCW-SGCT to fused Check window size.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefixed", "prefix64", "prefix72", "prefix80", "dispersed", "sequential", "clustered"]},
            {"key": "fused_window_bits", "target": "algorithm", "values": [0, 2, 4, 6, 8, 12, 16]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 5000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
            "enable_fused_check_window": True,
            "enable_adaptive_fcw": False,
        },
    },
    {
        "name": "formal_ovg_stress_ablation",
        "description": "Stress ablation for OVG under long-prefix, clustered, and dispersed IDs.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["prefix64", "prefix72", "prefix80", "dispersed", "clustered"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 5000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_check_gating_ablation",
        "description": "Formal ablation for FCW and Check-Gated EPC Verification.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefixed", "prefix80", "dispersed", "sequential", "clustered"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 5000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_full_algorithm_comparison",
        "description": "Full paired-seed comparison with extended baseline algorithms and stress distributions.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefixed", "prefix64", "prefix72", "prefix80", "dispersed", "sequential", "clustered"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 5000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_experiment10_algorithm_comparison",
        "description": "Experiment 10 main paper comparison for SGCT against reproduced baselines.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefixed", "prefix64", "prefix72", "prefix80", "dispersed", "sequential", "clustered"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 10000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_experiment11_hlct_improvement",
        "description": "Experiment 11 ablation for HLCT-Base retry budget, Adaptive FCW, OVG, and prefix-stagnation controls.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefixed", "prefix80", "dispersed", "clustered"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 5000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_experiment12_hlct_feedback",
        "description": "Experiment 12 ablation for Adaptive CBIT width and feedback-risk guards in HLCT-Base.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefixed", "prefix64", "prefix80", "dispersed", "sequential", "clustered"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 5000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_experiment13_sgct_signature_grouping",
        "description": "Progressive sparse signature grouping comparison and module ablation for SGCT.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefixed", "prefix64", "prefix72", "prefix80", "dispersed", "sequential", "clustered"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 10000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_sgct_scalability",
        "description": "Scalability curves for SGCT under key EPC distributions.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefixed", "clustered", "sequential"]},
            {"key": "TOTAL_TAGS", "target": "scenario", "values": [1000, 2000, 3000, 5000, 7000, 10000]},
        ],
        "scenario_config": {
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_sgct_prefix_sweep",
        "description": "Prefix-length sweep for SGCT and strong baselines.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "TOTAL_TAGS", "target": "scenario", "values": [100, 1000, 10000]},
            {"key": "prefix_length", "target": "scenario", "values": [0, 16, 32, 48, 64, 72, 80, 88]},
        ],
        "scenario_config": {
            "BINARY_LENGTH": 96,
            "id_distribution": "prefixed",
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_sgct_signature_sensitivity",
        "description": "Sensitivity of SGCT to sparse signature width and slot cap.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefix80", "dispersed", "sequential", "clustered"]},
            {"key": "sgct_d_target", "target": "algorithm", "values": [4, 6, 8, 10]},
            {"key": "signature_slot_cap", "target": "algorithm", "values": [256, 512, 1024]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 10000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_sgct_ber_robustness",
        "description": "BER robustness for SGCT and strong baselines.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefix80", "clustered", "dispersed", "sequential"]},
            {"key": "ber", "target": "algorithm", "values": [0.0, 1e-5, 1e-4, 1e-3]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 10000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_sgct_id_length_structured",
        "description": "Structured ID-length sensitivity for SGCT under random, clustered, and proportional prefix stress.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "BINARY_LENGTH", "target": "scenario", "values": [64, 96, 128, 160]},
            {"key": "scenario_label", "target": "scenario", "values": ["random", "medium-prefix", "long-prefix", "clustered"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 10000,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_sgct_energy_sensitivity",
        "description": "Energy-model sensitivity for SGCT and strong baselines under representative EPC distributions.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefix80", "dispersed", "clustered"]},
            {"key": "energy_profile", "target": "algorithm", "values": ["baseline", "tag-expensive", "reader-expensive", "listen-expensive", "balanced-high"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 10000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_extended_baseline_screen",
        "description": "Optional appendix screen with additional reproduced baselines.",
        "varying_param_key": "scenario_point",
        "varying_params": [
            {"key": "scenario_label", "target": "scenario", "values": ["random", "prefixed", "prefix80", "clustered"]},
        ],
        "scenario_config": {
            "TOTAL_TAGS": 10000,
            "BINARY_LENGTH": 96,
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
    {
        "name": "formal_sequential_scalability",
        "description": "Scalability under sequential IDs.",
        "varying_param_key": "TOTAL_TAGS",
        "varying_param_values": list(np.linspace(1000, 5000, 5, dtype=int)),
        "scenario_config": {
            "BINARY_LENGTH": 96,
            "id_distribution": "sequential",
        },
        "algorithm_specific_config": {
            "ber": 0.0,
            "enable_refined_energy_model": True,
            "enable_resource_monitoring": True,
        },
    },
]


OCG_ABLATION_LIBRARY = {
    "HLCT-Base": ALGORITHM_LIBRARY["HLCT-Base"],
    "HLCT-Base(no_ovg)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_ovg": False},
    },
    "HLCT-Base(no_check_escalation)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "f_default": 4, "f_escalated": 4},
    },
    "HLCT-Base(fixed_8bit_check)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "f_default": 8, "f_escalated": 8},
    },
    "HLCT-Base(no_check_gating)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_check_gating": False},
    },
    "HLCT-Base(no_fused_check)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_fused_check_window": False},
    },
    "HLCT-Base(no_prefix_stagnation)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_prefix_stagnation": False},
    },
    "HLCT-Base(cbit_only)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {
            **ALGORITHM_LIBRARY["HLCT-Base"]["config"],
            "split_policy": "CBIT_ONLY",
            "enable_ovg": False,
            "theta_v": 10**9,
        },
    },
    "HLCT-Base(lock_only)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {
            **ALGORITHM_LIBRARY["HLCT-Base"]["config"],
            "r_max": 1,
            "H_skew": 10**9,
            "theta_v": 10**9,
        },
    },
}


EXPERIMENT11_HLCT_LIBRARY = {
    "HLCT-Base": ALGORITHM_LIBRARY["HLCT-Base"],
    "HLCT-Base(prev_R2)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "R_OVG": 2},
    },
    "HLCT-Base(no_ovg)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_ovg": False},
    },
    "HLCT-Base(adaptive_fcw)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_adaptive_fcw": True},
    },
    "HLCT-Base(no_prefix_stagnation)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_prefix_stagnation": False},
    },
}


EXPERIMENT12_HLCT_LIBRARY = {
    "HLCT-Base": ALGORITHM_LIBRARY["HLCT-Base"],
    "HLCT-Base(no_adaptive_cbit)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_adaptive_cbit": False},
    },
    "HLCT-Base(no_multibit_fallback)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_multibit_fallback": False},
    },
    "HLCT-Base(prev_R2)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "R_OVG": 2},
    },
    "HLCT-Base(no_ovg)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_ovg": False},
    },
    "HLCT-Base(adaptive_fcw)": {
        **ALGORITHM_LIBRARY["HLCT-Base"],
        "config": {**ALGORITHM_LIBRARY["HLCT-Base"]["config"], "enable_adaptive_fcw": True},
    },
}


SGCT_ABLATION_LIBRARY = {
    PRIMARY_SG_ALGORITHM: ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM],
    "SGCT(no_signature_grouping)": {
        **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM],
        "config": {
            **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM]["config"],
            "enable_signature_grouping": False,
        },
    },
    "SGCT(no_local_short_id)": {
        **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM],
        "config": {
            **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM]["config"],
            "enable_local_short_id": False,
        },
    },
    "SGCT(no_suffix_extension)": {
        **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM],
        "config": {
            **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM]["config"],
            "enable_suffix_signature": False,
        },
    },
    "SGCT(no_low_d_fallback)": {
        **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM],
        "config": {
            **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM]["config"],
            "enable_low_d_fallback": False,
        },
    },
    "SGCT(d4)": {
        **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM],
        "config": {
            **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM]["config"],
            "d_target_dense": 4,
            "d_target_normal": 4,
            "d_target_skew": 4,
            "signature_d_max": 4,
        },
    },
    "SGCT(d6)": {
        **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM],
        "config": {
            **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM]["config"],
            "d_target_dense": 6,
            "d_target_normal": 6,
            "d_target_skew": 4,
            "signature_d_max": 6,
        },
    },
    "SGCT(d8)": {
        **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM],
        "config": {
            **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM]["config"],
            "d_target_dense": 8,
            "d_target_normal": 6,
            "d_target_skew": 4,
            "signature_d_max": 8,
        },
    },
    "SGCT(d10)": {
        **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM],
        "config": {
            **ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM]["config"],
            "d_target_dense": 10,
            "d_target_normal": 10,
            "d_target_skew": 6,
            "signature_d_max": 10,
            "signature_slot_cap": 1024,
        },
    },
}


ABLATION_EXPERIMENT = {
    "name": "formal_ocg_ablation",
    "description": "Ablation study for HLCT-Base components.",
    "varying_param_key": "id_distribution",
    "varying_param_values": ["random", "prefixed", "sequential", "dispersed"],
    "scenario_config": {
        "TOTAL_TAGS": 5000,
        "BINARY_LENGTH": 96,
    },
    "algorithm_specific_config": {
        "ber": 0.0,
        "enable_refined_energy_model": True,
        "enable_resource_monitoring": True,
    },
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


def stable_seed(*parts: Any) -> int:
    payload = json.dumps(parts, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return int(digest[:16], 16) % (2**32)


def generate_tag_ids_for_point(scenario_config: Dict[str, Any], seed: int) -> List[str]:
    rng = random.Random(seed)
    tags = generate_scenario(scenario_config, rng=rng)
    return sorted(tag.id for tag in tags)


def apply_scenario_label(scenario_config: Dict[str, Any]) -> None:
    label = scenario_config.get("scenario_label")
    if not label:
        return
    if label not in SCENARIO_PRESETS:
        raise ValueError(f"Unknown scenario_label: {label}")
    scenario_config.update(SCENARIO_PRESETS[label])
    if "prefix_ratio" in scenario_config:
        binary_length = int(scenario_config["BINARY_LENGTH"])
        total_tags = int(scenario_config.get("TOTAL_TAGS", 1))
        suffix_bits_needed = math.ceil(math.log2(max(1, total_tags)))
        max_prefix_length = max(0, binary_length - suffix_bits_needed)
        scenario_config["prefix_length"] = max(
            0,
            min(max_prefix_length, int(binary_length * scenario_config.pop("prefix_ratio"))),
        )
    if scenario_config.get("id_distribution") == "clustered":
        binary_length = int(scenario_config["BINARY_LENGTH"])
        cluster_count = max(1, int(scenario_config.get("cluster_count", 8)))
        tags_per_cluster = math.ceil(int(scenario_config.get("TOTAL_TAGS", 1)) / cluster_count)
        suffix_bits_needed = math.ceil(math.log2(max(1, tags_per_cluster)))
        max_cluster_prefix = max(0, binary_length - suffix_bits_needed)
        scenario_config["cluster_prefix_length"] = min(
            int(scenario_config.get("cluster_prefix_length", max_cluster_prefix)),
            max_cluster_prefix,
        )


def _iter_experiment_points(experiment: Dict[str, Any]):
    if "varying_params" not in experiment:
        varying_key = experiment["varying_param_key"]
        varying_target = experiment.get("varying_param_target", "scenario")
        for value in experiment["varying_param_values"]:
            yield [(varying_key, varying_target, value)]
        return

    param_specs = experiment["varying_params"]
    value_lists = [spec["values"] for spec in param_specs]
    for values in itertools.product(*value_lists):
        yield [
            (spec["key"], spec.get("target", "scenario"), value)
            for spec, value in zip(param_specs, values)
        ]


def build_paired_tasks(
    experiment: Dict[str, Any],
    algorithms: Sequence[str],
    runs_per_point: int,
    base_seed: int = DEFAULT_BASE_SEED,
) -> List[FormalTask]:
    tasks: List[FormalTask] = []

    for point_params in _iter_experiment_points(experiment):
        scenario_config = dict(experiment["scenario_config"])
        algorithm_specific_config = dict(experiment["algorithm_specific_config"])
        point_labels = []
        for key, target, value in point_params:
            point_labels.append(f"{key}={value}")
            if target == "algorithm":
                algorithm_specific_config[key] = value
            elif target == "scenario":
                scenario_config[key] = value
            else:
                raise ValueError(f"Unsupported varying_param_target: {target}")
        apply_scenario_label(scenario_config)
        if "varying_params" in experiment:
            scenario_config[experiment["varying_param_key"]] = ",".join(point_labels)

        for run_id in range(runs_per_point):
            point_seed = stable_seed(base_seed, experiment["name"], scenario_config, run_id)
            try:
                tag_ids = generate_tag_ids_for_point(scenario_config, point_seed)
            except ValueError:
                continue

            for algorithm_name in algorithms:
                algorithm_seed = stable_seed(point_seed, algorithm_name)
                tasks.append(
                    FormalTask(
                        experiment_name=experiment["name"],
                        algorithm_name=algorithm_name,
                        scenario_config=dict(scenario_config),
                        algorithm_specific_config=dict(algorithm_specific_config),
                        run_id=run_id,
                        point_seed=point_seed,
                        algorithm_seed=algorithm_seed,
                        tag_ids=tag_ids,
                    )
                )

    return tasks


def run_formal_task(task: FormalTask, algorithm_library: Dict[str, Dict[str, Any]]):
    random.seed(task.algorithm_seed)
    np.random.seed(task.algorithm_seed)

    algorithm_info = algorithm_library[task.algorithm_name]
    final_config = {
        **algorithm_info["config"],
        **task.algorithm_specific_config,
    }
    energy_profile = final_config.pop("energy_profile", None)
    if energy_profile:
        if energy_profile not in ENERGY_PROFILES:
            raise ValueError(f"Unknown energy profile: {energy_profile}")
        final_config.update(ENERGY_PROFILES[energy_profile])
    if "sgct_d_target" in final_config:
        d_target = final_config.pop("sgct_d_target")
        final_config["d_target_dense"] = d_target
        final_config["d_target_normal"] = d_target
        final_config["signature_d_max"] = d_target
    tags = [Tag(tag_id) for tag_id in task.tag_ids]
    result = run_simulation_with_tags(tags, algorithm_info["class"], final_config)

    config_log = {
        **task.scenario_config,
        **task.algorithm_specific_config,
        "experiment_name": task.experiment_name,
        "point_seed": task.point_seed,
        "algorithm_seed": task.algorithm_seed,
    }
    return result, config_log, task.algorithm_name, task.run_id


def run_formal_task_default(task: FormalTask):
    return run_formal_task(task, ALGORITHM_LIBRARY)


def calculate_summary_ci(
    df: pd.DataFrame,
    group_keys: Sequence[str],
    metric_columns: Iterable[str],
) -> pd.DataFrame:
    rows = []
    for group_values, group_df in df.groupby(list(group_keys), dropna=False):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        base = dict(zip(group_keys, group_values))
        for metric in metric_columns:
            if metric not in group_df.columns:
                continue
            series = pd.to_numeric(group_df[metric], errors="coerce").dropna()
            if series.empty:
                continue
            mean = float(series.mean())
            std = float(series.std(ddof=1)) if len(series) > 1 else 0.0
            ci95 = 1.96 * std / float(np.sqrt(len(series))) if len(series) > 1 else 0.0
            p95 = float(series.quantile(0.95))
            rows.append({
                **base,
                "metric": metric,
                "mean": mean,
                "std": std,
                "p95": p95,
                "ci95": ci95,
                "n": len(series),
            })
    return pd.DataFrame(rows)


def metric_columns_for_summary(df: pd.DataFrame) -> List[str]:
    preferred = [
        "total_protocol_time_ms",
        "throughput_tags_per_sec",
        "system_efficiency",
        "collision_slots",
        "idle_slots",
        "total_energy_uj",
        "energy_per_tag_uj",
        "total_reader_tx_energy_uj",
        "total_tag_tx_energy_uj",
        "total_listening_energy_uj",
        "total_transmission_energy_uj",
        "total_bits",
        "avg_tag_bits",
        "avg_reader_bits",
        "avg_total_bits",
        "avg_query_efficiency",
        "peak_stack_depth",
        "ovg_trigger_count",
        "fallback_invocation_count",
        "fallback_invocation_ratio",
        "prefix_stagnation_trigger_count",
        "prefix_stag_score_trigger_count",
        "repeated_pattern_trigger_count",
        "ovg_success_count",
        "post_ovg_singleton_count",
        "ovg_fallback_avoid_count",
        "ovg_rehash_count",
        "ovg_width_up_count",
        "ovg_width_down_count",
        "ovg_no_singleton_count",
        "inspect_collision_count",
        "fcw_cache_created_count",
        "fcw_cache_hit_count",
        "fcw_cache_hit_ratio",
        "fcw_fast_path_count",
        "fcw_width_up_count",
        "fcw_width_down_count",
        "adaptive_cbit_r4_count",
        "multibit_fallback_count",
        "progressive_probe_count",
        "signature_grouping_trigger_count",
        "local_short_id_trigger_count",
        "signature_groups_pruned",
        "sparse_signature_groups",
        "signature_marker_bits",
        "signature_marker_tag_bits",
        "signature_non_idle_marker_count",
        "signature_collision_groups",
        "signature_singleton_groups",
        "low_d_fallback_count",
        "suffix_signature_trigger_count",
        "hash_short_id_round_count",
        "hash_short_id_split_count",
        "hash_short_id_collision_groups",
        "hash_short_id_singleton_groups",
        "small_cluster_guard_count",
        "max_signature_d",
        "epc_verification_count",
        "verify_fail_count",
        "avg_tag_responses",
    ]
    return [col for col in preferred if col in df.columns]


def deduplicate_result_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate metric columns created by repeated derived-metric passes.

    Pandas reads duplicate CSV headers back as ``metric.1``.  Formal outputs
    keep the canonical unsuffixed column when the duplicate values are equal.
    If the values differ, the suffixed column is retained to avoid data loss.
    """

    if df.empty:
        return df
    result = df.loc[:, ~df.columns.duplicated()].copy()
    drop_columns: List[str] = []
    for column in list(result.columns):
        if "." not in column:
            continue
        base, suffix = column.rsplit(".", 1)
        if not suffix.isdigit() or base not in result.columns:
            continue
        left = result[base]
        right = result[column]
        if left.equals(right):
            drop_columns.append(column)
            continue
        left_num = pd.to_numeric(left, errors="coerce")
        right_num = pd.to_numeric(right, errors="coerce")
        both_missing = left_num.isna() & right_num.isna()
        numeric_equal = ((left_num - right_num).abs().fillna(0.0) <= 1e-12) | both_missing
        if bool(numeric_equal.all()):
            drop_columns.append(column)
    return result.drop(columns=drop_columns) if drop_columns else result


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, type):
        return value.__name__
    return value


def build_config_snapshot(
    df: pd.DataFrame,
    experiment: Dict[str, Any],
    algorithm_library: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    algorithms = sorted(str(name) for name in df.get("algorithm_name", pd.Series(dtype=str)).dropna().unique())
    algorithm_configs = {}
    for name in algorithms:
        info = algorithm_library.get(name, {})
        algorithm_configs[name] = {
            "class": getattr(info.get("class"), "__name__", None),
            "config": _json_safe(info.get("config", {})),
            "year": _json_safe(info.get("year")),
        }

    scenario_columns = [
        "scenario_point",
        "scenario_label",
        "TOTAL_TAGS",
        "BINARY_LENGTH",
        "id_distribution",
        "prefix_length",
        "ber",
        "energy_profile",
    ]
    scenarios = []
    for column in scenario_columns:
        if column in df.columns:
            values = sorted({_json_safe(value) for value in df[column].dropna().unique()})
            scenarios.append({"field": column, "values": values})

    return {
        "experiment_name": experiment["name"],
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "results_base_dir": RESULTS_BASE_DIR,
        "varying_param_key": experiment["varying_param_key"],
        "varying_param_values": _json_safe(experiment.get("varying_param_values")),
        "varying_params": _json_safe(experiment.get("varying_params")),
        "scenario_config": _json_safe(experiment.get("scenario_config", {})),
        "algorithm_specific_config": _json_safe(experiment.get("algorithm_specific_config", {})),
        "algorithms": algorithms,
        "algorithm_configs": algorithm_configs,
        "scenarios": scenarios,
        "runs_per_point": int(df["run_id"].nunique()) if "run_id" in df.columns else None,
        "row_count": int(len(df)),
        "drct_note": "The formal baseline named DRCT is implemented by DRCTFinalAlgorithm.",
    }


def calculate_paired_significance(
    df: pd.DataFrame,
    group_key: str,
    metric: str = "total_protocol_time_ms",
    candidate: str = PRIMARY_SG_ALGORITHM,
    baselines: Sequence[str] = ("HLCT-Base", "EMDT", "NLHQT(n=2)"),
) -> pd.DataFrame:
    if metric not in df.columns or candidate not in set(df.get("algorithm_name", [])):
        return pd.DataFrame()

    rows = []
    for group_value, group_df in df.groupby(group_key, dropna=False):
        pivot = group_df.pivot_table(
            index="run_id",
            columns="algorithm_name",
            values=metric,
            aggfunc="mean",
        )
        if candidate not in pivot.columns:
            continue
        for baseline in baselines:
            if baseline not in pivot.columns:
                continue
            paired = pivot[[candidate, baseline]].dropna()
            if paired.empty:
                continue
            diff = paired[baseline] - paired[candidate]
            mean_baseline = float(paired[baseline].mean())
            mean_candidate = float(paired[candidate].mean())
            mean_diff = float(diff.mean())
            std_diff = float(diff.std(ddof=1)) if len(diff) > 1 else 0.0
            enough_for_normal_approx = len(diff) >= 5
            if enough_for_normal_approx and std_diff > 0:
                t_stat = mean_diff / (std_diff / math.sqrt(len(diff)))
                p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
                cohens_d = mean_diff / std_diff
            else:
                t_stat = math.nan
                p_value = math.nan
                cohens_d = mean_diff / std_diff if std_diff > 0 else math.nan
            rows.append(
                {
                    group_key: group_value,
                    "candidate": candidate,
                    "baseline": baseline,
                    "metric": metric,
                    "candidate_mean": mean_candidate,
                    "baseline_mean": mean_baseline,
                    "mean_improvement": mean_diff,
                    "mean_improvement_pct": (
                        mean_diff / mean_baseline * 100.0 if mean_baseline else 0.0
                    ),
                    "paired_t_stat": t_stat,
                    "paired_t_p_value_normal_approx": p_value,
                    "cohens_d": cohens_d,
                    "win_rate": float((paired[candidate] < paired[baseline]).mean()),
                    "n": len(paired),
                }
            )
    return pd.DataFrame(rows)


def save_formal_outputs(
    analytics: SimulationAnalytics,
    experiment: Dict[str, Any],
    output_dir: str,
    algorithm_library: Dict[str, Dict[str, Any]],
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    df = analytics.get_results_dataframe()
    if df.empty:
        return

    df = analytics._calculate_derived_metrics(df)
    df = deduplicate_result_columns(df)
    raw_path = os.path.join(output_dir, "raw_runs.csv")
    df.to_csv(raw_path, index=False, float_format="%.6f")

    manifest_df = df.copy()
    if "algorithm_name" in manifest_df.columns and "algorithm" not in manifest_df.columns:
        manifest_df["algorithm"] = manifest_df["algorithm_name"]
    if "scenario_label" in manifest_df.columns and "scenario" not in manifest_df.columns:
        manifest_df["scenario"] = manifest_df["scenario_label"]
    elif experiment["varying_param_key"] in manifest_df.columns and "scenario" not in manifest_df.columns:
        manifest_df["scenario"] = manifest_df[experiment["varying_param_key"]]
    if "TOTAL_TAGS" in manifest_df.columns and "tag_count" not in manifest_df.columns:
        manifest_df["tag_count"] = manifest_df["TOTAL_TAGS"]
    if "BINARY_LENGTH" in manifest_df.columns and "epc_length" not in manifest_df.columns:
        manifest_df["epc_length"] = manifest_df["BINARY_LENGTH"]
    if "status" not in manifest_df.columns:
        manifest_df["status"] = "ok"
    if "runtime" not in manifest_df.columns:
        manifest_df["runtime"] = ""

    manifest_cols = [
        "experiment_name",
        "scenario",
        "run_id",
        "point_seed",
        "algorithm",
        "algorithm_seed",
        "tag_count",
        "epc_length",
        "status",
        "runtime",
        experiment["varying_param_key"],
        "algorithm_name",
    ]
    manifest_cols = [col for col in manifest_cols if col in manifest_df.columns]
    manifest_df[manifest_cols].drop_duplicates().to_csv(
        os.path.join(output_dir, "run_manifest.csv"),
        index=False,
    )
    with open(os.path.join(output_dir, "config_snapshot.json"), "w", encoding="utf-8") as handle:
        json.dump(
            build_config_snapshot(df, experiment, algorithm_library),
            handle,
            ensure_ascii=False,
            indent=2,
        )

    summary = calculate_summary_ci(
        df,
        group_keys=[experiment["varying_param_key"], "algorithm_name"],
        metric_columns=metric_columns_for_summary(df),
    )
    summary.to_csv(os.path.join(output_dir, "summary_ci95.csv"), index=False, float_format="%.6f")

    significance = calculate_paired_significance(
        df,
        group_key=experiment["varying_param_key"],
        baselines=[name for name in PAPER_BASELINE_ALGORITHMS if name != PRIMARY_SG_ALGORITHM],
    )
    if not significance.empty:
        significance.to_csv(
            os.path.join(output_dir, "paired_significance.csv"),
            index=False,
            float_format="%.6f",
        )

    analytics.results_data = df.to_dict("records")
    analytics.save_to_csv(x_axis_key=experiment["varying_param_key"], output_dir=output_dir)
    analytics.plot_results(
        x_axis_key=experiment["varying_param_key"],
        algorithm_library=algorithm_library,
        save_path=os.path.join(output_dir, f"{experiment['name']}_plot.png"),
        show=False,
    )


def selected_experiments(names: Sequence[str], paper_only: bool = False) -> List[Dict[str, Any]]:
    experiment_map = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}
    experiment_map[ABLATION_EXPERIMENT["name"]] = ABLATION_EXPERIMENT
    if paper_only and names:
        raise ValueError("--paper-only cannot be combined with explicit --experiment values.")
    if paper_only:
        return [experiment_map[name] for name in FORMAL_PAPER_EXPERIMENTS]
    if not names:
        return FORMAL_EXPERIMENTS
    missing = [name for name in names if name not in experiment_map]
    if missing:
        raise ValueError(f"Unknown formal experiment(s): {', '.join(missing)}")
    return [experiment_map[name] for name in names]


def algorithm_library_for_experiment(experiment_name: str):
    if experiment_name == "formal_experiment13_sgct_signature_grouping":
        return {
            "HLCT-Base": ALGORITHM_LIBRARY["HLCT-Base"],
            **{name: ALGORITHM_LIBRARY[name] for name in PAPER_BASELINE_ALGORITHMS},
            **SGCT_ABLATION_LIBRARY,
        }
    if experiment_name == "formal_sgct_signature_sensitivity":
        return {PRIMARY_SG_ALGORITHM: ALGORITHM_LIBRARY[PRIMARY_SG_ALGORITHM]}
    if experiment_name.startswith("formal_sgct_"):
        return {name: ALGORITHM_LIBRARY[name] for name in PAPER_BASELINE_ALGORITHMS}
    if experiment_name == "formal_extended_baseline_screen":
        return {name: ALGORITHM_LIBRARY[name] for name in EXTENDED_COMPARISON_ALGORITHMS}
    if experiment_name == "formal_experiment12_hlct_feedback":
        return EXPERIMENT12_HLCT_LIBRARY
    if experiment_name == "formal_experiment11_hlct_improvement":
        return EXPERIMENT11_HLCT_LIBRARY
    if experiment_name.startswith(ABLATION_EXPERIMENT["name"]) or experiment_name in {
        "formal_ovg_stress_ablation",
        "formal_check_gating_ablation",
    }:
        return OCG_ABLATION_LIBRARY
    return ALGORITHM_LIBRARY


def algorithms_for_experiment(experiment_name: str, requested_algorithms: Sequence[str]) -> List[str]:
    library = algorithm_library_for_experiment(experiment_name)
    if requested_algorithms:
        unknown = [name for name in requested_algorithms if name not in library]
        if unknown:
            raise ValueError(f"Unknown algorithm(s): {', '.join(unknown)}")
        return list(requested_algorithms)
    if experiment_name.startswith(ABLATION_EXPERIMENT["name"]) or experiment_name in {
        "formal_ovg_stress_ablation",
        "formal_check_gating_ablation",
    }:
        return list(OCG_ABLATION_LIBRARY.keys())
    if experiment_name == "formal_experiment11_hlct_improvement":
        return list(EXPERIMENT11_HLCT_LIBRARY.keys())
    if experiment_name == "formal_experiment12_hlct_feedback":
        return list(EXPERIMENT12_HLCT_LIBRARY.keys())
    if experiment_name == "formal_experiment13_sgct_signature_grouping":
        return [
            PRIMARY_SG_ALGORITHM,
            "HLCT-Base",
            "SGCT(no_signature_grouping)",
            "SGCT(no_local_short_id)",
            "SGCT(no_suffix_extension)",
            "SGCT(no_low_d_fallback)",
            "SGCT(d4)",
            "SGCT(d6)",
            "SGCT(d8)",
            "SGCT(d10)",
            "EMDT",
            "NLHQT(n=2)",
            "DRCT",
            "LAPCT",
            "DQTA(k_max=3)",
        ]
    if experiment_name == "formal_sgct_id_length_structured":
        return [
            PRIMARY_SG_ALGORITHM,
            "NLHQT(n=2)",
            "EMDT",
            "DQTA(k_max=3)",
            "DRCT",
            "LAPCT",
        ]
    if experiment_name == "formal_sgct_energy_sensitivity":
        return [
            PRIMARY_SG_ALGORITHM,
            "NLHQT(n=2)",
            "EMDT",
            "DQTA(k_max=3)",
        ]
    if experiment_name.startswith("formal_sgct_"):
        return [name for name in PAPER_BASELINE_ALGORITHMS if name in library]
    if experiment_name == "formal_experiment10_algorithm_comparison":
        return [name for name in EXPERIMENT10_ALGORITHMS if name in library]
    if experiment_name == "formal_extended_baseline_screen":
        return [name for name in EXTENDED_COMPARISON_ALGORITHMS if name in library]
    return [name for name in ALGORITHMS_TO_TEST if name in library]


def run_formal_task_for_experiment(task: FormalTask):
    return run_formal_task(task, algorithm_library_for_experiment(task.experiment_name))


def _normalize_existing_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _task_identity(task: FormalTask, varying_param_key: str) -> tuple:
    return (
        task.algorithm_name,
        int(task.run_id),
        _normalize_existing_value(task.scenario_config.get(varying_param_key, "")),
    )


def _existing_task_identities(df: pd.DataFrame, varying_param_key: str) -> set:
    required = {"algorithm_name", "run_id", varying_param_key}
    if df.empty or not required.issubset(df.columns):
        return set()
    return {
        (
            str(row["algorithm_name"]),
            int(row["run_id"]),
            _normalize_existing_value(row[varying_param_key]),
        )
        for _, row in df[list(required)].drop_duplicates().iterrows()
    }


def load_existing_results(output_dir: str) -> pd.DataFrame:
    raw_path = os.path.join(output_dir, "raw_runs.csv")
    checkpoint_path = os.path.join(output_dir, "raw_runs_checkpoint.csv")
    frames = []
    if os.path.exists(raw_path):
        frames.append(pd.read_csv(raw_path))
    if os.path.exists(checkpoint_path):
        frames.append(pd.read_csv(checkpoint_path))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False).drop_duplicates(keep="last")


def filter_missing_tasks(
    tasks: Sequence[FormalTask],
    existing_df: pd.DataFrame,
    varying_param_key: str,
) -> List[FormalTask]:
    existing = _existing_task_identities(existing_df, varying_param_key)
    return [task for task in tasks if _task_identity(task, varying_param_key) not in existing]


def run_experiment(
    experiment: Dict[str, Any],
    algorithms: Sequence[str],
    runs_per_point: int,
    base_seed: int,
    processes: int,
    resume_existing: bool = False,
    checkpoint_interval: int = 100,
) -> None:
    library = algorithm_library_for_experiment(experiment["name"])
    tasks = build_paired_tasks(experiment, algorithms, runs_per_point, base_seed)
    output_dir = os.path.join(RESULTS_BASE_DIR, experiment["name"])
    os.makedirs(output_dir, exist_ok=True)
    checkpoint_path = os.path.join(output_dir, "raw_runs_checkpoint.csv")
    analytics = SimulationAnalytics()
    existing_df = pd.DataFrame()
    if resume_existing:
        existing_df = load_existing_results(output_dir)
        tasks = filter_missing_tasks(tasks, existing_df, experiment["varying_param_key"])
        if not existing_df.empty:
            analytics.results_data = existing_df.to_dict("records")

    print("\n" + "=" * 80)
    print(f"Experiment: {experiment['name']}")
    print(f"Description: {experiment['description']}")
    print(f"Algorithms: {', '.join(algorithms)}")
    if "varying_params" in experiment:
        varying_description = {
            spec["key"]: spec["values"]
            for spec in experiment["varying_params"]
        }
    else:
        varying_description = {experiment["varying_param_key"]: experiment["varying_param_values"]}
    print(f"Varying: {varying_description}")
    print(f"Runs per point: {runs_per_point}; paired base seed: {base_seed}")
    if resume_existing:
        print(f"Existing rows loaded: {len(existing_df)}")
    print(f"Tasks to run: {len(tasks)}")
    print("=" * 80)

    start = time.time()
    if not tasks:
        save_formal_outputs(analytics, experiment, output_dir, library)
        print(f"No missing tasks; refreshed formal outputs in {output_dir}; elapsed {time.time() - start:.2f}s")
        return

    completed_since_checkpoint = 0

    def record_result(result_tuple) -> None:
        nonlocal completed_since_checkpoint
        analytics.add_run_result(*result_tuple)
        completed_since_checkpoint += 1
        if checkpoint_interval > 0 and completed_since_checkpoint >= checkpoint_interval:
            checkpoint_df = analytics._calculate_derived_metrics(analytics.get_results_dataframe())
            checkpoint_df = deduplicate_result_columns(checkpoint_df)
            checkpoint_df.to_csv(checkpoint_path, index=False, float_format="%.6f")
            completed_since_checkpoint = 0

    if processes == 1:
        iterator = map(lambda task: run_formal_task(task, library), tasks)
        for result_tuple in tqdm(iterator, total=len(tasks), desc=experiment["name"]):
            record_result(result_tuple)
    else:
        with multiprocessing.Pool(processes=processes) as pool:
            for result_tuple in tqdm(
                pool.imap_unordered(run_formal_task_for_experiment, tasks),
                total=len(tasks),
                desc=experiment["name"],
            ):
                record_result(result_tuple)

    save_formal_outputs(analytics, experiment, output_dir, library)
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
    print(f"Saved formal outputs to {output_dir}; elapsed {time.time() - start:.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paired-seed formal HLCT-Base experiments.")
    parser.add_argument("--experiment", action="append", default=[], help="Experiment name. Repeat to run several.")
    parser.add_argument("--algorithm", action="append", default=[], help="Algorithm name. Repeat to run a subset.")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS_PER_POINT)
    parser.add_argument("--base-seed", type=int, default=DEFAULT_BASE_SEED)
    parser.add_argument("--processes", type=int, default=DEFAULT_PROCESSES)
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Load existing raw_runs.csv and run only missing algorithm/point/run rows.",
    )
    parser.add_argument("--checkpoint-interval", type=int, default=100)
    parser.add_argument(
        "--paper-only",
        action="store_true",
        help=(
            "Run only the five SGCT paper experiments: main comparison, "
            "scalability, prefix sweep, ablation, and BER robustness."
        ),
    )
    args = parser.parse_args()

    for experiment in selected_experiments(args.experiment, paper_only=args.paper_only):
        algorithms = algorithms_for_experiment(experiment["name"], args.algorithm)
        run_experiment(
            experiment=experiment,
            algorithms=algorithms,
            runs_per_point=args.runs,
            base_seed=args.base_seed,
            processes=args.processes,
            resume_existing=args.resume_existing,
            checkpoint_interval=args.checkpoint_interval,
        )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()



