#!/usr/bin/env python3
from __future__ import annotations

from app.article_map import build_argument_blocks, normalize_article_map


def main():
    article = """开头提出：大家都在学CPI，但到底学什么？

Part 1 内容生态

先有内容生态，再有商业流量。

传统商业往往先招商再包装概念。

CPI先找到故事标题，再用品牌填充。

这说明内容应该先于招商。

内容思维和养成思维，是CPI区别于传统商业的关键。

CPI是内容生产型商业，而传统项目是空间出租型商业。

行业痛点总结：很多项目只学外在形态，没有学内容逻辑。

定位决定命运。很多项目的问题仍然是只学外在形态。

Part 2 以人为核心

客群结构决定商业模式。

黄金三角是高消费力、高到达意愿、高传播力。

以人为主，物业为配套。

T09形成创作、落地、消费、迭代的循环。

行业痛点总结：项目应先认清客群。

绝大多数项目仍守着建筑和商铺做运营。

Part 3 组织

长期资本使团队不必为季度KPI妥协。

团队获得较强话语权与灵活经营方式。

总结

CPI是定位、客群、资源、组织四重变量的乘积。

存量商业面临认知、条件、体制三层困境。

所有学不会CPI的项目，本质都是输给功利与浮躁。"""

    blocks = build_argument_blocks(article)
    # Headings may attach to the next prose paragraph, but prose paragraphs must never disappear
    # merely because several make the same point.
    prose = [b for b in blocks if b["text"] and not b["text"].startswith("Part ") and b["text"] != "总结"]
    assert len(prose) >= 19, len(prose)
    assert any("这说明内容应该先于招商" in b["text"] for b in blocks)
    assert any("内容思维和养成思维" in b["text"] for b in blocks)
    assert any("行业痛点总结" in b["text"] for b in blocks)
    assert any("定位决定命运" in b["text"] for b in blocks)

    # Simulate an LLM that labels only a small subset. Normalization must still preserve every
    # deterministic source block so representation loss cannot hide repetition.
    raw = {
        "core_question": "为什么CPI难复制",
        "thesis": "不同项目需要理解自身条件",
        "units": [
            {
                "block_id": blocks[0]["block_id"], "heading": "", "anchor_quote": blocks[0]["text"][:20],
                "role": "opening", "main_claim": "提出问题", "evidence_used": [], "mechanism": "",
                "relation_to_prior": "opens", "new_contribution": "提出核心问题"
            },
            {
                "block_id": blocks[6]["block_id"], "heading": "", "anchor_quote": blocks[6]["text"][:20],
                "role": "summary", "main_claim": "再次概括内容逻辑", "evidence_used": [], "mechanism": "",
                "relation_to_prior": "restates", "new_contribution": "重述前文内容逻辑"
            },
        ],
        "fact_claims": [],
    }
    m = normalize_article_map(raw, article, blocks)
    assert m["representation_grain"] == "DETERMINISTIC_ARGUMENT_BLOCKS"
    assert m["source_block_count"] == len(blocks)
    assert len(m["units"]) == len(blocks)
    assert [u["block_id"] for u in m["units"]] == [b["block_id"] for b in blocks]
    assert m["units"][6]["relation_to_prior"] == "restates"
    # Unlabelled blocks are retained neutrally, not deleted.
    assert m["units"][3]["role"] == "other"
    assert m["units"][3]["source_excerpt"]

    print(f"[PASS] Argument Map fidelity: preserved {len(blocks)} deterministic blocks; no semantic collapse")


if __name__ == "__main__":
    main()
