# 标准比赛工作区布局

每个比赛工作区由 `project-scaffold` 从 `shared/templates/project/` 创建，可重复生成；已存在文件默认不覆盖（`--overwrite` 显式覆盖模板文件）。

| 路径 | 用途 |
| --- | --- |
| `README.md` | 工作区说明与目录约定 |
| `data/` | 原始数据与清洗后数据 |
| `code/` | 求解与分析脚本 |
| `experiments/` | 实验记录，约定写为 `experiments/<experiment_id>.json`（符合 `experiment` 契约） |
| `artifacts/` | 图表、结果表等产物；约定索引写为 `artifacts/index.json`（符合 `artifact` 契约） |
| `paper/` | 论文 LaTeX 工程 |

产物索引由 `artifact-index` 生成：跳过 `.gitkeep` 占位文件（模板内为 `data/.gitkeep`、`code/.gitkeep`、`experiments/.gitkeep`、`artifacts/.gitkeep`、`paper/.gitkeep`）与缓存目录（`.git`、`__pycache__`、`.pytest_cache`、`.superpowers`、`.venv`、`.worktrees`）；所有路径必须满足可移植工作区路径规则（相对、正斜杠、无保留设备名）。

工作区与核心仓库隔离：`workspaces/` 不入库；比赛临时修改不得直接污染 `shared/` 与 `toolkit/`。
