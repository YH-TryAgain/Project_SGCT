import binascii
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from Framework import AlgorithmStepResult, CONSTANTS, Tag, TraditionalAlgorithmInterface


@dataclass
class DRCTParams:
    """Paper-level DRCT parameters.

    The paper uses a 4-bit random Check and a 2-bit Answer. The deterministic
    check mode is kept only for repeatable tests; the default mode samples a
    pseudo-random Check for every responding tag and response cycle.
    """

    check_bits: int = 4
    answer_bits: int = 2
    seed: int = 0xDACE
    check_mode: str = "random"
    check_seed: int = 0xDACE
    data_rate_bps: int = 40000
    t1_us: float = 25.0
    t2_us: float = 25.0
    paper_timing: bool = False
    include_reader_cmd_base_bits: bool = True


@dataclass(eq=True)
class DRCTNode:
    preStr: str
    seDepth: int


@dataclass
class DRCTCycleRecord:
    node: DRCTNode
    cycle_name: str
    tag_ids: List[str]
    outcome: str


def modify_prestr(preStr: str, is_r1_collision: bool) -> str:
    """Apply Algorithm 1's reader-side prefix update rule.

    R0-cycle collision: append 1.
    R1-cycle collision: replace the last bit by 0 and append the old last bit.
    """
    if not preStr:
        return "1"
    if not is_r1_collision:
        return preStr + "1"
    return preStr[:-1] + "0" + preStr[-1]


def _crc16_int(payload: str) -> int:
    return binascii.crc_hqx(payload.encode("ascii"), 0xFFFF)


def _deterministic_check_value(epc: str, preStr: str, cycle_name: str, params: DRCTParams) -> int:
    if params.check_bits <= 0:
        return 0
    payload = f"{epc}|{preStr}|{cycle_name}|{params.seed}"
    return _crc16_int(payload) % (1 << params.check_bits)


class DRCTFinalAlgorithm(TraditionalAlgorithmInterface):
    """Strict reproduction of the DRCT paper process.

    The implementation follows Algorithm 1 and the communication model:
    one reader Query carries ``preStr`` and ``seDepth``; tags with matching
    tag-side ``seDepth`` split into R0/R1 by binary magnitude comparison;
    each cycle transmits a low-bit Check; a success receives a 2-bit Answer
    and then transmits the remaining ID; an identical-Check alias is detected
    during the rest-ID transmission and re-enqueued as a collision. Only
    R1-cycle collisions increment tag-side and reader-side ``seDepth``.
    """

    def __init__(self, tags_in_field: List[Tag], **kwargs):
        super().__init__(tags_in_field, **kwargs)
        self.params = DRCTParams(
            check_bits=kwargs.get("check_bits", 4),
            answer_bits=kwargs.get("answer_bits", 2),
            seed=kwargs.get("seed", 0xDACE),
            check_mode=kwargs.get("check_mode", "random"),
            check_seed=kwargs.get("check_seed", kwargs.get("seed", 0xDACE)),
            data_rate_bps=kwargs.get("data_rate_bps", 40000),
            t1_us=kwargs.get("t1_us", 25.0),
            t2_us=kwargs.get("t2_us", 25.0),
            paper_timing=kwargs.get("paper_timing", False),
            include_reader_cmd_base_bits=kwargs.get("include_reader_cmd_base_bits", True),
        )
        if self.params.check_mode not in {"random", "epc_deterministic"}:
            raise ValueError("check_mode must be 'random' or 'epc_deterministic'.")

        self.id_length = len(tags_in_field[0].id) if tags_in_field else 0
        self.stack: List[DRCTNode] = [DRCTNode(preStr="1", seDepth=0)] if tags_in_field else []
        self.tag_se_depth: Dict[str, int] = {tag.id: 0 for tag in tags_in_field}
        self.tag_response_counts: Dict[str, int] = {tag.id: 0 for tag in tags_in_field}
        self.query_history: List[DRCTNode] = []
        self.cycle_history: List[DRCTCycleRecord] = []
        self.current_node: Optional[DRCTNode] = None
        self.current_r0_tags: List[Tag] = []
        self.current_r1_tags: List[Tag] = []
        self.current_cycle: str = "POP"
        self.pending_query_reader_bits: float = 0.0
        self.enable_monitoring = kwargs.get("enable_resource_monitoring", False)
        self._rng = random.Random(self.params.check_seed)
        self.metrics.update(
            {
                "drct_query_count": 0,
                "drct_r0_collision_count": 0,
                "drct_r1_collision_count": 0,
                "drct_r1_sedepth_increment_count": 0,
                "check_answer_alias_count": 0,
                "drct_random_check_count": 0,
                "drct_unresolved_stack_empty_count": 0,
                "avg_tag_responses": 0.0,
            }
        )

    def _step_result(self, *args, **kwargs) -> AlgorithmStepResult:
        result = AlgorithmStepResult(*args, **kwargs)
        if self.enable_monitoring:
            result.internal_metrics = {"stack_depth": len(self.stack)}
        return result

    def is_finished(self) -> bool:
        finished = len(self.identified_tags) == len(self.tags_in_field)
        if finished:
            counts = list(self.tag_response_counts.values())
            self.metrics["avg_tag_responses"] = float(np.mean(counts)) if counts else 0.0
            total_slots = (
                self.metrics["success_slots"]
                + self.metrics["collision_slots"]
                + self.metrics["idle_slots"]
            )
            self.metrics["channel_use_ratio"] = (
                (self.metrics["success_slots"] + self.metrics["collision_slots"]) / total_slots
                if total_slots > 0
                else 0.0
            )
        return finished

    def _record_responses(self, tags: List[Tag]) -> None:
        for tag in tags:
            if tag.id in self.tag_response_counts:
                self.tag_response_counts[tag.id] += 1

    def perform_step(self) -> AlgorithmStepResult:
        if self.current_cycle == "POP":
            if not self.stack:
                if not self.is_finished():
                    self.metrics["drct_unresolved_stack_empty_count"] += 1
                return self._step_result("internal_op")
            self._start_query(self.stack.pop())
            return self._step_result("internal_op")

        if self.current_cycle == "R0":
            result = self._process_response_cycle(self.current_r0_tags, "R0")
            self.current_cycle = "R1"
            return result

        if self.current_cycle == "R1":
            result = self._process_response_cycle(self.current_r1_tags, "R1")
            self._clear_query()
            return result

        return self._step_result("internal_op")

    def _start_query(self, node: DRCTNode) -> None:
        self.current_node = node
        self.query_history.append(DRCTNode(node.preStr, node.seDepth))
        self.current_cycle = "R0"
        self.metrics["drct_query_count"] += 1
        self.pending_query_reader_bits = self._query_reader_bits(node)
        active_tags = [
            tag
            for tag in self.tags_in_field
            if tag.id not in self.identified_tags
            and self.tag_se_depth.get(tag.id, 0) == node.seDepth
        ]
        self.current_r0_tags = []
        self.current_r1_tags = []
        for tag in active_tags:
            tag_prefix = tag.id[: len(node.preStr)].ljust(len(node.preStr), "0")
            if tag_prefix >= node.preStr:
                self.current_r0_tags.append(tag)
            else:
                self.current_r1_tags.append(tag)

    def _process_response_cycle(self, tags: List[Tag], cycle_name: str) -> AlgorithmStepResult:
        assert self.current_node is not None
        reader_bits = self.pending_query_reader_bits
        self.pending_query_reader_bits = 0.0

        if not tags:
            self.metrics["idle_slots"] += 1
            self._record_cycle(tags, cycle_name, "idle")
            return self._step_result(
                "idle_slot",
                reader_bits=reader_bits,
                expected_max_tag_bits=0,
                override_time_us=self._paper_slot_time(reader_bits, 0, "idle"),
                operation_description=f"DRCT strict {cycle_name} idle",
            )

        self._record_responses(tags)
        check_bits_total = len(tags) * self.params.check_bits
        check_values = {self._check_value(tag, cycle_name) for tag in tags}

        if len(tags) == 1:
            self._record_cycle(tags, cycle_name, "success")
            return self._commit_success(tags[0], cycle_name, reader_bits, check_bits_total)

        self._enqueue_collision(tags, cycle_name)
        self.metrics["collision_slots"] += 1

        if len(check_values) == 1:
            self.metrics["check_answer_alias_count"] += 1
            self._record_cycle(tags, cycle_name, "fallback_collision")
            rest_len = self._rest_id_len()
            return self._step_result(
                "collision_slot",
                reader_bits=reader_bits + self.params.answer_bits,
                tag_bits=check_bits_total + len(tags) * rest_len,
                expected_max_tag_bits=rest_len,
                override_time_us=self._paper_slot_time(
                    reader_bits,
                    rest_len,
                    "fallback_collision",
                ),
                operation_description=f"DRCT strict {cycle_name} fallback collision after identical Check",
            )

        self._record_cycle(tags, cycle_name, "check_collision")
        return self._step_result(
            "collision_slot",
            reader_bits=reader_bits,
            tag_bits=check_bits_total,
            expected_max_tag_bits=self.params.check_bits,
            override_time_us=self._paper_slot_time(reader_bits, 0, "collision"),
            operation_description=f"DRCT strict {cycle_name} Check collision",
        )

    def _check_value(self, tag: Tag, cycle_name: str) -> int:
        if self.params.check_bits <= 0:
            return 0
        if self.params.check_mode == "epc_deterministic":
            return _deterministic_check_value(tag.id, self.current_node.preStr, cycle_name, self.params)
        self.metrics["drct_random_check_count"] += 1
        return self._rng.randrange(1 << self.params.check_bits)

    def _commit_success(
        self,
        tag: Tag,
        cycle_name: str,
        reader_bits: float,
        check_bits_total: float,
    ) -> AlgorithmStepResult:
        self.identified_tags.add(tag.id)
        self.metrics["success_slots"] += 1
        rest_len = self._rest_id_len()
        answer = "01" if cycle_name == "R0" else "10"
        return self._step_result(
            "success_slot",
            reader_bits=reader_bits + self.params.answer_bits,
            tag_bits=check_bits_total + rest_len,
            expected_max_tag_bits=max(self.params.check_bits, rest_len),
            override_time_us=self._paper_slot_time(reader_bits, rest_len, "success"),
            operation_description=f"DRCT strict {cycle_name} success Answer={answer}",
        )

    def _enqueue_collision(self, tags: List[Tag], cycle_name: str) -> None:
        assert self.current_node is not None
        is_r1 = cycle_name == "R1"
        new_prestr = modify_prestr(self.current_node.preStr, is_r1_collision=is_r1)
        new_sedepth = self.current_node.seDepth + 1 if is_r1 else self.current_node.seDepth
        self.stack.append(DRCTNode(preStr=new_prestr, seDepth=new_sedepth))
        if is_r1:
            self.metrics["drct_r1_collision_count"] += 1
            for tag in tags:
                self.tag_se_depth[tag.id] = self.tag_se_depth.get(tag.id, 0) + 1
            self.metrics["drct_r1_sedepth_increment_count"] += len(tags)
        else:
            self.metrics["drct_r0_collision_count"] += 1

    def _record_cycle(self, tags: List[Tag], cycle_name: str, outcome: str) -> None:
        assert self.current_node is not None
        self.cycle_history.append(
            DRCTCycleRecord(
                node=DRCTNode(self.current_node.preStr, self.current_node.seDepth),
                cycle_name=cycle_name,
                tag_ids=[tag.id for tag in tags],
                outcome=outcome,
            )
        )

    def _rest_id_len(self) -> int:
        assert self.current_node is not None
        return max(0, self.id_length - len(self.current_node.preStr))

    def _query_reader_bits(self, node: DRCTNode) -> int:
        base_bits = CONSTANTS.READER_CMD_BASE_BITS if self.params.include_reader_cmd_base_bits else 0
        return base_bits + len(node.preStr) + max(1, node.seDepth.bit_length())

    def _bits_time_us(self, bits: float) -> float:
        return bits / self.params.data_rate_bps * 1.0e6 if bits > 0 else 0.0

    def _paper_slot_time(self, query_reader_bits: float, rest_id_bits: int, outcome: str) -> Optional[float]:
        if not self.params.paper_timing:
            return None
        query_time = self._bits_time_us(query_reader_bits)
        check_time = self._bits_time_us(self.params.check_bits)
        if outcome == "idle" or outcome == "collision":
            return query_time + self.params.t1_us + check_time + self.params.t2_us
        if outcome == "success":
            return (
                query_time
                + self.params.t1_us
                + check_time
                + self.params.t2_us
                + self._bits_time_us(self.params.answer_bits + rest_id_bits)
            )
        if outcome == "fallback_collision":
            return (
                query_time
                + self.params.t1_us
                + check_time
                + self.params.t2_us
                + self._bits_time_us(self.params.answer_bits + rest_id_bits)
            )
        return None

    def _clear_query(self) -> None:
        self.current_node = None
        self.current_r0_tags = []
        self.current_r1_tags = []
        self.current_cycle = "POP"
        self.pending_query_reader_bits = 0.0


DRCTStrictAlgorithm = DRCTFinalAlgorithm
DRCTAlgorithm = DRCTFinalAlgorithm
