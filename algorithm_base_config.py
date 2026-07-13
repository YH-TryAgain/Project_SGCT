"""Canonical algorithm registry for the submitted SGCT manuscript."""

from DQTA import DQTAAlgorithm
from DRCT import DRCTAlgorithm
from EAQ_CBB import EAQCBBAlgorithm
from EMDT import EMDTAlgorithm
from LAPCT import LAPCTAlgorithm
from NLHQT import NLHQTAlgorithm
from SGCT import SGCTAlgorithm


PAPER_ALGORITHMS = [
    "SGCT",
    "DRCT",
    "LAPCT",
    "EMDT",
    "DQTA",
    "EAQ-CBB",
    "NLHQT(n=2)",
]

# Historical CSV keys remain immutable. Convert them only at the display layer.
DISPLAY_NAMES = {
    "SGCT": "SGCT",
    "DRCT": "DRCT",
    "LAPCT": "LAPCT",
    "EMDT": "EMDT",
    "DQTA": "DQTA",
    "DQTA(k_max=3)": "DQTA",
    "EAQ_CBB": "EAQ-CBB",
    "EAQ-CBB": "EAQ-CBB",
    "NLHQT(n=2)": "NLHQT(n=2)",
    "SGCT(no_signature_grouping)": "SGCT (w/o marker pruning)",
    "SGCT(no_local_short_id)": "SGCT (w/o local short-ID)",
}

ALGORITHM_LIBRARY = {
    "SGCT": {
        "class": SGCTAlgorithm,
        "config": {
            "probe_chunk_bits": 16,
            "d_target_dense": 8,
            "d_target_normal": 6,
            "d_target_skew": 4,
            "signature_d_min": 4,
            "signature_d_max": 8,
            "signature_slot_cap": 256,
            "signature_marker_bits": 1,
            "terminal_group_size": 1,
            "enable_suffix_terminal_verify": True,
            "enable_signature_grouping": True,
            "enable_low_d_fallback": True,
            "enable_local_short_id": True,
            "local_short_id_min_bits": 8,
            "enable_hash_short_id": False,
            "hash_short_id_bits": 8,
            "hash_short_id_max_bits": 16,
            "enable_suffix_signature": True,
            "enable_adaptive_suffix_signature": True,
            "suffix_signature_root_only": True,
            "suffix_signature_min_prefix_bits": 64,
            "suffix_signature_max_remaining_bits": 32,
            "suffix_signature_d_max": 12,
            "suffix_signature_slot_cap": 4096,
            "suffix_signature_min_tags_per_slot": 8.0,
            "suffix_signature_max_non_idle_ratio": 0.35,
            "suffix_signature_sequential_non_idle_ratio": 0.65,
            "suffix_signature_cost_margin": 1.2,
            "max_suffix_signature_trials_per_node": 1,
            "enable_small_cluster_guard": False,
            "small_cluster_guard_max_tags": 128,
            "small_cluster_guard_prefix_bits": 64,
        },
        "display_name": "SGCT",
        "year": 2026,
        "style_id": 0,
    },
    "DRCT": {
        "class": DRCTAlgorithm,
        "config": {
            "check_bits": 4,
            "answer_bits": 2,
            "check_mode": "random",
            "paper_timing": False,
            "include_reader_cmd_base_bits": True,
        },
        "display_name": "DRCT",
        "year": 2025,
        "style_id": 1,
    },
    "LAPCT": {
        "class": LAPCTAlgorithm,
        "config": {"k_threshold_divisor": 3.0},
        "display_name": "LAPCT",
        "year": 2024,
        "style_id": 2,
    },
    "EMDT": {
        "class": EMDTAlgorithm,
        "config": {},
        "display_name": "EMDT",
        "year": 2024,
        "style_id": 3,
    },
    "DQTA": {
        "class": DQTAAlgorithm,
        "config": {"k_max": 3},
        "display_name": "DQTA",
        "year": 2019,
        "style_id": 4,
    },
    "EAQ-CBB": {
        "class": EAQCBBAlgorithm,
        "config": {},
        "display_name": "EAQ-CBB",
        "year": 2023,
        "style_id": 5,
    },
    "NLHQT(n=2)": {
        "class": NLHQTAlgorithm,
        "config": {"n_way": 2},
        "display_name": "NLHQT(n=2)",
        "year": 2023,
        "style_id": 6,
    },
}

# Compatibility for retained runner code while exposing only the paper set.
ALGORITHMS_TO_TEST = PAPER_ALGORITHMS
