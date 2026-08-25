from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from cumcm_toolkit.review.bundle import REVIEW_SLOTS, build_review_bundle
from cumcm_toolkit.review.engine import is_review_current, load_rubric, review
from cumcm_toolkit.review.inputs import (
    build_paper_inputs,
    build_reproducibility_inputs,
    build_submission_inputs,
)


ROOT = Path(__file__).resolve().parents[2]
CAPABILITIES = {
    "citation_check",
    "latex_lint",
    "latex_build",
    "pdf_inspect",
    "evidence_linker",
    "citation_linker",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hash(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha(path)
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _scores(rubric: dict[str, object], score: float = 90) -> list[dict[str, object]]:
    return [
        {
            "dimension_id": item["dimension_id"],
            "score": score,
            "rationale": f"Current evidence for {item['dimension_id']}",
            "evidence_refs": ["clm_key_result"],
        }
        for item in rubric["scoring"]["dimensions"]  # type: ignore[index]
    ]


def _setup(project: Path) -> dict[str, object]:
    phase3 = project / "phase3"
    paper = project / "paper"
    phase3.mkdir(parents=True)
    paper.mkdir(parents=True)
    (phase3 / "input.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    (phase3 / "solve.py").write_text("print('solved')\n", encoding="utf-8")
    (paper / "main.tex").write_text("\\section{Result} Supported result.\n", encoding="utf-8")
    (paper / "main.pdf").write_bytes(b"verified-phase4-pdf-fixture")

    kinds = ["problem-analysis", "data-audit", "model-selection", "solver-run", "sensitivity-report"]
    handoffs: list[dict[str, object]] = []
    artifacts: list[dict[str, object]] = []
    phase3_files: list[Path] = []
    for kind in kinds:
        output = phase3 / f"{kind}.json"
        payload = {"kind": kind, "status": "complete"}
        output.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        phase3_files.append(output)
        artifact_id = f"art_{kind.replace('-', '_')}"
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "path": output.relative_to(project).as_posix(),
                "sha256": _sha(output),
            }
        )
        handoffs.append(
            {
                "status": "complete",
                "artifact_type": kind,
                "inputs": [],
                "outputs": [output.relative_to(project).as_posix()],
                "evidence": ["clm_key_result"] if kind == "solver-run" else [artifact_id],
                "missing_inputs": [],
                "failed_step": None,
                "resume_when": [],
            }
        )
    artifacts.extend(
        [
            {
                "artifact_id": "art_input",
                "path": "phase3/input.csv",
                "sha256": _sha(phase3 / "input.csv"),
            },
            {
                "artifact_id": "art_code",
                "path": "phase3/solve.py",
                "sha256": _sha(phase3 / "solve.py"),
            },
        ]
    )
    experiments = [
        {
            "experiment_id": "exp_solver_run",
            "input_artifact_ids": ["art_input"],
            "code_artifact_id": "art_code",
            "output_artifact_ids": ["art_solver_run"],
            "environment": {"python_version": "3.11", "lock_sha256": "a" * 64},
            "status": "succeeded",
        }
    ]
    links = [
        {
            "claim_id": "clm_key_result",
            "artifact_id": "art_solver_run",
            "experiment_id": "exp_solver_run",
        }
    ]
    repro_inputs = build_reproducibility_inputs(
        handoffs,
        artifact_records=artifacts,
        experiment_records=experiments,
        evidence_links=links,
    )
    model_inputs = {
        "model_selection": {
            "baseline": "mean predictor",
            "candidate_comparison": ["mean predictor", "linear regression"],
            "validation_plan": {"metric": "rmse", "split": "held-out"},
        },
        "sensitivity_report": {"status": "complete"},
        "evidence_refs": ["clm_key_result"],
        "evidence_index": {"clm_key_result": links[0]},
    }
    paper_inputs = build_paper_inputs(
        evidence_report={"status": "ok", "unresolved": []},
        citation_report={"status": "ok", "errors": []},
        lint_report={"status": "ok", "issues": []},
        key_claim_ids=["clm_key_result"],
        claim_boundaries=[{"claim_id": "clm_key_result", "boundary": "held-out set only"}],
        limitations=["The sample is small."],
        evidence_index={"clm_key_result": links[0]},
        challenges=[
            {
                "claim_id": "clm_key_result",
                "challenge": "Could leakage explain the result?",
                "response": "The split is held out.",
            }
        ],
    )
    submission_inputs = build_submission_inputs(
        build_report={"status": "ok", "undefined_references": []},
        lint_report={"status": "ok", "issues": []},
        citation_report={"status": "ok", "errors": []},
        pdf_report={"status": "ok", "blank_pages": [], "errors": []},
        source_sha256=_sha(paper / "main.tex"),
        pdf_sha256=_sha(paper / "main.pdf"),
        annual_rule_verified=True,
        evidence_refs=["clm_key_result"],
        evidence_index={"clm_key_result": links[0]},
    )
    inputs = {
        "submission": submission_inputs,
        "reproducibility": repro_inputs,
        "model": model_inputs,
        "paper": paper_inputs,
        "red_team": copy.deepcopy(paper_inputs),
    }
    rubric_files = {
        "submission": "submission.yaml",
        "reproducibility": "reproducibility.yaml",
        "model": "model-quality.yaml",
        "paper": "paper-quality.yaml",
        "red_team": "red-team.yaml",
    }
    rubrics = {
        slot: load_rubric(ROOT / "shared/rubrics" / filename)
        for slot, filename in rubric_files.items()
    }
    scores = {"model": _scores(rubrics["model"]), "paper": _scores(rubrics["paper"])}
    reviewed_files = {
        "submission": [paper / "main.tex", paper / "main.pdf"],
        "reproducibility": phase3_files,
        "model": [phase3 / "model-selection.json", phase3 / "sensitivity-report.json"],
        "paper": [paper / "main.tex"],
        "red_team": [paper / "main.tex"],
    }
    reports = {
        slot: review(
            inputs[slot],
            rubrics[slot],
            capabilities=CAPABILITIES,
            score_dimensions=scores.get(slot),
            reviewed_files=reviewed_files[slot],
            file_root=project,
            reviewed_at="2026-08-25T12:00:00+08:00",
        )
        for slot in REVIEW_SLOTS
    }
    return {
        "inputs": inputs,
        "rubrics": rubrics,
        "scores": scores,
        "reviewed_files": reviewed_files,
        "reports": reports,
    }


def test_five_gate_ready_flow_is_read_only_and_revision_invalidates_paper_gates(
    tmp_path: Path,
) -> None:
    material = _setup(tmp_path)
    before = _tree_hash(tmp_path)
    reports = material["reports"]
    assert all(report["status"] == "passed" for report in reports.values())
    assert len({report["rubric_id"] for report in reports.values()}) == 5
    assert reports["model"]["scorecard"]["weighted_total"] == 90
    assert reports["paper"]["scorecard"]["weighted_total"] == 90
    bundle = build_review_bundle(
        reports=reports,
        current_inputs=material["inputs"],
        rubrics=material["rubrics"],
        reviewed_files=material["reviewed_files"],
        reviewed_artifact_ids=["art_final_paper"],
        file_root=tmp_path,
        score_dimensions=material["scores"],
        created_at="2026-08-25T13:00:00+08:00",
    )
    assert bundle["readiness"] == "ready_for_phase_6"
    assert _tree_hash(tmp_path) == before

    main = tmp_path / "paper/main.tex"
    main.write_text(main.read_text(encoding="utf-8") + "Revision.\n", encoding="utf-8")
    for slot in ("paper", "red_team", "submission"):
        assert not is_review_current(
            reports[slot],
            material["inputs"][slot],
            material["rubrics"][slot],
            reviewed_files=material["reviewed_files"][slot],
            file_root=tmp_path,
            score_dimensions=material["scores"].get(slot),
        )
    for slot in ("reproducibility", "model"):
        assert is_review_current(
            reports[slot],
            material["inputs"][slot],
            material["rubrics"][slot],
            reviewed_files=material["reviewed_files"][slot],
            file_root=tmp_path,
            score_dimensions=material["scores"].get(slot),
        )
    stale_bundle = build_review_bundle(
        reports=reports,
        current_inputs=material["inputs"],
        rubrics=material["rubrics"],
        reviewed_files=material["reviewed_files"],
        reviewed_artifact_ids=["art_final_paper"],
        file_root=tmp_path,
        score_dimensions=material["scores"],
    )
    assert stale_bundle["readiness"] == "not_ready"


def test_gate_failures_remain_isolated(tmp_path: Path) -> None:
    material = _setup(tmp_path)
    reports = material["reports"]
    inputs = material["inputs"]
    rubrics = material["rubrics"]
    scores = material["scores"]
    files = material["reviewed_files"]

    bad_paper = copy.deepcopy(inputs["paper"])
    bad_paper["paper_reports"]["citations"]["status"] = "failed"
    paper_report = review(
        bad_paper,
        rubrics["paper"],
        capabilities=CAPABILITIES,
        score_dimensions=scores["paper"],
    )
    bad_submission = copy.deepcopy(inputs["submission"])
    bad_submission["submission_reports"]["citations"]["status"] = "failed"
    submission_report = review(
        bad_submission, rubrics["submission"], capabilities=CAPABILITIES
    )
    assert paper_report["status"] == submission_report["status"] == "failed"
    assert reports["red_team"]["status"] == "passed"

    uncovered = copy.deepcopy(inputs["red_team"])
    uncovered["paper_reports"]["challenges"] = []
    red_report = review(uncovered, rubrics["red_team"], capabilities=CAPABILITIES)
    assert red_report["status"] == "failed"
    assert reports["paper"]["status"] == "passed"

    low_scores = copy.deepcopy(scores["model"])
    low_scores[0]["score"] = 69
    model_report = review(
        inputs["model"], rubrics["model"], score_dimensions=low_scores
    )
    assert model_report["status"] == "failed"
    assert reports["reproducibility"]["status"] == "passed"
