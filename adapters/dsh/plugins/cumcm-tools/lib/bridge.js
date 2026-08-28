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
import { spawn } from 'node:child_process';
import { access, constants } from 'node:fs/promises';
import { mkdtemp, open, readFile, rm, stat } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
const DEFAULT_TIMEOUT_MS = 120_000;
/** Defensive per-stream capture cap; larger output fails closed. */
const MAX_STREAM_BYTES = 8 * 1024 * 1024;
/** True when `candidate` exists on disk. */
async function exists(candidate) {
    try {
        await access(candidate, constants.F_OK);
        return true;
    }
    catch {
        return false;
    }
}
/** True when an executable named `name` is visible on PATH. */
async function commandOnPath(name) {
    const exts = process.platform === 'win32' ? ['.exe', '.cmd', '.bat', ''] : [''];
    const dirs = (process.env.PATH ?? '').split(path.delimiter).filter(Boolean);
    for (const dir of dirs) {
        for (const ext of exts) {
            if (await exists(path.join(dir, `${name}${ext}`)))
                return true;
        }
    }
    return false;
}
/**
 * Resolve the argv prefix that runs the cumcm-workbench CLI.
 *
 * Order: explicit `pythonBin` → `cumcmRoot/.venv` python (Windows
 * `Scripts/python.exe`, POSIX `bin/python`) → `["uv", "run"]` when `uv` is on
 * PATH. Throws a clear error (mentioning cumcmRoot/pythonBin) when nothing
 * matches.
 */
export async function resolvePython(config) {
    if (config.pythonBin && config.pythonBin.trim() !== '') {
        return [config.pythonBin];
    }
    if (config.cumcmRoot && config.cumcmRoot.trim() !== '') {
        const rel = process.platform === 'win32'
            ? path.join('.venv', 'Scripts', 'python.exe')
            : path.join('.venv', 'bin', 'python');
        const venvPython = path.join(config.cumcmRoot, rel);
        if (await exists(venvPython))
            return [venvPython];
    }
    if (await commandOnPath('uv'))
        return ['uv', 'run'];
    throw new Error('cannot resolve a python interpreter: pythonBin is empty, ' +
        `cumcmRoot '${config.cumcmRoot}' has no usable .venv python, and 'uv' is not on PATH. ` +
        'Configure cumcmRoot and/or pythonBin in the cumcm-tools plugin config.');
}
/**
 * PYTHONPATH for the child: `cumcmRoot/toolkit/src` and `cumcmRoot` first so
 * `cumcm_toolkit.*` and the repo-root `scripts` package resolve regardless of
 * whether the venv has an editable install.
 */
function buildPythonPath(cwd) {
    const parts = [path.join(cwd, 'toolkit', 'src'), cwd];
    const existing = process.env.PYTHONPATH;
    if (existing && existing.trim() !== '')
        parts.push(existing);
    return parts.join(path.delimiter);
}
function firstNonEmptyLine(text) {
    for (const line of text.split(/\r?\n/)) {
        if (line.trim() !== '')
            return line.trim();
    }
    return undefined;
}
/** Last non-empty line of `text`, or undefined when every line is blank. */
function lastNonEmptyLine(text) {
    const lines = text.split(/\r?\n/);
    for (let index = lines.length - 1; index >= 0; index -= 1) {
        const line = lines[index].trim();
        if (line !== '')
            return line;
    }
    return undefined;
}
function isRecord(value) {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
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
export async function runPythonTool(config, moduleName, args, options = {}) {
    let python;
    try {
        python = await resolvePython(config);
    }
    catch (error) {
        return {
            ok: false,
            error: error instanceof Error ? error.message : String(error),
        };
    }
    const cwd = config.cumcmRoot && config.cumcmRoot.trim() !== ''
        ? config.cumcmRoot
        : options.cwd || process.cwd();
    const timeoutMs = Number.isFinite(config.toolTimeoutMs) && config.toolTimeoutMs > 0
        ? config.toolTimeoutMs
        : DEFAULT_TIMEOUT_MS;
    const argv = [...python, '-m', `cumcm_toolkit.${moduleName}`, ...args];
    const env = {
        ...process.env,
        PYTHONDONTWRITEBYTECODE: '1',
        // Deterministic UTF-8 regardless of console/locale codepage.
        PYTHONIOENCODING: 'utf-8',
        PYTHONPATH: buildPythonPath(cwd),
    };
    // Per-call temp dir for stdout/stderr capture (file-descriptor stdio).
    const captureDir = await mkdtemp(path.join(os.tmpdir(), 'cumcm-tools-'));
    const stdoutFile = path.join(captureDir, 'stdout.txt');
    const stderrFile = path.join(captureDir, 'stderr.txt');
    const outHandle = await open(stdoutFile, 'w');
    const errHandle = await open(stderrFile, 'w');
    let outcome;
    try {
        const child = spawn(argv[0], argv.slice(1), {
            cwd,
            env,
            stdio: ['ignore', outHandle.fd, errHandle.fd],
            windowsHide: true,
        });
        outcome = await new Promise((resolve) => {
            let settled = false;
            const finish = (value) => {
                if (settled)
                    return;
                settled = true;
                clearTimeout(timer);
                resolve(value);
            };
            const timer = setTimeout(() => {
                child.kill('SIGKILL');
                finish({ kind: 'timeout', timeoutMs });
            }, timeoutMs);
            const onAbort = () => {
                child.kill('SIGKILL');
                finish({ kind: 'cancel' });
            };
            if (options.signal) {
                if (options.signal.aborted)
                    onAbort();
                else
                    options.signal.addEventListener('abort', onAbort, { once: true });
            }
            child.on('error', (error) => finish({ kind: 'spawn-error', error }));
            child.on('close', (code, signal) => {
                finish({ kind: 'exit', code: code ?? -1, signal });
            });
        });
    }
    finally {
        // The child has settled; release the capture handles.
        await outHandle.close().catch(() => { });
        await errHandle.close().catch(() => { });
    }
    try {
        if (outcome.kind === 'spawn-error') {
            return {
                ok: false,
                error: `cannot start python subprocess (${argv[0]}): ${outcome.error.message}`,
            };
        }
        if (outcome.kind === 'timeout') {
            return {
                ok: false,
                error: `cumcm_toolkit.${moduleName} timed out after ${outcome.timeoutMs}ms`,
            };
        }
        if (outcome.kind === 'cancel') {
            return {
                ok: false,
                error: `cumcm_toolkit.${moduleName} tool call cancelled`,
            };
        }
        const [stdoutSize, stderrSize] = await Promise.all([
            stat(stdoutFile).then((s) => s.size, () => 0),
            stat(stderrFile).then((s) => s.size, () => 0),
        ]);
        if (stdoutSize > MAX_STREAM_BYTES || stderrSize > MAX_STREAM_BYTES) {
            return {
                ok: false,
                error: `cumcm_toolkit.${moduleName} produced more than ${MAX_STREAM_BYTES} bytes of output`,
            };
        }
        const stdout = await readFile(stdoutFile, 'utf8');
        const stderr = await readFile(stderrFile, 'utf8');
        // Contract: the JSON is the LAST non-empty stdout line. A CLI may log
        // noise to stdout before the result — scan from the end so leading log
        // lines never break parsing.
        const lastLine = lastNonEmptyLine(stdout);
        let parsed;
        let jsonError = null;
        if (lastLine !== undefined) {
            try {
                parsed = JSON.parse(lastLine);
            }
            catch {
                jsonError = 'invalid JSON output';
            }
        }
        else {
            jsonError = 'no JSON output (empty stdout)';
        }
        if (outcome.code === 0) {
            if (jsonError !== null) {
                const stderrFirst = firstNonEmptyLine(stderr);
                return {
                    ok: false,
                    error: `cumcm_toolkit.${moduleName}: ${jsonError}${stderrFirst ? ` (stderr: ${stderrFirst})` : ''}`,
                };
            }
            return { ok: true, data: parsed };
        }
        // Non-zero exit: prefer the CLI's own JSON error field, else the first
        // stderr line, else a fixed message (I-1: empty stdout + usage must fail
        // closed, never crash, never look like success).
        if (jsonError === null && isRecord(parsed) && typeof parsed.error === 'string') {
            return { ok: false, error: parsed.error };
        }
        const stderrFirst = firstNonEmptyLine(stderr);
        return {
            ok: false,
            error: stderrFirst ??
                `cumcm_toolkit.${moduleName} exited with code ${outcome.code} and no JSON output`,
        };
    }
    finally {
        await rm(captureDir, { recursive: true, force: true }).catch(() => { });
    }
}
