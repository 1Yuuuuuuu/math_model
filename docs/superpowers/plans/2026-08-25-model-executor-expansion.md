# Multi-Executor Model Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 23 real, JSON-safe mathematical-modeling capabilities behind seven standard executors while preserving the existing `run_model(name, X, y)` interface.

**Architecture:** A `ModelSpec` registry is the single capability source. `execute(model_id, payload)` validates and dispatches model-specific payloads to family executors, then wraps their raw outputs in a formal `model-execution` contract. Existing estimator factories remain available through `run_model`, while their three models are also exposed through the new JSON-only path.

**Tech Stack:** Python 3.11, NumPy, Pandas, SciPy, scikit-learn, statsmodels, JSON Schema 2020-12, pytest.

**Spec:** `docs/superpowers/specs/2026-08-25-model-executor-expansion-design.md`

## Global Constraints

- Work only in branch `codex/model-executor-expansion` and its isolated worktree.
- Do not modify `adapters/dsh/` production files; the existing DSH migration test may remain untouched.
- Use only dependencies already locked in `uv.lock`; do not add a numerical package.
- Every production behavior starts with a failing test and a witnessed RED result.
- Public `execute()` results must survive `json.dumps(..., allow_nan=False)` and `json.loads()` without estimator objects.
- Reject empty, ragged, boolean-as-number, complex, `NaN`, and infinite numerical inputs unless an executor explicitly accepts an empty optional field.
- Do not evaluate Python code, callbacks, or string formulas.
- Keep `run_model()` behavior and current tests backward compatible.
- Keep the exact 23 new `model_id` values defined in the spec.
- Each task ends with its targeted tests green and an independent commit.

---

## File Map

| File | Responsibility |
| --- | --- |
| `shared/contracts/model-execution.schema.json` | Formal success/failure persistence envelope |
| `toolkit/src/cumcm_toolkit/models/result.py` | JSON normalization, finite-value checks, success envelope |
| `toolkit/src/cumcm_toolkit/models/specifications.py` | `ModelSpec`, registration and capability listing |
| `toolkit/src/cumcm_toolkit/models/execution.py` | Public `execute(model_id, payload)` dispatcher |
| `toolkit/src/cumcm_toolkit/models/executors/base.py` | Shared array, payload and parameter validation |
| `toolkit/src/cumcm_toolkit/models/executors/evaluation.py` | TOPSIS, entropy weight, AHP, grey relational analysis |
| `toolkit/src/cumcm_toolkit/models/executors/expression.py` | Bounded declarative nonlinear expression evaluator |
| `toolkit/src/cumcm_toolkit/models/executors/optimization.py` | LP, MILP and nonlinear programming |
| `toolkit/src/cumcm_toolkit/models/executors/forecasting.py` | GM(1,1), ARIMA, exponential smoothing, nonlinear regression |
| `toolkit/src/cumcm_toolkit/models/executors/data_processing.py` | Normalization, interpolation, anomaly detection, PCA |
| `toolkit/src/cumcm_toolkit/models/executors/statistics.py` | Correlation, confidence intervals, tests and ANOVA |
| `toolkit/src/cumcm_toolkit/models/executors/supervised.py` | Linear regression, decision tree, logistic regression JSON results |
| `toolkit/src/cumcm_toolkit/models/executors/clustering.py` | KMeans, DBSCAN and hierarchical clustering JSON results |
| `adapters/codex/routing.py` | Capability-derived execute/plan-only decision |
| `adapters/codex/skills/solver/resources.json` | Self-contained packaged runtime closure |

All executor functions consume `Mapping[str, object]` and produce this internal raw structure:

```python
{
    "parameters": dict[str, object],
    "input_summary": dict[str, object],
    "result": dict[str, object],
    "diagnostics": dict[str, object],
    "warnings": list[str],
    "seed": int | None,
}
```

`result.py` alone adds schema version, status, model identity, executor identity and reproducibility fields.

---

### Task 1: Formal model-execution contract and result normalization

**Files:**
- Create: `shared/contracts/model-execution.schema.json`
- Create: `shared/fixtures/contracts/valid/model-execution.json`
- Create: `shared/fixtures/contracts/invalid/model-execution-missing-result.json`
- Create: `shared/fixtures/contracts/invalid/model-execution-failed-with-result.json`
- Modify: `shared/contracts/catalog.json`
- Modify: `docs/architecture/contracts.md`
- Create: `toolkit/src/cumcm_toolkit/models/result.py`
- Create: `toolkit/tests/models/test_result.py`
- Modify: `tests/contracts/test_catalog.py`
- Modify: `tests/contracts/test_contract_examples.py`

**Interfaces:**
- Produces: `normalize_json(value: object, field: str) -> object`
- Produces: `build_success_result(model_id: str, executor: str, raw: Mapping[str, object], *, deterministic: bool) -> dict[str, object]`

- [ ] **Step 1: Write failing contract and result tests**

```python
def test_success_result_is_finite_json_and_contract_valid(project_root):
    raw = {
        "parameters": {}, "input_summary": {"rows": 2},
        "result": {"scores": np.array([0.25, 0.75])},
        "diagnostics": {}, "warnings": [], "seed": None,
    }
    result = build_success_result("topsis", "evaluation", raw, deterministic=True)
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    assert result["result"]["scores"] == [0.25, 0.75]
    make_validator(load_json(project_root / "shared/contracts/model-execution.schema.json")).validate(result)

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), np.float64("-inf")])
def test_result_rejects_nonfinite_values(bad):
    with pytest.raises(ValueError, match="finite"):
        normalize_json({"value": bad}, "result")

def test_result_rejects_estimator_objects():
    with pytest.raises(ValueError, match="JSON"):
        normalize_json({"model": LinearRegression()}, "result")
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `python -m pytest toolkit/tests/models/test_result.py tests/contracts/test_catalog.py -v`

Expected: collection fails because `cumcm_toolkit.models.result` and the new schema do not exist.

- [ ] **Step 3: Add the schema and fixtures**

Define a success branch requiring exactly `schema_version`, `status`, `model_id`, `executor`, `parameters`, `input_summary`, `result`, `diagnostics`, `warnings`, and `reproducibility`. Set `status` to `succeeded`, executor to the seven approved values, IDs to the repository identifier convention, warnings to unique strings, and reproducibility to `{seed, deterministic}`. Add a failure persistence branch that forbids `result`; public `execute()` will not emit it.

Register the contract as catalog item 16 and update the contract count and documentation row. Add named invalid expectations: a succeeded envelope without `result` fails its required-field branch; failed-with-result fails its conditional Schema branch. Keep actual `NaN`/infinity coverage in `test_result.py`, because those tokens are not valid strict JSON fixture data.

- [ ] **Step 4: Implement strict JSON normalization and success wrapping**

```python
def normalize_json(value: object, field: str) -> object:
    if isinstance(value, np.ndarray):
        return normalize_json(value.tolist(), field)
    if isinstance(value, np.generic):
        return normalize_json(value.item(), field)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field} must contain only finite numbers")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError(f"{field} must use string keys")
        return {key: normalize_json(item, f"{field}.{key}") for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_json(item, field) for item in value]
    raise ValueError(f"{field} contains a non-JSON value: {type(value).__name__}")
```

Make `build_success_result` sort and deduplicate warnings, normalize the entire envelope, validate it against the new Schema using the existing offline validator, and return a deep JSON copy.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest toolkit/tests/models/test_result.py tests/contracts -q -p no:cacheprovider`

Commit: `feat: define model execution result contract`

---

### Task 2: Shared payload validators, ModelSpec registry and dispatcher

**Files:**
- Create: `toolkit/src/cumcm_toolkit/models/executors/__init__.py`
- Create: `toolkit/src/cumcm_toolkit/models/executors/base.py`
- Create: `toolkit/src/cumcm_toolkit/models/specifications.py`
- Create: `toolkit/src/cumcm_toolkit/models/execution.py`
- Modify: `toolkit/src/cumcm_toolkit/models/__init__.py`
- Create: `toolkit/tests/models/test_specifications.py`
- Create: `toolkit/tests/models/test_execution.py`

**Interfaces:**
- Produces: `numeric_array(payload, field, *, ndim=None, min_size=1) -> np.ndarray`
- Produces: `required_mapping(payload, field) -> Mapping[str, object]`
- Produces: frozen `ModelSpec(model_id, executor, knowledge_card, deterministic, seed_supported, payload_fields, function)`
- Produces: `CapabilityRegistry`, module-level `register_spec(spec)`, `get_spec(model_id)`, `list_capabilities()` and `execute(model_id, payload)`

- [ ] **Step 1: Write failing validator and registry tests**

```python
@pytest.mark.parametrize("bad", [[], [[1, 2], [3]], [True, False], [1, np.nan], [1 + 2j]])
def test_numeric_array_rejects_unsafe_inputs(bad):
    with pytest.raises(ValueError):
        numeric_array({"x": bad}, "x", ndim=1 if bad != [[1, 2], [3]] else 2)

def test_registry_rejects_missing_knowledge_card(tmp_path):
    registry = CapabilityRegistry(repository_root=tmp_path)
    spec = ModelSpec("probe-model", "statistics", "missing.md", True, False, ("x",), lambda p: {})
    with pytest.raises(ValueError, match="knowledge card"):
        registry.register(spec)

def test_registry_rejects_duplicate_model_id(project_root):
    registry = CapabilityRegistry(repository_root=project_root)
    spec = ModelSpec("probe-model", "statistics", "shared/knowledge/model-cards/statistics/anova.md", True, False, ("x",), lambda p: RAW)
    registry.register(spec)
    with pytest.raises(ValueError, match="duplicate model_id"):
        registry.register(spec)

def test_execute_routes_and_wraps_json(monkeypatch, project_root):
    registry = CapabilityRegistry(repository_root=project_root)
    registry.register(ModelSpec("probe-model", "statistics", "shared/knowledge/model-cards/statistics/anova.md", True, False, ("x",), lambda p: RAW))
    monkeypatch.setattr(execution, "get_spec", registry.get)
    result = execute("probe-model", {"x": [1, 2]})
    assert result["model_id"] == "probe-model"
    assert result["executor"] == "statistics"
```

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest toolkit/tests/models/test_specifications.py toolkit/tests/models/test_execution.py -v`

Expected: missing modules and interfaces.

- [ ] **Step 3: Implement base validators**

Use `np.asarray(value)` only after rejecting strings and mappings. Require numeric dtype excluding `bool` and complex; require exact ndim when specified; reject empty/ragged and nonfinite arrays. Add helpers for required fields, finite floats, bounded integers, string enums and seed/random-state conflicts.

- [ ] **Step 4: Implement the registry and dispatcher**

```python
@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    executor: str
    knowledge_card: str
    deterministic: bool
    seed_supported: bool
    payload_fields: tuple[str, ...]
    function: Callable[[Mapping[str, object]], Mapping[str, object]]

class CapabilityRegistry:
    def __init__(self, *, repository_root: Path) -> None:
        self._repository_root = repository_root
        self._specs: dict[str, ModelSpec] = {}

    def register(self, spec: ModelSpec) -> None:
        if spec.model_id in self._specs:
            raise ValueError(f"duplicate model_id: {spec.model_id}")
        if not (self._repository_root / spec.knowledge_card).is_file():
            raise ValueError(f"knowledge card does not exist: {spec.knowledge_card}")
        self._specs[spec.model_id] = spec

    def get(self, model_id: str) -> ModelSpec:
        try:
            return self._specs[model_id]
        except KeyError as exc:
            raise KeyError(f"unknown model_id: {model_id}") from exc

def execute(model_id: str, payload: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    spec = get_spec(model_id)
    missing = [field for field in spec.payload_fields if field not in payload]
    if missing:
        raise ValueError(f"{model_id}: missing payload fields: {', '.join(missing)}")
    raw = spec.function(copy.deepcopy(dict(payload)))
    return build_success_result(model_id, spec.executor, raw, deterministic=spec.deterministic)
```

Do not catch `KeyboardInterrupt`, `SystemExit`, or arbitrary `BaseException`. Wrap expected numerical/library exceptions as `ValueError` with model ID and execution stage.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest toolkit/tests/models/test_specifications.py toolkit/tests/models/test_execution.py -q -p no:cacheprovider`

Commit: `feat: add model capability registry and dispatcher`

---

### Task 3: TOPSIS and entropy-weight execution

**Files:**
- Create: `toolkit/src/cumcm_toolkit/models/executors/evaluation.py`
- Create: `toolkit/tests/models/test_evaluation_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_topsis(payload)` and `execute_entropy_weight(payload)` raw results
- Registers: `topsis`, `entropy-weight`

- [ ] **Step 1: Write failing known-answer tests**

```python
def test_topsis_known_two_alternative_order():
    result = execute("topsis", {
        "matrix": [[90, 10], [70, 30]],
        "criteria": ["benefit", "cost"],
        "weights": [0.5, 0.5],
    })
    assert result["result"]["ranking"] == [0, 1]
    assert result["result"]["closeness"][0] == pytest.approx(1.0)

def test_entropy_weight_prefers_varying_column():
    result = execute("entropy-weight", {
        "matrix": [[1, 5], [2, 5], [4, 5]], "criteria": ["benefit", "benefit"]
    })
    assert result["result"]["weights"] == pytest.approx([1.0, 0.0])
    assert "zero information" in " ".join(result["warnings"])
```

Add failures for negative weights, weight sum drift, zero-norm TOPSIS columns, invalid criteria, and all-zero entropy information.

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest toolkit/tests/models/test_evaluation_executor.py -v`

Expected: unknown models.

- [ ] **Step 3: Implement both algorithms**

For TOPSIS, orient cost criteria by swapping ideal maxima/minima after weighted vector normalization. Compute distances and define closeness as `d_minus / (d_plus + d_minus)`; reject a zero denominator. Rank with `np.lexsort((original_index, -closeness))`.

For entropy weights, min-max orient each column, compute proportions with zero entries contributing zero to `p*log(p)`, use `k=1/log(n)`, and normalize positive divergence coefficients. Mark constant columns with zero weight.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest toolkit/tests/models/test_evaluation_executor.py -q -p no:cacheprovider`

Commit: `feat: add TOPSIS and entropy weight execution`

---

### Task 4: AHP and grey relational analysis

**Files:**
- Modify: `toolkit/src/cumcm_toolkit/models/executors/evaluation.py`
- Modify: `toolkit/tests/models/test_evaluation_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_ahp(payload)` and `execute_grey_relational(payload)`
- Registers: `ahp`, `grey-relational-analysis`

- [ ] **Step 1: Write failing behavioral tests**

```python
def test_ahp_consistent_matrix_returns_expected_weights():
    matrix = [[1, 2, 4], [0.5, 1, 2], [0.25, 0.5, 1]]
    result = execute("ahp", {"pairwise_matrix": matrix})
    assert result["result"]["weights"] == pytest.approx([4/7, 2/7, 1/7], abs=1e-6)
    assert result["diagnostics"]["consistent"] is True

def test_grey_relational_identical_series_ranks_first():
    result = execute("grey-relational-analysis", {
        "reference": [1, 2, 3], "comparatives": [[1, 2, 3], [3, 2, 1]], "rho": 0.5
    })
    assert result["result"]["grades"][0] == pytest.approx(1.0)
    assert result["result"]["ranking"][0] == 0
```

Add reciprocity, positive-entry, dimension, `rho`, equal-length and RI-size failures. Test a CR > 0.1 result succeeds with `consistent: false`.

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest toolkit/tests/models/test_evaluation_executor.py -v`

Expected: two unknown model IDs.

- [ ] **Step 3: Implement AHP and grey relations**

Use the principal real eigenpair, normalize the positive eigenvector, compute `CI=(lambda_max-n)/(n-1)`, and the fixed Saaty RI values for n=1..15. For grey relations, normalize by the requested `initial`, `mean`, or `range` method, compute absolute differences, and apply `(delta_min + rho*delta_max)/(delta + rho*delta_max)`.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_evaluation_executor.py -q -p no:cacheprovider`

Commit: `feat: add AHP and grey relational execution`

---

### Task 5: Linear and mixed-integer programming

**Files:**
- Create: `toolkit/src/cumcm_toolkit/models/executors/optimization.py`
- Create: `toolkit/tests/models/test_optimization_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_linear_programming(payload)` and `execute_integer_programming(payload)`
- Registers: `linear-programming`, `integer-programming`

- [ ] **Step 1: Write failing exact-solution tests**

```python
def test_linear_programming_known_optimum():
    result = execute("linear-programming", {
        "objective": [3, 2], "sense": "maximize",
        "bounds": [[0, None], [0, None]],
        "inequality": {"matrix": [[1, 1], [1, 0], [0, 1]], "upper": [4, 2, 3]},
    })
    assert result["result"]["solution"] == pytest.approx([2, 2])
    assert result["result"]["objective"] == pytest.approx(10)

def test_integer_programming_does_not_round_continuous_solution():
    result = execute("integer-programming", {
        "objective": [1], "sense": "maximize", "bounds": [[0, 2.7]], "integrality": [1]
    })
    assert result["result"]["solution"] == pytest.approx([2])
```

Add dimension, invalid integrality, infeasible and unbounded tests.

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest toolkit/tests/models/test_optimization_executor.py -v`

- [ ] **Step 3: Implement SciPy adapters**

Translate maximize to a negated objective and translate the returned objective back. Normalize bounds from `[lower, upper]`, preserving JSON `null` as unbounded. For `milp`, construct `LinearConstraint` and `Bounds` without rounding outputs. Accept only solver `success=True` and finite solution/objective; include residuals, message and status in diagnostics.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_optimization_executor.py -q -p no:cacheprovider`

Commit: `feat: add linear and integer programming execution`

---

### Task 6: Safe nonlinear programming

**Files:**
- Create: `toolkit/src/cumcm_toolkit/models/executors/expression.py`
- Modify: `toolkit/src/cumcm_toolkit/models/executors/optimization.py`
- Create: `toolkit/tests/models/test_expression.py`
- Modify: `toolkit/tests/models/test_optimization_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `compile_expression(node, *, variable_count) -> Callable[[np.ndarray], float]`
- Produces: `execute_nonlinear_programming(payload)`
- Registers: `nonlinear-programming`

- [ ] **Step 1: Write failing expression safety tests**

```python
def test_expression_tree_evaluates_quadratic():
    fn = compile_expression({"op": "power", "args": [
        {"op": "variable", "index": 0},
        {"op": "constant", "value": 2},
    ]}, variable_count=1)
    assert fn(np.array([3.0])) == pytest.approx(9.0)

@pytest.mark.parametrize("node", [
    {"op": "python", "code": "import os"},
    {"op": "power", "args": [
        {"op": "variable", "index": 0},
        {"op": "constant", "value": 99},
    ]},
    {"op": "variable", "index": 4},
])
def test_expression_tree_rejects_unapproved_operations(node):
    with pytest.raises(ValueError):
        compile_expression(node, variable_count=1)
```

Add hard-limit tests for depth 17, more than 256 nodes, division by zero and log/sqrt domain errors.

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest toolkit/tests/models/test_expression.py -v`

- [ ] **Step 3: Implement the bounded expression compiler**

Use recursive construction without `eval`, `exec`, `ast.parse`, imports or callbacks. Every node is an object; constants use `{"op": "constant", "value": number}` and bare numeric children are rejected. Approve only the spec operations, integer constant powers -8..8, tree depth <=16 and node count <=256. Each returned function converts its result to finite float or raises `ValueError`.

- [ ] **Step 4: Write RED nonlinear optimizer test**

```python
def test_nonlinear_programming_minimizes_quadratic():
    result = execute("nonlinear-programming", {
        "objective": {"op": "power", "args": [
            {"op": "subtract", "args": [
                {"op": "variable", "index": 0},
                {"op": "constant", "value": 3},
            ]},
            {"op": "constant", "value": 2},
        ]},
        "initial": [0], "bounds": [[-10, 10]], "sense": "minimize", "constraints": []
    })
    assert result["result"]["solution"] == pytest.approx([3], abs=1e-5)
```

- [ ] **Step 5: Implement constrained SciPy minimize adapter**

Compile objective and constraint expression trees once. Convert equality to zero residual and interval inequality to lower/upper SciPy constraints. Require finite initial values, matching bounds, successful convergence and finite output. Return iteration/evaluation counts and solver message.

- [ ] **Step 6: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_expression.py toolkit/tests/models/test_optimization_executor.py -q -p no:cacheprovider`

Commit: `feat: add safe nonlinear programming execution`

---

### Task 7: Normalization, interpolation and anomaly detection

**Files:**
- Create: `toolkit/src/cumcm_toolkit/models/executors/data_processing.py`
- Create: `toolkit/tests/models/test_data_processing_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_normalization`, `execute_interpolation`, `execute_anomaly_detection`
- Registers: `normalization`, `interpolation`, `anomaly-detection`

- [ ] **Step 1: Write failing behavior tests**

```python
def test_zscore_normalization_records_parameters():
    result = execute("normalization", {"matrix": [[1, 10], [3, 10]], "method": "zscore"})
    assert result["result"]["transformed"] == pytest.approx([[-1, 0], [1, 0]])
    assert "constant column" in " ".join(result["warnings"])

def test_pchip_interpolation_marks_explicit_extrapolation():
    result = execute("interpolation", {
        "x": [0, 1, 2], "y": [0, 1, 4], "new_x": [-1, 1.5],
        "method": "pchip", "extrapolation": "allow"
    })
    assert result["result"]["extrapolated"] == [True, False]

def test_iqr_anomaly_detection_finds_outlier():
    result = execute("anomaly-detection", {"matrix": [[1], [1], [1], [10]], "method": "iqr"})
    assert result["result"]["anomaly_indices"] == [3]
```

Add robust/minmax normalization, duplicate x, default extrapolation rejection, z-score zero scale, Isolation Forest same-seed, and invalid method tests.

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest toolkit/tests/models/test_data_processing_executor.py -v`

- [ ] **Step 3: Implement the three data operations**

Use NumPy for normalization, SciPy `interp1d`/`PchipInterpolator` for interpolation, and scikit-learn IsolationForest. Require explicit `missing_policy` of `reject`, `drop-rows`, or `column-mean`; record affected rows. Keep IQR/Z-score threshold fields separate from Isolation Forest contamination/seed fields.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_data_processing_executor.py -q -p no:cacheprovider`

Commit: `feat: add data processing model execution`

---

### Task 8: PCA execution

**Files:**
- Modify: `toolkit/src/cumcm_toolkit/models/executors/data_processing.py`
- Modify: `toolkit/tests/models/test_data_processing_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_pca(payload)`
- Registers: `pca`

- [ ] **Step 1: Write failing PCA tests**

```python
def test_pca_returns_variance_loadings_and_scores():
    result = execute("pca", {"matrix": [[1, 2], [2, 4], [3, 6]], "components": 1, "standardize": True})
    assert len(result["result"]["transformed"][0]) == 1
    assert result["result"]["explained_variance_ratio"][0] == pytest.approx(1.0)
    assert len(result["result"]["loadings"]) == 1
```

Add component count, constant standardized column and nonfinite failures.

- [ ] **Step 2: Confirm RED, implement and verify GREEN**

Use StandardScaler only when requested, then sklearn PCA. Emit transformed scores, components/loadings, explained variance, ratio, cumulative ratio, mean and standardization parameters.

Run: `python -m pytest toolkit/tests/models/test_data_processing_executor.py -q -p no:cacheprovider`

- [ ] **Step 3: Commit**

Commit: `feat: add PCA execution`

---

### Task 9: Correlation and confidence intervals

**Files:**
- Create: `toolkit/src/cumcm_toolkit/models/executors/statistics.py`
- Create: `toolkit/tests/models/test_statistics_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_correlation(payload)`, `execute_confidence_interval(payload)`
- Registers: `correlation-analysis`, `confidence-interval`

- [ ] **Step 1: Write failing statistical known-answer tests**

```python
def test_pearson_perfect_relationship():
    result = execute("correlation-analysis", {"x": [1, 2, 3], "y": [2, 4, 6], "method": "pearson"})
    assert result["result"]["coefficient"] == pytest.approx(1.0)
    assert result["result"]["sample_size"] == 3

def test_mean_t_interval_matches_scipy():
    result = execute("confidence-interval", {"method": "mean-t", "sample": [1, 2, 3, 4], "confidence": 0.95})
    assert result["result"]["estimate"] == pytest.approx(2.5)
    assert result["result"]["lower"] < 2.5 < result["result"]["upper"]

def test_wilson_interval_stays_in_probability_bounds():
    result = execute("confidence-interval", {"method": "proportion-wilson", "successes": 0, "total": 10, "confidence": 0.95})
    assert 0 <= result["result"]["lower"] <= result["result"]["upper"] <= 1
```

Add Pearson/Spearman/Kendall matrix mode, constant input, confidence bounds and invalid successes tests.

- [ ] **Step 2: Confirm RED and implement**

Use SciPy correlation functions with pairwise finite masks only when `missing_policy="pairwise"`; default rejects missing input. Omit an uncomputable coefficient and add a structured diagnostic reason rather than returning `NaN`. Compute mean t intervals with sample standard deviation `ddof=1`, and Wilson intervals from the closed formula.

- [ ] **Step 3: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_statistics_executor.py -q -p no:cacheprovider`

Commit: `feat: add correlation and confidence interval execution`

---

### Task 10: Parametric and nonparametric hypothesis tests

**Files:**
- Modify: `toolkit/src/cumcm_toolkit/models/executors/statistics.py`
- Modify: `toolkit/tests/models/test_statistics_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_parametric_test(payload)`, `execute_nonparametric_test(payload)`
- Registers: `parametric-test`, `nonparametric-test`

- [ ] **Step 1: Write RED tests for every approved method**

```python
@pytest.mark.parametrize("test,payload", [
    ("one-sample-t", {"sample": [2, 3, 4], "population_mean": 0}),
    ("independent-t", {"sample_a": [1, 2, 3], "sample_b": [4, 5, 6], "equal_variance": False}),
    ("paired-t", {"sample_a": [1, 2, 3], "sample_b": [1, 2, 4]}),
])
def test_parametric_methods_return_statistic_p_and_effect(test, payload):
    result = execute("parametric-test", {"test": test, **payload})
    assert {"statistic", "p_value", "effect_size"} <= result["result"].keys()

@pytest.mark.parametrize("test,payload", [
    ("mann-whitney-u", {"sample_a": [1, 2], "sample_b": [3, 4]}),
    ("wilcoxon", {"sample_a": [1, 2, 3], "sample_b": [1, 2, 4]}),
    ("kruskal-wallis", {"groups": [[1, 2], [3, 4], [5, 6]]}),
    ("chi-square", {"table": [[10, 20], [20, 10]]}),
])
def test_nonparametric_methods_return_finite_results(test, payload):
    result = execute("nonparametric-test", {"test": test, **payload})
    assert math.isfinite(result["result"]["statistic"])
    assert math.isfinite(result["result"]["p_value"])
```

Add paired length mismatch, all-zero Wilcoxon differences, insufficient groups, invalid alternative and low chi-square expected frequency tests.

- [ ] **Step 2: Confirm RED and implement the adapters**

Use SciPy `ttest_1samp`, `ttest_ind`, `ttest_rel`, `mannwhitneyu`, `wilcoxon`, `kruskal`, and `chi2_contingency`. Compute Cohen's d for t tests, rank-biserial effect where well-defined, and include expected counts plus a warning when any expected count is below 5.

- [ ] **Step 3: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_statistics_executor.py -q -p no:cacheprovider`

Commit: `feat: add hypothesis test execution`

---

### Task 11: One-way ANOVA

**Files:**
- Modify: `toolkit/src/cumcm_toolkit/models/executors/statistics.py`
- Modify: `toolkit/tests/models/test_statistics_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_anova(payload)`
- Registers: `anova`

- [ ] **Step 1: Write failing ANOVA decomposition test**

```python
def test_anova_returns_complete_decomposition():
    result = execute("anova", {"groups": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]})
    out = result["result"]
    assert out["df_between"] == 2
    assert out["df_within"] == 6
    assert out["ss_total"] == pytest.approx(out["ss_between"] + out["ss_within"])
    assert 0 <= out["eta_squared"] <= 1
```

Add fewer-than-two-groups, empty group, zero total variance and insufficient degrees-of-freedom failures.

- [ ] **Step 2: Confirm RED and implement direct sums-of-squares calculation**

Compute group/grand means, SS between/within/total, degrees of freedom, mean squares, F, SciPy F survival p-value and eta-squared. Cross-check F and p against `scipy.stats.f_oneway` in the test.

- [ ] **Step 3: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_statistics_executor.py -q -p no:cacheprovider`

Commit: `feat: add ANOVA execution`

---

### Task 12: GM(1,1) and nonlinear regression

**Files:**
- Create: `toolkit/src/cumcm_toolkit/models/executors/forecasting.py`
- Create: `toolkit/tests/models/test_forecasting_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_gm11(payload)`, `execute_nonlinear_regression(payload)`
- Registers: `grey-prediction-gm11`, `nonlinear-regression`

- [ ] **Step 1: Write failing GM(1,1) tests**

```python
def test_gm11_returns_fitted_forecast_and_accuracy_diagnostics():
    result = execute("grey-prediction-gm11", {"series": [2.874, 3.278, 3.795, 4.435, 5.199], "forecast_steps": 2})
    assert len(result["result"]["fitted"]) == 5
    assert len(result["result"]["forecast"]) == 2
    assert {"posterior_ratio_c", "small_error_probability_p"} <= result["diagnostics"]
```

Add nonpositive series, fewer than four samples, constant residual variance and level-ratio warning tests.

- [ ] **Step 2: Confirm RED and implement GM(1,1)**

Build AGO `x1`, background sequence `z1`, least-squares coefficients `[a,b]`, time response, restored fitted series, residuals and future forecast. Guard `a` near zero with its limit form. Compute C and P only when the original variance is positive; otherwise provide a diagnostic reason without nonfinite values.

- [ ] **Step 3: Write failing fixed-family nonlinear regression tests**

```python
@pytest.mark.parametrize("family", ["polynomial", "exponential", "power", "logistic"])
def test_nonlinear_regression_fixed_families_are_json_safe(family, nonlinear_case):
    result = execute("nonlinear-regression", {"family": family, **nonlinear_case[family]})
    assert result["result"]["family"] == family
    assert math.isfinite(result["result"]["rmse"])

def test_nonlinear_regression_rejects_formula_or_callback():
    with pytest.raises(ValueError):
        execute("nonlinear-regression", {"family": "custom", "formula": "__import__('os')", "x": [1,2], "y": [1,2]})
```

- [ ] **Step 4: Implement fixed curve families**

Use `np.polyfit` for polynomial degrees 1–5 and SciPy `curve_fit` for exponential `a*exp(b*x)+c`, power `a*x**b+c`, and logistic `L/(1+exp(-k*(x-x0)))`. Enforce domain rules and exact initial-parameter lengths. Emit parameters by stable names, fitted/predicted arrays, RMSE, MAE and R².

- [ ] **Step 5: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_forecasting_executor.py -q -p no:cacheprovider`

Commit: `feat: add grey and nonlinear forecast execution`

---

### Task 13: ARIMA and exponential smoothing

**Files:**
- Modify: `toolkit/src/cumcm_toolkit/models/executors/forecasting.py`
- Modify: `toolkit/tests/models/test_forecasting_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Produces: `execute_arima(payload)`, `execute_exponential_smoothing(payload)`
- Registers: `arima`, `exponential-smoothing`

- [ ] **Step 1: Write failing deterministic forecast tests**

```python
def test_arima_returns_forecast_interval_and_information_criteria():
    series = [10 + 0.5*i for i in range(30)]
    result = execute("arima", {"series": series, "order": [1, 1, 0], "forecast_steps": 3})
    assert len(result["result"]["forecast"]) == 3
    assert len(result["result"]["confidence_interval"]) == 3
    assert math.isfinite(result["diagnostics"]["aic"])

def test_exponential_smoothing_requires_two_seasons():
    with pytest.raises(ValueError, match="two complete"):
        execute("exponential-smoothing", {"series": list(range(10)), "forecast_steps": 2, "seasonal": "add", "seasonal_periods": 6})
```

Add invalid ARIMA order, insufficient sample, invalid trend/seasonal, failed fit, and no-nonfinite-output tests.

- [ ] **Step 2: Confirm RED and implement statsmodels adapters**

Use `statsmodels.tsa.arima.model.ARIMA` and `statsmodels.tsa.holtwinters.ExponentialSmoothing`. Suppress only documented convergence warnings inside `warnings.catch_warnings(record=True)` and copy their text into the result warning list. Never blanket-suppress warnings. Return fitted series, forecast, confidence interval where available, parameters, AIC/BIC or SSE, and residual summaries.

- [ ] **Step 3: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_forecasting_executor.py -q -p no:cacheprovider`

Commit: `feat: add ARIMA and exponential smoothing execution`

---

### Task 14: Supervised learning JSON executor and legacy compatibility

**Files:**
- Create: `toolkit/src/cumcm_toolkit/models/executors/supervised.py`
- Create: `toolkit/tests/models/test_supervised_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`
- Preserve: `toolkit/src/cumcm_toolkit/models/runner.py`
- Preserve: `toolkit/src/cumcm_toolkit/models/registry.py`

**Interfaces:**
- Produces JSON paths for `linear-regression`, `decision-tree`, `logistic-regression`
- Keeps old `run_model()` return structure unchanged

- [ ] **Step 1: Write failing JSON execution and compatibility tests**

```python
def test_logistic_regression_returns_probabilities_without_estimator():
    result = execute("logistic-regression", {"X": [[0], [1], [2], [3]], "y": [0, 0, 1, 1], "predict_X": [[1.5]], "seed": 7})
    assert len(result["result"]["probabilities"][0]) == 2
    assert "fitted" not in result["result"]

def test_existing_linear_model_new_and_old_interfaces_coexist():
    legacy = run_model("linear-regression", [[1], [2], [3]], [3, 5, 7])
    modern = execute("linear-regression", {"X": [[1], [2], [3]], "y": [3, 5, 7], "predict_X": [[4]]})
    assert hasattr(legacy["fitted"], "predict")
    assert modern["result"]["predictions"] == pytest.approx([9])
```

Add class-count, X/y length, prediction feature width, seed conflict and unsupported parameter failures.

- [ ] **Step 2: Confirm RED and implement wrappers**

Construct sklearn estimators with the same factories/parameter semantics as the legacy registry. Return coefficients/importances/tree depth/classes, training predictions, optional prediction outputs, and applicable metrics. For classification, return labels, class probabilities and accuracy; never serialize estimator internals wholesale.

- [ ] **Step 3: Verify compatibility and commit**

Run: `python -m pytest toolkit/tests/models/test_supervised_executor.py toolkit/tests/models/test_runner.py toolkit/tests/models/test_registry.py -q -p no:cacheprovider`

Commit: `feat: add supervised model JSON execution`

---

### Task 15: Clustering executor

**Files:**
- Create: `toolkit/src/cumcm_toolkit/models/executors/clustering.py`
- Create: `toolkit/tests/models/test_clustering_executor.py`
- Modify: `toolkit/src/cumcm_toolkit/models/specifications.py`

**Interfaces:**
- Registers: `kmeans`, `dbscan`, `hierarchical-clustering`

- [ ] **Step 1: Write failing clustering tests**

```python
def test_dbscan_reports_clusters_and_noise():
    result = execute("dbscan", {"X": [[0,0], [0,0.1], [10,10]], "params": {"eps": 0.3, "min_samples": 2}, "standardized": False})
    assert result["result"]["cluster_count"] == 1
    assert result["result"]["noise_count"] == 1
    assert "scale" in " ".join(result["warnings"]).lower()

def test_hierarchical_returns_linkage_and_labels():
    result = execute("hierarchical-clustering", {"X": [[0], [0.1], [5], [5.1]], "params": {"n_clusters": 2, "linkage": "ward"}, "standardized": True})
    assert sorted(set(result["result"]["labels"])) == [0, 1]
    assert len(result["result"]["linkage_matrix"]) == 3
```

Add mutually exclusive cluster count/distance threshold, invalid DBSCAN parameters, KMeans same-seed and feature-dimension failures.

- [ ] **Step 2: Confirm RED and implement**

Use sklearn KMeans/DBSCAN/AgglomerativeClustering for labels and SciPy `linkage` for the hierarchical merge matrix with matching method/metric restrictions. Canonicalize arbitrary cluster labels to first-occurrence integers for deterministic JSON comparison. Count `-1` as DBSCAN noise only.

- [ ] **Step 3: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_clustering_executor.py toolkit/tests/models/test_runner.py -q -p no:cacheprovider`

Commit: `feat: add clustering model execution`

---

### Task 16: Exact capability inventory and Codex routing

**Files:**
- Modify: `adapters/codex/routing.py`
- Modify: `tests/e2e/test_codex_modeling_flow.py`
- Create: `toolkit/tests/models/test_capability_inventory.py`

**Interfaces:**
- Consumes: `get_spec`, `list_capabilities`
- Produces: registry-derived `solver_execution_mode(model_id)`

- [ ] **Step 1: Write failing inventory and routing tests**

```python
NEW_MODELS = {
    "topsis", "entropy-weight", "ahp", "grey-relational-analysis",
    "linear-programming", "integer-programming", "nonlinear-programming",
    "grey-prediction-gm11", "arima", "exponential-smoothing", "nonlinear-regression",
    "normalization", "interpolation", "anomaly-detection", "pca",
    "correlation-analysis", "confidence-interval", "parametric-test",
    "nonparametric-test", "anova", "logistic-regression", "dbscan",
    "hierarchical-clustering",
}

def test_exact_new_inventory_and_minimum_total():
    ids = {item["model_id"] for item in list_capabilities()}
    assert NEW_MODELS <= ids
    assert {"linear-regression", "decision-tree", "kmeans"} <= ids
    assert len(ids) >= 26

@pytest.mark.parametrize("model_id", sorted(NEW_MODELS))
def test_every_real_capability_routes_to_execute(model_id):
    assert solver_execution_mode(model_id) == "execute"

@pytest.mark.parametrize("model_id", ["heuristic", "dynamic-programming", "unknown-model"])
def test_unregistered_capability_is_plan_only(model_id):
    assert solver_execution_mode(model_id) == "plan-only"
```

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest toolkit/tests/models/test_capability_inventory.py tests/e2e/test_codex_modeling_flow.py -v`

Expected: hard-coded routing disagrees with the registry and new IDs.

- [ ] **Step 3: Replace the hard-coded whitelist**

```python
def solver_execution_mode(model_id: str) -> str:
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must be a non-empty string")
    try:
        get_spec(model_id)
    except KeyError:
        return "plan-only"
    return "execute"
```

Ensure specification built-ins register lazily but deterministically and never depend on importing `adapters` from the toolkit.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest toolkit/tests/models/test_capability_inventory.py tests/e2e/test_codex_modeling_flow.py -q -p no:cacheprovider`

Commit: `fix: derive solver capability routing from real registry`

---

### Task 17: Six end-to-end model scenarios

**Files:**
- Create: `tests/e2e/test_model_executor_expansion.py`

**Interfaces:**
- Consumes: public `execute()` only
- Produces: user-visible scenario coverage across all seven executors

- [ ] **Step 1: Write six failing E2E scenarios**

Create real pipelines with these assertions:

```python
EVALUATION_PAYLOAD = {
    "matrix": [[80, 7], [90, 9], [75, 6]],
    "criteria": ["benefit", "cost"],
}
LP_PAYLOAD = {
    "objective": [3, 2],
    "sense": "maximize",
    "bounds": [[0, None], [0, None]],
    "inequality": {"matrix": [[1, 1], [1, 0], [0, 1]], "upper": [4, 2, 3]},
}

def test_evaluation_pipeline_entropy_weights_feed_topsis():
    weights = execute("entropy-weight", EVALUATION_PAYLOAD)["result"]["weights"]
    ranking = execute("topsis", {**EVALUATION_PAYLOAD, "weights": weights})
    assert sorted(ranking["result"]["ranking"]) == list(range(len(EVALUATION_PAYLOAD["matrix"])))

def test_optimization_continuous_and_integer_solutions_are_feasible():
    continuous = execute("linear-programming", LP_PAYLOAD)
    integer = execute("integer-programming", {**LP_PAYLOAD, "integrality": [1, 1]})
    assert integer["result"]["objective"] <= continuous["result"]["objective"] + 1e-9

def test_forecasts_expose_fitted_and_future_regions():
    series = [10 + 0.5 * index for index in range(30)]
    arima = execute("arima", {"series": series, "order": [1, 1, 0], "forecast_steps": 3})
    smoothing = execute("exponential-smoothing", {
        "series": series, "forecast_steps": 3, "trend": "add", "seasonal": None,
    })
    assert len(arima["result"]["fitted"]) == len(series)
    assert len(arima["result"]["forecast"]) == 3
    assert len(smoothing["result"]["fitted"]) == len(series)
    assert len(smoothing["result"]["forecast"]) == 3
    json.dumps([arima, smoothing], allow_nan=False)

def test_data_pipeline_normalize_detect_and_reduce():
    matrix = [[1, 10], [2, 11], [3, 12], [20, 30]]
    normalized = execute("normalization", {"matrix": matrix, "method": "zscore"})
    reduced = execute("pca", {
        "matrix": normalized["result"]["transformed"], "components": 1, "standardize": False,
    })
    anomalies = execute("anomaly-detection", {"matrix": matrix, "method": "iqr"})
    assert len(reduced["result"]["transformed"]) == len(matrix)
    assert all(len(row) == 1 for row in reduced["result"]["transformed"])
    assert anomalies["result"]["anomaly_indices"] == [3]
    json.dumps([normalized, reduced, anomalies], allow_nan=False)

def test_statistics_pipeline_reports_test_and_anova_summaries():
    correlation = execute("correlation-analysis", {
        "x": [1, 2, 3, 4], "y": [2, 4, 6, 8], "method": "pearson",
    })
    hypothesis = execute("parametric-test", {
        "test": "independent-t", "sample_a": [1, 2, 3],
        "sample_b": [4, 5, 6], "equal_variance": False,
    })
    anova = execute("anova", {"groups": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]})
    assert correlation["result"]["coefficient"] == pytest.approx(1.0)
    assert 0 <= hypothesis["result"]["p_value"] <= 1
    assert anova["result"]["ss_total"] == pytest.approx(
        anova["result"]["ss_between"] + anova["result"]["ss_within"]
    )
    json.dumps([correlation, hypothesis, anova], allow_nan=False)

def test_supervised_and_clustering_outputs_are_json_roundtrippable():
    classified = execute("logistic-regression", {
        "X": [[0], [1], [2], [3]], "y": [0, 0, 1, 1],
        "predict_X": [[1.5]], "seed": 7,
    })
    clustered = execute("dbscan", {
        "X": [[0, 0], [0, 0.1], [10, 10]],
        "params": {"eps": 0.3, "min_samples": 2}, "standardized": False,
    })
    assert len(classified["result"]["probabilities"][0]) == 2
    assert clustered["result"]["cluster_count"] == 1
    assert clustered["result"]["noise_count"] == 1
    assert json.loads(json.dumps([classified, clustered], allow_nan=False)) == [classified, clustered]
```

- [ ] **Step 2: Run and diagnose RED**

Run: `python -m pytest tests/e2e/test_model_executor_expansion.py -v`

Expected: any remaining executor integration mismatch is exposed. Do not change expected mathematical behavior to hide a failure.

- [ ] **Step 3: Fix only integration defects through additional RED/GREEN cycles**

For each discovered defect, first split a minimal reproduction into the relevant executor unit-test file, confirm RED, then fix production code and rerun the E2E scenario.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest tests/e2e/test_model_executor_expansion.py toolkit/tests/models -q -p no:cacheprovider`

Commit: `test: add multi-executor modeling scenarios`

---

### Task 18: Solver Skill packaging and usage documentation

**Files:**
- Modify: `adapters/codex/skills/solver/SKILL.md`
- Modify: `adapters/codex/skills/solver/resources.json`
- Modify: `docs/operations/codex-modeling-skills.md`
- Create: `docs/operations/model-executors.md`
- Modify: `tests/snapshots/codex-skills/test_packaging.py`
- Modify: `tests/snapshots/codex-skills/test_skill_contracts.py`

**Interfaces:**
- Documents: one minimal valid payload, core output and failure example for every new `model_id`
- Packages: exact runtime closure for `execute()` and all executor files

- [ ] **Step 1: Write failing documentation and package-import tests**

```python
def test_solver_docs_name_every_registered_capability(project_root):
    guide = (project_root / "docs/operations/model-executors.md").read_text(encoding="utf-8")
    for capability in list_capabilities():
        assert f"`{capability['model_id']}`" in guide

def test_packaged_solver_imports_public_execute_in_isolation(tmp_path):
    package_skills(ROOT, tmp_path / "skills")
    references = tmp_path / "skills/solver/references"
    result = isolated_import(references, "from cumcm_toolkit.models.execution import execute")
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest tests/snapshots/codex-skills/test_packaging.py tests/snapshots/codex-skills/test_skill_contracts.py -v`

- [ ] **Step 3: Update solver resources and documentation**

List exact Python files, `scripts/contract_formats.py`, `scripts/validate_contracts.py`, `shared/contracts/model-execution.schema.json`, and registered knowledge cards in `resources.json`; do not package entire cache-bearing directories. Document family-specific payloads and the fail-closed rules. Explain that `run_model` is legacy and `execute` is the Codex/DSH contract.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest tests/snapshots/codex-skills -q -p no:cacheprovider`

Run: `python scripts/package_codex_skills.py --check`

Commit: `docs: publish model executor usage and skill resources`

---

### Task 19: Full verification and Phase 7 handoff preparation

**Files:**
- Modify: `docs/superpowers/plans/2026-08-25-model-executor-expansion.md` (checkboxes only after commands pass)
- Create: `docs/operations/model-executor-to-dsh-handoff.md`

**Interfaces:**
- Produces: exact Phase 7 consumption surface without editing DSH production files

- [ ] **Step 1: Write the handoff acceptance test**

Add a documentation test asserting the handoff names:

- `cumcm_toolkit.models.execution.execute`
- `cumcm_toolkit.models.specifications.list_capabilities`
- `shared/contracts/model-execution.schema.json`
- JSON-only results
- no copied algorithm implementation
- Phase 7 rebase/merge order

Run the new test and confirm RED because the handoff file does not exist.

- [ ] **Step 2: Write the handoff and verify GREEN**

Document the exact imports, payload/result version, error semantics, contract validation command, and a minimal DSH adapter pseudocode that delegates to `execute` without copying algorithms.

- [ ] **Step 3: Run targeted acceptance commands**

Run:

```powershell
python -m pytest toolkit/tests/models tests/e2e/test_model_executor_expansion.py -q -p no:cacheprovider
python -m pytest tests/contracts -q -p no:cacheprovider
python scripts/validate_contracts.py
python scripts/package_codex_skills.py --check
```

Expected:

- All model and E2E tests pass.
- Contract validator reports 16 contracts and zero errors.
- Skill packager reports 12 skills and status ok.

- [ ] **Step 4: Run the complete suite**

Run: `python -m pytest -q -p no:cacheprovider`

Expected: zero failures. Environment-dependent LaTeX tests may retain their existing explicit skips; no new skips are allowed for the 23 model capabilities.

- [ ] **Step 5: Inspect repository and DSH isolation**

Run:

```powershell
git diff --check
git status --short
git diff --name-only 8b9b807...HEAD -- adapters/dsh
```

Expected: no whitespace errors; only intended plan checkbox/handoff changes remain before the last commit; no Phase 7 DSH production file changed.

- [ ] **Step 6: Commit verification evidence**

Commit: `docs: hand off model executors for DSH integration`

- [ ] **Step 7: Request independent code review before merging**

Use `superpowers:requesting-code-review` against the complete branch. Require the reviewer to verify all 23 IDs execute, the registry is the routing truth, outputs are finite JSON, nonlinear expressions cannot execute code, and DSH production files are untouched.

Do not merge to `main` until Phase 7 is complete and the user explicitly chooses the integration action.
