/**
 * literature-tools — literature thin-adapter plugin for DeepSeek Harness.
 *
 * Registers 3 tools on `ctx.tools`:
 *
 *   literature_read_source       deterministic OFFLINE parse of a PDF/JSON/text
 *                                file into a literature-source-compatible
 *                                candidate object (never fabricates metadata);
 *   literature_route_candidate   forwards a candidate array to the Python dedup
 *                                rule engine (`python -m
 *                                cumcm_toolkit.literature.rules --group`) and
 *                                returns `{groups, conflicts}` — the TypeScript
 *                                side carries ZERO rule logic;
 *   literature_search            fail-closed search gate: no backend → blocked;
 *                                backend not covered by `allowedDomains` →
 *                                blocked; otherwise returns an authorization
 *                                placeholder with an empty candidate list (no
 *                                real backend forwarding is implemented, so no
 *                                fabricated results are ever returned).
 *
 * Host-only plugin: no `dsh.client`, single tsconfig program.
 */
import type { Context } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
export declare const name = "literature-tools";
export declare const inject: string[];
export interface Config {
    /** Search backend identifier (e.g. paper-search / runtime-search); '' = none. */
    backend: string;
    /** Network allowlist; must explicitly cover the configured backend (fail-closed). */
    allowedDomains: string[];
    /** cumcm-workbench repo root containing toolkit/src/cumcm_toolkit. REQUIRED. */
    sourceRoot: string;
}
export declare const Config: z<Schemastery.ObjectS<{
    backend: z<string, string>;
    allowedDomains: z<string[], string[]>;
    sourceRoot: z<string, string>;
}>, Schemastery.ObjectT<{
    backend: z<string, string>;
    allowedDomains: z<string[], string[]>;
    sourceRoot: z<string, string>;
}>>;
export declare function apply(ctx: Context, config: Config): void;
