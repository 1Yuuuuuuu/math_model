from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath


def load_skill_catalog(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "adapters/codex/skills/catalog.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load skill catalog: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("catalog_version") != "1.0":
        raise ValueError("invalid skill catalog version")
    skills = payload.get("skills")
    if (
        not isinstance(skills, list)
        or not skills
        or any(not isinstance(name, str) or not name for name in skills)
        or len(skills) != len(set(skills))
    ):
        raise ValueError("skill catalog must contain unique non-empty names")
    return tuple(skills)


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def package_skills(repo_root: Path, output: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    source_root = repo_root / "adapters/codex/skills"
    if output.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    skills = load_skill_catalog(repo_root)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent)
    )
    packaged: list[Path] = []

    actual = tuple(sorted(p.name for p in source_root.iterdir() if p.is_dir()))
    if set(actual) != set(skills):
        shutil.rmtree(staging, ignore_errors=True)
        raise ValueError(f"skill catalog mismatch: expected={skills!r}, actual={actual!r}")

    try:
        for name in skills:
            source_dir = source_root / name
            target_dir = staging / name
            target_dir.mkdir(parents=True, exist_ok=False)
            for relative in ("SKILL.md", "agents/openai.yaml", "resources.json"):
                source = source_dir / relative
                if not source.is_file():
                    raise FileNotFoundError(f"missing skill file: {source}")
                target = target_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

            declaration = json.loads((source_dir / "resources.json").read_text(encoding="utf-8"))
            if declaration.get("skill") != name:
                raise ValueError(f"resource manifest skill mismatch: {name}")
            assets: list[dict[str, str]] = []
            resource_files: list[tuple[PurePosixPath, Path]] = []
            for value in declaration.get("resources", []):
                relative = validate_resource_path(value)
                source = repo_root.joinpath(*relative.parts).resolve()
                try:
                    source.relative_to(repo_root)
                except ValueError as exc:
                    raise ValueError(f"resource escapes repository: {value}") from exc
                if not source.exists():
                    raise FileNotFoundError(f"missing resource: {value}")
                if source.is_dir():
                    for child in sorted(path for path in source.rglob("*") if path.is_file()):
                        resolved = child.resolve()
                        try:
                            resolved.relative_to(source)
                        except ValueError as exc:
                            raise ValueError(f"resource escapes declared directory: {child}") from exc
                        resource_files.append(
                            (PurePosixPath(resolved.relative_to(repo_root).as_posix()), resolved)
                        )
                elif source.is_file():
                    resource_files.append((relative, source))
                else:
                    raise ValueError(f"unsupported resource type: {value}")

            seen_resources: set[str] = set()
            for relative, source in sorted(resource_files, key=lambda item: item[0].as_posix()):
                if relative.as_posix() in seen_resources:
                    continue
                seen_resources.add(relative.as_posix())
                packaged_path = PurePosixPath("references") / relative
                target = target_dir.joinpath(*packaged_path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                assets.append(
                    {
                        "source_path": relative.as_posix(),
                        "packaged_path": packaged_path.as_posix(),
                        "sha256": _sha256(source),
                    }
                )
            manifest = {"skill": name, "assets": sorted(assets, key=lambda item: item["source_path"])}
            (target_dir / "asset-manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        staging.replace(output)
        packaged = [output / name for name in skills]
        return packaged
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_packaged_output(repo_root: Path, output: Path) -> None:
    if not output.is_dir():
        raise FileNotFoundError(f"packaged output directory not found: {output}")
    with tempfile.TemporaryDirectory(prefix="codex-skills-verify-") as temp:
        expected = Path(temp) / "skills"
        package_skills(repo_root, expected)
        expected_manifest = _tree_manifest(expected)
        actual_manifest = _tree_manifest(output)
    if actual_manifest != expected_manifest:
        missing = sorted(set(expected_manifest) - set(actual_manifest))
        extra = sorted(set(actual_manifest) - set(expected_manifest))
        changed = sorted(
            path
            for path in set(expected_manifest).intersection(actual_manifest)
            if expected_manifest[path] != actual_manifest[path]
        )
        raise ValueError(
            f"package drift detected: missing={missing!r}, extra={extra!r}, changed={changed!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Package self-contained Codex modeling skills.")
    parser.add_argument("--check", action="store_true", help="validate by packaging into a temporary directory")
    parser.add_argument("--output", type=Path, help="output directory (required without --check)")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    try:
        if args.check and args.output is not None:
            verify_packaged_output(repo_root, args.output)
            packaged = [args.output / name for name in load_skill_catalog(repo_root)]
        elif args.check:
            with tempfile.TemporaryDirectory(prefix="codex-skills-") as temp:
                packaged = package_skills(repo_root, Path(temp) / "skills")
        else:
            if args.output is None:
                parser.error("--output is required unless --check is used")
            packaged = package_skills(repo_root, args.output)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "status": "failed"}, sort_keys=True))
        return 1
    print(json.dumps({"skills": len(packaged), "status": "ok"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
