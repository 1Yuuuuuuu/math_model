---
model_id: kmeans
category: classification
title: K-means 聚类
file: shared/knowledge/model-cards/classification/kmeans.md
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

# K-means 聚类

## 适用问题
数值型数据的无监督聚类，把样本分成 K 个紧凑组，如客户分群、区域划分、图像压缩。

## 禁用场景
类别为非凸形状或嵌套时效果差；类别数 K 未知且无业务依据时需谨慎；含类别变量或离群值多时需先处理。

## 输入与假设
输入为数值特征矩阵与 K；假设簇大致为球形、大小相近，欧氏距离度量有意义。

## 核心公式
目标 min Σₖ Σ_{i∈Cₖ} ‖xᵢ−μₖ‖²；迭代：分配（最近质心）→ 更新质心（组均值）直至收敛。

## 直观解释
先随便放 K 个中心，把点归给最近的中心，再把中心挪到组内平均位置，反复直到稳定。

## 建模步骤
① 标准化并处理离群；② 选 K（肘部/轮廓系数）；③ 多随机初始化运行取最优；④ 解释簇特征。

## 参数选择
K 用肘部法则、轮廓系数或业务确定；n_init（≥10）与随机种子；max_iter；初始化方法 k-means++。

## 工具入口
sklearn.cluster.KMeans（默认 k-means++）、sklearn.metrics.silhouette_score、sklearn.preprocessing 标准化。

## 最小示例
`from sklearn.cluster import KMeans; km = KMeans(n_clusters=3, n_init=10).fit(X); km.labels_; km.cluster_centers_`。

## 评价指标
轮廓系数（大于 0.5 较理想）；组内平方和（SSE）肘部；簇间距离与簇内紧密度；业务可解释性。

## 检验方法
不同 K 与随机种子下稳定性；降维（PCA）可视化检查簇形状；样本子集重复聚类对比。

## 对比基线
基线为 K=1（不聚类）的 SSE；或与层次聚类对比簇结构。

## 替代模型
非凸簇用 DBSCAN；未知 K 用层次聚类/DBSCAN；类别混合数据用 K-prototypes。

## 常见误用
未标准化直接用原始量纲（距离被大数值特征主导）；K 拍脑袋且不验证；把聚类标签当分类预测用。

## 失效征兆
轮廓系数接近 0 或为负；不同 n_init 结果差异大（局部最优）；簇中心与数据分布明显不符。

## 论文表达示例
"对标准化后的客户特征做 K-means 聚类，肘部法则确定 K=4，轮廓系数 0.52；各簇中心差异显著，据此将客户分为 4 类并给出差异化策略。"

## 对应练习
对标准化数据计算 K=2-8 的 SSE 与轮廓系数并选 K；比较不同 n_init 下的稳定性。
