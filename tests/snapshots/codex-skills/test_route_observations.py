from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.validate_codex_route_observations import validate_observations


ROOT = Path(__file__).resolve().parents[3]


def _cases() -> dict:
    return yaml.safe_load(
        (ROOT / "tests/snapshots/codex-skills/routing-cases.yaml").read_text(
            encoding="utf-8"
        )
    )


def _complete_observations(cases: dict) -> list[dict[str, object]]:
    observations = []
    run_number = 0
    for skill, groups in cases["skills"].items():
        for case_type in ("trigger", "non_trigger"):
            for prompt in groups[case_type]:
                run_number += 1
                observations.append(
                    {
                        "run_id": f"run-{run_number:03d}",
                        "model": "recorded-agent-model",
                        "skill": skill,
                        "case_type": case_type,
                        "prompt": prompt,
                        "observed_skill": skill if case_type == "trigger" else None,
                    }
                )
    return observations


def test_complete_forward_observations_pass() -> None:
    cases = _cases()
    report = validate_observations(cases, _complete_observations(cases))
    assert report == {"cases": 48, "errors": [], "status": "ok"}


def test_missing_duplicate_or_wrong_route_observation_fails() -> None:
    cases = _cases()
    observations = _complete_observations(cases)
    observations.pop()
    observations.append(dict(observations[0]))
    observations[1]["observed_skill"] = "wrong-skill"
    with pytest.raises(ValueError, match="routing observations invalid"):
        validate_observations(cases, observations)
