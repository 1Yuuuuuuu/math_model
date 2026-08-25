#!/usr/bin/env node
/**
 * literature-tools smoke test (plain node, no framework).
 *
 * Asserts, against the BUILT plugin (lib/), that:
 *   1. the plugin registers exactly the 3 literature_* tools;
 *   2. Config rejects a missing sourceRoot (schema required → startup failure)
 *      and apply() throws on an empty sourceRoot;
 *   3. literature_search is fail-closed: no backend → blocked
 *      ("no literature backend configured"); backend not covered by
 *      allowedDomains → blocked ("domain not allowed"); gate pass → an
 *      authorization placeholder with an EMPTY candidate list (no fabricated
 *      results);
 *   4. literature_read_source on a tmp JSON file → candidate shape with
 *      verification_status "candidate" and metadata_gaps, and fails closed on
 *      a missing file;
 *   5. literature_route_candidate runs the REAL Python rules CLI once (when a
 *      cumcm python + sourceRoot are available) → {groups, conflicts} shape,
 *      and fails closed on invalid candidate JSON.
 *
 * Exit code 0 = all mandatory checks passed; 1 = any failure.
 */
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const pluginRoot = path.resolve(here, '..')

let passed = 0
let failed = 0
function check(name, cond, detail = '') {
  if (cond) {
    passed += 1
    console.log(`PASS  ${name}`)
  } else {
    failed += 1
    console.error(`FAIL  ${name}${detail ? ` — ${detail}` : ''}`)
  }
}

const libIndex = path.join(pluginRoot, 'lib', 'index.js')
if (!existsSync(libIndex)) {
  console.error('FAIL  lib/ is not built — run `pnpm build` before `pnpm test`')
  process.exit(1)
}

/** Walk up from `start` to the cumcm-workbench root (pyproject.toml marker). */
function findWorktreeRoot(start) {
  let dir = start
  for (let i = 0; i < 8; i += 1) {
    if (
      existsSync(path.join(dir, 'pyproject.toml')) &&
      existsSync(path.join(dir, 'toolkit', 'src', 'cumcm_toolkit'))
    ) {
      return dir
    }
    dir = path.resolve(dir, '..')
  }
  return null
}

/**
 * Detect a usable sourceRoot + python for real-bridge checks.
 *
 * Root resolution: `LITERATURE_TOOLS_SOURCE_ROOT` (when set, e.g. for
 * out-of-tree verification runs) wins; otherwise walk up from this file to the
 * cumcm-workbench root. Python: Windows `sourceRoot/.venv/Scripts/python.exe`
 * (the plugin's own resolvePython order; POSIX probe is out of scope).
 */
function detectEnv() {
  const override = process.env.LITERATURE_TOOLS_SOURCE_ROOT
  const root = override && existsSync(override)
    ? path.resolve(override)
    : findWorktreeRoot(here)
  if (!root) return { config: null }
  if (process.platform !== 'win32') return { config: null }
  const venvPython = path.join(root, '.venv', 'Scripts', 'python.exe')
  if (!existsSync(venvPython)) return { config: null }
  return { config: { backend: '', allowedDomains: [], sourceRoot: root } }
}

const plugin = await import(pathToFileURL(libIndex).href)

console.log('== 1. plugin shape + registration ==')
check(
  'plugin name/inject exports',
  plugin.name === 'literature-tools' &&
    Array.isArray(plugin.inject) &&
    plugin.inject.includes('tools'),
  `name=${plugin.name} inject=${JSON.stringify(plugin.inject)}`,
)

// Config schema: backend/allowedDomains default; sourceRoot REQUIRED.
let cfgMissingSourceRoot = false
try {
  plugin.Config({ backend: '', allowedDomains: [] })
} catch {
  cfgMissingSourceRoot = true
}
check(
  'Config rejects missing sourceRoot (schema required → startup failure)',
  cfgMissingSourceRoot,
)

let cfgOk = null
try {
  cfgOk = plugin.Config({
    backend: 'paper-search',
    allowedDomains: ['example.com'],
    sourceRoot: 'C:\\worktree',
  })
} catch (error) {
  cfgOk = error
}
check(
  'Config accepts backend/allowedDomains/sourceRoot',
  cfgOk &&
    cfgOk.backend === 'paper-search' &&
    Array.isArray(cfgOk.allowedDomains) &&
    cfgOk.allowedDomains[0] === 'example.com' &&
    cfgOk.sourceRoot === 'C:\\worktree',
  JSON.stringify(cfgOk),
)

/** Minimal fake tools registry (real defineTool schema compilation still runs). */
function makeRegistry(config) {
  const registered = new Map()
  const fakeCtx = {
    tools: {
      register(def) {
        if (registered.has(def.name)) throw new Error(`duplicate tool ${def.name}`)
        registered.set(def.name, def)
        return () => registered.delete(def.name)
      },
    },
  }
  plugin.apply(fakeCtx, config)
  return registered
}

let applyError = null
try {
  plugin.apply(
    { tools: { register() { return () => {} } } },
    { backend: '', allowedDomains: [], sourceRoot: '' },
  )
} catch (error) {
  applyError = error
}
check(
  'apply throws when sourceRoot empty (startup failure, no silent degrade)',
  applyError instanceof Error && /sourceRoot/.test(applyError.message),
  String(applyError),
)

let registered
try {
  registered = makeRegistry({ backend: '', allowedDomains: [], sourceRoot: 'C:\\worktree' })
  applyError = null
} catch (error) {
  applyError = error
}
check(
  'apply registers 3 tools without throwing',
  applyError === null && registered.size === 3,
  applyError ? String(applyError) : `registered=${registered.size}`,
)

const EXPECTED_NAMES = [
  'literature_read_source',
  'literature_route_candidate',
  'literature_search',
]
const missing = EXPECTED_NAMES.filter((n) => !registered.has(n))
check('all 3 tool names registered', missing.length === 0, `missing: ${missing.join(', ')}`)

const routeTool = registered.get('literature_route_candidate')
check(
  'route_candidate parameters compile (candidate required)',
  routeTool?.parameters?.type === 'object' &&
    Array.isArray(routeTool.parameters.required) &&
    routeTool.parameters.required.includes('candidate') &&
    'candidate' in routeTool.parameters.properties,
  JSON.stringify(routeTool?.parameters),
)
const searchTool = registered.get('literature_search')
check(
  'search parameters compile (query required, limit optional)',
  searchTool?.parameters?.properties &&
    'query' in searchTool.parameters.properties &&
    'limit' in searchTool.parameters.properties &&
    Array.isArray(searchTool.parameters.required) &&
    searchTool.parameters.required.includes('query'),
  JSON.stringify(searchTool?.parameters),
)
const readTool = registered.get('literature_read_source')
check(
  'read_source parameters compile (path required)',
  readTool?.parameters?.properties &&
    'path' in readTool.parameters.properties &&
    Array.isArray(readTool.parameters.required) &&
    readTool.parameters.required.includes('path'),
  JSON.stringify(readTool?.parameters),
)

console.log('== 2. search gate (fail-closed) ==')
const signal = new AbortController().signal

const noBackend = makeRegistry({ backend: '', allowedDomains: [], sourceRoot: 'C:\\worktree' })
let searchErr = null
try {
  await noBackend.get('literature_search').execute({ query: 'x' }, { signal })
} catch (error) {
  searchErr = error
}
check(
  'search without backend → blocked (no literature backend configured)',
  searchErr instanceof Error && /no literature backend configured/.test(searchErr.message),
  String(searchErr),
)

const domainBlocked = makeRegistry({
  backend: 'paper-search',
  allowedDomains: ['example.com'],
  sourceRoot: 'C:\\worktree',
})
let domainErr = null
try {
  await domainBlocked.get('literature_search').execute({ query: 'x' }, { signal })
} catch (error) {
  domainErr = error
}
check(
  'search with backend not in allowedDomains → blocked (domain not allowed)',
  domainErr instanceof Error && /domain not allowed/.test(domainErr.message),
  String(domainErr),
)

const gatePass = makeRegistry({
  backend: 'paper-search',
  allowedDomains: ['paper-search'],
  sourceRoot: 'C:\\worktree',
})
const authResult = await gatePass.get('literature_search').execute(
  { query: 'linear regression', limit: 5 },
  { signal },
)
check(
  'search gate pass → authorization placeholder, empty candidates (no fabricated results)',
  authResult.status === 'requires-user-authorization' &&
    Array.isArray(authResult.candidates) &&
    authResult.candidates.length === 0 &&
    authResult.backend === 'paper-search' &&
    authResult.query === 'linear regression' &&
    authResult.limit === 5,
  JSON.stringify(authResult),
)

console.log('== 3. read_source (JSON file → candidate shape) ==')
const tmp = mkdtempSync(path.join(tmpdir(), 'literature-tools-smoke-'))
try {
  const jsonPath = path.join(tmp, 'candidate.json')
  writeFileSync(
    jsonPath,
    JSON.stringify({ id: 'rec1', title: 'Test Paper', authors: ['Alice'], doi: '10.1/x' }),
    'utf8',
  )
  const cand = await readTool.execute({ path: jsonPath }, { signal })
  check(
    'read_source JSON → candidate shape (verification_status candidate)',
    cand && typeof cand === 'object' && cand.verification_status === 'candidate',
    JSON.stringify(cand),
  )
  check(
    'read_source preserves present fields (title/authors/identifiers)',
    cand.title === 'Test Paper' &&
      Array.isArray(cand.authors) &&
      cand.authors[0] === 'Alice' &&
      cand.identifiers?.doi === '10.1/x',
    JSON.stringify(cand),
  )
  check(
    'read_source marks missing fields as metadata_gaps (year/source_id)',
    Array.isArray(cand.metadata_gaps) &&
      cand.metadata_gaps.includes('year') &&
      cand.metadata_gaps.includes('source_id') &&
      cand.year === null &&
      cand.source_id === null,
    JSON.stringify(cand.metadata_gaps),
  )
  check(
    'read_source computes content_sha256 from the actual file bytes',
    typeof cand.content_sha256 === 'string' && /^[a-f0-9]{64}$/.test(cand.content_sha256),
    String(cand.content_sha256),
  )

  let readErr = null
  try {
    await readTool.execute({ path: path.join(tmp, 'nope.json') }, { signal })
  } catch (error) {
    readErr = error
  }
  check(
    'read_source missing file → failed',
    readErr instanceof Error && /literature_read_source/.test(readErr.message),
    String(readErr),
  )

  // I2: multi-line .jsonl is NOT supported → explicit fail-closed rejection
  // (never mis-parsed as one JSON document, never silently read as text).
  const jsonlPath = path.join(tmp, 'records.jsonl')
  writeFileSync(jsonlPath, '{"id": "a", "title": "One"}\n{"id": "b", "title": "Two"}\n', 'utf8')
  let jsonlErr = null
  try {
    await readTool.execute({ path: jsonlPath }, { signal })
  } catch (error) {
    jsonlErr = error
  }
  check(
    'read_source .jsonl multi-line → failed (unsupported .jsonl, fail-closed)',
    jsonlErr instanceof Error && /unsupported \.jsonl/.test(jsonlErr.message),
    String(jsonlErr),
  )
} finally {
  rmSync(tmp, { recursive: true, force: true })
}

console.log('== 3b. route_candidate oversized payload pre-check (I1) ==')
let tooLargeErr = null
try {
  await noBackend
    .get('literature_route_candidate')
    .execute({ candidate: 'x'.repeat(21_000) }, { signal })
} catch (error) {
  tooLargeErr = error
}
check(
  'route_candidate oversized candidate → clear batching error (no ENAMETOOLONG)',
  tooLargeErr instanceof Error &&
    /literature_route_candidate/.test(tooLargeErr.message) &&
    /candidate payload too large/.test(tooLargeErr.message),
  String(tooLargeErr),
)
// Right-sized payload (small but valid) passes the pre-check and reaches the
// Python bridge only when a real env exists — here it must fail with the
// bridge-level python resolution error, NOT the size pre-check.
// Force an unresolvable python (LITERATURE_TOOLS_PYTHON → nonexistent path) so
// the bridge deterministically fails regardless of whether the ambient
// machine happens to have a real cumcmRoot at the sample sourceRoot.
const prevPython = process.env.LITERATURE_TOOLS_PYTHON
process.env.LITERATURE_TOOLS_PYTHON = path.join(tmpdir(), 'cumcm-tools-smoke-no-such-python.exe')
let smallErr = null
try {
  await noBackend
    .get('literature_route_candidate')
    .execute({ candidate: JSON.stringify([{ id: 'a', doi: '10.1/x' }]) }, { signal })
} catch (error) {
  smallErr = error
} finally {
  if (prevPython === undefined) delete process.env.LITERATURE_TOOLS_PYTHON
  else process.env.LITERATURE_TOOLS_PYTHON = prevPython
}
check(
  'route_candidate small payload passes pre-check (fails later at bridge, not on size)',
  smallErr instanceof Error &&
    !/candidate payload too large/.test(smallErr.message),
  String(smallErr),
)

console.log('== 4. route_candidate walks the real Python rules CLI ==')
const env = detectEnv()
if (env.config) {
  const reg = makeRegistry(env.config)
  const rc = reg.get('literature_route_candidate')
  const candidates = [
    { id: 'a', doi: '10.1000/ABC', title: 'One', authors: ['A'], year: 2020, venue_or_repository: 'V' },
    { id: 'b', doi: '10.1000/abc', title: 'Two', authors: ['B'], year: 2021, venue_or_repository: 'V' },
    { id: 'c', title: 'A Novel Method' },
    { id: 'd', title: 'A  Novel  Method!' },
  ]
  let result = null
  let rcError = null
  try {
    result = await rc.execute({ candidate: JSON.stringify(candidates) }, { signal })
  } catch (error) {
    rcError = error
  }
  check(
    'route_candidate → {groups, conflicts} shape from real rules CLI',
    rcError === null &&
      result &&
      typeof result.groups === 'object' &&
      typeof result.conflicts === 'object',
    rcError ? String(rcError) : JSON.stringify(result),
  )
  if (result) {
    const doiGroup = result.groups['doi:10.1000/abc']
    const titleGroup = result.groups['title:anovelmethod']
    check(
      'route_candidate → DOI case-insensitive group',
      Array.isArray(doiGroup) &&
        doiGroup.includes('a') &&
        doiGroup.includes('b'),
      JSON.stringify(result.groups),
    )
    check(
      'route_candidate → title-normalized group',
      Array.isArray(titleGroup) && titleGroup.length === 2,
      JSON.stringify(result.groups),
    )
    check(
      'route_candidate → conflict flags (same_doi_diff_metadata)',
      Array.isArray(result.conflicts['doi:10.1000/abc']) &&
        result.conflicts['doi:10.1000/abc'].includes('same_doi_diff_metadata'),
      JSON.stringify(result.conflicts),
    )
  }

  let badJsonErr = null
  try {
    await rc.execute({ candidate: '{bad' }, { signal })
  } catch (error) {
    badJsonErr = error
  }
  check(
    'route_candidate invalid candidate JSON → failed',
    badJsonErr instanceof Error && /literature_route_candidate/.test(badJsonErr.message),
    String(badJsonErr),
  )
} else {
  console.log('SKIP  route_candidate real-CLI checks (no cumcm python + sourceRoot available)')
}

console.log('')
console.log(`${passed} passed, ${failed} failed`)
process.exit(failed === 0 ? 0 : 1)
