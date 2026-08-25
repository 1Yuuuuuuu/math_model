# CUMCM 大规模模型执行器扩展设计

**日期：** 2026-08-25

**状态：** 已获用户逐节确认，等待规格复核后进入实施计划

## 目标

将现有仅适合监督学习的 `run_model(name, X, y)` 扩展为多执行器模型系统。本阶段必须新增 23 项真实可执行能力，并让现有线性回归、决策树和 KMeans 也能通过新入口执行。系统不得通过硬编码白名单声称尚未实现的模型可运行。

本阶段最终至少登记 26 项真实能力：23 项新增能力加 3 项现有能力。每项能力必须有实际执行代码、输入边界、JSON 可序列化结果、知识卡关联和自动化测试。

## 范围

### 新增的 23 项能力

| 执行器 | `model_id` | 中文能力 | 对应知识卡 |
| --- | --- | --- | --- |
| `evaluation` | `topsis` | TOPSIS | `shared/knowledge/model-cards/evaluation/topsis.md` |
| `evaluation` | `entropy-weight` | 熵权法 | `shared/knowledge/model-cards/evaluation/entropy-weight.md` |
| `evaluation` | `ahp` | 层次分析法 | `shared/knowledge/model-cards/evaluation/ahp.md` |
| `evaluation` | `grey-relational-analysis` | 灰色关联分析 | `shared/knowledge/model-cards/evaluation/grey-relational.md` |
| `optimization` | `linear-programming` | 线性规划 | `shared/knowledge/model-cards/optimization/linear-programming.md` |
| `optimization` | `integer-programming` | 整数规划 | `shared/knowledge/model-cards/optimization/integer-programming.md` |
| `optimization` | `nonlinear-programming` | 非线性规划 | `shared/knowledge/model-cards/optimization/nonlinear-programming.md` |
| `forecasting` | `grey-prediction-gm11` | GM(1,1) 灰色预测 | `shared/knowledge/model-cards/prediction/grey-prediction.md` |
| `forecasting` | `arima` | ARIMA | `shared/knowledge/model-cards/prediction/arima.md` |
| `forecasting` | `exponential-smoothing` | 指数平滑 | `shared/knowledge/model-cards/prediction/exponential-smoothing.md` |
| `forecasting` | `nonlinear-regression` | 非线性回归 | `shared/knowledge/model-cards/prediction/nonlinear-regression.md` |
| `data-processing` | `normalization` | 标准化 | `shared/knowledge/model-cards/data/normalization.md` |
| `data-processing` | `interpolation` | 插值 | `shared/knowledge/model-cards/data/interpolation.md` |
| `data-processing` | `anomaly-detection` | 异常检测 | `shared/knowledge/model-cards/data/anomaly-detection.md` |
| `data-processing` | `pca` | 主成分分析 | `shared/knowledge/model-cards/evaluation/pca.md` |
| `statistics` | `correlation-analysis` | 相关分析 | `shared/knowledge/model-cards/statistics/correlation-analysis.md` |
| `statistics` | `confidence-interval` | 置信区间 | `shared/knowledge/model-cards/statistics/confidence-interval.md` |
| `statistics` | `parametric-test` | 参数检验 | `shared/knowledge/model-cards/statistics/parametric-tests.md` |
| `statistics` | `nonparametric-test` | 非参数检验与卡方检验 | `shared/knowledge/model-cards/statistics/nonparametric-tests.md` |
| `statistics` | `anova` | 单因素方差分析 | `shared/knowledge/model-cards/statistics/anova.md` |
| `supervised` | `logistic-regression` | 逻辑回归 | `shared/knowledge/model-cards/classification/logistic-regression.md` |
| `clustering` | `dbscan` | DBSCAN | `shared/knowledge/model-cards/classification/dbscan.md` |
| `clustering` | `hierarchical-clustering` | 层次聚类 | `shared/knowledge/model-cards/classification/hierarchical-clustering.md` |

### 迁入新入口的现有能力

`linear-regression` 和 `decision-tree` 由 `supervised` 执行器包装；`kmeans` 由 `clustering` 执行器包装。旧 `run_model` 的返回结构和构造行为保持兼容，新入口不返回 Python estimator。

### 不在本阶段范围

- 不实现动态规划、启发式算法、多目标优化、模糊综合评价、因子分析或机器学习回归知识卡。
- 不执行用户提供的 Python 代码、回调或字符串公式。非线性规划只解释本规格定义的受限声明式表达式树；非线性回归只使用固定函数族。
- 不修改 `adapters/dsh/` 的 Phase 7 生产实现；只提供 Phase 7 完成后可消费的稳定契约和 Python API。
- 不将统计显著性自动解释为实际意义显著，也不自动生成论文结论。

## 架构

```text
cumcm_toolkit.models
├── execution.py             # execute(model_id, payload) 统一入口
├── specifications.py        # ModelSpec、模型注册表和能力查询
├── result.py                # 结果外壳、有限值检查与 JSON 规范化
├── runner.py                # 保留 run_model 兼容入口
├── registry.py              # 保留旧 estimator factory 注册表
└── executors/
    ├── __init__.py
    ├── base.py
    ├── evaluation.py
    ├── optimization.py
    ├── forecasting.py
    ├── data_processing.py
    ├── statistics.py
    ├── supervised.py
    └── clustering.py
```

`ModelSpec` 是能力事实来源。每条记录至少包含：

- `model_id`
- `executor`
- `knowledge_card`
- `deterministic`
- `seed_supported`
- `payload_fields`
- 执行函数

注册时拒绝重复 ID、不存在的知识卡、未知执行器和不一致的随机种子声明。`list_capabilities()` 返回按 `model_id` 排序的只读描述，不暴露内部函数对象。

## 公共接口

### 新入口

```python
def execute(model_id: str, payload: Mapping[str, object]) -> dict[str, object]:
    ...
```

入口执行以下固定流程：

1. 校验 `model_id` 和 payload 是合法映射。
2. 从 `ModelSpec` 注册表解析执行器。
3. 由对应执行器校验模型专属输入。
4. 执行模型并生成标准结果。
5. 递归拒绝 `NaN`、正负无穷、非字符串字典键和不可 JSON 表示的对象。
6. 通过 `model-execution` Schema 验证后返回深拷贝结果。

未知模型、输入错误、算法不适用、求解失败和结果不可序列化均抛出 `ValueError`，错误信息包含 `model_id` 和失败阶段。失败不返回部分成功外壳。

### 旧入口

```python
def run_model(
    name: str,
    X: object,
    y: object,
    *,
    seed: int | None = None,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    ...
```

旧入口继续返回 `fitted` estimator。现有三个模型的参数、随机种子冲突检查和异常语义保持不变。

## 结果契约

新增 `shared/contracts/model-execution.schema.json`，在目录中登记为第 16 项契约，并提供至少一个有效 fixture 和以下无效 fixtures：非有限数值、缺少结果、未知状态或执行器、失败状态携带伪造结果。

成功结果结构：

```json
{
  "schema_version": "1.0",
  "status": "succeeded",
  "model_id": "topsis",
  "executor": "evaluation",
  "parameters": {},
  "input_summary": {
    "rows": 4,
    "columns": 3
  },
  "result": {},
  "diagnostics": {},
  "warnings": [],
  "reproducibility": {
    "seed": null,
    "deterministic": true
  }
}
```

`status` 在公共 `execute` 成功返回时固定为 `succeeded`。算法失败通过异常表达，不生成 `failed` 结果；契约仍可为未来持久化失败记录预留独立的条件分支，但本阶段不消费它。

数组统一转成 JSON 数组，NumPy/Pandas 标量转成 Python `int`、`float` 或 `bool`。结果数值不得使用字符串代替；缺失的统计量使用省略字段或带原因的诊断，不使用 `NaN`。

## 七类执行器

### 综合评价执行器

`topsis` 输入 `matrix`、`criteria` 和可选 `weights`。`criteria` 每项为 `benefit` 或 `cost`。输出向量归一化矩阵、正负理想解、到理想解距离、贴近度和稳定排序。拒绝权重和不为 1、负权重、常量或零范数指标列。

`entropy-weight` 输入 `matrix` 和 `criteria`。先按指标方向进行非负归一化，再输出熵值、差异系数和权重。零信息列权重为 0 并产生警告；全部指标均无信息时失败。

`ahp` 输入正互反 `pairwise_matrix`。输出最大特征值、归一化权重、CI 和 CR。规模 1–2 时 CR 为 `null` 并写明无需一致性检验；规模 3–15 使用固定 RI 表；规模大于 15 拒绝。CR 大于 0.1 不伪造通过结论，结果成功但诊断标记 `consistent: false`。

`grey-relational-analysis` 输入 `reference`、`comparatives`、可选 `rho` 和归一化方法。要求所有序列等长且 `0 < rho <= 1`。输出逐点关联系数、关联度和稳定排序。

### 优化执行器

`linear-programming` 使用 SciPy `linprog`。输入目标系数、`minimize|maximize`、变量上下界、等式和不等式约束。输出解、目标值、约束余量和求解器状态；不可行、无界或数值失败均抛错。

`integer-programming` 使用 SciPy `milp`。输入与线性规划一致，并增加 `integrality` 数组，值限定为 SciPy 支持的 0–3。输出整数/半整数约束下的解、目标值、界和状态；不得在结果阶段通过四舍五入伪造整数解。

`nonlinear-programming` 使用 SciPy `minimize`。为保持纯 JSON 和安全性，目标与约束采用声明式表达式树，不接受字符串表达式或回调。允许的节点仅为 `constant`、`variable`、`add`、`subtract`、`multiply`、`divide`、整数次 `power`、`negate`、`abs`、`exp`、`log`、`sqrt`；树深、节点数和幂指数设硬上限。约束仅允许等式和区间不等式。输出解、目标值、迭代次数和收敛信息；域错误或未收敛失败关闭。

### 预测执行器

`grey-prediction-gm11` 输入正数 `series` 和 `forecast_steps`。至少 4 个样本。输出发展系数、灰作用量、拟合、预测、残差、相对误差、后验差比 C 和小误差概率 P。级比检验不满足时写入适用性警告。

`arima` 输入 `series`、三元非负整数 `order` 和 `forecast_steps`，使用 statsmodels ARIMA。输出拟合值、预测值、置信区间、AIC、BIC 和残差摘要。样本不足、参数不可识别或拟合失败均抛错；非平稳风险进入诊断，不自动改阶。

`exponential-smoothing` 输入 `series`、`forecast_steps`、趋势类型、季节类型和可选季节周期，使用 statsmodels ExponentialSmoothing。季节模型要求至少两个完整周期。输出拟合、预测、SSE 和已拟合平滑参数。

`nonlinear-regression` 只接受 `family` 为 `polynomial`、`exponential`、`power` 或 `logistic`。输入 `x`、`y`、可选初值和预测点。禁止字符串公式与回调。输出参数、拟合值、预测值、RMSE、MAE 和 R²；函数域不合法或 curve fitting 未收敛时失败。

### 数据处理执行器

`normalization` 支持 `minmax`、`zscore` 和 `robust`。输入二维矩阵和可选列选择，输出变换结果以及中心、尺度或极值参数。常量列输出 0 并产生警告；缺失值只有在明确 `missing_policy` 时处理。

`interpolation` 支持 `linear`、`nearest`、`cubic` 和 `pchip`。输入严格递增且无重复的 `x`、对应 `y`、`new_x` 和明确的 `extrapolation` 策略。默认拒绝范围外点；允许时必须在结果中标记外推位置。

`anomaly-detection` 支持 `iqr`、`zscore` 和 `isolation-forest`。输出异常掩码、异常索引、得分或阈值、异常数量。Isolation Forest 必须使用显式或默认固定 seed；单变量规则和多变量模型不得共享含糊参数。

`pca` 输入二维数值矩阵、组件数和是否标准化。使用 scikit-learn PCA，输出降维数据、方差、方差贡献率、累计贡献率、载荷和输入中心。组件数不得超过 `min(n_samples, n_features)`。

### 统计执行器

`correlation-analysis` 支持 `pearson`、`spearman` 和 `kendall`。输入一对序列或二维矩阵。输出系数矩阵、p 值矩阵、有效样本数和成对缺失摘要。常量输入不产生 `NaN` 成功结果，而是失败或按成对字段记录不可计算原因。

`confidence-interval` 支持均值 t 区间和比例 Wilson 区间。输入样本或成功次数/总数、置信水平。输出估计值、上下界、置信水平、样本量和方法。

`parametric-test` 支持 `one-sample-t`、`independent-t` 和 `paired-t`。输出统计量、p 值、自由度、样本量、均值差和效应量。独立样本 t 检验允许显式选择 Welch 或等方差版本。

`nonparametric-test` 支持 `mann-whitney-u`、`wilcoxon`、`kruskal-wallis` 和 `chi-square`。卡方输入列联表并输出期望频数与小期望频数警告；其他方法输出统计量、p 值、秩或效应量摘要。

`anova` 实现单因素 ANOVA。输入至少两组样本，输出 F、p 值、组间/组内自由度、平方和、均方和 eta-squared。任一组为空、全部数据无方差或自由度不足时失败。

### 监督学习与聚类执行器

`supervised` 包含 `linear-regression`、`decision-tree` 和 `logistic-regression`。payload 使用 `X`、`y`、可选 `predict_X`、`params` 和 `seed`。新入口输出模型参数、预测和适用的训练指标，不返回 estimator；旧入口仍返回 estimator。

`clustering` 包含 `kmeans`、`dbscan` 和 `hierarchical-clustering`。输入 `X` 和算法参数，输出标签、簇数、噪声数及适用诊断。层次聚类额外输出 linkage matrix；簇数和距离阈值互斥。DBSCAN 与层次聚类结果必须提醒尺度敏感性，除非输入声明已经标准化。

## 数据安全与数值边界

- 公共数组转换器拒绝空输入、ragged 数组、布尔伪数值、复数和所有非有限值。
- 不静默丢弃缺失值。允许缺失处理的执行器必须要求显式策略，并在 `input_summary` 记录处理数量。
- 随机算法统一通过 `seed` 进入；禁止 payload 同时提供 `seed` 和底层 `random_state`。
- 排名相同使用原始索引作为稳定次序，保证跨运行确定性。
- p 值、置信区间和效应量只描述计算结果，不生成领域结论。
- 预测结果明确区分 fitted 与 forecast；样本内拟合不得标为泛化验证。
- 所有警告是去重、排序后的字符串列表，不能携带异常对象或不可序列化结构。

## 路由与事实来源

`adapters/codex/routing.py::solver_execution_mode()` 改为查询模型能力注册表。只有成功注册且具有执行函数的模型返回 `execute`；未知、知识卡存在但未准入或显式计划能力返回 `plan-only`。

能力测试必须证明：

- 注册表中的每项能力可被 `execute` 调用。
- Codex 路由不会把未注册模型标为 execute。
- 当前 `entropy-weight`、`topsis` 和 `linear-programming` 的硬编码能力声明由真实实现替换。

## 测试策略

### 单元测试

每个模型至少包含：

1. 一个可手工核验或与公开数学定义一致的已知答案测试。
2. 一个输入边界失败测试。
3. 一个非有限值或维度错误测试。
4. 一个 JSON 往返测试。
5. 随机模型的同 seed 确定性测试。

测试直接调用真实实现，不用 mock 替代数值库。

### 注册与契约测试

- 精确断言 23 项新增模型全部存在，且总真实能力不少于 26。
- 所有注册知识卡路径必须存在，不能出现孤立能力。
- `model-execution` 正负 fixtures 通过离线验证器。
- 结果递归检查拒绝 NumPy `NaN`、无穷和 estimator。
- `run_model` 现有测试保持通过。

### 集成与 E2E

建立六类场景：

1. 熵权法生成权重后输入 TOPSIS。
2. 线性规划和整数规划在同一约束问题上的可行解对照。
3. 时间序列预测返回拟合、预测和区间。
4. 标准化、异常检测和 PCA 顺序处理。
5. 统计检验与 ANOVA 输出完整统计摘要。
6. 逻辑回归、DBSCAN 和层次聚类返回可序列化结果。

全仓验收还必须运行契约验证器、Skill 打包检查和完整 pytest。

## 文档

- 更新模型库说明，区分知识卡、真实执行能力和计划能力。
- 为 23 项新增能力提供最小 payload 示例、输出字段、适用条件和失败示例。
- 更新现有模型库 PDF 的源文档；PDF 重新生成可作为后续独立交付，不纳入源码提交。
- 更新 Codex solver Skill 的资源清单，使打包后包含执行器、注册表、契约和知识卡。

## Phase 7 并行与合流规则

开发固定在 `codex/model-executor-expansion` 独立工作树。实现期间：

- 不修改 `adapters/dsh/` Phase 7 生产代码。
- 不合并到 `main`，直到 Phase 7 完成并通过复审。
- Phase 7 完成后先将其最终主线合入或变基到本分支，再解决 `shared/contracts/catalog.json`、Skill 资源和文档计数冲突。
- DSH 只接入稳定的 `execute(model_id, payload)` 与 `model-execution` 契约，不复制七套算法实现。

## 实施顺序

1. 结果契约、公共验证器、`ModelSpec` 注册表与统一路由。
2. 综合评价和优化执行器，替换已有虚假可执行声明。
3. 数据处理和统计执行器。
4. 预测执行器。
5. 监督学习和聚类执行器，并接入现有三个模型。
6. Codex 路由、solver Skill 资源、E2E 和使用文档。
7. 全仓验证、独立审查和 Phase 7 后合流。

每一步均按测试驱动执行：先写会因能力缺失而失败的行为测试，确认 RED，再实现最小代码到 GREEN，最后重构并运行相关回归。

## 验收条件

- 23 项新增能力全部通过 `execute()` 真实运行。
- 新注册表至少含 26 项有执行函数的能力。
- 新接口不返回 estimator 或其他不可 JSON 表示对象。
- 旧 `run_model` 行为兼容。
- 所有注册项拥有存在的知识卡和明确执行器。
- Codex 能力路由与注册表一致，无硬编码漂移。
- 优化失败、统计不可计算、预测不适用和数值非有限全部失败关闭。
- 新契约正负 fixtures、六类 E2E、Skill 打包和全仓测试通过。
- Phase 7 DSH 生产文件未被本分支修改。
