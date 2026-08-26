---
model_id: anova
category: statistics
title: 单因素方差分析（one-way ANOVA）
file: shared/knowledge/model-cards/statistics/anova.md
status: active
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

# 单因素方差分析

## 适用问题

用一个分类因素比较两个或以上独立组的总体均值是否全相等，例如比较不同方案、批次或处理水平的连续结果。`anova` 只执行单因素、组间独立的总体（omnibus）检验。

## 禁用场景

它不适用于重复测量、配对数据、多因素设计或含协变量的比较；这些分别需要重复测量 ANOVA、配对方法、析因 ANOVA 或 ANCOVA。若独立性、近似正态性或方差齐性明显不合理，可考虑 Kruskal–Wallis 等替代方法。

## 输入与假设

调用 `execute("anova", {"groups": groups})`，其中 `groups` 是至少两个非空的 JSON 数值数组。所有数值必须是有限的内建 `int` 或 `float`，每组代表一个独立样本。总样本数必须大于组数，且总变异和组内变异都必须为正，避免未定义或无穷大的 F 统计量。

## 核心公式

令第 \(i\) 组样本量为 \(n_i\)、组均值为 \(\bar{x}_i\)、总均值为 \(\bar{x}\)，组数为 \(k\)、总样本数为 \(N\)：

\[
SS_B=\sum_i n_i(\bar{x}_i-\bar{x})^2,\quad
SS_W=\sum_i\sum_j(x_{ij}-\bar{x}_i)^2,\quad
SS_T=SS_B+SS_W.
\]

\[
df_B=k-1,\quad df_W=N-k,\quad
MS_B=SS_B/df_B,\quad MS_W=SS_W/df_W,\quad F=MS_B/MS_W.
\]

执行器使用 F 分布生存函数计算 `p_value`，并给出效应量 \(\eta^2=SS_B/SS_T\)。

## 直观解释

ANOVA 将观测到的总波动拆成组均值之间的波动和每组内部的波动。当组间均方相对组内均方很大时，F 值变大，说明“所有组均值相等”的零假设与数据不相符。

## 建模步骤

1. 确认各组对应独立观测，检查异常值、分布形态和方差齐性。
2. 将每组连续观测整理为 `groups` 中的一个数组。
3. 运行 `execute("anova", {"groups": groups})`。
4. 报告 `statistic`（F）、`p_value`、自由度、平方和、均方和与 `eta_squared`，并结合研究情境解释效应大小。

## 参数选择

此入口没有显著性水平、备择方向、随机种子或事后比较参数。显著性阈值由报告或研究方案在执行器外预先定义；执行器只返回计算出的 p 值。

## 工具入口

Python 统一入口：`cumcm_toolkit.models.execution.execute`。模型 ID 固定为 `anova`，payload 只接受 `groups`，不接受 Tukey、Bonferroni 或成对比较字段。

## 最小示例

```python
from cumcm_toolkit.models.execution import execute

out = execute("anova", {"groups": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]})
print(out["result"]["statistic"])
print(out["result"]["p_value"])
```

`result` 包含 `statistic`、`p_value`、`df_between`、`df_within`、`ss_between`、`ss_within`、`ss_total`、`ms_between`、`ms_within` 和 `eta_squared`。诊断字段明确标记 `post_hoc: "not_performed"`。

## 评价指标

F 和 p 值描述均值相等零假设的证据；`eta_squared` 描述因素解释的样本总变异比例。平方和和均方支持复核计算，但不替代实际问题中的效应解释。

## 检验方法

可在执行前使用残差图、Q–Q 图和 Levene 等诊断评估假设。该执行器不自动运行或解释这些诊断，也不会自动把统计显著性翻译成实际重要性。

## 对比基线

零假设是所有组有相同的总体均值。若只有两组，ANOVA 与等方差双样本 t 检验在相同假设下等价；多组时 ANOVA 避免把多个未校正 t 检验混在一起。

## 替代模型

方差齐性问题可使用 Welch ANOVA（本入口未实现）；分布或尺度不适合时考虑 Kruskal–Wallis；有协变量或层级、重复测量结构时使用相应的回归或混合模型。

## 常见误用

显著的 omnibus ANOVA **不说明哪一对组不同**，也不说明所有组两两不同。`anova` 不产生任何成对结论或多重比较校正；若需要事后比较，必须在另一个明确声明比较方案、校正方法和输出契约的分析步骤中完成。

## 失效征兆

任一组为空、组数少于两组、`df_within` 不足、所有数据没有总变异，或组内变异为零时，入口会失败而不是输出 NaN、无穷 F 或部分成功结果。极端尺度导致平方和无法以有限 JSON 数字表示时也会失败关闭。

## 论文表达示例

“对三种处理的结果实施单因素方差分析，得到 \(F(2,6)=27.00\)、\(p<0.001\)、\(\eta^2=0.90\)，表明至少一组总体均值与其他组不全相等。该总体检验未识别具体差异组对，未在本分析中报告事后两两比较。”

## 对应练习

用三组有限数值样本计算 `anova`，手工核对 \(SS_T=SS_B+SS_W\)、F 和 \(\eta^2\)。随后说明：即使 p 值显著，为什么仍不能从本执行器的输出断言某个具体组对存在差异。
