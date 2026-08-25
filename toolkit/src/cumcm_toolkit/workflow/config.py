from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


STAGES = ["intake", "model_design", "solve", "outline", "write", "review", "submission", "complete"]
GATES = ["gate_1_problem", "gate_2_model", "gate_3_outline", "gate_4_submission"]
EVENT_TYPES = {
    "workspace_started",
    "child_completed",
    "stage_completed",
    "stage_failed",
    "resumed",
    "gate_decided",
    "literature_branch_decided",
    "review_bundle_attached",
    "submission_completed",
}


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate YAML key: {key}", key_node.start_mark
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot load workflow config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("workflow config must be a mapping")
    return value


def _exact_fields(value: dict, expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields must be exactly: {', '.join(sorted(expected))}")


def load_workflow_config(
    transitions_path: Path,
    schedule_path: Path,
    *,
    skill_catalog_path: Path,
) -> dict[str, Any]:
    transitions = _load(transitions_path)
    schedule = _load(schedule_path)
    _exact_fields(
        transitions,
        {"workflow_id", "version", "stage_order", "event_types", "gates", "automatic_transitions"},
        "transition config",
    )
    _exact_fields(
        schedule,
        {"workflow_id", "version", "timeboxes", "routes", "literature_branch", "review"},
        "schedule config",
    )
    if transitions["workflow_id"] != "cumcm-72h" or schedule["workflow_id"] != "cumcm-72h":
        raise ValueError("workflow_id must be cumcm-72h")
    if transitions["version"] != "1.0" or schedule["version"] != "1.0":
        raise ValueError("workflow config version must be 1.0")
    if transitions["stage_order"] != STAGES:
        raise ValueError("invalid stage order")
    if set(transitions["event_types"]) != EVENT_TYPES or len(transitions["event_types"]) != len(EVENT_TYPES):
        raise ValueError("invalid event types")
    gates = transitions["gates"]
    if not isinstance(gates, dict) or list(gates) != GATES:
        raise ValueError("workflow must define exactly four ordered gates")
    expected_gate_routes = {
        "gate_1_problem": ("intake", "model_design"),
        "gate_2_model": ("model_design", "solve"),
        "gate_3_outline": ("outline", "write"),
        "gate_4_submission": ("review", "submission"),
    }
    for gate, route in gates.items():
        if not isinstance(route, dict) or set(route) != {"stage", "next_stage"}:
            raise ValueError(f"invalid gate route: {gate}")
        if (route["stage"], route["next_stage"]) != expected_gate_routes[gate]:
            raise ValueError(f"invalid transition for {gate}")
    if transitions["automatic_transitions"] != {
        "solve": "outline",
        "write": "review",
        "submission": "complete",
    }:
        raise ValueError("invalid automatic transitions")

    try:
        catalog = json.loads(skill_catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load Skill catalog: {exc}") from exc
    skills = set(catalog.get("skills", []))
    routes = schedule["routes"]
    if not isinstance(routes, dict) or list(routes) != STAGES:
        raise ValueError("routes must cover every stage in order")
    for stage, stage_skills in routes.items():
        if (
            not isinstance(stage_skills, list)
            or len(stage_skills) != len(set(stage_skills))
            or any(skill not in skills for skill in stage_skills)
        ):
            raise ValueError(f"unknown skill or duplicate route in stage {stage}")
    branch = schedule["literature_branch"]
    if not isinstance(branch, dict) or set(branch) != {"decision_stages", "skill", "gate"}:
        raise ValueError("invalid literature branch fields")
    if branch != {
        "decision_stages": ["solve", "outline"],
        "skill": "literature-researcher",
        "gate": "gate_3_outline",
    } or branch["skill"] not in skills:
        raise ValueError("invalid literature branch")
    review = schedule["review"]
    if not isinstance(review, dict) or set(review) != {"skills", "bundle_builder"}:
        raise ValueError("invalid review fields")
    if review["skills"] != routes["review"] or review["bundle_builder"] != "build_review_bundle":
        raise ValueError("invalid review route")

    timeboxes = schedule["timeboxes"]
    if not isinstance(timeboxes, list) or len(timeboxes) != len(STAGES):
        raise ValueError("timeboxes must cover all stages")
    previous_end = 0
    for stage, item in zip(STAGES, timeboxes):
        if not isinstance(item, dict) or set(item) != {"stage", "start_hour", "end_hour"}:
            raise ValueError("invalid timebox fields")
        if (
            item["stage"] != stage
            or isinstance(item["start_hour"], bool)
            or isinstance(item["end_hour"], bool)
            or not isinstance(item["start_hour"], int)
            or not isinstance(item["end_hour"], int)
            or item["start_hour"] != previous_end
            or item["end_hour"] <= item["start_hour"]
        ):
            raise ValueError("timeboxes must be contiguous and monotonic")
        previous_end = item["end_hour"]
    if previous_end != 72:
        raise ValueError("timeboxes must end at hour 72")
    return {
        **transitions,
        "timeboxes": timeboxes,
        "routes": routes,
        "literature_branch": branch,
        "review": review,
    }
