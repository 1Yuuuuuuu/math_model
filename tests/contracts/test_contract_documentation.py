import json
from pathlib import Path


def load_catalog(project_root: Path) -> dict:
    return json.loads(
        (project_root / "shared/contracts/catalog.json").read_text(encoding="utf-8")
    )


def test_contract_docs_cover_every_catalog_entry_and_fixture_link(project_root: Path) -> None:
    architecture = (project_root / "docs/architecture/contracts.md").read_text(encoding="utf-8")
    catalog = load_catalog(project_root)

    for entry in catalog["contracts"]:
        assert f"`{entry['id']}`" in architecture
        valid_fixture = entry["valid_examples"][0]
        assert (project_root / valid_fixture).is_file()
        assert f"../../{valid_fixture}" in architecture


def test_contract_docs_explain_shared_format_and_path_rules(project_root: Path) -> None:
    architecture = (project_root / "docs/architecture/contracts.md").read_text(encoding="utf-8")

    for expected in (
        "scripts/contract_formats.py",
        "普通消费者不能忽略",
        "正斜杠 `/`",
        "不可越界",
        "时区",
        "synthetic",
        "不宣称官方规则",
    ):
        assert expected in architecture


def test_change_policy_defines_breaking_change_and_migration(project_root: Path) -> None:
    policy = (project_root / "docs/operations/change-policy.md").read_text(encoding="utf-8")

    for expected in (
        "破坏性变更",
        "迁移",
        "双端契约回归",
        "schema_version",
        "manifest_version",
        "年度规则",
        "溯源核验",
    ):
        assert expected in policy


def test_acceptance_gate_lists_exact_commands_and_operational_guarantees(project_root: Path) -> None:
    gate = (project_root / "docs/quality/acceptance-gates.md").read_text(encoding="utf-8")

    for expected in (
        "uv run pytest tests/contracts -v",
        "uv run python scripts/validate_contracts.py",
        "exit 0",
        "status = ok",
        "contracts = 9",
        "errors = []",
        "未完成标记",
        "命名原因",
        "离线",
        "只读",
        "零写入",
    ):
        assert expected in gate
