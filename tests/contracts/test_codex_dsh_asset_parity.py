"""Task 4b — Codex/DSH 双端共享资产奇偶测试（asset parity）。

断言三类一致性（对应计划 Task 4b / task-4b-brief.md）：

① 资产哈希清单双端一致：
   - codex 侧：scripts.package_codex_skills.package_skills 打包到 tmp_path，
     汇总各 skill 的 asset-manifest.json（source_path -> sha256）。
   - dsh 侧：scripts.package_dsh_assets.build_manifest 生成的 assets（路径 -> sha256）。
   - 以 model-cards 子集为锚（brief 指定，Task 5 review 协调项 I2）：
     双端覆盖集合一致 + 逐路径 sha256 一致；扩展 contracts 覆盖一致、knowledge 子集一致。
② 契约版本一致：
   - shared/contracts/catalog.json：catalog_version == "1.0"、15 个契约
     （id 与 tests/contracts/test_catalog.py 的 EXPECTED_CONTRACT_IDS 一致）。
   - 抽查 schema_version const 值（review-bundle / workflow-event / decision / modeling-handoff）
     双端一致（"1.0"），并与 cumcm_toolkit 产出的 schema_version 一致。
③ 关键产物形状语义一致：
   - modeling-handoff：12 个 DSH SKILL.md 的 Handoff Contract yaml 字段
     ⊆ schema required 8 基础字段 + Codex 扩展字段（review 系 decision_status/input_digest/rubric_digest、
     orchestrator next_action）；artifact_type ∈ schema enum；最小记录过 schema。
   - experiment：schema required 字段 == cumcm_toolkit.experiments.manifest.create_experiment_record
     产出键集，样例过 schema。
   - review-report：schema required 14 字段 == cumcm_toolkit.review.engine.review 产出键集，样例过 schema。
   - DSH SKILL.md 侧：12 目录名 == codex catalog skills 列表；solver / literature-researcher
     fail-closed 声明；无"已支持真实网络检索"类未实现能力声称。

纪律（Task 5 review 协调项）：断言基于字段/集合/哈希，不依赖 manifest 键序（I3）；
workflow 分类含 codex agents 哈希引用，双端对比以 model-cards 子集为锚（I2）；
不依赖 dist/ 产物，直接调用打包器函数（输出写 tmp_path）。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

import scripts.package_codex_skills as codex_pkg
import scripts.package_dsh_assets as dsh_pkg
from cumcm_toolkit.experiments.manifest import create_experiment_record
from cumcm_toolkit.review.engine import load_rubric, review
from scripts.package_codex_skills import package_skills
from scripts.package_dsh_assets import build_manifest
from tests.contracts.test_catalog import EXPECTED_CONTRACT_IDS

# --- 契约/形状常量 -----------------------------------------------------------

MODEL_CARDS_PREFIX = "shared/knowledge/model-cards/"
CONTRACTS_PREFIX = "shared/contracts/"
KNOWLEDGE_PREFIX = "shared/knowledge/"

# modeling-handoff schema 的 8 个基础必填字段（schema_version 由 DSH handoff 机制隐式承担）
HANDOFF_BASE_FIELDS = frozenset(
    {"status", "artifact_type", "inputs", "outputs", "evidence", "missing_inputs", "failed_step", "resume_when"}
)
# Codex 同款扩展字段：review 系（5 个）+ orchestrator（1 个）
HANDOFF_EXTENSION_REVIEW = frozenset({"decision_status", "input_digest", "rubric_digest"})
HANDOFF_EXTENSION_ORCHESTRATOR = frozenset({"next_action"})
REVIEW_EXTENDED_SKILLS = frozenset(
    {"model-reviewer", "repro-reviewer", "paper-reviewer", "red-team-reviewer", "submission-auditor"}
)
ORCHESTRATOR_SKILL = "cumcm-orchestrator"

# ② 抽查的契约（brief 指定）
SAMPLED_CONTRACTS = ("review-bundle", "workflow-event", "decision", "modeling-handoff")

# ③ 未实现能力声称的禁用表述（对 12 个 DSH SKILL.md 全量断言缺失）
FORBIDDEN_CAPABILITY_CLAIMS = (
    "已支持真实网络检索",
    "支持真实网络检索",
    "已实现真实网络检索",
    "实现真实检索",
    "真实检索已",
    "检索后端已实现",
    "网络检索已支持",
)

# --- 小工具 -------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dsh_skills(project_root: Path) -> dict[str, Path]:
    base = project_root / "adapters/dsh/skills"
    return {p.name: p / "SKILL.md" for p in sorted(base.iterdir()) if p.is_dir()}


def _read_handoff_yaml(skill_md: Path) -> dict:
    """提取 SKILL.md 中 Handoff Contract 的 ```yaml 块并解析为 dict。"""
    text = skill_md.read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\r?\n(.*?)\r?\n```", text, flags=re.DOTALL)
    assert len(blocks) == 1, f"expected exactly one yaml handoff block in {skill_md}"
    payload = yaml.safe_load(blocks[0])
    assert isinstance(payload, dict), skill_md
    return payload


def _read_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\r?\n(.*?)\r?\n---", text, flags=re.DOTALL)
    assert match is not None, skill_md
    payload = yaml.safe_load(match.group(1))
    assert isinstance(payload, dict), skill_md
    return payload


def _schema_version_consts(schema: dict) -> set[str]:
    """递归收集契约 schema 中所有可达的 schema_version const（兼容 oneOf/allOf/$defs 结构）。"""

    def walk(node: object) -> None:
        if not isinstance(node, dict):
            return
        version = node.get("properties", {}).get("schema_version", {}).get("const")
        if version is not None:
            found.add(str(version))
        for key in ("oneOf", "anyOf", "allOf"):
            for child in node.get(key, []):
                walk(child)
        for child in node.get("$defs", {}).values():
            walk(child)
        for child in node.get("properties", {}).values():
            walk(child)

    found: set[str] = set()
    walk(schema)
    return found


def _codex_packaged_assets(project_root: Path, tmp_path: Path) -> dict[str, str]:
    """运行 codex 打包器到 tmp，返回跨 skill 合并的 {source_path: sha256}。"""
    output = tmp_path / "codex-skills"  # 必须不存在（package_skills 拒绝覆盖）
    package_skills(project_root, output)
    assets: dict[str, str] = {}
    for manifest_path in sorted(output.glob("*/asset-manifest.json")):
        for entry in _load_json(manifest_path)["assets"]:
            assets.setdefault(entry["source_path"], entry["sha256"])
    return assets


# --- 模块级夹具（每个打包器只跑一次） ----------------------------------------

@pytest.fixture(scope="module")
def codex_assets(project_root: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return _codex_packaged_assets(project_root, tmp_path_factory.mktemp("parity-codex"))


@pytest.fixture(scope="module")
def dsh_manifest(project_root: Path) -> dict:
    return build_manifest(project_root)


# ① 资产哈希清单双端一致 --------------------------------------------------------

def test_model_cards_coverage_identical_between_packagers(
    codex_assets: dict[str, str], dsh_manifest: dict
) -> None:
    """model-cards 子集双端覆盖集合一致（Task 5 锚：33 个，与 codex *.md 全集严格一致）。"""
    codex_cards = {p: h for p, h in codex_assets.items() if p.startswith(MODEL_CARDS_PREFIX)}
    dsh_cards = {
        p: dsh_manifest["assets"][p] for p in dsh_manifest["asset_categories"]["model-cards"]
    }
    assert set(codex_cards) == set(dsh_cards)
    assert len(dsh_cards) == 33


def test_model_cards_hashes_identical_between_packagers(
    codex_assets: dict[str, str], dsh_manifest: dict, project_root: Path
) -> None:
    """同一源文件在 codex 打包器与 dsh 打包器中的 sha256 相同（与源文件现算值一致）。"""
    dsh_cards = {
        p: dsh_manifest["assets"][p] for p in dsh_manifest["asset_categories"]["model-cards"]
    }
    for path, digest in dsh_cards.items():
        assert codex_assets[path] == digest == _sha256(project_root / path), path


def test_contracts_coverage_identical_between_packagers(
    codex_assets: dict[str, str], dsh_manifest: dict, project_root: Path
) -> None:
    """扩展：contracts 子集双端覆盖一致（16 = 15 schema + catalog.json），哈希一致。"""
    codex_contracts = {p: h for p, h in codex_assets.items() if p.startswith(CONTRACTS_PREFIX)}
    dsh_contracts = {
        p: dsh_manifest["assets"][p] for p in dsh_manifest["asset_categories"]["contracts"]
    }
    assert set(codex_contracts) == set(dsh_contracts)
    assert len(dsh_contracts) == 16
    for path, digest in dsh_contracts.items():
        assert codex_contracts[path] == digest == _sha256(project_root / path), path


def test_knowledge_codex_subset_of_dsh_with_equal_hashes(
    codex_assets: dict[str, str], dsh_manifest: dict, project_root: Path
) -> None:
    """扩展：codex 引用的 knowledge 文件 ⊆ dsh knowledge 分类，且双端哈希一致。"""
    codex_knowledge = {p: h for p, h in codex_assets.items() if p.startswith(KNOWLEDGE_PREFIX)}
    dsh_knowledge = {
        p: dsh_manifest["assets"][p] for p in dsh_manifest["asset_categories"]["knowledge"]
    }
    assert set(codex_knowledge) <= set(dsh_knowledge)
    for path, digest in codex_knowledge.items():
        assert digest == dsh_knowledge[path] == _sha256(project_root / path), path


def test_manifest_parsed_by_field_not_key_order(dsh_manifest: dict) -> None:
    """Task 5 concern I3：dsh manifest 键序是 sort_keys 结果——按字段解析，勿比文本/键序。"""
    assert dsh_manifest["manifest_version"] == "1.0"
    assert isinstance(dsh_manifest["assets"], dict) and dsh_manifest["assets"]
    assert set(dsh_manifest["asset_categories"]) == {
        "contracts",
        "templates",
        "knowledge",
        "model-cards",
        "workflow",
    }


# ② 契约版本一致 ----------------------------------------------------------------

def test_catalog_version_and_contract_ids(project_root: Path) -> None:
    """catalog 15 个契约、id 与 test_catalog.py 的 EXPECTED_CONTRACT_IDS 一致。"""
    catalog = _load_json(project_root / "shared/contracts/catalog.json")
    assert catalog["catalog_version"] == "1.0"
    ids = [entry["id"] for entry in catalog["contracts"]]
    assert set(ids) == EXPECTED_CONTRACT_IDS
    assert len(ids) == 15
    assert len(set(ids)) == 15
    # 双端目录版本锚一致：codex skill catalog 与 shared contract catalog 同为 "1.0"
    codex_catalog = _load_json(project_root / "adapters/codex/skills/catalog.json")
    assert codex_catalog["catalog_version"] == "1.0"


def test_schema_version_const_consistent_across_sampled_contracts(project_root: Path) -> None:
    """抽查 review-bundle / workflow-event / decision / modeling-handoff 的 schema_version const。

    decision schema 为 oneOf 双版本结构（v1 const "1.0" + v2 legacy 迁移分支 const "2.0"，
    与 tests/contracts/test_decision_migration.py 的迁移语义一致）；当前轨道版本仍为 "1.0"。
    """
    catalog = _load_json(project_root / "shared/contracts/catalog.json")
    by_id = {entry["id"]: entry for entry in catalog["contracts"]}
    for contract_id in SAMPLED_CONTRACTS:
        schema = _load_json(project_root / by_id[contract_id]["schema"])
        consts = _schema_version_consts(schema)
        assert "1.0" in consts, (contract_id, consts)
        if contract_id == "decision":
            assert consts == {"1.0", "2.0"}, consts
        else:
            assert consts == {"1.0"}, (contract_id, consts)


# ③ 关键产物形状语义一致 --------------------------------------------------------

def test_dsh_skill_dirs_match_codex_catalog(project_root: Path) -> None:
    """12 个 DSH 目录名 == codex catalog skills 列表（frontmatter name == 目录名）。"""
    codex_catalog = _load_json(project_root / "adapters/codex/skills/catalog.json")
    expected = set(codex_catalog["skills"])
    assert len(expected) == 12
    dsh = _dsh_skills(project_root)
    assert set(dsh) == expected
    for name, path in dsh.items():
        assert _read_frontmatter(path)["name"] == name


def test_handoff_contract_fields_within_schema_required_plus_codex_extensions(
    project_root: Path,
) -> None:
    """12 份 Handoff Contract yaml 字段 ⊆ modeling-handoff required 8 基础字段 + Codex 扩展字段。"""
    schema = _load_json(project_root / "shared/contracts/modeling-handoff.schema.json")
    required = set(schema["required"])
    assert HANDOFF_BASE_FIELDS <= required  # 8 个基础字段在 schema 必填集内
    artifact_enum = set(schema["properties"]["artifact_type"]["enum"])
    for name, path in _dsh_skills(project_root).items():
        payload = _read_handoff_yaml(path)
        keys = set(payload)
        allowed = HANDOFF_BASE_FIELDS
        if name in REVIEW_EXTENDED_SKILLS:
            allowed = allowed | HANDOFF_EXTENSION_REVIEW
        elif name == ORCHESTRATOR_SKILL:
            allowed = allowed | HANDOFF_EXTENSION_ORCHESTRATOR
        assert keys <= allowed, (name, sorted(keys - allowed))
        assert HANDOFF_BASE_FIELDS <= keys, (name, sorted(HANDOFF_BASE_FIELDS - keys))
        if name in REVIEW_EXTENDED_SKILLS:
            assert HANDOFF_EXTENSION_REVIEW <= keys, name
        if name == ORCHESTRATOR_SKILL:
            assert HANDOFF_EXTENSION_ORCHESTRATOR <= keys, name
        assert payload["artifact_type"] in artifact_enum, name


def test_modeling_handoff_minimal_record_validates(project_root: Path) -> None:
    """对 12 个 artifact_type 各构造一条最小 complete 记录，断言过 modeling-handoff schema。"""
    schema = _load_json(project_root / "shared/contracts/modeling-handoff.schema.json")
    validator = Draft202012Validator(schema)
    for name, path in _dsh_skills(project_root).items():
        payload = _read_handoff_yaml(path)
        record = {
            "schema_version": "1.0",
            "status": "complete",
            "artifact_type": payload["artifact_type"],
            "inputs": ["problem-statement.md"],
            "outputs": ["artifacts/out.json"],
            "evidence": ["clm_parity_sample"],
            "missing_inputs": [],
            "failed_step": None,
            "resume_when": [],
        }
        errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
        assert not errors, (name, [error.message for error in errors])


def test_experiment_schema_required_matches_library_output(project_root: Path) -> None:
    """experiment：schema required 字段 == create_experiment_record 产出键集（双端版本一致）。"""
    schema = _load_json(project_root / "shared/contracts/experiment.schema.json")
    record = create_experiment_record(
        input_artifact_ids=["art_input_a"],
        code_artifact_id="art_code_a",
        parameters={"alpha": 0.1},
        random_seed=42,
        status="succeeded",
        output_artifact_ids=["art_output_a"],
        metrics={"rmse": 0.5},
        project_root=project_root,
    )
    assert set(record) == set(schema["required"])
    assert record["schema_version"] == schema["properties"]["schema_version"]["const"] == "1.0"
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
    assert not errors, [error.message for error in errors]


def test_review_report_schema_required_matches_library_output(project_root: Path, tmp_path: Path) -> None:
    """review-report：schema required 14 字段 == cumcm_toolkit.review.engine.review 产出键集。"""
    report_schema = _load_json(project_root / "shared/contracts/review-report.schema.json")
    finding_schema = _load_json(project_root / "shared/contracts/review-finding.schema.json")
    registry = Registry().with_resource(
        finding_schema["$id"], Resource.from_contents(finding_schema)
    )
    validator = Draft202012Validator(report_schema, registry=registry, format_checker=FormatChecker())

    rubric = load_rubric(project_root / "shared/rubrics/model-quality.yaml")
    artifact_root = tmp_path / "phase3"
    artifact_root.mkdir()
    inputs = {
        "problem_analysis": {"status": "complete"},
        "data_audit": {"status": "complete"},
        "model_selection": {
            "status": "complete",
            "baseline": "mean predictor",
            "candidate_comparison": [{"model": "linear-regression"}],
            "validation_plan": {"metric": "rmse"},
        },
        "solver_run": {"status": "complete", "experiment_id": "exp_review_001"},
        "sensitivity_report": {"status": "complete"},
        "evidence_refs": ["clm_model_review"],
        "evidence_index": {"clm_model_review": {"claim_id": "clm_model_review"}},
    }
    (artifact_root / "handoffs.json").write_text(
        json.dumps(inputs, sort_keys=True), encoding="utf-8"
    )
    score_dimensions = [
        {
            "dimension_id": item["dimension_id"],
            "score": 90,
            "rationale": f"Evidence for {item['dimension_id']}",
            "evidence_refs": ["clm_model_review"],
        }
        for item in rubric["scoring"]["dimensions"]
    ]
    report = review(
        inputs,
        rubric,
        reviewed_at="2026-08-25T12:00:00+08:00",
        reviewed_files=[artifact_root / "handoffs.json"],
        file_root=artifact_root,
        score_dimensions=score_dimensions,
    )
    assert set(report) == set(report_schema["required"])
    assert report["status"] == "passed"
    assert report["schema_version"] == report_schema["properties"]["schema_version"]["const"] == "1.0"
    errors = sorted(validator.iter_errors(report), key=lambda error: list(error.path))
    assert not errors, [error.message for error in errors]


# --- DSH SKILL.md 侧 fail-closed 与未实现能力声明 ------------------------------

def test_solver_fail_closed_declarations(project_root: Path) -> None:
    """solver：执行面限 registry 模型（plan-only），不得冒充替代品。"""
    text = (project_root / "adapters/dsh/skills/solver/SKILL.md").read_text(encoding="utf-8")
    assert "plan-only" in text
    assert "registry" in text
    for name in ("linear-regression", "decision-tree", "kmeans"):
        assert name in text
    assert "冒充" in text  # 不得用 registry 模型或手工计算冒充替代品
    assert "TOPSIS" in text and "plan-only" in text


def test_literature_fail_closed_declarations(project_root: Path) -> None:
    """literature-researcher：无后端/未授权 → blocked、候选为空；候选≠引用。"""
    text = (project_root / "adapters/dsh/skills/literature-researcher/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "未实现真实网络检索后端转发" in text  # 明确否定式声明
    assert "fail-closed" in text
    assert "blocked" in text
    assert "候选列表为空" in text
    assert "never become references" in text  # 候选≠引用


def test_no_unimplemented_capability_claims(project_root: Path) -> None:
    """12 个 DSH SKILL.md 均不含"已支持真实网络检索"类未实现能力声称。"""
    for name, path in _dsh_skills(project_root).items():
        text = path.read_text(encoding="utf-8")
        for phrase in FORBIDDEN_CAPABILITY_CLAIMS:
            assert phrase not in text, (name, phrase)
