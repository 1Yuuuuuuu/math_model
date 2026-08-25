from __future__ import annotations

from pathlib import Path

import yaml


FILES = {
    "reproducibility.yaml": "reproducibility",
    "model-quality.yaml": "model",
    "paper-quality.yaml": "paper",
    "red-team.yaml": "red_team",
    "submission.yaml": "hard",
}
SEVERITIES = {"S0", "S1", "S2", "S3"}
CHECKERS = {
    "required_path",
    "non_empty",
    "equals",
    "all_present",
    "hash_matches",
    "covers_claims",
}
PHASE4_RUBRICS = {"paper-quality.yaml", "red-team.yaml", "submission.yaml"}


def test_rubrics_have_consistent_safe_structure(project_root: Path) -> None:
    rubric_root = project_root / "shared/rubrics"
    rubric_ids: set[str] = set()
    rule_ids: set[str] = set()
    for filename, gate in FILES.items():
        path = rubric_root / filename
        assert path.is_file(), f"missing rubric: {path}"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert payload["version"] == "1.0"
        assert payload["review_gate"] == gate
        assert payload["rubric_id"] not in rubric_ids
        rubric_ids.add(payload["rubric_id"])
        assert isinstance(payload["requires_capabilities"], list)
        assert payload["rules"]
        if filename in PHASE4_RUBRICS:
            assert payload["requires_capabilities"], filename
        for rule in payload["rules"]:
            assert rule["rule_id"] not in rule_ids
            rule_ids.add(rule["rule_id"])
            assert rule["severity"] in SEVERITIES
            assert rule["checker"] in CHECKERS
            assert isinstance(rule["params"], dict)
            assert isinstance(rule["evidence_paths"], list) and rule["evidence_paths"]
            assert str(rule["summary"]).strip()
            assert str(rule["recommendation"]).strip()
