# cumcm-tools

CUMCM（全国大学生数学建模竞赛）workbench 的 DeepSeek Harness **薄适配器插件**。

本插件注册 15 个 `cumcm_*` 工具。每个工具都是纯适配器：把模型参数组装为 CLI
argv，`spawn` 一个 `python -m cumcm_toolkit.<module> <args>` 子进程，严格解析
stdout 的**最后一行 JSON**，失败即关闭（failed + 明确 error）。**TypeScript 侧零
toolkit 逻辑**——所有确定性行为（数据画像/变换、模型拟合、指标、证据/引用链接、
LaTeX 构建/检查、PDF 检查、结果导出、工作区脚手架、实验清单、产物索引）都执行
cumcm-workbench 仓库里的 Python CLI（Task 1 交付物），本插件不做任何业务逻辑。

## 安装

```sh
dsh plugin --profile <name> add <此包路径或 git/npm 引用>
```

`dsh plugin` 会把包安装进 profile 并把它对账进 `dsh.profile.bundles` 层。

## 配置

`cordis.patch.yml` 提供默认配置，可在 profile 层覆盖（整段替换，需重述所有键）：

```yaml
- insert:
    - id: cumcm-tools
      name: cumcm-tools
      config:
        cumcmRoot: 'C:\path\to\cumcm-workbench'   # 仓库根（含 .venv 与 toolkit/src）
        pythonBin: ''                              # 显式 python 绝对路径（可选，优先于 .venv）
        toolTimeoutMs: 120000                      # 每次子进程超时（毫秒）
```

- `cumcmRoot`（必配，除非 `pythonBin` 已指定）：cumcm-workbench 仓库根目录。
  子进程以其为 cwd，并注入 `PYTHONPATH=<cumcmRoot>/toolkit/src;<cumcmRoot>`，
  因此 `python -m cumcm_toolkit.*` 可解析。为空时回退到插件进程 cwd，通常不可用。
- `pythonBin`（可选）：显式 python 可执行文件绝对路径。非空时直接用它，不再探测
  `.venv` 或 `uv run`。**注意**：该 python 必须安装了 cumcm-workbench 的依赖
  （numpy/pandas/scikit-learn/pypdf 等），否则子进程失败关闭。
- `toolTimeoutMs`（可选，默认 120000）：超时后 kill 子进程并失败关闭。

### python 解析顺序（`resolvePython`）

1. `pythonBin` 非空 → 直接使用；
2. `cumcmRoot/.venv/Scripts/python.exe`（Windows）或 `.venv/bin/python` 存在 → 使用；
3. `uv` 在 PATH 上 → 使用 `["uv", "run"]`；
4. 全缺 → 抛明确错误（提示配置 cumcmRoot/pythonBin）。

## 工具清单（15）

| 工具 | Python 模块 | 说明 |
| --- | --- | --- |
| `cumcm_data_profile` | `data.profile` | CSV 数据画像报告 |
| `cumcm_data_transform` | `data.transform` | 按 steps 变换 CSV（steps 为 JSON 字符串） |
| `cumcm_model_run` | `models.runner` | 拟合注册模型（X/y 为 JSON 字符串） |
| `cumcm_metrics` | `evaluation.metrics` | 回归/分类指标（y_true/y_pred 为 JSON 字符串） |
| `cumcm_sensitivity` | `evaluation.sensitivity` | 灵敏度报告输入契约校验（validate 为 JSON 字符串） |
| `cumcm_evidence_link` | `evidence.linker` | 创建证据链接记录（claim 为 JSON 字符串） |
| `cumcm_citation_link` | `evidence.citation_linker` | 从已批准文献源创建引用链接 |
| `cumcm_latex_build` | `latex.build` | xelatex 编译论文目录（需本机 TeX 工具链） |
| `cumcm_latex_lint` | `latex.lint` | 论文目录 lint 报告 |
| `cumcm_citation_check` | `latex.citation_check` | 引用/参考文献/批准源一致性检查 |
| `cumcm_pdf_inspect` | `pdf.inspect` | PDF 检查报告（页数/空白页/字体/元数据） |
| `cumcm_result_export` | `results.export` | 结果导出（json/csv/latex 三选一 + out） |
| `cumcm_workspace_scaffold` | `project.scaffold` | 创建标准 CUMCM 工作区 |
| `cumcm_experiment_record` | `experiments.manifest` | 创建实验清单记录 |
| `cumcm_artifact_index` | `artifacts.index` | 索引工作区产物 |

JSON 型参数一律声明为 string（CLI 收 argv 字符串），description 注明「JSON 字符串」。

## 失败语义（全部 fail-closed）

- 子进程非 0 退出、stdout 无 JSON / JSON 解析失败、或契约不符 → 工具 **failed**，
  附明确 error 文本；**绝不把空输出当成功**。
- argparse 层失败（缺参/未知 flag，`SystemExit(2)` + stderr usage + 空 stdout）
  同样归 failed（I-1 契约），不崩溃。
- 超时（`toolTimeoutMs`）→ kill 子进程 → failed（timeout 错误）。
- 取消（调用方 signal abort）→ kill 子进程 → failed（cancelled）。

## 开发

```sh
pnpm typecheck   # tsc --noEmit
pnpm build       # tsc -> lib/
pnpm test        # node tests/smoke.mjs（真实注册 15 工具 + 失败关闭 + 成功路径）
```

冒烟测试需要本机 python（`cumcmRoot/.venv` 或 `pythonBin`）与 cumcmRoot 才能跑
成功路径；不可用时成功路径打印 SKIP，注册与失败关闭断言仍强制通过。
