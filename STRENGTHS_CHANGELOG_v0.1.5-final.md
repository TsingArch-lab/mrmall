# Strengths Patch v0.1.5-final

This patch tightens the positive-feedback runtime without changing any content Rule, severity, Gate threshold, or Registry.

## Governance change

Old: PASS + strength-eligible => candidate strength.

New: PASS + eligible + anchor Rule + Significance Test => strength.

A strength is published only when it is:
1. specific and distinctive to the submitted article;
2. supported by literal article evidence;
3. grounded in current PASS Rules;
4. anchored in a Rule that represents content value rather than mere evidence sufficiency;
5. something whose removal would materially reduce the article's quality.

## Explicitly excluded

The system must not praise an article merely because it has data, examples, first-party material, adequate wording, or no detected violation.

Evidence Rules can support a positive finding but cannot independently create one.

## Runtime safety

Positive feedback remains isolated from Gate aggregation and final judgement. It cannot turn a failing article into a passing article.
