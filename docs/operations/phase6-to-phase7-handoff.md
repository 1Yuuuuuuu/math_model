# Phase 6 → Phase 7 交接说明

Phase 6 已将 72 小时流程固化为可重放状态机。当前稳定基线为 **16 contracts**、**12 Codex Skills**、四个人工门和一个 optional literature 分支；下一阶段是 **Phase 7: DeepSeek Harness adapter**。

## DSH 必须复用的事实层

- `shared/contracts/workflow-event.schema.json`：append-only 输入。
- `workflow-state`：由事件重放得到的兼容快照。
- `decision`：仅接受 `decided_by: human`；DSH 不得自行构造审批。
- `review-bundle`：`gate_4_submission` 前必须是当前 `ready_for_phase_6`。
- `shared/workflows/*.yaml`：阶段、四门禁、路由和时间盒的唯一配置。
- `cumcm_toolkit.workflow`：配置、事件链、状态、门禁和唯一下一动作政策。

DSH 适配层不得复制或改写上述政策；应薄封装同一 Python 核心，确保同一事件序列在 Codex 与 DeepSeek Harness 得到同一快照和动作。

## Phase 7 验收

1. 映射 12 个同名 Skill，显式声明网络、文件和进程权限。
2. 为搜索/读取等外部能力提供确定性 Tool 插件；无权限时 fail closed。
3. 对 Codex 与 DSH 运行同一 golden event histories，逐字段比较状态和下一动作。
4. 验证失败恢复、optional literature、旧评审失效和四个人工门不可跳过。
5. 保留部署限制：本地静态测试通过不代表真实 DSH Agent 的触发与权限观测已经通过。

## 已知边界

Phase 6 只声明 `paper_outline` 与 `paper_write` 能力，不伪装成本地专用 Skill；Phase 7 必须明确绑定已安装论文 Skill/插件，或在能力缺失时返回 blocked。网络检索也必须由 DSH 权限配置显式允许。
