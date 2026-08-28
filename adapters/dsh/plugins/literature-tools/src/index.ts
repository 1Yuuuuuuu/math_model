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

import type { Context } from '@deepseek-ai/cordis'
import z from '@deepseek-ai/schemastery'
import {
  defineTool,
  type ValueSchemaSpec,
} from '@deepseek-ai/dsh-tools'
import { spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { access, constants, mkdtemp, open, readFile, rm, stat } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

export const name = 'literature-tools'
export const inject = ['tools']

export interface Config {
  /** Search backend identifier (e.g. paper-search / runtime-search); '' = none. */
  backend: string
  /** Network allowlist; must explicitly cover the configured backend (fail-closed). */
  allowedDomains: string[]
  /** cumcm-workbench repo root containing toolkit/src/cumcm_toolkit. REQUIRED. */
  sourceRoot: string
}

export const Config = z.object({
  backend: z.string().default(''),
  allowedDomains: z.array(z.string()).default([]),
  // Required on purpose: a missing sourceRoot must fail plugin startup
  // (schema required), never silently degrade.
  sourceRoot: z.string().required(),
})

/** Config after normalization inside apply(). */
interface NormalizedConfig {
  backend: string
  allowedDomains: string[]
  sourceRoot: string
}

/** Open object: any JSON object passes (unknown keys allowed). */
const openObject: ValueSchemaSpec = { type: 'object', additionalProperties: true }
/** Integer or JSON null (CLI emits `null` for unset optional ints). */
const nullableInt: ValueSchemaSpec = { oneOf: [{ type: 'integer' }, { type: 'null' }] }
/** String or JSON null. */
const nullableString: ValueSchemaSpec = { oneOf: [{ type: 'string' }, { type: 'null' }] }
/** String array or JSON null. */
const nullableStringArray: ValueSchemaSpec = {
  oneOf: [{ type: 'array', items: { type: 'string' } }, { type: 'null' }],
}
/** Object or JSON null. */
const nullableObject: ValueSchemaSpec = { oneOf: [openObject, { type: 'null' }] }

const RULES_CLI_TIMEOUT_MS = 120_000
/** Defensive per-stream capture cap; larger output fails closed. */
const MAX_STREAM_BYTES = 8 * 1024 * 1024
/**
 * Safety ceiling for the serialized `--group` candidate array passed as a
 * single argv. Windows CreateProcess caps the command line at ~32,767 chars;
 * crossing it turns a Node spawn into ENAMETOOLONG deep inside the bridge.
 * Pre-checking here surfaces a clear batching error instead. 20000 chars ≈
 * roughly 100–200 records; the documented guidance is ~500 records per call.
 */
const MAX_CANDIDATE_ARGV_CHARS = 20_000

/** Contract-required candidate metadata fields tracked for gap reporting. */
const CANDIDATE_GAP_FIELDS = [
  'source_id',
  'title',
  'authors',
  'year',
  'venue_or_repository',
  'identifiers',
  'canonical_url',
  'retrieved_at',
  'retrieval_backend',
] as const

const SEARCH_BACKENDS = ['paper-search', 'runtime-search', 'user-provided'] as const

// ---------------------------------------------------------------------------
// Python rules CLI subprocess bridge (fail-closed; zero rule logic here)
// ---------------------------------------------------------------------------

/** Outcome of one bridged rules-CLI call. */
interface RulesCliResult {
  ok: boolean
  data?: unknown
  error?: string
}

type ChildOutcome =
  | { kind: 'exit'; code: number }
  | { kind: 'timeout'; timeoutMs: number }
  | { kind: 'cancel' }
  | { kind: 'spawn-error'; error: Error }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** True when `candidate` exists on disk. */
async function exists(candidate: string): Promise<boolean> {
  try {
    await access(candidate, constants.F_OK)
    return true
  } catch {
    return false
  }
}

/**
 * Resolve the argv prefix that runs the literature rules CLI.
 *
 * Order: `LITERATURE_TOOLS_PYTHON` env override (ops/test hook) →
 * `sourceRoot/.venv` python (Windows `Scripts/python.exe`, POSIX `bin/python`)
 * → `python` on PATH. The plugin refuses to start without sourceRoot, so a
 * missing interpreter surfaces at call time as a failed tool, never silently.
 */
async function resolvePython(config: NormalizedConfig): Promise<string[]> {
  const override = process.env.LITERATURE_TOOLS_PYTHON
  if (override && override.trim() !== '') return [override]
  const rel =
    process.platform === 'win32'
      ? path.join('.venv', 'Scripts', 'python.exe')
      : path.join('.venv', 'bin', 'python')
  const venvPython = path.join(config.sourceRoot, rel)
  if (await exists(venvPython)) return [venvPython]
  return ['python']
}

/**
 * PYTHONPATH for the child: `sourceRoot/toolkit/src` and `sourceRoot` first so
 * `cumcm_toolkit.literature.rules` resolves regardless of whether the venv has
 * an editable install.
 */
function buildPythonPath(sourceRoot: string): string {
  const parts = [path.join(sourceRoot, 'toolkit', 'src'), sourceRoot]
  const existing = process.env.PYTHONPATH
  if (existing && existing.trim() !== '') parts.push(existing)
  return parts.join(path.delimiter)
}

/** Last non-empty line of `text`, or undefined when every line is blank. */
function lastNonEmptyLine(text: string): string | undefined {
  const lines = text.split(/\r?\n/)
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index].trim()
    if (line !== '') return line
  }
  return undefined
}

/** First non-empty line of `text`, or undefined. */
function firstNonEmptyLine(text: string): string | undefined {
  for (const line of text.split(/\r?\n/)) {
    if (line.trim() !== '') return line.trim()
  }
  return undefined
}

/**
 * Spawn `python -m cumcm_toolkit.literature.rules <args>` and interpret the
 * outcome with fail-closed semantics (mirrors the cumcm-tools bridge):
 * spawn failure / timeout / cancellation → failed; stdout last-line
 * `JSON.parse` failure → failed; exit 0 + valid JSON → ok; exit ≠ 0 → failed
 * (stdout JSON `error` field when present, else first stderr line, else a
 * fixed message). Output is captured through per-call temp files
 * (file-descriptor stdio) to avoid pipe deadlocks and sandbox pipe limits.
 */
async function runRulesCli(
  config: NormalizedConfig,
  args: string[],
  signal: AbortSignal | undefined,
): Promise<RulesCliResult> {
  const python = await resolvePython(config)
  const cwd = config.sourceRoot
  const argv = [...python, '-m', 'cumcm_toolkit.literature.rules', ...args]
  const env = {
    ...process.env,
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHONIOENCODING: 'utf-8',
    PYTHONPATH: buildPythonPath(cwd),
  }

  const captureDir = await mkdtemp(path.join(os.tmpdir(), 'literature-tools-'))
  const stdoutFile = path.join(captureDir, 'stdout.txt')
  const stderrFile = path.join(captureDir, 'stderr.txt')
  const outHandle = await open(stdoutFile, 'w')
  const errHandle = await open(stderrFile, 'w')

  let outcome: ChildOutcome
  try {
    const child = spawn(argv[0], argv.slice(1), {
      cwd,
      env,
      stdio: ['ignore', outHandle.fd, errHandle.fd],
      windowsHide: true,
    })
    outcome = await new Promise<ChildOutcome>((resolve) => {
      let settled = false
      const finish = (value: ChildOutcome) => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        resolve(value)
      }
      const timer = setTimeout(() => {
        child.kill('SIGKILL')
        finish({ kind: 'timeout', timeoutMs: RULES_CLI_TIMEOUT_MS })
      }, RULES_CLI_TIMEOUT_MS)
      const onAbort = () => {
        child.kill('SIGKILL')
        finish({ kind: 'cancel' })
      }
      if (signal) {
        if (signal.aborted) onAbort()
        else signal.addEventListener('abort', onAbort, { once: true })
      }
      child.on('error', (error) => finish({ kind: 'spawn-error', error }))
      child.on('close', (code) => finish({ kind: 'exit', code: code ?? -1 }))
    })
  } finally {
    await outHandle.close().catch(() => {})
    await errHandle.close().catch(() => {})
  }

  try {
    if (outcome.kind === 'spawn-error') {
      return {
        ok: false,
        error: `cannot start python subprocess (${argv[0]}): ${outcome.error.message}`,
      }
    }
    if (outcome.kind === 'timeout') {
      return { ok: false, error: `literature rules CLI timed out after ${outcome.timeoutMs}ms` }
    }
    if (outcome.kind === 'cancel') {
      return { ok: false, error: 'literature rules CLI call cancelled' }
    }

    const [stdoutSize, stderrSize] = await Promise.all([
      stat(stdoutFile).then((s) => s.size, () => 0),
      stat(stderrFile).then((s) => s.size, () => 0),
    ])
    if (stdoutSize > MAX_STREAM_BYTES || stderrSize > MAX_STREAM_BYTES) {
      return {
        ok: false,
        error: `literature rules CLI produced more than ${MAX_STREAM_BYTES} bytes of output`,
      }
    }
    const stdout = await readFile(stdoutFile, 'utf8')
    const stderr = await readFile(stderrFile, 'utf8')

    // Contract: the JSON is the LAST non-empty stdout line.
    const lastLine = lastNonEmptyLine(stdout)
    let parsed: unknown
    let jsonError: string | null = null
    if (lastLine !== undefined) {
      try {
        parsed = JSON.parse(lastLine)
      } catch {
        jsonError = 'invalid JSON output'
      }
    } else {
      jsonError = 'no JSON output (empty stdout)'
    }

    if (outcome.code === 0) {
      if (jsonError !== null) {
        const stderrFirst = firstNonEmptyLine(stderr)
        return {
          ok: false,
          error: `literature rules CLI: ${jsonError}${
            stderrFirst ? ` (stderr: ${stderrFirst})` : ''
          }`,
        }
      }
      return { ok: true, data: parsed }
    }

    if (jsonError === null && isRecord(parsed) && typeof parsed.error === 'string') {
      return { ok: false, error: parsed.error }
    }
    const stderrFirst = firstNonEmptyLine(stderr)
    return {
      ok: false,
      error:
        stderrFirst ??
        `literature rules CLI exited with code ${outcome.code} and no JSON output`,
    }
  } finally {
    await rm(captureDir, { recursive: true, force: true }).catch(() => {})
  }
}

// ---------------------------------------------------------------------------
// read_source: deterministic offline parse (zero fabricated metadata)
// ---------------------------------------------------------------------------

/** Contract-shaped empty candidate; missing metadata stays null/empty. */
function emptyCandidate(): Record<string, unknown> {
  return {
    schema_version: '1.0',
    source_id: null,
    title: null,
    authors: null,
    year: null,
    venue_or_repository: null,
    identifiers: null,
    canonical_url: null,
    retrieved_at: null,
    retrieval_backend: null,
    verification_status: 'candidate',
    artifact_ids: [],
    content_sha256: null,
    extracted_text: null,
    extraction_note: null,
    metadata_gaps: [],
  }
}

/** Report `field` as missing when the candidate value is null/empty. */
function pushGap(gaps: string[], field: string, value: unknown): void {
  const empty =
    value === null ||
    value === undefined ||
    value === '' ||
    (Array.isArray(value) && value.length === 0) ||
    (isRecord(value) && Object.keys(value).length === 0)
  if (empty) gaps.push(field)
}

/**
 * Map a parsed JSON value onto the candidate shape. Only fields actually
 * present in the input are copied — nothing is invented (no fabricated
 * DOI/authors/year/retrieval time). All gap fields are reported in
 * `metadata_gaps`.
 */
function buildCandidateFromJson(parsed: unknown): Record<string, unknown> {
  const out = emptyCandidate()
  if (!isRecord(parsed)) {
    out.metadata_gaps = [...CANDIDATE_GAP_FIELDS]
    return out
  }

  const pick = (key: string): unknown => {
    const value = parsed[key]
    return value === undefined ? null : value
  }

  const sourceId = pick('source_id')
  if (typeof sourceId === 'string' && sourceId !== '') out.source_id = sourceId

  const title = pick('title')
  if (typeof title === 'string' && title !== '') out.title = title

  const authors = pick('authors')
  if (
    Array.isArray(authors) &&
    authors.every((a) => typeof a === 'string' && a.length > 0)
  ) {
    out.authors = authors
  }

  const year = pick('year')
  if (typeof year === 'number' && Number.isInteger(year)) out.year = year

  const venue = pick('venue_or_repository')
  if (typeof venue === 'string' && venue !== '') out.venue_or_repository = venue

  // identifiers: honor an input identifiers object; else map a flat `doi`.
  const identifiers = pick('identifiers')
  if (isRecord(identifiers)) {
    const mapped: Record<string, string> = {}
    for (const key of ['doi', 'arxiv_id', 'pmid'] as const) {
      const value = identifiers[key]
      if (typeof value === 'string' && value !== '') mapped[key] = value
    }
    if (Object.keys(mapped).length > 0) out.identifiers = mapped
  } else {
    const flatDoi = pick('doi')
    if (typeof flatDoi === 'string' && flatDoi !== '') out.identifiers = { doi: flatDoi }
  }

  const canonicalUrl = pick('canonical_url')
  const url = pick('url')
  if (typeof canonicalUrl === 'string' && canonicalUrl !== '') {
    out.canonical_url = canonicalUrl
  } else if (typeof url === 'string' && url !== '') {
    out.canonical_url = url
  }

  const retrievedAt = pick('retrieved_at')
  if (typeof retrievedAt === 'string' && retrievedAt !== '') out.retrieved_at = retrievedAt

  const backend = pick('retrieval_backend')
  if (
    typeof backend === 'string' &&
    (SEARCH_BACKENDS as readonly string[]).includes(backend)
  ) {
    out.retrieval_backend = backend
  }

  const artifactIds = pick('artifact_ids')
  if (
    Array.isArray(artifactIds) &&
    artifactIds.every((a) => typeof a === 'string' && a.length > 0)
  ) {
    out.artifact_ids = artifactIds
  }

  const gaps: string[] = []
  for (const field of CANDIDATE_GAP_FIELDS) {
    pushGap(gaps, field, out[field])
  }
  out.metadata_gaps = gaps
  return out
}

/**
 * Minimal, honest PDF text extraction: only text inside `(...) Tj` operators
 * of uncompressed content streams is recovered. Compressed/scanned PDFs yield
 * little or nothing — the result is labeled with `extraction_note` instead of
 * pretending. Metadata fields are NEVER derived from extracted text.
 */
function extractPdfText(buf: Buffer): { text: string | null; note: string } {
  const latin1 = buf.toString('latin1')
  const matches: string[] = []
  const re = /\(((?:[^()\\]|\\.)*)\)\s*Tj/g
  let match: RegExpExecArray | null
  while ((match = re.exec(latin1)) !== null) {
    matches.push(match[1].replace(/\\([()\\])/g, '$1'))
  }
  const text = matches.join(' ').trim()
  return text
    ? {
        text,
        note:
          'pdf minimal text extraction (uncompressed Tj streams only); metadata fields not populated',
      }
    : {
        text: null,
        note:
          'pdf text unavailable via plain-text fallback (compressed or scanned); metadata fields not populated',
      }
}

/** sha256 hex digest of the file bytes actually read (real, verifiable data). */
function sha256Of(buf: Buffer): string {
  return createHash('sha256').update(buf).digest('hex')
}

/** Tool body for literature_read_source. */
async function readSource(filePath: string): Promise<any> {
  let buf: Buffer
  try {
    buf = await readFile(filePath)
  } catch (error) {
    throw new Error(
      `literature_read_source: cannot read ${filePath}: ${
        error instanceof Error ? error.message : String(error)
      }`,
    )
  }
  const contentSha256 = sha256Of(buf)

  const extension = path.extname(filePath).toLowerCase()
  // JSONL is NOT supported: a multi-record JSONL file has no single-object
  // candidate shape, so it is rejected explicitly (fail-closed) instead of
  // being mis-parsed as one JSON document or silently read as plain text.
  if (extension === '.jsonl') {
    throw new Error(
      'literature_read_source: unsupported .jsonl input — only single-object .json files are supported',
    )
  }
  if (extension === '.json') {
    const text = buf.toString('utf8').replace(/^\uFEFF/, '')
    let parsed: unknown
    try {
      parsed = JSON.parse(text)
    } catch (error) {
      throw new Error(
        `literature_read_source: invalid JSON in ${filePath}: ${
          error instanceof Error ? error.message : String(error)
        }`,
      )
    }
    const candidate = buildCandidateFromJson(parsed)
    candidate.content_sha256 = contentSha256
    candidate.extraction_note = 'json record parsed'
    return candidate
  }

  const header = buf.subarray(0, 5).toString('latin1')
  if (header === '%PDF-') {
    const { text, note } = extractPdfText(buf)
    const candidate = emptyCandidate()
    candidate.content_sha256 = contentSha256
    candidate.extracted_text = text
    candidate.extraction_note = note
    candidate.metadata_gaps = [...CANDIDATE_GAP_FIELDS]
    return candidate
  }

  // Plain-text fallback.
  const text = buf.toString('utf8').replace(/^\uFEFF/, '').trim()
  const candidate = emptyCandidate()
  candidate.content_sha256 = contentSha256
  candidate.extracted_text = text || null
  candidate.extraction_note = 'plain text file read verbatim'
  candidate.metadata_gaps = [...CANDIDATE_GAP_FIELDS]
  return candidate
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

/** Stable compact renderer: the full JSON value as one text block. */
function renderJson(_args: unknown, value: unknown): { type: 'text'; text: string }[] {
  return [{ type: 'text', text: JSON.stringify(value) }]
}

const SOURCE_ROOT_NOTE =
  '前置条件：sourceRoot 必须指向 cumcm-workbench 仓库根（含 toolkit/src/cumcm_toolkit），' +
  '子进程以 sourceRoot 为 cwd、注入 PYTHONPATH=<sourceRoot>/toolkit/src;<sourceRoot> 执行 `python -m cumcm_toolkit.literature.rules`。' +
  'python 解析顺序：LITERATURE_TOOLS_PYTHON 环境变量 → <sourceRoot>/.venv python → PATH 上的 python。'
const FAIL_CLOSED_NOTE =
  '失败语义：子进程非 0 退出、stdout 非 JSON 或契约不符时，工具返回 failed 并附明确 error，绝不返回伪造结果。'
const CANDIDATE_NOTE =
  '候选 ≠ 引用（Phase 0A 政策）：本工具只产出/路由 candidate，未经人工核验不得作为正式引用。'

function buildTools(config: NormalizedConfig) {
  return [
    defineTool({
      name: 'literature_read_source',
      description:
        '离线确定性解析单个文献源文件（PDF/单对象 JSON/纯文本），输出与 literature-source 契约 candidate 状态兼容的候选对象。' +
        'PDF：提取文本（纯文本兜底，仅恢复未压缩 Tj 文本流，质量在 extraction_note 如实标注；压缩/扫描 PDF 可能提取为空）。' +
        'JSON：解析为记录，只复制输入中实际存在的字段。仅支持单对象 .json 文件；.jsonl（JSON Lines）不支持，传入即 failed（fail-closed）。' +
        '绝不补造 DOI/作者/年份/检索时间——缺项保留 null/空并在 metadata_gaps 列出。' +
        'content_sha256 为所读文件字节的 sha256（真实可校验）。' +
        CANDIDATE_NOTE +
        '输入契约：path 为 PDF 或 .json 文件绝对路径（必填）；仅处理用户显式指定的路径。',
      parameters: {
        path: { type: 'string', required: true, description: 'PDF 或 JSON 文件绝对路径' },
      },
      output: {
        schema: {
          type: 'object',
          additionalProperties: true,
          properties: {
            schema_version: { type: 'string' },
            source_id: nullableString,
            title: nullableString,
            authors: nullableStringArray,
            year: nullableInt,
            venue_or_repository: nullableString,
            identifiers: nullableObject,
            canonical_url: nullableString,
            retrieved_at: nullableString,
            retrieval_backend: nullableString,
            verification_status: { type: 'string' },
            artifact_ids: { type: 'array', items: { type: 'string' } },
            content_sha256: nullableString,
            extracted_text: nullableString,
            extraction_note: nullableString,
            metadata_gaps: { type: 'array', items: { type: 'string' } },
          },
        },
        render: renderJson,
      },
      async execute(args) {
        return readSource(args.path)
      },
    }),

    defineTool({
      name: 'literature_route_candidate',
      description:
        '按共享去重规则（shared/knowledge/literature/deduplication.md，参考实现 tests/knowledge/test_literature_knowledge.py）' +
        '对候选记录数组做确定性归一化分组与组内冲突标记。规则引擎在 Python（toolkit/src/cumcm_toolkit/literature/rules.py），' +
        '本工具只做参数转发，TS 侧零规则实现。' +
        '输入契约：candidate 为 JSON 字符串（候选记录数组，每条至少含 id 与 doi/title/url 之一）。' +
        '容量：候选数组经单个 argv 传给子进程，受命令行长度上限约束——建议分批处理（≤~500 条/次）；' +
        '超过安全阈值（约 20000 字符）时工具直接 failed 并提示分批，不会触发底层系统错误。' +
        '输出：{groups, conflicts} —— groups 为分组键→记录 id 列表（doi:…/title:…/url:… 前缀）；' +
        'conflicts 为分组键→冲突标记列表（authors_mismatch / year_mismatch / venue_mismatch / same_doi_diff_metadata），仅列出有冲突的组。' +
        '冲突语义：只标记、不合并、不挑选、不补全——组内元数据冲突的记录保持候选状态，须由人工核验后裁决（人工核验门）。' +
        SOURCE_ROOT_NOTE + FAIL_CLOSED_NOTE + CANDIDATE_NOTE,
      parameters: {
        candidate: {
          type: 'string',
          required: true,
          description: 'JSON 字符串：候选记录数组',
        },
      },
      output: {
        schema: {
          type: 'object',
          additionalProperties: true,
          properties: {
            groups: openObject,
            conflicts: openObject,
          },
        },
        render: renderJson,
      },
      async execute(args, exec) {
        if (args.candidate.length > MAX_CANDIDATE_ARGV_CHARS) {
          throw new Error(
            'literature_route_candidate: candidate payload too large — split into batches of ~500 records',
          )
        }
        const result = await runRulesCli(config, ['--group', args.candidate], exec.signal)
        if (!result.ok) {
          throw new Error(`literature_route_candidate: ${result.error}`)
        }
        const data = result.data
        if (!isRecord(data) || !isRecord(data.groups) || !isRecord(data.conflicts)) {
          throw new Error(
            'literature_route_candidate: rules CLI output missing groups/conflicts',
          )
        }
        return data as any
      },
    }),

    defineTool({
      name: 'literature_search',
      description:
        '文献检索——仅当配置了 backend 且其标识在 allowedDomains 白名单内时可用；否则 blocked（明确错误，不静默降级）。' +
        '网络后端转发未实现：本工具仅做配置门禁 + 授权占位（fail-closed），通过门禁后返回 status=requires-user-authorization 且 candidates 为空，' +
        '等待用户授权真实后端后再转发；绝不伪造检索结果。凭据经 DSH 凭据机制引用，不写死、不硬编码。' +
        '输入契约：query 为检索词（必填）；limit 为可选结果上限。',
      parameters: {
        query: { type: 'string', required: true, description: '检索词' },
        limit: { type: 'integer', description: '结果上限（可选）' },
      },
      output: {
        schema: {
          type: 'object',
          additionalProperties: true,
          properties: {
            backend: { type: 'string' },
            query: { type: 'string' },
            limit: nullableInt,
            status: { type: 'string' },
            candidates: { type: 'array', items: openObject },
          },
        },
        render: renderJson,
      },
      async execute(args) {
        const backend = (config.backend ?? '').trim()
        if (backend === '') {
          throw new Error('literature_search: no literature backend configured')
        }
        const allowed = config.allowedDomains ?? []
        if (!allowed.includes(backend)) {
          throw new Error(
            `literature_search: domain not allowed — backend "${backend}" is not covered by allowedDomains`,
          )
        }
        return {
          backend,
          query: args.query,
          limit: args.limit ?? null,
          status: 'requires-user-authorization',
          candidates: [],
        }
      },
    }),
  ]
}

export function apply(ctx: Context, config: Config): void {
  const sourceRoot = (config.sourceRoot ?? '').trim()
  if (sourceRoot === '') {
    throw new Error(
      'literature-tools: sourceRoot is required — point it at the cumcm-workbench repo root ' +
        '(contains toolkit/src/cumcm_toolkit) so `python -m cumcm_toolkit.literature.rules` resolves. ' +
        'Missing/empty sourceRoot fails plugin startup; it never degrades silently.',
    )
  }
  const normalized: NormalizedConfig = {
    backend: config.backend ?? '',
    allowedDomains: Array.isArray(config.allowedDomains) ? config.allowedDomains : [],
    sourceRoot,
  }
  for (const tool of buildTools(normalized)) {
    ctx.tools.register(tool)
  }
}
