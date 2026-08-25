# CUMCM 72 小时总控使用手册

本手册用于完整竞赛流程。总控以事件历史为唯一事实来源，每轮只返回一个下一动作；专用建模、写作或评审任务仍交给对应能力执行。

## 启动与恢复

1. 准备独立工作区，并固化赛题、附件和年度规则。
2. 使用 `cumcm-orchestrator` 启动或恢复；已有记录时必须完整提供 `workflow-event` 历史、human `decision` 和当前 `review-bundle`。
3. 执行返回的唯一动作，索引真实产物，再追加一个事件。子 Skill 必须按配置顺序完成，不能直接伪造 `stage_completed`。不要从聊天描述推断完成状态。
4. 遇到 `human_gate` 立即停止，等待人类审阅绑定产物并形成正式决定。

## 72 小时节奏

| 小时 | 阶段 | 专用能力与退出条件 |
| --- | --- | --- |
| 0–6 | intake | `problem-reader`、`data-auditor`；停在 `gate_1_problem` |
| 6–14 | model_design | `model-selector`；停在 `gate_2_model` |
| 14–36 | solve | `solver`、`sensitivity-analyst`；显式选择 optional literature 分支 |
| 36–42 | outline | 形成提纲和引用清单；停在 `gate_3_outline` |
| 42–58 | write | 形成论文与可构建源；缺写作能力时阻塞并说明缺口 |
| 58–68 | review | 五门独立评审，汇总必须为 `ready_for_phase_6`；停在 `gate_4_submission` |
| 68–70 | submission | 生成最终提交包并核对哈希 |
| 70–72 | complete | 留出上传、复核和应急时间，不再改动已提交版本 |

## 四个人工门

- `gate_1_problem`：确认问题拆解和数据需求。
- `gate_2_model`：确认模型、基线、验证和实验设计。
- `gate_3_outline`：确认提纲、引用清单，以及需要时的候选文献；选择 required 后，决定必须绑定文献候选 artifact。optional literature 不新增人工门。
- `gate_4_submission`：确认当前论文/PDF及五门 `ready_for_phase_6` 汇总；评审包、attach 事件和人工决定必须绑定同一论文/PDF artifact。

任何人工门都不能由总控或子 Skill 自批。被拒绝、产物更新或评审过期时，按恢复手册修订并重新审查。

## 本地核验

从仓库根目录运行：

```powershell
.venv\Scripts\python.exe -m pytest toolkit/tests/workflow tests/e2e/test_four_human_gates.py tests/e2e/test_optional_literature_branch.py tests/e2e/test_resume_after_failure.py tests/e2e/test_orchestrated_competition_flow.py -q -p no:cacheprovider
.venv\Scripts\python.exe scripts/validate_contracts.py
.venv\Scripts\python.exe scripts/package_codex_skills.py --check
```
