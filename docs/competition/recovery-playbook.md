# CUMCM 流程恢复手册

恢复原则是“保留历史、追加事实、重新验证”。不得删除失败事件、覆盖旧产物或手工改写派生状态。

## 标准恢复步骤

1. 重放全部事件并确认 `runtime_status: blocked`。
2. 阅读 `blocked_reason` 和每条 `resume_when`，只处理列出的缺口。
3. 保留已经索引且哈希有效的产物；修订内容写为新产物。
4. 条件满足后追加 `resumed`，让总控重新计算唯一下一动作。
5. 若被审文件变化，清空旧 Reviewer 完成状态，重跑受影响 Reviewer，并用五份当前报告和当前 `reviewed_artifact_ids` 重建 `review-bundle`。

## 常见故障

| 故障 | 禁止做法 | 恢复条件 |
| --- | --- | --- |
| 子 Skill 失败 | 假造完成事件 | 修复输入或能力，满足 `resume_when` 后恢复 |
| 人工门拒绝 | 修改旧 decision | 产出新版本并创建新的 human decision |
| 事件链断裂 | 手工调整 sequence | 找回最后有效事件，从其摘要后追加 |
| 文献能力不可用 | 编造引用 | 跳过 optional literature，或恢复真实检索能力 |
| 评审汇总过期 | 继续批准 `gate_4_submission` | 重评受影响门并重建 `ready_for_phase_6` 汇总 |
| 写作能力缺失 | 声称论文已生成 | 返回 blocked，明确所需 outline/write 能力 |

恢复后应再次运行定向测试、合同验证和 Skill 打包检查。若旧产物仍有效，总控会保留它们，不要求重复覆盖。
