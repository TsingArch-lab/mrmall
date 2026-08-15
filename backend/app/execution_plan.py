from __future__ import annotations

from dataclasses import dataclass

# Runtime execution metadata only. These IDs are existing Rules; this module does not
# create, reinterpret, or change any Rule or Gate. MAP_AWARE means the Rule benefits
# from cross-unit comparison through Article Map. Every other applicable Rule remains
# on the direct-text path.
MAP_AWARE_RULE_IDS = {
    "G002",
    "T001", "T002", "T003", "T004", "T005", "T101", "T102", "T103",
    "E001", "E002", "E003", "E101", "E401",
    "I001", "I002", "I003", "I004", "I005", "I006", "I101", "I201",
    "S001", "S005", "S006", "S007", "S101", "S201", "S301",
    "F003",
}


@dataclass(frozen=True)
class RuleExecutionPlan:
    direct_rule_ids: list[str]
    map_aware_rule_ids: list[str]

    @property
    def all_rule_ids(self) -> list[str]:
        return self.direct_rule_ids + self.map_aware_rule_ids


def build_execution_plan(applicable_rule_ids: list[str]) -> RuleExecutionPlan:
    """Split existing applicable Rules into two disjoint execution paths.

    This is a performance/execution concern, not a content-quality criterion.
    The union is exactly the incoming applicable Rule set and no Rule is added.
    """
    direct: list[str] = []
    mapped: list[str] = []
    seen: set[str] = set()
    for rid in applicable_rule_ids:
        if rid in seen:
            continue
        seen.add(rid)
        if rid in MAP_AWARE_RULE_IDS:
            mapped.append(rid)
        else:
            direct.append(rid)
    return RuleExecutionPlan(direct_rule_ids=direct, map_aware_rule_ids=mapped)
