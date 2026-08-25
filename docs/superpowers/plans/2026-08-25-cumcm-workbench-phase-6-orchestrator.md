# Phase 6 Deterministic Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Apply RED-GREEN-REFACTOR per task, preserve the shared dirty worktree, and do not commit or push unless separately requested.

**Goal:** Implement an append-only, deterministic and recoverable CUMCM orchestration state machine with four non-skippable human gates, an optional literature branch, a current Phase 5 review-bundle prerequisite, and a self-contained `cumcm-orchestrator` Skill.

**Architecture:** Add a formal `workflow-event` contract and replay events into the existing `workflow-state` snapshot. Decisions remain separate human records; Phase 5 review bundles are freshly rebuilt before attachment. YAML describes registered transitions and time boxes; Python performs all validation and state reduction.

**Tech Stack:** Python 3.11, pytest, JSON Schema Draft 2020-12, PyYAML, SHA-256, RFC 3339, Codex Agent Skills.

**Spec:** `docs/superpowers/specs/2026-08-25-cumcm-workbench-phase-6-orchestrator-design.md`

**Status:** ✅ Complete — full repository verification passed (652 passed, 12 deployment/environment skips).

## Global constraints

- Event history is append-only; replay never scans directories or edits artifacts.
- Only external `decided_by: human` decision records can approve/reject gates.
- Gate 4 requires a freshly rebuilt `ready_for_phase_6` bundle and becomes stale after any later artifact event.
- Literature is optional and introduces no fifth human gate.
- Orchestrator chooses at most one next action and does not implement child-Skill work.
- Contract catalog becomes exactly 15; Codex Skill catalog becomes exactly 12.
- Use `apply_patch` for edits. Run all commands through the existing `.venv`.

---

### Task 1: Formalize append-only workflow events

**Files:**

- Create: `shared/contracts/workflow-event.schema.json`
- Create: `shared/fixtures/contracts/valid/workflow-event.json`
- Create: `shared/fixtures/contracts/invalid/workflow-event-gate-without-decision.json`
- Modify: `shared/contracts/catalog.json`
- Modify: `docs/architecture/contracts.md`
- Modify: `tests/contracts/test_catalog.py`
- Modify: `tests/contracts/test_contract_examples.py`
- Modify: validator count tests
- Create: `tests/contracts/test_phase6_workflow_event_contract.py`

**Steps:**

- [ ] Write tests expecting contract ID `workflow-event`, exactly 15 catalog entries, one valid fixture, and one invalid conditional fixture.
- [ ] Run the new contract test and confirm RED.
- [ ] Implement strict schema with cross-runtime end assertions and event-type conditionals.
- [ ] Register fixtures, update documentation rows/counts, and migrate all catalog count assertions from 14 to 15.
- [ ] Run all contract tests and `scripts/validate_contracts.py`; require 15/0.

### Task 2: Define and validate workflow configuration

**Files:**

- Create: `shared/workflows/stage-transitions.yaml`
- Create: `shared/workflows/cumcm-72h.yaml`
- Create: `toolkit/src/cumcm_toolkit/workflow/config.py`
- Create: `toolkit/src/cumcm_toolkit/workflow/__init__.py`
- Create: `toolkit/tests/workflow/test_config.py`

**Steps:**

- [ ] Write failing tests for exact stage order, four gates, registered event types, unique Skill routes, time boxes, no dynamic code/import keys, and a literature route without an extra gate.
- [ ] Run and confirm import/file RED.
- [ ] Add strict YAML using unique-key loading and implement `load_workflow_config`.
- [ ] Reject unknown stages, gates, Skills, expressions, duplicate keys, and non-monotonic time boxes.
- [ ] Run configuration tests GREEN.

### Task 3: Create and validate deterministic event chains

**Files:**

- Create: `toolkit/src/cumcm_toolkit/workflow/events.py`
- Create: `toolkit/tests/workflow/test_events.py`

**Interfaces:**

```python
def create_event(..., history: Iterable[Mapping[str, object]]) -> dict[str, object]: ...
def validate_event_chain(events: Iterable[Mapping[str, object]]) -> list[dict[str, object]]: ...
```

**Steps:**

- [ ] Write RED tests for deterministic IDs, sequence 0, previous digest, all event-type field rules, duplicate/reordered/tampered events, line-break IDs, and canonical JSON rejection.
- [ ] Implement event ID from canonical material, RFC3339 checks, formal schema validation, and chain validation.
- [ ] Treat exact duplicate append as idempotent; same ID/different content rejects.
- [ ] Run event tests and contract boundary tests GREEN.

### Task 4: Replay state, enforce four gates, and recover

**Files:**

- Create: `toolkit/src/cumcm_toolkit/workflow/state.py`
- Create: `toolkit/src/cumcm_toolkit/workflow/gates.py`
- Create: `toolkit/tests/workflow/test_state.py`
- Create: `toolkit/tests/workflow/test_gates.py`

**Interfaces:**

```python
def replay_workflow(events, *, decisions=(), review_bundles=()) -> dict[str, object]: ...
def validate_gate_decision(state, event, decisions, review_bundles) -> None: ...
```

**Steps:**

- [ ] Write RED tests for every legal stage, all four gate skips, wrong/nonhuman/unresolved decision, rejected gate, failed stage, resume, artifact preservation, bundle missing/not-ready/stale-after-artifact, submission completion, and repeat replay stability.
- [ ] Implement indexes for decisions/bundles and validate their formal shapes.
- [ ] Reduce events into the existing `workflow-state` shape plus runtime status/recovery metadata.
- [ ] Validate every derived snapshot against `workflow-state.schema.json`.
- [ ] Run workflow tests GREEN.

### Task 5: Select exactly one deterministic next action

**Files:**

- Create: `toolkit/src/cumcm_toolkit/workflow/actions.py`
- Create: `toolkit/tests/workflow/test_actions.py`

**Interface:**

```python
def next_action(snapshot: Mapping[str, object], config: Mapping[str, object]) -> dict[str, object]: ...
```

**Steps:**

- [ ] Write RED tests for child Skill, human gate request, recovery instruction, literature required/skipped, five-reviewer sequence, bundle build, submission packaging, and complete/no-op.
- [ ] Implement closed action types and registered Skill routing only.
- [ ] Ensure at most one action and no automatic human decision.
- [ ] Run action/config tests GREEN.

### Task 6: Add the cumcm-orchestrator Skill

**Files:**

- Create: `adapters/codex/skills/cumcm-orchestrator/SKILL.md`
- Create: `adapters/codex/skills/cumcm-orchestrator/agents/openai.yaml`
- Create: `adapters/codex/skills/cumcm-orchestrator/resources.json`
- Modify: `adapters/codex/skills/catalog.json`
- Modify: `tests/snapshots/codex-skills/routing-cases.yaml`
- Modify: Skill/package tests

**Steps:**

- [ ] Add failing assertions for exactly 12 Skills, two positive/two negative routes, workflow resources, all child Skill names, one-action rule, four human gates, and fail-closed handoff.
- [ ] Create Skill files following skill-creator conventions; resources include contracts, configs, workflow modules, handoff helper, review bundle helper and catalog.
- [ ] Run snapshot tests, package check, and all 12 system Skill validators.

### Task 7: Complete flow, optional literature, and recovery E2E

**Files:**

- Create: `tests/e2e/test_four_human_gates.py`
- Create: `tests/e2e/test_optional_literature_branch.py`
- Create: `tests/e2e/test_resume_after_failure.py`
- Create: `tests/e2e/test_orchestrated_competition_flow.py`

**Steps:**

- [ ] Write RED complete-flow test that stops at all four gates and reaches complete only with human decisions and ready bundle.
- [ ] Add literature required/skipped tests; required candidates join Gate 3 and no fifth gate exists.
- [ ] Add solver failure/resume tests proving artifact preservation and stable replay.
- [ ] Add stale bundle and revised artifact cases blocking Gate 4.
- [ ] Run all workflow/E2E tests GREEN.

### Task 8: Operations, governance, and full verification

**Files:**

- Create: `docs/competition/72-hour-playbook.md`
- Create: `docs/competition/recovery-playbook.md`
- Create: `docs/operations/phase6-to-phase7-handoff.md`
- Modify: master implementation plan and documentation governance tests
- Modify: this plan/spec status after verification

**Steps:**

- [ ] Write governance assertions for Phase 6 checked, 15 contracts, 12 Skills, four gates, optional literature, ready bundle, recovery, and Phase 7 next.
- [ ] Update operator docs with repository-relative commands and no machine-specific validator path.
- [ ] Run fresh full pytest, contract validator, Skill package check, 12 Skill validators, `git diff --check`, and status inspection.
- [ ] Record skips/warnings accurately; do not treat deployment-only real Agent forward observation as locally passed.
- [ ] Mark Phase 6 complete only after all required evidence passes.
