---
model_id: ml-regression
category: prediction
title: 机器学习回归
file: shared/knowledge/model-cards/prediction/ml-regression.md
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

# 机器学习回归

## 适用问题
特征多、关系复杂非线性、数据量中等以上时的预测回归，如房价、能耗、销量的多变量预测。

## 禁用场景
样本量过小（如少于几百）时复杂模型过拟合；强解释性要求时优先线性或树模型白盒；数据泄漏未排查时结果不可信。

## 输入与假设
输入为特征矩阵与连续目标；假设样本独立、特征信息充分、分布相对稳定（无严重分布漂移）。

## 核心公式
随机森林预测为各树均值 f̂(x)=(1/T)Σfₜ(x)；梯度提升为加性模型 f̂(x)=Σρₜhₜ(x)，逐步拟合负梯度。

## 直观解释
随机森林让很多棵树投票平均，方差小；梯度提升让每棵树专攻上一轮的错误，拟合能力强但需控制过拟合。

## 建模步骤
① 清洗与特征工程；② 划分训练/验证/测试；③ 交叉验证选模型与超参；④ 评估样本外误差并做特征重要性分析。

## 参数选择
随机森林的 n_estimators、max_depth、max_features；GBDT 的学习率、n_estimators、max_depth、subsample；用 GridSearchCV/RandomizedSearchCV 搜索。

## 工具入口
sklearn.ensemble.RandomForestRegressor、sklearn.ensemble.GradientBoostingRegressor、sklearn.model_selection.GridSearchCV、xgboost.XGBRegressor、lightgbm.LGBMRegressor。

## 最小示例
`from sklearn.ensemble import RandomForestRegressor; m = RandomForestRegressor(n_estimators=200).fit(Xtr, ytr); m.predict(Xte)`。

## 评价指标
样本外 RMSE/MAE/MAPE、R²；交叉验证方差；特征重要性排序稳定性。

## 检验方法
分层交叉验证（KFold/ShuffleSplit）；训练-测试误差差（过拟合检测）；与线性基线对比；特征重要性可解释性检查。

## 对比基线
基线为线性回归或岭回归；若复杂模型样本外误差不显著低于线性基线（如改善不足 5%），选线性更稳妥。

## 替代模型
树模型解释性不够时用线性/广义线性；类别不平衡或多分类用分类模型；时间序列用带滞后特征的回归或专用时序模型。

## 常见误用
用全量数据做特征选择造成泄漏；调参只盯训练误差；对强时序数据随机打乱划分导致泄漏。

## 失效征兆
训练误差远小于验证误差（过拟合）；特征重要性集中在泄漏变量；样本外误差远大于交叉验证估计。

## 论文表达示例
"采用随机森林回归建模，5 折交叉验证 RMSE 较线性回归降低 18%，特征重要性显示 X 为主要驱动因素；为防止过拟合，限制 max_depth=8，训练与验证误差差控制在 6% 以内。"

## 对应练习
对给定数据集比较线性回归与随机森林的交叉验证误差；做一次 GridSearchCV 并报告最优参数。
