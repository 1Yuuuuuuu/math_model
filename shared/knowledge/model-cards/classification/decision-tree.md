---
model_id: decision-tree
category: classification
title: 决策树
file: shared/knowledge/model-cards/classification/decision-tree.md
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

# 决策树

## 适用问题
可解释的分类/回归任务、规则提取、特征重要性分析，如信用审批规则、故障诊断规则。

## 禁用场景
数据量大且特征多时单棵树易过拟合；特征取值连续且关系复杂时精度不如集成；对稳定性要求高时单树易变。

## 输入与假设
输入为特征与标签；假设可按特征取值递归划分使子集更纯，特征间关系可由分段常数近似。

## 核心公式
划分准则：信息增益（ID3）、增益率（C4.5）、基尼指数（CART）Gini(D)=1−Σpₖ²；递归划分至停止条件。

## 直观解释
像"二十个问题"游戏，每次问一个最能区分类别的特征，沿树走到叶子给出预测。

## 建模步骤
① 划分训练/测试；② 设 max_depth、min_samples_split；③ 拟合决策树；④ 剪枝/调参；⑤ 可视化并提取规则。

## 参数选择
max_depth（3-10）、min_samples_split、min_samples_leaf、criterion（gini/entropy）；用交叉验证选。

## 工具入口
sklearn.tree.DecisionTreeClassifier、sklearn.tree.plot_tree/export_text、sklearn.ensemble.RandomForestClassifier。

## 最小示例
`from sklearn.tree import DecisionTreeClassifier; clf = DecisionTreeClassifier(max_depth=4).fit(Xtr, ytr); export_text(clf)`。

## 评价指标
准确率/F1/AUC；树的深度与叶子数（复杂度）；特征重要性排序。

## 检验方法
交叉验证；测试集混淆矩阵；与剪枝前后对比；重要性稳定性检查。

## 对比基线
基线为多数类或逻辑回归；若决策树精度不高于逻辑回归且解释需求不高，可用后者。

## 替代模型
提升精度用随机森林/GBDT/XGBoost；连续决策面用 SVM；概率输出用逻辑回归。

## 常见误用
不设深度限制导致完全过拟合；在重要连续特征上解释叶子阈值过度外推；对不平衡数据不设 class_weight。

## 失效征兆
训练精度 100% 而测试大幅下降；树结构随数据微扰剧变；特征重要性集中在无关特征。

## 论文表达示例
"建立深度为 4 的 CART 决策树，测试集准确率 0.85，基尼指数显示变量 X 重要性最高；提取的规则如'若 X>3.2 且 Y=1 则判为合格'可直接用于业务解释。"

## 对应练习
用决策树拟合并 export_text 提取规则；改变 max_depth 观察训练/测试误差曲线。
