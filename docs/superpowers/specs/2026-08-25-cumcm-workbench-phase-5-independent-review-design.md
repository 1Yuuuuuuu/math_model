# Phase 5 独立评审基础设计

**状态：** 历史基础片已完成；Phase 4 合流与 Phase 5 完整闭环已由完成规格接续
**实施范围：** 不依赖 Phase 4 最终论文/PDF 的评审基础、模型评审与失效机制
**接续规格：** `docs/superpowers/specs/2026-08-25-cumcm-workbench-phase-5-completion-design.md`

## 目标

在 DSH 并行建设 Phase 4 时，先交付可独立验证的 Phase 5 基础：五套版本化评审量表、统一严重度与只读评审引擎、输入变更自动失效、评审隔离，以及消费 Phase 3 产物的 Codex `model-reviewer` Skill。

## 方案裁决

采用“先稳定评审内核，再接入论文检查器”的方案。量表格式和报告接口一次定稳；当前只让硬性、复现和模型规则在具备证据时实际裁决。论文、红队和投稿量表可以先声明规则与所需证据类型，但缺少 Phase 4 输入时只能返回 `blocked`，不得给出通过结论。

不采用以下方案：

- 只写 YAML 量表：无法验证 S0/S1 阻断、只读性和旧审批失效。
- 等 Phase 4 全部完成再开始：失去与 DSH 并行的价值，并推迟模型评审。
- 为 Phase 5 猜测 Phase 4 文件结构：容易形成第二套接口，合并成本高。

## 组件边界

| 组件 | 当前阶段职责 | 不做 |
| --- | --- | --- |
| `shared/rubrics/*.yaml` | 定义规则 ID、评审门、严重度、检查器、所需证据和建议 | 不保存某次评审结果 |
| `review/severity.py` | 校验 S0-S3、计算阻断状态 | 不读取文件或执行规则 |
| `review/engine.py` | 加载量表、规范化输入、计算哈希、执行注册检查器、生成只读报告 | 不修改被审对象，不自动修订 |
| `model-reviewer` | 读取 Phase 3 交接物并调用模型量表，返回问题与复审条件 | 不重新选模型，不修改实验 |
| `paper-reviewer` | 等 Phase 4 最终接口后实现 | 当前不创建占位 Skill |

## 量表结构

五个量表文件为：

- `reproducibility.yaml`
- `model-quality.yaml`
- `paper-quality.yaml`
- `red-team.yaml`
- `submission.yaml`

每个量表使用相同结构：

```yaml
rubric_id: model-quality
version: "1.0"
review_gate: model
rules:
  - rule_id: model_baseline_present
    severity: S1
    checker: required_path
    params:
      path: model_selection.baseline
    summary: The model selection has no evaluated baseline.
    evidence_paths:
      - evidence_refs
    recommendation: Add and evaluate a simple baseline.
```

每条规则必须提供非空 `summary` 和 `recommendation`。允许的检查器仅来自显式注册表，首批包括：`required_path`、`non_empty`、`equals`、`all_present`、`hash_matches`。YAML 不能携带代码、表达式或任意导入路径。

`paper-quality`、`red-team` 和 `submission` 中依赖 Phase 4 的规则使用 `requires_capability` 标记所需输入（如 `citation_check`、`latex_build`、`pdf_inspect`）。能力不存在时整个门返回 `blocked`，而不是跳过规则后误报通过。

## 严重度和裁决

| 严重度 | 含义 | 对单门结果的影响 |
| --- | --- | --- |
| S0 | 规则、证据或提交合法性根本失效 | 阻断 |
| S1 | 关键模型、复现或论文质量缺陷 | 阻断 |
| S2 | 重要但不阻止继续迭代的问题 | 不阻断，必须记录 |
| S3 | 表达、维护或轻微改进项 | 不阻断，必须记录 |

单门状态为 `passed`、`failed` 或 `blocked`：存在 open S0/S1 finding 为 `failed`；缺少执行该门的前置能力或证据索引为 `blocked`；其余为 `passed`。`accepted_risk` 不自动解除 S0，S1 只有带人工 decision ID 时才可不阻断；当前独立片不实现这一人工裁决写入流程。

## 评审输入与报告

评审引擎消费普通映射，但在执行前将其转换成排序键、禁止 NaN/Infinity 的规范 JSON，并计算 SHA-256。报告包含：

```yaml
review_id: review_<digest>
rubric_id: model-quality
rubric_version: "1.0"
review_gate: model
evaluated_rule_ids: []
rubric_digest: <sha256>
input_digest: <sha256>
reviewed_files: []
status: passed | failed | blocked
findings: []
errors: []
reviewed_at: <RFC3339>
```

每个实际 finding 必须符合既有 `review-finding.schema.json`，包含现存的 `clm_*` 证据引用、严重度和修订建议。若连可引用的证据索引都不存在，引擎在 `errors` 中返回阻塞原因，不伪造 `clm_*`。

## 只读性、隔离与失效

1. 引擎不接受修订回调，只返回新报告。
2. 测试在评审前后计算源目录文件哈希，必须完全相等。
3. 每次只运行一个量表；模型门不能读取论文门规则或替其他门给结论。
4. `is_review_current(report, inputs, rubric, reviewed_files, file_root)` 重新计算输入、量表和实际文件内容哈希；任一变化均返回 `false`。
5. 旧报告不被原地改写，调用方必须重新运行并生成新的 `review_id`。

## Model Reviewer Skill

`adapters/codex/skills/model-reviewer/` 延续 Phase 3 Skill 结构：`SKILL.md`、`agents/openai.yaml`、`resources.json`。它的输入至少包括：

- `problem-analysis`
- `data-audit`
- `model-selection`
- `solver-run`
- `sensitivity-report`
- 对应 `clm_*` 证据索引

Skill 只能读取这些产物、调用模型/复现量表并输出 review report。发现问题时给定位、严重度、建议和 `resume_when`；不得直接修改模型、参数、代码或实验结果。Phase 3 打包器相应扩展为包含该 Skill，并继续进行自包含资源哈希检查。

## Phase 4 合流接口

当前不会固定 DSH 尚未交付的具体文件路径，只预留能力名：

- `evidence_linker`
- `citation_linker`
- `citation_check`
- `latex_lint`
- `latex_build`
- `pdf_inspect`

Phase 4 完成后，`paper-reviewer` 通过薄适配层把实际结构化报告映射到这些能力名；量表、严重度、哈希和失效机制不变。

## 测试与验收

1. 五份量表通过结构、唯一 ID、合法严重度、合法检查器和必备建议测试。
2. S0/S1 open finding 阻断，S2/S3 只记录。
3. 缺证据或缺 Phase 4 能力返回 `blocked`，不返回 `passed`。
4. 每条 finding 含证据位置、严重度和修订建议，并符合现有契约。
5. 评审前后源文件哈希一致。
6. 修改任一输入后旧报告自动失效；原输入仍可验证为当前。
7. 单门执行不混入其他量表的问题。
8. `model-reviewer` 有触发/不触发、缺输入和只读测试，并可自包含打包。

## 本轮明确延后

- 创建和执行 `paper-reviewer`。
- 真实 LaTeX、引用检查和 PDF 报告到评审能力的映射。
- 五门聚合为最终投稿批准及 `gate_4_submission` 人工决策。
- 自动修订论文或模型；评审与修订始终分离。

## 实施验证（2026-08-25）

- Phase 3 Skill 复审修复定向测试：48 项通过（含真实 handoff、文献路由、打包、前向观测验收器和路线文档）。
- 全仓回归：560 项通过、7 项跳过；仅有 1 条 joblib 无法读取物理核心数并回退逻辑核心的环境警告。
- 契约验证：11 个契约、0 错误。
- Codex Skill 打包：7 个 Skill，自包含资源与 SHA-256 检查通过。
