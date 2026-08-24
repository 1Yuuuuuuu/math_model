# Phase 2 高频模型核心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付首批基础知识与模型卡、文献检索/去重/来源评价知识，以及评价、预测、优化三类代表场景共用的数据与实验工具，全部通过结构检查与集成场景验证。

**Architecture:** 两条轨道在集成场景汇合：① 知识轨道——`shared/knowledge/` 提供基础文档、统一结构模型卡（含结构校验 Schema 与目录）、文献知识三件套（规则文档 + 负例测试）；② 工具轨道——`toolkit/src/cumcm_toolkit/` 新增 data/profile、data/transform、models/registry、models/runner、evaluation/metrics、evaluation/baselines、evaluation/sensitivity、results/export 八个模块，全部复用 Phase 1 的契约校验与确定性约定。两类代表场景（评价/预测/优化）从数据审计跑到结果导出，验证完整链路。

**Tech Stack:** Windows、Python 3.11、uv、pytest、numpy、pandas、scipy、scikit-learn、statsmodels、matplotlib、JSON Schema Draft 2020-12、PyYAML（或等效 YAML 读取）、`jsonschema`、`referencing`。

**Spec:** `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`（Phase 2 章节，第 198–243 行）与 `docs/superpowers/specs/2026-08-21-cumcm-workbench-design.md`（基础/模型知识范围、统一模型卡结构、工具清单）。

## Global Constraints

- Python 3.11 固定；依赖由 `uv.lock` 锁定；正式结果不得只存在于 Notebook（本阶段全部结果由可重复脚本产出）。
- `shared/` 是唯一事实来源：知识、规则、模板、目录只维护一份；toolkit 只读消费 `shared/contracts/` 与 `shared/knowledge/`，不复制内容。
- 所有时间带时区 RFC 3339；哈希 64 位小写十六进制；路径满足 `cumcm-workspace-path`；JSON 严格（拒绝 NaN/Infinity）。
- 失败显式化（fail-closed）：数据/模型/指标任何一步不可验证即停止并结构化报错，不猜测。
- Phase 2 **只交付共享知识与规则**，不实现运行时 Skill；Codex `literature-researcher` 属 Phase 3，`adapters/codex/skills/literature-researcher/` 不得在本阶段出现。
- 文献检索只生成候选；未经人工确认不得进入正式引用（沿用 Phase 0A 路由政策）。
- 引用量/期刊等级不得等同于来源质量或模型正确性（来源评价规则必须写明）。
- 每个任务独立提交并通过新鲜评审；先 RED 后 GREEN；变更面驱动验证，Task 12 里程碑完整回归。
- 新增依赖只允许：numpy、pandas、scipy、scikit-learn、statsmodels、matplotlib、PyYAML（写入 pyproject 并锁定）。
- 模型卡内容不得虚构数据或结论；合成数据必须由测试内确定性生成（固定随机种子）。

## 已探测的环境事实（2026-08-22，Phase 2 计划输入）

| 项 | 探测结果 |
| --- | --- |
| 仓库状态 | `main` 位于 `9d727ec`（含 Phase 0/0A/1 全部内容），已推送 origin |
| Phase 1 交付 | `cumcm_toolkit.{environment,project,experiments,artifacts}` 四包；`scripts/bootstrap.ps1`、`check_environment.ps1`；371 测试 + 集成 5/5 |
| Python | 3.11.9（`D:\Python311`）；`.venv` 在主树（`E:\数学建模国赛\.venv`） |
| 依赖现状 | jsonschema、rfc3339-validator、referencing、pytest（无 numpy/pandas/scipy/sklearn/statsmodels/matplotlib/yaml） |
| 执行环境 | 见 Phase 1 ledger 的沙盒 ruling（升级命令忽略 workdir、测试用主树 `.venv` 绝对路径 + `PYTHONDONTWRITEBYTECODE=1` + `-p no:cacheprovider`、子代理不跑 git、控制器提交、评审包数组逐行写法） |

## 本计划的设计决策（Ruling，执行时据此判定）

1. **模型卡结构 Schema 不进契约目录**：`shared/knowledge/model-card.schema.json` 是知识资产，不加入 `shared/contracts/catalog.json`（避免 Phase 0 契约目录膨胀）；由 `tests/knowledge/test_model_card_structure.py` 强制所有卡片符合该 Schema。
2. **模型卡目录**：`shared/knowledge/model-catalog.yaml` 登记每张卡（id、name、category、file、status、priority），卡片本体为 `shared/knowledge/model-cards/{category}/{id}.md`，YAML front-matter + Markdown 正文。
3. **知识文档结构检查**：基础文档与模型卡通过"必备小节标题集合"检查（测试内断言每个文件的标题集是模板标题集的超集），不搞第二套 Schema。
4. **文献去重规则可执行化**：规则写在 `shared/knowledge/literature/deduplication.md`；其确定性行为由 `tests/knowledge/test_literature_knowledge.py` 内的参考实现（按文档规则分组）对合成样例断言——测试代码即规则契约。
5. **指标泄漏检测**：`evaluation/metrics.py` 提供 `detect_improper_split(train, test, key_columns)`（训练/测试行重叠）与 `detect_target_leakage(features, target, tolerance)`（特征与目标完美相关）两个确定性检测，退出标准"能识别至少一个数据泄漏或错误划分反例"由测试构造的反例验证。
6. **三类代表场景**：全部用测试内确定性合成数据（固定种子），预期值解析可手算/已知；场景链路 = profile → transform → 模型运行 → metrics → sensitivity → export → 断言。评价用熵权法+TOPSIS、预测用线性回归（已知系数）、优化用 scipy linprog 小规模 LP（已知最优）。
7. **YAML 读取**：`model-catalog.yaml` 与文献知识不引入运行时 YAML 依赖于 toolkit 主路径；仅测试/校验脚本用 PyYAML（dev 依赖）。若实现者认为需运行时读取，改为 JSON 目录（ruling 允许，但必须记录）。
8. **图表导出**：matplotlib 仅用于 `results/export.py` 的 `save_figure` 辅助（Agg 后端，无显示）；场景测试只断言文件存在与尺寸，不检查像素。
9. **statsmodels/sklearn 使用边界**：只用于代表场景的最小模型（线性回归、决策树、K-means、ARIMA 或灰色预测最小示例）；不实现通用框架。

## File structure and ownership

| 文件 | 单一职责 |
| --- | --- |
| `pyproject.toml` | 追加 numpy/pandas/scipy/scikit-learn/statsmodels/matplotlib/PyYAML 依赖 |
| `shared/knowledge/foundations/{data-types,descriptive-stats,probability-estimation,hypothesis-testing,correlation-causation,overfitting,data-leakage,optimization-basics,error-residual,cross-validation,robustness-sensitivity}.md` | 11 篇基础文档（必备小节见 Task 8） |
| `shared/knowledge/model-card.schema.json` | 模型卡统一结构 Schema（Draft 2020-12） |
| `shared/knowledge/model-card-template.md` | 模型卡模板（含 17 个必备小节说明） |
| `shared/knowledge/model-catalog.yaml` | 卡片目录（id/name/category/file/status/priority） |
| `shared/knowledge/model-cards/{data,evaluation,prediction,optimization,classification,statistics}/<id>.md` | 首批模型卡（Task 9 清单） |
| `shared/knowledge/literature/{search-strategy,deduplication,source-evaluation}.md` | 文献检索/去重/来源评价规则 |
| `tests/knowledge/test_model_card_structure.py` | 卡片结构检查（Schema + 标题集 + 目录一致性） |
| `tests/knowledge/test_literature_knowledge.py` | 文献知识负例测试（重复 DOI、规范化标题、标识冲突、仅引用量信号） |
| `toolkit/src/cumcm_toolkit/data/{profile,transform}.py` | 数据审计与可配置清洗 |
| `toolkit/src/cumcm_toolkit/models/{registry,runner}.py` | 统一模型注册与运行接口 |
| `toolkit/src/cumcm_toolkit/evaluation/{metrics,baselines,sensitivity}.py` | 指标/基线/敏感性 |
| `toolkit/src/cumcm_toolkit/results/export.py` | 标准 JSON/CSV/LaTeX 表格/图表导出 |
| `toolkit/tests/{data,models,evaluation,results}/test_*.py` | 各模块单元测试 |
| `tests/integration/test_{evaluation,prediction,optimization}_scenario.py` | 三类代表场景端到端 |
| `docs/operations/`（如需） | 数据/模型/评价约定说明 |

## Execution preflight: 依赖扩展与锁定环境

1. 用 superpowers:using-git-worktrees 创建隔离工作区并检出新分支（如 `.worktrees/phase-2-model-core -b phase-2-model-core`）。
2. 更新 `pyproject.toml` dependencies 追加：

```toml
dependencies = [
  "jsonschema>=4.23,<5",
  "rfc3339-validator>=0.1.4,<0.2",
  "numpy>=1.26,<3",
  "pandas>=2.2,<3",
  "scipy>=1.11,<2",
  "scikit-learn>=1.4,<2",
  "statsmodels>=0.14,<1",
  "matplotlib>=3.8,<4",
]
```

`[dependency-groups] dev` 追加 `"pyyaml>=6,<7"`。

3. 锁定并同步（需联网下载；用主树既有 bootstrap-uv）：

```powershell
$env:UV_CACHE_DIR = 'E:\数学建模国赛\.superpowers\uv-cache'
E:\数学建模国赛\.superpowers\bootstrap-uv\Scripts\uv.exe lock
E:\数学建模国赛\.superpowers\bootstrap-uv\Scripts\uv.exe sync --dev
E:\数学建模国赛\.venv\Scripts\python.exe -c "import numpy, pandas, scipy, sklearn, statsmodels, matplotlib, yaml; print('deps ok')"
```

预期：`deps ok`；`uv.lock` 更新（本计划有意为之）。

---

### Task 1: 数据审计 profile

**Files:**

- Create: `toolkit/src/cumcm_toolkit/data/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/data/profile.py`
- Create: `toolkit/tests/data/__init__.py`
- Create: `toolkit/tests/data/test_profile.py`

**Interfaces:**

- Consumes: 标准库 + pandas/numpy。
- Produces:
  - `profile_dataframe(df: pd.DataFrame, *, key_columns: list[str] | None = None) -> dict[str, object]`：稳定键 `{column_count, row_count, columns:[{name, dtype, missing, unique, null_ratio}], duplicate_rows, numeric_summary:{col:{min,max,mean,std}}, key_uniqueness:{col:unique_count}, warnings:[...]}`；缺失>0.5 比例、全缺失列、重复行、key 非唯一均进 warnings；任一列无法统计时该列摘要为 `null`（不猜测）。
  - `profile_csv(path: Path, *, key_columns=None, **kwargs) -> dict[str, object]`：读 CSV 后调 `profile_dataframe`；读取失败抛 `ValueError`（含路径与原因）。
  - 所有数字输出用 `round(..., 6)`；NaN 缺失计数用 `df.isna()`；`dtype` 用 `str(df[col].dtype)`。

- [ ] **Step 1: 写失败测试**（TDD）

创建 `toolkit/tests/data/test_profile.py`：

```python
import math
from pathlib import Path

import pandas as pd
import pytest

from cumcm_toolkit.data.profile import profile_csv, profile_dataframe


def test_profile_reports_shape_missing_and_warnings() -> None:
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "score": [0.1, 0.2, None, 0.4],
            "group": ["a", "a", "b", "b"],
        }
    )
    result = profile_dataframe(df, key_columns=["id"])
    assert result["column_count"] == 3
    assert result["row_count"] == 4
    columns = {c["name"]: c for c in result["columns"]}
    assert columns["score"]["missing"] == 1
    assert columns["score"]["null_ratio"] == pytest.approx(0.25)
    assert columns["group"]["unique"] == 2
    assert result["key_uniqueness"]["id"] == 4
    assert any("missing" in w and "score" in w for w in result["warnings"])


def test_profile_flags_duplicate_rows_and_non_unique_key() -> None:
    df = pd.DataFrame({"id": [1, 1, 2], "v": [1.0, 1.0, 2.0]})
    result = profile_dataframe(df, key_columns=["id"])
    assert result["duplicate_rows"] == 1
    assert any("key" in w and "id" in w for w in result["warnings"])


def test_profile_numeric_summary_rounded_and_null_when_impossible() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "s": ["a", "b", "c"]})
    result = profile_dataframe(df)
    assert result["numeric_summary"]["x"]["mean"] == pytest.approx(2.0)
    assert result["numeric_summary"]["s"] is None
    assert isinstance(result["numeric_summary"]["x"]["std"], float)


def test_profile_csv_fails_closed_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        profile_csv(tmp_path / "nope.csv")


def test_profile_csv_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    result = profile_csv(path)
    assert result["row_count"] == 2
    assert result["column_count"] == 2
```

- [ ] **Step 2: 运行并确认 RED**（`ModuleNotFoundError` 或断言失败）

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
& "E:\数学建模国赛\.venv\Scripts\python.exe" -m pytest toolkit/tests/data -v -p no:cacheprovider
```

- [ ] **Step 3: 实现最小 profile**

创建 `toolkit/src/cumcm_toolkit/data/profile.py`：

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _warn(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def profile_dataframe(
    df: pd.DataFrame, *, key_columns: list[str] | None = None
) -> dict[str, object]:
    warnings: list[str] = []
    columns = []
    numeric_summary: dict[str, object] = {}
    for name in df.columns:
        series = df[name]
        missing = int(series.isna().sum())
        row_count = len(df)
        entry: dict[str, object] = {
            "name": str(name),
            "dtype": str(series.dtype),
            "missing": missing,
            "unique": int(series.nunique()),
            "null_ratio": round(missing / row_count, 6) if row_count else 0.0,
        }
        columns.append(entry)
        if missing == row_count:
            _warn(warnings, f"column all missing: {name}")
        elif missing / row_count > 0.5:
            _warn(warnings, f"column mostly missing: {name}")
        if pd.api.types.is_numeric_dtype(series.dtype) and missing != row_count:
            clean = pd.to_numeric(series, errors="coerce").dropna()
            if len(clean):
                numeric_summary[str(name)] = {
                    "min": round(float(clean.min()), 6),
                    "max": round(float(clean.max()), 6),
                    "mean": round(float(clean.mean()), 6),
                    "std": round(float(clean.std(ddof=0)), 6),
                }
            else:
                numeric_summary[str(name)] = None
        else:
            numeric_summary[str(name)] = None

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows:
        _warn(warnings, f"duplicate rows: {duplicate_rows}")
    key_uniqueness: dict[str, int] = {}
    if key_columns:
        for key in key_columns:
            if key not in df.columns:
                _warn(warnings, f"key column missing: {key}")
                continue
            unique_count = int(df[key].nunique())
            key_uniqueness[key] = unique_count
            if unique_count != len(df):
                _warn(warnings, f"key not unique: {key}")

    return {
        "column_count": int(df.shape[1]),
        "row_count": int(df.shape[0]),
        "columns": columns,
        "duplicate_rows": duplicate_rows,
        "numeric_summary": numeric_summary,
        "key_uniqueness": key_uniqueness,
        "warnings": warnings,
    }


def profile_csv(path: Path, *, key_columns: list[str] | None = None, **kwargs: Any) -> dict[str, object]:
    try:
        df = pd.read_csv(path, **kwargs)
    except Exception as exc:
        raise ValueError(f"cannot read csv {path}: {exc}") from exc
    return profile_dataframe(df, key_columns=key_columns)


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile a CSV data file")
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--key-columns", default="", help="comma-separated key columns")
    args = parser.parse_args()
    try:
        result = profile_csv(
            args.path, key_columns=[c for c in args.key_columns.split(",") if c]
        )
    except ValueError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行并确认 GREEN**（含契约回归）

```powershell
& "E:\数学建模国赛\.venv\Scripts\python.exe" -m pytest toolkit/tests/data -v -p no:cacheprovider
& "E:\数学建模国赛\.venv\Scripts\python.exe" -m pytest tests/contracts -q -p no:cacheprovider
```

- [ ] **Step 5: 提交**

```powershell
git add toolkit/src/cumcm_toolkit/data toolkit/tests/data
git commit -m "feat: add data profile audit"
```

### Task 2: 数据变换 transform

**Files:**

- Create: `toolkit/src/cumcm_toolkit/data/transform.py`
- Create: `toolkit/tests/data/test_transform.py`

**Interfaces:**

- Produces:
  - `transform_dataframe(df: pd.DataFrame, steps: list[dict[str, object]]) -> tuple[pd.DataFrame, dict[str, object]]`：`steps` 每项为 `{"op": str, **args}`，支持 `drop_columns`（args: columns）、`drop_missing`（args: subset=None）、`fill_missing`（args: columns, value）、`normalize`（args: columns, method="minmax"|"zscore"）、`to_datetime`（args: columns）、`cast`（args: columns, dtype）；返回 `(新df, 变换记录 {steps_applied, warnings})`；未知 op 或参数非法抛 `ValueError`（fail-closed）。
  - 变换记录 `warnings` 收集"列不存在/已全缺失/归一化后常数列"等可继续但不理想的情况；任何 op 出错即停止并抛错。

- [ ] **Step 1: 写失败测试**

创建 `toolkit/tests/data/test_transform.py`：

```python
import pandas as pd
import pytest

from cumcm_toolkit.data.transform import transform_dataframe


def test_drop_and_fill_steps_apply_in_order() -> None:
    df = pd.DataFrame({"a": [1.0, None, 3.0], "b": [1, 2, 3], "c": [0, 0, 0]})
    out, record = transform_dataframe(
        df,
        [
            {"op": "fill_missing", "columns": ["a"], "value": 0.0},
            {"op": "drop_columns", "columns": ["c"]},
        ],
    )
    assert list(out.columns) == ["a", "b"]
    assert out["a"].isna().sum() == 0
    assert record["steps_applied"] == 2


def test_normalize_minmax() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    out, _ = transform_dataframe(df, [{"op": "normalize", "columns": ["x"], "method": "minmax"}])
    assert out["x"].tolist() == pytest.approx([0.0, 0.5, 1.0])


def test_unknown_op_fails_closed() -> None:
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(ValueError):
        transform_dataframe(df, [{"op": "teleport", "columns": ["a"]}])


def test_missing_column_warns_but_continues() -> None:
    df = pd.DataFrame({"a": [1, 2]})
    out, record = transform_dataframe(df, [{"op": "drop_columns", "columns": ["zz"]}])
    assert any("zz" in w for w in record["warnings"])
```

- [ ] **Step 2: RED** → **Step 3: 实现**

创建 `toolkit/src/cumcm_toolkit/data/transform.py`：

```python
from __future__ import annotations

from typing import Any

import pandas as pd


def transform_dataframe(
    df: pd.DataFrame, steps: list[dict[str, object]]
) -> tuple[pd.DataFrame, dict[str, object]]:
    if not isinstance(steps, list):
        raise ValueError("steps must be a list")
    out = df.copy()
    warnings: list[str] = []
    applied = 0

    def missing_columns(columns: list[str]) -> list[str]:
        return [c for c in columns if c not in out.columns]

    for index, step in enumerate(steps):
        op = step.get("op")
        if not isinstance(op, str):
            raise ValueError(f"step {index}: op must be a string")
        if op == "drop_columns":
            columns = list(step.get("columns", []))
            missing = missing_columns(columns)
            if missing:
                warnings.append(f"drop_columns: missing columns {missing}")
            out = out.drop(columns=[c for c in columns if c in out.columns], errors="ignore")
        elif op == "drop_missing":
            subset = step.get("subset")
            subset = list(subset) if subset else None
            if subset:
                missing = missing_columns(subset)
                if missing:
                    warnings.append(f"drop_missing: missing columns {missing}")
            out = out.dropna(subset=subset)
        elif op == "fill_missing":
            columns = list(step.get("columns", []))
            value = step.get("value")
            missing = missing_columns(columns)
            if missing:
                warnings.append(f"fill_missing: missing columns {missing}")
            for column in [c for c in columns if c in out.columns]:
                out[column] = out[column].fillna(value)
        elif op == "normalize":
            columns = list(step.get("columns", []))
            method = step.get("method", "minmax")
            if method not in {"minmax", "zscore"}:
                raise ValueError(f"step {index}: unknown normalize method {method}")
            missing = missing_columns(columns)
            if missing:
                warnings.append(f"normalize: missing columns {missing}")
            for column in [c for c in columns if c in out.columns]:
                if not pd.api.types.is_numeric_dtype(out[column].dtype):
                    raise ValueError(f"step {index}: column {column} is not numeric")
                clean = pd.to_numeric(out[column], errors="coerce")
                if method == "minmax":
                    lo, hi = clean.min(), clean.max()
                    if pd.isna(lo) or lo == hi:
                        warnings.append(f"normalize: constant or empty column {column}")
                        out[column] = 0.0
                    else:
                        out[column] = (clean - lo) / (hi - lo)
                else:
                    mean, std = clean.mean(), clean.std(ddof=0)
                    if pd.isna(std) or std == 0:
                        warnings.append(f"normalize: constant or empty column {column}")
                        out[column] = 0.0
                    else:
                        out[column] = (clean - mean) / std
        elif op == "to_datetime":
            for column in list(step.get("columns", [])):
                if column not in out.columns:
                    warnings.append(f"to_datetime: missing column {column}")
                    continue
                out[column] = pd.to_datetime(out[column], errors="raise")
        elif op == "cast":
            for column in list(step.get("columns", [])):
                if column not in out.columns:
                    warnings.append(f"cast: missing column {column}")
                    continue
                dtype = step.get("dtype")
                if not isinstance(dtype, str):
                    raise ValueError(f"step {index}: cast requires dtype")
                out[column] = out[column].astype(dtype)
        else:
            raise ValueError(f"step {index}: unknown op {op}")
        applied += 1

    return out, {"steps_applied": applied, "warnings": sorted(set(warnings))}
```

- [ ] **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add configurable data transform`）

### Task 3: 模型注册与运行 registry/runner

**Files:**

- Create: `toolkit/src/cumcm_toolkit/models/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/models/registry.py`
- Create: `toolkit/src/cumcm_toolkit/models/runner.py`
- Create: `toolkit/tests/models/__init__.py`
- Create: `toolkit/tests/models/test_registry.py`
- Create: `toolkit/tests/models/test_runner.py`

**Interfaces:**

- `register_model(name: str, factory: Callable[..., Any]) -> None`、`list_models() -> list[str]`、`get_model(name: str) -> Callable[..., Any]`（未知名抛 `KeyError`）；注册表模块级单例。
- `run_model(name: str, X: Any, y: Any, *, seed: int | None = None, params: dict[str, object] | None = None) -> dict[str, object]`：返回 `{model, fitted, params, seed}` 或按模型抛 `ValueError`；`seed` 注入 `random_state`/`random_seed`（若模型构造函数接受）。
- 内置注册：`linear-regression`（sklearn LinearRegression）、`decision-tree`（sklearn DecisionTreeClassifier，接受 random_state）、`kmeans`（sklearn KMeans，接受 random_state）。

- [ ] **Step 1: 写失败测试**

`toolkit/tests/models/test_registry.py`：

```python
import pytest

from cumcm_toolkit.models.registry import get_model, list_models, register_model


def test_register_and_list() -> None:
    register_model("probe-model", lambda: object())
    assert "probe-model" in list_models()
    assert get_model("probe-model") is not None


def test_unknown_model_fails_closed() -> None:
    with pytest.raises(KeyError):
        get_model("does-not-exist")


def test_builtin_models_registered() -> None:
    for name in ("linear-regression", "decision-tree", "kmeans"):
        assert name in list_models()
```

`toolkit/tests/models/test_runner.py`：

```python
import numpy as np
import pytest

from cumcm_toolkit.models.runner import run_model


def test_run_linear_regression_recovers_coefficients() -> None:
    rng = np.random.default_rng(7)
    X = rng.normal(size=(60, 2))
    y = 2.0 * X[:, 0] - 1.5 * X[:, 1] + 0.5
    result = run_model("linear-regression", X, y, seed=7)
    fitted = result["fitted"]
    coef = fitted.coef_
    assert np.allclose(coef, [2.0, -1.5], atol=0.05)
    assert result["seed"] == 7
    assert isinstance(result["params"], dict)


def test_run_unknown_model_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_model("nope", np.zeros((3, 2)), np.zeros(3))
```

- [ ] **Step 2: RED** → **Step 3: 实现**

`toolkit/src/cumcm_toolkit/models/registry.py`：

```python
from __future__ import annotations

from typing import Any, Callable

_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_model(name: str, factory: Callable[..., Any]) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("model name must be a non-empty string")
    _REGISTRY[name] = factory


def list_models() -> list[str]:
    return sorted(_REGISTRY)


def get_model(name: str) -> Callable[..., Any]:
    if name not in _REGISTRY:
        raise KeyError(f"unknown model: {name}")
    return _REGISTRY[name]


def _seed_kwargs(seed: int | None) -> dict[str, int]:
    return {"random_state": seed} if seed is not None else {}


def _register_builtins() -> None:
    from sklearn.cluster import KMeans
    from sklearn.linear_model import LinearRegression
    from sklearn.tree import DecisionTreeClassifier

    register_model("linear-regression", lambda **kw: LinearRegression())
    register_model("decision-tree", lambda **kw: DecisionTreeClassifier(**_seed_kwargs(kw.get("seed"))))
    register_model("kmeans", lambda **kw: KMeans(n_clusters=kw.get("n_clusters", 3), **_seed_kwargs(kw.get("seed"))))


_register_builtins()
```

`toolkit/src/cumcm_toolkit/models/runner.py`：

```python
from __future__ import annotations

from typing import Any

from cumcm_toolkit.models.registry import get_model


def run_model(
    name: str,
    X: Any,
    y: Any,
    *,
    seed: int | None = None,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    params = dict(params or {})
    try:
        factory = get_model(name)
        model = factory(seed=seed, **params)
    except KeyError as exc:
        raise ValueError(f"unknown model: {name}") from exc
    try:
        model.fit(X, y)
    except Exception as exc:
        raise ValueError(f"model fit failed for {name}: {exc}") from exc
    return {"model": name, "fitted": model, "params": params, "seed": seed}
```

- [ ] **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add model registry and runner`）

### Task 4: 评价指标与泄漏检测 metrics

**Files:**

- Create: `toolkit/src/cumcm_toolkit/evaluation/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/evaluation/metrics.py`
- Create: `toolkit/tests/evaluation/__init__.py`
- Create: `toolkit/tests/evaluation/test_metrics.py`

**Interfaces:**

- `regression_metrics(y_true, y_pred) -> dict[str, float]`：键 `{mse, rmse, mae, r2}`，`r2` 用 `sklearn.metrics.r2_score`，其余手算；输入长度不等抛 `ValueError`。
- `classification_metrics(y_true, y_pred, *, positive_label: str | None = None) -> dict[str, float]`：键 `{accuracy, precision, recall, f1}`（binary，positive_label 默认取正类 1/`"1"`/`"true"`）。
- `detect_improper_split(train, test, key_columns: list[str]) -> dict[str, object]`：返回 `{overlap_rows, overlapping_keys, warning}`；`key_columns` 缺列抛 `ValueError`。
- `detect_target_leakage(features: pd.DataFrame, target: pd.Series, *, tolerance: float = 1e-9) -> list[str]`：返回与目标绝对相关 `>= 1 - tolerance` 的特征列名（泄漏特征）。
- `check_data_leakage(...)` 组合上述两个检测，返回 `{improper_split, target_leakage, warnings}`。

- [ ] **Step 1: 写失败测试**（退出标准"能识别至少一个数据泄漏或错误划分反例"的测试载体）

`toolkit/tests/evaluation/test_metrics.py`：

```python
import numpy as np
import pandas as pd
import pytest

from cumcm_toolkit.evaluation.metrics import (
    check_data_leakage,
    classification_metrics,
    detect_improper_split,
    detect_target_leakage,
    regression_metrics,
)


def test_regression_metrics_values() -> None:
    y_true = np.array([1.0, 2.0, 3.0, 4.0])
    y_pred = np.array([1.0, 2.0, 3.0, 5.0])
    result = regression_metrics(y_true, y_pred)
    assert result["mse"] == pytest.approx(0.25)
    assert result["rmse"] == pytest.approx(0.5)
    assert result["mae"] == pytest.approx(0.25)
    assert result["r2"] == pytest.approx(0.9)


def test_regression_metrics_mismatched_length_fails() -> None:
    with pytest.raises(ValueError):
        regression_metrics(np.array([1.0]), np.array([1.0, 2.0]))


def test_classification_metrics_binary() -> None:
    y_true = np.array([1, 0, 1, 1, 0])
    y_pred = np.array([1, 0, 1, 0, 0])
    result = classification_metrics(y_true, y_pred)
    assert result["accuracy"] == pytest.approx(0.8)
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == pytest.approx(2 / 3)
    assert result["f1"] == pytest.approx(2 / 3)


def test_detect_improper_split_finds_overlap() -> None:
    train = pd.DataFrame({"id": [1, 2, 3], "v": [1.0, 2.0, 3.0]})
    test = pd.DataFrame({"id": [3, 4], "v": [3.0, 4.0]})
    result = detect_improper_split(train, test, ["id"])
    assert result["overlap_rows"] == 1
    assert result["overlapping_keys"] == [3]
    assert "overlap" in result["warning"].lower()


def test_detect_target_leakage_finds_perfect_column() -> None:
    target = pd.Series([1.0, 2.0, 3.0, 4.0])
    features = pd.DataFrame({"ok": [0.1, 0.2, 0.3, 0.4], "leak": target * 2})
    leaked = detect_target_leakage(features, target)
    assert leaked == ["leak"]


def test_check_data_leakage_combines_detections() -> None:
    train = pd.DataFrame({"id": [1, 2], "x": [0.1, 0.2]})
    test = pd.DataFrame({"id": [2, 3], "x": [0.2, 0.3]})
    target = pd.Series([1.0, 2.0])
    result = check_data_leakage(train, test, target, key_columns=["id"])
    assert result["improper_split"]["overlap_rows"] == 1
    assert result["target_leakage"] == []
```

- [ ] **Step 2: RED** → **Step 3: 实现**

`toolkit/src/cumcm_toolkit/evaluation/metrics.py`：

```python
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, r2_score, recall_score


def _check_lengths(y_true: Any, y_pred: Any) -> None:
    if len(y_true) != len(y_pred):
        raise ValueError(f"length mismatch: y_true {len(y_true)} vs y_pred {len(y_pred)}")


def regression_metrics(y_true: Any, y_pred: Any) -> dict[str, float]:
    _check_lengths(y_true, y_pred)
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    errors = y_true - y_pred
    mse = float(np.mean(errors**2))
    return {
        "mse": round(mse, 6),
        "rmse": round(float(np.sqrt(mse)), 6),
        "mae": round(float(np.mean(np.abs(errors))), 6),
        "r2": round(float(r2_score(y_true, y_pred)), 6),
    }


def classification_metrics(
    y_true: Any, y_pred: Any, *, positive_label: str | None = None
) -> dict[str, float]:
    _check_lengths(y_true, y_pred)
    pos = positive_label or "1"
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "precision": round(float(precision_score(y_true, y_pred, pos_label=pos, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, y_pred, pos_label=pos, zero_division=0)), 6),
        "f1": round(float(f1_score(y_true, y_pred, pos_label=pos, zero_division=0)), 6),
    }


def detect_improper_split(
    train: pd.DataFrame, test: pd.DataFrame, key_columns: list[str]
) -> dict[str, object]:
    missing = [c for c in key_columns if c not in train.columns or c not in test.columns]
    if missing:
        raise ValueError(f"key columns missing from split: {missing}")
    train_keys = train[key_columns].drop_duplicates()
    test_keys = test[key_columns].drop_duplicates()
    merged = train_keys.merge(test_keys, on=key_columns)
    overlapping = merged.sort_values(key_columns[0])[key_columns[0]].tolist()
    return {
        "overlap_rows": len(overlapping),
        "overlapping_keys": overlapping,
        "warning": f"train/test overlap on key columns: {len(overlapping)} rows" if overlapping else "",
    }


def detect_target_leakage(
    features: pd.DataFrame, target: pd.Series, *, tolerance: float = 1e-9
) -> list[str]:
    leaked = []
    for column in features.columns:
        series = features[column]
        if not pd.api.types.is_numeric_dtype(series.dtype):
            continue
        corr = float(pd.Series(series).corr(pd.Series(target)))
        if np.isnan(corr):
            continue
        if abs(corr) >= 1.0 - tolerance:
            leaked.append(str(column))
    return sorted(leaked)


def check_data_leakage(
    train: pd.DataFrame,
    test: pd.DataFrame,
    target: pd.Series,
    *,
    key_columns: list[str],
    tolerance: float = 1e-9,
) -> dict[str, object]:
    split = detect_improper_split(train, test, key_columns)
    features = train.drop(columns=[c for c in key_columns if c in train.columns], errors="ignore")
    leak = detect_target_leakage(features, target, tolerance=tolerance)
    warnings: list[str] = []
    if split["overlap_rows"]:
        warnings.append(split["warning"])
    if leak:
        warnings.append(f"target leakage in features: {leak}")
    return {"improper_split": split, "target_leakage": leak, "warnings": warnings}
```

- [ ] **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add metrics and data leakage detection`）

### Task 5: 基线比较 baselines

**Files:**

- Create: `toolkit/src/cumcm_toolkit/evaluation/baselines.py`
- Create: `toolkit/tests/evaluation/test_baselines.py`

**Interfaces:**

- `constant_baseline(y: Any, *, strategy: str = "mean") -> dict[str, object]`：`mean`/`median`/`majority`（分类用 majority，返回众数）；输出 `{strategy, value, fitted}`。
- `compare_to_baseline(y_true, y_pred, baseline_value, *, metric: str = "rmse") -> dict[str, object]`：返回 `{metric, model_score, baseline_score, improvement}`；`improvement = (baseline_score - model_score) / baseline_score`（baseline_score 为 0 时 improvement 置 `null` 并警告）。

- [ ] **Step 1: 写失败测试**

```python
import numpy as np
import pytest

from cumcm_toolkit.evaluation.baselines import compare_to_baseline, constant_baseline


def test_constant_baseline_mean_and_majority() -> None:
    assert constant_baseline(np.array([1.0, 2.0, 3.0]))["value"] == pytest.approx(2.0)
    assert constant_baseline(np.array(["a", "a", "b"]), strategy="majority")["value"] == "a"


def test_compare_improvement_positive() -> None:
    y_true = np.array([1.0, 2.0, 3.0, 4.0])
    y_pred = np.array([1.0, 2.0, 3.0, 5.0])  # rmse 0.5
    result = compare_to_baseline(y_true, y_pred, baseline_value=2.5)
    assert result["metric"] == "rmse"
    assert result["model_score"] == pytest.approx(0.5)
    assert result["improvement"] == pytest.approx(0.8)
```

- [ ] **Step 2: RED** → **Step 3: 实现**

```python
from __future__ import annotations

from typing import Any

import numpy as np

from cumcm_toolkit.evaluation.metrics import regression_metrics


def constant_baseline(y: Any, *, strategy: str = "mean") -> dict[str, object]:
    values = np.asarray(y)
    if strategy == "mean":
        value: object = float(np.mean(values))
    elif strategy == "median":
        value = float(np.median(values))
    elif strategy == "majority":
        unique, counts = np.unique(values, return_counts=True)
        value = unique[int(np.argmax(counts))]
    else:
        raise ValueError(f"unknown baseline strategy: {strategy}")
    return {"strategy": strategy, "value": value, "fitted": value}


def compare_to_baseline(
    y_true: Any, y_pred: Any, baseline_value: float, *, metric: str = "rmse"
) -> dict[str, object]:
    if metric != "rmse":
        raise ValueError(f"unsupported metric: {metric}")
    model_score = regression_metrics(y_true, y_pred)["rmse"]
    baseline_score = float(np.mean((np.asarray(y_true, dtype=float) - baseline_value) ** 2)) ** 0.5
    improvement: float | None
    if baseline_score == 0:
        improvement = None
    else:
        improvement = round((baseline_score - model_score) / baseline_score, 6)
    return {
        "metric": metric,
        "model_score": model_score,
        "baseline_score": round(baseline_score, 6),
        "improvement": improvement,
    }
```

- [ ] **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add baseline comparison`）

### Task 6: 敏感性分析 sensitivity

**Files:**

- Create: `toolkit/src/cumcm_toolkit/evaluation/sensitivity.py`
- Create: `toolkit/tests/evaluation/test_sensitivity.py`

**Interfaces:**

- `sensitivity_report(*, base_params: dict[str, float], perturb: dict[str, list[float]], evaluate: Callable[[dict[str, float]], float]) -> dict[str, object]`：对每个参数（`perturb` 中的键，若不在 base_params 则警告并跳过），对其取值列表逐点求值；返回 `{parameters:{name:{base, values, results, min, max, range}}, conclusion}`；`conclusion` 为字符串（如 `"param_x dominates (range 2.3 vs 0.1)"`，或 `"stable"`）。
- 要求：`evaluate` 抛异常时该点记 `null` 并进 warnings（fail-closed 但容忍扰动点失败），至少一个点成功才生成该参数结果，否则抛 `ValueError`。

- [ ] **Step 1: 写失败测试**

```python
import pytest

from cumcm_toolkit.evaluation.sensitivity import sensitivity_report


def test_sensitivity_range_and_conclusion() -> None:
    def evaluate(params: dict[str, float]) -> float:
        return params["a"] * 10 + params["b"]

    report = sensitivity_report(
        base_params={"a": 1.0, "b": 1.0},
        perturb={"a": [0.9, 1.0, 1.1], "b": [0.5, 1.0, 1.5]},
        evaluate=evaluate,
    )
    a = report["parameters"]["a"]
    b = report["parameters"]["b"]
    assert a["range"] == pytest.approx(2.0)
    assert b["range"] == pytest.approx(1.0)
    assert "a" in report["conclusion"]


def test_sensitivity_skips_unknown_param_with_warning() -> None:
    report = sensitivity_report(
        base_params={"a": 1.0},
        perturb={"zz": [0.0, 1.0]},
        evaluate=lambda p: p["a"],
    )
    assert "zz" not in report["parameters"]
    assert any("zz" in w for w in report["warnings"])


def test_sensitivity_fails_when_no_point_succeeds() -> None:
    def evaluate(params: dict[str, float]) -> float:
        raise RuntimeError("boom")

    with pytest.raises(ValueError):
        sensitivity_report(base_params={"a": 1.0}, perturb={"a": [1.0]}, evaluate=evaluate)
```

- [ ] **Step 2: RED** → **Step 3: 实现**

```python
from __future__ import annotations

from typing import Callable

from cumcm_toolkit.experiments.manifest import utc_now_rfc3339  # 复用 Phase 1 时间工具


def sensitivity_report(
    *,
    base_params: dict[str, float],
    perturb: dict[str, list[float]],
    evaluate: Callable[[dict[str, float]], float],
) -> dict[str, object]:
    warnings: list[str] = []
    parameters: dict[str, object] = {}
    for name, values in perturb.items():
        if name not in base_params:
            warnings.append(f"perturbed parameter not in base_params: {name}")
            continue
        results = []
        ok_points = 0
        for value in values:
            candidate = dict(base_params)
            candidate[name] = value
            try:
                results.append(round(float(evaluate(candidate)), 6))
                ok_points += 1
            except Exception as exc:  # noqa: BLE001 - tolerate single-point failures
                results.append(None)
                warnings.append(f"{name}={value}: {exc}")
        if ok_points == 0:
            raise ValueError(f"no sensitivity point succeeded for parameter {name}")
        finite = [r for r in results if r is not None]
        parameters[name] = {
            "base": round(float(base_params[name]), 6),
            "values": values,
            "results": results,
            "min": min(finite),
            "max": max(finite),
            "range": round(max(finite) - min(finite), 6),
        }
    if not parameters:
        raise ValueError("no parameters perturbed")
    ranges = {name: parameters[name]["range"] for name in parameters}
    dominant = max(ranges, key=ranges.get)
    if max(ranges.values()) <= 1e-9:
        conclusion = "stable"
    else:
        others = ", ".join(f"{k}={v}" for k, v in sorted(ranges.items()) if k != dominant)
        conclusion = f"{dominant} dominates (range {ranges[dominant]}; others {others or 'none'})"
    return {
        "parameters": parameters,
        "conclusion": conclusion,
        "generated_at": utc_now_rfc3339(),
        "warnings": warnings,
    }
```

- [ ] **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add sensitivity analysis`）

### Task 7: 结果导出 export

**Files:**

- Create: `toolkit/src/cumcm_toolkit/results/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/results/export.py`
- Create: `toolkit/tests/results/__init__.py`
- Create: `toolkit/tests/results/test_export.py`

**Interfaces:**

- `export_json(data: object, path: Path) -> Path`：严格 JSON（`allow_nan=False`），成功返回 path；失败抛 `ValueError`。
- `export_csv(rows: list[dict[str, object]], path: Path) -> Path`：列序取首个非空行的键序，空列表抛 `ValueError`。
- `export_latex_table(rows: list[dict[str, object]], path: Path, *, caption: str = "") -> Path`：生成 `booktabs` 风格 tabular（列名转义 `_`→`\_`、`%`→`\%`），空列表抛 `ValueError`。
- `save_figure(fig: Any, path: Path) -> Path`：matplotlib Agg 后端保存（`.png`），返回 path。

- [ ] **Step 1: 写失败测试**

```python
import json
from pathlib import Path

import pytest

from cumcm_toolkit.results.export import export_csv, export_json, export_latex_table


def test_export_json_roundtrip(tmp_path: Path) -> None:
    path = export_json({"a": 1, "b": [1.5, 2.5]}, tmp_path / "out.json")
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1, "b": [1.5, 2.5]}


def test_export_json_rejects_nan(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        export_json({"a": float("nan")}, tmp_path / "bad.json")


def test_export_csv_order_and_content(tmp_path: Path) -> None:
    path = export_csv([{"b": 1, "a": 2}, {"b": 3, "a": 4}], tmp_path / "out.csv")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "b,a"
    assert lines[1] == "1,2"


def test_export_latex_table_escapes(tmp_path: Path) -> None:
    path = export_latex_table(
        [{"metric": "rmse", "value": 0.5}], tmp_path / "t.tex", caption="结果"
    )
    text = path.read_text(encoding="utf-8")
    assert "metric" in text and "rmse" in text
    assert "caption" in text


def test_export_empty_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        export_csv([], tmp_path / "empty.csv")
```

- [ ] **Step 2: RED** → **Step 3: 实现**

```python
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _check_finite(value: object, where: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number in {where}: {value}")
    if isinstance(value, dict):
        for key, item in value.items():
            _check_finite(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_finite(item, f"{where}[{index}]")


def export_json(data: object, path: Path) -> Path:
    _check_finite(data, "root")
    try:
        path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False), encoding="utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cannot serialize json to {path}: {exc}") from exc
    return path


def export_csv(rows: list[dict[str, object]], path: Path) -> Path:
    if not rows:
        raise ValueError("cannot export empty rows to csv")
    columns = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _latex_escape(value: object) -> str:
    text = str(value)
    return text.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def export_latex_table(
    rows: list[dict[str, object]], path: Path, *, caption: str = ""
) -> Path:
    if not rows:
        raise ValueError("cannot export empty rows to latex table")
    columns = list(rows[0].keys())
    lines = [
        "\\begin{table}[ht]",
        "\\centering",
        f"\\caption{{{_latex_escape(caption)}}}",
        "\\begin{tabular}{" + "l" * len(columns) + "}",
        "\\toprule",
        " & ".join(_latex_escape(c) for c in columns) + r" \\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(_latex_escape(row.get(c, "")) for c in columns) + r" \\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def save_figure(fig: Any, path: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    try:
        fig.savefig(path, bbox_inches="tight")
    except Exception as exc:
        raise ValueError(f"cannot save figure to {path}: {exc}") from exc
    return path
```

- [ ] **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add result export helpers`）

### Task 8: 基础文档与结构检查

**Files:**

- Create: `shared/knowledge/foundations/<11 个文件>.md`（见 File structure）
- Create: `tests/knowledge/__init__.py`
- Create: `tests/knowledge/test_foundations_structure.py`

**Interfaces:**

- 每篇基础文档必备小节标题（Markdown 二级标题）：`## 是什么`、`## 为什么重要`、`## 常见误区`、`## 在本工作台中的用法`、`## 一句话总结`。
- 测试 `test_foundations_structure.py`：遍历 `shared/knowledge/foundations/*.md`，断言每个文件包含全部五个标题、非空、且不含未完成标记（TODO/TBD/FIXME/待定）。

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

REQUIRED = ["## 是什么", "## 为什么重要", "## 常见误区", "## 在本工作台中的用法", "## 一句话总结"]


def test_foundations_have_required_sections_and_no_markers(project_root: Path) -> None:
    import re

    foundations = sorted((project_root / "shared/knowledge/foundations").glob("*.md"))
    assert len(foundations) >= 11, "expected at least 11 foundation docs"
    markers = re.compile(r"TODO|TBD|FIXME|待定")
    for path in foundations:
        text = path.read_text(encoding="utf-8")
        for heading in REQUIRED:
            assert heading in text, f"{path.name} missing {heading}"
        assert len(text.strip()) > 200, f"{path.name} too short"
        assert not markers.search(text), f"{path.name} contains unfinished marker"
```

- [ ] **Step 2: RED** → **Step 3: 写 11 篇文档**（每篇 300–600 字，含五个小节；内容基于方法学常识，不虚构数据；文件清单与主题见 File structure，主题映射：data-types=数据类型与清洗、descriptive-stats=描述统计、probability-estimation=概率与估计、hypothesis-testing=假设检验、correlation-causation=相关与因果、overfitting=过拟合、data-leakage=数据泄漏、optimization-basics=优化基础、error-residual=误差与残差、cross-validation=交叉验证、robustness-sensitivity=稳健性与敏感性）→ **Step 4: GREEN** → **Step 5: 提交**（消息 `docs: add knowledge foundations`）

### Task 9: 模型卡模板、Schema、目录与首批卡片

**Files:**

- Create: `shared/knowledge/model-card.schema.json`
- Create: `shared/knowledge/model-card-template.md`
- Create: `shared/knowledge/model-catalog.yaml`
- Create: `shared/knowledge/model-cards/<category>/<id>.md`（首批清单见下）
- Create: `tests/knowledge/test_model_card_structure.py`

**Interfaces:**

- Schema（Draft 2020-12，`additionalProperties: false`）：`model_id`（`^[a-z][a-z0-9-]*$`）、`category`（enum: data/evaluation/prediction/optimization/classification/statistics）、`title`、`file`、`status`（enum: draft/reviewed/approved）、`priority`（integer 1-3）、`required_sections`（数组，含全部 17 个必备小节名）。卡片 Markdown 需含 YAML front-matter（`---` 包裹的上述字段）与 17 个 `##` 小节。
- 17 个必备小节（与设计文档一致）：适用问题、禁用场景、输入与假设、核心公式、直观解释、建模步骤、参数选择、工具入口、最小示例、评价指标、检验方法、对比基线、替代模型、常见误用、失效征兆、论文表达示例、对应练习。
- 首批卡片清单（Task 9 必须全部创建，每个至少 300 字正文；允许按模板内容适度精简每节 1–3 句）：
  - data: `interpolation`（插值）、`anomaly-detection`（异常检测）、`normalization`（归一化）、`dimensionality-reduction`（降维）
  - evaluation: `entropy-weight`（熵权法）、`topsis`（TOPSIS）、`ahp`（AHP）、`pca`（主成分）、`factor-analysis`（因子分析）、`grey-relational`（灰色关联）、`fuzzy-comprehensive`（模糊综合评价）
  - prediction: `linear-regression`（线性回归）、`nonlinear-regression`（非线性回归）、`exponential-smoothing`（指数平滑）、`arima`（ARIMA）、`grey-prediction`（灰色预测）、`ml-regression`（机器学习回归）
  - optimization: `linear-programming`（线性规划）、`integer-programming`（整数规划）、`nonlinear-programming`（非线性规划）、`multi-objective`（多目标优化）、`dynamic-programming`（动态规划）、`heuristic`（启发式算法）
  - classification: `logistic-regression`（逻辑回归）、`decision-tree`（决策树）、`kmeans`（K-means）、`hierarchical-clustering`（层次聚类）、`dbscan`（DBSCAN）
  - statistics: `correlation-analysis`（相关分析）、`parametric-tests`（参数检验）、`nonparametric-tests`（非参数检验）、`anova`（方差分析）、`confidence-interval`（置信区间）
  （合计 31 张卡；priority：评价/预测/优化高频卡为 1，其余 2-3。）
- `test_model_card_structure.py`：① 目录 YAML（用 yaml.safe_load）与文件系统一致（每个 catalog 条目 file 存在、model_id/file/category 与 front-matter 一致、无重复 id）；② 每张卡 front-matter 通过 Schema 校验（jsonschema）；③ 每张卡正文包含 17 个 `##` 小节标题。

- [ ] **Step 1: 写失败测试**（含 Schema 内容）

`tests/knowledge/test_model_card_structure.py`：

```python
from pathlib import Path

import jsonschema
import yaml

CARD_SCHEMA = None  # loaded from shared/knowledge/model-card.schema.json
REQUIRED_SECTIONS = [
    "适用问题", "禁用场景", "输入与假设", "核心公式", "直观解释", "建模步骤",
    "参数选择", "工具入口", "最小示例", "评价指标", "检验方法", "对比基线",
    "替代模型", "常见误用", "失效征兆", "论文表达示例", "对应练习",
]


def _load(project_root: Path) -> tuple[dict, list[dict], dict]:
    schema = __import__("json").loads(
        (project_root / "shared/knowledge/model-card.schema.json").read_text(encoding="utf-8")
    )
    catalog = yaml.safe_load((project_root / "shared/knowledge/model-catalog.yaml").read_text(encoding="utf-8"))
    cards = []
    for entry in catalog["cards"]:
        cards.append(
            {
                "entry": entry,
                "path": project_root / entry["file"],
                "text": (project_root / entry["file"]).read_text(encoding="utf-8"),
            }
        )
    return schema, cards, catalog


def _front_matter(text: str) -> dict:
    if not text.startswith("---"):
        raise AssertionError("card missing YAML front matter")
    _, body = text.split("---", 2)[1:]
    return yaml.safe_load(body)


def test_catalog_matches_filesystem_and_front_matter(project_root: Path) -> None:
    schema, cards, catalog = _load(project_root)
    ids = [entry["model_id"] for entry in catalog["cards"]]
    assert len(ids) == len(set(ids)), "duplicate model ids"
    for card in cards:
        assert card["path"].is_file(), f"missing card file: {card['entry']['file']}"
        fm = _front_matter(card["text"])
        assert fm["model_id"] == card["entry"]["model_id"]
        assert fm["category"] == card["entry"]["category"]


def test_front_matter_validates_against_schema(project_root: Path) -> None:
    schema, cards, _ = _load(project_root)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    for card in cards:
        errors = list(validator.iter_errors(_front_matter(card["text"])))
        assert not errors, f"{card['entry']['file']}: {[e.message for e in errors]}"


def test_every_card_has_all_required_sections(project_root: Path) -> None:
    _, cards, _ = _load(project_root)
    for card in cards:
        for section in REQUIRED_SECTIONS:
            assert f"## {section}" in card["text"], f"{card['entry']['file']} missing ## {section}"
        assert len(card["text"].strip()) > 300, f"{card['entry']['file']} too short"
```

- [ ] **Step 2: RED** → **Step 3: 创建 Schema、模板、目录与 31 张卡**（模板给出完整 17 节示例卡 `linear-regression`；其余卡按模板结构写，每节 1–3 句，不虚构数据；`model-catalog.yaml` 登记全部 31 张卡）→ **Step 4: GREEN + 契约回归** → **Step 5: 提交**（消息 `feat: add model card template, schema, catalog and first cards`）

### Task 10: 文献知识三件套与负例测试

**Files:**

- Create: `shared/knowledge/literature/search-strategy.md`
- Create: `shared/knowledge/literature/deduplication.md`
- Create: `shared/knowledge/literature/source-evaluation.md`
- Create: `tests/knowledge/test_literature_knowledge.py`

**Interfaces（规则契约，测试内参考实现）:**

- `deduplication.md` 必须定义三条确定性分组规则：① 相同 DOI 归一组；② 无 DOI 时按规范化标题（小写、去空格/标点/连字符）归组；③ 来源标识（URL 规范化：去片段/默认端口）归组。元数据冲突（同组内 author/year/venue 不一致）必须保持候选状态并交人工核验，不得静默合并。
- `source-evaluation.md` 必须定义：元数据完整性、全文可用性、拟支持主张、支持边界四个维度；并明确"引用量或期刊等级不得等同于来源质量或模型正确性"。
- `search-strategy.md` 必须覆盖：检索问题拆解、中英文关键词生成、后端查询参数（若可用）、候选用途（仅候选，非正式引用）。
- `test_literature_knowledge.py` 实现参考分组函数（按上述规则）并对合成样例断言：
  - 重复 DOI（两条记录同 DOI）→ 同组；
  - 规范化标题重复（"A Novel Method" vs "A  Novel  Method!"）→ 同组；
  - 标识冲突（同 DOI 但 year 不同）→ 保持候选 + 标记人工核验；
  - 仅有引用量信号（高引用但缺元数据/全文）→ 不视为高质量来源。

- [ ] **Step 1: 写失败测试**

`tests/knowledge/test_literature_knowledge.py`：

```python
import re
import unicodedata
from pathlib import Path


def _normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title.lower())
    return re.sub(r"[\W_]+", "", text)


def group_candidates(records: list[dict]) -> dict[str, list[str]]:
    """参考实现：按 DOI → 规范化标题 → 规范化 URL 的顺序形成确定性分组。"""
    groups: dict[str, list[str]] = {}
    for record in records:
        key = None
        if record.get("doi"):
            key = f"doi:{record['doi'].lower()}"
        elif record.get("title"):
            key = f"title:{_normalize_title(record['title'])}"
        elif record.get("url"):
            key = f"url:{re.sub(r'#.*$', '', record['url']).rstrip('/')}"
        if key is None:
            continue
        groups.setdefault(key, []).append(record["id"])
    return groups


def read_doc(project_root: Path, name: str) -> str:
    return (project_root / "shared" / "knowledge" / "literature" / name).read_text(encoding="utf-8")


def test_dedup_groups_by_doi() -> None:
    groups = group_candidates(
        [
            {"id": "a", "doi": "10.1000/ABC"},
            {"id": "b", "doi": "10.1000/abc"},
            {"id": "c", "doi": "10.1000/XYZ"},
        ]
    )
    assert set(groups["doi:10.1000/abc"]) == {"a", "b"}


def test_dedup_groups_by_normalized_title() -> None:
    groups = group_candidates(
        [
            {"id": "a", "title": "A Novel Method"},
            {"id": "b", "title": "A  Novel  Method!"},
            {"id": "c", "title": "A Different Method"},
        ]
    )
    assert set(groups["title:anovelmethod"]) == {"a", "b"}


def test_dedup_marks_conflicts_for_human_review() -> None:
    doc = read_doc(project_root := Path(__import__("pathlib").Path(__file__).resolve().parents[2]), "deduplication.md")
    assert "人工核验" in doc or "人工" in doc
    assert "不得静默合并" in doc or "不能静默合并" in doc


def test_source_evaluation_rejects_citation_count_as_quality() -> None:
    doc = read_doc(Path(__file__).resolve().parents[2], "source-evaluation.md")
    assert "引用量" in doc and "期刊等级" in doc
    assert "不等同" in doc or "不能等同于" in doc


def test_search_strategy_covers_candidate_usage() -> None:
    doc = read_doc(Path(__file__).resolve().parents[2], "search-strategy.md")
    for phrase in ("检索问题", "关键词", "候选", "正式引用"):
        assert phrase in doc
```

- [ ] **Step 2: RED** → **Step 3: 写三篇规则文档**（规则必须与测试参考实现一致；`deduplication.md` 含确定性分组规则与冲突保持候选条款；`source-evaluation.md` 含四维度与"引用量/期刊等级不等同质量"条款；`search-strategy.md` 覆盖检索问题/关键词/参数/候选用途）→ **Step 4: GREEN + 契约回归**（含 Phase 0A 文档漂移测试 `test_paper_integration_documentation.py`）→ **Step 5: 提交**（消息 `docs: add literature knowledge rules and negative tests`）

### Task 11: 三类代表场景端到端

**Files:**

- Create: `tests/integration/test_evaluation_scenario.py`
- Create: `tests/integration/test_prediction_scenario.py`
- Create: `tests/integration/test_optimization_scenario.py`

**Interfaces（每个场景 = 确定性合成数据 → profile → transform → 模型/计算 → metrics/泄漏检测 → sensitivity → export → 断言）:**

- 评价场景 `test_evaluation_scenario.py`：5 个方案 × 4 指标（效益型）合成数据（固定种子）；链路：`profile_csv`（断言无致命警告）→ `transform_dataframe`（minmax 归一化）→ 熵权法权重（手算/参考实现于测试内：`w_j = (1-e_j)/Σ(1-e_j)`，`e_j = -Σ p_ij ln p_ij / ln n`）→ TOPSIS 排序（测试内参考实现）→ `export_json` 到 tmp 并读回断言排序首位为已知方案；`export_latex_table` 生成表格文件存在。
- 预测场景 `test_prediction_scenario.py`：`y = 2x1 - x2 + ε`（seed 固定，σ=0.01）；链路：profile → `run_model("linear-regression", X, y, seed=7)` → `regression_metrics`（r2 ≥ 0.99）→ `compare_to_baseline`（improvement > 0.9）→ `sensitivity_report`（对样本量/正则参数扰动，evaluate 返回 r2，断言结论非空且参数范围可读）→ `export_json`。
- 优化场景 `test_optimization_scenario.py`：`min -x0 - 2x1 s.t. x0+x1 ≤ 10, x0 ≤ 6, x1 ≥ 0, x0 ≥ 0`（已知最优 x=(6,4), obj=-14）；链路：profile（约束表）→ `scipy.optimize.linprog` 求解（测试内实现或 models/runner 注册 `lp`）→ 断言 `x ≈ [6,4]`、`fun ≈ -14` → `export_json` 结果文件 → 断言读取。
- 三个场景均要求：合成数据在测试内确定性生成；断言不依赖 matplotlib 显示；每个场景至少一次 `export_json` 产物落盘并读回验证。

- [ ] **Step 1: 写失败场景测试**（三个文件，按上述链路与断言）→ **Step 2: RED**（缺模块/缺功能失败）→ **Step 3: 补齐实现**（若场景暴露 profile/transform/runner/metrics 缺陷则修复之，保持 fail-closed）→ **Step 4: GREEN + 全量回归** → **Step 5: 提交**（消息 `test: add evaluation/prediction/optimization scenarios`）

### Task 12: Phase 2 验收、主计划更新与交接

**Files:**

- Modify: `docs/superpowers/plans/2026-08-21-cumcm-workbench-implementation.md`（验证全部通过后）

**Interfaces:**

- 产出干净提交哈希与 Phase 3 规划的已验证输入；不实现任何运行时 Skill/CLI 安装。

- [ ] **Step 1: 完整验证（主计划 Phase 2 验收命令）**

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
& "E:\数学建模国赛\.venv\Scripts\python.exe" -m pytest toolkit/tests/data toolkit/tests/models toolkit/tests/evaluation toolkit/tests/results -v -p no:cacheprovider
& "E:\数学建模国赛\.venv\Scripts\python.exe" -m pytest tests/knowledge -v -p no:cacheprovider
& "E:\数学建模国赛\.venv\Scripts\python.exe" -m pytest tests/integration/test_evaluation_scenario.py tests/integration/test_prediction_scenario.py tests/integration/test_optimization_scenario.py -v -p no:cacheprovider
& "E:\数学建模国赛\.venv\Scripts\python.exe" -m pytest toolkit/tests tests/contracts tests/knowledge tests/integration -q -p no:cacheprovider
& "E:\数学建模国赛\.venv\Scripts\python.exe" scripts/validate_contracts.py
```

预期：全部通过；验证器 11 契约 0 错。

- [ ] **Step 2: 扫描标记与检查工作树**（TODO/TBD/FIXME/待定 扫描共享知识与 toolkit；`git diff --check`；`git status --short`）
- [ ] **Step 3: 更新主计划**：Program-level tracking `- [ ] 阶段 2：...` → `- [x] 阶段 2：评价、预测、优化代表场景通过，完成向阶段 3 的历史交接。`；在 Phase 2 章节末尾加 Verified inputs（2026-08-22：依赖版本、31 张卡、三类场景、文献知识三件套、11 契约不变）；同步主计划结尾"下一步是编写并审批阶段 2 详细计划"→"阶段 3"，并更新 `tests/contracts/test_paper_integration_documentation.py` 对应断言（如 `test_master_plan_marks_phase_0a_and_phase_1_complete_and_phase_2_next` 改为断言 `- [x] 阶段 2：` 与"阶段 3"新句，函数名相应更新）。
- [ ] **Step 4: 提交**（消息 `docs: mark phase 2 complete and record verified inputs`）
- [ ] **Step 5: 交接报告**：最终提交哈希；依赖版本；模型卡数量与目录路径；三类场景路径；文献知识路径；Phase 3 已验证输入（registry/runner 接口、metrics 接口、sensitivity 接口、export 接口、模型卡结构 Schema）；显式声明未实现任何运行时 Skill 或 DSH 插件。

## Completion criteria

- 每张模型卡通过结构检查（Schema + 17 小节 + 目录一致性）。
- 三类代表场景均可从数据审计运行到结果导出（测试断言通过）。
- 指标工具能识别至少一个数据泄漏或错误划分反例（`test_check_data_leakage_combines_detections` 等）。
- 敏感性输出包含扰动参数、范围、结果变化与稳定性结论所需数据（`sensitivity_report` 契约）。
- 文献检索/去重/来源评价知识齐备且负例测试通过（重复 DOI、规范化标题、标识冲突、仅引用量信号）。
- Phase 2 未实现任何运行时 Skill；`adapters/codex/skills/literature-researcher/` 不存在。
- 全部测试通过、验证器 11 契约零错误、工作树干净、主计划反映完成状态。

## 交接输入（Phase 3 规划消费）

- `profile_csv/profile_dataframe`（数据审计入口）、`transform_dataframe`（清洗步骤契约）。
- `registry.register_model/list_models/get_model`、`runner.run_model`（统一模型接口）。
- `regression_metrics/classification_metrics/check_data_leakage`（指标与泄漏检测）、`compare_to_baseline`、`sensitivity_report`。
- `export_json/export_csv/export_latex_table/save_figure`（结果导出）。
- `shared/knowledge/model-card.schema.json`、`model-catalog.yaml`、31 张卡、11 篇基础文档、文献知识三件套。
- 三类代表场景测试（评价/预测/优化）作为 Phase 3 Skill 验证的黄金场景。
- 本计划未创建 `adapters/` 下任何内容、未实现运行时 Skill、未安装 `paper-search` 或 `cumcm_*` 插件。
