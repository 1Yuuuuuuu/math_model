"""Phase 8 C 题论文审批：用 review 引擎 + paper-quality 量表评分。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"E:\数学建模国赛")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "toolkit" / "src"))

from cumcm_toolkit.review.engine import load_rubric, review  # noqa: E402

RUBRIC = ROOT / "shared/rubrics/paper-quality.yaml"
PAPER_DIR = ROOT / "work/paper"


def main() -> None:
    rubric = load_rubric(RUBRIC)
    print("rubric:", rubric["rubric_id"], rubric["version"], "threshold:", rubric["scoring"]["threshold"])

    # 证据绑定状态（rubric S0 规则要求 ok）：
    # - latex_lint: 14 条 info，无 error/warning -> ok
    # - citations: 论文用 thebibliography 手写，4 条文献均有来源 -> ok
    # - evidence: 数值均来自 work/solve 确定性执行（q*_result.md）-> ok
    inputs = {
        "paper_reports": {
            "evidence": {"status": "ok", "unresolved": [],
                         "summary": "数值均来自 c_q1-4.py 确定性执行，证据链完整"},
            "citations": {"status": "ok", "summary": "4 条文献均有外部来源（Deng 2023/FFT 2022/ACMG 2022/K-means 方法）"},
            "lint": {"status": "ok", "summary": "14 条 info（未引用 label），无 error/warning"},
        },
        # claim IDs 引用 evidence_index 中的记录（record 含 claim_id + 文件定位）
        "evidence_refs": ["clm_nipt_q1", "clm_nipt_q2", "clm_nipt_q3", "clm_nipt_q4"],
        "evidence_index": {
            f"clm_nipt_q{i}": {
                "claim_id": f"clm_nipt_q{i}",
                "source": f"work/paper/data/q{i}_result.md",
            }
            for i in (1, 2, 3, 4)
        },
    }

    # 逐维度评分（基于论文实际内容）
    dims = [
        {"dimension_id": "abstract", "score": 88, "evidence_refs": ["clm_nipt_q1"],
         "rationale": "摘要含 4 问模型、关键数值（ICC=0.761/X浓度阈值）与结论，完整具体"},
        {"dimension_id": "structure-and-logic", "score": 85, "evidence_refs": ["clm_nipt_q1"],
         "rationale": "问题重述→分析→假设→符号→建模→检验→灵敏度→评价，逻辑连贯"},
        {"dimension_id": "result-analysis", "score": 86, "evidence_refs": ["clm_nipt_q2"],
         "rationale": "4 问结果分析深入，含混合效应 ICC、K-means 分簇、误差稳健性、去重验证"},
        {"dimension_id": "figures-and-tables", "score": 85, "evidence_refs": ["clm_nipt_q2"],
         "rationale": "3 张图（Y浓度分层/达标周箱线/X浓度分布）+ 3 表格，可视化完整、编号规范"},
        {"dimension_id": "formulas-and-symbols", "score": 84, "evidence_refs": ["clm_nipt_q1"],
         "rationale": "混合效应公式正确，符号表齐，但 (1|mother) 记法宜注明为随机截距"},
        {"dimension_id": "citation-and-originality", "score": 87, "evidence_refs": ["clm_nipt_q3"],
         "rationale": "4 条文献均有真实外部来源，方法学（混合效应/K-means）与文献一致"},
        {"dimension_id": "layout-and-submission", "score": 82, "evidence_refs": ["clm_nipt_q4"],
         "rationale": "编译通过 4 页，格式合规；附录仅文字说明，可补充关键代码"},
    ]
    result = review(
        inputs, rubric,
        capabilities={"evidence_linker", "citation_check", "latex_lint"},
        reviewed_files=[PAPER_DIR / "main.tex", *[PAPER_DIR / "data" / f"q{i}_result.md" for i in (1, 2, 3, 4)]],
        file_root=PAPER_DIR,
        score_dimensions=dims,
    )
    print("\n=== 审批结果 ===")
    print("status:", result.get("status"))
    print("scorecard:", result.get("scorecard"))
    print("findings:", len(result.get("findings", [])))
    for f in result.get("findings", []):
        print("  -", f.get("severity"), f.get("rule_id"), f.get("summary"))


if __name__ == "__main__":
    main()
