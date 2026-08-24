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
