---
name: problem-reader
description: Use when a CUMCM problem statement, attachment note, or competition prompt must be decomposed before data processing or model selection.
---

# Problem Reader

## Overview

Turn the supplied problem—not memory of a similar problem—into explicit modeling requirements. Preserve ambiguity instead of resolving it with invented facts.

## When to Use

Use for initial problem reading, sub-question decomposition, objective/constraint extraction, symbol planning, attachment inventory, and assumption logging.

## Do Not Use

Do not use to select the final model, run computations, write the final paper, or approve citations. Hand the result to `data-auditor` and `model-selector` when ready.

## Workflow

Before starting, read `resources.json` and only the declared resources needed for this request. In a packaged Skill, resolve them under `references/<source path>`.

Before returning `complete`, write every declared output into the competition workspace, index it with the declared artifact index, and call `complete_handoff` with the real workspace, artifact, experiment, and evidence-link records. A format-valid ID without a matching record is not evidence.

1. Inventory the exact problem text, attachments, tables, units, time range, and requested deliverables.
2. Split every explicit question into an answerable objective. Record dependencies between questions.
3. For each objective, list inputs, outputs, constraints, evaluation criteria, and unresolved terms.
4. Separate stated facts from proposed assumptions. Every assumption needs a reason and a validation route.
5. Produce a data-needs table and stop on missing material that changes the mathematical problem.
6. Save the problem analysis before any downstream modeling claim.

## Failure Closure

If the statement or a referenced attachment is missing, return `status: blocked`, identify it in `missing_inputs`, set `failed_step`, and state `resume_when`. Do not fabricate omitted constraints, data, units, or task wording.

## Handoff Contract

```yaml
status: complete | blocked
artifact_type: problem-analysis
inputs: []
outputs: []
evidence: []
missing_inputs: []
failed_step: null
resume_when: []
```

A complete output contains: question list, objective/constraint table, data inventory, symbol draft, assumptions with validation routes, and open questions.

## Quick Reference

| Observation | Record as |
| --- | --- |
| Explicit sentence in prompt | stated fact + location |
| Necessary but unstated condition | proposed assumption |
| Missing attachment or column | blocker |
| Possible method | downstream candidate, not decision |

## Common Mistakes

- Treating an example value as a universal constraint.
- Combining two questions with different objectives.
- Selecting a familiar model before identifying the output and validation target.
- Hiding missing data inside an assumption.
