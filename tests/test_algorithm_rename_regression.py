"""Characterization tests that protect SGCT/DRCT during module normalization."""

import hashlib
import json

from Framework import Tag, calculate_time_delta, run_simulation_with_tags
from DRCT import DRCTAlgorithm
from SGCT import SGCTAlgorithm


SGCT_IDS = (
    "00000000",
    "00000011",
    "00001100",
    "00001111",
    "00110000",
    "00110011",
    "00111100",
    "00111111",
)
SGCT_CONFIG = {
    "d_target_dense": 6,
    "d_target_normal": 4,
    "signature_d_min": 3,
    "terminal_group_size": 1,
    "enable_resource_monitoring": True,
}
SGCT_EXPECTED_DIGEST = "ba48adf984ee289c7f0d49d82bc9796341b5c17721aac3d925d97a91a399275f"

DRCT_IDS = (
    "0010010",
    "0110001",
    "0110110",
    "1001110",
    "1010101",
    "1100110",
)
DRCT_CONFIG = {
    "check_mode": "random",
    "check_seed": 7,
    "enable_resource_monitoring": True,
}
DRCT_EXPECTED_DIGEST = "1c460130ef9fca030ee4ede0f9fab6dc1b75742b53ee454ebbc60d2e171ade3f"


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    if hasattr(value, "item"):
        return value.item()
    return value


def _behavior_snapshot(algorithm_class, identities, config):
    tags = [Tag(identity) for identity in identities]
    result = run_simulation_with_tags(tags, algorithm_class, config)
    algorithm = algorithm_class([Tag(identity) for identity in identities], **config)
    trace = []
    while not algorithm.is_finished():
        step = algorithm.perform_step()
        trace.append(
            {
                "operation_type": step.operation_type,
                "reader_bits": step.reader_bits,
                "tag_bits": step.tag_bits,
                "expected_max_tag_bits": step.expected_max_tag_bits,
                "operation_description": step.operation_description,
                "override_time_us": step.override_time_us,
                "internal_metrics": step.internal_metrics,
                "response_windows_bits": step.response_windows_bits,
                "time_us": calculate_time_delta(step),
            }
        )
    return _json_safe(
        {
            "result": result,
            "identified": algorithm.get_results(),
            "metrics": algorithm.metrics,
            "trace": trace,
        }
    )


def _digest(snapshot):
    encoded = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def test_legacy_sgct_behavior_snapshot_is_deterministic_and_complete():
    first = _behavior_snapshot(SGCTAlgorithm, SGCT_IDS, SGCT_CONFIG)
    second = _behavior_snapshot(SGCTAlgorithm, SGCT_IDS, SGCT_CONFIG)

    assert first == second
    assert _digest(first) == SGCT_EXPECTED_DIGEST
    assert first["result"] | {
        "identified_tags_count": 8,
        "total_protocol_time_us": 4950.0,
        "total_reader_bits": 271.0,
        "total_tag_bits": 104.0,
        "total_steps": 11,
        "success_slots": 8,
        "idle_slots": 0,
        "collision_slots": 1,
    } == first["result"]


def test_legacy_drct_behavior_snapshot_captures_seeded_random_path():
    first = _behavior_snapshot(DRCTAlgorithm, DRCT_IDS, DRCT_CONFIG)
    second = _behavior_snapshot(DRCTAlgorithm, DRCT_IDS, DRCT_CONFIG)

    assert first == second
    assert _digest(first) == DRCT_EXPECTED_DIGEST
    assert first["result"] | {
        "identified_tags_count": 6,
        "total_protocol_time_us": 3871.25,
        "total_reader_bits": 196.0,
        "total_tag_bits": 108.0,
        "total_steps": 21,
        "success_slots": 6,
        "idle_slots": 2,
        "collision_slots": 6,
        "drct_random_check_count": 20,
    } == first["result"]
