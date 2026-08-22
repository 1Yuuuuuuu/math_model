# Phase 1 可复现底座 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在全新 Windows 环境中诊断依赖、创建标准比赛工作区、记录实验并编译最小中文 PDF，交付 Phase 1「可复现底座」。

**Architecture:** `toolkit/src/cumcm_toolkit/` 提供四个确定性 Python 模块（环境诊断、项目骨架、实验记录、产物索引），全部复用 Phase 0/0A 已验证的契约 Schema 与格式校验；`shared/templates/` 提供项目工作区与最小 LaTeX 模板；`scripts/*.ps1` 提供幂等环境引导与检查入口。Phase 1 不实现任何模型运行、数据审计或 Skill，那些属于 Phase 2/3。

**Tech Stack:** Windows、Python 3.11、uv（0.12.x，由 bootstrap 引导）、pytest（`pythonpath` ini 选项）、MiKTeX（用户级安装）、xelatex、latexmk、JSON Schema Draft 2020-12、`jsonschema`、`referencing`、SHA-256、PowerShell 7（`pwsh`）。

**Spec:** `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`（Phase 1 章节，第 162–196 行）与 `docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md`（总体架构、工具体系、证据链）。

## Global Constraints

- Python 版本固定为 3.11（`environment.python_version` 契约常量为 `"3.11"`）；依赖由 `uv.lock` 锁定，正式结果不得只存在于 Notebook。
- 论文主生产线为 XeLaTeX 与最终 PDF；Windows 环境不得依赖符号链接。
- `shared/` 是唯一事实来源；toolkit 与测试只读消费 `shared/contracts/` 与 `shared/templates/`，不复制内容。
- 所有时间必须是带时区的 RFC 3339 字符串；哈希为 64 位小写十六进制；路径必须满足 `cumcm-workspace-path` 可移植规则（正斜杠、相对、无盘符、无 Windows 保留设备名）。
- 失败显式化（fail-closed）：环境缺依赖返回结构化失败，不误报"可用"；无法校验的记录不得产出。
- 每个任务独立提交并通过新鲜评审；步骤先写失败测试（RED）再实现（GREEN），逐任务验证。
- 变更面驱动验证：本计划只运行覆盖当前变更面的最小充分测试，Task 8 里程碑运行完整回归。
- 比赛工作区与核心隔离：`workspaces/` 已 gitignore；比赛临时修改不得污染 `shared/` 与 `toolkit/`。
- 本计划不安装 `paper-search`、不创建 `cumcm_*` 运行时 Skill、不实现 Phase 2+ 工具与 DSH 插件。
- 不引入新的第三方运行时依赖：Phase 1 全部使用标准库 + 现有依赖（`jsonschema`、`rfc3339-validator`、`referencing`、`pytest`）。

## 已探测的环境事实（2026-08-22，Phase 1 计划输入）

| 项 | 探测结果 |
| --- | --- |
| Python | 3.11.9，`D:\Python311\python.exe`（在 PATH） |
| uv | 不在 PATH；`.superpowers/bootstrap-uv` 不存在 → 需 preflight 引导 |
| TeX 发行版 | MiKTeX（用户级安装），根目录 `%LOCALAPPDATA%\Programs\MiKTeX` |
| xelatex | `C:\Users\YU\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe`（在 PATH） |
| latexmk | 同 MiKTeX bin 目录（在 PATH） |
| 仓库状态 | `main` 位于 `027ccc9`，Phase 0A 已合入；11 项契约验证通过 |

## 本计划的设计决策（Ruling，执行时据此判定，不得另起炉灶）

1. **toolkit 导入路径**：不改打包配置，`pyproject.toml` 的 `[tool.pytest.ini_options]` 增加 `pythonpath = ["toolkit/src", "."]`；`check_environment.ps1` 设置 `$env:PYTHONPATH = "$Root\toolkit\src;$Root"`。工具包打包留待 Phase 7 DSH 适配。成本：CLI 必须从仓库根运行或依赖 PYTHONPATH。
2. **契约复用**：toolkit 直接 `from scripts.validate_contracts import load_json, make_validator` 与 `from scripts.contract_formats import is_cumcm_workspace_path`。`scripts/` 是仓库根可导入模块（Phase 0 已验证）；未来阶段可把校验助手迁入 toolkit，届时走迁移。
3. **实验身份确定性**：`experiment_id = "exp_" + sha256(排序后的 input_artifact_ids + code_artifact_id + 稳定序列化参数 + 随机种子)[:24]`；相同输入、参数、种子产生相同 ID（满足退出标准）。
4. **产物 ID 确定性**：`artifact_id = "art_" + sha256(相对路径 + "\n" + sha256)[:24]`。
5. **页数与引用状态**：从 `main.log` 解析 `\((\d+) page` 取页数、检查 `undefined` 判引用状态，不新增 poppler/pypdf 依赖。
6. **最小 LaTeX 模板**：用 `article + fontspec + \setCJKmainfont{SimSun}`（Windows 自带宋体），**不用 ctex 包**，避免首次编译触发 MiKTeX 在线装包。完整论文模板属 Phase 4。
7. **不新增 JSON 契约**：scaffold 模板只含目录与 README，不写未版本化的 workspace 元数据文件；工作区状态契约由 Phase 6 `workflow-state` 承担。
8. **`.gitkeep` 与缓存目录不入索引**：占位文件不是产物；`.git`、`__pycache__`、`.pytest_cache`、`.superpowers`、`.venv`、`.worktrees` 被索引忽略。
9. **manifest/index 提供库 API + CLI**：doctor 与 scaffold 的 CLI 被 ps1 与验收使用；manifest/index 的 CLI 便于人工检查，消费方接口以库函数为准。
10. **PowerShell 脚本的测试边界**：ps1 是薄包装，逻辑由 doctor/scaffold 的单元测试覆盖；ps1 本身在 Task 2 与 Task 8 用真实命令冒烟验证，不写进 pytest。

## File structure and ownership

| 文件 | 单一职责 |
| --- | --- |
| `toolkit/src/cumcm_toolkit/__init__.py` | 工具包标记（空） |
| `toolkit/src/cumcm_toolkit/environment/doctor.py` | 结构化环境诊断（python/uv/xelatex/latexmk），fail-closed |
| `toolkit/src/cumcm_toolkit/project/scaffold.py` | 从 `shared/templates/project/` 创建比赛工作区，默认不覆盖 |
| `toolkit/src/cumcm_toolkit/experiments/manifest.py` | 生成符合 `experiment.schema.json` 的确定性实验记录 |
| `toolkit/src/cumcm_toolkit/artifacts/index.py` | 扫描工作区生成符合 `artifact.schema.json` 的产物索引 |
| `toolkit/tests/conftest.py` | `project_root` fixture（toolkit/tests 作用域） |
| `toolkit/tests/environment/test_doctor.py` | doctor 的存在/缺失/探测失败/CLI 测试 |
| `toolkit/tests/project/test_scaffold.py` | scaffold 创建/拒绝覆盖/模板缺失/CLI 测试 |
| `toolkit/tests/experiments/test_manifest.py` | manifest 确定性/契约校验/时区测试 |
| `toolkit/tests/artifacts/test_index.py` | index 产物生成/路径守卫/确定性测试 |
| `shared/templates/project/{README.md,data/.gitkeep,code/.gitkeep,experiments/.gitkeep,artifacts/.gitkeep,paper/.gitkeep}` | 标准比赛工作区模板 |
| `shared/templates/latex/main.tex` | 最小 XeLaTeX 中文论文模板（含前向引用） |
| `scripts/bootstrap.ps1` | 幂等恢复锁定环境（引导 uv + `uv sync --frozen --dev`） |
| `scripts/check_environment.ps1` | 运行 doctor CLI 并透传退出码 |
| `tests/integration/conftest.py` | `project_root` fixture（tests/integration 作用域） |
| `tests/integration/test_fresh_workspace.py` | 全新工作区端到端：scaffold → index → 契约校验 |
| `tests/integration/test_minimal_latex_build.py` | 最小中文 PDF 编译、页数、引用状态 |
| `tests/integration/test_operations_docs.py` | 运维文档与模板/检查项漂移防护 |
| `docs/operations/environment.md` | 依赖清单、探测事实、bootstrap 与检查命令 |
| `docs/operations/workspace-layout.md` | 标准工作区布局与产物/实验记录约定 |
| `pyproject.toml` | 追加 `pythonpath` 测试配置（唯一配置变更） |
| `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md` | Task 8 标记阶段 1 完成并记录交接输入 |

## Execution preflight: worktree 与锁定环境

1. 在 `main` 上确认工作树干净后，用 superpowers:using-git-worktrees 创建隔离工作区并检出新分支：

```powershell
git worktree add .worktrees/phase-1-foundation -b phase-1-foundation
```

2. 当前机器无全局 `uv`、无 `.venv`；恢复锁定环境（与 Phase 0A preflight 同法，目录为当前计划独立命名）：

```powershell
python -m venv .superpowers\bootstrap-uv
.superpowers\bootstrap-uv\Scripts\python.exe -m pip install uv==0.12.5
$env:UV_CACHE_DIR = 'E:\数学建模国赛\.superpowers\uv-cache'
.superpowers\bootstrap-uv\Scripts\uv.exe sync --frozen --dev
.venv\Scripts\python.exe --version
```

预期：Python 3.11.x；`uv.lock` 哈希与 Git 状态不变。bootstrap 与缓存目录是被忽略的执行资产，不是产品依赖。

3. 每步验证命令统一用 `.venv\Scripts\python.exe -m pytest <目标> -v -p no:cacheprovider`；CLI 冒烟用 `.venv\Scripts\python.exe -m cumcm_toolkit.<包>.<模块> ...`（cwd 必须为仓库根）。

---

### Task 1: toolkit 包基础与环境诊断 doctor

**Files:**

- Modify: `pyproject.toml`（`[tool.pytest.ini_options]` 追加 `pythonpath`）
- Create: `toolkit/src/cumcm_toolkit/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/environment/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/environment/doctor.py`
- Create: `toolkit/tests/conftest.py`
- Create: `toolkit/tests/environment/__init__.py`
- Create: `toolkit/tests/environment/test_doctor.py`

**Interfaces:**

- Consumes: 无（标准库）。
- Produces: `doctor(which: Callable[[str], str | None] = shutil.which) -> dict[str, object]`，稳定键 `doctor_version`、`status`（`"ok"`/`"failed"`）、`checks`（每个元素 `{name, required, found, ok}`）、`errors`；CLI `python -m cumcm_toolkit.environment.doctor` 输出 JSON，全部必需项通过时 exit 0，否则 exit 1。

- [ ] **Step 1: 配置 pytest 导入路径**

修改 `pyproject.toml` 的 `[tool.pytest.ini_options]`：

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "toolkit/tests"]
addopts = "--strict-markers --strict-config"
pythonpath = ["toolkit/src", "."]
```

- [ ] **Step 2: 写失败的环境诊断测试**

创建 `toolkit/tests/conftest.py`：

```python
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
```

创建 `toolkit/tests/environment/test_doctor.py`：

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.environment.doctor import doctor


def fake_which(present: set[str]) -> object:
    def lookup(name: str) -> str | None:
        if name in present:
            return f"C:/tools/{name}.exe"
        return None

    return lookup


def test_doctor_reports_ok_when_all_toolchains_present() -> None:
    payload = doctor(fake_which({"uv", "xelatex", "latexmk"}))
    assert payload["status"] == "ok"
    assert payload["errors"] == []
    names = {check["name"]: check for check in payload["checks"]}
    assert set(names) == {"python", "uv", "xelatex", "latexmk"}
    assert names["uv"]["found"] == "C:/tools/uv.exe"
    assert names["uv"]["ok"] is True


def test_doctor_fails_closed_on_missing_uv() -> None:
    payload = doctor(fake_which({"xelatex", "latexmk"}))
    assert payload["status"] == "failed"
    uv = next(check for check in payload["checks"] if check["name"] == "uv")
    assert uv["ok"] is False
    assert uv["found"] is None


def test_doctor_never_guesses_when_probe_errors() -> None:
    def broken_lookup(name: str) -> str | None:
        if name == "latexmk":
            raise OSError("probe exploded")
        return fake_which({"uv", "xelatex"})(name)

    payload = doctor(broken_lookup)
    assert payload["status"] == "failed"
    latexmk = next(check for check in payload["checks"] if check["name"] == "latexmk")
    assert latexmk["ok"] is False
    assert any("latexmk" in error for error in payload["errors"])


def test_doctor_cli_emits_stable_json(tmp_path: Path, project_root: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "cumcm_toolkit.environment.doctor"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1)
    payload = json.loads(result.stdout)
    assert set(payload) == {"doctor_version", "status", "checks", "errors"}
    assert payload["doctor_version"] == "1.0"
```

- [ ] **Step 3: 运行测试并确认 RED**

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/environment -v -p no:cacheprovider
```

预期：收集失败，`ModuleNotFoundError: cumcm_toolkit`（先建空 `__init__.py` 后重跑，RED 变为 `cannot import name 'doctor'` 或断言失败；最终 RED 必须是测试断言失败而非导入错误）。

- [ ] **Step 4: 实现最小 doctor**

创建 `toolkit/src/cumcm_toolkit/__init__.py`（空文件）、`toolkit/src/cumcm_toolkit/environment/__init__.py`（空文件）与 `toolkit/src/cumcm_toolkit/environment/doctor.py`：

```python
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from typing import Callable


REQUIRED_PYTHON = (3, 11)


@dataclass
class Check:
    name: str
    required: bool
    found: object
    ok: bool
    details: str = ""


def _check_python() -> Check:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = (sys.version_info.major, sys.version_info.minor) == REQUIRED_PYTHON
    return Check(
        name="python",
        required=True,
        found=version,
        ok=ok,
        details=f"need {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}.x",
    )


def _check_executable(
    name: str,
    required: bool,
    which: Callable[[str], str | None],
) -> Check:
    path = None
    error = ""
    try:
        path = which(name)
    except Exception as exc:  # noqa: BLE001 - fail-closed on any probe error
        error = str(exc)
    return Check(name=name, required=required, found=path, ok=path is not None and not error, details=error)


def doctor(which: Callable[[str], str | None] = shutil.which) -> dict[str, object]:
    checks = [
        _check_python(),
        _check_executable("uv", True, which),
        _check_executable("xelatex", True, which),
        _check_executable("latexmk", True, which),
    ]
    errors = sorted(f"{c.name}: {c.details}" for c in checks if c.details)
    failed = [c.name for c in checks if c.required and not c.ok]
    return {
        "doctor_version": "1.0",
        "status": "ok" if not failed else "failed",
        "checks": [
            {"name": c.name, "required": c.required, "found": c.found, "ok": c.ok}
            for c in checks
        ],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CUMCM workbench environment doctor")
    parser.parse_args()
    payload = doctor()
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 运行测试并确认 GREEN**

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/environment -v -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/contracts -q -p no:cacheprovider
```

预期：doctor 测试全部通过；契约测试仍全绿（pyproject 配置变更无副作用）。注意：`tests/contracts` 在 `pythonpath` 增加后行为不变。

- [ ] **Step 6: 提交**

```powershell
git add pyproject.toml toolkit
git commit -m "feat: add environment doctor and toolkit package"
```

### Task 2: bootstrap.ps1 与 check_environment.ps1

**Files:**

- Create: `scripts/bootstrap.ps1`
- Create: `scripts/check_environment.ps1`

**Interfaces:**

- Consumes: Task 1 的 `cumcm_toolkit.environment.doctor`（通过 `python -m` 调用）。
- Produces: `scripts/bootstrap.ps1` 幂等恢复 `.venv`（引导 uv 于 `.superpowers/bootstrap-uv`，然后 `uv sync --frozen --dev`）；`scripts/check_environment.ps1` 设置 `PYTHONPATH` 后运行 doctor 并透传退出码。

- [ ] **Step 1: 写 bootstrap.ps1**

创建 `scripts/bootstrap.ps1`：

```powershell
# 幂等恢复锁定环境：引导 uv（如缺）→ uv sync --frozen --dev → 报告 Python 版本。
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Bootstrap = Join-Path $Root '.superpowers\bootstrap-uv'
$UV = Join-Path $Bootstrap 'Scripts\uv.exe'
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$env:UV_CACHE_DIR = Join-Path $Root '.superpowers\uv-cache'

if (-not (Test-Path $UV)) {
    Write-Host "bootstrapping uv..."
    python -m venv $Bootstrap
    & (Join-Path $Bootstrap 'Scripts\python.exe') -m pip install --quiet uv==0.12.5
    if ($LASTEXITCODE -ne 0) { throw "uv bootstrap failed" }
}

Write-Host "syncing locked environment..."
& $UV sync --frozen --dev
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

& $VenvPython --version
if ($LASTEXITCODE -ne 0) { throw ".venv python check failed" }
```

- [ ] **Step 2: 写 check_environment.ps1**

创建 `scripts/check_environment.ps1`：

```powershell
# 运行环境诊断：要求 .venv 已由 bootstrap.ps1 建立；透传 doctor 退出码。
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Error "缺少 .venv：请先运行 scripts\bootstrap.ps1"
    exit 1
}

$env:PYTHONPATH = (Join-Path $Root 'toolkit\src') + ';' + $Root
& $VenvPython -m cumcm_toolkit.environment.doctor
exit $LASTEXITCODE
```

- [ ] **Step 3: 冒烟验证两个脚本**

```powershell
pwsh -NoProfile -File scripts\bootstrap.ps1
pwsh -NoProfile -File scripts\check_environment.ps1
```

预期：bootstrap 幂等成功；check_environment 输出稳定 JSON，`uv` 项 `ok=false`、`status="failed"`、exit 1（本机真实状态：uv 缺失，正确 fail-closed，不误报可用）。重复运行 bootstrap 不报错（幂等）。

- [ ] **Step 4: 提交**

```powershell
git add scripts/bootstrap.ps1 scripts/check_environment.ps1
git commit -m "feat: add environment bootstrap and check scripts"
```

### Task 3: 项目骨架 scaffold 与工作区模板

**Files:**

- Create: `shared/templates/project/README.md`
- Create: `shared/templates/project/data/.gitkeep`
- Create: `shared/templates/project/code/.gitkeep`
- Create: `shared/templates/project/experiments/.gitkeep`
- Create: `shared/templates/project/artifacts/.gitkeep`
- Create: `shared/templates/project/paper/.gitkeep`
- Create: `toolkit/src/cumcm_toolkit/project/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/project/scaffold.py`
- Create: `toolkit/tests/project/__init__.py`
- Create: `toolkit/tests/project/test_scaffold.py`

**Interfaces:**

- Consumes: 模板目录 `shared/templates/project/`（本任务创建）。
- Produces: `scaffold_workspace(target_root: Path, workspace_id: str, *, template_root: Path | None = None, overwrite: bool = False) -> dict[str, object]`，返回 `{workspace_id, root, files:[{path, size, sha256}]}`；目录非空且 `overwrite=False` 时抛 `FileExistsError`，模板缺失抛 `FileNotFoundError`。CLI `python -m cumcm_toolkit.project.scaffold --target <root> --workspace-id <id> [--overwrite]`。

- [ ] **Step 1: 创建工作区模板**

创建 `shared/templates/project/README.md`：

```markdown
# 比赛工作区

本目录是单次比赛的标准工作区，由 project-scaffold 创建，结构固定：

- `data/`        原始数据与清洗后数据
- `code/`        求解与分析脚本
- `experiments/` 实验记录（experiment manifest JSON）
- `artifacts/`   图表、结果表、索引等产物
- `paper/`       论文 LaTeX 工程

约定：实验记录写为 `experiments/<experiment_id>.json`，产物索引写为 `artifacts/index.json`。
比赛临时文件只允许放在本工作区内，不得修改共享核心。
```

其余文件为空的 `.gitkeep` 占位。

- [ ] **Step 2: 写失败的工作区创建测试**

创建 `toolkit/tests/project/test_scaffold.py`：

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

from cumcm_toolkit.project.scaffold import scaffold_workspace


def write_template(root: Path) -> None:
    (root / "data").mkdir(parents=True)
    (root / "code").mkdir()
    (root / "README.md").write_text("# workspace\n", encoding="utf-8")
    (root / "data" / "notes.txt").write_text("x", encoding="utf-8")


def test_scaffold_creates_exact_template_tree(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    result = scaffold_workspace(tmp_path, "ws_demo", template_root=template)
    target = tmp_path / "ws_demo"
    assert (target / "README.md").read_text(encoding="utf-8") == "# workspace\n"
    assert (target / "data" / "notes.txt").read_text(encoding="utf-8") == "x"
    paths = {entry["path"] for entry in result["files"]}
    assert paths == {"README.md", "data/notes.txt"}
    assert result["workspace_id"] == "ws_demo"


def test_scaffold_refuses_to_overwrite_existing_files(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    scaffold_workspace(tmp_path, "ws_demo", template_root=template)
    with pytest.raises(FileExistsError):
        scaffold_workspace(tmp_path, "ws_demo", template_root=template)


def test_scaffold_overwrite_flag_replaces_template_files(tmp_path: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    scaffold_workspace(tmp_path, "ws_demo", template_root=template)
    (tmp_path / "ws_demo" / "README.md").write_text("changed", encoding="utf-8")
    scaffold_workspace(tmp_path, "ws_demo", template_root=template, overwrite=True)
    assert (tmp_path / "ws_demo" / "README.md").read_text(encoding="utf-8") == "# workspace\n"


def test_scaffold_missing_template_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        scaffold_workspace(tmp_path, "ws_demo", template_root=tmp_path / "nope")


def test_scaffold_cli_reports_failure_json(tmp_path: Path, project_root: Path) -> None:
    template = tmp_path / "template"
    write_template(template)
    result = subprocess.run(
        [sys.executable, "-m", "cumcm_toolkit.project.scaffold",
         "--target", str(tmp_path), "--workspace-id", "ws_demo"],
        cwd=project_root, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
```

- [ ] **Step 3: 运行测试并确认 RED**

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/project -v -p no:cacheprovider
```

预期：收集失败或导入失败（`cumcm_toolkit.project.scaffold` 不存在）。

- [ ] **Step 4: 实现最小 scaffold**

创建 `toolkit/src/cumcm_toolkit/project/__init__.py`（空）与 `toolkit/src/cumcm_toolkit/project/scaffold.py`：

```python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[4] / "shared" / "templates" / "project"


def scaffold_workspace(
    target_root: Path,
    workspace_id: str,
    *,
    template_root: Path | None = None,
    overwrite: bool = False,
) -> dict[str, object]:
    root = target_root.resolve()
    target = root / workspace_id
    template = (template_root or DEFAULT_TEMPLATE).resolve()
    if not template.is_dir():
        raise FileNotFoundError(f"template not found: {template}")
    if target.exists() and not overwrite and any(p.is_file() for p in target.rglob("*")):
        raise FileExistsError(f"workspace already exists and is not empty: {target}")

    target.mkdir(parents=True, exist_ok=True)
    created = []
    for source in sorted(template.rglob("*")):
        if source.is_dir():
            continue
        relative = source.relative_to(template)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        destination.write_bytes(data)
        created.append(
            {
                "path": relative.as_posix(),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return {"workspace_id": workspace_id, "root": str(target), "files": created}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a standard CUMCM workspace")
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        result = scaffold_workspace(args.target, args.workspace_id, overwrite=args.overwrite)
    except (FileExistsError, FileNotFoundError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 运行测试并确认 GREEN**

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/project -v -p no:cacheprovider
```

预期：全部通过；用真实模板再冒烟一次：

```powershell
.venv\Scripts\python.exe -m cumcm_toolkit.project.scaffold --target .superpowers\sdd-smoke --workspace-id ws_smoke
```

- [ ] **Step 6: 提交**

```powershell
git add shared/templates/project toolkit/src/cumcm_toolkit/project toolkit/tests/project
git commit -m "feat: add project scaffold and workspace template"
```

### Task 4: 实验记录 manifest

**Files:**

- Create: `toolkit/src/cumcm_toolkit/experiments/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/experiments/manifest.py`
- Create: `toolkit/tests/experiments/__init__.py`
- Create: `toolkit/tests/experiments/test_manifest.py`

**Interfaces:**

- Consumes: `scripts.validate_contracts.load_json`、`make_validator`；`shared/contracts/experiment.schema.json`；仓库根 `uv.lock`。
- Produces: `derive_experiment_id(input_artifact_ids, code_artifact_id, parameters, random_seed) -> str`；`utc_now_rfc3339() -> str`；`lock_sha256_for(project_root: Path) -> str`；`create_experiment_record(*, input_artifact_ids, code_artifact_id, parameters, random_seed, status, output_artifact_ids, metrics, project_root, started_at=None, finished_at=None) -> dict[str, object]`，记录必须通过 `experiment.schema.json` 校验，否则抛 `ValueError`。

- [ ] **Step 1: 写失败的实验记录测试**

创建 `toolkit/tests/experiments/test_manifest.py`：

```python
from pathlib import Path

import pytest

from cumcm_toolkit.experiments.manifest import (
    create_experiment_record,
    derive_experiment_id,
)
from scripts.validate_contracts import load_json, make_validator


def test_experiment_id_is_deterministic_across_parameter_order() -> None:
    first = derive_experiment_id(["art_raw_data"], "art_solve_code", {"a": 1, "b": 2}, 7)
    second = derive_experiment_id(["art_raw_data"], "art_solve_code", {"b": 2, "a": 1}, 7)
    assert first == second
    assert first.startswith("exp_")
    assert len(first) == 4 + 24


def test_experiment_id_changes_with_seed_or_input() -> None:
    base = derive_experiment_id(["art_raw_data"], "art_solve_code", {}, 7)
    assert base != derive_experiment_id(["art_raw_data"], "art_solve_code", {}, 8)
    assert base != derive_experiment_id(["art_other"], "art_solve_code", {}, 7)


def test_experiment_record_validates_against_phase0_schema(project_root: Path, tmp_path: Path) -> None:
    lock = project_root / "uv.lock"
    if not lock.is_file():
        pytest.skip("uv.lock not present")
    record = create_experiment_record(
        input_artifact_ids=["art_raw_data"],
        code_artifact_id="art_solve_code",
        parameters={"max_iterations": 1000},
        random_seed=7,
        status="succeeded",
        output_artifact_ids=["art_result_table"],
        metrics={"rmse": 0.125},
        project_root=project_root,
    )
    schema = load_json(project_root / "shared/contracts/experiment.schema.json")
    validator = make_validator(schema)
    assert list(validator.iter_errors(record)) == []
    assert record["environment"]["python_version"] == "3.11"
    assert record["environment"]["lock_sha256"] == lock_sha256_expected(lock)


def lock_sha256_expected(lock: Path) -> str:
    import hashlib

    return hashlib.sha256(lock.read_bytes()).hexdigest()


def test_experiment_record_rejects_invalid_status(project_root: Path) -> None:
    with pytest.raises(ValueError):
        create_experiment_record(
            input_artifact_ids=["art_raw_data"],
            code_artifact_id="art_solve_code",
            parameters={},
            random_seed=None,
            status="exploded",
            output_artifact_ids=[],
            metrics={},
            project_root=project_root,
        )
```

- [ ] **Step 2: 运行测试并确认 RED**

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/experiments -v -p no:cacheprovider
```

预期：导入失败（模块不存在）。

- [ ] **Step 3: 实现最小 manifest**

创建 `toolkit/src/cumcm_toolkit/experiments/__init__.py`（空）与 `toolkit/src/cumcm_toolkit/experiments/manifest.py`：

```python
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.validate_contracts import load_json, make_validator

_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "shared" / "contracts" / "experiment.schema.json"
_SCHEMA = load_json(_SCHEMA_PATH)
_VALIDATOR = make_validator(_SCHEMA)


def _stable_parameters(parameters: dict[str, Any]) -> str:
    return json.dumps(parameters, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def derive_experiment_id(
    input_artifact_ids: list[str],
    code_artifact_id: str,
    parameters: dict[str, Any],
    random_seed: int | None,
) -> str:
    material = "\n".join(
        [
            "|".join(sorted(input_artifact_ids)),
            code_artifact_id,
            _stable_parameters(parameters),
            "none" if random_seed is None else str(random_seed),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"exp_{digest[:24]}"


def utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def lock_sha256_for(project_root: Path) -> str:
    lock = project_root / "uv.lock"
    if not lock.is_file():
        raise FileNotFoundError(f"uv.lock not found: {lock}")
    return hashlib.sha256(lock.read_bytes()).hexdigest()


def create_experiment_record(
    *,
    input_artifact_ids: list[str],
    code_artifact_id: str,
    parameters: dict[str, Any],
    random_seed: int | None,
    status: str,
    output_artifact_ids: list[str],
    metrics: dict[str, float],
    project_root: Path,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    now = utc_now_rfc3339()
    record: dict[str, Any] = {
        "schema_version": "1.0",
        "experiment_id": derive_experiment_id(
            input_artifact_ids, code_artifact_id, parameters, random_seed
        ),
        "input_artifact_ids": list(input_artifact_ids),
        "code_artifact_id": code_artifact_id,
        "parameters": dict(parameters),
        "random_seed": random_seed,
        "environment": {
            "python_version": "3.11",
            "lock_sha256": lock_sha256_for(project_root),
        },
        "started_at": started_at or now,
        "finished_at": finished_at or now,
        "status": status,
        "output_artifact_ids": list(output_artifact_ids),
        "metrics": dict(metrics),
    }
    errors = list(_VALIDATOR.iter_errors(record))
    if errors:
        raise ValueError(f"experiment record invalid: {errors[0].message}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an experiment manifest record")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--input-artifacts", required=True, help="comma-separated art_ ids")
    parser.add_argument("--code-artifact", required=True)
    parser.add_argument("--parameters", default="{}", help="JSON object")
    parser.add_argument("--random-seed", type=int, default=None)
    parser.add_argument("--status", choices=["succeeded", "failed", "cancelled"], required=True)
    parser.add_argument("--output-artifacts", default="", help="comma-separated art_ ids")
    parser.add_argument("--metrics", default="{}", help="JSON object of numbers")
    args = parser.parse_args()
    try:
        record = create_experiment_record(
            input_artifact_ids=[item for item in args.input_artifacts.split(",") if item],
            code_artifact_id=args.code_artifact,
            parameters=json.loads(args.parameters),
            random_seed=args.random_seed,
            status=args.status,
            output_artifact_ids=[item for item in args.output_artifacts.split(",") if item],
            metrics=json.loads(args.metrics),
            project_root=args.project_root,
        )
    except (ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(record, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行测试并确认 GREEN**

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/experiments -v -p no:cacheprovider
```

预期：全部通过（`uv.lock` 存在于仓库根，测试不跳过）。

- [ ] **Step 5: 提交**

```powershell
git add toolkit/src/cumcm_toolkit/experiments toolkit/tests/experiments
git commit -m "feat: add deterministic experiment manifest"
```

### Task 5: 产物索引 index

**Files:**

- Create: `toolkit/src/cumcm_toolkit/artifacts/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/artifacts/index.py`
- Create: `toolkit/tests/artifacts/__init__.py`
- Create: `toolkit/tests/artifacts/test_index.py`

**Interfaces:**

- Consumes: `scripts.contract_formats.is_cumcm_workspace_path`；`scripts.validate_contracts.load_json`、`make_validator`；`shared/contracts/artifact.schema.json`。
- Produces: `classify_kind(path: Path) -> str`；`derive_artifact_id(relative: str, sha256: str) -> str`；`make_artifact_record(root, relative, sha256, created_at, classify) -> dict`（路径不可移植时抛 `ValueError`）；`index_artifacts(workspace_root: Path, *, classify=classify_kind, now=None) -> list[dict]`（跳过 `.gitkeep` 与忽略目录，逐条契约校验）。CLI `python -m cumcm_toolkit.artifacts.index --root <workspace>`。

- [ ] **Step 1: 写失败的产物索引测试**

创建 `toolkit/tests/artifacts/test_index.py`：

```python
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cumcm_toolkit.artifacts.index import (
    classify_kind,
    derive_artifact_id,
    index_artifacts,
    make_artifact_record,
)
from scripts.validate_contracts import load_json, make_validator

FIXED = datetime(2026, 8, 22, 1, 0, 0, tzinfo=timezone.utc)


def write_workspace(root: Path) -> None:
    (root / "data").mkdir()
    (root / "code").mkdir()
    (root / "data" / "input.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (root / "code" / "solve.py").write_text("print(1)\n", encoding="utf-8")
    (root / "README.md").write_text("# ws\n", encoding="utf-8")


def test_index_artifacts_produces_valid_phase0_records(project_root: Path, tmp_path: Path) -> None:
    write_workspace(tmp_path)
    records = index_artifacts(tmp_path, now=lambda: FIXED)
    schema = load_json(project_root / "shared/contracts/artifact.schema.json")
    validator = make_validator(schema)
    for record in records:
        assert list(validator.iter_errors(record)) == []
    paths = {record["path"] for record in records}
    assert paths == {"data/input.csv", "code/solve.py", "README.md"}
    kinds = {record["path"]: record["kind"] for record in records}
    assert kinds["data/input.csv"] == "data"
    assert kinds["code/solve.py"] == "code"


def test_index_artifacts_is_deterministic(tmp_path: Path) -> None:
    write_workspace(tmp_path)
    first = index_artifacts(tmp_path, now=lambda: FIXED)
    second = index_artifacts(tmp_path, now=lambda: FIXED)
    assert first == second


def test_index_skips_gitkeep_and_caches(tmp_path: Path) -> None:
    write_workspace(tmp_path)
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    records = index_artifacts(tmp_path, now=lambda: FIXED)
    paths = {record["path"] for record in records}
    assert "artifacts/.gitkeep" not in paths
    assert all("__pycache__" not in path for path in paths)


def test_make_artifact_record_rejects_non_portable_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        make_artifact_record(
            tmp_path,
            "data/NUL.txt",
            "a" * 64,
            FIXED.isoformat(timespec="seconds"),
            classify_kind,
        )


def test_derive_artifact_id_is_stable_and_prefixed() -> None:
    first = derive_artifact_id("data/input.csv", "a" * 64)
    second = derive_artifact_id("data/input.csv", "a" * 64)
    assert first == second
    assert first.startswith("art_")
    assert len(first) == 4 + 24


def test_index_cli_emits_json(tmp_path: Path, project_root: Path) -> None:
    write_workspace(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "cumcm_toolkit.artifacts.index", "--root", str(tmp_path)],
        cwd=project_root, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    records = json.loads(result.stdout)
    assert isinstance(records, list)
    assert {record["path"] for record in records} == {"data/input.csv", "code/solve.py", "README.md"}
```

- [ ] **Step 2: 运行测试并确认 RED**

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/artifacts -v -p no:cacheprovider
```

预期：导入失败（模块不存在）。

- [ ] **Step 3: 实现最小 index**

创建 `toolkit/src/cumcm_toolkit/artifacts/__init__.py`（空）与 `toolkit/src/cumcm_toolkit/artifacts/index.py`：

```python
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from scripts.contract_formats import is_cumcm_workspace_path
from scripts.validate_contracts import load_json, make_validator

_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "shared" / "contracts" / "artifact.schema.json"
_SCHEMA = load_json(_SCHEMA_PATH)
_VALIDATOR = make_validator(_SCHEMA)

IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", ".superpowers", ".venv", ".worktrees"}

KIND_BY_SUFFIX = {
    ".csv": "data", ".xlsx": "data", ".xls": "data",
    ".py": "code", ".ipynb": "code", ".r": "code", ".jl": "code",
    ".png": "figure", ".jpg": "figure", ".jpeg": "figure", ".svg": "figure",
    ".pdf": "pdf", ".tex": "latex",
    ".md": "report", ".json": "config", ".yml": "config", ".yaml": "config",
}


def classify_kind(path: Path) -> str:
    return KIND_BY_SUFFIX.get(path.suffix.lower(), "other")


def derive_artifact_id(relative: str, sha256: str) -> str:
    digest = hashlib.sha256(f"{relative}\n{sha256}".encode("utf-8")).hexdigest()
    return f"art_{digest[:24]}"


def make_artifact_record(
    root: Path,
    relative: str,
    sha256: str,
    created_at: str,
    classify: Callable[[Path], str],
) -> dict[str, object]:
    if not is_cumcm_workspace_path(relative):
        raise ValueError(f"non-portable path in workspace: {relative}")
    record: dict[str, object] = {
        "schema_version": "1.0",
        "artifact_id": derive_artifact_id(relative, sha256),
        "kind": classify(root / relative),
        "path": relative,
        "sha256": sha256,
        "created_at": created_at,
        "source_artifact_ids": [],
    }
    errors = list(_VALIDATOR.iter_errors(record))
    if errors:
        raise ValueError(f"artifact record invalid: {errors[0].message}")
    return record


def index_artifacts(
    workspace_root: Path,
    *,
    classify: Callable[[Path], str] = classify_kind,
    now: Callable[[], datetime] | None = None,
) -> list[dict[str, object]]:
    root = workspace_root.resolve()
    records = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        relative_posix = relative.as_posix()
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        created = (now() if now else datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
        records.append(
            make_artifact_record(
                root, relative_posix, sha256, created.isoformat(timespec="seconds"), classify
            )
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Index workspace artifacts")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        records = index_artifacts(args.root)
    except ValueError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(records, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行测试并确认 GREEN**

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/artifacts -v -p no:cacheprovider
```

预期：全部通过。CLI 冒烟：

```powershell
.venv\Scripts\python.exe -m cumcm_toolkit.artifacts.index --root .superpowers\sdd-smoke\ws_smoke
```

- [ ] **Step 5: 提交**

```powershell
git add toolkit/src/cumcm_toolkit/artifacts toolkit/tests/artifacts
git commit -m "feat: add workspace artifact index"
```

### Task 6: 最小 XeLaTeX 中文模板与构建测试

**Files:**

- Create: `shared/templates/latex/main.tex`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_minimal_latex_build.py`

**Interfaces:**

- Consumes: 本机 MiKTeX（`xelatex`、`latexmk` 在 PATH）。
- Produces: 最小中文模板 `shared/templates/latex/main.tex`（`article + fontspec + SimSun`，含前向 `\ref`）；集成测试验证编译 exit 0、PDF 存在、日志页数 ≥ 1、无 undefined 引用；TeX 工具链缺失时测试跳过（skipif）。

- [ ] **Step 1: 创建最小中文 LaTeX 模板**

创建 `shared/templates/latex/main.tex`：

```latex
\documentclass[11pt]{article}
\usepackage{fontspec}
\setCJKmainfont{SimSun}
\title{最小中文论文}
\author{固定三人队}
\date{\today}
\begin{document}
\maketitle
\section{引言}\label{sec:intro}
这是一篇用于验证可复现编译链的最小中文论文。
第~\ref{sec:conclusion}~节总结全文。
\section{结论}\label{sec:conclusion}
本模板验证 XeLaTeX 中文编译、引用解析与页数读取。
\end{document}
```

- [ ] **Step 2: 写失败的编译测试**

创建 `tests/integration/conftest.py`：

```python
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
```

创建 `tests/integration/test_minimal_latex_build.py`：

```python
import re
import shutil
import subprocess
from pathlib import Path

import pytest

LATEXMK = shutil.which("latexmk")
XELATEX = shutil.which("xelatex")

pytestmark = pytest.mark.skipif(
    not (LATEXMK and XELATEX),
    reason="TeX toolchain (latexmk/xelatex) not available",
)


def test_minimal_chinese_pdf_compiles_and_reports_pages(
    project_root: Path, tmp_path: Path
) -> None:
    template = project_root / "shared" / "templates" / "latex"
    assert template.is_dir(), "latex template missing"
    dest = tmp_path / "paper"
    shutil.copytree(template, dest)

    result = subprocess.run(
        [LATEXMK, "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
        cwd=dest,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]

    pdf = dest / "main.pdf"
    assert pdf.is_file(), "main.pdf not produced"

    log = (dest / "main.log").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\((\d+) page", log)
    assert match, "page count not found in latexmk log"
    assert int(match.group(1)) >= 1
    assert "undefined" not in log.lower(), "undefined reference remains after latexmk reruns"
```

- [ ] **Step 3: 运行测试并确认 RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_minimal_latex_build.py -v -p no:cacheprovider
```

预期：断言失败（模板缺失 → `assert template.is_dir()` 失败，或导入失败）。若 MiKTeX 首次编译弹出"自动安装缺失包"提示导致超时，先在 Task 6 说明中手动预装（见 Step 4 注）。

- [ ] **Step 4: 运行测试并确认 GREEN**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_minimal_latex_build.py -v -p no:cacheprovider
```

预期：通过，日志显示 `(N page)`（N ≥ 1），无 undefined。注：若 MiKTeX 提示需要安装 `fontspec` 等基础包，执行 `miktex packages install fontspec` 或开启"自动安装缺失包"后重跑；本模板刻意避开 `ctex` 以降低首次编译的装包面。

- [ ] **Step 5: 提交**

```powershell
git add shared/templates/latex tests/integration
git commit -m "feat: add minimal xelatex template and build test"
```

### Task 7: 运维文档与文档漂移测试

**Files:**

- Create: `docs/operations/environment.md`
- Create: `docs/operations/workspace-layout.md`
- Create: `tests/integration/test_operations_docs.py`

**Interfaces:**

- Consumes: Task 1 的 doctor 检查项、Task 3 的模板树、Task 5 的索引忽略规则。
- Produces: `docs/operations/environment.md` 记录依赖清单与 2026-08-22 探测事实；`docs/operations/workspace-layout.md` 记录标准布局与记录约定；`tests/integration/test_operations_docs.py` 防漂移（模板树 ⊆ 文档、文档行 ∈ 模板树、doctor 检查项全部被文档覆盖、模板文件路径全部出现在文档中）。

- [ ] **Step 1: 写失败的操作文档测试**

创建 `tests/integration/test_operations_docs.py`：

```python
from pathlib import Path


def read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def template_files(root: Path) -> set[str]:
    template = root / "shared" / "templates" / "project"
    return {
        path.relative_to(template).as_posix()
        for path in template.rglob("*")
        if path.is_file()
    }


def test_environment_doc_covers_every_doctor_check(project_root: Path) -> None:
    doc = read(project_root, "docs/operations/environment.md")
    for name in ("python", "uv", "xelatex", "latexmk"):
        assert f"`{name}`" in doc
    assert "bootstrap.ps1" in doc
    assert "check_environment.ps1" in doc


def test_workspace_layout_doc_matches_template_tree(project_root: Path) -> None:
    doc = read(project_root, "docs/operations/workspace-layout.md")
    for relative in template_files(project_root):
        assert relative in doc, f"template file missing from layout doc: {relative}"
    assert "默认不覆盖" in doc
    assert "artifacts/index.json" in doc
    assert "experiments/<experiment_id>.json" in doc


def test_template_tree_matches_layout_doc_rows(project_root: Path) -> None:
    doc = read(project_root, "docs/operations/workspace-layout.md")
    rows = []
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "`" in stripped:
            first = stripped.strip("|").split("|")[0].strip().strip("`")
            if first.endswith("/") or first.endswith(".md"):
                rows.append(first)
    for row in rows:
        assert (project_root / "shared" / "templates" / "project" / row).exists(), (
            f"layout doc row not in template: {row}"
        )
```

- [ ] **Step 2: 写 environment.md**

创建 `docs/operations/environment.md`：

```markdown
# 环境与依赖

## 必需依赖

| 检查项 | 必需 | 说明 | 2026-08-22 实测 |
| --- | --- | --- | --- |
| `python` | 是 | 3.11.x（契约 `environment.python_version` 固定为 `"3.11"`） | 3.11.9（`D:\Python311\python.exe`） |
| `uv` | 是 | 依赖锁与 `.venv` 恢复工具 | 不在 PATH；由 `scripts/bootstrap.ps1` 引导至 `.superpowers\bootstrap-uv` |
| `xelatex` | 是 | XeLaTeX 引擎（中文 PDF 主生产线） | MiKTeX 用户级安装，`%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64\xelatex.exe` |
| `latexmk` | 是 | 多遍编译编排（引用解析） | 同 MiKTeX bin 目录 |

## 恢复环境

```powershell
pwsh -NoProfile -File scripts\bootstrap.ps1
```

幂等：引导缺失的 uv，然后 `uv sync --frozen --dev` 恢复 `.venv`；重复运行安全。

## 检查环境

```powershell
pwsh -NoProfile -File scripts\check_environment.ps1
```

输出稳定 JSON（`doctor_version`、`status`、`checks`、`errors`）；任一必需项缺失时 `status = "failed"` 且退出码为 1。诊断只报告探测事实，缺失即失败，不猜测"可用"。

## 失败处理

- 缺 `.venv`：先运行 `scripts\bootstrap.ps1`。
- `uv` 缺失：bootstrap 自动引导；如需手动：`python -m venv .superpowers\bootstrap-uv` 后 `pip install uv==0.12.5`。
- TeX 缺失或未在 PATH：安装 MiKTeX 并确认 `xelatex`、`latexmk` 在 PATH；本仓库依赖用户级安装（`%LOCALAPPDATA%\Programs\MiKTeX`）。
```

- [ ] **Step 3: 写 workspace-layout.md**

创建 `docs/operations/workspace-layout.md`：

```markdown
# 标准比赛工作区布局

每个比赛工作区由 `project-scaffold` 从 `shared/templates/project/` 创建，可重复生成；已存在文件默认不覆盖（`--overwrite` 显式覆盖模板文件）。

| 路径 | 用途 |
| --- | --- |
| `README.md` | 工作区说明与目录约定 |
| `data/` | 原始数据与清洗后数据 |
| `code/` | 求解与分析脚本 |
| `experiments/` | 实验记录，约定写为 `experiments/<experiment_id>.json`（符合 `experiment` 契约） |
| `artifacts/` | 图表、结果表等产物；约定索引写为 `artifacts/index.json`（符合 `artifact` 契约） |
| `paper/` | 论文 LaTeX 工程 |

产物索引由 `artifact-index` 生成：跳过 `.gitkeep` 占位文件与缓存目录（`.git`、`__pycache__`、`.pytest_cache`、`.superpowers`、`.venv`、`.worktrees`）；所有路径必须满足可移植工作区路径规则（相对、正斜杠、无保留设备名）。

工作区与核心仓库隔离：`workspaces/` 不入库；比赛临时修改不得直接污染 `shared/` 与 `toolkit/`。
```

- [ ] **Step 4: 运行测试并确认 GREEN**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_operations_docs.py -v -p no:cacheprovider
```

预期：全部通过。

- [ ] **Step 5: 提交**

```powershell
git add docs/operations tests/integration/test_operations_docs.py
git commit -m "docs: add environment and workspace layout operations guides"
```

### Task 8: 全新工作区端到端集成测试

**Files:**

- Create: `tests/integration/test_fresh_workspace.py`

**Interfaces:**

- Consumes: Task 3 `scaffold_workspace`、Task 5 `index_artifacts`、Phase 0 `artifact` 契约。
- Produces: 从模板创建全新工作区 → 索引 → 契约校验的端到端链路测试；重复 scaffold 拒绝覆盖。

- [ ] **Step 1: 写失败的新工作区测试**

创建 `tests/integration/test_fresh_workspace.py`：

```python
from pathlib import Path

import pytest

from cumcm_toolkit.artifacts.index import index_artifacts
from cumcm_toolkit.project.scaffold import DEFAULT_TEMPLATE, scaffold_workspace
from scripts.validate_contracts import load_json, make_validator


def test_fresh_workspace_end_to_end(project_root: Path, tmp_path: Path) -> None:
    result = scaffold_workspace(tmp_path, "ws_2026", template_root=DEFAULT_TEMPLATE)
    target = tmp_path / "ws_2026"
    assert (target / "README.md").is_file()
    for directory in ("data", "code", "experiments", "artifacts", "paper"):
        assert (target / directory).is_dir()

    records = index_artifacts(target)
    schema = load_json(project_root / "shared/contracts/artifact.schema.json")
    validator = make_validator(schema)
    assert records, "expected at least README.md to be indexed"
    for record in records:
        assert list(validator.iter_errors(record)) == []
        assert record["path"] not in ("data/.gitkeep", "code/.gitkeep")

    with pytest.raises(FileExistsError):
        scaffold_workspace(tmp_path, "ws_2026", template_root=DEFAULT_TEMPLATE)
```

- [ ] **Step 2: 运行测试并确认 GREEN**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_fresh_workspace.py -v -p no:cacheprovider
```

预期：通过（前置任务已全部实现）。

- [ ] **Step 3: 提交**

```powershell
git add tests/integration/test_fresh_workspace.py
git commit -m "test: cover fresh workspace end-to-end"
```

### Task 9: Phase 1 验收、主计划更新与交接

**Files:**

- Modify: `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`（仅当验证全部通过后）
- Modify only if verification finds a demonstrated defect: Tasks 1–8 创建的文件。

**Interfaces:**

- 产出干净提交哈希与 Phase 2 规划的已验证输入；不安装任何运行时 Skill 或插件。

- [ ] **Step 1: 运行完整验证（主计划 Phase 1 验收命令）**

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/environment toolkit/tests/project toolkit/tests/experiments toolkit/tests/artifacts -v -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/integration/test_fresh_workspace.py -v -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/integration/test_minimal_latex_build.py -v -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/contracts tests/integration -q -p no:cacheprovider
.venv\Scripts\python.exe scripts/validate_contracts.py
```

预期：全部通过；验证器 `{"contracts": 11, "errors": [], "status": "ok"}`。

- [ ] **Step 2: 冒烟验证 CLI 与 ps1**

```powershell
pwsh -NoProfile -File scripts\bootstrap.ps1
pwsh -NoProfile -File scripts\check_environment.ps1
.venv\Scripts\python.exe -m cumcm_toolkit.project.scaffold --target .superpowers\acceptance-smoke --workspace-id ws_ok
.venv\Scripts\python.exe -m cumcm_toolkit.artifacts.index --root .superpowers\acceptance-smoke\ws_ok
```

预期：bootstrap 幂等；check_environment 输出 JSON（uv 项 `ok=false` 为预期真实状态，不误报）；scaffold/index CLI exit 0。

- [ ] **Step 3: 更新主计划跟踪**

修改 `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`：

- Program-level tracking 中：`- [ ] 阶段 1：...` 改为 `- [x] 阶段 1：新环境诊断、标准工作区和最小 PDF 通过，完成向阶段 2 的历史交接。`
- 在 Phase 1 章节末尾新增：

```markdown
**Verified inputs (2026-08-22):** Python 3.11.9（`D:\Python311`）；uv 由 `scripts/bootstrap.ps1` 引导；TeX 为 MiKTeX 用户级安装，`xelatex`/`latexmk` 在 PATH；11 项契约不变；toolkit 通过 pytest `pythonpath` 导入，无新增依赖。
```

- [ ] **Step 4: 扫描未完成标记并检查工作树**

```powershell
$markers = @(('TO' + 'DO'), ('T' + 'BD'), ('FIX' + 'ME'), ('待' + '定'))
Select-String -Path toolkit\src\cumcm_toolkit\*.py,toolkit\src\cumcm_toolkit\**\*.py,shared\templates\*\*,docs\operations\*.md,tests\integration\*.py -Pattern $markers -CaseSensitive:$false
git diff --check
git status --short
```

预期：无未完成标记；`git diff --check` 干净；仅出现本计划有意提交的文件。

- [ ] **Step 5: 提交主计划更新并交接**

```powershell
git add docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md
git commit -m "docs: mark phase 1 complete and record verified inputs"
```

交接报告须包含：最终提交哈希；Python/uv/TeX 版本与来源；11 项契约不变声明；doctor 检查项与实测状态；模板与文档路径；Phase 2 的已验证输入（scaffold 布局、manifest/index 库签名、最小 LaTeX 模板路径）；显式声明 Phase 1 未安装任何运行时 Skill、CLI 或 DSH 插件。

## Completion criteria

本计划完成当且仅当：

- 环境诊断对缺失依赖返回结构化失败，不误报"可用"（doctor 单元测试 + 真实机器冒烟均为 fail-closed）。
- 项目骨架可重复创建，默认不覆盖已有文件（scaffold 单元测试 + `test_fresh_workspace.py`）。
- 相同输入、参数和随机种子生成一致的实验身份与关键结果（manifest 确定性测试）。
- 最小 XeLaTeX 中文论文可编译，引用状态和页数可读取（`test_minimal_latex_build.py`）。
- 主计划 Phase 1 章节与 Program-level tracking 反映完成状态，并记录 2026-08-22 实测输入。
- 全部测试通过、验证器 11 契约零错误、工作树干净。

## 交接输入（Phase 2 规划消费）

- `scaffold_workspace(target_root, workspace_id, *, template_root=None, overwrite=False)` 与工作区模板树 `shared/templates/project/`。
- `create_experiment_record(...)` 与 `derive_experiment_id(...)`（契约 `experiment.schema.json` 已校验）。
- `index_artifacts(workspace_root, ...)` 与 `derive_artifact_id(...)`（契约 `artifact.schema.json` 已校验）。
- 最小 LaTeX 模板 `shared/templates/latex/main.tex` 与页数/引用解析约定（日志解析，无新依赖）。
- doctor 检查项与 `scripts/bootstrap.ps1`、`scripts/check_environment.ps1`。
- 本计划未创建 Phase 2+ 的任何数据/模型/评价工具、运行时 Skill 或 DSH 插件；它们仍需各自阶段计划。
