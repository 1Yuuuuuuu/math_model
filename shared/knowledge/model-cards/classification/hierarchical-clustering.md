---
model_id: hierarchical-clustering
category: classification
title: 层次聚类
file: shared/knowledge/model-cards/classification/hierarchical-clustering.md
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

# 层次聚类

## 适用问题
样本量适中（几百以内）时希望获得层次结构或自动确定簇数，如物种分类、文档主题树。

## 禁用场景
样本量大（上万）时凝聚算法 O(n²) 以上不可行；数据含强噪声时单连接法易链式效应；需要扁平硬分类时 K-means 更简单。

## 输入与假设
输入为样本间距离矩阵；假设簇之间存在可度量的相似性层次。

## 核心公式
凝聚式从每点一簇开始，合并距离最近的两簇（单/全/平均连接），生成树状图；簇间距离定义决定簇形状。

## 直观解释
从每个点各成一类开始，把"最近的"两类并起来，一层层往上，得到一棵聚类树（树状图），沿树切一刀即得 K 类。

## 建模步骤
① 计算距离矩阵；② 选连接准则；③ 凝聚聚类生成树状图；④ 按业务或拐点切树定 K；⑤ 解释各簇。

## 参数选择
连接准则（ward 默认较好/单连接易链式/平均居中）；距离度量（欧氏/余弦）；切树高度或 K。

## 工具入口
scipy.cluster.hierarchy.linkage/dendrogram/fcluster、sklearn.cluster.AgglomerativeClustering。

## 最小示例
`from scipy.cluster.hierarchy import linkage, fcluster; Z = linkage(X, method="ward"); labels = fcluster(Z, t=3, criterion="maxclust")`。

## 评价指标
轮廓系数；树状图的结构清晰度；与 K-means 结果的一致性；业务可解释性。

## 检验方法
不同连接准则对比；不同距离度量稳定性；与 K-means 聚类交叉验证。

## 对比基线
基线为 K-means；若两者簇结构差异大，检查数据是否适合球形假设。

## 替代模型
大样本用 K-means/MiniBatchKMeans；非凸簇用 DBSCAN；需要概率归属用高斯混合模型。

## 常见误用
单连接在噪声下产生链式簇；对超大样本硬跑；用原始量纲距离不标准化。

## 失效征兆
树状图出现长链（链式效应）；切树结果对高度微调极敏感；与 K-means 结论冲突。

## 论文表达示例
"采用 ward 连接凝聚层次聚类，树状图在高度 2.1 处切分为 4 簇，轮廓系数 0.48，与 K-means 结果 82% 一致，簇结构稳定。"

## 对应练习
对给定数据画树状图并尝试不同连接准则；比较切树定 K 与肘部法则的差异。
