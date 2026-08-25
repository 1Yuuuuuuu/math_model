"""E2E: evidence-bound paper pipeline (Phase 4 exit criteria 1-5).

链路：① 实验记录（metrics 含已知数值）+ approved 来源 → ② scaffold 论文工程
→ ③ 证据绑定正文（摘要数值来自实验 metrics、正文含 \\cite{<bib hash key>}
与 \\ref）→ ④ build_paper（xelatex 双遍）→ ⑤ lint_paper + citation_check
（显式传 approved_source_ids）+ inspect_pdf → ⑥ 断言各环节结构化报告与
退出标准。

人工门 3 的 toolkit 侧表达：未获批准（verification_status != approved）
的文献来源必须在 citation 阶段被 link_approved_source 拒绝。

环境注记：真实编译需 MiKTeX 写 %LOCALAPPDATA%（受限令牌可能被拒）。若
build 相关断言在受限沙盒因 MiKTeX access-denied 失败（RegCreateKeyExW /
log4cxx setFile），属环境性失败，需控制器/用户升级权限后复跑确认 GREEN。
"""

import shutil
from pathlib import Path

import pytest

from cumcm_toolkit.evidence.citation_linker import approved_sources, link_approved_source
from cumcm_toolkit.evidence.linker import link_claim_to_metrics, resolve_numeric_claims
from cumcm_toolkit.experiments.manifest import create_experiment_record
from cumcm_toolkit.latex.bibliography import generate_bibliography
from cumcm_toolkit.latex.build import build_paper
from cumcm_toolkit.latex.citation_check import citation_check
from cumcm_toolkit.latex.lint import lint_paper
from cumcm_toolkit.latex.scaffold import scaffold_paper
from cumcm_toolkit.pdf.inspect import inspect_pdf

XELATEX = shutil.which("xelatex")

pytestmark = pytest.mark.skipif(not XELATEX, reason="xelatex not available")


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _approved_source() -> dict:
    return {
        "schema_version": "1.0",
        "source_id": "src_synthetic_method",
        "title": "示例性鲁棒优化说明",
        "authors": ["甲", "乙"],
        "year": 2024,
        "venue_or_repository": "合成期刊",
        "identifiers": {},
        "canonical_url": "https://example.invalid/method",
        "retrieved_at": "2026-08-22T00:00:00+00:00",
        "retrieval_backend": "user-provided",
        "verification_status": "approved",
        "artifact_ids": ["art_method_note"],
        "content_sha256": "a" * 64,
        "decision_id": "dec_outline_sources",
    }


def _bib_key(bib_text: str) -> str:
    """Return the first BibTeX entry key (hash-derived: src_<sha256-8>)."""
    for line in bib_text.splitlines():
        if line.startswith("@"):
            return line.split("{", 1)[1].rstrip(",")
    raise AssertionError("no bib key generated")


def test_evidence_bound_paper_pipeline(project_root: Path, tmp_path: Path) -> None:
    # 1) experiment record with known metric value
    experiment = create_experiment_record(
        input_artifact_ids=["art_raw_data"],
        code_artifact_id="art_solve_code",
        parameters={"max_iterations": 1000},
        random_seed=7,
        status="succeeded",
        output_artifact_ids=["art_result_table"],
        metrics={"rmse": 0.125},
        project_root=project_root,
    )
    claim = link_claim_to_metrics(
        claim_id="clm_rmse", claim_text=f"模型 RMSE 为 {experiment['metrics']['rmse']}",
        experiment_record=experiment, metric_keys=["rmse"], boundary="单次运行",
    )

    # 2) approved source + citation link (human gate 3: approved + decision_id)
    source = _approved_source()
    assert approved_sources([source]) == [source], "approved gate must admit the record"
    citation = link_approved_source(
        source_record=source, claim_id="clm_rmse", usage="method",
        locator={"kind": "paragraph", "value": "第 2 段"}, support_boundary="仅支持方法性主张",
    )

    # 3) scaffold paper and write evidence-bound body
    result = scaffold_paper(tmp_path, "paper2026")
    paper_dir = Path(result["root"])
    bib = generate_bibliography([source])
    # bib keys are hash-derived (src_<sha256-8> of source_id), not the source_id itself
    key = _bib_key(bib)
    rmse = experiment["metrics"]["rmse"]
    tex = (
        "\\documentclass[11pt]{ctexart}\n"
        "\\begin{document}\n"
        f"\\begin{{abstract}}\n模型 RMSE 为 {rmse}。\n\\end{{abstract}}\n"
        "\\section{方法}\\label{sec:method}\n"
        "方法参考~\\cite{" + key + "}。\n"
        "\\section{结果}\\label{sec:results}\n"
        "第~\\ref{sec:method}~节说明方法。\n"
        "\\bibliographystyle{plain}\n"
        "\\bibliography{bibliography}\n"
        "\\end{document}\n"
    )
    (paper_dir / "main.tex").write_text(tex, encoding="utf-8")
    (paper_dir / "bibliography.bib").write_text(bib, encoding="utf-8")
    # No hand-written .bbl: build_paper runs its own bibtex pass (Fix 1) when
    # bibliography.bib exists, so \cite{key} is resolved by the real pipeline.

    # 4) build (xelatex → bibtex → xelatex → xelatex)
    build = build_paper(paper_dir)
    assert build["status"] == "ok", (
        f"build failed: errors={build['errors']} warnings={build['warnings']} "
        f"log={build['log_path']}"
    )
    assert build["pages"] is not None and build["pages"] >= 1, build
    assert build["undefined_references"] == [], build["undefined_references"]

    # 5) lint + citation check (approved_source_ids passed explicitly) + pdf inspect
    lint = lint_paper(paper_dir)
    assert lint["status"] == "ok", lint["issues"]
    check = citation_check(
        tex, bib, [citation], approved_source_ids={source["source_id"]}
    )
    assert check["status"] == "ok", check["errors"]
    pdf = inspect_pdf(paper_dir / "main.pdf")
    assert pdf["pages"] == build["pages"]
    assert isinstance(pdf["blank_pages"], list)
    assert "fonts" in pdf

    # abstract numbers resolve to evidence; the abstract number == the metric value
    assert str(rmse) in tex, "abstract number must come from the experiment metrics"
    resolved = resolve_numeric_claims(f"模型 RMSE 为 {rmse}", [claim])
    assert resolved["status"] == "ok", resolved["unresolved"]
    assert resolved["unresolved"] == []


def test_pipeline_rejects_unapproved_source(project_root: Path, tmp_path: Path) -> None:
    source = _approved_source()
    source["verification_status"] = "candidate"
    # human gate 3: candidate (unapproved) sources must not pass the approved gate
    assert approved_sources([source]) == []
    with pytest.raises(ValueError):
        link_approved_source(
            source_record=source, claim_id="clm_x", usage="method",
            locator={"kind": "paragraph", "value": "p"}, support_boundary="b",
        )
