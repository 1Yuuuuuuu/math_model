# Phase 8 真题回归报告 — 2025-C NIPT

> 场景：2025 高教社杯 C 题（NIPT 时点选择与胎儿异常判定）
> 套件：representative（首个真题代表场景）
> 日期：2026-08-29

## 1. 场景信息

| 项 | 值 |
|---|---|
| 题目 | 2025-C NIPT 的时点选择与胎儿的异常判定 |
| 数据 | 男胎 1082 行/267 孕妇、女胎 605 行/147 孕妇（官方附件，含纵向多次检测）|
| 数据源 | `E:\国赛论文对比\官网题目\C题\附件.xlsx`（官方公开）|
| 入库 | `shared/fixtures/historical/2025-c-nipt/`（README + problem-analysis）|
| 题型 | 统计建模 + 聚类分组优化 + 分类判定 |

## 2. 模型选择与结果

| 问题 | 模型 | 关键结果 | 审批 |
|---|---|---|---|
| Q1 | 线性混合效应（孕妇随机截距）| ICC=0.761；week β=0.0032 (p<1e-73)；bmi β=-0.0013 (p=0.02) | 证据绑定 |
| Q2 | K-means 聚类（k=5）+ P90 + bootstrap CI | 5 簇 BMI 中心 28.5-40.1；高 BMI 达标晚/率低；误差 ±10% 仅 3.5% 影响 | 证据绑定 |
| Q3 | 混合效应多因素 + 共线性处理 | weight~bmi=0.827 共线；height 独立显著 (p=0.035) | 证据绑定 |
| Q4 | X 浓度阈值 + 孕妇去重 | x_conc≤-0.02：recall 52.3%/precision 56.1%；Z 值法失效 (4.5%) | 证据绑定 |

## 3. 失败点与根因修正（评审驱动）

| 失败点 | 根因 | 修正 | 映射 |
|---|---|---|---|
| Q1/Q3 简单回归高估显著性 | 重复测量不独立（267 孕妇 × 1082 记录）| 混合效应模型（ICC=0.761 证实）| **工具**（统计方法）|
| Q2 固定 BMI 区间无依据 | 分组未数据驱动 | K-means 聚类 + 肘部法则 | **工具**（聚类）|
| Q4 逻辑回归 recall=0 | 类别不平衡（11% 异常）+ 特征异质 | X 浓度阈值 + 孕妇去重 + 分型 | **知识**（特征选择）|
| 论文审批初评 84.4<85 | figures 缺图 + evidence 结构 | 补 3 图 + unresolved 字段 | **量表**（figures 维度）|

## 4. 审批分数（paper-quality 量表）

- 初评：**failed**（84.4 / threshold 85）——figures 75（缺图）
- 修订：补 3 图 + evidence 修复
- **终评：passed（85.9）**，findings=0，S0 规则 4/4

## 5. 人工复核结论

1. **方法学**：混合效应处理重复测量是必要修正（ICC=0.76 证明 OLS 不适用）；K-means 分组比固定区间严谨，与已发表方法一致。
2. **外部证据一致性**：BMI 负相关（Deng 2023, 153,306 例）、孕周正相关（ScienceDirect 2022）、Z 值 PPV 局限（ACMG 2022）——与文献方向一致。
3. **数据局限**：高 BMI 极端组样本少（~40.1 仅 10 人），置信区间宽；女胎 AB 标记与健康列不一致（检测疑似 vs 出生确认），Q4 标签敏感性未做——记录为遗留。
4. **工具缺口（Phase 8 发现，映射到工具）**：
   - `logistic-regression` executor 无 class_weight/自定义阈值 → 类别不平衡需外部调阈值
   - 二分类 coefficients 形状 `[[...]]` 需解包
   - review 引擎的 evidence_index/claim_id 格式要求明确（bare 文件名不合格）——已在 c_review.py 适配，建议文档化

## 6. 复现命令

```powershell
& ".venv\Scripts\python.exe" work\solve\c_q1.py   # Q1 混合效应
& ".venv\Scripts\python.exe" work\solve\c_q2.py   # Q2 K-means
& ".venv\Scripts\python.exe" work\solve\c_q3.py   # Q3 多因素
& ".venv\Scripts\python.exe" work\solve\c_q4.py   # Q4 女胎判定
& ".venv\Scripts\python.exe" work\solve\c_figs.py # 图表
& ".venv\Scripts\python.exe" work\solve\c_review.py  # 审批（passed 85.9）
```

## 7. 结论

2025-C 作为**首个真题代表场景**跑通完整链路（拆解→建模→论文→编译→审批），验证了 Phase 8 前构建的 26 模型能力在真实真题上的可用性，并发现 2 个工具缺口（logistic 阈值/系数形状）与 1 个统计方法要求（混合效应）。回归稳定后可按 `model-expansion-policy` 决定模型扩展。
