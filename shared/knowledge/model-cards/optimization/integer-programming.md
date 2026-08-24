---
model_id: integer-programming
category: optimization
title: 整数规划
file: shared/knowledge/model-cards/optimization/integer-programming.md
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

# 整数规划

## 适用问题
决策变量必须为整数（0-1 或正整数）时的选址、排班、装载、投资组合选择等组合优化问题。

## 禁用场景
变量可连续时用 LP 更高效；问题规模极大（数十万变量）时精确求解困难，需启发式；数据不确定时先考虑鲁棒建模。

## 输入与假设
输入为线性目标/约束加整数约束；假设整数性严格必要（不是近似），数据确定。

## 核心公式
min cᵀx，s.t. Ax ≤ b，x ∈ ℤⁿ（或子集为 {0,1}ⁿ）；用分支定界/割平面求解。

## 直观解释
和线性规划一样，但解被限定在整数格点上；整数约束让问题变难（NP 难），求解靠分支定界剪枝。

## 建模步骤
① 明确哪些变量必须整数/0-1；② 写 LP 部分；③ 加整数约束与逻辑约束（如互斥用 x₁+x₂≤1）；④ 求解并验证整数性。

## 参数选择
求解器 CBC/GLPK/SCIP；MIP 的 gap 容差（如 0.01）；时间限制；分支策略。

## 工具入口
pulp（CBC 默认）、ortools CP-SAT、scipy.optimize.milp（HiGHS）、mip 库（CBC）。

## 最小示例
`from scipy.optimize import milp; milp(c, integrality=np.ones(n), bounds=..., constraints=...)`；pulp 中 `x = LpVariable.dicts("x", range(n), cat="Binary")`。

## 评价指标
最优值或 gap；求解时间；松弛 LP 解与整数解的差距；约束有效性。

## 检验方法
小规模穷举验证；LP 松弛下界合理性检查；gap 报告；对参数扰动重解看稳定性。

## 对比基线
基线为 LP 松弛解四舍五入；若舍入解不可行或与最优差距大，说明整数性至关重要。

## 替代模型
规模大求近似用启发式（遗传/模拟退火）；分配问题用匈牙利算法（scipy.optimize.linear_sum_assignment）；非线性整数用 MINLP 或启发式。

## 常见误用
把 LP 解直接取整当答案；0-1 逻辑约束写错（如"至少一个"写成"恰好一个"）；大模型无时间限制导致空跑。

## 失效征兆
求解长时间不收敛或 gap 无法下降；整数解与 LP 解差异巨大；无可行解但业务上应有解（检查约束）。

## 论文表达示例
"建立 0-1 整数规划选址模型，用 CBC 求解器在 3 秒内得到 gap<1% 的可行最优解，总成本 86 万元，选中的 5 个备选点覆盖全部需求点。"

## 对应练习
用 pulp 建模一个 0-1 背包问题并与动态规划对比；建模"互斥二选一"约束并验证。
