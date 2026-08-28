# Model executor → DSH handoff

Phase 7 consumes the model-executor branch through one boundary: a registered `model_id` plus a JSON payload produces a versioned JSON result. DSH must not import executor modules, call the legacy `run_model()`, or duplicate any numerical implementation.

## Stable imports and discovery

```python
from cumcm_toolkit.models.execution import execute
from cumcm_toolkit.models.specifications import list_capabilities
```

`cumcm_toolkit.models.specifications.list_capabilities` is the routing truth. It returns sorted, function-free descriptions containing `model_id`, `executor`, `knowledge_card`, `deterministic`, `seed_supported`, and `payload_fields`. The adapter must obtain the allowed IDs from this registry and call `cumcm_toolkit.models.execution.execute` only for a registered ID. `run_model(name, X, y)` remains a backwards-compatible Python-only API that returns a fitted estimator; it is not a DSH transport API.

## Payload and result contract

The input is `execute(model_id: str, payload: Mapping[str, object])`. DSH sends a JSON object whose required top-level fields are the registered capability's `payload_fields`; model-specific fields and constraints remain owned by the registered executor. It must not evaluate Python code, callbacks, or string formulas. In particular, nonlinear programming accepts only its declared JSON expression tree, and nonlinear regression accepts only its fixed families.

Every successful call returns JSON-only results under `shared/contracts/model-execution.schema.json`, with `schema_version` exactly `"1.0"` and `status` exactly `"succeeded"`. The common envelope is `schema_version`, `status`, `model_id`, `executor`, `parameters`, `input_summary`, `result`, `diagnostics`, `warnings`, and `reproducibility`; `reproducibility` contains `seed` and `deterministic`. The result must survive `json.dumps(result, allow_nan=False)` followed by `json.loads()` with no estimator objects, callbacks, NumPy/Pandas objects, `NaN`, or infinities. A future persisted `failed` schema branch exists, but public `execute()` does not return it.

## Failure and validation rules

`execute()` fails closed: unknown IDs, invalid or missing payload fields, algorithm/domain/solver failures, and non-JSON or non-finite output raise `ValueError`. The message identifies the `model_id` and the failed stage (`specification`, `payload`, `payload fields`, `execution`, or `result`); DSH must return a failed tool invocation rather than manufacture a partial success envelope.

Validate the shared catalog and fixtures from the repository root before integration:

```powershell
python scripts/validate_contracts.py
```

The current verified baseline is 16 contracts with zero validation errors.

## Minimal DSH delegation

```text
capabilities = list_capabilities()
allowed_ids = {item["model_id"] for item in capabilities}
if request.model_id not in allowed_ids:
    return tool_failure("unregistered model_id")

try:
    result = execute(request.model_id, request.payload)
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    return tool_success(result)
except ValueError as error:
    return tool_failure(str(error))
```

This adapter owns request/response transport only: **no copied algorithm implementation**. It neither ports the seven executors to TypeScript nor evaluates executable payload content; algorithm validation, solving, finite-value checks, and schema-shaped result construction remain in the Python public API.

## Phase 7 rebase/merge order

1. Complete and independently review the Phase 7 DSH branch without changing this model-executor contract.
2. First bring the final Phase 7 mainline into `codex/model-executor-expansion` by merge, or rebase this branch onto that final mainline.
3. Then resolve only the resulting `shared/contracts/catalog.json`, Skill-resource, and documentation-count conflicts; rerun contract, package, model, and full-suite verification.
4. Do not merge to `main` until Phase 7 is complete and the user explicitly chooses the integration action.

This is the required Phase 7 rebase/merge order. It preserves the registry and `execute()` as the single routing and algorithm source while Phase 7 adds its thin adapter.
