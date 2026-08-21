import json
from pathlib import Path
import re


CONTRACT_ROW = re.compile(r"^\|\s+`(?P<contract_id>[a-z][a-z0-9-]*)`\s+\|")


def load_catalog(project_root: Path) -> dict:
    return json.loads(
        (project_root / "shared/contracts/catalog.json").read_text(encoding="utf-8")
    )


def test_contract_docs_keep_each_fixture_link_on_its_contract_row(project_root: Path) -> None:
    architecture = (project_root / "docs/architecture/contracts.md").read_text(encoding="utf-8")
    catalog = load_catalog(project_root)
    rows = {
        match.group("contract_id"): line
        for line in architecture.splitlines()
        if (match := CONTRACT_ROW.match(line))
    }
    catalog_ids = {entry["id"] for entry in catalog["contracts"]}

    assert set(rows) == catalog_ids
    for entry in catalog["contracts"]:
        valid_fixture = entry["valid_examples"][0]
        assert (project_root / valid_fixture).is_file()
        assert f"../../{valid_fixture}" in rows[entry["id"]]


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
        "删除字段（包括可选字段）",
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
        "contracts = 11",
        "errors = []",
        "未完成标记",
        "命名原因",
        "离线",
        "只读",
        "零写入",
        "仅限于 `scripts/validate_contracts.py`",
        "uv 可能同步环境或访问依赖源",
        "pytest 可能生成缓存",
        "严格复核",
    ):
        assert expected in gate
