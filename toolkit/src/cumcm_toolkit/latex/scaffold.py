from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.contract_formats import is_cumcm_workspace_path

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[4] / "shared" / "templates" / "latex" / "cumcm"


def scaffold_paper(
    target_root: Path,
    paper_id: str,
    *,
    template_root: Path | None = None,
    overwrite: bool = False,
) -> dict[str, object]:
    if (
        not paper_id
        or "/" in paper_id
        or "\\" in paper_id
        or paper_id in {".", ".."}
        or not is_cumcm_workspace_path(paper_id)
    ):
        raise ValueError(f"invalid paper id: {paper_id}")
    root = target_root.resolve()
    target = root / paper_id
    template = (template_root or DEFAULT_TEMPLATE).resolve()
    if not template.is_dir():
        raise FileNotFoundError(f"template not found: {template}")
    if target.exists() and not overwrite and any(target.iterdir()):
        raise FileExistsError(f"paper project already exists and is not empty: {target}")

    target.mkdir(parents=True, exist_ok=True)
    created = []
    for source in sorted(template.rglob("*"), key=lambda p: p.relative_to(template).as_posix()):
        if source.is_dir():
            continue
        relative = source.relative_to(template)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        destination.write_bytes(data)
        created.append(
            {"path": relative.as_posix(), "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    return {"paper_id": paper_id, "root": str(target), "files": created}


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a CUMCM paper project")
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        result = scaffold_paper(args.target, args.paper_id, overwrite=args.overwrite)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True, ensure_ascii=True))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
