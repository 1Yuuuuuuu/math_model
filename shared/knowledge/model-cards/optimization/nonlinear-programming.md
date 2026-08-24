---
model_id: nonlinear-programming
category: optimization
title: 非线性规划
file: shared/knowledge/model-cards/optimization/nonlinear-programming.md
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

# 非线性规划

## 适用问题
目标或约束含非线性项（平方、乘积、指数等）的优化，如投资组合（风险-收益）、化学配比、几何设计。

## 禁用场景
问题本质线性时别用非线性（求解慢且只保证局部最优）；函数非光滑或含离散决策时需专门方法；初值影响大时需多起点。

## 输入与假设
输入为非线性目标与约束、变量界；假设函数可微（对梯度类方法）或至少可评估，问题可能非凸。

## 核心公式
min f(x)，s.t. gᵢ(x) ≤ 0，hⱼ(x) = 0；KKT 条件刻画一阶最优性；迭代法（SQP、内点、L-BFGS）。

## 直观解释
从某个初值出发沿下降方向逐步逼近最优；非凸问题像"走山路"，可能停在山谷（局部最优）而非最低点。

## 建模步骤
① 写清目标与约束；② 估计变量范围与初值；③ 选算法（SLSQP/trust-constr）；④ 多起点求解；⑤ 验证 KKT/约束满足。

## 参数选择
scipy 的 method（SLSQP/trust-constr）；初值与 bounds；容差（ftol/xtol）；是否提供解析梯度/雅可比。

## 工具入口
scipy.optimize.minimize（method="SLSQP"/"trust-constr"）、scipy.optimize.differential_evolution（全局）、pymoo（多目标）。

## 最小示例
`from scipy.optimize import minimize; minimize(fun, x0, method="SLSQP", bounds=bnds, constraints=cons)`。

## 评价指标
最优值；约束违反量；KKT 残差；多起点结果一致性；求解耗时。

## 检验方法
多初值重解看是否收敛同一解；数值梯度验证；小规模与解析解对比；约束可行性终检。

## 对比基线
基线为线性化近似或网格搜索；若非线性求解收益不明显，考虑简化模型。

## 替代模型
凸问题用 cvxpy 精确求解；目标可分离用分解法；全局优化用 differential_evolution 或启发式算法。

## 常见误用
只跑一个初值就宣称最优；忽略约束违反（成功标志不代表约束满足）；非凸问题未做全局性验证。

## 失效征兆
不同初值结果差异大（多峰）；约束违反量不降；迭代不收敛或目标发散。

## 论文表达示例
"构建非线性规划模型，采用 SLSQP 从 20 个随机初值求解均收敛于同一最优解，约束最大违反量 10⁻⁹，最优风险-收益组合确定，敏感性分析表明结果对参数扰动稳健。"

## 对应练习
求解一个带非线性约束的问题并做多起点验证；比较 SLSQP 与 trust-constr 的结果。
