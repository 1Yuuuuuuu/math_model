# Task 3 Report: Citation Link Contract

## Implementation

- Added `shared/contracts/citation-link.schema.json` using JSON Schema Draft 2020-12.
- Enforced `additionalProperties: false` and the required fields from the brief.
- Added `cite_`, `clm_`, and `src_` identifier patterns, controlled usage values, precise nested locators, support boundaries, and date-time verification timestamps.
- Added valid synthetic citation fixture and an invalid fixture that removes only the top-level `locator`.
- Added `tests/contracts/test_citation_link.py` to verify valid acceptance and required-locator rejection.
- Left catalog registration and the existing evidence-link/literature-source contracts unchanged, as required by task boundaries.

## TDD evidence

### RED

After adding the failing test and before creating the contract files:

```text
.venv\Scripts\python.exe -m pytest tests/contracts/test_citation_link.py -v -p no:cacheprovider
1 failed: FileNotFoundError for shared/contracts/citation-link.schema.json
```

The failure was caused by the requested citation files not yet existing.

### GREEN

After adding the schema and fixtures:

```text
.venv\Scripts\python.exe -m pytest tests/contracts/test_citation_link.py tests/contracts/test_contract_boundaries.py -v -p no:cacheprovider
188 passed in 0.34s
```

## Full verification

```text
.venv\Scripts\python.exe -m pytest -p no:cacheprovider
296 passed in 18.68s
```

`git diff --check` completed without errors before commit.

## Files changed

- `shared/contracts/citation-link.schema.json`
- `shared/fixtures/contracts/valid/citation-link.json`
- `shared/fixtures/contracts/invalid/citation-link-missing-locator.json`
- `tests/contracts/test_citation_link.py`

## Commit

`71a55cc feat: define citation evidence contract`

## Self-review

- Required fields and exact property definitions match the task brief.
- Locator is mandatory and constrained to the specified kinds and newline-free values.
- Identifier patterns use the required cross-runtime end assertion.
- The fixture is explicitly synthetic and contains no real-paper quotation.
- No existing literature-source or evidence-link files were modified.

## Concerns

No implementation concerns. Catalog registration is intentionally deferred to Task 4.

## Review fix round 1

Addressed the review finding that citation-specific ID and locator newline behavior was not covered by the boundary matrix. Added these four cases to `PATTERN_FIELD_CASES` in `tests/contracts/test_contract_boundaries.py`:

- `citation-link.citation_id`
- `citation-link.claim_id`
- `citation-link.source_id`
- `citation-link.locator.value`

Command and result:

```text
.venv\Scripts\python.exe -m pytest tests/contracts/test_citation_link.py tests/contracts/test_contract_boundaries.py -v -p no:cacheprovider
196 passed in 0.36s
```

The expanded parametrized test now executes both LF and CR rejection for all four citation fields.
