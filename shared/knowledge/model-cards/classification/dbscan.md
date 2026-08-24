---
model_id: dbscan
category: classification
title: DBSCAN 聚类
file: shared/knowledge/model-cards/classification/dbscan.md
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

# DBSCAN 聚类

## 适用问题
簇形状任意（非凸）、含噪声点、簇数未知的聚类，如地理点位聚簇、异常点识别。

## 禁用场景
簇密度差异悬殊时一个参数难以兼顾；高维数据距离意义弱化；样本量小且无噪声时 K-means 更直接。

## 输入与假设
输入为距离度量与参数 (eps, min_samples)；假设簇内密度高于簇间，噪声点密度低。

## 核心公式
点 p 的 ε-邻域 Nε(p)={q: d(p,q)≤ε}；核心点满足 |Nε(p)|≥min_samples；密度可达/密度相连定义簇，其余为噪声。

## 直观解释
把"抱团够密"的点连成一簇，四周稀疏的点直接标为噪声；不需要预先指定簇数。

## 建模步骤
① 标准化；② 用 k-距离图或经验选 eps；③ 调 min_samples（常取 2×维度）；④ 聚类并检查噪声占比。

## 参数选择
eps 用 k-距离图拐点；min_samples 常取 2×d（d 为维度）或更大；距离度量（欧氏）。

## 工具入口
sklearn.cluster.DBSCAN、sklearn.neighbors.NearestNeighbors（k-距离图）、sklearn.metrics.silhouette_score。

## 最小示例
`from sklearn.cluster import DBSCAN; db = DBSCAN(eps=0.5, min_samples=5).fit(X); db.labels_`（-1 为噪声）。

## 评价指标
簇数、噪声占比；轮廓系数；与真实结构对比的纯度；参数敏感性。

## 检验方法
k-距离图验证 eps 选择；不同 eps 的簇结构稳定性；与 K-means/层次聚类对比。

## 对比基线
基线为 K-means（固定 K）；若数据含大量噪声，DBSCAN 的噪声处理优势明显。

## 替代模型
密度差异大用 OPTICS；高维用 HDBSCAN 或先降维；球形簇用 K-means。

## 常见误用
eps 拍脑袋导致全部点一簇或全是噪声；未标准化就设 eps；高维数据直接 DBSCAN 效果差。

## 失效征兆
噪声占比过高（>30%）或为 0（eps 过大）；簇数对 eps 微调剧烈变化；簇内点分布与业务不符。

## 论文表达示例
"基于 k-距离图确定 eps=0.42，min_samples=5 运行 DBSCAN，识别出 6 个簇与 3.2% 的噪声点，噪声点经复核为设备异常记录，聚类结果符合实际分布。"

## 对应练习
绘制 k-距离图选 eps 并用 DBSCAN 聚类；比较 DBSCAN 与 K-means 在含噪声数据上的差异。
