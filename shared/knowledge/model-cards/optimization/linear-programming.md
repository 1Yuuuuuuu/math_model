---
model_id: linear-programming
category: optimization
title: 线性规划
file: shared/knowledge/model-cards/optimization/linear-programming.md
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

# 线性规划

## 适用问题
目标函数与约束均为线性时的资源分配、生产计划、运输与调度问题，如利润最大化、成本最小化。

## 禁用场景
目标或约束含非线性项（如乘积、平方）时需用非线性规划；变量必须取整数时需整数规划；约束矛盾导致无可行解时先检查建模。

## 输入与假设
输入为决策变量、线性目标系数与线性约束矩阵；假设线性性成立、数据确定（无随机性）。

## 核心公式
min/max cᵀx，s.t. Ax ≤ b，x ≥ 0；最优解在可行域顶点取得（单纯形法/内点法）。

## 直观解释
在约束围成的多边形（多面体）里找一个角点，使目标函数值最优；线性假设使问题可高效精确求解。

## 建模步骤
① 定义决策变量；② 写目标函数；③ 列全部约束；④ 用求解器求解并检验合理性；⑤ 做灵敏度分析。

## 参数选择
求解器选 HiGHS（scipy）/CBC（pulp 默认）；单纯形 vs 内点法；大规模问题注意数值缩放。

## 工具入口
scipy.optimize.linprog（HiGHS）；pulp（LpProblem + LpMinimize）配合 CBC/GLPK；ortools 的 linear_solver。

## 最小示例
`from scipy.optimize import linprog; linprog(c, A_ub=A, b_ub=b, bounds=[(0, None)]*n)`；pulp：`prob += lpSum(c[i]*x[i] for i in range(n)); prob.solve()`。

## 评价指标
最优值；求解状态（optimal/infeasible/unbounded）；对偶价格与影子价格；灵敏度范围。

## 检验方法
小算例手工验算；约束松紧（对偶）检查；灵敏度分析报告系数变化范围；与穷举/枚举在小规模上对比。

## 对比基线
基线为贪心或启发式分配；若启发式与 LP 最优解差距大，说明约束交互强，LP 价值明显。

## 替代模型
整数要求时用整数规划（MILP）；含二次目标用二次规划；多目标用加权或 ε-约束转单目标。

## 常见误用
约束方向写反（≥/≤ 混淆）；漏写非负约束；把非线性目标硬线性化失真；无视不可行解直接看"最优值"。

## 失效征兆
求解返回 infeasible（检查约束矛盾）或 unbounded（漏约束）；最优解含非整数而业务要求整数；灵敏度区间过窄导致结论脆弱。

## 论文表达示例
"建立线性规划模型，以利润最大化为目标并满足产能、原料与需求约束，使用 scipy.optimize.linprog（HiGHS）求解，最优利润为 128 万元，影子价格显示产能约束为瓶颈资源。"

## 对应练习
用 pulp 求解一个 2 变量 LP 并与图解法对比；对运输问题建模并报告最优调运方案。
