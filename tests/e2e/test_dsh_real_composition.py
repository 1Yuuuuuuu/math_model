"""E2E: real composition of the cumcm-tools dsh plugin on a scratch profile.

链路（Phase 7 / plan Task 7）：
  ① 临时 DSH_HOME（pytest tmp_path）→ `dsh plugin --profile scratch add
     link:<cumcm-tools 本地路径>`。
     —— npm registry 不可达是已知约束：link: 本地路径全程离线可行（pnpm 以
     junction 复用插件目录自身 node_modules —— 含补全的 peer 依赖；
     pnpm-workspace.yaml 的 autoInstallPeers=false 不触发联网安装）。
  ② `dsh --profile scratch --dump-config` 断言 cumcm-tools 层
     （id/name/config 默认值 cumcmRoot=''/pythonBin=''/toolTimeoutMs=120000）。
  ③ Loader 启动：以 node 直跑 dsh 的 lib/bin.js（与 dsh.ps1 等价，绕过
     PowerShell 执行策略），再经 @deepseek-ai/dsh-app-boot.boot() 装载同一组合
     树（bundle 层 + profile 用户 patch 层），断言 15 个 cumcm_* 工具注册。
  ④ 真实调用 cumcm_workspace_scaffold / cumcm_data_profile /
     cumcm_latex_build（xelatex 可用时）→ 断言 JSON 形状 + 磁盘副作用
     （verify the world，不只看自报结果）。
  ⑤ 失败关闭：bad input → isError=true + error.message，绝不返回伪造成功结果。

环境注记：
  - registry 不可达 → 走 link 本地路径（首选路径，实测成功，非 pnpm add 联网）。
  - dsh.ps1 受 PowerShell 执行策略（Restricted）限制 → 直接 node lib/bin.js。
  - Loader 沙盒：agent-less 直接工具调用实测不被 tools/pre-execute 拦截
    （默认 allow；approval policy 仅在 permission mode=danger-full-access 时
    为 never，本测试未改权限模式）。
  - cumcm_latex_build 需要本机 xelatex（同 tests/e2e/test_paper_pipeline.py 的
    skipif 约定）；MiKTeX 写 %LOCALAPPDATA% 若被受限令牌拒绝属环境性失败，
    需控制器/用户升级后复跑。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CUMCM_TOOLS_DIR = ROOT / "adapters" / "dsh" / "plugins" / "cumcm-tools"
VENV_PYTHON = (
    ROOT / ".venv" / "Scripts" / "python.exe"
    if os.name == "nt"
    else ROOT / ".venv" / "bin" / "python"
)

NODE = shutil.which("node")
PNPM = shutil.which("pnpm")
XELATEX = shutil.which("xelatex")

EXPECTED_TOOL_NAMES = [
    "cumcm_artifact_index",
    "cumcm_citation_check",
    "cumcm_citation_link",
    "cumcm_data_profile",
    "cumcm_data_transform",
    "cumcm_evidence_link",
    "cumcm_experiment_record",
    "cumcm_latex_build",
    "cumcm_latex_lint",
    "cumcm_metrics",
    "cumcm_model_run",
    "cumcm_pdf_inspect",
    "cumcm_result_export",
    "cumcm_sensitivity",
    "cumcm_workspace_scaffold",
]


def _dsh_binjs() -> Path | None:
    """The dsh CLI entry, resolved the same way dsh.ps1 does (node + lib/bin.js)."""
    if not NODE:
        return None
    node_dir = Path(NODE).resolve().parent
    candidate = node_dir / "node_modules" / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
    return candidate if candidate.is_file() else None


DSH_BINJS = _dsh_binjs()

_ENV_READY = bool(
    DSH_BINJS is not None
    and PNPM
    and CUMCM_TOOLS_DIR.is_dir()
    and (CUMCM_TOOLS_DIR / "node_modules").is_dir()
    and VENV_PYTHON.is_file()
)

pytestmark = pytest.mark.skipif(
    not _ENV_READY,
    reason=(
        "environment not ready: need node + dsh lib/bin.js, pnpm, "
        "cumcm-tools plugin with node_modules, and the worktree venv python"
    ),
)

# Loader probe: boots the composed profile tree via dsh-app-boot.boot() (the same
# mechanism `dsh` uses) and executes tool calls through the real ToolRuntime.
# Env: DSH_INSTALL = dir of the @deepseek-ai/dsh package; DSH_HOME; PROFILE;
# TOOL_CALLS = JSON array of {name, arguments, callId?}.
LOADER_PROBE_JS = r"""// Loader probe for the cumcm-tools real-composition e2e.
// Boots the composed profile tree through dsh-app-boot.boot(): bundle layers +
// the profile's own patch layer over the empty root config — the core mechanism
// of `dsh`'s runProfile. Core-mechanism equivalence only, NOT a byte-level
// replica of runProfile. Omitted (all no-ops under a fresh DSH_HOME, so the
// composition is equivalent here): home patch layer, --patch overlays,
// telemetry switch, agent-presets roots, the prepare callback (cmdlineArgs /
// launch environment), installFailLoud, HMR creation and user-patch watching.
import { pathToFileURL } from "node:url";
import { join } from "node:path";
import { writeFileSync } from "node:fs";

let ctx;
try {
  const install = process.env.DSH_INSTALL;
  if (!install) throw new Error("DSH_INSTALL not set");
  const appBoot = await import(
    pathToFileURL(join(install, "node_modules", "@deepseek-ai", "dsh-app-boot", "lib", "index.js")).href
  );
  const { boot, loadProfile, healProfilesModuleFallback } = appBoot;
  const installAnchor = join(install, "package.json");
  healProfilesModuleFallback(installAnchor);
  const profileName = process.env.PROFILE ?? "scratch";
  const profile = loadProfile("dsh", profileName, installAnchor);
  const rootConfigPath = join(profile.dir, "cordis.yml");
  writeFileSync(rootConfigPath, "# probe root\n[]\n");
  const patches = [
    ...profile.layers.flatMap((layer) => layer.patches),
    ...profile.patches,
  ];
  ctx = await boot("dsh", rootConfigPath, patches, () => {});
  const tools = ctx.get("tools");
  const cumcmToolNames = [...tools.view(undefined).visible.keys()]
    .filter((name) => name.startsWith("cumcm_"))
    .sort();
  const calls = JSON.parse(process.env.TOOL_CALLS ?? "[]");
  const results = [];
  for (const call of calls) {
    const controller = new AbortController();
    const result = await tools.execute({
      callId: call.callId ?? "probe-" + (results.length + 1),
      name: call.name,
      arguments: call.arguments,
      signal: controller.signal,
    });
    results.push({ name: call.name, result });
  }
  console.log(JSON.stringify({ cumcmToolNames, results }));
} catch (error) {
  console.error(
    "PROBE_FATAL: " +
      (error instanceof Error ? (error.stack ?? error.message) : String(error))
  );
  process.exitCode = 1;
} finally {
  if (ctx !== undefined) {
    try {
      await ctx.fiber.dispose();
    } catch (error) {
      console.error("PROBE_DISPOSE: " + String(error));
    }
  }
}
"""


def _node_env(dsh_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["DSH_HOME"] = str(dsh_home)
    # PNPM_CONFIG_DIR changes pnpm's workspace-root detection (the lockfile
    # importer becomes the config dir); never inherit it for the profile add.
    env.pop("PNPM_CONFIG_DIR", None)
    return env


def _run(
    cmd: list[str], *, cwd: Path, env: dict[str, str], timeout: int = 300
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _config_patch() -> str:
    """Profile user patch layer: point cumcm-tools at the worktree + venv python."""
    return (
        "- id: cumcm-tools\n"
        "  config:\n"
        f"    cumcmRoot: {ROOT.as_posix()}\n"
        f"    pythonBin: {VENV_PYTHON.as_posix()}\n"
    )


@pytest.fixture(scope="session")
def scratch_profile(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, dict[str, str]]:
    """One scratch profile (session-scoped): plugin added via `dsh plugin add`
    link:<local> (offline) and configured with cumcmRoot/pythonBin."""
    dsh_home = tmp_path_factory.mktemp("dsh-home")
    env = _node_env(dsh_home)
    add = _run(
        [str(NODE), str(DSH_BINJS), "plugin", "--profile", "scratch", "add", f"link:{CUMCM_TOOLS_DIR}"],
        cwd=tmp_path_factory.getbasetemp(),
        env=env,
    )
    assert add.returncode == 0, (
        f"dsh plugin add failed (rc={add.returncode})\nstdout={add.stdout}\nstderr={add.stderr}"
    )
    profile_dir = dsh_home / "profiles" / "scratch"
    manifest = json.loads((profile_dir / "package.json").read_text(encoding="utf-8"))
    assert "cumcm-tools" in manifest["dependencies"], manifest
    (profile_dir / "cordis.patch.yml").write_text(_config_patch(), encoding="utf-8")
    return dsh_home, "scratch", env


@pytest.fixture(scope="session")
def loader_probe(tmp_path_factory: pytest.TempPathFactory) -> Path:
    probe = tmp_path_factory.mktemp("probe") / "loader_probe.mjs"
    probe.write_text(LOADER_PROBE_JS, encoding="utf-8")
    return probe


def _run_probe(
    probe: Path,
    scratch: tuple[Path, str, dict[str, str]],
    tmp_path: Path,
    calls: list[dict],
) -> dict:
    dsh_home, profile_name, base_env = scratch
    env = dict(base_env)
    env["DSH_INSTALL"] = str(DSH_BINJS.parent.parent)
    env["PROFILE"] = profile_name
    env["TOOL_CALLS"] = json.dumps(calls)
    proc = _run([str(NODE), str(probe)], cwd=tmp_path, env=env, timeout=300)
    assert proc.returncode == 0, (
        f"loader probe failed (rc={proc.returncode})\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    # The probe's JSON result is the LAST non-empty stdout line (same last-line
    # convention as the plugin bridge): a future dsh-base banner on stdout must
    # not break parsing. On parse failure include stderr for diagnosis.
    last_line = next(
        (line for line in reversed(proc.stdout.splitlines()) if line.strip()),
        "",
    )
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"loader probe stdout has no parseable JSON result: {error}\n"
            f"last line: {last_line!r}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        ) from error
    assert "cumcmToolNames" in payload and "results" in payload, payload
    return payload


def test_scratch_profile_plugin_add_and_dump_config(tmp_path: Path) -> None:
    """① plugin add (offline link) → profile artifacts; ② --dump-config layer."""
    dsh_home = tmp_path / "dsh-home"
    env = _node_env(dsh_home)
    add = _run(
        [str(NODE), str(DSH_BINJS), "plugin", "--profile", "scratch", "add", f"link:{CUMCM_TOOLS_DIR}"],
        cwd=tmp_path,
        env=env,
    )
    assert add.returncode == 0, (
        f"dsh plugin add failed (rc={add.returncode})\nstdout={add.stdout}\nstderr={add.stderr}"
    )

    profile_dir = dsh_home / "profiles" / "scratch"
    assert (profile_dir / "package.json").is_file()
    manifest = json.loads((profile_dir / "package.json").read_text(encoding="utf-8"))
    dep = manifest["dependencies"]["cumcm-tools"]
    assert dep.startswith("link:"), dep
    # the plugin was reconciled into the bundle layer list
    assert manifest["dsh"]["profile"]["bundles"] == ["@deepseek-ai/dsh-base", "cumcm-tools"]
    # initProfile artifacts
    assert (profile_dir / "cordis.patch.yml").is_file()
    assert (profile_dir / "pnpm-workspace.yaml").is_file()
    # the profile's node_modules/cumcm-tools resolves to the plugin dir itself,
    # reusing the plugin's own node_modules (peer deps) — no registry required
    linked = profile_dir / "node_modules" / "cumcm-tools"
    assert linked.is_dir()
    assert os.path.normcase(str(linked.resolve())) == os.path.normcase(
        str(CUMCM_TOOLS_DIR.resolve())
    ), "profile node_modules/cumcm-tools must resolve to the plugin dir (junction reuse)"

    # ② --dump-config: assert the cumcm-tools layer with the default config
    dump = _run(
        [str(NODE), str(DSH_BINJS), "--profile", "scratch", "--dump-config"],
        cwd=tmp_path,
        env=env,
    )
    assert dump.returncode == 0, dump.stderr
    out = dump.stdout
    assert "# == @deepseek-ai/dsh-base" in out, out
    assert "# == cumcm-tools" in out, out
    assert "- id: cumcm-tools" in out, out
    assert "name: cumcm-tools" in out, out
    assert "cumcmRoot: ''" in out, out
    assert "pythonBin: ''" in out, out
    assert "toolTimeoutMs: 120000" in out, out


def test_loader_boot_registers_all_cumcm_tools(
    scratch_profile: tuple[Path, str, dict[str, str]],
    loader_probe: Path,
    tmp_path: Path,
) -> None:
    """③ Loader 启动：组合树装载成功且 15 个 cumcm_* 工具全部注册。"""
    payload = _run_probe(loader_probe, scratch_profile, tmp_path, [])
    assert payload["cumcmToolNames"] == EXPECTED_TOOL_NAMES, payload["cumcmToolNames"]


def test_real_tool_calls_json_shape_and_side_effects(
    scratch_profile: tuple[Path, str, dict[str, str]],
    loader_probe: Path,
    tmp_path: Path,
) -> None:
    """④ 真实调用 scaffold + data_profile：JSON 形状 + 磁盘副作用。"""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(
        "id,value,label\n"
        "1,10.5,alpha\n"
        "2,20.0,beta\n"
        "3,15.25,alpha\n"
        "1,10.5,alpha\n"
        "4,7.75,gamma\n",
        encoding="utf-8",
    )
    calls = [
        {"name": "cumcm_workspace_scaffold", "arguments": {"target": str(tmp_path), "workspace_id": "ws_e2e"}},
        {"name": "cumcm_data_profile", "arguments": {"path": str(csv_path), "key_columns": "id"}},
    ]
    payload = _run_probe(loader_probe, scratch_profile, tmp_path, calls)
    by_name = {result["name"]: result["result"] for result in payload["results"]}
    assert set(by_name) == {"cumcm_workspace_scaffold", "cumcm_data_profile"}

    scaffold = by_name["cumcm_workspace_scaffold"]
    assert scaffold["isError"] is False, scaffold
    value = scaffold["value"]
    assert value["workspace_id"] == "ws_e2e"
    assert isinstance(value["root"], str) and value["root"]
    assert isinstance(value["files"], list) and len(value["files"]) >= 1
    for item in value["files"]:
        assert {"path", "size", "sha256"} <= set(item), item
    # verify the world: the scaffolded workspace really exists on disk
    root = Path(value["root"])
    assert root.is_dir(), root
    assert (root / "README.md").is_file()
    assert (root / "paper").is_dir()

    profile_result = by_name["cumcm_data_profile"]
    assert profile_result["isError"] is False, profile_result
    pvalue = profile_result["value"]
    assert pvalue["row_count"] == 5
    assert pvalue["column_count"] == 3
    assert pvalue["duplicate_rows"] == 1
    assert isinstance(pvalue["warnings"], list) and pvalue["warnings"]


@pytest.mark.skipif(not XELATEX, reason="xelatex not available")
def test_cumcm_latex_build_real(
    scratch_profile: tuple[Path, str, dict[str, str]],
    loader_probe: Path,
    tmp_path: Path,
) -> None:
    """④ 真实 xelatex 编译（xelatex 可用时）：build 报告 + PDF 落盘。"""
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "main.tex").write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "Hello e2e latex.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    payload = _run_probe(
        loader_probe,
        scratch_profile,
        tmp_path,
        [{"name": "cumcm_latex_build", "arguments": {"dir": str(paper_dir)}}],
    )
    result = payload["results"][0]["result"]
    assert result["isError"] is False, result
    value = result["value"]
    assert value["status"] == "ok", value
    assert value["errors"] == [], value
    assert value["undefined_references"] == [], value
    assert value["failed_pass"] is None, value
    assert isinstance(value["pages"], int) and value["pages"] >= 1, value
    # verify the world: the PDF really exists on disk
    assert Path(value["pdf_path"]).is_file()
    assert Path(value["log_path"]).is_file()


def test_fail_closed_on_bad_input(
    scratch_profile: tuple[Path, str, dict[str, str]],
    loader_probe: Path,
    tmp_path: Path,
) -> None:
    """⑤ 失败关闭：bad input → isError=true + 明确 error，绝无伪造成功。"""
    calls = [
        {"name": "cumcm_workspace_scaffold", "arguments": {"target": str(tmp_path), "workspace_id": "bad/id"}},
        {"name": "cumcm_data_profile", "arguments": {"path": str(tmp_path / "missing.csv")}},
    ]
    payload = _run_probe(loader_probe, scratch_profile, tmp_path, calls)
    by_name = {result["name"]: result["result"] for result in payload["results"]}

    scaffold = by_name["cumcm_workspace_scaffold"]
    assert scaffold["isError"] is True, scaffold
    assert scaffold.get("value") is None, "failed call must not carry a fake value"
    assert "invalid workspace id" in scaffold["error"]["message"], scaffold["error"]
    assert scaffold["content"][0]["type"] == "text"
    assert scaffold["content"][0]["text"].startswith("Error: "), scaffold["content"]

    profile_result = by_name["cumcm_data_profile"]
    assert profile_result["isError"] is True, profile_result
    assert profile_result.get("value") is None, "failed call must not carry a fake value"
    assert "cannot read csv" in profile_result["error"]["message"], profile_result["error"]
