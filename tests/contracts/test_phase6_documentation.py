from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase6_operator_and_handoff_docs_cover_governance() -> None:
    playbook = (ROOT / "docs/competition/72-hour-playbook.md").read_text(encoding="utf-8")
    recovery = (ROOT / "docs/competition/recovery-playbook.md").read_text(encoding="utf-8")
    handoff = (ROOT / "docs/operations/phase6-to-phase7-handoff.md").read_text(encoding="utf-8")
    combined = "\n".join((playbook, recovery, handoff))
    for phrase in (
        "gate_1_problem", "gate_2_model", "gate_3_outline", "gate_4_submission",
        "optional literature", "ready_for_phase_6", "resume_when", "16 contracts",
        "12 Codex Skills", "Phase 7", "DeepSeek Harness",
    ):
        assert phrase in combined
    assert "gate_5" not in combined
    assert "E:\\" not in combined
