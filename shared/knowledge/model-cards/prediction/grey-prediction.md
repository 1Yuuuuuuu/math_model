---
model_id: grey-prediction-gm11
category: prediction
title: 灰色预测
file: shared/knowledge/model-cards/prediction/grey-prediction.md
status: approved
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

# 灰色预测

## 适用问题
小样本（一般不少于 4 个观测）、数据增长近似指数规律时的短期预测，如少数据年份的产量、需求预测。

## 禁用场景
数据量大且信息完整时用统计/机器学习更准；数据波动剧烈或非单调时 GM(1,1) 精度差；长期外推误差迅速放大。

## 输入与假设
执行器接收一个普通 JSON 对象。`series` 是至少 4 个严格正的有限数构成的等间隔一维数组；`forecast_steps` 是 1–10000 的整数。布尔值、复数、NaN/Inf、不能有限转换的超大数、容器或数值子类以及未声明字段均会被拒绝。调用过程中输入对象不会被修改。

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `series` | number[] | 是 | 长度至少 4；每项严格大于 0 且有限 |
| `forecast_steps` | integer | 是 | 1–10000；布尔值不视为整数 |

## 核心公式
GM(1,1)：对累加序列 x⁽¹⁾ 建模 dx⁽¹⁾/dt + a·x⁽¹⁾ = b，参数 (a,b) 用最小二乘估计，还原预测 x̂⁽⁰⁾(k+1)。

## 直观解释
先把"乱"的原始数据累加变得"有规律"（近似指数），用一条指数曲线拟合，再差分还原出原尺度的预测。

## 建模步骤
① 严格校验输入；② 对原序列执行一次累加生成（AGO）；③ 用相邻累加值的均值构造背景序列；④ 最小二乘估计 `a`、`b`；⑤ 计算时间响应并差分还原拟合值和未来值；⑥ 输出残差、相对误差、级比和后验精度诊断。`a` 接近 0 时使用线性极限式，避免除零和消去误差。

## 参数选择
唯一执行参数是 `forecast_steps`。级比可容区间为 `(exp(-2/(n+1)), exp(2/(n+1)))`；不满足时仍返回结果，但 `level_ratio_applicable=false` 并给出警告。建模长度通常取最近 4–6 个点，外推尽量控制在 1–3 步。

## 工具入口
调用 `cumcm_toolkit.models.execute("grey-prediction-gm11", payload)`。能力是确定性的，不接受种子，响应中 `reproducibility` 固定为 `{"seed": null, "deterministic": true}`。

## 最小示例
```python
from cumcm_toolkit.models import execute

result = execute(
    "grey-prediction-gm11",
    {"series": [2.874, 3.278, 3.795, 4.435, 5.199], "forecast_steps": 2},
)
print(result["result"]["forecast"])
```

`result` 同时含 `fitted`、`forecast`、`residuals`、`relative_errors`；`diagnostics` 含估计的 `a`、`b`、级比与可容区间。原序列方差为正时还含 `posterior_ratio_c` 和 `small_error_probability_p`。

## 评价指标
逐点绝对相对误差；后验差比 C 与小误差概率 P（常按 C<0.35、P>0.95 判优）。若原序列方差为 0，C/P 在数学上未定义，执行器会省略这两个数值并通过 `posterior_accuracy_reason` 说明原因，绝不输出 NaN/Inf。

## 检验方法
级比检验；残差检验（还原值与原始值相对误差）；后验差检验；样本外 1-2 步验证。

## 对比基线
基线为指数平滑或线性外推；小样本下若 GM(1,1) 相对误差不低于简单外推，考虑放弃。

## 替代模型
数据充分时可用 ARIMA/指数平滑；非线性更复杂时可调用固定族 `nonlinear-regression` 的 Logistic 曲线；GM(1,N) 适合多变量灰色系统，但不属于本执行器范围。

## 常见误用
对波动大的序列硬套；外推步数过多；不检查 `level_ratio_applicable` 就声称“适用”；传入零值、负值或不等间隔数据。少于 4 点、非正/非有限数据、非法步数、未知字段以及累加、拟合或预测产生非有限值时，公开入口均抛出带模型与字段上下文的 `ValueError`。

## 失效征兆
级比超出可容区间；预测出现负值或发散；后验差比 C>0.65 判为不合格。

## 论文表达示例
"数据级比检验全部落入可容区间，建立 GM(1,1) 模型，后验差比 C=0.21、小误差概率 P=1，平均相对误差 2.3%，预测未来 3 期需求，精度等级为优。"

## 对应练习
对 5 个点的序列建立 GM(1,1) 并做级比与后验差检验；预测 2 步并与真实值对比。
