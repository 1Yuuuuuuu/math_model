---
name: literature-researcher
description: Use when a CUMCM modeling claim, method choice, domain assumption, or related-work question needs candidate scholarly sources and metadata verification.
---

# Literature Researcher

> DSH 镜像：与 Codex 轨道语义一致；工具面为 cumcm-tools / literature-tools 插件。本目录仅 SKILL.md（无 resources.json/agents），打包/安装方式待 Task 5/8 交接。

## Overview

Build an auditable candidate literature set for later human review. A search hit is a lead, not an approved citation—candidates never become references inside this Skill.

## When to Use

Use when the modeling process needs method origins, domain evidence, comparable studies, parameter evidence, or a gap analysis.

## Do Not Use

Do not use to approve formal citations, create final BibTeX, claim a paper supports text not inspected, or rank source quality by citation count alone.

DSH 侧未实现真实网络检索后端转发：`literature_search` 只是配置门禁 + 授权占位（fail-closed）。未配置 backend、backend 不在 allowedDomains、或未获用户授权时，检索**blocked**，候选列表为空——绝不伪造检索结果。

## Workflow

1. Convert the evidence need into a search question, intended claim, inclusion/exclusion criteria, date/language limits, and Chinese/English keywords（策略参考 `shared/knowledge/literature/search-strategy.md`）。
2. Determine the backend per the literature-tools plugin config（backend + allowedDomains）。调用 `literature_search`（query / limit）：无后端或域名未授权 → 工具失败（fail-closed）→ 按 Failure Closure 关闭；通过门禁 → 仅返回 requires-user-authorization 占位 + 空候选，等待用户授权真实后端。
3. 用户提供的 DOI/PDF/URL/JSON 源文件用 `literature_read_source` 离线确定性解析为 candidate（PDF 仅恢复未压缩 Tj 文本流，缺项如实列在 metadata_gaps；绝不补造 DOI/作者/年份）。
4. 用 `literature_route_candidate` 对候选数组做确定性归一化分组与组内冲突标记（{groups, conflicts}）；只标记、不合并、不挑选——冲突候选保持 candidate 状态待人工核验。
5. Evaluate metadata completeness, full-text availability, intended claim, support boundary, and verification gaps.
6. Index the candidate table with `cumcm_artifact_index` and return candidates with `candidate` status only. Route inspection and approval to the later evidence/paper phase（`cumcm_citation_link` 仅在源记录 approved 且含 decision_id 时可用）。

## Failure Closure

If no approved backend or user source is available, return `status: blocked` with the search plan, `failed_step`, and `resume_when`; candidate outputs stay empty. Do not fabricate authors, title, DOI, venue, year, quotation, or support. This Skill must not approve any candidate.

## Handoff Contract

```yaml
status: complete | blocked
artifact_type: literature-candidates
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
```

Every candidate records identifier/source URL, title/author/year only when retrieved, query provenance, intended claim, support boundary, full-text state, conflicts, and verification tasks.

## Quick Reference

| Evidence state | Allowed output |
| --- | --- |
| Metadata hit only | candidate + metadata gaps |
| Full text inspected | candidate + bounded support note |
| Conflicting identifiers | separate candidates + conflict |
| No backend / no user source | blocked search plan, no candidates |

## Common Mistakes

- Treating a title or abstract as proof of a detailed claim.
- Silently merging conflicting DOI/title metadata.
- Equating citation count or journal tier with correctness.
- Producing polished references before source approval.
- Treating the `literature_search` authorization placeholder as a real search result.
