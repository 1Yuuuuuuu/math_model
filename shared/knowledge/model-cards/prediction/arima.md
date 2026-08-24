---
model_id: arima
category: prediction
title: ARIMA 时间序列模型
file: shared/knowledge/model-cards/prediction/arima.md
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

# ARIMA 时间序列模型

## 适用问题
单变量时间序列建模与预测，适合有明显自相关结构和趋势的平稳或差分平稳序列，如经济指标、客流、价格预测。

## 禁用场景
数据量太小（一般要求不少于 50 个观测）；含强季节时需加季节分量（SARIMA）或改用季节分解；多变量影响强时需回归类模型。

## 输入与假设
输入为等间隔单变量序列；假设差分后平稳（弱平稳），残差为白噪声，模型阶数 (p,d,q) 恰当。

## 核心公式
yₜ = c + Σφᵢyₜ₋ᵢ + Σθⱼεₜ₋ⱼ + εₜ（ARMA(p,q)），d 次差分处理趋势；SARIMA 增加季节项 (P,D,Q,m)。

## 直观解释
AR 项用"过去的自己"解释现在，MA 项用"过去的误差"修正现在，差分把趋势变成波动再建模。

## 建模步骤
① ADF 检验平稳性并定差分阶 d；② 看 ACF/PACF 或信息准则定 p、q；③ statsmodels 拟合并检查残差；④ 预测并评估样本外误差。

## 参数选择
p、d、q 用 AIC 网格搜索或 ACF/PACF 目视；季节项 m 按周期设定；是否含常数项由序列均值是否为零决定。

## 工具入口
statsmodels.tsa.arima.model.ARIMA、statsmodels.tsa.statespace.SARIMAX、statsmodels.graphics.tsaplots.plot_acf/plot_pacf、statsmodels.tsa.stattools.adfuller。

## 最小示例
`from statsmodels.tsa.arima.model import ARIMA; fit = ARIMA(y, order=(1,1,1)).fit(); fit.forecast(5)`。

## 评价指标
样本外 RMSE/MAE/MAPE；AIC/BIC；残差白噪声（Ljung-Box p>0.05）；预测区间覆盖率。

## 检验方法
ADF 平稳性检验；残差 ACF 与 Ljung-Box 检验；滚动原点交叉验证；与朴素/平滑基线比较。

## 对比基线
基线为指数平滑与朴素预测；若 ARIMA 样本外误差不优于指数平滑，说明自相关结构弱，可简化。

## 替代模型
季节强时用 SARIMA；非线性用机器学习时序；多变量用 VAR 或回归+ARMA 误差结构。

## 常见误用
差分阶数过度（过差分引入额外噪声）；用样本内拟合优度代替样本外验证；对短序列硬套高阶模型。

## 失效征兆
残差仍显著自相关；预测值发散或出现异常负值；AIC 选出的阶数对数据微扰极不稳定。

## 论文表达示例
"对序列取一阶差分后 ADF 检验 p<0.01 平稳，按 AIC 选定 ARIMA(1,1,1)，样本外 6 期 MAPE 5.2%，残差 Ljung-Box 检验 p=0.28，模型通过检验。"

## 对应练习
对给定序列做 ADF 检验、定阶并预测；用滚动交叉验证比较 ARIMA 与指数平滑误差。
