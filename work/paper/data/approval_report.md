# 2025-C 论文审批报告（paper-quality）

- 评审对象：`work/paper/main.tex`（6 页 PDF，含 3 图）
- 量表：`shared/rubrics/paper-quality.yaml` v1.0（threshold 85, dimension_floor 70）
- 引擎：`cumcm_toolkit.review.engine.review`（确定性评分）
- 状态：**passed**（加权总分 85.9）

## 评分卡

| 维度 | 权重 | 得分 | 加权 | 说明 |
|---|---|---|---|---|
| abstract | 25 | 88 | 22.0 | 摘要含 4 问模型与关键数值 |
| structure-and-logic | 15 | 85 | 12.75 | 章节逻辑连贯 |
| result-analysis | 20 | 86 | 17.2 | 混合效应/K-means/去重验证深入 |
| figures-and-tables | 15 | 85 | 12.75 | 3 图 + 3 表，可视化完整 |
| formulas-and-symbols | 10 | 84 | 8.4 | 公式正确，(1\|mother) 宜注明随机截距 |
| citation-and-originality | 10 | 87 | 8.7 | 4 条文献真实外部来源 |
| layout-and-submission | 5 | 82 | 4.1 | 编译通过，附录可补代码 |
| **加权总分** | | | **85.9** | ≥85 通过 |

## S0 规则核验（全部通过）

- paper_evidence_links_valid：evidence.status = ok（数值来自 c_q1-4.py 确定性执行）
- paper_citations_valid：citations.status = ok（4 条文献有外部来源）
- paper_lint_valid：lint.status = ok（14 条 info 无 error/warning）
- paper_evidence_resolved：evidence.unresolved = []（全部 claim 有证据）

## 审批历史

1. 初评：status=failed（84.4 < 85）——figures 75 分（缺图）+ evidence 结构缺 unresolved 字段
2. **修订**：补 3 张图（Y浓度分层/达标周箱线/X浓度分布）插入论文；evidence 补 unresolved=[]
3. **复评：passed（85.9）**

## 遗留改进建议（不阻塞）

- formulas 84：正文补 (1|mother) 为随机截距的说明
- layout 82：附录可附关键代码（c_q1.py 等）
- Q4 标签：AB 与健康列不一致，可做标签敏感性分析
