#!/usr/bin/env node
/**
 * cumcm-tools smoke test (plain node, no framework).
 *
 * Asserts, against the BUILT plugin (lib/), that:
 *   1. the plugin registers exactly the 15 cumcm_* tools;
 *   2. bridge failure-closing: missing python → failed; argparse exit-2 with
 *      empty stdout (I-1) → failed without crashing; unknown module → failed;
 *   3. success path (when a cumcm python + cumcmRoot are available): a real
 *      `data.profile` and `data.transform` run over a temp CSV → ok:true with
 *      the expected shape.
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
const libBridge = path.join(pluginRoot, 'lib', 'bridge.js')
if (!existsSync(libIndex) || !existsSync(libBridge)) {
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
 * Detect a usable cumcm python + cumcmRoot for real-bridge checks.
 *
 * Root resolution: `CUMCM_TOOLS_ROOT` (when set, e.g. for out-of-tree
 * verification runs) wins; otherwise walk up from this file to the
 * cumcm-workbench root (pyproject.toml + toolkit/src/cumcm_toolkit markers).
 */
function detectEnv() {
  const override = process.env.CUMCM_TOOLS_ROOT
  const root = (override && existsSync(override))
    ? path.resolve(override)
    : findWorktreeRoot(here)
  if (!root) return { config: null, python: null, tmp: null }
  const venvPython = path.join(root, '.venv', 'Scripts', 'python.exe')
  if (process.platform !== 'win32') {
    // POSIX fallback probe is out of scope; report unavailable.
    return { config: null, python: null, tmp: null }
  }
  if (!existsSync(venvPython)) return { config: null, python: null, tmp: null }
  return {
    config: { cumcmRoot: root, pythonBin: '', toolTimeoutMs: 30000 },
    python: venvPython,
    tmp: mkdtempSync(path.join(tmpdir(), 'cumcm-tools-smoke-')),
  }
}

const plugin = await import(pathToFileURL(libIndex).href)
const bridge = await import(pathToFileURL(libBridge).href)

console.log('== 1. plugin shape + registration ==')
check(
  'plugin name/inject exports',
  plugin.name === 'cumcm-tools' &&
    Array.isArray(plugin.inject) &&
    plugin.inject.includes('tools'),
  `name=${plugin.name} inject=${JSON.stringify(plugin.inject)}`,
)

// Config schema defaults and rejection.
const cfgDefaults = plugin.Config({})
check(
  'Config defaults (cumcmRoot/pythonBin empty, toolTimeoutMs 120000)',
  cfgDefaults.cumcmRoot === '' &&
    cfgDefaults.pythonBin === '' &&
    cfgDefaults.toolTimeoutMs === 120000,
  JSON.stringify(cfgDefaults),
)
let cfgRejected = false
try {
  plugin.Config({ toolTimeoutMs: 'nope' })
} catch {
  cfgRejected = true
}
check('Config rejects invalid input', cfgRejected)

// Minimal fake tools registry; the plugin still runs the REAL defineTool
// (schema compilation + assertSupportedJsonSchema happen at definition time).
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
let applyError = null
try {
  plugin.apply(fakeCtx, { cumcmRoot: '', pythonBin: '', toolTimeoutMs: 120000 })
} catch (error) {
  applyError = error
}
check(
  'apply registers 15 tools without throwing',
  applyError === null && registered.size === 15,
  applyError ? String(applyError) : `registered=${registered.size}`,
)

const EXPECTED_NAMES = [
  'cumcm_data_profile',
  'cumcm_data_transform',
  'cumcm_model_run',
  'cumcm_metrics',
  'cumcm_sensitivity',
  'cumcm_evidence_link',
  'cumcm_citation_link',
  'cumcm_latex_build',
  'cumcm_latex_lint',
  'cumcm_citation_check',
  'cumcm_pdf_inspect',
  'cumcm_result_export',
  'cumcm_workspace_scaffold',
  'cumcm_experiment_record',
  'cumcm_artifact_index',
]
const missing = EXPECTED_NAMES.filter((n) => !registered.has(n))
check('all 15 tool names registered', missing.length === 0, `missing: ${missing.join(', ')}`)

// Spot checks on compiled definitions.
const modelRun = registered.get('cumcm_model_run')
check(
  'cumcm_model_run parameters compile (name/X/y required)',
  modelRun?.parameters?.type === 'object' &&
    Array.isArray(modelRun.parameters.required) &&
    ['name', 'X', 'y'].every((k) => modelRun.parameters.required.includes(k)) &&
    ['name', 'X', 'y', 'seed', 'params'].every((k) => k in modelRun.parameters.properties),
  JSON.stringify(modelRun?.parameters),
)
const exportTool = registered.get('cumcm_result_export')
check(
  'cumcm_result_export parameters include json/csv/latex/out',
  exportTool?.parameters?.properties &&
    ['json', 'csv', 'latex', 'rows', 'caption', 'out'].every(
      (k) => k in exportTool.parameters.properties,
    ) &&
    exportTool.parameters.required.includes('out'),
)
check(
  'cumcm_artifact_index output schema is an array',
  registered.get('cumcm_artifact_index')?.output?.schema?.type === 'array',
)
check(
  'cumcm_data_profile output schema is an object',
  registered.get('cumcm_data_profile')?.output?.schema?.type === 'object',
)

console.log('== 2. bridge failure-closing ==')

// resolvePython throws a clear error when nothing is configured.
let resolveError = null
try {
  await bridge.resolvePython({ cumcmRoot: '', pythonBin: '', toolTimeoutMs: 120000 })
} catch (error) {
  resolveError = error
}
check(
  'resolvePython throws when unconfigured (mentions cumcmRoot/pythonBin)',
  resolveError instanceof Error && /cumcmRoot|pythonBin/.test(resolveError.message),
  String(resolveError),
)

// Nonexistent pythonBin → spawn error → failed, never a crash.
const fakePython = path.join(pluginRoot, '__no_such_python__.exe')
const missingPython = await bridge.runPythonTool(
  { cumcmRoot: '', pythonBin: fakePython, toolTimeoutMs: 5000 },
  'data.profile',
  ['--path', 'nope.csv'],
)
check(
  'runPythonTool fails closed on missing python',
  missingPython.ok === false &&
    typeof missingPython.error === 'string' &&
    missingPython.error.length > 0,
  JSON.stringify(missingPython),
)

const env = detectEnv()
if (env.config) {
  // I-1 contract: argparse failure (missing --input) → SystemExit(2), usage on
  // stderr, EMPTY stdout → bridge returns failed with a non-empty error.
  const i1 = await bridge.runPythonTool(
    env.config,
    'data.transform',
    ['--steps', '[]', '--output', path.join(env.tmp, 'out.csv')],
  )
  check(
    'I-1: argparse exit 2 + empty stdout → failed, no crash',
    i1.ok === false && typeof i1.error === 'string' && i1.error.length > 0,
    JSON.stringify(i1),
  )

  // Unknown module → non-zero exit + empty stdout → failed.
  const unknownModule = await bridge.runPythonTool(env.config, 'no_such_module', [])
  check(
    'unknown module fails closed (non-zero exit, empty stdout)',
    unknownModule.ok === false &&
      typeof unknownModule.error === 'string' &&
      unknownModule.error.length > 0,
    JSON.stringify(unknownModule),
  )

  // Tool body end-to-end with a REAL config: apply to a second registry so
  // the body's bridge resolves the cumcm python, then call execute with a
  // missing required CLI arg → argparse exit 2 → bridge fails → body throws
  // (the registry turns it into a failed tool result).
  const registeredReal = new Map()
  const fakeCtxReal = {
    tools: {
      register(def) {
        registeredReal.set(def.name, def)
        return () => registeredReal.delete(def.name)
      },
    },
  }
  plugin.apply(fakeCtxReal, env.config)
  const transformTool = registeredReal.get('cumcm_data_transform')
  let bodyError = null
  try {
    await transformTool.execute(
      { input: path.join(env.tmp, 'missing.csv'), steps: '[]', output: path.join(env.tmp, 'out.csv') },
      { signal: new AbortController().signal },
    )
  } catch (error) {
    bodyError = error
  }
  check(
    'tool body throws on bridge failure',
    bodyError instanceof Error && /cumcm_data_transform/.test(bodyError.message),
    String(bodyError),
  )
} else {
  console.log('SKIP  I-1 / unknown-module / body-throw checks (no cumcm python available)')
}

console.log('== 3. success path (real python + cumcmRoot) ==')
if (env.config) {
  const csvPath = path.join(env.tmp, 'profile_input.csv')
  writeFileSync(csvPath, 'a,b\n1,2\n3,4\n5,6\n', 'utf8')

  const prof = await bridge.runPythonTool(env.config, 'data.profile', [
    '--path', csvPath,
    '--key-columns', 'a',
  ])
  check(
    'success: data.profile on tmp CSV → ok:true + profile object',
    prof.ok === true && prof.data !== null && typeof prof.data === 'object',
    JSON.stringify(prof),
  )
  if (prof.ok) {
    check(
      'success: profile shape (row_count/columns/key_uniqueness)',
      prof.data.row_count === 3 &&
        Array.isArray(prof.data.columns) &&
        prof.data.key_uniqueness.a === 3,
      JSON.stringify(prof.data),
    )
  }

  const outCsv = path.join(env.tmp, 'transform_out.csv')
  const steps = JSON.stringify([{ op: 'drop_columns', columns: ['b'] }])
  const tform = await bridge.runPythonTool(env.config, 'data.transform', [
    '--input', csvPath,
    '--steps', steps,
    '--output', outCsv,
  ])
  check(
    'success: data.transform → ok:true + {steps_applied, warnings}',
    tform.ok === true &&
      tform.data.steps_applied === 1 &&
      Array.isArray(tform.data.warnings) &&
      existsSync(outCsv),
    JSON.stringify(tform),
  )

  // Regression (review finding): stdout may carry leading log lines before the
  // JSON result — the bridge must parse the LAST non-empty line. Inject a
  // sitecustomize.py (found via the bridge's appended PYTHONPATH) that prints
  // two noise lines at interpreter startup, then run the real CLI. Pre-fix
  // (first-line parsing) this fails with "invalid JSON output".
  writeFileSync(
    path.join(env.tmp, 'sitecustomize.py'),
    [
      'print("noisy stdout line 1")',
      'print("noisy stdout line 2")',
      '',
    ].join('\n'),
    'utf8',
  )
  const savedPythonPath = process.env.PYTHONPATH
  process.env.PYTHONPATH = env.tmp
  let noisy
  try {
    noisy = await bridge.runPythonTool(env.config, 'data.profile', [
      '--path', csvPath,
      '--key-columns', 'a',
    ])
  } finally {
    if (savedPythonPath === undefined) delete process.env.PYTHONPATH
    else process.env.PYTHONPATH = savedPythonPath
  }
  check(
    'last-line JSON: leading stdout log lines → still ok:true (last line parsed)',
    noisy.ok === true &&
      noisy.data.row_count === 3 &&
      noisy.data.key_uniqueness.a === 3,
    JSON.stringify(noisy),
  )
} else {
  console.log('SKIP  success-path checks (no cumcm python available)')
}

if (env.tmp) rmSync(env.tmp, { recursive: true, force: true })

console.log('')
console.log(`${passed} passed, ${failed} failed`)
process.exit(failed === 0 ? 0 : 1)
