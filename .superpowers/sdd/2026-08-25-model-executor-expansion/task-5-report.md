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
