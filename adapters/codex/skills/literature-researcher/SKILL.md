---
name: literature-researcher
description: Use when a CUMCM modeling claim, method choice, domain assumption, or related-work question needs candidate scholarly sources and metadata verification.
---

# Literature Researcher

## Overview

Build an auditable candidate literature set for later human review. A search hit is a lead, not an approved citation.

## When to Use

Use when the modeling process needs method origins, domain evidence, comparable studies, parameter evidence, or a gap analysis.

## Do Not Use

Do not use to approve formal citations, create final BibTeX, claim a paper supports text not inspected, or rank source quality by citation count alone.

## Workflow

Before starting, read `resources.json` and only the declared resources needed for this request. In a packaged Skill, resolve them under `references/<source path>`.

Before returning `complete`, write the candidate table into the competition workspace, index it with the declared artifact index, and call `complete_handoff` with the real workspace and records. A format-valid ID without a matching record is not evidence and a candidate is not an approved citation.

1. Convert the evidence need into a search question, intended claim, inclusion/exclusion criteria, date/language limits, and Chinese/English keywords.
2. Build `BackendCapability` records and call the declared `route_literature_backend` helper. Select in order: approved and callable runtime search, approved and callable paper-search Skill, then user-provided DOI/PDF/URL.
3. Record exact queries, backend, retrieval date, identifiers, and available metadata.
4. Normalize DOI/title/source identifiers and group duplicates. Preserve conflicting metadata as separate candidate records pending review.
5. Evaluate metadata completeness, full-text availability, intended claim, support boundary, and verification gaps.
6. Return candidates with `candidate` status only. Route inspection and approval to the later evidence/paper phase.

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
| No backend | blocked search plan, no candidates |

## Common Mistakes

- Treating a title or abstract as proof of a detailed claim.
- Silently merging conflicting DOI/title metadata.
- Equating citation count or journal tier with correctness.
- Producing polished references before source approval.
