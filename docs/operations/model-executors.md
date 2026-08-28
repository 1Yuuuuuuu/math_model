# 模型执行器运行手册

真正的执行边界是 `model_id + JSON payload → execute → model-execution JSON`。先用 `cumcm_toolkit.models.specifications.list_capabilities()` 读取当前注册表，再调用 `cumcm_toolkit.models.execution.execute(model_id, payload)`；未知模型、输入错误、算法不适用、求解失败或非有限结果均抛出带 `model_id` 和失败阶段的 `ValueError`，不得把局部结果当作成功。

```python
from cumcm_toolkit.models.execution import execute
from cumcm_toolkit.models.specifications import list_capabilities

available = {item["model_id"] for item in list_capabilities()}
if "topsis" not in available:
    raise RuntimeError("topsis is plan-only in this runtime")
result = execute(
    "topsis",
    {"matrix": [[4, 1], [1, 4]], "criteria": ["benefit", "cost"]},
)
```

成功外壳固定含 `schema_version`、`status: "succeeded"`、`model_id`、`executor`、`parameters`、`input_summary`、`result`、`diagnostics`、`warnings` 和 `reproducibility`。下面“核心输出”均指 `result` 内的字段；失败 payload 是可直接复现的失败关闭示例。

## 综合评价

### `topsis`

适用于同时含效益型和成本型指标的有限数值矩阵；常量列、零范数列或非法权重失败关闭。

最小合法 payload：
```json
{"matrix": [[4, 1], [1, 4]], "criteria": ["benefit", "cost"]}
```

核心输出：`closeness`、`ranking`

失败 payload：
```json
{"matrix": [[1, 2], [3, 4]], "criteria": ["benefit"]}
```

### `entropy-weight`

适用于由样本离散程度确定指标权重；全部指标都无信息时失败，不伪造均匀权重。

最小合法 payload：
```json
{"matrix": [[1, 8], [2, 4], [4, 1]], "criteria": ["benefit", "cost"]}
```

核心输出：`weights`、`scores`、`ranking`

失败 payload：
```json
{"matrix": [[1, 1], [1, 1]], "criteria": ["benefit", "benefit"]}
```

### `ahp`

适用于 1–15 阶正互反判断矩阵；`CR > 0.1` 仍返回计算结果，但 `diagnostics.consistent` 为 false。

最小合法 payload：
```json
{"pairwise_matrix": [[1, 2], [0.5, 1]]}
```

核心输出：`lambda_max`、`weights`、`CI`、`CR`

失败 payload：
```json
{"pairwise_matrix": [[1, 2], [2, 1]]}
```

### `grey-relational-analysis`

适用于等长参考序列与比较序列；序列长度不一致或 `rho` 不在 `(0, 1]` 时失败。

最小合法 payload：
```json
{"reference": [1, 2, 3], "comparatives": [[1, 2, 3], [3, 2, 1]]}
```

核心输出：`coefficients`、`grades`、`ranking`

失败 payload：
```json
{"reference": [1, 2, 3], "comparatives": [[1, 2]]}
```

## 优化

### `linear-programming`

适用于线性目标、线性约束和显式变量边界；不可行、无界或数值失败通过异常表达。

最小合法 payload：
```json
{"objective": [1], "sense": "minimize", "bounds": [[0, 1]]}
```

核心输出：`solution`、`objective`

失败 payload：
```json
{"objective": [1], "sense": "minimize", "bounds": [[1, 0]]}
```

### `integer-programming`

适用于 SciPy `milp` 支持的 0–3 型整数约束；不会通过四舍五入伪造整数解。

最小合法 payload：
```json
{"objective": [1], "sense": "maximize", "bounds": [[0, 2]], "integrality": [1]}
```

核心输出：`solution`、`objective`

失败 payload：
```json
{"objective": [1], "sense": "maximize", "bounds": [[0, 2]], "integrality": [4]}
```

### `nonlinear-programming`

适用于受限声明式表达式树；字符串公式、回调、超限表达式或未收敛求解均失败关闭。

最小合法 payload：
```json
{"objective": {"op": "power", "args": [{"op": "subtract", "args": [{"op": "variable", "index": 0}, {"op": "constant", "value": 3}]}, {"op": "constant", "value": 2}]}, "initial": [0], "bounds": [[-10, 10]], "sense": "minimize", "constraints": []}
```

核心输出：`solution`、`objective`

失败 payload：
```json
{"objective": "(x-3)^2", "initial": [0], "bounds": [[-10, 10]], "sense": "minimize", "constraints": []}
```

## 预测

### `grey-prediction-gm11`

适用于至少 4 个正数样本的 GM(1,1)；级比检验不满足会产生适用性警告。

最小合法 payload：
```json
{"series": [2.874, 3.278, 3.795, 4.435, 5.199], "forecast_steps": 1}
```

核心输出：`fitted`、`forecast`、`residuals`、`relative_errors`

失败 payload：
```json
{"series": [1, 2, -3, 4], "forecast_steps": 1}
```

### `arima`

适用于样本量足以识别给定非负整数阶数的序列；执行器不会自动改阶。

最小合法 payload：
```json
{"series": [10.0, 10.66829419696158, 11.181859485365136, 11.528224001611973, 11.848639500938415, 12.308215145067372, 12.944116900360214, 13.631397319743758, 14.197871649324677, 14.582423697048], "order": [1, 1, 0], "forecast_steps": 1}
```

核心输出：`fitted`、`forecast`、`confidence_interval`、`fitted_parameters`

失败 payload：
```json
{"series": [1, 2], "order": [1, 1, 0], "forecast_steps": 1}
```

### `exponential-smoothing`

适用于加性或乘性趋势/季节结构；季节模型至少需要两个完整周期。

最小合法 payload：
```json
{"series": [10.0, 10.3, 10.6, 10.9, 11.2, 11.5, 11.8, 12.1], "forecast_steps": 1, "trend": "add", "seasonal": null, "damped_trend": false}
```

核心输出：`fitted`、`forecast`、`fitted_parameters`

失败 payload：
```json
{"series": [10.0], "forecast_steps": 1, "trend": "add", "seasonal": null}
```

### `nonlinear-regression`

只接受 `polynomial`、`exponential`、`power` 或 `logistic` 固定函数族，不接受任意公式。

最小合法 payload：
```json
{"family": "polynomial", "x": [-2.0, -1.0, 0.0, 1.0, 2.0], "y": [9.0, 2.0, 1.0, 6.0, 17.0], "degree": 2, "predict_x": [3.0]}
```

核心输出：`family`、`parameters`、`fitted`、`predicted`、`rmse`、`mae`、`r_squared`

失败 payload：
```json
{"family": "custom", "x": [0, 1, 2], "y": [0, 1, 4]}
```

## 数据处理

### `normalization`

支持 `minmax`、`zscore` 和 `robust`；常量列输出 0 并产生警告，缺失处理必须显式声明。

最小合法 payload：
```json
{"matrix": [[1, 2], [3, 4]], "method": "minmax"}
```

核心输出：`transformed`、`min`、`range`

失败 payload：
```json
{"matrix": [], "method": "minmax"}
```

### `interpolation`

要求 `x` 严格递增且无重复；默认拒绝范围外插值点。

最小合法 payload：
```json
{"x": [0, 1], "y": [0, 2], "new_x": [0.5]}
```

核心输出：`values`、`extrapolated`

失败 payload：
```json
{"x": [0, 1], "y": [0, 2], "new_x": [-1]}
```

### `anomaly-detection`

支持 `iqr`、`zscore` 和 `isolation-forest`；随机算法使用显式或固定 seed。

最小合法 payload：
```json
{"matrix": [[1], [1], [1], [10]], "method": "iqr"}
```

核心输出：`mask`、`anomaly_indices`、`count`

失败 payload：
```json
{"matrix": [[1], [2], [3]], "method": "unknown"}
```

### `pca`

组件数不得超过 `min(n_samples, n_features)`；输出载荷为组件优先方向。

最小合法 payload：
```json
{"matrix": [[1, 2], [2, 3], [3, 4]], "components": 1, "standardize": false}
```

核心输出：`transformed`、`components`、`loadings`、`explained_variance_ratio`

失败 payload：
```json
{"matrix": [[1, 2], [2, 3]], "components": 3, "standardize": false}
```

## 统计

### `correlation-analysis`

支持 `pearson`、`spearman` 和 `kendall`；常量输入不返回带 `NaN` 的伪成功。

最小合法 payload：
```json
{"x": [1, 2, 3], "y": [2, 4, 6], "method": "pearson"}
```

核心输出：`coefficient`、`p_value`、`sample_size`

失败 payload：
```json
{"x": [1, 1, 1], "y": [1, 2, 3], "method": "pearson"}
```

### `confidence-interval`

支持均值 t 区间和比例 Wilson 区间；置信水平必须严格位于 0 与 1 之间。

最小合法 payload：
```json
{"method": "mean-t", "sample": [2, 3, 5, 8], "confidence": 0.95}
```

核心输出：`estimate`、`lower`、`upper`、`confidence`、`sample_size`、`method`

失败 payload：
```json
{"method": "mean-t", "sample": [2, 3, 5, 8], "confidence": 1.0}
```

### `parametric-test`

支持单样本、独立样本和配对 t 检验；只报告统计量，不自动生成领域结论。

最小合法 payload：
```json
{"test": "one-sample-t", "sample": [2, 3, 5, 8], "population_mean": 1}
```

核心输出：`statistic`、`p_value`、`degrees_freedom`、`mean_difference`、`effect_size`

失败 payload：
```json
{"test": "one-sample-t", "sample": [2], "population_mean": 1}
```

### `nonparametric-test`

支持 Mann–Whitney U、Wilcoxon、Kruskal–Wallis 和卡方检验；空样本或不可计算输入失败。

最小合法 payload：
```json
{"test": "mann-whitney-u", "sample_a": [1, 2, 3], "sample_b": [4, 6, 8]}
```

核心输出：`statistic`、`p_value`、`effect_size`

失败 payload：
```json
{"test": "mann-whitney-u", "sample_a": [], "sample_b": [4, 6, 8]}
```

### `anova`

实现单因素总体 ANOVA；显著结果不识别具体差异组，事后比较需另行设计。

最小合法 payload：
```json
{"groups": [[1, 2, 3], [4, 5, 6]]}
```

核心输出：`statistic`、`p_value`、`df_between`、`df_within`、`eta_squared`

失败 payload：
```json
{"groups": [[1, 2, 3]]}
```

## 监督学习与聚类

### `linear-regression`

适用于数值特征与连续目标；新入口返回 JSON 参数和指标，不返回 estimator。

最小合法 payload：
```json
{"X": [[1.0], [2.0], [3.0]], "y": [3.0, 5.0, 7.0], "predict_X": [[4.0]]}
```

核心输出：`training_predictions`、`coefficients`、`intercept`、`rmse`、`mae`、`r_squared`、`predictions`

失败 payload：
```json
{"X": [[1.0], [2.0]], "y": [3.0]}
```

### `decision-tree`

适用于分类标签；随机性由 `seed` 管理，不能与底层 `random_state` 冲突。

最小合法 payload：
```json
{"X": [[0.0], [1.0], [2.0], [3.0]], "y": ["low", "low", "high", "high"], "params": {"max_depth": 1}, "seed": 7}
```

核心输出：`training_predictions`、`classes`、`accuracy`、`feature_importances`、`tree_depth`

失败 payload：
```json
{"X": [], "y": [], "seed": 7}
```

### `logistic-regression`

适用于至少两个类别的监督分类；拟合不收敛或类别不足时失败关闭。

最小合法 payload：
```json
{"X": [[-2.0], [-1.0], [1.0], [2.0]], "y": ["negative", "negative", "positive", "positive"], "params": {"C": 1000.0, "max_iter": 1000, "solver": "liblinear"}, "seed": 7}
```

核心输出：`training_predictions`、`classes`、`accuracy`、`coefficients`、`intercept`

失败 payload：
```json
{"X": [[-1.0], [1.0]], "y": ["same", "same"], "seed": 7}
```

### `kmeans`

适用于预先考虑尺度影响的数值特征；固定 `seed` 保证可复现标签规范化。

最小合法 payload：
```json
{"X": [[0.0, 0.0], [0.0, 2.0], [10.0, 10.0], [10.0, 12.0]], "params": {"n_clusters": 2, "n_init": 10}, "seed": 7}
```

核心输出：`labels`、`cluster_count`、`noise_count`、`cluster_centers`、`inertia`、`iteration_count`

失败 payload：
```json
{"X": [[0.0], [1.0]], "params": {"n_clusters": 3}, "seed": 7}
```

### `dbscan`

适用于密度聚类；未声明已标准化时，结果警告尺度敏感性。

最小合法 payload：
```json
{"X": [[0.0], [0.1], [5.0], [5.1]], "params": {"eps": 0.25, "min_samples": 2}}
```

核心输出：`labels`、`cluster_count`、`noise_count`

失败 payload：
```json
{"X": [[0.0], [0.1]], "params": {"eps": 0, "min_samples": 2}}
```

### `hierarchical-clustering`

适用于层次聚类和树结构诊断；`n_clusters` 与 `distance_threshold` 互斥。

最小合法 payload：
```json
{"X": [[0.0], [0.2], [5.0], [5.2]], "params": {"n_clusters": 2, "linkage": "complete", "metric": "euclidean"}}
```

核心输出：`labels`、`cluster_count`、`noise_count`、`linkage_matrix`

失败 payload：
```json
{"X": [[0.0], [0.2], [5.0], [5.2]], "params": {"n_clusters": 2, "distance_threshold": 1.0}}
```

## Legacy 边界

`run_model(name, X, y)` 是 legacy 兼容入口，保留旧线性回归、决策树和 KMeans 调用行为，并返回 fitted estimator。`execute(model_id, payload)` 才是 Codex/DSH 契约：它按注册表分派七类执行器，只返回通过 `shared/contracts/model-execution.schema.json` 校验的 JSON 数据。两者不能互换，也不能把 estimator 序列化进交接物。
