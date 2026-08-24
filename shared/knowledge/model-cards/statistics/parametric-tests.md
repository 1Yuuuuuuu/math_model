---
model_id: parametric-tests
category: statistics
title: 参数检验
file: shared/knowledge/model-cards/statistics/parametric-tests.md
status: draft
priority: 2
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

# 参数检验

## 适用问题
在总体分布已知（如正态）假设下比较均值/方差等参数，如两组均值差异、单样本与标准值比较。

## 禁用场景
分布严重偏离正态且样本量小时 t 检验不稳健；数据为等级或顺序尺度；方差差异悬殊（先做 Levene 检验，必要时用 Welch）。

## 输入与假设
输入为数值样本；t 检验假设近似正态与方差齐性（Welch 版放宽后者）；样本独立（配对 t 除外）。

## 核心公式
单样本 t = (x̄−μ₀)/(s/√n)；两独立样本 t 用合并方差；配对 t 对差值做单样本 t；p<0.05 拒绝原假设。

## 直观解释
看样本均值与假设均值的差距相对于抽样波动（标准误）有多大，差距足够大就拒绝"无差异"假设。

## 建模步骤
① 检验正态性（Shapiro）与方差齐性（Levene）；② 选检验类型；③ 计算统计量与 p 值；④ 报告效应量与结论。

## 参数选择
单/双尾（由业务方向决定）；α 取 0.05；方差不等时用 Welch 校正；多重比较需校正 p 值。

## 工具入口
scipy.stats.ttest_ind、scipy.stats.ttest_rel、scipy.stats.ttest_1samp、scipy.stats.shapiro、scipy.stats.levene。

## 最小示例
`from scipy.stats import ttest_ind; t, p = ttest_ind(a, b, equal_var=False)`。

## 评价指标
p 值与效应量（Cohen's d）；检验功效；置信区间宽度。

## 检验方法
正态性/方差齐性前置检验；bootstrap 验证；与效应量联合解读避免"显著但无意义"。

## 对比基线
基线为"无差异"零假设；与非参数检验（Wilcoxon/Mann-Whitney）结果对照。

## 替代模型
正态假设不满足时用 Mann-Whitney U/Wilcoxon；三组以上用 ANOVA；配对非正态用符号秩检验。

## 常见误用
不检查正态性直接 t 检验；多重比较不校正；把 p 值当效应大小；样本不独立仍用独立 t 检验。

## 失效征兆
Shapiro 检验拒绝正态且样本小；t 检验结论与箱线图观感矛盾；Levene 显著但未用 Welch。

## 论文表达示例
"两组数据 Shapiro 检验 p=0.32、Levene 检验 p=0.18，满足正态与方差齐性；独立样本 t 检验 t=2.87、p=0.006<0.05，拒绝无差异假设，Cohen's d=0.62 为中等效应。"

## 对应练习
对两组数据做正态性检查后选 t 检验或非参数检验；比较 Welch 与合并方差 t 的结果差异。
