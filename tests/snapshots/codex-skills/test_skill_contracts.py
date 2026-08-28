from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from cumcm_toolkit.models import execute
from cumcm_toolkit.models.specifications import list_capabilities


ROOT = Path(__file__).resolve().parents[3]
SKILLS = tuple(
    json.loads((ROOT / "adapters/codex/skills/catalog.json").read_text(encoding="utf-8"))[
        "skills"
    ]
)
REQUIRED_SECTIONS = (
    "## Overview",
    "## When to Use",
    "## Do Not Use",
    "## Workflow",
    "## Failure Closure",
    "## Handoff Contract",
    "## Quick Reference",
    "## Common Mistakes",
)


def _root() -> Path:
    return ROOT


def _frontmatter(text: str) -> dict[str, object]:
    assert text.startswith("---\n")
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


def test_routing_snapshot_covers_every_skill() -> None:
    cases = yaml.safe_load(
        (_root() / "tests/snapshots/codex-skills/routing-cases.yaml").read_text(encoding="utf-8")
    )["skills"]
    assert set(cases) == set(SKILLS)
    for skill, examples in cases.items():
        assert len(examples["trigger"]) >= 2, skill
        assert len(examples["non_trigger"]) >= 2, skill


def test_each_skill_has_discoverable_metadata_and_contract() -> None:
    for name in SKILLS:
        skill_dir = _root() / "adapters/codex/skills" / name
        skill_file = skill_dir / "SKILL.md"
        assert skill_file.is_file(), f"missing {skill_file}"
        text = skill_file.read_text(encoding="utf-8")
        metadata = _frontmatter(text)
        assert metadata["name"] == name
        description = str(metadata["description"])
        assert description.startswith("Use when ")
        assert len(description) <= 500
        for section in REQUIRED_SECTIONS:
            assert section in text, f"{name} missing {section}"
        for field in (
            "status",
            "artifact_type",
            "inputs",
            "outputs",
            "evidence",
            "missing_inputs",
            "failed_step",
            "resume_when",
        ):
            assert re.search(rf"\b{field}\b", text), f"{name} missing handoff field {field}"

        ui = yaml.safe_load((skill_dir / "agents/openai.yaml").read_text(encoding="utf-8"))
        assert 25 <= len(ui["interface"]["short_description"]) <= 64
        assert f"${name}" in ui["interface"]["default_prompt"]


def test_each_skill_declares_safe_existing_shared_resources() -> None:
    root = _root()
    for name in SKILLS:
        manifest_path = root / "adapters/codex/skills" / name / "resources.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["skill"] == name
        assert manifest["resources"], f"{name} has no declared resources"
        for relative in manifest["resources"]:
            path = Path(relative)
            assert not path.is_absolute() and ".." not in path.parts
            assert path.parts[0] in {"adapters", "scripts", "shared", "toolkit"}
            assert (root / path).exists(), f"{name}: missing {relative}"


def test_fail_closed_language_is_explicit() -> None:
    root = _root()
    for name in SKILLS:
        text = (root / "adapters/codex/skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "status: blocked" in text
        assert "Do not fabricate" in text

    solver = (root / "adapters/codex/skills/solver/SKILL.md").read_text(encoding="utf-8")
    assert "linear-regression" in solver and "linear programming" in solver
    assert "unsupported" in solver.lower()

    sensitivity = (
        root / "adapters/codex/skills/sensitivity-analyst/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "zero valid" in sensitivity.lower()

    literature = (
        root / "adapters/codex/skills/literature-researcher/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "candidate" in literature.lower()
    assert "must not approve" in literature.lower()

    reviewer = (root / "adapters/codex/skills/model-reviewer/SKILL.md").read_text(encoding="utf-8")
    assert "read-only" in reviewer.lower()
    assert "must not modify" in reviewer.lower()
    assert "input_digest" in reviewer
    assert "decision_status" in reviewer

    orchestrator = (
        root / "adapters/codex/skills/cumcm-orchestrator/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "exactly one" in orchestrator.lower()
    assert "must not self-approve" in orchestrator.lower()
    assert "four human gates" in orchestrator.lower()


def test_model_selector_declares_every_model_card() -> None:
    root = _root()
    declaration = json.loads(
        (root / "adapters/codex/skills/model-selector/resources.json").read_text(encoding="utf-8")
    )
    assert "shared/knowledge/model-cards" in declaration["resources"]


def test_runtime_routing_and_handoff_helpers_are_packaged() -> None:
    root = _root()
    expected = {
        "solver": "adapters/codex/routing.py",
        "literature-researcher": "adapters/codex/routing.py",
        "model-reviewer": "adapters/codex/handoff.py",
        "repro-reviewer": "adapters/codex/handoff.py",
        "paper-reviewer": "adapters/codex/handoff.py",
        "red-team-reviewer": "adapters/codex/handoff.py",
        "submission-auditor": "adapters/codex/handoff.py",
        "cumcm-orchestrator": "toolkit/src/cumcm_toolkit/workflow/actions.py",
    }
    for skill, resource in expected.items():
        declaration = json.loads(
            (root / "adapters/codex/skills" / skill / "resources.json").read_text(
                encoding="utf-8"
            )
        )
        assert resource in declaration["resources"]

    for skill in SKILLS:
        text = (root / "adapters/codex/skills" / skill / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "references/<source path>" in text
        assert "references/shared/<source path>" not in text

    for skill in (
        "problem-reader",
        "data-auditor",
        "model-selector",
        "solver",
        "sensitivity-analyst",
        "literature-researcher",
    ):
        declaration = json.loads(
            (root / "adapters/codex/skills" / skill / "resources.json").read_text(
                encoding="utf-8"
            )
        )
        assert "adapters/codex/handoff.py" in declaration["resources"]
        assert "toolkit/src/cumcm_toolkit/artifacts/index.py" in declaration["resources"]
        assert "shared/contracts/artifact.schema.json" in declaration["resources"]
        assert "scripts/contract_formats.py" in declaration["resources"]
        assert "scripts/validate_contracts.py" in declaration["resources"]


def test_five_reviewers_have_isolated_formal_review_resources() -> None:
    root = _root()
    reviewers = {
        "submission-auditor": "shared/rubrics/submission.yaml",
        "repro-reviewer": "shared/rubrics/reproducibility.yaml",
        "model-reviewer": "shared/rubrics/model-quality.yaml",
        "paper-reviewer": "shared/rubrics/paper-quality.yaml",
        "red-team-reviewer": "shared/rubrics/red-team.yaml",
    }
    all_rubrics = set(reviewers.values())
    common = {
        "shared/contracts/review-report.schema.json",
        "shared/contracts/review-finding.schema.json",
        "toolkit/src/cumcm_toolkit/review/engine.py",
        "toolkit/src/cumcm_toolkit/review/severity.py",
        "toolkit/src/cumcm_toolkit/review/scorecard.py",
    }
    for skill, own_rubric in reviewers.items():
        declaration = json.loads(
            (root / "adapters/codex/skills" / skill / "resources.json").read_text(
                encoding="utf-8"
            )
        )
        resources = set(declaration["resources"])
        assert common <= resources
        assert own_rubric in resources
        assert not (all_rubrics - {own_rubric}) & resources

    model_text = (root / "adapters/codex/skills/model-reviewer/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "cannot approve reproducibility" in model_text.lower()
    assert "separate reproducibility" in model_text.lower()


def _documented_executor_examples(guide: str) -> dict[str, dict[str, object]]:
    sections = re.findall(
        r"^### `([^`]+)`\n(.*?)(?=^### `|\Z)", guide, flags=re.MULTILINE | re.DOTALL
    )
    examples: dict[str, dict[str, object]] = {}
    for model_id, body in sections:
        payload_match = re.search(
            r"最小合法 payload：\n```json\n(.*?)\n```", body, flags=re.DOTALL
        )
        failure_match = re.search(
            r"失败 payload：\n```json\n(.*?)\n```", body, flags=re.DOTALL
        )
        core_marker = re.search(r"核心输出：([^\n]+)", body)
        assert payload_match is not None, f"{model_id}: missing minimal payload"
        assert failure_match is not None, f"{model_id}: missing failure payload"
        assert core_marker is not None, f"{model_id}: missing core output fields"
        examples[model_id] = {
            "payload": json.loads(payload_match.group(1)),
            "failure": json.loads(failure_match.group(1)),
            "core": re.findall(r"`([^`]+)`", core_marker.group(1)),
        }
    return examples


def test_solver_docs_execute_every_registered_minimal_payload_and_failure_example(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guide = (ROOT / "docs/operations/model-executors.md").read_text(encoding="utf-8")
    examples = _documented_executor_examples(guide)
    capabilities = {str(item["model_id"]): item for item in list_capabilities()}
    assert set(examples) == set(capabilities)
    monkeypatch.setenv("LOKY_MAX_CPU_COUNT", "1")

    for model_id, example in examples.items():
        result = execute(model_id, example["payload"])
        assert result["status"] == "succeeded"
        assert result["executor"] == capabilities[model_id]["executor"]
        assert example["core"]
        assert set(example["core"]) <= set(result["result"])
        with pytest.raises(ValueError, match=re.escape(model_id)):
            execute(model_id, example["failure"])


def test_solver_docs_define_public_execute_and_legacy_run_model_boundaries() -> None:
    guide = (ROOT / "docs/operations/model-executors.md").read_text(encoding="utf-8")
    skill_guide = (ROOT / "docs/operations/codex-modeling-skills.md").read_text(
        encoding="utf-8"
    )
    combined = guide + "\n" + skill_guide

    assert "cumcm_toolkit.models.execution.execute" in combined
    assert "Codex/DSH" in combined
    assert "JSON" in combined
    assert "run_model" in combined
    assert "legacy" in combined.lower()
    assert "estimator" in combined
