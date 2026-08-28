from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_model_executor_handoff_documents_phase7_consumption_surface() -> None:
    handoff = (
        ROOT / "docs/operations/model-executor-to-dsh-handoff.md"
    ).read_text(encoding="utf-8")

    for required_name in (
        "cumcm_toolkit.models.execution.execute",
        "cumcm_toolkit.models.specifications.list_capabilities",
        "shared/contracts/model-execution.schema.json",
        "JSON-only results",
        "no copied algorithm implementation",
        "Phase 7 rebase/merge order",
    ):
        assert required_name in handoff
