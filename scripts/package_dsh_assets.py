from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

MANIFEST_VERSION = "1.0"
DEFAULT_OUTPUT = "dist/dsh-assets"

# 资产分类 -> 收集规格（kind, pattern）；kind: dir=递归收集 / file=单文件 / glob=通配匹配。
# 覆盖范围与 scripts/package_codex_skills.py 对齐（model-cards 子集严格一致）；
# workflow 额外哈希引用 codex 产物 agents/openai.yaml（DSH 不复制 codex 产物，只哈希引用）。
ASSET_SPECS: dict[str, tuple[tuple[str, str], ...]] = {
    "contracts": (("glob", "shared/contracts/*.json"),),
    "templates": (("dir", "shared/templates"),),
    "knowledge": (("dir", "shared/knowledge"),),
    "model-cards": (("dir", "shared/knowledge/model-cards"),),
    "workflow": (
        ("dir", "shared/workflows"),
        ("dir", "shared/rubrics"),
        ("file", "shared/knowledge/model-catalog.yaml"),
        ("glob", "adapters/codex/skills/*/agents/openai.yaml"),
    ),
    # DSH 侧交付物：preset 组合层（Phase 7 产物，纳入漂移监测）。
    "presets": (("dir", "adapters/dsh/presets"),),
}


def validate_resource_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or ":" in value
        or path.parts[0] not in {"adapters", "scripts", "shared", "toolkit"}
    ):
        raise ValueError(f"unsafe resource path: {value}")
    return path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _collect(repo_root: Path, kind: str, pattern: str) -> list[Path]:
    if kind == "dir":
        source = repo_root.joinpath(*PurePosixPath(pattern).parts)
        if not source.is_dir():
            raise FileNotFoundError(f"missing asset directory: {pattern}")
        return sorted(path for path in source.rglob("*") if path.is_file())
    if kind == "file":
        source = repo_root.joinpath(*PurePosixPath(pattern).parts)
        if not source.is_file():
            raise FileNotFoundError(f"missing asset file: {pattern}")
        return [source]
    if kind == "glob":
        matches = sorted(path for path in repo_root.glob(pattern) if path.is_file())
        if not matches:
            raise FileNotFoundError(f"no files matched asset glob: {pattern}")
        return matches
    raise ValueError(f"unsupported asset kind: {kind}")


def _safe_relative(repo_root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"asset escapes repository: {path}") from exc
    relative = resolved.relative_to(repo_root).as_posix()
    return validate_resource_path(relative).as_posix()


def build_manifest(repo_root: Path) -> dict:
    repo_root = repo_root.resolve()
    categories: dict[str, list[str]] = {}
    assets: dict[str, str] = {}
    for category, specs in ASSET_SPECS.items():
        category_paths: set[str] = set()
        for kind, pattern in specs:
            for path in _collect(repo_root, kind, pattern):
                relative = _safe_relative(repo_root, path)
                category_paths.add(relative)
                assets.setdefault(relative, _sha256(path))
        categories[category] = sorted(category_paths)
    return {
        "manifest_version": MANIFEST_VERSION,
        "generated_at": _utc_now().isoformat(timespec="seconds"),
        "asset_categories": categories,
        "assets": dict(sorted(assets.items())),
    }


def package_assets(repo_root: Path, output: Path) -> int:
    repo_root = repo_root.resolve()
    manifest = build_manifest(repo_root)
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return len(manifest["assets"])


def verify_manifest(repo_root: Path, output: Path) -> dict[str, list[str]]:
    manifest_path = output / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    try:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load manifest: {exc}") from exc
    if not isinstance(existing, dict) or existing.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("unsupported manifest version")
    previous = existing.get("assets")
    if not isinstance(previous, dict):
        raise ValueError("manifest assets must be a map of relative path to sha256")

    current = build_manifest(repo_root)["assets"]
    missing = sorted(set(previous) - set(current))  # 清单有、仓库无 → 资产缺失
    extra = sorted(set(current) - set(previous))  # 仓库有、清单无 → 新增资产
    changed = sorted(
        path for path in set(previous) & set(current) if previous[path] != current[path]
    )
    return {"missing": missing, "extra": extra, "changed": changed}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package DSH shared assets as a SHA-256 manifest."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify an existing manifest against the repository (exit 1 on drift)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
        help=f"output directory (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else repo_root / args.output
    try:
        if args.check:
            drift = verify_manifest(repo_root, output)
            if any(drift.values()):
                print(
                    json.dumps(
                        {"error": "asset drift detected", "status": "failed", **drift},
                        sort_keys=True,
                    )
                )
                return 1
            assets = len(build_manifest(repo_root)["assets"])
            print(json.dumps({"assets": assets, "status": "ok"}, sort_keys=True))
            return 0
        assets = package_assets(repo_root, output)
        print(json.dumps({"assets": assets, "status": "ok"}, sort_keys=True))
        return 0
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "status": "failed"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
