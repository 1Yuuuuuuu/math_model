from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover - dev dep (pyyaml) must be installed
    yaml = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[3]
PRESET = ROOT / "adapters/dsh/presets/cumcm-agent/cordis.yml"

CUCM_TOOLS_LIB = ROOT / "adapters/dsh/plugins/cumcm-tools/lib/index.js"
CUCM_TOOLS_BRIDGE = ROOT / "adapters/dsh/plugins/cumcm-tools/lib/bridge.js"
LIT_TOOLS_LIB = ROOT / "adapters/dsh/plugins/literature-tools/lib/index.js"

# The preset is a patch layer: a top-level list with exactly one `- insert:`
# entry holding the two plugin rows, in the plugin contract's row shape.
EXPECTED_PLUGIN_IDS = {"cumcm-tools", "literature-tools"}

# Config key sets per plugin, mirroring the plugins' Config contracts
# (adapters/dsh/plugins/*/cordis.patch.yml and src/index.ts).
EXPECTED_CONFIG_KEYS = {
    "cumcm-tools": ("cumcmRoot", "pythonBin", "toolTimeoutMs"),
    "literature-tools": ("backend", "allowedDomains", "sourceRoot"),
}

# Keys the preset declares REQUIRED: an unconfigured preset must fail startup
# (fail-closed), never degrade silently.
REQUIRED_KEYS = {
    "cumcm-tools": ("cumcmRoot", "pythonBin"),
    "literature-tools": ("sourceRoot",),
}

# Patterns that would reveal a hardcoded machine path inside the preset.
_MACHINE_PATH = re.compile(
    r"(^|[\\/:])([A-Za-z]:[\\/]|Users[\\/]|home[\\/]|\.venv[\\/]|C:\\|/mnt/|/home/)",
    re.IGNORECASE,
)


def _skip_without_pyyaml() -> None:
    if yaml is None:
        pytest.skip("pyyaml is not installed (dev dependency)")


def _preset_rows() -> dict[str, dict]:
    """Parse the preset and return {plugin_id: row} for its insert entries."""
    _skip_without_pyyaml()
    assert PRESET.is_file(), f"preset file missing: {PRESET}"
    data = yaml.safe_load(PRESET.read_text(encoding="utf-8"))
    assert isinstance(data, list), "preset must be a top-level list (patch layer)"
    inserts = [entry for entry in data if isinstance(entry, dict) and "insert" in entry]
    assert len(inserts) == 1, "preset must contain exactly one `- insert:` entry"
    rows = inserts[0]["insert"]
    assert isinstance(rows, list), "`insert` must hold a list of plugin rows"
    by_id: dict[str, dict] = {}
    for row in rows:
        assert isinstance(row, dict), "each insert row must be a map"
        by_id[row["id"]] = row
    return by_id


def test_preset_composes_both_plugins() -> None:
    """① The preset composes cumcm-tools + literature-tools."""
    rows = _preset_rows()
    assert set(rows) == EXPECTED_PLUGIN_IDS, f"unexpected plugin ids: {sorted(rows)}"
    for plugin_id, row in rows.items():
        assert row["name"] == plugin_id, f"{plugin_id} row must name itself"
        assert isinstance(row.get("config"), dict), f"{plugin_id} must carry a config map"


def test_preset_config_keys_complete() -> None:
    """③ With the required keys present, the config shape matches the contracts."""
    rows = _preset_rows()
    for plugin_id, keys in EXPECTED_CONFIG_KEYS.items():
        config = rows[plugin_id]["config"]
        assert set(config) == set(keys), (
            f"{plugin_id} config keys {sorted(config)} != expected {sorted(keys)}"
        )
    # Defaults from the plugin contracts that the preset keeps stable.
    assert rows["cumcm-tools"]["config"]["toolTimeoutMs"] == 120000
    assert rows["literature-tools"]["config"]["backend"] == ""
    assert rows["literature-tools"]["config"]["allowedDomains"] == []


def test_preset_required_keys_are_empty_placeholders_with_required_notes() -> None:
    """
    Required keys are EMPTY placeholders (never hardcoded machine paths) and
    the file documents each one as REQUIRED next to its key line.
    """
    rows = _preset_rows()
    lines = PRESET.read_text(encoding="utf-8").splitlines()
    for plugin_id, keys in REQUIRED_KEYS.items():
        for key in keys:
            assert rows[plugin_id]["config"][key] == "", (
                f"{plugin_id}.{key} must be an empty placeholder, got "
                f"{rows[plugin_id]['config'][key]!r}"
            )
            # The REQUIRED note sits in the comment window ending at the key line.
            key_line = next(
                i for i, line in enumerate(lines)
                if re.match(rf"^\s*{re.escape(key)}:", line)
            )
            window = "\n".join(lines[max(0, key_line - 4): key_line + 1])
            assert "REQUIRED" in window, (
                f"{plugin_id}.{key} must be documented as REQUIRED near its key line"
            )


def test_preset_contains_no_hardcoded_machine_paths() -> None:
    """No machine-specific path appears anywhere in the preset (values or notes)."""
    text = PRESET.read_text(encoding="utf-8")
    for match in _MACHINE_PATH.finditer(text):
        pytest.fail(f"hardcoded machine path in preset: {match.group(0)!r}")
    # Every config string value must be an empty placeholder; the only
    # non-string leaf is the numeric timeout.
    rows = _preset_rows()
    for plugin_id, row in rows.items():
        for key, value in row["config"].items():
            if isinstance(value, str):
                assert value == "", (
                    f"{plugin_id}.{key} must be an empty placeholder, got {value!r}"
                )


# ---------------------------------------------------------------------------
# Fail-closed semantics of the REQUIRED keys.
#
# Tier note (brief: "若受限沙盒不可行，退而求其次断言 Config schema 拒绝 +
# apply 抛错路径"): this sandbox cannot write to DSH_HOME (C:\\Users\\YU\\.dsh
# is read-only here), so a real scratch-profile Loader boot of the preset is
# not executable from these tests. Instead, these tests load the BUILT plugin
# libs (the same artifacts `dsh` would compose) and assert the exact
# fail-closed seams the preset's REQUIRED keys rely on:
#   - literature-tools: Config schema rejects a missing sourceRoot and
#     apply() throws on an empty sourceRoot (plugin startup failure);
#   - cumcm-tools: resolvePython() throws a clear cumcmRoot/pythonBin error
#     when both are unconfigured AND `uv` is not on PATH (the bridge's own
#     order is pythonBin → cumcmRoot/.venv python → `uv` on PATH → throw).
#     The "no uv" premise is forced deterministically by stripping uv from
#     PATH inside the probe, so the assertion holds on machines with or
#     without uv installed. The uv-on-PATH branch is covered separately: it
#     must NOT throw, and a tool call with an empty cumcmRoot must still fail
#     closed (never fabricate a result).
# A full Loader/patch startup-failure e2e belongs to Task 7's real-composition
# suite (tests/e2e/test_dsh_real_composition.py), which has scratch-profile
# write access.
# ---------------------------------------------------------------------------

NODE_ASSERT_SCRIPT = r"""
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const result = {}

// literature-tools: Config schema requires sourceRoot.
const lit = await import(pathToFileURL(%(litIndex)r).href)
try {
  lit.Config({ backend: '', allowedDomains: [] })
  result.litMissingSourceRootRejected = false
} catch {
  result.litMissingSourceRootRejected = true
}

// literature-tools: apply() with an empty sourceRoot must throw (startup
// failure, never silent degrade).
let applyErr = null
try {
  lit.apply(
    { tools: { register() { return () => {} } } },
    { backend: '', allowedDomains: [], sourceRoot: '' },
  )
} catch (error) {
  applyErr = error
}
result.litApplyThrew = applyErr instanceof Error && /sourceRoot/.test(applyErr.message)

// literature-tools: a fully configured shape passes Config and apply().
const configured = lit.Config({
  backend: 'paper-search',
  allowedDomains: ['paper-search'],
  sourceRoot: 'D:/worktree',
})
result.litConfiguredOk =
  configured.backend === 'paper-search' &&
  configured.allowedDomains.length === 1 &&
  configured.sourceRoot === 'D:/worktree'

// cumcm-tools: load the built plugin + bridge.
const cumcm = await import(pathToFileURL(%(cumcmIndex)r).href)
const bridge = await import(pathToFileURL(%(cumcmBridge)r).href)

// Deterministic "uv not on PATH" premise: rebuild PATH without any directory
// that holds a uv / uv.exe / uv.cmd / uv.bat executable (mirrors the bridge's
// commandOnPath probe), so the throw assertion holds regardless of whether
// this machine has uv installed.
function stripUvFromPath() {
  const exts = process.platform === 'win32' ? ['.exe', '.cmd', '.bat', ''] : ['']
  return (process.env.PATH ?? '')
    .split(path.delimiter)
    .filter((dir) => dir !== '' && !exts.some((ext) => existsSync(path.join(dir, 'uv' + ext))))
    .join(path.delimiter)
}

const savedPath = process.env.PATH
process.env.PATH = stripUvFromPath()
let resolveErr = null
try {
  await bridge.resolvePython({ cumcmRoot: '', pythonBin: '', toolTimeoutMs: 120000 })
} catch (error) {
  resolveErr = error
}
process.env.PATH = savedPath
result.cumcmResolveThrewNoUv =
  resolveErr instanceof Error && /cumcmRoot|pythonBin/.test(resolveErr.message)

// uv-on-PATH branch: with a stub `uv` on PATH, resolvePython takes the uv
// branch (returns ['uv', 'run'], does NOT throw), and a tool call with an
// empty cumcmRoot still FAILS CLOSED — the stub exits non-zero (POSIX) or
// cannot be spawned as a bare .cmd (Windows EINVAL), so the bridge surfaces a
// failure instead of fabricating a result.
const stubDir = mkdtempSync(path.join(tmpdir(), 'cumcm-preset-uv-'))
try {
  const uvStub = path.join(stubDir, process.platform === 'win32' ? 'uv.cmd' : 'uv')
  writeFileSync(
    uvStub,
    process.platform === 'win32' ? '@exit /b 1\r\n' : '#!/bin/sh\nexit 1\n',
    { mode: 0o755 },
  )
  process.env.PATH = stubDir + path.delimiter + savedPath
  let uvResolve = null
  let uvResolveErr = null
  try {
    uvResolve = await bridge.resolvePython({ cumcmRoot: '', pythonBin: '', toolTimeoutMs: 120000 })
  } catch (error) {
    uvResolveErr = error
  }
  result.uvOnPathResolvesToUvRun =
    uvResolveErr === null &&
    Array.isArray(uvResolve) &&
    uvResolve[0] === 'uv' &&
    uvResolve[1] === 'run'

  let uvTool = null
  let uvToolErr = null
  try {
    uvTool = await bridge.runPythonTool(
      { cumcmRoot: '', pythonBin: '', toolTimeoutMs: 5000 },
      'data.profile',
      ['--path', 'nope.csv'],
    )
  } catch (error) {
    uvToolErr = error
  }
  result.uvOnPathEmptyRootFailsClosed =
    (uvTool !== null &&
      uvTool.ok === false &&
      typeof uvTool.error === 'string' &&
      uvTool.error.length > 0) ||
    uvToolErr instanceof Error
} finally {
  process.env.PATH = savedPath
  rmSync(stubDir, { recursive: true, force: true })
}

// cumcm-tools: a configured pythonBin is honored by resolvePython.
const resolved = await bridge.resolvePython({
  cumcmRoot: '',
  pythonBin: 'D:/worktree/.venv/Scripts/python.exe',
  toolTimeoutMs: 120000,
})
result.cumcmConfiguredOk = resolved[0] === 'D:/worktree/.venv/Scripts/python.exe'

console.log(JSON.stringify(result))
"""


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH (plugin fail-closed checks need it)")
    return node


def test_fail_closed_when_required_config_missing() -> None:
    """
    ② Missing REQUIRED config → plugin startup failure (fail-closed): assert
    the Config-schema rejection and apply/resolvePython throw paths of the
    BUILT plugin libs that the preset's REQUIRED keys depend on.
    """
    node = _node()
    for lib in (CUCM_TOOLS_LIB, CUCM_TOOLS_BRIDGE, LIT_TOOLS_LIB):
        assert lib.is_file(), f"plugin lib not built (run pnpm build): {lib}"

    script = NODE_ASSERT_SCRIPT % {
        "litIndex": LIT_TOOLS_LIB.as_posix(),
        "cumcmIndex": CUCM_TOOLS_LIB.as_posix(),
        "cumcmBridge": CUCM_TOOLS_BRIDGE.as_posix(),
    }
    proc = subprocess.run(
        [node, "--input-type=module", "-e", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"node fail-closed probe failed\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    result = json.loads(proc.stdout.strip().splitlines()[-1])

    # literature-tools REQUIRED sourceRoot: schema + apply double protection.
    assert result["litMissingSourceRootRejected"] is True, (
        "literature-tools Config must reject a missing sourceRoot "
        "(schema required → startup failure)"
    )
    assert result["litApplyThrew"] is True, (
        "literature-tools apply() must throw on an empty sourceRoot "
        "(startup failure, no silent degrade)"
    )
    # cumcm-tools REQUIRED cumcmRoot/pythonBin: with `uv` stripped from PATH,
    # resolve fails closed with a clear error (deterministic on any machine).
    assert result["cumcmResolveThrewNoUv"] is True, (
        "cumcm-tools resolvePython must throw a clear cumcmRoot/pythonBin "
        "error when both are unconfigured and `uv` is not on PATH (fail-closed)"
    )
    # uv-on-PATH branch: resolvePython takes the uv branch (no throw), and a
    # tool call with an empty cumcmRoot still fails closed (never fabricated).
    assert result["uvOnPathResolvesToUvRun"] is True, (
        "with `uv` on PATH, cumcm-tools resolvePython must return ['uv', 'run'] "
        "instead of throwing"
    )
    assert result["uvOnPathEmptyRootFailsClosed"] is True, (
        "with `uv` on PATH and an empty cumcmRoot, a cumcm-tools tool call "
        "must still fail closed (ok:false or bridge error), never fabricate a result"
    )
    # Configured shapes must keep working (the preset, once filled, is valid).
    assert result["litConfiguredOk"] is True, "configured literature-tools shape must pass"
    assert result["cumcmConfiguredOk"] is True, "configured cumcm-tools pythonBin must resolve"


def test_preset_parseable_by_yaml() -> None:
    """The preset file itself must be valid YAML (structure sanity)."""
    _skip_without_pyyaml()
    _preset_rows()
