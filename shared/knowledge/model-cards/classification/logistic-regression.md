---
model_id: logistic-regression
category: classification
title: 逻辑回归
file: shared/knowledge/model-cards/classification/logistic-regression.md
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

# 逻辑回归

## 适用问题
二分类（可扩展多分类）概率预测与影响因素分析，如是否违约、是否合格，输出类别概率。

## 禁用场景
类别严重不平衡且未处理时概率偏移；特征强共线性导致系数不稳定；需要复杂非线性边界时线性决策面不足。

## 输入与假设
输入为特征矩阵与 0/1 标签；假设对数几率与特征线性相关，样本独立，无严重共线性。

## 核心公式
P(y=1|x) = 1/(1+e^(−βᵀx))；系数用最大似然估计，损失为对数损失，可加 L1/L2 正则化。

## 直观解释
把线性组合的值压缩到 (0,1) 当作概率；系数为正表示该特征增加"属于 1 类"的几率。

## 建模步骤
① 检查类别分布与缺失；② 划分训练/测试；③ 标准化特征；④ 拟合并加正则；⑤ 评估混淆矩阵与 AUC。

## 参数选择
正则化强度 C（网格搜索）；L1/L2 选择（L1 可做特征选择）；class_weight 处理不平衡；是否标准化。

## 工具入口
sklearn.linear_model.LogisticRegression、statsmodels.api.Logit（统计推断）、sklearn.metrics 评估。

## 最小示例
`from sklearn.linear_model import LogisticRegression; clf = LogisticRegression(C=0.1).fit(Xtr, ytr); clf.predict_proba(Xte)`。

## 评价指标
准确率（类别平衡时）、精确率/召回率/F1、AUC-ROC；系数显著性（statsmodels 版）。

## 检验方法
分层交叉验证；混淆矩阵与 ROC 曲线；校准曲线检查概率可靠性；系数符号业务合理性。

## 对比基线
基线为多数类预测（准确率=多数类占比）；AUC>0.5 且优于基线才有建模价值。

## 替代模型
非线性边界用决策树/随机森林/XGBoost；多分类用 softmax 回归或 OvR 逻辑回归；序列用马尔可夫/时序分类。

## 常见误用
对不平衡数据只看准确率；未标准化导致系数解释混乱；把预测概率当精确概率不做校准。

## 失效征兆
AUC 接近 0.5（无区分度）；系数符号与业务矛盾且 VIF 高；校准曲线严重偏离对角线。

## 论文表达示例
"构建逻辑回归分类模型，5 折交叉验证 AUC=0.86，精确率 0.82、召回率 0.79；系数显示变量 X 每增加一个标准差，违约几率提升 45%（p<0.01）。"

## 对应练习
用 sklearn 拟合逻辑回归并画 ROC 曲线；比较 C 值对 AUC 与系数幅度的影响。
