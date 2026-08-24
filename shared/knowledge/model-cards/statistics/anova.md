---
model_id: anova
category: statistics
title: 方差分析
file: shared/knowledge/model-cards/statistics/anova.md
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

# 方差分析

## 适用问题
比较三个及以上组的均值是否有显著差异，如不同方案/批次/水平对结果的影响。

## 禁用场景
只比较两组时用 t 检验；正态与方差齐性假设严重不满足时需 Kruskal-Wallis；重复测量结构需专门设计。

## 输入与假设
输入为分组变量与连续因变量；假设各组独立、近似正态、方差齐性。

## 核心公式
F = MS_组间/MS_组内，MS 为平方和除以自由度；单因素 SST = SSB + SSW；p<0.05 拒绝"各组均值全相等"。

## 直观解释
把总变异拆成"组间差异"与"组内随机波动"两块，组间占比足够大就说明分组确实有影响。

## 建模步骤
① 检查正态与方差齐性；② 建立单/双因素 ANOVA；③ 计算 F 与 p；④ 显著时做事后多重比较（Tukey HSD）。

## 参数选择
因素与水平设置；α=0.05；事后检验方法（Tukey HSD/Bonferroni）；随机效应 vs 固定效应。

## 工具入口
scipy.stats.f_oneway、statsmodels.formula.api.ols 配合 anova_lm、statsmodels.stats.multicomp.pairwise_tukeyhsd。

## 最小示例
`from scipy.stats import f_oneway; f, p = f_oneway(g1, g2, g3)`；Tukey：`pairwise_tukeyhsd(data, groups)`。

## 评价指标
F 统计量与 p；η² 效应量（组间平方和占比）；事后比较的差异对。

## 检验方法
Levene 方差齐性检验；Shapiro 正态检验；残差 vs 拟合图；Tukey 置信区间目视。

## 对比基线
基线为"各组均值无差异"零假设；与 Kruskal-Wallis 对照。

## 替代模型
正态不满足用 Kruskal-Wallis；多个协变量用 ANCOVA；重复测量用混合模型。

## 常见误用
ANOVA 显著就认为"所有组两两都不同"（需事后检验）；忽略方差齐性；把组内相关数据当独立样本。

## 失效征兆
Levene 检验显著且组样本量悬殊；F 显著但事后检验全不显著（样本量大效应小）；残差呈喇叭状。

## 论文表达示例
"单因素方差分析 F=5.32、p=0.004<0.05，三组均值存在显著差异，η²=0.31；Tukey HSD 事后检验显示 A 组显著高于 B、C 组（p<0.05），B、C 间无显著差异。"

## 对应练习
对三组数据做 ANOVA 与 Tukey 事后检验；比较 f_oneway 与 Kruskal 的结论。
