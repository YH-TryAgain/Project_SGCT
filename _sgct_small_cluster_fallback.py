import binascii
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from Framework import (
    AlgorithmStepResult,
    CONSTANTS,
    Tag,
    TraditionalAlgorithmInterface,
    apply_ber_noise,
)
from Tool import RfidUtils


@dataclass
class SGCTSmallClusterFallbackParams:
    f_default: int = 4
    f_escalated: int = 8
    r_max: int = 3
    rho: float = 0.5
    H_skew: int = 2
    theta_v: int = 2
    R_OVG: int = 1
    H_stop: int = 3
    seed_h: int = 0xACE1
    fallback_after_verify_fail: bool = False
    inspect_window_bits: int = 8
    ovg_min_prefix_bits: int = 16
    enable_check_gating: bool = True
    enable_ovg: bool = True
    enable_fused_check_window: bool = True
    fused_window_bits: int = 4
    enable_adaptive_fcw: bool = False
    adaptive_fused_window_bits: int = 8
    adaptive_fcw_min_bits: int = 2
    adaptive_fcw_max_bits: int = 16
    enable_prefix_stagnation: bool = True
    prefix_stagnation_threshold: int = 1
    prefix_stag_score_threshold: int = 2
    enable_repeated_pattern_trigger: bool = True
    repeated_pattern_threshold: int = 2
    enable_adaptive_cbit: bool = True
    adaptive_cbit_max: int = 4
    adaptive_cbit_idle_guard: float = 0.6
    enable_multibit_fallback: bool = True
    fallback_max_bits: int = 2
    split_policy: str = "HYBRID"


@dataclass
class SGCTFallbackNode:
    tags: List[Tag]
    depth: int = 0
    f: int = 4
    skew_streak: int = 0
    verify_fail_streak: int = 0
    no_progress_streak: int = 0
    ovg_retry: int = 0
    ovg_r_h: int = 2
    collision_rich_streak: int = 0
    fcw_bits: Optional[int] = None
    has_cached_window: bool = False
    cached_common_prefix: str = ""
    cached_collision_positions: List[int] = field(default_factory=list)
    cached_k_consec: int = 0
    constraint_len: int = 0
    prefix_stagnation_count: int = 0
    prefix_stag_score: int = 0
    last_collision_signature: Optional[Tuple[int, int, int, int]] = None
    repeated_collision_pattern_count: int = 0
    mode_hint: str = "AUTO"
    last_idle_ratio: float = 0.0
    trace: str = "root"


@dataclass
class SGCTFallbackObservation:
    kind: str
    tags: List[Tag] = field(default_factory=list)
    common_prefix: str = ""
    collision_positions: List[int] = field(default_factory=list)
    k_consec: int = 0


@dataclass
class LocalSplitStats:
    mode: str
    total_groups: int
    idle_groups: int
    non_idle_groups: int
    committed_count: int = 0
    verify_fail_count: int = 0
    collision_child_count: int = 0

    @property
    def idle_ratio(self) -> float:
        return self.idle_groups / self.total_groups if self.total_groups else 0.0


def _consecutive_collision_run(collision_positions: List[int]) -> int:
    if not collision_positions:
        return 0
    longest = 1
    current = 1
    for prev, pos in zip(collision_positions, collision_positions[1:]):
        if pos == prev + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _crc16_int(payload: str) -> int:
    return binascii.crc_hqx(payload.encode("ascii"), 0xFFFF)


def check_value(epc: str, seed: int, uid: str, f_bits: int) -> int:
    if f_bits <= 0:
        return 0
    return _crc16_int(f"{epc}|{seed}|{uid}") % (1 << f_bits)


def ovg_value(epc: str, seed: int, r_h: int) -> int:
    if r_h <= 0:
        return 0
    return _crc16_int(f"{epc}|{seed}") % (1 << r_h)


def _fallback_arg(node: SGCTFallbackNode, obs: SGCTFallbackObservation, p: SGCTSmallClusterFallbackParams) -> Dict:
    if not p.enable_multibit_fallback or len(obs.collision_positions) < 2:
        return {}
    fallback_bits = min(len(obs.collision_positions), max(1, p.fallback_max_bits))
    return {"positions": obs.collision_positions[:fallback_bits]}


def select_mode(node: SGCTFallbackNode, obs: SGCTFallbackObservation, p: SGCTSmallClusterFallbackParams) -> Tuple[str, Dict]:
    if node.mode_hint == "FALLBACK":
        return "FALLBACK", _fallback_arg(node, obs, p)

    if p.enable_ovg and node.mode_hint == "OVG" and node.ovg_retry < p.R_OVG:
        return "OVG", {"r_h": node.ovg_r_h}

    if (
        p.enable_ovg
        and p.enable_prefix_stagnation
        and node.prefix_stagnation_count >= p.prefix_stagnation_threshold
        and node.ovg_retry < p.R_OVG
        and len(obs.common_prefix) >= p.ovg_min_prefix_bits
    ):
        return "OVG", {"r_h": node.ovg_r_h}

    if (
        p.enable_ovg
        and p.enable_prefix_stagnation
        and node.prefix_stag_score >= p.prefix_stag_score_threshold
        and node.ovg_retry < p.R_OVG
        and len(obs.common_prefix) >= p.ovg_min_prefix_bits
    ):
        return "OVG", {"r_h": node.ovg_r_h}

    if (
        p.enable_ovg
        and p.enable_repeated_pattern_trigger
        and node.repeated_collision_pattern_count >= p.repeated_pattern_threshold
        and node.ovg_retry < p.R_OVG
        and len(obs.common_prefix) >= p.ovg_min_prefix_bits
    ):
        return "OVG", {"r_h": node.ovg_r_h}

    if node.no_progress_streak >= p.H_stop:
        return "FALLBACK", _fallback_arg(node, obs, p)

    if (
        p.enable_ovg
        and
        node.skew_streak >= p.H_skew
        and node.last_idle_ratio >= p.rho
        and node.ovg_retry < p.R_OVG
        and len(obs.common_prefix) >= p.ovg_min_prefix_bits
    ):
        return "OVG", {"r_h": node.ovg_r_h}

    if node.verify_fail_streak >= p.theta_v:
        return "PIVOT", {"pivot_len": 2, "preStr": "10"}

    if p.split_policy == "CBIT_ONLY":
        if obs.collision_positions:
            r = min(max(obs.k_consec, len(obs.collision_positions)), p.r_max)
            return "CBIT", {"r": max(1, r)}
        return "FALLBACK", {}

    if obs.k_consec >= 2:
        if (
            p.enable_adaptive_cbit
            and obs.k_consec >= 4
            and node.last_idle_ratio < p.adaptive_cbit_idle_guard
            and node.prefix_stagnation_count == 0
            and node.prefix_stag_score < p.prefix_stag_score_threshold
            and node.repeated_collision_pattern_count < p.repeated_pattern_threshold
            and node.skew_streak == 0
            and node.collision_rich_streak == 0
            and node.no_progress_streak == 0
            and node.verify_fail_streak == 0
            and node.ovg_retry == 0
        ):
            return "CBIT", {"r": min(obs.k_consec, p.adaptive_cbit_max)}
        return "CBIT", {"r": min(obs.k_consec, p.r_max)}

    if len(obs.collision_positions) >= 2:
        return "LOCK2", {"positions": obs.collision_positions[:2]}

    if len(obs.collision_positions) >= 1:
        return "LOCK1", {"positions": obs.collision_positions[:1]}

    return "PIVOT", {"pivot_len": 1, "preStr": "1"}


class SGCTSmallClusterFallbackAlgorithm(TraditionalAlgorithmInterface):
    def __init__(self, tags_in_field: List[Tag], **kwargs):
        super().__init__(tags_in_field, **kwargs)
        self.params = SGCTSmallClusterFallbackParams(
            f_default=kwargs.get("f_default", kwargs.get("f", 4)),
            f_escalated=kwargs.get("f_escalated", 8),
            r_max=kwargs.get("r_max", 3),
            rho=kwargs.get("rho", 0.5),
            H_skew=kwargs.get("H_skew", kwargs.get("Hskew", 2)),
            theta_v=kwargs.get("theta_v", 2),
            R_OVG=kwargs.get("R_OVG", kwargs.get("R_OVG", 1)),
            H_stop=kwargs.get("H_stop", 3),
            seed_h=kwargs.get("seed_h", 0xACE1),
            fallback_after_verify_fail=kwargs.get("fallback_after_verify_fail", False),
            inspect_window_bits=kwargs.get("inspect_window_bits", 8),
            ovg_min_prefix_bits=kwargs.get("ovg_min_prefix_bits", 16),
            enable_check_gating=kwargs.get("enable_check_gating", True),
            enable_ovg=kwargs.get("enable_ovg", True),
            enable_fused_check_window=kwargs.get("enable_fused_check_window", True),
            fused_window_bits=kwargs.get("fused_window_bits", 4),
            enable_adaptive_fcw=kwargs.get("enable_adaptive_fcw", False),
            adaptive_fused_window_bits=kwargs.get("adaptive_fused_window_bits", 8),
            adaptive_fcw_min_bits=kwargs.get("adaptive_fcw_min_bits", 2),
            adaptive_fcw_max_bits=kwargs.get("adaptive_fcw_max_bits", 16),
            enable_prefix_stagnation=kwargs.get("enable_prefix_stagnation", True),
            prefix_stagnation_threshold=kwargs.get("prefix_stagnation_threshold", 1),
            prefix_stag_score_threshold=kwargs.get("prefix_stag_score_threshold", 2),
            enable_repeated_pattern_trigger=kwargs.get("enable_repeated_pattern_trigger", True),
            repeated_pattern_threshold=kwargs.get("repeated_pattern_threshold", 2),
            enable_adaptive_cbit=kwargs.get("enable_adaptive_cbit", True),
            adaptive_cbit_max=kwargs.get("adaptive_cbit_max", 4),
            adaptive_cbit_idle_guard=kwargs.get("adaptive_cbit_idle_guard", 0.6),
            enable_multibit_fallback=kwargs.get("enable_multibit_fallback", True),
            fallback_max_bits=kwargs.get("fallback_max_bits", 2),
            split_policy=kwargs.get("split_policy", "HYBRID"),
        )
        self.id_length = len(tags_in_field[0].id) if tags_in_field else 0
        self.queue: List[SGCTFallbackNode] = [
            SGCTFallbackNode(tags=list(tags_in_field), f=self.params.f_default)
        ]
        self.current_node: Optional[SGCTFallbackNode] = None
        self.current_obs: Optional[SGCTFallbackObservation] = None
        self.current_mode: str = "POP_NODE"
        self.current_mode_arg: Dict = {}
        self.current_groups: List[List[Tag]] = []
        self.current_stats: Optional[LocalSplitStats] = None
        self.current_split_children: List[SGCTFallbackNode] = []
        self.group_cursor: int = 0
        self.pending_split_reader_bits: float = 0.0
        self.enable_monitoring = kwargs.get("enable_resource_monitoring", False)
        self.tag_response_counts: Dict[str, int] = {tag.id: 0 for tag in tags_in_field}

        self.metrics.update(
            {
                "epc_verification_count": 0,
                "verify_fail_count": 0,
                "ovg_trigger_count": 0,
                "hbmt_ovg_trigger_count": 0,
                "fallback_invocation_count": 0,
                "prefix_stagnation_trigger_count": 0,
                "prefix_stag_score_trigger_count": 0,
                "repeated_pattern_trigger_count": 0,
                "ovg_rehash_count": 0,
                "ovg_width_up_count": 0,
                "ovg_width_down_count": 0,
                "ovg_no_singleton_count": 0,
                "ovg_success_count": 0,
                "post_ovg_singleton_count": 0,
                "ovg_fallback_avoid_count": 0,
                "inspect_collision_count": 0,
                "fcw_cache_created_count": 0,
                "fcw_cache_hit_count": 0,
                "fcw_cache_hit_ratio": 0.0,
                "fcw_fast_path_count": 0,
                "fcw_width_up_count": 0,
                "fcw_width_down_count": 0,
                "adaptive_cbit_r4_count": 0,
                "multibit_fallback_count": 0,
                "mode_lock1_count": 0,
                "mode_lock2_count": 0,
                "mode_cbit_count": 0,
                "mode_pivot_count": 0,
                "mode_ovg_count": 0,
                "mode_fallback_count": 0,
                "fallback_invocation_ratio": 0.0,
            }
        )

    def _step_result(self, *args, **kwargs) -> AlgorithmStepResult:
        result = AlgorithmStepResult(*args, **kwargs)
        if self.enable_monitoring:
            result.internal_metrics = {"stack_depth": len(self.queue)}
        return result

    def is_finished(self) -> bool:
        finished = len(self.identified_tags) == len(self.tags_in_field)
        if finished:
            self._finalize_metrics()
        return finished

    def _finalize_metrics(self) -> None:
        counts = list(self.tag_response_counts.values())
        self.metrics["avg_tag_responses"] = float(np.mean(counts)) if counts else 0.0
        processed = (
            self.metrics["mode_lock1_count"]
            + self.metrics["mode_lock2_count"]
            + self.metrics["mode_cbit_count"]
            + self.metrics["mode_pivot_count"]
            + self.metrics["mode_ovg_count"]
            + self.metrics["mode_fallback_count"]
        )
        self.metrics["fallback_invocation_ratio"] = (
            self.metrics["fallback_invocation_count"] / processed if processed else 0.0
        )
        created = self.metrics.get("fcw_cache_created_count", 0)
        self.metrics["fcw_cache_hit_ratio"] = (
            self.metrics.get("fcw_cache_hit_count", 0) / created if created else 0.0
        )

    def _active_tags(self, tags: List[Tag]) -> List[Tag]:
        return [tag for tag in tags if tag.id not in self.identified_tags]

    def _inspect_node(self, node: SGCTFallbackNode) -> SGCTFallbackObservation:
        tags = self._active_tags(node.tags)
        if not tags:
            return SGCTFallbackObservation(kind="idle")
        if len(tags) == 1:
            return SGCTFallbackObservation(kind="singleton", tags=tags, common_prefix=tags[0].id)

        tag_ids = [tag.id for tag in tags]
        common_prefix, collision_positions = RfidUtils.get_collision_info(tag_ids)
        return SGCTFallbackObservation(
            kind="collision",
            tags=tags,
            common_prefix=common_prefix,
            collision_positions=collision_positions,
            k_consec=_consecutive_collision_run(collision_positions),
        )

    def _record_tag_responses(self, tags: List[Tag]) -> None:
        for tag in tags:
            if tag.id in self.tag_response_counts:
                self.tag_response_counts[tag.id] += 1

    def _inspect_cost(self, obs: SGCTFallbackObservation) -> AlgorithmStepResult:
        if obs.kind == "idle":
            self.metrics["idle_slots"] += 1
            return self._step_result(
                "idle_slot",
                reader_bits=CONSTANTS.READER_CMD_BASE_BITS,
                expected_max_tag_bits=0,
                operation_description="SGCT fallback inspect idle",
            )

        if obs.kind == "singleton":
            return self._verify_group(
                obs.tags,
                reader_bits=CONSTANTS.READER_CMD_BASE_BITS,
                include_check_bits=False,
            )

        self.metrics["collision_slots"] += 1
        self.metrics["inspect_collision_count"] += 1
        self._record_tag_responses(obs.tags)
        remaining_len = self.id_length - len(obs.common_prefix)
        inspect_bits = min(remaining_len, self.params.inspect_window_bits)
        return self._step_result(
            "collision_slot",
            reader_bits=CONSTANTS.READER_CMD_BASE_BITS + len(obs.common_prefix),
            tag_bits=len(obs.tags) * inspect_bits,
            expected_max_tag_bits=inspect_bits,
            operation_description="SGCT fallback inspect collision",
        )

    def perform_step(self) -> AlgorithmStepResult:
        if self.current_mode == "POP_NODE":
            if not self.queue:
                self._finalize_metrics()
                return self._step_result("internal_op")

            self.current_node = self.queue.pop(0)
            if (
                self.params.enable_ovg
                and self.current_node.mode_hint == "OVG"
                and self.current_node.ovg_retry < self.params.R_OVG
            ):
                active_tags = self._active_tags(self.current_node.tags)
                if len(active_tags) > 1:
                    self.current_obs = SGCTFallbackObservation(kind="collision", tags=active_tags)
                    self._plan_current_collision_node()
                    return self._step_result("internal_op")

            active_tags = self._active_tags(self.current_node.tags)
            if (
                self.current_node.has_cached_window
                and len(active_tags) > 1
                and self.current_node.cached_collision_positions
            ):
                self.metrics["fcw_cache_hit_count"] += 1
                self.current_obs = SGCTFallbackObservation(
                    kind="collision",
                    tags=active_tags,
                    common_prefix=self.current_node.cached_common_prefix,
                    collision_positions=list(self.current_node.cached_collision_positions),
                    k_consec=self.current_node.cached_k_consec,
                )
                self._plan_current_collision_node()
                return self._step_result("internal_op")

            self.current_obs = self._inspect_node(self.current_node)

            if self.current_obs.kind != "collision":
                return self._inspect_cost(self.current_obs)

            self.current_mode = "PLAN_SPLIT"
            return self._inspect_cost(self.current_obs)

        if self.current_mode == "PLAN_SPLIT":
            self._plan_current_collision_node()
            return self._step_result("internal_op")

        if self.current_mode == "EXEC_SPLIT":
            return self._execute_next_group()

        return self._step_result("internal_op")

    def _plan_current_collision_node(self) -> None:
        assert self.current_node is not None
        assert self.current_obs is not None
        mode, arg = select_mode(self.current_node, self.current_obs, self.params)
        self.current_mode_arg = arg
        self.current_mode = "EXEC_SPLIT"
        self.current_groups = self._make_groups(mode, arg, self.current_node, self.current_obs)
        self.group_cursor = 0
        self.current_split_children = []
        self.pending_split_reader_bits = self._split_reader_bits(mode, arg, self.current_obs)
        idle_groups = sum(1 for group in self.current_groups if not group)
        self.current_stats = LocalSplitStats(
            mode=mode,
            total_groups=len(self.current_groups),
            idle_groups=idle_groups,
            non_idle_groups=len(self.current_groups) - idle_groups,
        )
        self._record_mode(mode, arg)

    def _record_mode(self, mode: str, arg: Optional[Dict] = None) -> None:
        metric_map = {
            "LOCK1": "mode_lock1_count",
            "LOCK2": "mode_lock2_count",
            "CBIT": "mode_cbit_count",
            "PIVOT": "mode_pivot_count",
            "OVG": "mode_ovg_count",
            "FALLBACK": "mode_fallback_count",
        }
        self.metrics[metric_map[mode]] += 1
        if mode == "CBIT" and arg is not None and arg.get("r", 0) > self.params.r_max:
            self.metrics["adaptive_cbit_r4_count"] += 1
        if mode == "FALLBACK" and arg is not None and len(arg.get("positions", [])) > 1:
            self.metrics["multibit_fallback_count"] += 1
        if mode == "OVG":
            self.metrics["ovg_trigger_count"] += 1
            self.metrics["hbmt_ovg_trigger_count"] += 1
        if mode == "FALLBACK":
            self.metrics["fallback_invocation_count"] += 1

    def _split_reader_bits(self, mode: str, arg: Dict, obs: SGCTFallbackObservation) -> float:
        if mode in {"LOCK1", "LOCK2"}:
            return CONSTANTS.READER_CMD_BASE_BITS + len(obs.common_prefix) + 4 + 7 * len(arg["positions"])
        if mode == "CBIT":
            return CONSTANTS.READER_CMD_BASE_BITS + len(obs.common_prefix) + 4 + 4 * arg["r"]
        if mode == "OVG":
            return CONSTANTS.READER_CMD_BASE_BITS + len(obs.common_prefix) + 4 + 16 + arg["r_h"]
        if mode == "PIVOT":
            return CONSTANTS.READER_CMD_BASE_BITS + len(obs.common_prefix) + 4 + arg["pivot_len"]
        if mode == "FALLBACK" and arg.get("positions"):
            return CONSTANTS.READER_CMD_BASE_BITS + len(obs.common_prefix) + 4 + 7 * len(arg["positions"])
        return CONSTANTS.READER_CMD_BASE_BITS + len(obs.common_prefix) + 4

    def _make_groups(self, mode: str, arg: Dict, node: SGCTFallbackNode, obs: SGCTFallbackObservation) -> List[List[Tag]]:
        if mode in {"LOCK1", "LOCK2"}:
            positions = arg["positions"]
            groups = [[] for _ in range(1 << len(positions))]
            for tag in obs.tags:
                groups[int("".join(tag.id[pos] for pos in positions), 2)].append(tag)
            return groups

        if mode == "CBIT":
            positions = obs.collision_positions[: arg["r"]]
            groups = [[] for _ in range(1 << len(positions))]
            for tag in obs.tags:
                groups[int("".join(tag.id[pos] for pos in positions), 2)].append(tag)
            return groups

        if mode == "OVG":
            groups = [[] for _ in range(1 << arg["r_h"])]
            for tag in obs.tags:
                groups[ovg_value(tag.id, self.params.seed_h + node.ovg_retry, arg["r_h"])].append(tag)
            return groups

        if mode == "PIVOT":
            pivot_len = arg["pivot_len"]
            pre_str = arg["preStr"]
            start = len(obs.common_prefix)
            groups = [[], []]
            for tag in obs.tags:
                segment = tag.id[start : start + pivot_len].ljust(pivot_len, "0")
                groups[0 if segment < pre_str else 1].append(tag)
            return groups

        return self._make_fallback_groups(obs, arg)

    def _make_fallback_groups(self, obs: SGCTFallbackObservation, arg: Optional[Dict] = None) -> List[List[Tag]]:
        if not obs.collision_positions:
            return [obs.tags]
        positions = list((arg or {}).get("positions") or obs.collision_positions[:1])
        groups = [[] for _ in range(1 << len(positions))]
        for tag in obs.tags:
            groups[int("".join(tag.id[pos] for pos in positions), 2)].append(tag)
        return groups

    def _execute_next_group(self) -> AlgorithmStepResult:
        assert self.current_node is not None
        assert self.current_stats is not None

        if self.group_cursor >= len(self.current_groups):
            self._promote_unique_skew_child()
            self.current_mode = "POP_NODE"
            return self._step_result("internal_op")

        group = self.current_groups[self.group_cursor]
        self.group_cursor += 1
        reader_bits = self.pending_split_reader_bits
        self.pending_split_reader_bits = 0.0

        if not group:
            self.metrics["idle_slots"] += 1
            result = self._step_result(
                "idle_slot",
                reader_bits=reader_bits,
                expected_max_tag_bits=0,
                operation_description="SGCT fallback check-gated idle child",
            )
        else:
            result = self._classify_check_group(group, reader_bits)

        if self.group_cursor >= len(self.current_groups):
            self._promote_unique_skew_child()
            self.current_mode = "POP_NODE"

        return result

    def _promote_unique_skew_child(self) -> None:
        assert self.current_stats is not None
        assert self.current_obs is not None
        if (
            self.current_stats.mode == "OVG"
            or not self.params.enable_ovg
            or self.current_stats.collision_child_count != 1
            or self.current_stats.idle_groups < self.current_stats.total_groups - 2
            or len(self.current_obs.common_prefix) < self.params.ovg_min_prefix_bits
        ):
            return

        for child in self.current_split_children:
            if len(child.tags) > 1 and child.mode_hint != "FALLBACK" and child.ovg_retry < self.params.R_OVG:
                child.mode_hint = "OVG"
                child.skew_streak = max(child.skew_streak, self.params.H_skew)
                child.last_idle_ratio = max(child.last_idle_ratio, self.params.rho)
                return

    def _classify_check_group(self, group: List[Tag], reader_bits: float) -> AlgorithmStepResult:
        assert self.current_node is not None
        assert self.current_stats is not None

        if not self.params.enable_check_gating:
            return self._verify_group(
                group,
                reader_bits=reader_bits,
                tag_bits_prefix=0,
                include_check_bits=False,
            )

        f_bits = self.current_node.f
        fused_bits = self._effective_fused_window_bits()
        uid = f"{self.current_node.trace}|{self.current_stats.mode}|{self.group_cursor - 1}"
        check_values = {check_value(tag.id, self.params.seed_h, uid, f_bits) for tag in group}
        self._record_tag_responses(group)
        tag_check_bits = len(group) * (f_bits + fused_bits)

        if len(check_values) == 1:
            return self._verify_group(group, reader_bits=reader_bits, tag_bits_prefix=tag_check_bits)

        self.metrics["collision_slots"] += 1
        self.current_stats.collision_child_count += 1
        cached_obs = self._make_fused_cached_observation(group, fused_bits)
        if cached_obs is not None:
            self.metrics["fcw_cache_created_count"] += 1
        self._enqueue_child(group, verify_failed=False, cached_obs=cached_obs)
        return self._step_result(
            "collision_slot",
            reader_bits=reader_bits,
            tag_bits=tag_check_bits,
            expected_max_tag_bits=f_bits + fused_bits,
            operation_description="SGCT fallback check collision child",
        )

    def _effective_fused_window_bits(self) -> int:
        assert self.current_node is not None
        assert self.current_stats is not None
        if not self.params.enable_fused_check_window:
            return 0
        base_bits = self.params.fused_window_bits
        if not self.params.enable_adaptive_fcw:
            return base_bits
        if self._is_fast_fcw_path():
            self.metrics["fcw_fast_path_count"] += 1
            return base_bits
        node_bits = self.current_node.fcw_bits if self.current_node.fcw_bits is not None else base_bits
        in_skew_recovery = (
            self.current_stats.mode == "OVG"
            or self.current_node.mode_hint == "OVG"
            or self.current_node.prefix_stagnation_count > 0
            or self.current_node.prefix_stag_score >= self.params.prefix_stag_score_threshold
            or self.current_node.repeated_collision_pattern_count >= self.params.repeated_pattern_threshold
            or self.current_node.skew_streak >= self.params.H_skew
            or self.current_node.verify_fail_streak > 0
        )
        if in_skew_recovery:
            node_bits = max(node_bits, self.params.adaptive_fused_window_bits)
        return self._clamp_fcw_bits(node_bits)

    def _clamp_fcw_bits(self, bits: int) -> int:
        return min(self.params.adaptive_fcw_max_bits, max(self.params.adaptive_fcw_min_bits, bits))

    def _is_fast_fcw_path(self) -> bool:
        assert self.current_node is not None
        assert self.current_stats is not None
        return (
            self.current_stats.mode != "OVG"
            and self.current_node.mode_hint != "OVG"
            and self.current_node.prefix_stagnation_count == 0
            and self.current_node.prefix_stag_score == 0
            and self.current_node.repeated_collision_pattern_count == 0
            and self.current_node.skew_streak == 0
            and self.current_node.verify_fail_streak == 0
            and self.current_node.no_progress_streak == 0
        )

    def _make_fused_cached_observation(self, group: List[Tag], fused_bits: int) -> Optional[SGCTFallbackObservation]:
        if fused_bits <= 0 or len(group) <= 1:
            return None
        common_prefix, collision_positions = RfidUtils.get_collision_info([tag.id for tag in group])
        window_end = min(self.id_length, len(common_prefix) + fused_bits)
        cached_positions = [pos for pos in collision_positions if pos < window_end]
        if not cached_positions:
            return None
        return SGCTFallbackObservation(
            kind="collision",
            tags=list(group),
            common_prefix=common_prefix,
            collision_positions=cached_positions,
            k_consec=_consecutive_collision_run(cached_positions),
        )

    def _child_constraint_len(
        self,
        group: List[Tag],
        cached_obs: Optional[SGCTFallbackObservation],
    ) -> int:
        if cached_obs is not None:
            return len(cached_obs.common_prefix)
        if self.current_obs is None:
            return 0
        if len(group) <= 1:
            return self.id_length
        return len(self.current_obs.common_prefix)

    def _prefix_stagnation_count(
        self,
        group: List[Tag],
        cached_obs: Optional[SGCTFallbackObservation],
    ) -> int:
        if (
            not self.params.enable_prefix_stagnation
            or self.current_obs is None
            or len(group) <= 1
        ):
            return 0
        old_len = max(self.current_node.constraint_len, len(self.current_obs.common_prefix))
        new_len = self._child_constraint_len(group, cached_obs)
        collision_observed = cached_obs is None or bool(cached_obs.collision_positions)
        if collision_observed and new_len - old_len <= 1:
            return self.current_node.prefix_stagnation_count + 1
        return 0

    def _collision_signature(
        self,
        cached_obs: Optional[SGCTFallbackObservation],
    ) -> Optional[Tuple[int, int, int, int]]:
        if self.current_stats is None:
            return None
        collision_positions: List[int] = []
        k_consec = 0
        if cached_obs is not None:
            collision_positions = list(cached_obs.collision_positions)
            k_consec = cached_obs.k_consec
        elif self.current_obs is not None:
            collision_positions = list(self.current_obs.collision_positions)
            k_consec = self.current_obs.k_consec
        if not collision_positions:
            return None
        return (
            collision_positions[0],
            k_consec,
            self.current_stats.collision_child_count,
            self.current_stats.idle_groups,
        )

    def _repeated_collision_pattern_count(
        self,
        collision_signature: Optional[Tuple[int, int, int, int]],
    ) -> int:
        if (
            not self.params.enable_repeated_pattern_trigger
            or collision_signature is None
            or self.current_node is None
        ):
            return 0
        if collision_signature == self.current_node.last_collision_signature:
            return self.current_node.repeated_collision_pattern_count + 1
        return 1

    def _prefix_stag_score(
        self,
        group: List[Tag],
        cached_obs: Optional[SGCTFallbackObservation],
        prefix_stagnation_count: int,
        repeated_pattern_count: int,
    ) -> int:
        assert self.current_node is not None
        assert self.current_stats is not None
        if (
            not self.params.enable_prefix_stagnation
            or self.current_obs is None
            or len(group) <= 1
        ):
            return 0

        old_len = max(self.current_node.constraint_len, len(self.current_obs.common_prefix))
        new_len = self._child_constraint_len(group, cached_obs)
        prefix_gain = new_len - old_len
        score = self.current_node.prefix_stag_score

        if prefix_stagnation_count > 0:
            score += 1
        if self.current_stats.committed_count == 0 and self.current_stats.collision_child_count >= 1:
            score += 1
        if (
            self.current_stats.collision_child_count == 1
            and self.current_stats.idle_groups >= max(1, self.current_stats.total_groups - 2)
        ):
            score += 1
        if repeated_pattern_count >= self.params.repeated_pattern_threshold:
            score += 1
        if self.current_stats.committed_count > 0 or prefix_gain >= 2:
            score = max(0, score - 1)
        return max(0, score)

    def _next_fcw_bits(
        self,
        prefix_stag_score: int,
        prefix_score_triggered: bool,
        repeated_pattern_triggered: bool,
    ) -> Optional[int]:
        assert self.current_node is not None
        assert self.current_stats is not None
        if not self.params.enable_adaptive_fcw:
            return self.current_node.fcw_bits

        base_bits = self.params.fused_window_bits
        current_bits = self.current_node.fcw_bits if self.current_node.fcw_bits is not None else base_bits
        high_risk = (
            prefix_score_triggered
            or repeated_pattern_triggered
            or self.current_stats.mode == "OVG"
            or self.current_stats.verify_fail_count > 0
        )
        idle_rich = (
            self.current_stats.idle_groups >= max(1, self.current_stats.total_groups // 2)
            and self.current_stats.collision_child_count <= 1
            and self.current_stats.committed_count == 0
        )

        if high_risk:
            next_bits = self._clamp_fcw_bits(max(current_bits * 2, self.params.adaptive_fused_window_bits))
        elif idle_rich:
            next_bits = self._clamp_fcw_bits(max(base_bits, current_bits // 2))
        else:
            next_bits = base_bits

        if next_bits > current_bits:
            self.metrics["fcw_width_up_count"] += 1
        elif next_bits < current_bits:
            self.metrics["fcw_width_down_count"] += 1
        return next_bits

    def _verify_group(
        self,
        group: List[Tag],
        reader_bits: float = 0.0,
        tag_bits_prefix: float = 0.0,
        include_check_bits: bool = True,
    ) -> AlgorithmStepResult:
        self.metrics["epc_verification_count"] += 1
        verify_reader_bits = reader_bits + CONSTANTS.ACK_CMD_BITS

        expected_bits = self.id_length
        if len(group) == 1:
            tag = group[0]
            self._record_tag_responses(group)
            perfect_response = tag.id
            noisy_response = apply_ber_noise(perfect_response, self.ber)
            if perfect_response == noisy_response:
                self.identified_tags.add(tag.id)
                self.metrics["success_slots"] += 1
                if self.current_stats is not None:
                    self.current_stats.committed_count += 1
                return self._step_result(
                    "success_slot",
                    reader_bits=verify_reader_bits,
                    tag_bits=tag_bits_prefix + expected_bits,
                    expected_max_tag_bits=expected_bits,
                    operation_description="SGCT fallback EPC verified singleton",
                )

        self.metrics["collision_slots"] += 1
        self.metrics["verify_fail_count"] += 1
        if self.current_stats is not None:
            self.current_stats.verify_fail_count += 1
            self.current_stats.collision_child_count += 1
        self._enqueue_child(group, verify_failed=True)
        return self._step_result(
            "collision_slot",
            reader_bits=verify_reader_bits,
            tag_bits=tag_bits_prefix + len(group) * expected_bits,
            expected_max_tag_bits=expected_bits,
            operation_description="SGCT fallback apparent singleton failed EPC verify",
        )

    def _enqueue_child(
        self,
        group: List[Tag],
        verify_failed: bool,
        cached_obs: Optional[SGCTFallbackObservation] = None,
    ) -> None:
        assert self.current_node is not None
        assert self.current_stats is not None
        if not group:
            return

        idle_ratio = self.current_stats.idle_ratio
        ovg_retry = self.current_node.ovg_retry
        skewed = len(group) > 1 and idle_ratio >= self.params.rho
        no_progress_event = (
            self.current_stats.committed_count == 0
            and (
                (
                    self.current_stats.collision_child_count == 1
                    and self.current_stats.idle_groups >= self.current_stats.total_groups - 2
                )
                or self.current_stats.collision_child_count >= self.current_stats.total_groups
            )
        )
        no_progress = self.current_node.no_progress_streak + 1 if no_progress_event else 0
        collision_rich = self.current_stats.collision_child_count >= max(1, self.current_stats.total_groups // 2)
        collision_rich_streak = self.current_node.collision_rich_streak + 1 if collision_rich else 0
        mode_hint = "AUTO"
        ovg_r_h = self.current_node.ovg_r_h
        child_constraint_len = self._child_constraint_len(group, cached_obs)
        prefix_stagnation_count = self._prefix_stagnation_count(group, cached_obs)
        collision_signature = self._collision_signature(cached_obs)
        repeated_pattern_count = self._repeated_collision_pattern_count(collision_signature)
        prefix_stag_score = self._prefix_stag_score(
            group,
            cached_obs,
            prefix_stagnation_count,
            repeated_pattern_count,
        )
        prefix_stagnated = (
            self.params.enable_ovg
            and self.params.enable_prefix_stagnation
            and prefix_stagnation_count >= self.params.prefix_stagnation_threshold
            and child_constraint_len >= self.params.ovg_min_prefix_bits
            and ovg_retry < self.params.R_OVG
        )
        prefix_score_triggered = (
            self.params.enable_ovg
            and self.params.enable_prefix_stagnation
            and prefix_stag_score >= self.params.prefix_stag_score_threshold
            and child_constraint_len >= self.params.ovg_min_prefix_bits
            and ovg_retry < self.params.R_OVG
        )
        repeated_pattern_triggered = (
            self.params.enable_ovg
            and self.params.enable_repeated_pattern_trigger
            and repeated_pattern_count >= self.params.repeated_pattern_threshold
            and child_constraint_len >= self.params.ovg_min_prefix_bits
            and ovg_retry < self.params.R_OVG
        )
        fcw_bits = self._next_fcw_bits(
            prefix_stag_score,
            prefix_score_triggered,
            repeated_pattern_triggered,
        )
        if self.current_stats.mode == "OVG":
            ovg_retry += 1
            if self.current_stats.committed_count > 0:
                self.metrics["ovg_success_count"] += 1
                self.metrics["post_ovg_singleton_count"] += self.current_stats.committed_count
            if self.current_stats.committed_count == 0:
                self.metrics["ovg_no_singleton_count"] += 1
            if self.current_stats.collision_child_count >= max(2, self.current_stats.total_groups // 2):
                if ovg_r_h < 3:
                    self.metrics["ovg_width_up_count"] += 1
                ovg_r_h = min(3, ovg_r_h + 1)
            elif self.current_stats.idle_groups >= max(1, self.current_stats.total_groups // 2):
                if ovg_r_h > 1:
                    self.metrics["ovg_width_down_count"] += 1
                ovg_r_h = max(1, ovg_r_h - 1)
            if (
                self.current_stats.committed_count == 0
                and self.current_stats.collision_child_count == 1
                and self.current_stats.idle_groups >= self.current_stats.total_groups - 2
            ):
                self.metrics["ovg_rehash_count"] += 1
        if self.current_stats.mode == "FALLBACK":
            no_progress = 0
        if prefix_score_triggered:
            self.metrics["prefix_stag_score_trigger_count"] += 1
        if repeated_pattern_triggered:
            self.metrics["repeated_pattern_trigger_count"] += 1
        if verify_failed and self.params.fallback_after_verify_fail:
            mode_hint = "FALLBACK"
        elif self.current_stats.mode == "OVG" and ovg_retry < self.params.R_OVG and self.current_stats.committed_count == 0:
            mode_hint = "OVG"
            self.metrics["ovg_fallback_avoid_count"] += 1
        elif prefix_stagnated:
            mode_hint = "OVG"
            self.metrics["prefix_stagnation_trigger_count"] += 1
        elif prefix_score_triggered:
            mode_hint = "OVG"
        elif repeated_pattern_triggered:
            mode_hint = "OVG"
        elif ovg_retry >= self.params.R_OVG or no_progress >= self.params.H_stop:
            mode_hint = "FALLBACK"

        child = SGCTFallbackNode(
            tags=list(group),
            depth=self.current_node.depth + 1,
            f=self.params.f_escalated if verify_failed else self.current_node.f,
            skew_streak=self.current_node.skew_streak + 1 if skewed else 0,
            verify_fail_streak=self.current_node.verify_fail_streak + 1 if verify_failed else 0,
            no_progress_streak=no_progress,
            ovg_retry=ovg_retry,
            ovg_r_h=ovg_r_h,
            collision_rich_streak=collision_rich_streak,
            fcw_bits=fcw_bits,
            has_cached_window=cached_obs is not None,
            cached_common_prefix=cached_obs.common_prefix if cached_obs is not None else "",
            cached_collision_positions=list(cached_obs.collision_positions) if cached_obs is not None else [],
            cached_k_consec=cached_obs.k_consec if cached_obs is not None else 0,
            constraint_len=child_constraint_len,
            prefix_stagnation_count=prefix_stagnation_count,
            prefix_stag_score=prefix_stag_score,
            last_collision_signature=collision_signature,
            repeated_collision_pattern_count=repeated_pattern_count,
            mode_hint=mode_hint,
            last_idle_ratio=idle_ratio,
            trace=f"{self.current_node.trace}/{self.current_stats.mode}:{self.group_cursor - 1}",
        )
        self.queue.append(child)
        self.current_split_children.append(child)

