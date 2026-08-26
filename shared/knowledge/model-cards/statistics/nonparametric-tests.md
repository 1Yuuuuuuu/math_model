---
model_id: nonparametric-tests
category: statistics
title: 非参数检验
file: shared/knowledge/model-cards/statistics/nonparametric-tests.md
status: draft
priority: 3
required_sections:
  - 适用问题
  - 禁用场景
  - 输入与假设
  - 核心公式
  - 直观解释
  - 建模步骤
  - 参数选择
  - 工具入口
  - 最小示例
  - 评价指标
  - 检验方法
  - 对比基线
  - 替代模型
  - 常见误用
  - 失效征兆
  - 论文表达示例
  - 对应练习
---

# 非参数检验

## 适用问题
分布未知、非正态、样本量小或数据为等级尺度时的假设检验，如两组中位数比较、顺序评分差异。

## 禁用场景
数据满足正态假设时非参数检验功效较低（更易漏检）；样本量足够大且正态时优先 t 检验；需要估计参数（均值差）时非参数只给位置差异。

## 输入与假设
执行器支持独立两组的 Mann–Whitney U、配对两组的 Wilcoxon、至少两组独立样本的 Kruskal–Wallis，以及至少 2×2 的列联表卡方独立性检验。输入必须为有限、非布尔数值；Wilcoxon 样本必须等长，列联表计数必须非负且每行、每列总数为正。秩检验不要求正态，但仍要求与方法匹配的独立或配对设计。

## 核心公式
Mann–Whitney U 基于两组联合秩；Wilcoxon 对非零配对差值的绝对值排秩；Kruskal–Wallis 是多组秩的 ANOVA 类比；卡方检验比较观察频数与独立性假设下的期望频数。执行器分别报告秩二列相关、配对秩二列相关、epsilon-squared 或 Cramér's V 作为效应量。

## 直观解释
不看原始数值大小，只看"谁排在谁前面"（秩），用秩的差异判断两组是否有系统性高低之分。

## 建模步骤
① 判断数据类型与配对关系；② 选检验（两组独立 U / 配对符号秩 / 多组 K-W）；③ 计算统计量与 p；④ 报告秩中位数与结论。

## 参数选择
单/双尾；α=0.05；多组事后比较（Dunn 检验）需校正；存在并列秩（ties）时注意方法要求。

## 工具入口
统一入口为 `cumcm_toolkit.models.execute("nonparametric-test", payload)`，内部使用 `scipy.stats.mannwhitneyu`、`wilcoxon`、`kruskal` 或 `chi2_contingency`。结果至少包含有限的 `statistic`、`p_value` 和可定义的 `effect_size`；卡方还返回 `expected_counts`。

## 最小示例
```python
from cumcm_toolkit.models import execute

result = execute("nonparametric-test", {
    "test": "mann-whitney-u",
    "sample_a": [1, 2, 3],
    "sample_b": [4, 5, 7],
    "alternative": "two-sided",
})
```

Mann–Whitney U 与 Wilcoxon 的 `alternative` 可取 `two-sided`、`less` 或 `greater`，缺省为双侧。Kruskal–Wallis 与卡方不接收该字段。卡方的任一期望频数小于 5 时仍返回计算结果，并在 `warnings` 中提示适用性风险；全零 Wilcoxon 差值、退化秩样本或任何非有限结果均失败关闭。

## 评价指标
p 值；秩中位数差；检验功效（样本量足够时）；效应量（如 r=Z/√n）。

## 检验方法
分布图确认非正态；与参数检验结果对照；bootstrap 验证稳定性。

## 对比基线
基线为 t 检验（若正态）；两者结论一致时报告参数检验更有利（功效高）。

## 替代模型
正态满足用 t 检验/ANOVA；多组用 Kruskal-Wallis；配伍多组用 Friedman 检验。

## 常见误用
数据正态仍用非参数损失功效；把秩检验解读为"均值差异"；样本非独立仍用 U 检验。

## 失效征兆
p 值恰好卡在 0.05 附近且对剔除一个点极敏感；结论与均值差异观感矛盾（中位数 vs 均值）。

## 论文表达示例
"两组评分数据 Shapiro 检验拒绝正态（p<0.05），改用 Mann-Whitney U 检验，U=1423、p=0.018<0.05，A 组秩中位数显著更高，结论稳健。"

## 对应练习
对非正态数据分别做 t 检验与 Mann-Whitney U 并比较结论；尝试 Wilcoxon 配对检验。
