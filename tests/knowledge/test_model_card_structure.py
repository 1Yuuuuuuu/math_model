import json
from pathlib import Path

import jsonschema
import yaml

REQUIRED_SECTIONS = [
    "适用问题", "禁用场景", "输入与假设", "核心公式", "直观解释", "建模步骤",
    "参数选择", "工具入口", "最小示例", "评价指标", "检验方法", "对比基线",
    "替代模型", "常见误用", "失效征兆", "论文表达示例", "对应练习",
]


def _load(project_root: Path) -> tuple[dict, list[dict], dict]:
    schema = json.loads(
        (project_root / "shared/knowledge/model-card.schema.json").read_text(encoding="utf-8")
    )
    catalog = yaml.safe_load(
        (project_root / "shared/knowledge/model-catalog.yaml").read_text(encoding="utf-8")
    )
    cards = []
    for entry in catalog["cards"]:
        cards.append(
            {
                "entry": entry,
                "path": project_root / entry["file"],
                "text": (project_root / entry["file"]).read_text(encoding="utf-8"),
            }
        )
    return schema, cards, catalog


def _front_matter(text: str) -> dict:
    if not text.startswith("---"):
        raise AssertionError("card missing YAML front matter")
    body, _ = text.split("---", 2)[1:]
    return yaml.safe_load(body)


def test_catalog_matches_filesystem_and_front_matter(project_root: Path) -> None:
    schema, cards, catalog = _load(project_root)
    ids = [entry["model_id"] for entry in catalog["cards"]]
    assert len(ids) == len(set(ids)), "duplicate model ids"
    for card in cards:
        assert card["path"].is_file(), f"missing card file: {card['entry']['file']}"
        fm = _front_matter(card["text"])
        assert fm["model_id"] == card["entry"]["model_id"]
        assert fm["category"] == card["entry"]["category"]


def test_front_matter_validates_against_schema(project_root: Path) -> None:
    schema, cards, _ = _load(project_root)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    for card in cards:
        errors = list(validator.iter_errors(_front_matter(card["text"])))
        assert not errors, f"{card['entry']['file']}: {[e.message for e in errors]}"


def test_every_card_has_all_required_sections(project_root: Path) -> None:
    _, cards, _ = _load(project_root)
    for card in cards:
        for section in REQUIRED_SECTIONS:
            assert f"## {section}" in card["text"], f"{card['entry']['file']} missing ## {section}"
        assert len(card["text"].strip()) > 300, f"{card['entry']['file']} too short"


def test_no_orphan_card_files(project_root: Path) -> None:
    _, _, catalog = _load(project_root)
    disk = {
        str(p.relative_to(project_root)).replace("\\", "/")
        for p in (project_root / "shared/knowledge/model-cards").rglob("*.md")
    }
    catalog_files = {entry["file"] for entry in catalog["cards"]}
    assert disk == catalog_files, {
        "orphans": sorted(disk - catalog_files),
        "missing": sorted(catalog_files - disk),
    }


def test_catalog_full_field_consistency(project_root: Path) -> None:
    _, cards, _ = _load(project_root)
    for card in cards:
        entry = card["entry"]
        fm = _front_matter(card["text"])
        for field in ("file", "title", "status", "priority", "category"):
            assert fm.get(field) == entry.get(field), (
                f"{entry['file']}: front-matter {field} {fm.get(field)!r} != catalog {entry.get(field)!r}"
            )


def test_catalog_no_duplicate_paths(project_root: Path) -> None:
    _, _, catalog = _load(project_root)
    files = [entry["file"] for entry in catalog["cards"]]
    assert len(files) == len(set(files)), "duplicate catalog file paths"


def test_catalog_header_describes_per_entry_status_lifecycle(project_root: Path) -> None:
    """A global-draft header contradicts approved statuses carried by individual cards."""
    catalog_text = (project_root / "shared/knowledge/model-catalog.yaml").read_text(
        encoding="utf-8"
    )

    assert "status 为逐条卡片的生命周期元数据" in catalog_text
    assert "status 统一为 draft" not in catalog_text


def test_nonlinear_regression_paper_example_matches_executor_output(
    project_root: Path,
) -> None:
    """The paper example must include the fitted offset and only reported diagnostics."""
    card_text = (
        project_root
        / "shared/knowledge/model-cards/prediction/nonlinear-regression.md"
    ).read_text(encoding="utf-8")
    paper_example = card_text.split("## 论文表达示例", 1)[1].split(
        "## 对应练习", 1
    )[0]

    assert "y=a·e^(bx)+c" in paper_example
    assert "R²" in paper_example
    assert "置信区间" not in paper_example
