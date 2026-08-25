/**
 * cumcm-tools bridge — thin subprocess adapter for the cumcm-workbench Python
 * CLI.
 *
 * Zero toolkit logic lives here. This file only resolves an interpreter,
 * assembles `python -m cumcm_toolkit.<module>` argv, spawns the child, and
 * interprets stdout / stderr / exit code with fail-closed semantics. All
 * deterministic behavior belongs to the Python CLI in the cumcm-workbench
 * repository (`toolkit/src/cumcm_toolkit/`).
 *
 * Output capture: the child's stdout/stderr are redirected to per-call temp
 * files (file-descriptor stdio) and read back after exit. This avoids pipe
 * buffer deadlocks on large reports, keeps the parent from blocking, and
 * works in sandboxed environments where pipe stdio is unavailable.
 */
/** Plugin configuration consumed by the bridge. */
export interface CumcmToolConfig {
    /** cumcm-workbench repository root: subprocess cwd and PYTHONPATH base. */
    cumcmRoot: string;
    /** Optional explicit python executable; wins over .venv / `uv run`. */
    pythonBin: string;
    /** Per-call subprocess timeout in milliseconds. */
    toolTimeoutMs: number;
}
/** Outcome of one bridged tool call. */
export interface RunPythonToolResult {
    /** Whether the CLI produced a valid JSON value on stdout and exited 0. */
    ok: boolean;
    /** Parsed stdout JSON value when `ok`; otherwise absent. */
    data?: unknown;
    /** Human-readable failure reason when `ok` is false. */
    error?: string;
}
export interface RunPythonToolOptions {
    /** Caller cancellation; abort kills the child and fails closed. */
    signal?: AbortSignal;
    /** cwd fallback used when config.cumcmRoot is empty. */
    cwd?: string;
}
/**
 * Resolve the argv prefix that runs the cumcm-workbench CLI.
 *
 * Order: explicit `pythonBin` → `cumcmRoot/.venv` python (Windows
 * `Scripts/python.exe`, POSIX `bin/python`) → `["uv", "run"]` when `uv` is on
 * PATH. Throws a clear error (mentioning cumcmRoot/pythonBin) when nothing
 * matches.
 */
export declare function resolvePython(config: CumcmToolConfig): Promise<string[]>;
/**
 * Spawn `python -m cumcm_toolkit.<module> <args>` and interpret its outcome
 * with fail-closed semantics:
 *
 * - spawn failure / timeout / cancellation → failed with a clear error;
 * - stdout last-line `JSON.parse` failure → failed ("invalid JSON output"),
 *   never treated as success even on exit 0;
 * - exit 0 + valid JSON → ok:true with the parsed value;
 * - exit ≠ 0 → failed: stdout JSON `error` field when present, otherwise the
 *   first stderr line, otherwise a fixed message. In particular the I-1
 *   contract holds: argparse-level failure (`SystemExit(2)`, usage on stderr,
 *   EMPTY stdout) fails closed with the stderr first line — it never crashes
 *   and never treats empty output as success.
 */
export declare function runPythonTool(config: CumcmToolConfig, moduleName: string, args: string[], options?: RunPythonToolOptions): Promise<RunPythonToolResult>;
