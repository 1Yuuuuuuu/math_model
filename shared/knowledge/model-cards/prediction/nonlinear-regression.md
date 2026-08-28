---
model_id: nonlinear-regression
category: prediction
title: 非线性回归
file: shared/knowledge/model-cards/prediction/nonlinear-regression.md
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

# 非线性回归

## 适用问题
因变量与自变量关系明显非线性时拟合曲线，如增长曲线、饱和曲线、指数衰减等业务规律的刻画与预测。

## 禁用场景
数据量不足支撑所选曲线形状；机理不明时盲目套复杂曲线易过拟合；目标为分类时改用分类模型。本执行器不运行自定义公式或回调，也不提供样条、ARIMA、指数平滑等其他预测能力。

## 输入与假设
执行器只接受普通 JSON 对象以及四种固定族：`polynomial`、`exponential`、`power`、`logistic`。`x` 与 `y` 是等长有限数数组；`predict_x` 可选。布尔值、复数、NaN/Inf、超大不可有限转换数、容器/数值子类以及任何未知字段都会被拒绝，输入不会被修改。

| family | 额外字段 | 样本与定义域 |
| --- | --- | --- |
| `polynomial` | `degree`（必填，1–5） | 至少 `degree+1` 个样本和不同 x |
| `exponential` | `initial_parameters`（可选，恰好 3 项） | 至少 3 个不同 x |
| `power` | `initial_parameters`（可选，恰好 3 项） | 至少 3 个不同 x；x 与 predict_x 严格为正 |
| `logistic` | `initial_parameters`（可选，恰好 3 项） | 至少 3 个不同 x |

## 核心公式
多项式为 `sum(coefficient_j*x^j)`；指数为 `a*exp(b*x)+c`；幂为 `a*x**b+c`；Logistic 为 `L/(1+exp(-k*(x-x0)))`。多项式用 `numpy.polyfit`，其余固定族用 `scipy.optimize.curve_fit`。

## 直观解释
选一个符合机理的曲线形状，让曲线尽量贴近数据点；与线性回归不同，参数估计需要迭代逼近。

## 建模步骤
① 画散点图判断曲线形状；② 选择四个固定族之一，并为非多项式曲线按需给出恰好 3 个初值；③ 严格检查长度、样本量和定义域；④ 拟合训练点并计算可选预测点；⑤ 检查有限的 RMSE、MAE、R² 和残差规律，必要时换族。

## 参数选择
多项式必须指定 `degree`。其他族可省略 `initial_parameters` 以使用确定性的启发式初值，也可按参数稳定顺序传入：指数/幂为 `[a,b,c]`，Logistic 为 `[L,k,x0]`。执行器固定 `maxfev=10000`，不开放任意优化器参数。

## 工具入口
调用 `cumcm_toolkit.models.execute("nonlinear-regression", payload)`。能力确定且不接受种子；响应的 `result.parameters` 使用稳定名称，多项式为 `coefficient_0` 至 `coefficient_5` 中实际阶数对应的键，其他族使用公式中的参数名。

## 最小示例
```python
from cumcm_toolkit.models import execute

result = execute(
    "nonlinear-regression",
    {
        "family": "exponential",
        "x": [0, 0.5, 1, 1.5, 2],
        "y": [3, 3.32, 3.70, 4.14, 4.64],
        "initial_parameters": [2, 0.3, 1],
        "predict_x": [2.5, 3],
    },
)
print(result["result"]["parameters"], result["result"]["predicted"])
```

输出固定含 `family`、命名 `parameters`、`fitted`、`predicted`、`rmse`、`mae`、`r_squared`。

## 评价指标
执行器输出有限的 R²、RMSE、MAE。目标恒定时，为避免 0/0，数值上完美的拟合定义 R²=1，否则定义为 0。当前接口不输出参数标准误、置信区间、AIC 或 BIC。

## 检验方法
残差随机性检查；参数显著性检查；留出验证（训练/测试划分）比较样本外误差。

## 对比基线
基线为线性回归；若线性 R² 已很高而曲线拟合提升有限，优先选线性（更可解释）。

## 替代模型
形状不明时用多项式回归、样条回归或机器学习回归；Logistic 增长曲线用于 S 形数据。

## 常见误用
初值不当导致不收敛或陷入局部最优；用拟合优度硬套不合理的函数形式；忽略参数不确定度直接下结论；传入 `custom`、`formula`、回调或族无关字段。长度不等、样本不足、阶数/初值长度错误、幂函数定义域错误、库拟合失败以及参数、拟合、预测或指标溢出，都会被转换为带字段上下文的 `ValueError`，不会泄漏 RuntimeWarning、原始 OverflowError、NaN 或 Inf。

## 失效征兆
拟合不收敛或参数跑到边界；曲线在数据范围外剧烈发散；残差呈系统模式说明函数形式错误。

## 论文表达示例
"依据数据散点呈指数增长特征，采用 y=a·e^(bx)+c 拟合；执行器返回参数 a、b、c 及 R²、RMSE、MAE，据此报告拟合误差和解释度。"

## 对应练习
对指数型数据用 curve_fit 拟合并报告参数与 R²；比较线性化与直接非线性拟合的差异。
