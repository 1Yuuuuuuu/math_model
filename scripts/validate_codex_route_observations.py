from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def validate_observations(cases: dict, observations: list[dict]) -> dict[str, object]:
    expected: dict[tuple[str, str, str], str | None] = {}
    skills = cases.get("skills")
    if not isinstance(skills, dict) or not skills:
        raise ValueError("routing observations invalid: routing cases are missing")
    for skill, groups in skills.items():
        if not isinstance(groups, dict):
            raise ValueError("routing observations invalid: malformed routing case group")
        for case_type in ("trigger", "non_trigger"):
            prompts = groups.get(case_type)
            if not isinstance(prompts, list):
                raise ValueError("routing observations invalid: malformed prompt list")
            for prompt in prompts:
                key = (skill, case_type, prompt)
                if key in expected:
                    raise ValueError("routing observations invalid: duplicate routing case")
                expected[key] = skill if case_type == "trigger" else None

    errors: list[str] = []
    observed: dict[tuple[str, str, str], dict] = {}
    run_ids: set[str] = set()
    for item in observations:
        if not isinstance(item, dict):
            errors.append("observation must be an object")
            continue
        key = (item.get("skill"), item.get("case_type"), item.get("prompt"))
        run_id = item.get("run_id")
        model = item.get("model")
        if not isinstance(run_id, str) or not run_id.strip():
            errors.append(f"missing run_id for {key!r}")
        elif run_id in run_ids:
            errors.append(f"duplicate run_id: {run_id}")
        else:
            run_ids.add(run_id)
        if not isinstance(model, str) or not model.strip():
            errors.append(f"missing model for {key!r}")
        if key not in expected:
            errors.append(f"unexpected observation: {key!r}")
            continue
        if key in observed:
            errors.append(f"duplicate observation: {key!r}")
            continue
        observed[key] = item

    for key, expected_skill in expected.items():
        item = observed.get(key)
        if item is None:
            errors.append(f"missing observation: {key!r}")
            continue
        actual = item.get("observed_skill")
        if expected_skill is not None and actual != expected_skill:
            errors.append(f"trigger routed incorrectly: {key!r} -> {actual!r}")
        if expected_skill is None and actual == key[0]:
            errors.append(f"non-trigger activated forbidden skill: {key!r}")

    if errors:
        raise ValueError("routing observations invalid: " + "; ".join(errors))
    return {"cases": len(expected), "errors": [], "status": "ok"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate recorded fresh-agent routing observations."
    )
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("tests/snapshots/codex-skills/routing-cases.yaml"),
    )
    args = parser.parse_args()
    try:
        cases = yaml.safe_load(args.cases.read_text(encoding="utf-8"))
        observations = json.loads(args.observations.read_text(encoding="utf-8"))
        if not isinstance(observations, list):
            raise ValueError("observations must be a JSON array")
        report = validate_observations(cases, observations)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "status": "failed"}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
