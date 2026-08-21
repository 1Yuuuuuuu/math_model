# CUMCM Workbench Phase 0 Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 初始化仓库并建立后续工具、Skill、论文和审批共同依赖的版本化契约、有效/无效样例、自动验证入口与变更规范。

**Architecture:** 使用 JSON Schema Draft 2020-12 描述跨运行时契约，以 `shared/contracts/catalog.json` 登记 Schema 和样例。一个无网络运行的 Python 验证脚本检查 Schema、正例、反例和资产文件，pytest 只验证外部可观察行为。

**Tech Stack:** Git、Python 3.11、uv、pytest、jsonschema 4.x、PowerShell、JSON Schema Draft 2020-12。

**Spec:** `docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md`

## Global Constraints

- 主要运行环境是 Codex 桌面环境和本地 Windows 工作区；DeepSeek Harness 是兼容运行时。
- Python 版本固定为 3.11；依赖由 uv 锁定。
- `shared/` 是开发时唯一事实来源；Windows 环境下不依赖符号链接。
- 所有契约包含字符串字段 `schema_version`，阶段 0 固定值为 `1.0`。
- 所有 ID 使用小写 ASCII 前缀和 `[a-z0-9_-]`，不得依赖文件系统大小写差异。
- 所有时间使用带时区的 RFC 3339 字符串；所有哈希使用 64 位小写 SHA-256 十六进制字符串。
- 契约中的文件路径必须是相对工作区的正斜杠路径，不允许盘符、反斜杠或绝对路径。
- 每个 Schema 必须提供至少一个有效样例和一个只违反一个明确规则的无效样例。
- 验证脚本不得联网，不得修改被验证文件。
- 当前目录尚未初始化 Git；Task 1 建立版本基线。

---

## Final file structure

```text
.gitignore
.python-version
pyproject.toml
uv.lock
shared/
├── contracts/
│   ├── catalog.json
│   ├── error.schema.json
│   ├── artifact.schema.json
│   ├── experiment.schema.json
│   ├── evidence-link.schema.json
│   ├── workflow-state.schema.json
│   ├── decision.schema.json
│   ├── review-finding.schema.json
│   ├── annual-rule.schema.json
│   └── asset-manifest.schema.json
└── fixtures/contracts/
    ├── valid/
    │   ├── error.json
    │   ├── artifact.json
    │   ├── experiment.json
    │   ├── evidence-link.json
    │   ├── workflow-state.json
    │   ├── decision.json
    │   ├── review-finding.json
    │   ├── annual-rule.json
    │   └── asset-manifest.json
    └── invalid/
        ├── error-missing-code.json
        ├── artifact-absolute-path.json
        ├── experiment-missing-input.json
        ├── evidence-link-missing-boundary.json
        ├── workflow-state-skipped-gate.json
        ├── decision-nonhuman.json
        ├── review-finding-bad-severity.json
        ├── annual-rule-missing-source.json
        └── asset-manifest-duplicate-target.json
scripts/
└── validate_contracts.py
tests/contracts/
├── conftest.py
├── test_catalog.py
├── test_contract_examples.py
└── test_validator_cli.py
docs/
├── architecture/contracts.md
├── quality/acceptance-gates.md
└── operations/change-policy.md
```

### Task 1: Repository and Python validation baseline

**Files:**

- Create: `.gitignore`
- Create: `.python-version`
- Create before the first test run: `pyproject.toml`
- Create: `tests/contracts/test_repository_baseline.py`
- Generated: `uv.lock`

**Interfaces:**

- Consumes: approved design and master implementation plan.
- Produces: Python 3.11 test environment and repository ignore rules used by every later task.

- [ ] **Step 1: Initialize Git, declare test dependencies, and write the failing repository-baseline test**

Run:

```powershell
git init
New-Item -ItemType Directory -Force tests/contracts | Out-Null
```

Create `pyproject.toml` before running pytest:

```toml
[project]
name = "cumcm-workbench"
version = "0.1.0"
description = "Reproducible CUMCM modeling and paper workflow"
requires-python = ">=3.11,<3.12"
dependencies = [
  "jsonschema>=4.23,<5",
]

[dependency-groups]
dev = [
  "pytest>=8.3,<9",
]

[tool.pytest.ini_options]
testpaths = ["tests", "toolkit/tests"]
addopts = "--strict-markers --strict-config"
```

Create `tests/contracts/test_repository_baseline.py` with:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_required_project_metadata_exists() -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.11"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11,<3.12"' in pyproject
    ignores = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in (".venv/", ".superpowers/", "dist/", "workspaces/", "__pycache__/"):
        assert entry in ignores
```

- [ ] **Step 2: Create the locked environment, then verify the test fails**

Run:

```powershell
uv lock
uv sync --dev
uv run pytest tests/contracts/test_repository_baseline.py -v
```

Expected: FAIL because `.python-version` and `.gitignore` do not exist.

- [ ] **Step 3: Create minimal project metadata**

Create `.python-version`:

```text
3.11
```

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
.pytest_cache/
.coverage
htmlcov/
.superpowers/
dist/
workspaces/
*.pyc
*.pyo
*.log
```

Run: `uv sync --frozen --dev`

Expected: the locked environment resolves to Python 3.11 without changing `uv.lock`.

- [ ] **Step 4: Run the baseline test**

Run: `uv run pytest tests/contracts/test_repository_baseline.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the repository baseline**

```powershell
git add .gitignore .python-version pyproject.toml uv.lock tests/contracts/test_repository_baseline.py docs/superpowers
git commit -m "chore: establish CUMCM workbench baseline"
```

### Task 2: Contract catalog and error envelope

**Files:**

- Create: `shared/contracts/catalog.json`
- Create: `shared/contracts/error.schema.json`
- Create: `shared/fixtures/contracts/valid/error.json`
- Create: `shared/fixtures/contracts/invalid/error-missing-code.json`
- Create: `tests/contracts/conftest.py`
- Create: `tests/contracts/test_catalog.py`

**Interfaces:**

- Consumes: Python test environment from Task 1.
- Produces: catalog entry shape `{id, schema, valid_examples, invalid_examples}` and common error envelope used by every tool.

- [ ] **Step 1: Write catalog tests**

Create `tests/contracts/conftest.py`:

```python
import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
```

Create `tests/contracts/test_catalog.py`:

```python
from jsonschema import Draft202012Validator

from conftest import load_json


def test_catalog_paths_and_schemas_are_valid(project_root) -> None:
    catalog = load_json(project_root / "shared/contracts/catalog.json")
    assert catalog["catalog_version"] == "1.0"
    ids = [entry["id"] for entry in catalog["contracts"]]
    assert len(ids) == len(set(ids))
    for entry in catalog["contracts"]:
        schema_path = project_root / entry["schema"]
        assert schema_path.is_file()
        Draft202012Validator.check_schema(load_json(schema_path))
        for key in ("valid_examples", "invalid_examples"):
            assert entry[key]
            assert all((project_root / path).is_file() for path in entry[key])
```

- [ ] **Step 2: Run the catalog test and verify it fails**

Run: `uv run pytest tests/contracts/test_catalog.py -v`

Expected: FAIL because `shared/contracts/catalog.json` does not exist.

- [ ] **Step 3: Create the error Schema, catalog, and examples**

Create `shared/contracts/error.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://cumcm.local/contracts/error.schema.json",
  "title": "Tool error envelope",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "code", "message", "recoverable", "details"],
  "properties": {
    "schema_version": {"const": "1.0"},
    "code": {"type": "string", "pattern": "^[A-Z][A-Z0-9_]{2,63}$"},
    "message": {"type": "string", "minLength": 1},
    "recoverable": {"type": "boolean"},
    "details": {"type": "object"}
  }
}
```

Create valid example `shared/fixtures/contracts/valid/error.json`:

```json
{"schema_version":"1.0","code":"FILE_MISSING","message":"Input data file is missing","recoverable":true,"details":{"path":"data/input.csv"}}
```

Create invalid example `shared/fixtures/contracts/invalid/error-missing-code.json`:

```json
{"schema_version":"1.0","message":"Input data file is missing","recoverable":true,"details":{}}
```

Create `shared/contracts/catalog.json`:

```json
{
  "catalog_version": "1.0",
  "contracts": [
    {
      "id": "error",
      "schema": "shared/contracts/error.schema.json",
      "valid_examples": ["shared/fixtures/contracts/valid/error.json"],
      "invalid_examples": ["shared/fixtures/contracts/invalid/error-missing-code.json"]
    }
  ]
}
```

- [ ] **Step 4: Run the catalog test**

Run: `uv run pytest tests/contracts/test_catalog.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the catalog and error envelope**

```powershell
git add shared/contracts shared/fixtures/contracts tests/contracts
git commit -m "feat: define contract catalog and error envelope"
```

### Task 3: Artifact and experiment contracts

**Files:**

- Create: `shared/contracts/artifact.schema.json`
- Create: `shared/contracts/experiment.schema.json`
- Create: `shared/fixtures/contracts/valid/artifact.json`
- Create: `shared/fixtures/contracts/invalid/artifact-absolute-path.json`
- Create: `shared/fixtures/contracts/valid/experiment.json`
- Create: `shared/fixtures/contracts/invalid/experiment-missing-input.json`
- Modify: `shared/contracts/catalog.json`
- Create: `tests/contracts/test_artifact_and_experiment.py`

**Interfaces:**

- Consumes: catalog structure from Task 2.
- Produces: artifact IDs `art_*`, experiment IDs `exp_*`, relative paths, hashes, parameters, metrics and output references used by stages 1–8.

- [ ] **Step 1: Write failing artifact and experiment tests**

Create `tests/contracts/test_artifact_and_experiment.py`:

```python
from jsonschema import Draft202012Validator, ValidationError
import pytest

from conftest import load_json


@pytest.mark.parametrize(
    ("schema_name", "valid_name", "invalid_name"),
    [
        ("artifact", "artifact", "artifact-absolute-path"),
        ("experiment", "experiment", "experiment-missing-input"),
    ],
)
def test_valid_and_invalid_contract_examples(project_root, schema_name, valid_name, invalid_name) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    validator = Draft202012Validator(schema)
    validator.validate(load_json(project_root / f"shared/fixtures/contracts/valid/{valid_name}.json"))
    with pytest.raises(ValidationError):
        validator.validate(load_json(project_root / f"shared/fixtures/contracts/invalid/{invalid_name}.json"))
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `uv run pytest tests/contracts/test_artifact_and_experiment.py -v`

Expected: two FAIL results because both Schema files are missing.

- [ ] **Step 3: Implement the artifact contract and examples**

Create `artifact.schema.json` with required fields `schema_version`, `artifact_id`, `kind`, `path`, `sha256`, `created_at`, and `source_artifact_ids`. Use these exact constraints:

```json
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"https://cumcm.local/contracts/artifact.schema.json",
  "type":"object",
  "additionalProperties":false,
  "required":["schema_version","artifact_id","kind","path","sha256","created_at","source_artifact_ids"],
  "properties":{
    "schema_version":{"const":"1.0"},
    "artifact_id":{"type":"string","pattern":"^art_[a-z0-9][a-z0-9_-]{2,63}$"},
    "kind":{"enum":["data","code","figure","table","latex","pdf","report","config","other"]},
    "path":{"type":"string","pattern":"^(?![A-Za-z]:)(?!/)(?!.*\\\\).+$"},
    "sha256":{"type":"string","pattern":"^[a-f0-9]{64}$"},
    "created_at":{"type":"string","format":"date-time"},
    "source_artifact_ids":{"type":"array","uniqueItems":true,"items":{"type":"string","pattern":"^art_[a-z0-9][a-z0-9_-]{2,63}$"}}
  }
}
```

Valid example uses `artifact_id` `art_raw_data`, path `data/input.csv`, SHA-256 of 64 `a` characters, time `2026-08-21T09:00:00+08:00`, and an empty source list. Invalid example is identical except path `E:/data/input.csv`.

- [ ] **Step 4: Implement the experiment contract and examples**

Create `experiment.schema.json` with exact required fields and constraints:

```json
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "$id":"https://cumcm.local/contracts/experiment.schema.json",
  "type":"object",
  "additionalProperties":false,
  "required":["schema_version","experiment_id","input_artifact_ids","code_artifact_id","parameters","random_seed","environment","started_at","finished_at","status","output_artifact_ids","metrics"],
  "properties":{
    "schema_version":{"const":"1.0"},
    "experiment_id":{"type":"string","pattern":"^exp_[a-z0-9][a-z0-9_-]{2,63}$"},
    "input_artifact_ids":{"type":"array","minItems":1,"uniqueItems":true,"items":{"type":"string","pattern":"^art_[a-z0-9][a-z0-9_-]{2,63}$"}},
    "code_artifact_id":{"type":"string","pattern":"^art_[a-z0-9][a-z0-9_-]{2,63}$"},
    "parameters":{"type":"object"},
    "random_seed":{"type":["integer","null"]},
    "environment":{"type":"object","additionalProperties":false,"required":["python_version","lock_sha256"],"properties":{"python_version":{"const":"3.11"},"lock_sha256":{"type":"string","pattern":"^[a-f0-9]{64}$"}}},
    "started_at":{"type":"string","format":"date-time"},
    "finished_at":{"type":"string","format":"date-time"},
    "status":{"enum":["succeeded","failed","cancelled"]},
    "output_artifact_ids":{"type":"array","uniqueItems":true,"items":{"type":"string","pattern":"^art_[a-z0-9][a-z0-9_-]{2,63}$"}},
    "metrics":{"type":"object","additionalProperties":{"type":"number"}}
  }
}
```

Valid example references `art_raw_data`, `art_solve_code`, and `art_result_table`, uses seed `20260910`, status `succeeded`, and metric `rmse: 0.125`. Invalid example sets `input_artifact_ids` to an empty array and changes nothing else.

Add `artifact` and `experiment` entries to `catalog.json` with their exact valid and invalid fixture paths.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/contracts/test_catalog.py tests/contracts/test_artifact_and_experiment.py -v`

Expected: PASS.

```powershell
git add shared/contracts shared/fixtures/contracts tests/contracts
git commit -m "feat: define artifact and experiment contracts"
```

### Task 4: Evidence, decision, and workflow-state contracts

**Files:**

- Create: `shared/contracts/evidence-link.schema.json`
- Create: `shared/contracts/decision.schema.json`
- Create: `shared/contracts/workflow-state.schema.json`
- Create: six corresponding valid/invalid fixtures from the final file structure
- Modify: `shared/contracts/catalog.json`
- Create: `tests/contracts/test_workflow_contracts.py`

**Interfaces:**

- Consumes: artifact and experiment IDs from Task 3.
- Produces: claim IDs `clm_*`, decision IDs `dec_*`, workspace IDs `ws_*`, four human-gate states and evidence locators.

- [ ] **Step 1: Write failing parameterized tests**

Create `tests/contracts/test_workflow_contracts.py` using the same valid/invalid validation structure as Task 3, with rows:

```python
CASES = [
    ("evidence-link", "evidence-link", "evidence-link-missing-boundary"),
    ("decision", "decision", "decision-nonhuman"),
    ("workflow-state", "workflow-state", "workflow-state-skipped-gate"),
]
```

Additionally assert the valid workflow has exactly the gate keys `gate_1_problem`, `gate_2_model`, `gate_3_outline`, and `gate_4_submission`.

- [ ] **Step 2: Verify the tests fail**

Run: `uv run pytest tests/contracts/test_workflow_contracts.py -v`

Expected: FAIL because the Schema files are missing.

- [ ] **Step 3: Implement evidence-link Schema and fixtures**

Require `schema_version`, `claim_id`, `claim_text`, `artifact_id`, `experiment_id`, `locator`, and `boundary`. The locator must contain `kind` from `json_pointer`, `csv_cell`, `file_region`, `figure`, or `table`, plus non-empty `value`. The valid fixture links claim `clm_rmse_result` to `art_result_table`, experiment `exp_prediction`, locator `table`/`results.csv#row=1,column=rmse`, and boundary `Applies only to the held-out seven-day test set`. The invalid fixture omits `boundary`.

- [ ] **Step 4: Implement decision and workflow-state Schema and fixtures**

The decision Schema requires `decision_id`, `gate`, `selected_option`, `rationale`, `artifact_ids`, `decided_by`, and `decided_at`. `gate` is one of `gate_1_problem`, `gate_2_model`, `gate_3_outline`, and `gate_4_submission`; `decided_by` must be the constant `human`; the invalid fixture uses `agent`.

The workflow Schema requires `workspace_id`, `stage`, `gates`, `latest_artifact_ids`, and `updated_at`. Stages are `intake`, `model_design`, `solve`, `outline`, `write`, `review`, `submission`, and `complete`. Each gate state is `pending`, `approved`, or `rejected`.

Add these conditional rules to prevent skipping any human gate:

```json
[
  {
    "if":{"properties":{"stage":{"enum":["model_design","solve","outline","write","review","submission","complete"]}}},
    "then":{"properties":{"gates":{"properties":{"gate_1_problem":{"const":"approved"}}}}}
  },
  {
    "if":{"properties":{"stage":{"enum":["solve","outline","write","review","submission","complete"]}}},
    "then":{"properties":{"gates":{"properties":{"gate_2_model":{"const":"approved"}}}}}
  },
  {
    "if":{"properties":{"stage":{"enum":["write","review","submission","complete"]}}},
    "then":{"properties":{"gates":{"properties":{"gate_3_outline":{"const":"approved"}}}}}
  },
  {
    "if":{"properties":{"stage":{"const":"complete"}}},
    "then":{"properties":{"gates":{"properties":{"gate_4_submission":{"const":"approved"}}}}}
  }
]
```

The valid fixture uses stage `model_design` with gate 1 approved and gates 2–4 pending. The invalid fixture uses stage `solve` while gate 1 remains pending. Add all three entries to the catalog.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/contracts/test_catalog.py tests/contracts/test_workflow_contracts.py -v`

Expected: PASS.

```powershell
git add shared/contracts shared/fixtures/contracts tests/contracts
git commit -m "feat: define evidence and workflow contracts"
```

### Task 5: Review, annual-rule, and asset-manifest contracts

**Files:**

- Create: `shared/contracts/review-finding.schema.json`
- Create: `shared/contracts/annual-rule.schema.json`
- Create: `shared/contracts/asset-manifest.schema.json`
- Create: six corresponding valid/invalid fixtures from the final file structure
- Modify: `shared/contracts/catalog.json`
- Create: `tests/contracts/test_governance_contracts.py`

**Interfaces:**

- Consumes: evidence references and common path/hash rules.
- Produces: review finding IDs `finding_*`, annual rule sets, and source-to-package asset manifests.

- [ ] **Step 1: Write failing governance tests**

Create a parameterized test with rows:

```python
CASES = [
    ("review-finding", "review-finding", "review-finding-bad-severity"),
    ("annual-rule", "annual-rule", "annual-rule-missing-source"),
    ("asset-manifest", "asset-manifest", "asset-manifest-duplicate-target"),
]
```

Use `Draft202012Validator` to accept each valid fixture and reject each invalid fixture.

- [ ] **Step 2: Verify the tests fail**

Run: `uv run pytest tests/contracts/test_governance_contracts.py -v`

Expected: FAIL because all three Schema files are missing.

- [ ] **Step 3: Implement review-finding Schema and fixtures**

Require `finding_id`, `review_gate`, `severity`, `summary`, `evidence_refs`, `recommendation`, and `status`. Gate values are `hard`, `reproducibility`, `model`, `paper`, and `red_team`; severity values are `S0`, `S1`, `S2`, and `S3`; status values are `open`, `resolved`, and `accepted_risk`. Valid fixture uses `finding_missing_sensitivity`, gate `model`, severity `S1`, evidence reference `clm_rmse_result`, and status `open`. Invalid fixture changes severity to `critical`.

- [ ] **Step 4: Implement annual-rule and asset-manifest Schema and fixtures**

Annual rule requires `rule_set_id`, `year`, `source_url`, `verified_at`, and non-empty `items`. Each item requires `rule_id`, `description`, `enforcement` (`machine` or `human`), and `blocking`. The valid fixture must clearly identify itself as a synthetic contract example with `rule_set_id` `cumcm-example-2026` and source URL `https://example.invalid/cumcm-rules`; it is not an official 2026 rule. The invalid fixture omits `source_url`.

Asset manifest requires `manifest_version` and non-empty `assets`. Each asset requires `asset_id`, `source_path`, `sha256`, and unique `package_targets` chosen from `codex` and `dsh`. The valid fixture contains one model-card asset targeting both. The invalid fixture repeats `codex` twice. Add all entries to the catalog.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/contracts/test_catalog.py tests/contracts/test_governance_contracts.py -v`

Expected: PASS.

```powershell
git add shared/contracts shared/fixtures/contracts tests/contracts
git commit -m "feat: define review and governance contracts"
```

### Task 6: Read-only contract validator CLI

**Files:**

- Create: `scripts/validate_contracts.py`
- Create: `tests/contracts/test_contract_examples.py`
- Create: `tests/contracts/test_validator_cli.py`

**Interfaces:**

- Consumes: `shared/contracts/catalog.json` and registered Schema/example files.
- Produces: exit code `0` with JSON summary on success; exit code `1` with JSON error list on validation failure. Does not modify repository files.

- [ ] **Step 1: Write failing validator tests**

Create `tests/contracts/test_contract_examples.py` to iterate over every catalog entry, call `Draft202012Validator.check_schema`, accept every valid fixture, and assert every invalid fixture raises `ValidationError`.

Create `tests/contracts/test_validator_cli.py`:

```python
import json
import subprocess
import sys


def test_validator_cli_reports_success(project_root) -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_contracts.py"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["contracts"] == 9
    assert payload["errors"] == []
```

- [ ] **Step 2: Verify the CLI test fails**

Run: `uv run pytest tests/contracts/test_contract_examples.py tests/contracts/test_validator_cli.py -v`

Expected: example test passes and CLI test fails because the script does not exist.

- [ ] **Step 3: Implement the validator**

Create `scripts/validate_contracts.py` with this complete implementation:

```python
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, SchemaError, ValidationError


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_catalog(root: Path) -> list[str]:
    errors: list[str] = []
    catalog_path = root / "shared/contracts/catalog.json"
    try:
        catalog = load_json(catalog_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"catalog: {exc}"]

    entries = catalog.get("contracts", [])
    ids = [entry.get("id") for entry in entries]
    if len(ids) != len(set(ids)):
        errors.append("catalog: duplicate contract id")

    for entry in entries:
        contract_id = str(entry.get("id", "<missing-id>"))
        try:
            schema = load_json(root / entry["schema"])
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            for relative_path in entry["valid_examples"]:
                validator.validate(load_json(root / relative_path))
            for relative_path in entry["invalid_examples"]:
                try:
                    validator.validate(load_json(root / relative_path))
                except ValidationError:
                    continue
                errors.append(f"{contract_id}: invalid fixture passed: {relative_path}")
        except (KeyError, OSError, json.JSONDecodeError, SchemaError, ValidationError) as exc:
            errors.append(f"{contract_id}: {exc}")
    return sorted(errors)


def main() -> int:
    errors = validate_catalog(ROOT)
    catalog = load_json(ROOT / "shared/contracts/catalog.json")
    payload = {
        "status": "ok" if not errors else "failed",
        "contracts": len(catalog.get("contracts", [])),
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Implementation requirements:

- Resolve `root` as the parent of `scripts/`.
- Reject duplicate contract IDs.
- Run `Draft202012Validator.check_schema` for every Schema.
- Validate every valid fixture and record any unexpected error.
- Require every invalid fixture to raise `ValidationError`; record an error if it passes.
- Keep the emitted JSON keys `status`, `contracts`, and `errors` stable.
- Preserve lexicographically sorted errors for deterministic output.
- Do not catch `KeyboardInterrupt` or modify any file.

- [ ] **Step 4: Run focused and full contract tests**

Run:

```powershell
uv run pytest tests/contracts/test_contract_examples.py tests/contracts/test_validator_cli.py -v
uv run python scripts/validate_contracts.py
```

Expected: all tests PASS; CLI outputs `{"status": "ok", "contracts": 9, "errors": []}` with JSON spacing allowed to differ.

- [ ] **Step 5: Commit the validator**

```powershell
git add scripts/validate_contracts.py tests/contracts
git commit -m "test: add contract validation gate"
```

### Task 7: Contract documentation and Phase 0 acceptance gate

**Files:**

- Create: `docs/architecture/contracts.md`
- Create: `docs/quality/acceptance-gates.md`
- Create: `docs/operations/change-policy.md`
- Create: `tests/contracts/test_contract_documentation.py`

**Interfaces:**

- Consumes: all nine contracts and validator behavior.
- Produces: maintainer-facing contract reference, phase gate, and migration policy used before later detailed plans are approved.

- [ ] **Step 1: Write failing documentation tests**

Create `tests/contracts/test_contract_documentation.py`:

```python
from pathlib import Path


def test_contract_docs_cover_every_catalog_entry(project_root: Path) -> None:
    architecture = (project_root / "docs/architecture/contracts.md").read_text(encoding="utf-8")
    for name in (
        "error", "artifact", "experiment", "evidence-link", "workflow-state",
        "decision", "review-finding", "annual-rule", "asset-manifest",
    ):
        assert f"`{name}`" in architecture


def test_change_policy_defines_breaking_change_and_migration(project_root: Path) -> None:
    policy = (project_root / "docs/operations/change-policy.md").read_text(encoding="utf-8")
    assert "破坏性变更" in policy
    assert "迁移" in policy
    assert "双端契约回归" in policy


def test_acceptance_gate_lists_exact_commands(project_root: Path) -> None:
    gate = (project_root / "docs/quality/acceptance-gates.md").read_text(encoding="utf-8")
    assert "uv run pytest tests/contracts -v" in gate
    assert "uv run python scripts/validate_contracts.py" in gate
```

- [ ] **Step 2: Verify the documentation tests fail**

Run: `uv run pytest tests/contracts/test_contract_documentation.py -v`

Expected: FAIL because the three documents do not exist.

- [ ] **Step 3: Write the three documents**

`docs/architecture/contracts.md` must define each contract's purpose, producer, consumer, ID prefix, required fields, failure semantics and one valid fixture link. It must state that relative paths use `/` and all times include timezone offsets.

`docs/quality/acceptance-gates.md` must list the two exact Phase 0 commands, expected zero exit codes, nine-contract count, unfinished-marker scan, and the requirement that each invalid fixture fails for its named reason.

`docs/operations/change-policy.md` must classify additive optional fields as backward compatible; removing fields, changing types, narrowing enums, changing ID patterns, or changing semantics as breaking. Breaking changes require a new `schema_version`, migration script, old/new fixtures, Codex/DSH contract regression, documentation update and release note before consumers migrate.

- [ ] **Step 4: Run the complete Phase 0 gate**

Run:

```powershell
uv run pytest tests/contracts -v
uv run python scripts/validate_contracts.py
$unfinishedMarkers = @('TO' + 'DO', 'T' + 'BD', '待' + '定', 'FIX' + 'ME')
Select-String -Path shared/contracts/*.json,docs/architecture/contracts.md,docs/quality/acceptance-gates.md,docs/operations/change-policy.md -Pattern $unfinishedMarkers -CaseSensitive:$false
git status --short
```

Expected: tests PASS; validator returns status `ok` and 9 contracts; unfinished-marker search returns no matches; Git status lists only the Task 7 documentation and test before commit.

- [ ] **Step 5: Commit Phase 0 documentation**

```powershell
git add docs/architecture/contracts.md docs/quality/acceptance-gates.md docs/operations/change-policy.md tests/contracts/test_contract_documentation.py
git commit -m "docs: define contract governance and acceptance gate"
```

### Task 8: Fresh-clone verification and phase handoff

**Files:**

- Modify only if verification finds a defect: files already created in Tasks 1–7.
- Record verification evidence in the execution handoff; do not create an extra report file unless the user requests one.

**Interfaces:**

- Consumes: committed Phase 0 repository.
- Produces: verified commit hash and the exact stable interfaces required to write the Phase 0A detailed plan.

- [ ] **Step 1: Verify repository cleanliness and commit history**

Run:

```powershell
git status --short
git log --oneline -8
```

Expected: clean status and separate commits for baseline, catalog, data contracts, workflow contracts, governance contracts, validator, and documentation.

- [ ] **Step 2: Recreate the locked environment**

Run:

```powershell
uv sync --frozen --dev
uv run python --version
```

Expected: sync succeeds without changing `uv.lock`; Python reports 3.11.x.

- [ ] **Step 3: Run the complete gate once**

Run:

```powershell
uv run pytest tests/contracts -v
uv run python scripts/validate_contracts.py
```

Expected: all tests PASS and validator reports 9 contracts with zero errors.

- [ ] **Step 4: Verify the validator detects a real regression**

Temporarily change the valid artifact fixture path from `data/input.csv` to `E:/data/input.csv`, run `uv run python scripts/validate_contracts.py`, and verify exit code `1` with an artifact validation error. Restore the original fixture using an editor patch, rerun the validator, and verify exit code `0`. Do not commit the temporary regression.

- [ ] **Step 5: Handoff exact Phase 0A inputs**

Report the final commit hash, Python version, uv version, nine-contract count, contract catalog path, validator command and any environment limitation. Phase 0A planning may begin only when the worktree is clean and all Phase 0 checks pass.

## Phase 0 completion criteria

Phase 0 is complete only when all eight tasks are committed, the full contract test suite passes, the read-only validator reports nine contracts and zero errors, the regression probe proves the validator can fail, and the repository is clean. Passing these conditions authorizes creation of the Phase 0A detailed plan; it does not authorize Phase 0A implementation without a separate user instruction.
