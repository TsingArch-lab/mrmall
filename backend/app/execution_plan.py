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

# Rule Test Batches are execution plans, not quality rules. They only group existing
# Rules by the cognitive operation needed to execute their own existing conditions.
# A Rule appears in at most one batch and is still decided exactly once.
RULE_TEST_BATCH_DEFS = (
    (
        "ARGUMENT_PROGRESSION",
        {
            "T001", "T004",
            "S001", "S005", "S006", "S007", "S101", "S201", "S301",
        },
        """先建立文章的论证推进视图，再逐条执行 supplied Rules。只做这些既有 Rule 所要求的检查：
- 沿 Argument Map 逐块确认核心问题、张力、结构关系和结尾承接是否真实存在；不得凭整体印象判定。
- 若 supplied Rules 包含 S007：逐 Block 比较论证功能；识别连续/跨段同功能重复；对候选重复组执行删除测试；对同类案例执行边际价值测试。只有命中 S007 既有 fail_condition 才能 FAIL。
- 若 supplied Rules 包含 S001/S005/S006/S101/S201/S301：分别检查其原有闭环、标题关系、正文与结尾、类型结构条件，不得把‘有小标题/有总结’当作自动 PASS。
- 若 supplied Rules 包含 T001/T004：检查核心问题或真实张力是否贯穿主要论证块，而非只在开头出现。
先完成上述操作，再分别输出每条 Rule 的 PASS/FAIL/NA/UNRESOLVED。""",
    ),
    (
        "MECHANISM_DERIVATION",
        {
            "T002", "T003", "T005", "T101", "T102", "T103",
            "I001", "I002", "I003", "I004", "I101", "I201",
        },
        """先建立核心判断→事实/案例→机制→推论的对应关系，再逐条执行 supplied Rules。只使用各 Rule 已有条件：
- 区分‘事实改写’与‘多走一步的机制/判断’，不要因为出现抽象词、框架词就自动认为有分析。
- 对核心判断定位其直接支撑块，确认机制是否具体、可理解，是否真的解释了为什么，而不是换词复述。
- 对 T002/T003/T005/T101/T102/T103 与 I001/I002/I003/I004/I101/I201，仅按各自既有 evaluation_question / pass_condition / fail_condition 判断。
- 一个局部亮点不能替全文核心判断补足缺失的推导。
完成关系映射后再分别裁决，不得先形成全文好坏印象再批量赋值。""",
    ),
    (
        "CLAIM_EVIDENCE_STRENGTH",
        {
            "G002", "E001", "E002", "E003", "E101", "E401",
            "I005", "I006", "F003",
        },
        """先做核心判断与证据强度扫描，再逐条执行 supplied Rules。只执行已有 Rule：
- 抽取承担核心论证作用的强确定性表达，尤其‘所有/任何/从来/注定/唯一/90%/必然/根本’等；逐一定位直接证据链，再按 I005/F003 的既有标准判断确定性是否超过证据。
- 对 G002 与证据类 Rules，区分事实材料、第一方自述、成绩清单、外部核验与作者推论；不得因为材料多就自动认为支撑充分，也不得因为缺第三方或缺反例自动 FAIL。
- E002 只在企业/项目自我评价或成绩被直接当成能力证明、且命中其既有条件时 FAIL。
- I006/E003 等条件触发型 Rule 必须先确认触发条件，未触发则按 Rule 原定义处理。
先完成 claim-strength / evidence-source 对照，再分别裁决。""",
    ),
)


@dataclass(frozen=True)
class RuleExecutionPlan:
    direct_rule_ids: list[str]
    map_aware_rule_ids: list[str]

    @property
    def all_rule_ids(self) -> list[str]:
        return self.direct_rule_ids + self.map_aware_rule_ids


@dataclass(frozen=True)
class RuleTestBatch:
    name: str
    rule_ids: list[str]
    test_plan: str


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


def build_rule_test_batches(map_aware_rule_ids: list[str]) -> list[RuleTestBatch]:
    """Group already-applicable map-aware Rules by execution operation.

    No Rule is added, removed, duplicated, or reinterpreted. The returned batches must
    exactly partition the incoming Rule IDs. Unknown future map-aware IDs fail closed so
    they cannot silently skip evaluation.
    """
    incoming = list(dict.fromkeys(map_aware_rule_ids))
    incoming_set = set(incoming)
    batches: list[RuleTestBatch] = []
    covered: set[str] = set()
    for name, members, test_plan in RULE_TEST_BATCH_DEFS:
        ids = [rid for rid in incoming if rid in members]
        if not ids:
            continue
        overlap = covered.intersection(ids)
        if overlap:
            raise ValueError(f"Rule Test Batch duplicate coverage: {sorted(overlap)}")
        covered.update(ids)
        batches.append(RuleTestBatch(name=name, rule_ids=ids, test_plan=test_plan))
    missing = incoming_set - covered
    if missing:
        raise ValueError(f"Map-aware Rules missing Rule Test Batch metadata: {sorted(missing)}")
    return batches
