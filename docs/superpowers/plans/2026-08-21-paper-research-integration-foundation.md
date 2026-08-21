# Paper Research Integration Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有论文 Skill 与文献检索 Skill 纳入工作台的阶段化路线，建立可验证的能力盘点、文献来源契约、引用证据契约和用户使用说明，同时不提前实现尚未具备依赖的论文总控或 DSH 插件。

**Architecture:** `cumcm-orchestrator` 仍是未来默认入口，`literature-researcher` 是按需子 Skill，`cumcm-paper` 与 `math-modeling-paper` 是用户显式选择的兼容备选。当前增量只建设共享契约、只读能力盘点和文档接口；Codex Skill、论文引用工具、总控路由与 DSH 插件分别留在 Phase 3、4、6、7 实现。

**Tech Stack:** Python 3.11、uv、pytest、JSON Schema Draft 2020-12、`jsonschema`、`referencing`、SHA-256、Markdown、Codex Skills、DeepSeek Harness。

**Spec:** `docs/superpowers/specs/2026-08-21-paper-research-skill-integration-design.md`

## Global Constraints

- `shared/` 是仓库内唯一事实来源；个人 Skill 只能作为迁移输入或用户显式选择的 legacy 入口。
- 不修改 `C:/Users/YU/.codex/skills/`，不安装 `paper-search`，不安装 `cumcm_*` 插件。
- `paper-search` CLI 和 `cumcm_*` 工具当前不可用；任何文档都不得把它们写成已安装能力。
- 文献检索只生成候选；未经人工确认不得进入论文引用。
- 不新增第五个全局人工门；正式引用在 gate 3 提纲确认中批准。
- 所有来源元数据、路径、URL、时间与 JSON 使用 Phase 0 已验证的严格格式语义。
- 缺少后端、元数据冲突或全文不匹配时停止，不用模型记忆补全 DOI、作者、年份或结论。
- Codex 与 DSH 只共享仓库打包资产，不依赖用户机器上的绝对路径或符号链接。
- 所有 Skill 创建或修改必须先有无 Skill 基线失败，再按 RED–GREEN–REFACTOR 前向测试；本计划不提前创建运行时 Skill。
- 每个任务独立提交并通过新鲜评审；范围外缺陷记入 ledger，不顺手扩展。

---

## File structure and ownership

| 文件 | 单一职责 |
| --- | --- |
| `scripts/inventory_paper_skills.py` | 只读盘点三个 legacy Skill 的存在性、文件哈希和 `paper-search` CLI 可用性 |
| `tests/integration/test_paper_skill_inventory.py` | 验证盘点脚本在存在、缺失和 CLI 可用/不可用条件下的确定性行为 |
| `shared/contracts/literature-source.schema.json` | 描述候选、批准和拒绝文献来源及人工决定 |
| `shared/contracts/citation-link.schema.json` | 描述论文主张与已批准来源的定位和支持边界 |
| `shared/fixtures/contracts/{valid,invalid}/literature-*.json` | 文献来源契约正负样例 |
| `shared/fixtures/contracts/{valid,invalid}/citation-link*.json` | 引用链接契约正负样例 |
| `shared/contracts/catalog.json` | 将契约目录从 9 项向后兼容扩展为 11 项 |
| `docs/architecture/contracts.md` | 记录两个新契约的生产者、消费者、字段和失败语义 |
| `docs/architecture/paper-skill-capability-matrix.md` | 记录默认入口、legacy 备选、后端状态与分阶段迁移归属 |
| `docs/guides/paper-and-literature-workflow.md` | 面向使用者的调用、确认、降级和恢复说明 |
| `tests/contracts/test_paper_integration_documentation.py` | 防止路线、能力状态和使用说明与设计漂移 |
| 总体设计与主计划 | 将受控候选检索和 Phase 0A 增量纳入项目路线 |

## Execution preflight: restore the locked runner

The current machine has Python 3.11.9 but no global `uv` command and no repository `.venv`. Before Task 1, obtain approval for any required package download, then create an ignored bootstrap environment and restore the locked project environment:

```powershell
python -m venv .superpowers\bootstrap-uv
.superpowers\bootstrap-uv\Scripts\python.exe -m pip install uv==0.12.5
$env:UV_CACHE_DIR = 'E:\数学建模国赛\.superpowers\uv-paper-integration-cache'
.superpowers\bootstrap-uv\Scripts\uv.exe sync --frozen --dev
.venv\Scripts\python.exe --version
```

Expected: Python 3.11.x; `uv.lock` hash and Git status remain unchanged. The bootstrap and cache directories are ignored execution assets, not product dependencies.

### Task 1: Add a read-only legacy Skill inventory

**Files:**

- Create: `scripts/inventory_paper_skills.py`
- Create: `tests/integration/test_paper_skill_inventory.py`

**Interfaces:**

- Consumes: a user-supplied skills root and an executable lookup callable.
- Produces: `inventory_skills(skills_root: Path, executable_lookup: Callable[[str], str | None] = shutil.which) -> dict[str, object]` and a JSON-only CLI.
- Stable output keys: `inventory_version`, `skills_root`, `skills`, `backends`, `errors`.
- The script reads files only; it never installs, copies, rewrites or deletes a Skill.

- [ ] **Step 1: Write failing inventory tests**

Create `tests/integration/test_paper_skill_inventory.py`:

```python
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from scripts.inventory_paper_skills import inventory_skills


TARGETS = {"math-modeling-paper", "cumcm-paper", "paper-search"}


def write_skill(root: Path, name: str, extra: str = "") -> None:
    skill = root / name
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use when testing {name}\n---\n",
        encoding="utf-8",
    )
    if extra:
        (skill / "references" / "guide.md").write_text(extra, encoding="utf-8")


def test_inventory_reports_present_missing_and_hashes(tmp_path: Path) -> None:
    write_skill(tmp_path, "cumcm-paper", "国赛")
    write_skill(tmp_path, "paper-search")

    payload = inventory_skills(tmp_path, executable_lookup=lambda _: None)
    rows = {row["name"]: row for row in payload["skills"]}

    assert set(rows) == TARGETS
    assert rows["cumcm-paper"]["present"] is True
    assert rows["math-modeling-paper"]["present"] is False
    expected = hashlib.sha256("国赛".encode()).hexdigest()
    guide = next(
        row
        for row in rows["cumcm-paper"]["files"]
        if row["path"] == "references/guide.md"
    )
    assert guide["sha256"] == expected
    assert payload["backends"]["paper-search-cli"]["available"] is False
    assert payload["errors"] == []


def test_inventory_reports_cli_without_installing(tmp_path: Path) -> None:
    write_skill(tmp_path, "paper-search")
    payload = inventory_skills(
        tmp_path,
        executable_lookup=lambda name: "C:/tools/paper-search.exe" if name == "paper-search" else None,
    )
    assert payload["backends"]["paper-search-cli"] == {
        "available": True,
        "executable": "C:/tools/paper-search.exe",
    }


def test_inventory_cli_emits_stable_json(tmp_path: Path, project_root: Path) -> None:
    result = subprocess.run(
        [sys.executable, "scripts/inventory_paper_skills.py", "--skills-root", str(tmp_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert set(json.loads(result.stdout)) == {
        "inventory_version", "skills_root", "skills", "backends", "errors"
    }
```

Before saving the production file, change the direct import to a guarded import or create the empty module only after collecting the missing-module failure. The RED must be `ModuleNotFoundError: scripts.inventory_paper_skills`.

- [ ] **Step 2: Run the inventory tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_paper_skill_inventory.py -v -p no:cacheprovider
```

Expected: collection fails because `scripts.inventory_paper_skills` does not exist.

- [ ] **Step 3: Implement the minimal inventory**

Create `scripts/inventory_paper_skills.py` with these exact behaviors:

```python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from typing import Callable


TARGET_SKILLS = ("math-modeling-paper", "cumcm-paper", "paper-search")


def file_record(path: Path, root: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def inventory_skills(
    skills_root: Path,
    executable_lookup: Callable[[str], str | None] = shutil.which,
) -> dict[str, object]:
    root = skills_root.resolve()
    rows = []
    errors = []
    for name in TARGET_SKILLS:
        directory = root / name
        present = (directory / "SKILL.md").is_file()
        files = []
        if present:
            try:
                files = [
                    file_record(path, directory)
                    for path in sorted(directory.rglob("*"))
                    if path.is_file()
                ]
            except (OSError, UnicodeError) as exc:
                errors.append(f"{name}: {exc}")
        rows.append({"name": name, "present": present, "files": files})

    executable = executable_lookup("paper-search")
    return {
        "inventory_version": "1.0",
        "skills_root": str(root),
        "skills": rows,
        "backends": {
            "paper-search-cli": {
                "available": executable is not None,
                "executable": executable,
            },
            "cumcm-runtime-tools": {"available": None, "probe": "runtime-only"},
        },
        "errors": sorted(errors),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", type=Path, required=True)
    args = parser.parse_args()
    payload = inventory_skills(args.skills_root)
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0 if not payload["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify GREEN and the real local inventory**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_paper_skill_inventory.py -v -p no:cacheprovider
.venv\Scripts\python.exe scripts/inventory_paper_skills.py --skills-root "$env:USERPROFILE\.codex\skills"
```

Expected: tests pass. The real inventory reports all three Skill directories present, `paper-search-cli.available = false`, and `cumcm-runtime-tools.available = null` because an OS script cannot inspect model tool registration.

- [ ] **Step 5: Commit the inventory**

```powershell
git add scripts/inventory_paper_skills.py tests/integration/test_paper_skill_inventory.py
git commit -m "feat: inventory legacy paper skills"
```

### Task 2: Define the literature source contract

**Files:**

- Create: `shared/contracts/literature-source.schema.json`
- Create: `shared/fixtures/contracts/valid/literature-source.json`
- Create: `shared/fixtures/contracts/invalid/literature-source-approved-without-decision.json`
- Create: `tests/contracts/test_literature_source.py`

**Interfaces:**

- Produces contract ID `literature-source` and source IDs with prefix `src_`.
- An approved source requires one or more artifact IDs, a SHA-256 content hash and a human decision ID.
- Candidate and rejected records may have no downloaded artifact, but still retain retrieval metadata.

- [ ] **Step 1: Write the failing source-contract tests**

```python
from pathlib import Path

from scripts.validate_contracts import load_json, make_validator


def test_approved_literature_source_requires_human_decision(project_root: Path) -> None:
    schema = load_json(project_root / "shared/contracts/literature-source.schema.json")
    validator = make_validator(schema)
    valid = load_json(project_root / "shared/fixtures/contracts/valid/literature-source.json")
    invalid = load_json(
        project_root
        / "shared/fixtures/contracts/invalid/literature-source-approved-without-decision.json"
    )

    assert list(validator.iter_errors(valid)) == []
    errors = list(validator.iter_errors(invalid))
    assert len(errors) == 1
    assert tuple(errors[0].absolute_path) == ()
    assert errors[0].validator == "required"
```

- [ ] **Step 2: Run the source test and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_literature_source.py -v -p no:cacheprovider
```

Expected: FAIL because the Schema and fixtures do not exist.

- [ ] **Step 3: Add the source Schema and fixtures**

Create `literature-source.schema.json` as Draft 2020-12 with `additionalProperties: false`. Require these properties:

```json
[
  "schema_version", "source_id", "title", "authors", "year",
  "venue_or_repository", "identifiers", "canonical_url", "retrieved_at",
  "retrieval_backend", "verification_status", "artifact_ids", "content_sha256"
]
```

Use these exact constraints:

```json
{
  "schema_version": {"const": "1.0"},
  "source_id": {"type": "string", "pattern": "^src_[a-z0-9][a-z0-9_-]{2,63}(?![\\s\\S])"},
  "title": {"type": "string", "minLength": 1},
  "authors": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
  "year": {"type": "integer", "minimum": 1800, "maximum": 2100},
  "venue_or_repository": {"type": "string", "minLength": 1},
  "identifiers": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "doi": {"type": "string", "minLength": 1},
      "arxiv_id": {"type": "string", "minLength": 1},
      "pmid": {"type": "string", "minLength": 1}
    }
  },
  "canonical_url": {"type": "string", "format": "cumcm-http-url"},
  "retrieved_at": {"type": "string", "format": "date-time"},
  "retrieval_backend": {"enum": ["paper-search", "runtime-search", "user-provided"]},
  "verification_status": {"enum": ["candidate", "approved", "rejected"]},
  "artifact_ids": {
    "type": "array", "uniqueItems": true,
    "items": {"type": "string", "pattern": "^art_[a-z0-9][a-z0-9_-]{2,63}(?![\\s\\S])"}
  },
  "content_sha256": {
    "oneOf": [
      {"type": "string", "pattern": "^[a-f0-9]{64}(?![\\s\\S])"},
      {"type": "null"}
    ]
  },
  "decision_id": {"type": "string", "pattern": "^dec_[a-z0-9][a-z0-9_-]{2,63}(?![\\s\\S])"}
}
```

Add an `allOf` conditional: if `verification_status` is `approved`, then require `decision_id`, require `content_sha256` to be the 64-character string form, and require `artifact_ids.minItems = 1`.

Use this exact conditional:

```json
{
  "allOf": [
    {
      "if": {
        "properties": {"verification_status": {"const": "approved"}},
        "required": ["verification_status"]
      },
      "then": {
        "required": ["decision_id"],
        "properties": {
          "artifact_ids": {"minItems": 1},
          "content_sha256": {
            "type": "string",
            "pattern": "^[a-f0-9]{64}(?![\\s\\S])"
          }
        }
      }
    }
  ]
}
```

The valid fixture uses only synthetic metadata and `example.invalid`, for example `source_id = src_synthetic_method`, `retrieval_backend = user-provided`, `decision_id = dec_outline_sources`. The invalid fixture is a deep copy with only `decision_id` removed.

- [ ] **Step 4: Verify the contract and boundary suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_literature_source.py tests/contracts/test_contract_boundaries.py -v -p no:cacheprovider
```

Expected: PASS; trailing LF/CR mutations of all new pattern-backed fields are rejected by existing recursive boundary tests.

- [ ] **Step 5: Commit the source contract**

```powershell
git add shared/contracts/literature-source.schema.json shared/fixtures/contracts tests/contracts/test_literature_source.py
git commit -m "feat: define literature source contract"
```

### Task 3: Define the citation link contract

**Files:**

- Create: `shared/contracts/citation-link.schema.json`
- Create: `shared/fixtures/contracts/valid/citation-link.json`
- Create: `shared/fixtures/contracts/invalid/citation-link-missing-locator.json`
- Create: `tests/contracts/test_citation_link.py`

**Interfaces:**

- Produces contract ID `citation-link` and citation IDs with prefix `cite_`.
- Links an existing claim ID to an approved source ID and a precise source locator.
- Does not replace `evidence-link`; experimental and literature evidence remain distinct.

- [ ] **Step 1: Write the failing citation test**

```python
from pathlib import Path

from scripts.validate_contracts import load_json, make_validator


def test_citation_link_requires_source_locator(project_root: Path) -> None:
    schema = load_json(project_root / "shared/contracts/citation-link.schema.json")
    validator = make_validator(schema)
    valid = load_json(project_root / "shared/fixtures/contracts/valid/citation-link.json")
    invalid = load_json(
        project_root / "shared/fixtures/contracts/invalid/citation-link-missing-locator.json"
    )

    assert list(validator.iter_errors(valid)) == []
    errors = list(validator.iter_errors(invalid))
    assert len(errors) == 1
    assert tuple(errors[0].absolute_path) == ()
    assert errors[0].validator == "required"
```

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_citation_link.py -v -p no:cacheprovider
```

Expected: FAIL because the citation files do not exist.

- [ ] **Step 3: Create the citation Schema and fixtures**

Use Draft 2020-12, `additionalProperties: false`, and require:

```json
[
  "schema_version", "citation_id", "claim_id", "source_id",
  "usage", "locator", "support_boundary", "verified_at"
]
```

Use these exact properties:

```json
{
  "schema_version": {"const": "1.0"},
  "citation_id": {"type": "string", "pattern": "^cite_[a-z0-9][a-z0-9_-]{2,63}(?![\\s\\S])"},
  "claim_id": {"type": "string", "pattern": "^clm_[a-z0-9][a-z0-9_-]{2,63}(?![\\s\\S])"},
  "source_id": {"type": "string", "pattern": "^src_[a-z0-9][a-z0-9_-]{2,63}(?![\\s\\S])"},
  "usage": {"enum": ["background", "method", "baseline", "data", "limitation"]},
  "locator": {
    "type": "object",
    "additionalProperties": false,
    "required": ["kind", "value"],
    "properties": {
      "kind": {"enum": ["page", "section", "figure", "table", "paragraph"]},
      "value": {"type": "string", "pattern": "^(?!.*[\\r\\n]).+(?![\\s\\S])"}
    }
  },
  "support_boundary": {"type": "string", "minLength": 1},
  "verified_at": {"type": "string", "format": "date-time"}
}
```

The valid fixture uses `cite_synthetic_method`, `clm_method_choice`, and `src_synthetic_method`; it describes a synthetic paragraph locator and does not quote a real paper. The invalid fixture removes only the top-level `locator`.

- [ ] **Step 4: Verify GREEN and pattern boundaries**

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_citation_link.py tests/contracts/test_contract_boundaries.py -v -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Commit the citation contract**

```powershell
git add shared/contracts/citation-link.schema.json shared/fixtures/contracts tests/contracts/test_citation_link.py
git commit -m "feat: define citation evidence contract"
```

### Task 4: Register eleven contracts and migrate the acceptance gate

**Files:**

- Modify: `shared/contracts/catalog.json`
- Modify: `tests/contracts/test_catalog.py`
- Modify: `tests/contracts/test_contract_examples.py`
- Modify: `tests/contracts/test_validator_cli.py`
- Modify: `tests/contracts/test_validator_offline.py`
- Modify: `docs/architecture/contracts.md`
- Modify: `docs/quality/acceptance-gates.md`
- Modify: every tracked assertion or sentence that still requires exactly 9 registered contracts

**Interfaces:**

- Catalog retains `catalog_version = 1.0` because entry shape is unchanged.
- Catalog grows additively from 9 to 11 unique IDs.
- Validator success becomes `{"contracts": 11, "errors": [], "status": "ok"}`.

- [ ] **Step 1: Write the failing catalog migration assertions**

In `tests/contracts/test_catalog.py`, replace the count-only assertion with an exact set plus count:

```python
EXPECTED_CONTRACT_IDS = {
    "error", "artifact", "experiment", "evidence-link", "decision",
    "workflow-state", "review-finding", "annual-rule", "asset-manifest",
    "literature-source", "citation-link",
}


assert set(ids) == EXPECTED_CONTRACT_IDS
assert len(ids) == 11
```

Add these entries to `NAMED_INVALID_EXPECTATIONS` before catalog registration:

```python
"shared/fixtures/contracts/invalid/literature-source-approved-without-decision.json": ((), "required"),
"shared/fixtures/contracts/invalid/citation-link-missing-locator.json": ((), "required"),
```

Run the tests before editing the catalog. Expected RED: the exact ID set and exhaustive invalid mapping report both new contracts missing.

- [ ] **Step 2: Register both contracts**

Append two entries to `shared/contracts/catalog.json`:

```json
{
  "id": "literature-source",
  "schema": "shared/contracts/literature-source.schema.json",
  "valid_examples": ["shared/fixtures/contracts/valid/literature-source.json"],
  "invalid_examples": ["shared/fixtures/contracts/invalid/literature-source-approved-without-decision.json"]
},
{
  "id": "citation-link",
  "schema": "shared/contracts/citation-link.schema.json",
  "valid_examples": ["shared/fixtures/contracts/valid/citation-link.json"],
  "invalid_examples": ["shared/fixtures/contracts/invalid/citation-link-missing-locator.json"]
}
```

- [ ] **Step 3: Migrate every stable count expectation**

Use PowerShell discovery rather than relying on memory:

```powershell
Get-ChildItem tests,docs,scripts -Recurse -File |
  Select-String -Pattern 'contracts.?=.?9|contracts.?==.?9|contracts\": 9|九个|9 个'
```

Change genuine catalog-count expectations from 9 to 11 in validator CLI/offline tests and documentation. Do not change unrelated years, IDs, ports or test data. Update `docs/architecture/contracts.md` with one table row per new contract and a valid fixture link on the same row. Update `docs/quality/acceptance-gates.md` to state `contracts = 11`.

- [ ] **Step 4: Run focused and full gates**

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_catalog.py tests/contracts/test_contract_examples.py tests/contracts/test_validator_cli.py tests/contracts/test_validator_offline.py tests/contracts/test_contract_documentation.py -v -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/contracts -v -p no:cacheprovider
.venv\Scripts\python.exe scripts/validate_contracts.py
```

Expected: all tests pass; validator outputs 11 contracts and zero errors; each invalid fixture still produces exactly one named error.

- [ ] **Step 5: Commit the catalog migration**

```powershell
git add shared/contracts/catalog.json tests/contracts docs/architecture/contracts.md docs/quality/acceptance-gates.md
git commit -m "feat: register literature evidence contracts"
```

### Task 5: Integrate the capability into the project roadmap

**Files:**

- Modify: `docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md`
- Modify: `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`
- Create: `docs/architecture/paper-skill-capability-matrix.md`
- Create: `tests/contracts/test_paper_integration_documentation.py`

**Interfaces:**

- Produces a single documented routing policy used by future Phase 3/4/6/7 detailed plans.
- Adds Phase 0A to the master roadmap without renumbering existing phases.
- Does not claim that `cumcm-orchestrator`, `literature-researcher`, CLI or plugins are currently implemented.

- [ ] **Step 1: Write failing roadmap documentation tests**

Create `tests/contracts/test_paper_integration_documentation.py`:

```python
from pathlib import Path


def read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def test_overall_design_defines_controlled_literature_route(project_root: Path) -> None:
    design = read(project_root, "docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md")
    for phrase in (
        "literature-researcher",
        "候选文献",
        "人工确认",
        "不得伪造",
        "cumcm-paper",
        "math-modeling-paper",
    ):
        assert phrase in design


def test_master_plan_contains_phase_0a_and_stage_owners(project_root: Path) -> None:
    plan = read(project_root, "docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md")
    for phrase in (
        "Phase 0A",
        "literature-source",
        "citation-link",
        "Phase 3",
        "Phase 4",
        "Phase 6",
        "Phase 7",
    ):
        assert phrase in plan


def test_capability_matrix_keeps_legacy_skills_as_explicit_options(project_root: Path) -> None:
    matrix = read(project_root, "docs/architecture/paper-skill-capability-matrix.md")
    for phrase in (
        "cumcm-orchestrator",
        "literature-researcher",
        "cumcm-paper",
        "math-modeling-paper",
        "paper-search",
        "当前不可用",
        "用户显式选择",
        "不直接复制",
    ):
        assert phrase in matrix
```

- [ ] **Step 2: Run and verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_paper_integration_documentation.py -v -p no:cacheprovider
```

Expected: FAIL because the matrix does not exist and the two existing documents do not yet contain the routing terms.

- [ ] **Step 3: Update the overall design**

Make these precise changes:

- Replace the non-goal “不自动伪造、搜索并插入参考文献” with “不伪造参考文献；不把检索候选未经人工确认直接插入论文”。
- Add `literature-researcher` to the core Skill table with the stop conditions from the integration spec.
- Add legacy `cumcm-paper` and `math-modeling-paper` to a compatibility subsection, not to the shared-core ownership table.
- Add controlled literature discovery between problem/model work and the gate 3 outline decision.
- Add source/citation contracts and negative citation scenarios to the test strategy.
- Preserve the four global human gates and the Phase 0–8 dependency direction.

- [ ] **Step 4: Update the master implementation plan**

Add a program row named `Phase 0A 论文与文献整合底座` after Phase 0. Phase 1 depends on Phase 0A completion. Its detailed plan path is this file. Add stage ownership:

- Phase 3: `literature-researcher` Codex Skill and trigger/route tests.
- Phase 4: citation evidence linker, BibTeX/LaTeX integration and `citation-check`.
- Phase 6: orchestrator optional literature branch and gate 3 approval.
- Phase 7: DSH Skill, deterministic search/read Tool plugin and network permissions.
- Phase 8: historical-case citation relevance and provenance regression.

Do not add executable files for those later phases to Phase 0A.

- [ ] **Step 5: Write the capability matrix**

Create `docs/architecture/paper-skill-capability-matrix.md` with:

- A warning that current default orchestrator and new sub Skill are planned, not installed.
- A table covering trigger, scope, required tools, current observed state, fallback role, migration source and target phase for all five capabilities.
- A route table for CUMCM full flow, CUMCM legacy flow, MCM/ICM, literature-only task and no-backend task.
- A migration rule that resources move into `shared/` only after hash inventory, source review, deduplication and tests.
- The exact inventory command using `$env:USERPROFILE\.codex\skills`.

- [ ] **Step 6: Verify and commit roadmap integration**

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_paper_integration_documentation.py -v -p no:cacheprovider
git diff --check
git add docs/superpowers docs/architecture/paper-skill-capability-matrix.md tests/contracts/test_paper_integration_documentation.py
git commit -m "docs: integrate paper research capability roadmap"
```

### Task 6: Write the paper and literature workflow guide

**Files:**

- Create: `docs/guides/paper-and-literature-workflow.md`
- Modify: `tests/contracts/test_paper_integration_documentation.py`

**Interfaces:**

- Produces the user-facing guide requested with this integration.
- Describes verified current capabilities separately from planned capabilities.
- Every command is either executable now or explicitly labelled as a future/optional installation example.

- [ ] **Step 1: Add failing guide assertions**

Append:

```python
def test_paper_and_literature_guide_covers_routes_and_recovery(project_root: Path) -> None:
    guide = read(project_root, "docs/guides/paper-and-literature-workflow.md")
    for phrase in (
        "默认入口",
        "备选入口",
        "候选文献",
        "人工确认",
        "gate 3",
        "Codex",
        "DeepSeek Harness",
        "paper-search",
        "用户提供",
        "不得伪造",
        "当前不可用",
        "恢复",
        "scripts/inventory_paper_skills.py",
    ):
        assert phrase in guide
```

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_paper_integration_documentation.py::test_paper_and_literature_guide_covers_routes_and_recovery -v -p no:cacheprovider
```

Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 3: Write the guide**

Structure `docs/guides/paper-and-literature-workflow.md` in this order:

1. Top warning: no fabricated data, results or citations; candidates are not references.
2. Current availability table: three legacy Skill directories present; `paper-search` CLI unavailable; `cumcm_*` runtime tools unconfirmed/unavailable in the current session; modular orchestrator and researcher planned.
3. Entry selection table with five common requests and the correct default/backup.
4. Current usable workflows: explicit `/cumcm-paper`, `/math-modeling-paper`, and literature planning with user-provided files.
5. Future modular workflow: problem → optional search → candidate table → human approval → source/citation records → paper → citation check.
6. Codex instructions and DSH instructions, clearly distinguishing planned commands from verified commands.
7. Read-only inventory command:

```powershell
.venv\Scripts\python.exe scripts/inventory_paper_skills.py --skills-root "$env:USERPROFILE\.codex\skills"
```

8. Candidate approval example with synthetic metadata and no real-paper claim.
9. Failure and recovery table for missing CLI, missing runtime tools, network failure, metadata conflict, unavailable PDF, hash mismatch and unapproved source.
10. Installation boundary: installation is never automatic and requires explicit authorization in the relevant phase.

Do not include `paper-search search` as a verified current command. It may appear only under a clearly labelled “安装后示例” subsection.

- [ ] **Step 4: Verify guide behavior and links**

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts/test_paper_integration_documentation.py -v -p no:cacheprovider
$markers = @(('TO' + 'DO'), ('T' + 'BD'), ('FIX' + 'ME'), ('待' + '定'))
Select-String -Path docs\guides\*.md -Pattern $markers -CaseSensitive:$false
```

Expected: tests pass; marker scan returns no matches. Manually open every relative link in the guide and confirm the target exists.

- [ ] **Step 5: Commit the guide**

```powershell
git add docs/guides/paper-and-literature-workflow.md tests/contracts/test_paper_integration_documentation.py
git commit -m "docs: add paper and literature workflow guide"
```

### Task 7: Run the Phase 0A acceptance and handoff

**Files:**

- Modify only if verification finds a demonstrated defect: files created or modified in Tasks 1–6.
- Do not create an extra committed report; record evidence in the execution handoff.

**Interfaces:**

- Produces a clean commit hash and the verified inputs required for Phase 1, Phase 3, Phase 4 and Phase 7 planning.
- Does not install or edit live personal Skills.

- [ ] **Step 1: Verify history and cleanliness**

```powershell
git status --short
git log --oneline --decorate -12
git diff --check
```

Expected: clean status and separate inventory, source, citation, catalog, roadmap and guide commits.

- [ ] **Step 2: Run the full contract and integration suites**

```powershell
.venv\Scripts\python.exe -m pytest tests/contracts tests/integration/test_paper_skill_inventory.py -v -p no:cacheprovider
.venv\Scripts\python.exe scripts/validate_contracts.py
```

Expected: all tests pass; validator returns `status = ok`, `contracts = 11`, `errors = []`.

- [ ] **Step 3: Prove the approval boundary fails closed**

Using `apply_patch`, temporarily remove `decision_id` from the valid approved literature source fixture. Run the validator and require exit 1 with a `literature-source` valid-fixture failure. Restore the exact field with `apply_patch`, rerun and require exit 0. Do not commit the probe.

- [ ] **Step 4: Run the real read-only inventory**

```powershell
.venv\Scripts\python.exe scripts/inventory_paper_skills.py --skills-root "$env:USERPROFILE\.codex\skills"
```

Expected for the current machine: all three legacy Skill folders are present; `paper-search-cli.available` is false; `cumcm-runtime-tools.available` is null and labelled `runtime-only`. A different machine may report different availability without failing the inventory.

- [ ] **Step 5: Scan documentation and confirm no live Skill mutation**

```powershell
$markers = @(('TO' + 'DO'), ('T' + 'BD'), ('FIX' + 'ME'), ('待' + '定'))
Select-String -Path shared/contracts/*.json,docs/architecture/*.md,docs/guides/*.md,docs/superpowers/specs/*.md,docs/superpowers/plans/*.md -Pattern $markers -CaseSensitive:$false
git status --short
```

Expected: no unfinished markers and clean status. Compare a fresh inventory hash list against the pre-implementation inventory evidence; files under the live personal Skill root are unchanged.

- [ ] **Step 6: Handoff exact next-phase inputs**

Report:

- final commit hash;
- Python and dependency versions;
- contract count and catalog path;
- inventory command and observed backend availability;
- the two new contract IDs and fixture paths;
- the user guide path;
- the tasks assigned to Phase 3/4/6/7;
- the explicit statement that no runtime Skill, CLI or DSH plugin was installed by Phase 0A.

## Completion criteria

This plan is complete only when:

- the three existing personal Skills can be inventoried without modification;
- both literature contracts have valid and single-reason invalid fixtures;
- the catalog and validator consistently report 11 contracts;
- the overall design and master roadmap include the controlled literature route;
- the capability matrix distinguishes default, backup, unavailable and planned capabilities;
- the requested user guide exists and matches actual availability;
- the approval regression probe fails before restoration and passes afterward;
- all tests pass and the repository is clean.

Completion authorizes Phase 1 work and later detailed plans to consume these stable interfaces. It does not authorize installing `paper-search`, installing `cumcm_*`, creating the runtime `literature-researcher`, or implementing the DSH plugin without their stage-specific instructions.
