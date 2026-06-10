from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from Framework import AlgorithmStepResult, CONSTANTS, Tag, TraditionalAlgorithmInterface
from Tool import RfidUtils


@dataclass
class ICTState:
    prefix: str
    tags: List[Tag]


class ICT_Algorithm(TraditionalAlgorithmInterface):
    """Deterministic prefix-tree implementation of Improved Collision Tree.

    The original project version used tag-side counters, but it could drop
    unresolved tags and leave the simulator spinning after the stack emptied.
    This version keeps the ICT interface and models collision-tree progression
    with prefix states, preserving the no-starvation property expected from a
    deterministic tree anti-collision protocol.
    """

    def __init__(self, tags_in_field: List[Tag], **kwargs):
        super().__init__(tags_in_field, **kwargs)
        self.id_length = len(tags_in_field[0].id) if tags_in_field else 0
        self.stack: List[ICTState] = [ICTState(prefix="", tags=list(tags_in_field))]
        self.tag_response_counts: Dict[str, int] = {tag.id: 0 for tag in tags_in_field}
        self.enable_monitoring = kwargs.get("enable_resource_monitoring", False)

    def _step_result(self, *args, **kwargs) -> AlgorithmStepResult:
        result = AlgorithmStepResult(*args, **kwargs)
        if self.enable_monitoring:
            result.internal_metrics = {"stack_depth": len(self.stack)}
        return result

    def is_finished(self) -> bool:
        finished = len(self.identified_tags) == len(self.tags_in_field)
        if finished and "avg_tag_responses" not in self.metrics:
            counts = list(self.tag_response_counts.values())
            self.metrics["avg_tag_responses"] = float(np.mean(counts)) if counts else 0.0
        return finished

    def perform_step(self) -> AlgorithmStepResult:
        if not self.stack:
            return self._step_result("internal_op", operation_description="ICT finished")

        state = self.stack.pop(0)
        tags = [tag for tag in state.tags if tag.id not in self.identified_tags]

        if not tags:
            self.metrics["idle_slots"] += 1
            return self._step_result(
                "idle_slot",
                reader_bits=CONSTANTS.READER_CMD_BASE_BITS + len(state.prefix),
                expected_max_tag_bits=0,
                operation_description=f"ICT idle prefix {state.prefix}",
            )

        if len(tags) == 1:
            tag = tags[0]
            self.tag_response_counts[tag.id] += 1
            self.identified_tags.add(tag.id)
            self.metrics["success_slots"] += 1
            remaining_len = max(0, self.id_length - len(state.prefix))
            return self._step_result(
                "success_slot",
                reader_bits=CONSTANTS.READER_CMD_BASE_BITS + len(state.prefix),
                tag_bits=remaining_len,
                expected_max_tag_bits=remaining_len,
                operation_description=f"ICT identified {tag.id}",
            )

        for tag in tags:
            self.tag_response_counts[tag.id] += 1

        common_prefix, collision_positions = RfidUtils.get_collision_info([tag.id for tag in tags])
        if not collision_positions:
            for tag in tags:
                self.identified_tags.add(tag.id)
                self.metrics["success_slots"] += 1
            return self._step_result(
                "success_slot",
                reader_bits=CONSTANTS.READER_CMD_BASE_BITS + len(common_prefix),
                tag_bits=0,
                expected_max_tag_bits=0,
                operation_description="ICT duplicate IDs committed",
            )

        split_pos = collision_positions[0]
        prefix_base = tags[0].id[:split_pos]
        group_0 = [tag for tag in tags if tag.id[split_pos] == "0"]
        group_1 = [tag for tag in tags if tag.id[split_pos] == "1"]
        self.stack.insert(0, ICTState(prefix=prefix_base + "1", tags=group_1))
        self.stack.insert(0, ICTState(prefix=prefix_base + "0", tags=group_0))

        self.metrics["collision_slots"] += 1
        expected_bits = max(0, self.id_length - len(state.prefix))
        return self._step_result(
            "collision_slot",
            reader_bits=CONSTANTS.READER_CMD_BASE_BITS + len(state.prefix),
            tag_bits=len(tags) * expected_bits,
            expected_max_tag_bits=expected_bits,
            operation_description=f"ICT split at bit {split_pos}",
        )
