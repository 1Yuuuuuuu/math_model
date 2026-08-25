# Phase 5 Five-Gate Review Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase 5 with five isolated review Skills, deterministic model/paper scorecards, formal review contracts, stale-review detection, and a review bundle that is ready for Phase 6 only when every gate is current and passed.

**Status:** Implemented and verified on 2026-08-25; Phase 6 design is the next gate.

**Architecture:** Extend the existing `cumcm_toolkit.review` foundation instead of creating a second review engine. Shared YAML rubrics remain the rule source; new contract schemas stabilize the handoff to Phase 6; five Codex Skills produce isolated reports; a pure bundle builder revalidates every report against current inputs, rubrics, and files.

**Tech Stack:** Python 3.11, pytest, PyYAML, jsonschema Draft 2020-12, SHA-256, RFC 3339, Codex Agent Skills, existing Phase 3 handoffs and Phase 4 latex/pdf/evidence modules.

**Spec:** `docs/superpowers/specs/2026-08-25-cumcm-workbench-phase-5-completion-design.md`

## Global Constraints

- Review is read-only; no reviewer receives a repair callback or writes reviewed sources.
- Open S0/S1 always blocks; a score cannot override S0/S1.
- Model and paper scorecards require weighted total >= 85 and every dimension >= 70.
- Missing evidence, capability, file, gate, or unverifiable identifier returns `blocked` or `not_ready`; never infer success.
- Review identity binds canonical inputs, rubric content, and reviewed-file hashes.
- `shared/` remains the single source; packaged resources use `references/<source path>`.
- Formal contracts use Draft 2020-12, strict additional properties, portable paths, RFC 3339, and lowercase 64-character SHA-256.
- The contract catalog grows from 11 to exactly 14 entries in this phase.
- The shared main worktree already contains uncommitted Phase 3/5 work. Preserve it, do not create a worktree that omits those files, and do not commit or push unless the user separately requests it.
- Use RED-GREEN-REFACTOR for every behavior change. Use `apply_patch` for file edits.

---

## File structure and ownership

| Path | Responsibility |
| --- | --- |
| `shared/contracts/{modeling-handoff,review-report,review-bundle}.schema.json` | Formal Phase 3→5 and Phase 5→6 interfaces |
| `shared/fixtures/contracts/{valid,invalid}/...` | Positive and negative contract evidence |
| `shared/rubrics/*.yaml` | Five executable gates and model/paper scoring definitions |
| `toolkit/src/cumcm_toolkit/review/scorecard.py` | Validate and deterministically recompute scorecards |
| `toolkit/src/cumcm_toolkit/review/engine.py` | Run rubric rules, scorecards, and validated external findings |
| `toolkit/src/cumcm_toolkit/review/inputs.py` | Normalize Phase 3/4 outputs into gate inputs |
| `toolkit/src/cumcm_toolkit/review/bundle.py` | Revalidate five reports and produce Phase 6 readiness |
| `adapters/codex/skills/{repro-reviewer,paper-reviewer,red-team-reviewer,submission-auditor}/` | Four new isolated reviewer Skills |
| `adapters/codex/skills/model-reviewer/` | Existing Skill narrowed to Gate 2 only |
| `tests/e2e/test_five_gate_review_flow.py` | Full Phase 3/4→five gates→bundle and revision invalidation |

---

### Task 1: Promote Phase 5 interfaces into formal contracts

**Files:**

- Create: `shared/contracts/modeling-handoff.schema.json`
- Create: `shared/contracts/review-report.schema.json`
- Create: `shared/contracts/review-bundle.schema.json`
- Create: `shared/fixtures/contracts/valid/modeling-handoff.json`
- Create: `shared/fixtures/contracts/invalid/modeling-handoff-complete-empty-output.json`
- Create: `shared/fixtures/contracts/valid/review-report.json`
- Create: `shared/fixtures/contracts/invalid/review-report-invalid-status.json`
- Create: `shared/fixtures/contracts/valid/review-bundle.json`
- Create: `shared/fixtures/contracts/invalid/review-bundle-missing-gate.json`
- Modify: `shared/contracts/catalog.json`
- Modify: `adapters/codex/handoff.py`
- Test: `tests/contracts/test_phase5_review_contracts.py`
- Test: `tests/e2e/test_handoff_contract.py`

**Interfaces:**

- `modeling-handoff` accepts artifact types already supported by `handoff.py` plus `repro-review`, `paper-review`, `red-team-review`, and `submission-audit`.
- Complete handoffs require non-empty outputs and evidence; blocked handoffs require empty outputs/evidence plus a failed step or missing input.
- `review-report` formalizes the current report fields and optional `scorecard`; `findings` use `review-finding` shape.
- `review-bundle` requires exactly five report slots: `submission`, `reproducibility`, `model`, `paper`, `red_team`.
- Catalog contains exactly 14 unique IDs and registers valid/invalid fixtures for each new schema.

- [ ] **Step 1: Write failing contract tests**

Add tests that load the catalog through the existing offline registry, assert the three IDs exist, validate all three positive fixtures, reject all three negative fixtures, and assert a complete modeling handoff with empty outputs cannot validate.

- [ ] **Step 2: Run the contract tests and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/contracts/test_phase5_review_contracts.py -v -p no:cacheprovider`

Expected: fail because the three schemas and fixtures do not exist and the catalog still contains 11 entries.

- [ ] **Step 3: Implement the schemas and catalog registration**

Use `$ref` only to registered local schemas. Keep `additionalProperties: false`; require five bundle slots; allow `scorecard` to be either null or an object with deterministic total, threshold, floor, dimensions, and passed flag.

- [ ] **Step 4: Extend handoff artifact types**

Add the four reviewer artifact types to `ARTIFACT_TYPES`. Preserve actual file/hash/evidence validation in `complete_handoff`.

- [ ] **Step 5: Run contract, handoff, and validator GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_phase5_review_contracts.py tests/e2e/test_handoff_contract.py -v -p no:cacheprovider
.venv\Scripts\python.exe scripts/validate_contracts.py
```

Expected: tests pass; validator reports `{"contracts": 14, "errors": [], "status": "ok"}`.

---

### Task 2: Add deterministic model and paper scorecards

**Files:**

- Create: `toolkit/src/cumcm_toolkit/review/scorecard.py`
- Create: `toolkit/tests/review/test_scorecard.py`
- Modify: `shared/rubrics/model-quality.yaml`
- Modify: `shared/rubrics/paper-quality.yaml`
- Modify: `toolkit/src/cumcm_toolkit/review/engine.py`
- Modify: `toolkit/tests/review/test_rubrics.py`

**Interfaces:**

```python
def evaluate_scorecard(
    rubric: Mapping[str, object],
    submitted_dimensions: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Return threshold, dimension_floor, weighted_total, dimensions, passed."""
```

Each submitted dimension is `{dimension_id, score, rationale, evidence_refs}`. Scores are finite numbers from 0 through 100. Evidence refs are non-empty unique `clm_*` IDs. The function rejects missing, duplicate, unknown, or extra dimensions; recomputes the total with `sum(score * weight / 100)`; and sets `passed` only when total >= 85 and every dimension >= 70.

- [ ] **Step 1: Write failing scorecard tests**

Cover exact model and paper weights, a passing 85/70 boundary, total below 85, one dimension below 70, missing/duplicate/unknown dimensions, score outside 0–100, non-finite score, empty rationale, missing evidence, and weights not summing to 100.

- [ ] **Step 2: Run scorecard tests and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest toolkit/tests/review/test_scorecard.py -v -p no:cacheprovider`

Expected: import failure because `scorecard.py` does not exist.

- [ ] **Step 3: Add rubric scoring definitions**

Add this shape to model and paper rubrics:

```yaml
scoring:
  threshold: 85
  dimension_floor: 70
  dimensions:
    - dimension_id: problem-and-data
      weight: 15
      summary: Problem understanding and data quality
```

Use the exact six model and seven paper dimensions and weights from the approved spec. Other rubrics omit `scoring`.

- [ ] **Step 4: Implement minimal scorecard evaluation and rubric validation**

Extend `_validate_rubric` so `scoring` is optional, but when present it validates exact keys, unique dimension IDs, finite positive weights, sum 100, and thresholds in 0–100. Implement `evaluate_scorecard` without trusting a submitted total.

- [ ] **Step 5: Run scorecard and rubric tests GREEN**

Run: `.venv\Scripts\python.exe -m pytest toolkit/tests/review/test_scorecard.py toolkit/tests/review/test_rubrics.py -v -p no:cacheprovider`

---

### Task 3: Validate external reviewer findings and scored reports

**Files:**

- Modify: `toolkit/src/cumcm_toolkit/review/engine.py`
- Modify: `toolkit/src/cumcm_toolkit/review/__init__.py`
- Modify: `toolkit/tests/review/test_engine.py`
- Modify: `shared/rubrics/model-quality.yaml`
- Modify: `shared/rubrics/paper-quality.yaml`

**Interfaces:**

```python
def review(
    inputs: dict[str, object],
    rubric: dict[str, object],
    *,
    capabilities: set[str] | None = None,
    reviewed_at: str | None = None,
    reviewed_files: Iterable[Path] = (),
    file_root: Path | None = None,
    score_dimensions: Iterable[Mapping[str, object]] | None = None,
    reviewer_findings: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
```

- A rubric with scoring and missing `score_dimensions` returns `blocked` with a stable error.
- A failing scorecard adds an engine-owned open S1 finding `finding_<rubric_id>_score` using current root evidence.
- External findings must validate against `review-finding.schema.json`, have unique IDs, use only current input `clm_*` evidence, and have status `open`.
- The report includes the recomputed scorecard or null. `gate_status` considers both automatic and external findings.

- [ ] **Step 1: Write failing engine tests**

Test scored pass, missing scorecard blocked, low score failed, open external S1 failed, external S2 preserved but passed, fabricated evidence rejected, duplicate finding IDs rejected, non-open external status rejected, and source file hashes unchanged.

- [ ] **Step 2: Run tests and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest toolkit/tests/review/test_engine.py -v -p no:cacheprovider`

Expected: failures for unsupported keyword arguments and missing scorecard behavior.

- [ ] **Step 3: Implement finding and scorecard integration**

Validate external findings before appending them. Deep-copy accepted findings. Do not add mutation or resolution APIs. Preserve the existing review identity calculation, but include the recomputed scorecard and external findings in the canonical input material so changing either creates a new review ID.

- [ ] **Step 4: Validate generated reports against the formal schema**

Load `shared/contracts/review-report.schema.json` through the existing offline validator and reject any engine output that fails it.

- [ ] **Step 5: Run review tests GREEN**

Run: `.venv\Scripts\python.exe -m pytest toolkit/tests/review -v -p no:cacheprovider`

---

### Task 4: Normalize Phase 3 and Phase 4 review inputs

**Files:**

- Create: `toolkit/src/cumcm_toolkit/review/inputs.py`
- Create: `toolkit/tests/review/test_inputs.py`
- Modify: `shared/rubrics/reproducibility.yaml`
- Modify: `shared/rubrics/paper-quality.yaml`
- Modify: `shared/rubrics/red-team.yaml`
- Modify: `shared/rubrics/submission.yaml`

**Interfaces:**

```python
def build_reproducibility_inputs(
    handoffs: Iterable[Mapping[str, object]],
    *,
    artifact_records: Iterable[Mapping[str, object]],
    experiment_records: Iterable[Mapping[str, object]],
    evidence_links: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    ...

def build_paper_inputs(
    *,
    evidence_report: Mapping[str, object],
    citation_report: Mapping[str, object],
    lint_report: Mapping[str, object],
    key_claim_ids: Iterable[str],
    claim_boundaries: Iterable[Mapping[str, object]],
    limitations: Iterable[str],
    challenges: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    ...

def build_submission_inputs(
    *,
    build_report: Mapping[str, object],
    lint_report: Mapping[str, object],
    citation_report: Mapping[str, object],
    pdf_report: Mapping[str, object],
    source_sha256: str,
    pdf_sha256: str,
    annual_rule_verified: bool,
) -> dict[str, object]:
    ...
```

`build_reproducibility_inputs` uses `model_review_inputs`, verifies every referenced artifact/experiment/claim exists, verifies experiment status and lock hash, and returns the five named handoffs plus evidence refs and record indexes. Paper inputs require valid `clm_*` key claims and expose the exact Phase 4 report statuses. Submission inputs reject malformed hashes and expose build/lint/citation/PDF/annual-rule fields.

- [ ] **Step 1: Write failing input-normalization tests**

Cover a valid Phase 3 bundle, missing artifact, broken evidence link, failed experiment, missing lock hash, valid Phase 4 reports, unresolved evidence, unapproved citation result, malformed source/PDF hash, and unverified annual rule.

- [ ] **Step 2: Run tests and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest toolkit/tests/review/test_inputs.py -v -p no:cacheprovider`

- [ ] **Step 3: Implement strict normalizers**

Return canonical JSON-compatible dictionaries only. Reject NaN/Infinity, path objects, duplicate identifiers, and unknown report status values. Do not read or write source files in these functions.

- [ ] **Step 4: Expand five rubrics to consume normalized fields**

- Reproducibility: all handoffs complete, experiment succeeded, lock hash present, artifact/evidence indexes present.
- Paper: evidence `ok`, citations `ok`, lint `ok`, unresolved list empty, scorecard required.
- Red team: limitations and claim boundaries non-empty; `covers_claims` verifies every key claim has a challenge record.
- Submission: build/lint/citations/PDF `ok`, blank pages empty, hashes present, annual rule verified.

Add `covers_claims` to the engine checker registry with params `claims_path`, `challenges_path`, and `claim_id_field`.

- [ ] **Step 5: Run normalizer, rubric, and engine tests GREEN**

Run: `.venv\Scripts\python.exe -m pytest toolkit/tests/review -v -p no:cacheprovider`

---

### Task 5: Build the five-report Phase 6 readiness bundle

**Files:**

- Create: `toolkit/src/cumcm_toolkit/review/bundle.py`
- Create: `toolkit/tests/review/test_bundle.py`
- Modify: `toolkit/src/cumcm_toolkit/review/__init__.py`

**Interfaces:**

```python
REVIEW_SLOTS: tuple[str, ...] = (
    "submission", "reproducibility", "model", "paper", "red_team"
)

def build_review_bundle(
    *,
    reports: Mapping[str, Mapping[str, object]],
    current_inputs: Mapping[str, dict[str, object]],
    rubrics: Mapping[str, dict[str, object]],
    reviewed_files: Mapping[str, Iterable[Path]],
    file_root: Path,
    created_at: str | None = None,
) -> dict[str, object]:
    ...
```

The function validates every report against `review-report.schema.json`, verifies slot-to-rubric identity, calls `is_review_current` with the slot's current inputs/rubric/files, computes canonical report digests, aggregates open S0/S1, and validates its output against `review-bundle.schema.json`.

- [ ] **Step 1: Write failing bundle tests**

Cover exactly five current passed reports => `ready_for_phase_6`; missing slot, wrong rubric, malformed report, and unverifiable input => `blocked`; stale report, failed/blocked report, or open S0/S1 => `not_ready`; S2/S3 alone remains ready but is retained in reports.

- [ ] **Step 2: Run tests and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest toolkit/tests/review/test_bundle.py -v -p no:cacheprovider`

- [ ] **Step 3: Implement deterministic bundle construction**

Set `bundle_id = "review_bundle_" + canonical_digest(identity_material)[:16]`. Use `validate_rfc3339` for `created_at`. Sort report IDs, digests, and blocking finding IDs for deterministic output.

- [ ] **Step 4: Run bundle and review tests GREEN**

Run: `.venv\Scripts\python.exe -m pytest toolkit/tests/review -v -p no:cacheprovider`

---

### Task 6: Add four reviewer Skills and narrow model-reviewer

**Files:**

- Create: `adapters/codex/skills/repro-reviewer/SKILL.md`
- Create: `adapters/codex/skills/repro-reviewer/agents/openai.yaml`
- Create: `adapters/codex/skills/repro-reviewer/resources.json`
- Create: `adapters/codex/skills/paper-reviewer/SKILL.md`
- Create: `adapters/codex/skills/paper-reviewer/agents/openai.yaml`
- Create: `adapters/codex/skills/paper-reviewer/resources.json`
- Create: `adapters/codex/skills/red-team-reviewer/SKILL.md`
- Create: `adapters/codex/skills/red-team-reviewer/agents/openai.yaml`
- Create: `adapters/codex/skills/red-team-reviewer/resources.json`
- Create: `adapters/codex/skills/submission-auditor/SKILL.md`
- Create: `adapters/codex/skills/submission-auditor/agents/openai.yaml`
- Create: `adapters/codex/skills/submission-auditor/resources.json`
- Modify: `adapters/codex/skills/model-reviewer/SKILL.md`
- Modify: `adapters/codex/skills/model-reviewer/resources.json`
- Modify: `adapters/codex/skills/catalog.json`
- Modify: `tests/snapshots/codex-skills/routing-cases.yaml`
- Modify: `tests/snapshots/codex-skills/test_skill_contracts.py`
- Modify: `tests/snapshots/codex-skills/test_packaging.py`

**Interfaces:**

All reviewer Skills emit the shared outer handoff fields. Complete outputs contain one indexed review-report file and artifact evidence. `decision_status` is `passed|failed|blocked`; outer `status` is `complete|blocked`. Reviewers must not edit source files or mark findings resolved.

- [ ] **Step 1: Add failing catalog, routing, resource, and packaging tests**

Expect exactly 11 Skill directories. Add two positive and two negative routing cases per new Skill. Assert each reviewer packages its rubric, formal review schemas, engine, severity, scorecard/inputs/bundle helper as needed, Phase 4 report modules as needed, and handoff helper.

- [ ] **Step 2: Run tests and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/snapshots/codex-skills -v -p no:cacheprovider`

Expected: catalog/source mismatch and missing Skill directories.

- [ ] **Step 3: Create each Skill one at a time**

For each Skill, create the three required files, run its focused static tests, then run the system Skill validator available at `C:\Users\YU\.codex\skills\.system\skill-creator\scripts\quick_validate.py`. Keep machine-specific validator paths out of repository documentation.

- [ ] **Step 4: Narrow model-reviewer**

Remove responsibility for running the reproducibility rubric. Require normalized model inputs and model score dimensions. Explicitly state that model review cannot approve reproducibility, paper, red-team, or submission gates.

- [ ] **Step 5: Update catalog and package GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/snapshots/codex-skills -v -p no:cacheprovider
.venv\Scripts\python.exe scripts/package_codex_skills.py --check
```

Expected package output: `{"skills": 11, "status": "ok"}`.

---

### Task 7: Add full five-gate end-to-end and revision invalidation

**Files:**

- Create: `tests/e2e/test_five_gate_review_flow.py`
- Modify: `tests/e2e/test_review_isolation.py`
- Modify: `tests/e2e/test_revision_requires_rereview.py`

**Interfaces:**

The E2E creates real temporary Phase 3 output files and indexed handoffs, uses valid-shaped Phase 4 evidence/citation/lint/build/PDF reports, writes a paper source and PDF fixture file, creates passing scorecards and complete red-team challenges, runs all five rubrics independently, then builds a ready bundle.

- [ ] **Step 1: Write failing ready-flow E2E**

Assert five reports have distinct rubric IDs, every report is `passed`, model/paper scorecards are recomputed, and bundle readiness is `ready_for_phase_6`.

- [ ] **Step 2: Run and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/e2e/test_five_gate_review_flow.py -v -p no:cacheprovider`

- [ ] **Step 3: Add failure and isolation cases**

Assert an unapproved citation fails paper/submission only; an uncovered key claim fails red-team only; a low model dimension fails model only; every source file hash remains identical before/after review.

- [ ] **Step 4: Add revision invalidation case**

Modify `paper/main.tex` after the ready bundle. Assert paper, red-team, and submission reports are no longer current and rebuilt bundle is `not_ready`. Repro/model reports remain current when their reviewed files and inputs did not change.

- [ ] **Step 5: Run E2E and all review tests GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/review tests/e2e/test_review_isolation.py tests/e2e/test_revision_requires_rereview.py tests/e2e/test_five_gate_review_flow.py -v -p no:cacheprovider
```

---

### Task 8: Document, govern, and verify Phase 5 completion

**Files:**

- Modify: `docs/operations/review-gates.md`
- Modify: `docs/superpowers/specs/2026-08-25-cumcm-workbench-phase-5-independent-review-design.md`
- Modify: `docs/superpowers/plans/2026-08-25-cumcm-workbench-phase-5-independent-review.md`
- Modify: `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`
- Create: `docs/operations/phase5-to-phase6-handoff.md`
- Modify: `tests/contracts/test_paper_integration_documentation.py`

**Interfaces:**

The operations guide documents five independent commands, score interpretation, status semantics, stale-report recovery, bundle readiness, and the exact Phase 6 handoff. The master plan marks Phase 5 complete only after fresh verification and identifies Phase 6 design/plan as next.

- [ ] **Step 1: Write failing governance assertions**

Extend documentation tests to require: Phase 5 checked, 14 contracts, 11 packaged Skills, five reviewer names, 85/70 internal thresholds, `ready_for_phase_6`, and explicit review/generation isolation.

- [ ] **Step 2: Run and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/contracts/test_paper_integration_documentation.py -v -p no:cacheprovider`

- [ ] **Step 3: Update operations and handoff documentation**

Use repository-relative commands such as `.venv\Scripts\python.exe`; do not include machine-specific validator or workspace paths. State that real Agent forward observations remain a separate deployment gate.

- [ ] **Step 4: Run complete verification**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe scripts/validate_contracts.py
.venv\Scripts\python.exe scripts/package_codex_skills.py --check
git diff --check
git status --short
```

Expected: zero test failures; contract validator reports 14/0; package check reports 11 Skills; diff check exits 0. Record skips and environment warnings without treating them as passes for skipped behavior.

- [ ] **Step 5: Run all 11 Skill format validators**

Discover the system validator at runtime, run it once per catalog entry, and require all exit codes 0. Do not persist the machine-specific validator path in user-facing operations documentation.

- [ ] **Step 6: Freeze the Phase 6 input**

Confirm `review-bundle.schema.json`, `build_review_bundle`, five rubric IDs, five Skill names, and stale-report semantics match the approved spec. Only then mark Phase 5 complete and begin Phase 6 brainstorming/design.
