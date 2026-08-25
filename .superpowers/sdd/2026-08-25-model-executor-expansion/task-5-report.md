# Task 5 report — linear and mixed-integer programming

## RED / GREEN

- RED: added the unknown-model exact LP test and ran `python -m pytest toolkit/tests/models/test_optimization_executor.py -v`; it failed because `linear-programming` was not registered. The complete new test file then failed 21 tests for the same missing registrations.
- GREEN: implemented the SciPy adapters and registrations. `python -m pytest toolkit/tests/models/test_optimization_executor.py -q -p no:cacheprovider` passed 21 tests.
- Regression: `python -m pytest toolkit/tests/models -q -p no:cacheprovider` passed 122 tests. One pre-existing joblib physical-core-discovery warning was emitted by the runner test.

## Files

- Added `toolkit/src/cumcm_toolkit/models/executors/optimization.py`.
- Added `toolkit/tests/models/test_optimization_executor.py`.
- Updated `toolkit/src/cumcm_toolkit/models/specifications.py` to register `linear-programming` and `integer-programming` with the existing optimization knowledge cards.

## Numerical and boundary behavior

- LP uses `scipy.optimize.linprog(method="highs")`; MILP uses `scipy.optimize.milp` with `Bounds` and explicit `LinearConstraint` objects.
- Maximization is solved by negating the objective only inside the solver. Returned objectives are recomputed from the original coefficients; no continuous solution is rounded.
- Bounds require one `[lower, upper]` pair per variable. JSON `null` maps to an infinite SciPy endpoint, while present endpoints must be finite and ordered.
- Both constraint families are optional only when omitted. Present matrices and right-hand sides must be finite, rectangular, and dimensionally aligned.
- The executor accepts only `success=True` and finite solutions/objectives. Infeasible, unbounded, and numerical solver outcomes become execution-stage `ValueError`s.

## Review notes / concerns

- Solver diagnostics include status, message, and constraint residuals. MILP records finite `mip_dual_bound` and `mip_gap` values when supplied; when either is unavailable or non-finite, it is omitted and a warning explains this.
- `git diff --check` completed without whitespace errors. No dependencies or DSH code were changed.

## Fix round 1 — dual-bound sign and feasibility summary

### RED / GREEN

- RED: added a maximization MILP regression with objective coefficient 9 and ran `python -m pytest toolkit/tests/models/test_optimization_executor.py -q -p no:cacheprovider -k 'mip_dual_bound_sign or feasibility_summary'`. All three selected tests failed: the dual bound was `-9.0`, and both LP/MILP diagnostics lacked `feasibility`.
- GREEN: after the repair, the same focused command passed `3 passed, 21 deselected`. The full optimization test file passed `24 passed in 2.03s`; `toolkit/tests/models` passed `125 passed, 1 warning in 7.30s` (the pre-existing joblib physical-core-discovery warning).

### Numerical contract

- A maximization MILP negates the objective only for SciPy. Its finite `mip_dual_bound` is negated back for public diagnostics; `mip_gap` is dimensionless and unchanged. Missing or non-finite MIP fields remain omitted with their existing warning.
- Every successful LP and MILP result now includes `diagnostics.feasibility` with tolerance `1e-8`. For returned solution `x`, the summary calculates:
  - `max_bound_violation = max(max(lower - x, 0), max(x - upper, 0))`
  - `max_inequality_violation = max(A_ub x - b_ub, 0)`
  - `max_equality_violation = max(abs(A_eq x - b_eq))`
  - `max_violation` is the maximum of those three; `feasible` is `max_violation <= tolerance`.
- Missing constraint families contribute exactly `0.0`; finite calculation is enforced before the result envelope is built. The status flag is reported separately and is not used as the feasibility decision.
