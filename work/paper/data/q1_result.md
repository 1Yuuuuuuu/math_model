# 2025-C 问题 1 结果（Y 染色体浓度与孕周、BMI 的关系模型）— 混合效应修正版

> 运行：`work/solve/c_q1.py`（评审 P0-1 修正：混合效应处理重复测量）
> 数据：男胎 950 条记录 / 260 位孕妇（平均 3.65 次检测/人）

## 方法学修正

原简单回归把每条记录当独立样本（违反独立性假设）。改为**线性混合效应模型**：
`y_conc ~ week + bmi + (1 | mother_id)`（孕妇随机截距）。

## 混合效应结果

| 项 | 估计 | p 值 |
|---|---|---|
| 固定截距 | 0.0662 | - |
| **week** | **+0.00322** | **1.2e-73** |
| **bmi** | **-0.00131** | **0.0199** |
| 孕妇随机效应 SD | 0.0296 | - |
| 残差 SD | 0.0166 | - |
| **ICC** | **0.761** | 76% 方差来自孕妇间 |

## 与 OLS 对照

| 指标 | OLS（旧） | 混合效应（新） |
|---|---|---|
| week 系数 | 0.00112 | 0.00322（更强）|
| week p | 7e-4 | 1e-73（更显著）|
| bmi 系数 | -0.00180 | -0.00131 |
| bmi p | 显著 | 0.0199 |

**ICC=0.761 证实重复测量严重不独立**——OL S 低估 week 效应、高估显著性；混合效应更严谨且 week 效应更强。

## 按孕妇聚合的相关（去重复）

- Y 浓度 ~ 孕周：r = -0.184（p=0.0029）——注意聚合后为负（与记录级不同，因孕妇间差异主导）
- Y 浓度 ~ BMI：r = -0.199（p=0.0012）——负相关稳健

## 外部证据对照

- **Deng et al. 2023**（153,306 例回顾）：BMI 与 fetal fraction 负相关 → 与 bmi 系数为负一致
- **ScienceDirect 2022**（fetal fraction 与孕周/性别）：fetal fraction 随孕周增长（非线性）、男胎高于女胎 → 支持 week 正系数与按性别分数据

## 结论

1. 孕周正相关（混合效应 p<1e-73）、BMI 负相关（p=0.02）——均显著
2. **个体差异主导**（ICC=76%），全局模型解释力有限，支持分组建模（Q2/Q3）
3. 与外部大样本证据方向一致

## 参考

- Deng C, et al. Maternal and fetal factors influencing fetal fraction: 153,306 cases. Frontiers in Pediatrics, 2023. https://pmc.ncbi.nlm.nih.gov/articles/PMC10126334/
- Non-intuitive trends of fetal fraction development related to gestational age and fetal gender. ScienceDirect, 2022. https://www.sciencedirect.com/science/article/pii/S0890850822000810
