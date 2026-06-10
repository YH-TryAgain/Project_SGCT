# -*- coding: utf-8 -*-
from NLHQT import NLHQTAlgorithm
from LAPCT import LAPCTAlgorithm
from DQTA import DQTAAlgorithm
from EMDT import EMDTAlgorithm
from EAQ_CBB import EAQCBBAlgorithm
from ICT import ICT_Algorithm
from SD_CGQT import SDCGQTAlgorithm
from SUBF_CGDFSA import SUBF_CGDFSA_Algorithm
from HT_EEAC import HT_EEAC
from FHS_RAC import FHS_RAC
from OCG_HLCT import OCGHLCTAlgorithm
from OCG_HLCT_PB import OCGHLCTPBAlgorithm
from DRCT_final import DRCTFinalAlgorithm
PLOT_STYLE_PALETTE = [


    {"color": "purple", "linestyle": "-", "marker": "*", "linewidth": 2.5, "markersize": 10, "zorder": 10},

    {"color": "deeppink", "linestyle": "--", "marker": "p", "linewidth": 2.0},
    # Style 2:
    {"color": "red", "linestyle": "-", "marker": "o"},
    # Style 3:
    {"color": "green", "linestyle": "-.", "marker": "s"},
    # Style 4:
    {"color": "blue", "linestyle": ":", "marker": "x"},
    # Style 5:
    {"color": "darkorange", "linestyle": "--", "marker": "^"},
    # Style 6:
    {"color": "brown", "linestyle": "-", "marker": "d"},
    # Style 7:
    {"color": "cyan", "linestyle": ":", "marker": "+"},
    # Style 8:
    {"color": "olive", "linestyle": "-.", "marker": "v"},
    # Style 9:
    {"color": "gray", "linestyle": "--", "marker": "."},
]
"""
    'SD-CGQT': {
        "class": SDCGQTAlgorithm,
        "config": {},
        "year": 23,
        "style_id": 7,
    },
    'SUBF_CGDFSA': {
        "class": SUBF_CGDFSA_Algorithm,
        "config": {},
        "year": 24,
        "style_id": 7,
    },
    'ICT': {
        "class": ICT_Algorithm,
        "config": {},
        "year": 24,
        "style_id": 7,
    },
"""
ALGORITHMS_TO_TEST = [
    'HLCT-Base',
    'SGCT',
    'DRCT',
    'NLHQT(n=2)', # 瑕佹祴璇曠殑鐗堟湰
    'NLHQT(n=1)', # 瑕佹祴璇曠殑鐗堟湰
    'LAPCT', # 瑕佹祴璇曠殑鐗堟湰
    'DQTA(k_max=3)',
    'EMDT',
    'EAQ_CBB', # 瑕佹祴璇曠殑鐗堟湰
    'HT_EEAC',
    'FHS_RAC',
    'ICT',
    'SD-CGQT',
    'SUBF-CGDFSA',
]
ALGORITHM_LIBRARY = {
    'HLCT-Base': {
        "class": OCGHLCTAlgorithm,
        "config": {
            "f_default": 5,
            "f_escalated": 8,
            "r_max": 3,
            "rho": 0.5,
            "H_skew": 2,
            "theta_v": 2,
            "R_OVG": 1,
            "H_stop": 3,
            "inspect_window_bits": 8,
            "ovg_min_prefix_bits": 16,
            "enable_fused_check_window": True,
            "fused_window_bits": 4,
            "enable_adaptive_fcw": False,
            "adaptive_fused_window_bits": 8,
            "adaptive_fcw_min_bits": 2,
            "adaptive_fcw_max_bits": 16,
            "enable_prefix_stagnation": True,
            "prefix_stagnation_threshold": 1,
            "enable_adaptive_cbit": True,
            "adaptive_cbit_max": 4,
            "adaptive_cbit_idle_guard": 0.6,
            "enable_multibit_fallback": True,
            "fallback_max_bits": 2,
        },
        "year": 26,
        "style_id": 0,
    },
    'SGCT': {
        "class": OCGHLCTPBAlgorithm,
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
        "year": 26,
        "style_id": 1,
    },
    'DRCT': {
        "class": DRCTFinalAlgorithm,
        "config": {
            "check_bits": 4,
            "answer_bits": 2,
            "check_mode": "random",
            "paper_timing": False,
            "include_reader_cmd_base_bits": True,
        },
        "year": 25,
        "style_id": 2,
    },
    'LAPCT': {
        "class": LAPCTAlgorithm,
        "config": {'k_threshold_divisor': 3.0},
        "year": 24,
        "style_id": 1,
    },
    'NLHQT(n=2)': {
        "class": NLHQTAlgorithm, 
        "config": {'n_way': 2},
        "year": 23,
        "style_id": 2,
    },
    'NLHQT(n=1)': {
        "class": NLHQTAlgorithm, 
        "config": {'n_way': 1},
        "year": 23,
        "style_id": 3,
    },
    'DQTA(k_max=3)': {
        "class": DQTAAlgorithm,
        "config": {'k_max': 3},
        "year": 19,
        "style_id": 4,
    },
    'EMDT': {
        "class": EMDTAlgorithm,
        "config": {},
        "year": 24,
        "style_id": 5,
    },
    'EAQ_CBB': {
        "class": EAQCBBAlgorithm,
        "config": {},
        "year": 23,
        "style_id": 6,
    },
    'HT_EEAC': {
        "class": HT_EEAC,
        "config": {},
        "year": 24,
        "style_id": 7,
    },
    'FHS_RAC': {
        "class": FHS_RAC,
        "config": {},
        "year": 21,
        "style_id": 8,
    },
    'ICT': {
        "class": ICT_Algorithm,
        "config": {},
        "year": 24,
        "style_id": 7,
    },
    'SD-CGQT': {
        "class": SDCGQTAlgorithm,
        "config": {},
        "year": 23,
        "style_id": 8,
    },
    'SUBF-CGDFSA': {
        "class": SUBF_CGDFSA_Algorithm,
        "config": {},
        "year": 24,
        "style_id": 9,
    },
}


