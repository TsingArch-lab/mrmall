from __future__ import annotations
from dataclasses import dataclass
from typing import Any

FACT_SENSITIVE_RULE_IDS = {"G001", "G002"}
VALID_VERIFICATION_STATES = {"NOT_RUN", "PARTIAL", "COMPLETE"}

@dataclass(frozen=True)
class VerificationContext:
    state: str
    results: list[dict[str, Any]]
    def __post_init__(self):
        if self.state not in VALID_VERIFICATION_STATES:
            raise ValueError(f"Invalid verification state: {self.state}")

def make_verification_context(verify_facts: bool, results=None, state: str | None = None) -> VerificationContext:
    results = results or []
    resolved_state = state or ("PARTIAL" if verify_facts else "NOT_RUN")
    return VerificationContext(resolved_state, results)

def verification_guard_text(ctx: VerificationContext) -> str:
    return f"""FACT_VERIFICATION_STATE: {ctx.state}
强制执行边界：
1. NOT_RUN：不得仅因“文章没有外链/出处”“模型无法联网确认”“无法核实/无法追溯”判事实类 Rule FAIL。
2. “尚未外部核验”不等于“事实错误”；依赖外部来源且材料不足时使用 UNRESOLVED。
3. PARTIAL：只能依据 VERIFICATION_RESULTS 已覆盖事实做外部事实判断，未覆盖事实不得自动 FAIL。
4. 只有 VERIFICATION_RESULTS 明确证明错误、文章内部事实自相矛盾、或与用户材料直接冲突时，才可据事实问题判 FAIL。
5. “缺乏来源”本身不等于“事实错误”，除非 Rule fail_condition 明确要求必须给出处。
6. 不得为了谨慎把未知状态转为 FAIL。"""

def fail_is_only_unverified(rule_id: str, explanation: str, ctx: VerificationContext) -> bool:
    if rule_id not in FACT_SENSITIVE_RULE_IDS:
        return False
    t=(explanation or "").lower()
    unknown=["无法核实","无法核验","未核实","未核验","没有来源","缺乏来源","未提供来源","未提供出处","无出处","不可追溯","无法追溯","cannot verify","unverified","no source"]
    substantive=["自相矛盾","与前文矛盾","明显错误","事实错误","数据冲突","与材料冲突","与已提供","不可能","contradict","false"]
    return any(x in t for x in unknown) and not any(x in t for x in substantive)
