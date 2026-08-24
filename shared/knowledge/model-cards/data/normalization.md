---
model_id: normalization
category: data
title: 归一化
file: shared/knowledge/model-cards/data/normalization.md
status: draft
priority: 1
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

# 归一化

## 适用问题
消除不同指标量纲与量级差异，使各特征在同一尺度上参与距离计算、优化或加权，如 TOPSIS 前处理、聚类与神经网络输入。

## 禁用场景
树模型等对尺度不敏感的模型无需归一化；保留原始含义（如百分比）且不需要跨指标比较时不必归一；含极端离群值时 min-max 会被拉偏。

## 输入与假设
输入为数值特征矩阵；假设特征取值有意义且方向一致（或先做正向化）；归一化只改变尺度，不改变数据分布形态。

## 核心公式
min-max 归一化 x' = (x−min)/(max−min)；z-score 标准化 x' = (x−μ)/σ。

## 直观解释
min-max 把数值压到 [0,1]，z-score 把数据变成均值为 0、标准差为 1 的分布；两者都只是"换一把尺子"。

## 建模步骤
① 处理缺失与异常值；② 按方法需要决定正向化；③ 对训练集估计 min/max 或 μ/σ；④ 用同一组参数变换训练与测试数据。

## 参数选择
有界数据用 min-max；分布近似正态或含离群值时用 z-score；量纲差异巨大时二者皆可，但要防止极端值主导。

## 工具入口
sklearn.preprocessing.MinMaxScaler、sklearn.preprocessing.StandardScaler、sklearn.preprocessing.RobustScaler（抗离群）。

## 最小示例
`from sklearn.preprocessing import StandardScaler; Xs = StandardScaler().fit_transform(X)`。

## 评价指标
变换后各特征方差同量级（z-score 方差约为 1）；距离/聚类类模型在归一化前后的效果对比。

## 检验方法
检查变换后特征的均值/方差是否符合预期；确认测试数据使用与训练一致的统计量（防止数据泄漏）；目视散点图确认量级一致。

## 对比基线
基线为不归一化直接建模；若归一化后模型误差或收敛性没有改善，说明该模型本就不敏感（如树模型）。

## 替代模型
离群值多时用 RobustScaler 或分位数变换；需要保留稀疏结构时用 MaxAbsScaler；非线性分布可考虑 Box-Cox 变换。

## 常见误用
用全量数据（含测试集）计算 min/max 造成数据泄漏；对 0/1 哑变量做 z-score；先归一化再划分训练测试集。

## 失效征兆
归一化后仍有个别特征方差远大于其他特征；测试集变换后出现超出 [0,1] 的值（说明测试值超出训练范围）；模型表现与归一化前后无差异。

## 论文表达示例
"为消除量纲影响，采用 min-max 归一化将各指标映射至 [0,1]，并在划分训练集与测试集后仅用训练集统计量完成变换，避免了信息泄漏。"

## 对应练习
对多量纲数据分别用 MinMaxScaler 与 StandardScaler 并比较聚类结果；演示错误地用全量数据拟合 scaler 带来的泄漏后果。
