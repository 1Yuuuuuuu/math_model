from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[4] / "shared" / "templates" / "project"


def scaffold_workspace(
    target_root: Path,
    workspace_id: str,
    *,
    template_root: Path | None = None,
    overwrite: bool = False,
) -> dict[str, object]:
    root = target_root.resolve()
    target = root / workspace_id
    template = (template_root or DEFAULT_TEMPLATE).resolve()
    if not template.is_dir():
        raise FileNotFoundError(f"template not found: {template}")
    if target.exists() and not overwrite and any(p.is_file() for p in target.rglob("*")):
        raise FileExistsError(f"workspace already exists and is not empty: {target}")

    target.mkdir(parents=True, exist_ok=True)
    created = []
    for source in sorted(template.rglob("*")):
        if source.is_dir():
            continue
        relative = source.relative_to(template)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        destination.write_bytes(data)
        created.append(
            {
                "path": relative.as_posix(),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return {"workspace_id": workspace_id, "root": str(target), "files": created}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a standard CUMCM workspace")
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        result = scaffold_workspace(args.target, args.workspace_id, overwrite=args.overwrite)
    except (FileExistsError, FileNotFoundError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
