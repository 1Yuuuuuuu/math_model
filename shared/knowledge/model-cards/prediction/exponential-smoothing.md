---
model_id: exponential-smoothing
category: prediction
title: 指数平滑
file: shared/knowledge/model-cards/prediction/exponential-smoothing.md
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

# 指数平滑

## 适用问题
单变量时间序列短期预测，尤其数据量不大、趋势/季节模式简单稳定时，如库存、客流、销量短期预报。

## 禁用场景
序列含强随机波动或突变时预测失真；长期预测误差累积大；多变量影响明显时应考虑回归类模型。

## 输入与假设
输入为等间隔时间序列；假设近期观测比远期更有信息量（权重指数衰减），且水平/趋势/季节模式稳定。

## 核心公式
一次平滑 Sₜ = αyₜ + (1−α)Sₜ₋₁；Holt 双参数加趋势；Holt-Winters 三参数加季节；α、β、γ 为平滑系数。

## 直观解释
预测是"对历史做加权平均"，越近的数据权重越大；Holt-Winters 相当于把水平、趋势、季节三件事分别平滑再组合。

## 建模步骤
① 画图判断趋势与季节；② 选模型阶数（SES/Holt/Holt-Winters）；③ 用 statsmodels 拟合自动选参；④ 检查残差并预测。

## 参数选择
平滑系数可由 statsmodels 自动优化（如 α 在 0.1-0.9 搜索）；季节周期长度需指定（如 12 个月/7 天）；是否加阻尼趋势。

## 工具入口
statsmodels.tsa.holtwinters.ExponentialSmoothing、statsmodels.tsa.holtwinters.SimpleExpSmoothing。

## 最小示例
`from statsmodels.tsa.holtwinters import ExponentialSmoothing; fit = ExponentialSmoothing(y, trend="add", seasonal="add", seasonal_periods=12).fit(); fit.forecast(3)`。

## 评价指标
RMSE/MAE/MAPE；样本外预测误差；AIC/BIC 比较模型；预测区间覆盖率。

## 检验方法
残差白噪声检验（Ljung-Box）；时间序列交叉验证（滚动原点）；训练/测试切分比较预测误差。

## 对比基线
基线为朴素预测（上期值）或简单平均；若平滑预测 RMSE 不低于朴素法，说明序列近乎随机游走。

## 替代模型
序列有自相关与趋势时用 ARIMA；含解释变量用回归/动态回归；非线性长记忆用机器学习时序模型。

## 常见误用
对非平稳序列直接预测而不检查；季节周期设错；把平滑系数调成极端值过拟合近期噪声。

## 失效征兆
残差显著自相关（信息未提取干净）；预测值出现负值而业务不允许；样本外误差远大于样本内误差。

## 论文表达示例
"采用 Holt-Winters 加法季节模型（周期 12）拟合月度销量，样本外 3 期预测 MAPE 为 4.8%，残差 Ljung-Box 检验 p=0.31 通过白噪声假设，预测可靠。"

## 对应练习
对含季节的序列分别用 SES 与 Holt-Winters 预测并比较 RMSE；检查残差自相关。
