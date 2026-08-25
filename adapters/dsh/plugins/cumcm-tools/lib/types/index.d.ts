/**
 * cumcm-tools — CUMCM workbench thin adapter plugin for DeepSeek Harness.
 *
 * Registers 15 deterministic `cumcm_*` tools on `ctx.tools`. Every tool is a
 * pure adapter: it assembles model arguments into CLI argv, spawns
 * `python -m cumcm_toolkit.<module> <args>` through {@link runPythonTool}, and
 * parses the stdout JSON with fail-closed semantics. The TypeScript side
 * carries zero toolkit logic — all deterministic behavior lives in the
 * cumcm-workbench Python CLI (`toolkit/src/cumcm_toolkit/`).
 *
 * Host-only plugin: no `dsh.client`, single tsconfig program.
 */
import type { Context } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
export declare const name = "cumcm-tools";
export declare const inject: string[];
export interface Config {
    /** cumcm-workbench repository root (contains .venv and toolkit/src). */
    cumcmRoot: string;
    /** Optional explicit python executable (absolute path). */
    pythonBin: string;
    /** Per-call subprocess timeout in milliseconds. */
    toolTimeoutMs: number;
}
export declare const Config: z<any, any>;
export declare function apply(ctx: Context, config: Config): void;
