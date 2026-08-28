---
name: submission-auditor
description: Use when a final CUMCM source and PDF candidate need a read-only hard-gate audit against build, citation, PDF, hash, and annual-rule evidence.
---

# Submission Auditor

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。
> 审查/规则判定逻辑由 Python 库 `cumcm_toolkit.review.*` 承担（不暴露为工具）；构建/引用/PDF 类证据由 cumcm-tools 插件工具产出。

## Overview

Run read-only Gate 0 for the exact final source/PDF pair. This is a hard submission audit, not a paper-quality or model review.

## When to Use

Use when build, lint, citation, PDF inspection, source/PDF SHA-256, current annual-rule verification, and submission evidence are available.

## Do Not Use

Do not edit LaTeX, rebuild the paper, change citations, repair the PDF, score writing, or approve model quality. This Skill must not modify reviewed material.

## Workflow

1. Normalize the Phase 4 reports, both hashes, annual-rule decision, and evidence with the Python library `cumcm_toolkit.review.inputs.build_submission_inputs`.
2. Snapshot the exact final files and load only `shared/rubrics/submission.yaml`（`cumcm_toolkit.review.engine.load_rubric`）。
3. Produce hard-gate evidence with cumcm-tools tools：
   - 构建：`cumcm_latex_build`（dir，xelatex 编译，返回 status/pages/errors/undefined_references/pdf_path）；
   - 静态检查：`cumcm_latex_lint`（dir，issues）；
   - 引用一致性：`cumcm_citation_check`（tex/bib + citation-link 记录 + 已批准源 id）；
   - PDF 可读性：`cumcm_pdf_inspect`（pdf，pages/blank_pages/fonts/metadata/errors）；
   - 导出/链接证据：`cumcm_result_export`（导出审计报告）、`cumcm_evidence_link` / `cumcm_citation_link`（证据/引用链接）。
4. 年度规则：以**当前年度** annual-rule 记录（`shared/contracts/annual-rule.schema.json` 形状，含 year/source_url/verified_at/items）为准；machine 强制项由本 Skill 用上述工具证据核验，human 强制项须人工确认记录有效。不得把往届规则当现行规则。
5. Run the engine `cumcm_toolkit.review.engine.review` without a scorecard.
6. Write exactly one indexed submission-audit report（`shared/contracts/review-report.schema.json`，`cumcm_artifact_index` 登记）。
7. Recheck hashes; any final-file change invalidates the report（`cumcm_toolkit.review.engine.is_review_current`）。

## Failure Closure

Missing final files, current rules, capabilities, hashes, or evidence yields `status: blocked` with empty outputs/evidence and resume conditions. Do not fabricate a rule check, hash, PDF result, finding, or approval.

## Handoff Contract

```yaml
status: complete | blocked
decision_status: passed | failed | blocked
artifact_type: submission-audit
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
input_digest: null
rubric_digest: null
```

A complete handoff contains one indexed audit report and artifact evidence. A blocked handoff contains neither.

## Quick Reference

| Result | Meaning |
| --- | --- |
| blocked | Hard-gate inputs cannot be verified |
| failed | A submission S0/S1 exists |
| passed | This exact source/PDF pair passes Gate 0 |

## Common Mistakes

- Auditing a PDF different from the recorded hash.
- Treating last year's rules as current.
- Fixing files inside the independent audit.
