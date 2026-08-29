from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

import numpy as np

from Framework import (
    AlgorithmStepResult,
    CONSTANTS,
    Tag,
    TraditionalAlgorithmInterface,
    apply_ber_noise,
)
from Tool import RfidUtils
from _sgct_small_cluster_fallback import SGCTSmallClusterFallbackAlgorithm


@dataclass
class SGCTParams:
    probe_chunk_bits: int = 16
    d_target_dense: int = 8
    d_target_normal: int = 6
    d_target_skew: int = 4
    signature_d_min: int = 4
    signature_d_max: int = 8
    signature_slot_cap: int = 256
    signature_marker_bits: int = 1
    terminal_group_size: int = 1
    enable_suffix_terminal_verify: bool = True
    enable_signature_grouping: bool = True
    enable_low_d_fallback: bool = True
    enable_local_short_id: bool = True
    local_short_id_min_bits: int = 8
    enable_hash_short_id: bool = False
    hash_short_id_bits: int = 8
    hash_short_id_max_bits: int = 16
    enable_suffix_signature: bool = False
    enable_adaptive_suffix_signature: bool = False
    suffix_signature_root_only: bool = True
    suffix_signature_min_prefix_bits: int = 64
    suffix_signature_max_remaining_bits: int = 32
    suffix_signature_d_max: int = 12
    suffix_signature_slot_cap: int = 4096
    suffix_signature_min_tags_per_slot: float = 8.0
    suffix_signature_max_non_idle_ratio: float = 0.35
    suffix_signature_sequential_non_idle_ratio: float = 0.65
    suffix_signature_cost_margin: float = 1.2
    max_suffix_signature_trials_per_node: int = 1
    enable_small_cluster_guard: bool = False
    small_cluster_guard_max_tags: int = 128
    small_cluster_guard_prefix_bits: int = 64


@dataclass
class SGCTNode:
    tags: List[Tag]
    depth: int = 0
    constraint_len: int = 0
    collision_rich_streak: int = 0
    last_idle_ratio: float = 0.0
    suffix_signature_trials: int = 0
    trace: str = "root"


@dataclass
class SGCTPlan:
    tags: List[Tag] = field(default_factory=list)
    common_prefix: str = ""
    probe_offset: int = 0
    positions: List[int] = field(default_factory=list)
    target_d: int = 0
    suffix_signature: bool = False


class SGCTAlgorithm(TraditionalAlgorithmInterface):
    """Sparse-Grouping Collision Tree protocol implementation."""

    def __init__(self, tags_in_field: List[Tag], **kwargs):
        super().__init__(tags_in_field, **kwargs)
        self.params = SGCTParams(
            probe_chunk_bits=kwargs.get("probe_chunk_bits", 16),
            d_target_dense=kwargs.get("d_target_dense", 8),
            d_target_normal=kwargs.get("d_target_normal", 6),
            d_target_skew=kwargs.get("d_target_skew", 4),
            signature_d_min=kwargs.get("signature_d_min", 4),
            signature_d_max=kwargs.get("signature_d_max", 8),
            signature_slot_cap=kwargs.get("signature_slot_cap", 256),
            signature_marker_bits=kwargs.get("signature_marker_bits", 1),
            terminal_group_size=kwargs.get("terminal_group_size", 1),
            enable_suffix_terminal_verify=kwargs.get("enable_suffix_terminal_verify", True),
            enable_signature_grouping=kwargs.get("enable_signature_grouping", True),
            enable_low_d_fallback=kwargs.get("enable_low_d_fallback", True),
            enable_local_short_id=kwargs.get("enable_local_short_id", True),
            local_short_id_min_bits=kwargs.get("local_short_id_min_bits", 8),
            enable_hash_short_id=kwargs.get("enable_hash_short_id", False),
            hash_short_id_bits=kwargs.get("hash_short_id_bits", 8),
            hash_short_id_max_bits=kwargs.get("hash_short_id_max_bits", 16),
            enable_suffix_signature=kwargs.get("enable_suffix_signature", False),
            enable_adaptive_suffix_signature=kwargs.get("enable_adaptive_suffix_signature", False),
            suffix_signature_root_only=kwargs.get("suffix_signature_root_only", True),
            suffix_signature_min_prefix_bits=kwargs.get("suffix_signature_min_prefix_bits", 64),
            suffix_signature_max_remaining_bits=kwargs.get("suffix_signature_max_remaining_bits", 32),
            suffix_signature_d_max=kwargs.get("suffix_signature_d_max", 12),
            suffix_signature_slot_cap=kwargs.get("suffix_signature_slot_cap", 4096),
            suffix_signature_min_tags_per_slot=kwargs.get("suffix_signature_min_tags_per_slot", 8.0),
            suffix_signature_max_non_idle_ratio=kwargs.get("suffix_signature_max_non_idle_ratio", 0.35),
            suffix_signature_sequential_non_idle_ratio=kwargs.get("suffix_signature_sequential_non_idle_ratio", 0.65),
            suffix_signature_cost_margin=kwargs.get("suffix_signature_cost_margin", 1.2),
            max_suffix_signature_trials_per_node=kwargs.get("max_suffix_signature_trials_per_node", 1),
            enable_small_cluster_guard=kwargs.get("enable_small_cluster_guard", False),
            small_cluster_guard_max_tags=kwargs.get("small_cluster_guard_max_tags", 128),
            small_cluster_guard_prefix_bits=kwargs.get("small_cluster_guard_prefix_bits", 64),
        )
        self.id_length = len(tags_in_field[0].id) if tags_in_field else 0
        self.delegate = (
            SGCTSmallClusterFallbackAlgorithm(tags_in_field, **kwargs)
            if self._should_use_small_cluster_guard(tags_in_field)
            else None
        )
        self.queue: Deque[SGCTNode] = deque([SGCTNode(tags=list(tags_in_field))])
        self.current_node: Optional[SGCTNode] = None
        self.current_plan = SGCTPlan()
        self.current_mode = "PLANNING"
        self.current_groups: List[List[Tag]] = []
        self.exec_groups: List[List[Tag]] = []
        self.non_idle_groups: List[List[Tag]] = []
        self.group_cursor = 0
        self.pending_signature_reader_bits = 0.0
        self.current_positions: List[int] = []
        self.current_prefix_len = 0
        self.enable_monitoring = kwargs.get("enable_resource_monitoring", False)
        self.tag_response_counts: Dict[str, int] = {tag.id: 0 for tag in tags_in_field}

        self.metrics.update(
            {
                "progressive_probe_count": 0,
                "signature_grouping_trigger_count": 0,
                "local_short_id_trigger_count": 0,
                "signature_groups_pruned": 0,
                "sparse_signature_groups": 0,
                "signature_marker_bits": 0,
                "signature_marker_tag_bits": 0,
                "signature_non_idle_marker_count": 0,
                "signature_collision_groups": 0,
                "signature_singleton_groups": 0,
                "low_d_fallback_count": 0,
                "suffix_signature_trigger_count": 0,
                "hash_short_id_round_count": 0,
                "hash_short_id_split_count": 0,
                "hash_short_id_collision_groups": 0,
                "hash_short_id_singleton_groups": 0,
                "max_signature_d": 0,
                "epc_verification_count": 0,
                "verify_fail_count": 0,
                "avg_tag_responses": 0.0,
                "small_cluster_guard_count": 1 if self.delegate is not None else 0,
            }
        )

    def _should_use_small_cluster_guard(self, tags: List[Tag]) -> bool:
        if (
            not self.params.enable_small_cluster_guard
            or len(tags) > self.params.small_cluster_guard_max_tags
            or self.id_length < self.params.small_cluster_guard_prefix_bits
        ):
            return False
        prefix_bits = self.params.small_cluster_guard_prefix_bits
        buckets: Dict[str, int] = {}
        for tag in tags:
            prefix = tag.id[:prefix_bits]
            buckets[prefix] = buckets.get(prefix, 0) + 1
        counts = list(buckets.values())
        non_singleton_buckets = sum(1 for count in counts if count > 1)
        balanced_multi_prefix = max(counts) - min(counts) <= 1 if counts else False
        return (
            2 <= non_singleton_buckets <= max(2, len(tags) // 4)
            and balanced_multi_prefix
            and min(counts) >= 4
        )

    def _step_result(self, *args, **kwargs) -> AlgorithmStepResult:
        result = AlgorithmStepResult(*args, **kwargs)
        if self.enable_monitoring:
            result.internal_metrics = {"stack_depth": len(self.queue)}
        return result

    def is_finished(self) -> bool:
        if self.delegate is not None:
            finished = self.delegate.is_finished()
            self.metrics.update(self.delegate.metrics)
            self.metrics["small_cluster_guard_count"] = 1
            return finished
        finished = len(self.identified_tags) == len(self.tags_in_field)
        if finished:
            self._finalize_metrics()
        return finished

    def _finalize_metrics(self) -> None:
        counts = list(self.tag_response_counts.values())
        self.metrics["avg_tag_responses"] = float(np.mean(counts)) if counts else 0.0

    def _active_tags(self, tags: List[Tag]) -> List[Tag]:
        return [tag for tag in tags if tag.id not in self.identified_tags]

    def _record_tag_responses(self, tags: List[Tag]) -> None:
        for tag in tags:
            if tag.id in self.tag_response_counts:
                self.tag_response_counts[tag.id] += 1

    def perform_step(self) -> AlgorithmStepResult:
        if self.delegate is not None:
            return self.delegate.perform_step()
        if self.current_mode == "PLANNING":
            return self._planning_step()
        if self.current_mode == "PROGRESSIVE_PROBE":
            return self._probe_step()
        if self.current_mode == "BITMAP_EXEC":
            return self._signature_exec_step()
        return self._step_result("internal_op")

    def get_results(self):
        if self.delegate is not None:
            return self.delegate.get_results()
        return super().get_results()

    def get_active_tag_count(self) -> int:
        if self.delegate is not None:
            return self.delegate.get_active_tag_count()
        return super().get_active_tag_count()

    def _planning_step(self) -> AlgorithmStepResult:
        if not self.queue:
            self._finalize_metrics()
            return self._step_result("internal_op")

        self.current_node = self.queue.popleft()
        tags = self._active_tags(self.current_node.tags)
        if not tags:
            return self._step_result("internal_op")
        if len(tags) <= self.params.terminal_group_size:
            return self._verify_terminal_group(
                tags,
                reader_bits=CONSTANTS.READER_CMD_BASE_BITS,
                known_prefix_len=self.current_node.constraint_len,
            )

        tag_ids = [tag.id for tag in tags]
        common_prefix, _ = RfidUtils.get_collision_info(tag_ids)
        if self._should_use_suffix_signature(common_prefix):
            self.current_plan = SGCTPlan(
                tags=tags,
                common_prefix=common_prefix,
                probe_offset=len(common_prefix),
                positions=self._suffix_signature_positions(common_prefix),
                target_d=self._suffix_signature_target(common_prefix),
                suffix_signature=True,
            )
            self.metrics["suffix_signature_trigger_count"] += 1
            return self._prepare_signature_grouping()

        target_d = self._target_d_for_node(self.current_node)
        self.current_plan = SGCTPlan(
            tags=tags,
            common_prefix=common_prefix,
            probe_offset=len(common_prefix),
            target_d=target_d,
        )
        self.current_mode = "PROGRESSIVE_PROBE"
        return self._step_result("internal_op", operation_description="SGCT start progressive probe")

    def _should_use_suffix_signature(self, common_prefix: str, tags: Optional[List[Tag]] = None) -> bool:
        remaining = self.id_length - len(common_prefix)
        basic_gate = (
            self.params.enable_suffix_signature
            and (not self.params.suffix_signature_root_only or (self.current_node is not None and self.current_node.depth == 0))
            and len(common_prefix) >= self.params.suffix_signature_min_prefix_bits
            and 0 < remaining <= self.params.suffix_signature_max_remaining_bits
            and (
                self.current_node is None
                or self.current_node.suffix_signature_trials < self.params.max_suffix_signature_trials_per_node
            )
        )
        if not basic_gate:
            return False
        if not self.params.enable_adaptive_suffix_signature:
            return True
        if self.params.suffix_signature_min_tags_per_slot <= 0:
            return True

        node = self.current_node
        observed_collision_rich = node is not None and node.collision_rich_streak >= 1
        observed_sparse_marker = node is not None and node.last_idle_ratio >= (
            1.0 - self.params.suffix_signature_max_non_idle_ratio
        )
        observed_sequential_like = node is not None and node.depth > 0 and node.last_idle_ratio <= (
            1.0 - self.params.suffix_signature_sequential_non_idle_ratio
        )
        root_long_prefix_probe = node is not None and node.depth == 0 and node.suffix_signature_trials == 0
        long_observable_prefix = len(common_prefix) >= self.params.suffix_signature_min_prefix_bits
        compact_suffix = remaining <= self.params.suffix_signature_max_remaining_bits
        retry_after_verify_fail = self.metrics.get("verify_fail_count", 0) > 0
        return (
            long_observable_prefix
            and compact_suffix
            and not observed_sequential_like
            and (
                root_long_prefix_probe
                or observed_collision_rich
                or observed_sparse_marker
                or retry_after_verify_fail
            )
        )

    def _suffix_signature_target(self, common_prefix: str) -> int:
        remaining = self.id_length - len(common_prefix)
        target = min(remaining, self.params.suffix_signature_d_max)
        while (1 << target) > self.params.suffix_signature_slot_cap and target > 1:
            target -= 1
        return max(1, target)

    def _suffix_signature_positions(self, common_prefix: str) -> List[int]:
        start = len(common_prefix)
        target = self._suffix_signature_target(common_prefix)
        return list(range(start, min(self.id_length, start + target)))

    def _target_d_for_node(self, node: SGCTNode) -> int:
        if node.last_idle_ratio >= 0.6:
            target = self.params.d_target_skew
        elif node.collision_rich_streak > 0 or node.last_idle_ratio <= 0.1:
            target = self.params.d_target_dense
        else:
            target = self.params.d_target_normal
        target = min(target, self.params.signature_d_max)
        while (1 << target) > self.params.signature_slot_cap and target > 1:
            target -= 1
        return max(1, target)

    def _probe_step(self) -> AlgorithmStepResult:
        plan = self.current_plan
        if len(plan.positions) >= plan.target_d or plan.probe_offset >= self.id_length:
            return self._prepare_signature_grouping()

        start = plan.probe_offset
        end = min(start + self.params.probe_chunk_bits, self.id_length)
        chunk_len = end - start
        if chunk_len <= 0:
            return self._prepare_signature_grouping()

        chunks = [tag.id[start:end] for tag in plan.tags]
        noisy_chunks = [apply_ber_noise(chunk, self.ber) for chunk in chunks]
        _, relative_positions = RfidUtils.get_collision_info(noisy_chunks)
        for rel_pos in relative_positions:
            abs_pos = start + rel_pos
            if abs_pos not in plan.positions:
                plan.positions.append(abs_pos)

        plan.probe_offset = end
        self.metrics["progressive_probe_count"] += 1
        self.metrics["collision_slots"] += 1
        self._record_tag_responses(plan.tags)
        return self._step_result(
            "collision_slot",
            reader_bits=CONSTANTS.READER_CMD_BASE_BITS + start,
            tag_bits=len(plan.tags) * chunk_len,
            expected_max_tag_bits=chunk_len,
            operation_description="SGCT progressive collision-bit probe",
        )

    def _prepare_signature_grouping(self) -> AlgorithmStepResult:
        plan = self.current_plan
        if not plan.positions:
            self._enqueue_or_verify(plan.tags, trace_suffix="nosplit")
            self.current_mode = "PLANNING"
            return self._step_result("internal_op", operation_description="SGCT no collision positions")

        d_cap = self.params.suffix_signature_d_max if plan.suffix_signature else self.params.signature_d_max
        d_to_use = min(len(plan.positions), plan.target_d, d_cap)
        d_to_use = max(1, d_to_use)
        if d_to_use < self.params.signature_d_min and self.params.enable_low_d_fallback:
            self.metrics["low_d_fallback_count"] += 1
            self._enqueue_low_d_groups(plan, plan.positions[:d_to_use])
            self.current_mode = "PLANNING"
            return self._step_result("internal_op", operation_description="SGCT low-d selected split fallback")

        positions = plan.positions[:d_to_use]
        groups = [[] for _ in range(1 << d_to_use)]
        for tag in plan.tags:
            index = int("".join(tag.id[pos] for pos in positions), 2)
            groups[index].append(tag)

        self.current_groups = groups
        if self.params.enable_signature_grouping:
            self.non_idle_groups = [group for group in groups if group]
            idle_groups = len(groups) - len(self.non_idle_groups)
            self.metrics["signature_groups_pruned"] += idle_groups
            exec_groups = self.non_idle_groups
        else:
            self.non_idle_groups = [group for group in groups if group]
            exec_groups = self.current_groups
        self.metrics["signature_grouping_trigger_count"] += 1
        self.metrics["sparse_signature_groups"] += len(self.non_idle_groups)
        self.metrics["signature_collision_groups"] += sum(1 for group in self.non_idle_groups if len(group) > 1)
        self.metrics["signature_singleton_groups"] += sum(1 for group in self.non_idle_groups if len(group) == 1)
        marker_tag_bits = len(plan.tags) * self.params.signature_marker_bits
        non_idle_marker_count = len(self.non_idle_groups)
        self.metrics["signature_marker_bits"] += marker_tag_bits
        self.metrics["signature_marker_tag_bits"] += marker_tag_bits
        self.metrics["signature_non_idle_marker_count"] += non_idle_marker_count
        self.metrics["max_signature_d"] = max(self.metrics["max_signature_d"], d_to_use)
        if self.params.enable_local_short_id and d_to_use >= self.params.local_short_id_min_bits:
            self.metrics["local_short_id_trigger_count"] += 1

        self.current_positions = positions
        self.current_prefix_len = len(plan.common_prefix)
        self.group_cursor = 0
        self.pending_signature_reader_bits = (
            CONSTANTS.READER_CMD_BASE_BITS + len(plan.common_prefix) + 5 + 7 * d_to_use
        )
        self.current_mode = "BITMAP_EXEC"
        self.exec_groups = exec_groups

        return self._step_result(
            "collision_slot",
            reader_bits=self.pending_signature_reader_bits,
            tag_bits=marker_tag_bits,
            expected_max_tag_bits=1 << d_to_use,
            operation_description="SGCT sparse signature grouping split",
        )

    def _enqueue_low_d_groups(self, plan: SGCTPlan, positions: List[int]) -> None:
        if not positions:
            self._enqueue_or_verify(plan.tags, trace_suffix="lowd")
            return
        groups = [[] for _ in range(1 << len(positions))]
        for tag in plan.tags:
            index = int("".join(tag.id[pos] for pos in positions), 2)
            groups[index].append(tag)
        for cursor, group in enumerate(reversed([group for group in groups if group])):
            self.queue.appendleft(
                SGCTNode(
                    tags=list(group),
                    depth=(self.current_node.depth + 1 if self.current_node else 0),
                    constraint_len=len(plan.common_prefix),
                    suffix_signature_trials=(
                        self.current_node.suffix_signature_trials + 1
                        if self.current_node and plan.suffix_signature
                        else (self.current_node.suffix_signature_trials if self.current_node else 0)
                    ),
                    trace=f"{self.current_node.trace}/LOWD:{cursor}" if self.current_node else f"LOWD:{cursor}",
                )
            )

    def _signature_exec_step(self) -> AlgorithmStepResult:
        self.pending_signature_reader_bits = 0.0
        groups = self.exec_groups
        if self.group_cursor >= len(groups):
            self.current_mode = "PLANNING"
            return self._step_result("internal_op")

        group = groups[self.group_cursor]
        cursor = self.group_cursor
        self.group_cursor += 1
        if not group:
            self.metrics["idle_slots"] += 1
            result = self._step_result(
                "idle_slot",
                reader_bits=CONSTANTS.QUERYREP_CMD_BITS,
                expected_max_tag_bits=0,
                operation_description="SGCT pruned sparse signature child",
            )
        elif len(group) <= self.params.terminal_group_size:
            result = self._verify_terminal_group(
                group,
                reader_bits=CONSTANTS.QUERYREP_CMD_BITS,
                known_prefix_len=self.current_prefix_len,
            )
        else:
            self.metrics["collision_slots"] += 1
            self._record_tag_responses(group)
            expected_bits = self._local_short_id_bits()
            if self.params.enable_local_short_id and self.params.enable_hash_short_id:
                self._enqueue_hash_short_id_groups(group, cursor, expected_bits)
                description = "SGCT hash short-ID child split"
            else:
                self._enqueue_child(group, cursor)
                description = "SGCT non-terminal signature child"
            result = self._step_result(
                "collision_slot",
                reader_bits=CONSTANTS.QUERYREP_CMD_BITS,
                tag_bits=len(group) * expected_bits,
                expected_max_tag_bits=expected_bits,
                operation_description=description,
            )

        if self.group_cursor >= len(groups):
            self.current_mode = "PLANNING"
        return result

    def _local_short_id_bits(self) -> int:
        remaining_bits = max(1, self.id_length - self.current_prefix_len)
        if not self.params.enable_local_short_id:
            return remaining_bits
        if self.params.enable_hash_short_id:
            self.metrics["hash_short_id_round_count"] += 1
            return max(1, min(remaining_bits, self.params.hash_short_id_bits, self.params.hash_short_id_max_bits))
        selected_bits = max(len(self.current_positions), self.params.local_short_id_min_bits)
        return max(1, min(remaining_bits, selected_bits))

    def _hash_short_id_value(self, tag_id: str, cursor: int, bits: int) -> int:
        if bits <= 0:
            return 0
        payload = f"{tag_id}|{self.current_node.trace if self.current_node else 'root'}|{cursor}|{bits}"
        import binascii
        return binascii.crc_hqx(payload.encode("ascii"), 0xFFFF) % (1 << bits)

    def _enqueue_hash_short_id_groups(self, group: List[Tag], cursor: int, bits: int) -> None:
        assert self.current_node is not None
        self.metrics["hash_short_id_split_count"] += 1
        buckets: Dict[int, List[Tag]] = {}
        for tag in group:
            buckets.setdefault(self._hash_short_id_value(tag.id, cursor, bits), []).append(tag)
        self.metrics["hash_short_id_collision_groups"] += sum(1 for child in buckets.values() if len(child) > 1)
        self.metrics["hash_short_id_singleton_groups"] += sum(1 for child in buckets.values() if len(child) == 1)
        for index, child in enumerate(sorted(buckets.values(), key=lambda tags: tags[0].id, reverse=True)):
            self.queue.appendleft(
                SGCTNode(
                    tags=list(child),
                    depth=self.current_node.depth + 1,
                    constraint_len=self.current_prefix_len,
                    suffix_signature_trials=self.current_node.suffix_signature_trials,
                    collision_rich_streak=(
                        self.current_node.collision_rich_streak + 1 if len(child) > 1 else 0
                    ),
                    last_idle_ratio=0.0,
                    trace=f"{self.current_node.trace}/HASH:{cursor}:{index}",
                )
            )

    def _enqueue_or_verify(self, group: List[Tag], trace_suffix: str) -> None:
        self.queue.append(
            SGCTNode(
                tags=list(group),
                depth=(self.current_node.depth + 1 if self.current_node else 0),
                constraint_len=self.current_prefix_len,
                suffix_signature_trials=(self.current_node.suffix_signature_trials if self.current_node else 0),
                trace=f"{self.current_node.trace}/{trace_suffix}" if self.current_node else trace_suffix,
            )
        )

    def _enqueue_child(self, group: List[Tag], cursor: int) -> None:
        assert self.current_node is not None
        non_idle = len(self.non_idle_groups)
        total = 1 << len(self.current_positions)
        idle_ratio = 1.0 - (non_idle / total if total else 0.0)
        collision_rich = non_idle >= max(1, total // 4)
        self.queue.appendleft(
            SGCTNode(
                tags=list(group),
                depth=self.current_node.depth + 1,
                constraint_len=self.current_prefix_len,
                suffix_signature_trials=(
                    self.current_node.suffix_signature_trials + 1
                    if self.current_plan.suffix_signature
                    else self.current_node.suffix_signature_trials
                ),
                collision_rich_streak=self.current_node.collision_rich_streak + 1 if collision_rich else 0,
                last_idle_ratio=idle_ratio,
                trace=f"{self.current_node.trace}/PB:{cursor}",
            ),
        )

    def _verify_terminal_group(
        self,
        group: List[Tag],
        reader_bits: float,
        known_prefix_len: int = 0,
    ) -> AlgorithmStepResult:
        self.metrics["epc_verification_count"] += 1
        verify_reader_bits = reader_bits + CONSTANTS.ACK_CMD_BITS
        known_prefix_len = max(0, min(self.id_length, known_prefix_len))
        if not self.params.enable_suffix_terminal_verify:
            known_prefix_len = 0
        expected_bits = max(1, self.id_length - known_prefix_len)

        if len(group) == 1:
            tag = group[0]
            self._record_tag_responses(group)
            perfect_response = tag.id[known_prefix_len:]
            noisy_response = apply_ber_noise(perfect_response, self.ber)
            if perfect_response == noisy_response:
                self.identified_tags.add(tag.id)
                self.metrics["success_slots"] += 1
                return self._step_result(
                    "success_slot",
                    reader_bits=verify_reader_bits,
                    tag_bits=expected_bits,
                    expected_max_tag_bits=expected_bits,
                    operation_description="SGCT terminal EPC verified",
                )

        self.metrics["collision_slots"] += 1
        self.metrics["verify_fail_count"] += 1
        self._record_tag_responses(group)
        self.queue.appendleft(
            SGCTNode(
                tags=list(group),
                depth=(self.current_node.depth + 1 if self.current_node else 0),
                constraint_len=self.current_prefix_len,
                suffix_signature_trials=(self.current_node.suffix_signature_trials if self.current_node else 0),
                collision_rich_streak=1,
                trace=f"{self.current_node.trace}/verify_fail" if self.current_node else "verify_fail",
            ),
        )
        return self._step_result(
            "collision_slot",
            reader_bits=verify_reader_bits,
            tag_bits=len(group) * expected_bits,
            expected_max_tag_bits=expected_bits,
            operation_description="SGCT terminal EPC verify failed",
        )


