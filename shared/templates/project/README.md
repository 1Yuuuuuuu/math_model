# 比赛工作区

本目录是单次比赛的标准工作区，由 project-scaffold 创建，结构固定：

- `data/`        原始数据与清洗后数据
- `code/`        求解与分析脚本
- `experiments/` 实验记录（experiment manifest JSON）
- `artifacts/`   图表、结果表、索引等产物
- `paper/`       论文 LaTeX 工程

约定：实验记录写为 `experiments/<experiment_id>.json`，产物索引写为 `artifacts/index.json`。
比赛临时文件只允许放在本工作区内，不得修改共享核心。
