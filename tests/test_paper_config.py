from algorithm_base_config import ALGORITHM_LIBRARY, DISPLAY_NAMES, PAPER_ALGORITHMS
from SGCT import SGCTAlgorithm, SGCTParams


EXPECTED_PAPER_ALGORITHMS = [
    "SGCT",
    "DRCT",
    "LAPCT",
    "EMDT",
    "DQTA",
    "EAQ-CBB",
    "NLHQT(n=2)",
]

EXPECTED_SGCT_DEFAULTS = {
    "probe_chunk_bits": 16,
    "d_target_dense": 8,
    "d_target_normal": 6,
    "d_target_skew": 4,
    "signature_d_min": 4,
    "signature_d_max": 8,
    "signature_slot_cap": 256,
    "signature_marker_bits": 1,
    "local_short_id_min_bits": 8,
    "suffix_signature_root_only": True,
    "suffix_signature_min_prefix_bits": 64,
    "suffix_signature_max_remaining_bits": 32,
    "suffix_signature_d_max": 12,
    "suffix_signature_slot_cap": 4096,
    "max_suffix_signature_trials_per_node": 1,
}


def test_paper_algorithm_registry_is_exact_and_ordered():
    assert PAPER_ALGORITHMS == EXPECTED_PAPER_ALGORITHMS
    assert list(ALGORITHM_LIBRARY) == EXPECTED_PAPER_ALGORITHMS
    assert ALGORITHM_LIBRARY["SGCT"]["class"] is SGCTAlgorithm
    assert ALGORITHM_LIBRARY["DQTA"]["config"] == {"k_max": 3}
    assert ALGORITHM_LIBRARY["EAQ-CBB"]["display_name"] == "EAQ-CBB"
    assert ALGORITHM_LIBRARY["NLHQT(n=2)"]["config"] == {"n_way": 2}


def test_legacy_result_keys_map_to_paper_display_names():
    assert DISPLAY_NAMES["DQTA(k_max=3)"] == "DQTA"
    assert DISPLAY_NAMES["EAQ_CBB"] == "EAQ-CBB"
    assert DISPLAY_NAMES["SGCT(no_signature_grouping)"] == "SGCT (w/o marker pruning)"
    assert DISPLAY_NAMES["SGCT(no_local_short_id)"] == "SGCT (w/o local short-ID)"


def test_sgct_default_parameters_match_pre_cleanup_snapshot():
    params = SGCTParams()
    assert {
        name: getattr(params, name) for name in EXPECTED_SGCT_DEFAULTS
    } == EXPECTED_SGCT_DEFAULTS
