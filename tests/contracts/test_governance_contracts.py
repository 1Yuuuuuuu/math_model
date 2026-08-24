import pytest
from jsonschema import Draft202012Validator, ValidationError

from tests.contracts.conftest import FORMAT_CHECKER, load_json


CASES = [
    ("review-finding", "review-finding", "review-finding-bad-severity"),
    ("annual-rule", "annual-rule", "annual-rule-missing-source"),
    ("asset-manifest", "asset-manifest", "asset-manifest-duplicate-target"),
]

GOVERNANCE_SCHEMA_NAMES = ("review-finding", "annual-rule", "asset-manifest")

ANNUAL_RULE_INVALID_EXAMPLES = (
    "annual-rule-empty-host",
    "annual-rule-invalid-source-url",
    "annual-rule-invalid-ipv6-colons",
    "annual-rule-invalid-ipv6-nine-segments",
    "annual-rule-timezone-less",
    "annual-rule-userinfo-empty-host",
)

NO_HOST_AUTHORITY_URLS = (
    "http://@/path",
    "http://:80/path",
    "https://user@/path",
    "https://user@:80/path",
)

VALID_ANNUAL_RULE_SOURCE_URLS = (
    "https://example.invalid/cumcm-rules",
    "https://192.0.2.1:8443/cumcm-rules",
    "https://[2001:db8::1]:443/cumcm-rules",
)

INVALID_ANNUAL_RULE_SOURCE_URLS = (
    "https://example.invalid:65536/cumcm-rules",
    "https://example.invalid/cumcm-rules\x00trailing",
    "https://example.invalid/cumcm-rules\x80trailing",
    "https://example.invalid/cumcm-rules\x9ftrailing",
    "https://[::1]junk/path",
    "https://[::1]example.com/path",
)


@pytest.mark.parametrize(("schema_name", "valid_name", "invalid_name"), CASES)
def test_valid_and_invalid_governance_contract_examples(
    project_root, schema_name, valid_name, invalid_name
) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    validator.validate(load_json(project_root / f"shared/fixtures/contracts/valid/{valid_name}.json"))
    with pytest.raises(ValidationError):
        validator.validate(
            load_json(project_root / f"shared/fixtures/contracts/invalid/{invalid_name}.json")
        )


@pytest.mark.parametrize("schema_name", GOVERNANCE_SCHEMA_NAMES)
def test_governance_contracts_reject_a_missing_schema_version(project_root, schema_name) -> None:
    schema = load_json(project_root / f"shared/contracts/{schema_name}.schema.json")
    fixture = load_json(project_root / f"shared/fixtures/contracts/valid/{schema_name}.json")
    fixture.pop("schema_version", None)
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    with pytest.raises(ValidationError):
        validator.validate(fixture)


@pytest.mark.parametrize("invalid_name", ANNUAL_RULE_INVALID_EXAMPLES)
def test_annual_rule_invalid_examples_are_rejected(project_root, invalid_name) -> None:
    schema = load_json(project_root / "shared/contracts/annual-rule.schema.json")
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    with pytest.raises(ValidationError):
        validator.validate(
            load_json(project_root / f"shared/fixtures/contracts/invalid/{invalid_name}.json")
        )


@pytest.mark.parametrize("source_url", NO_HOST_AUTHORITY_URLS)
def test_annual_rule_rejects_userinfo_or_bare_port_without_a_hostname(project_root, source_url) -> None:
    schema = load_json(project_root / "shared/contracts/annual-rule.schema.json")
    annual_rule = load_json(project_root / "shared/fixtures/contracts/valid/annual-rule.json")
    annual_rule["source_url"] = source_url
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    with pytest.raises(ValidationError):
        validator.validate(annual_rule)


def test_annual_rule_accepts_a_bracketed_ipv6_host(project_root) -> None:
    schema = load_json(project_root / "shared/contracts/annual-rule.schema.json")
    annual_rule = load_json(project_root / "shared/fixtures/contracts/valid/annual-rule.json")
    annual_rule["source_url"] = "https://[2001:db8::1]:443/cumcm-rules"
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    validator.validate(annual_rule)


@pytest.mark.parametrize("source_url", VALID_ANNUAL_RULE_SOURCE_URLS)
def test_annual_rule_accepts_semantically_valid_source_urls(project_root, source_url) -> None:
    schema = load_json(project_root / "shared/contracts/annual-rule.schema.json")
    annual_rule = load_json(project_root / "shared/fixtures/contracts/valid/annual-rule.json")
    annual_rule["source_url"] = source_url
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    validator.validate(annual_rule)


@pytest.mark.parametrize("source_url", INVALID_ANNUAL_RULE_SOURCE_URLS)
def test_annual_rule_rejects_semantically_invalid_source_url_boundaries(
    project_root, source_url
) -> None:
    schema = load_json(project_root / "shared/contracts/annual-rule.schema.json")
    annual_rule = load_json(project_root / "shared/fixtures/contracts/valid/annual-rule.json")
    annual_rule["source_url"] = source_url
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    with pytest.raises(ValidationError):
        validator.validate(annual_rule)
