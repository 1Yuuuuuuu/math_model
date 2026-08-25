# Decision 2.0 迁移说明

`decision` 2.0 新增必填 `outcome`，取值只能为 `approved` 或 `rejected`。这是破坏性变更；旧 1.0 对象继续由共享 Schema 识别，但 Phase 6 工作流不消费它们。

迁移时运行 `scripts/migrate_decision_v1_to_v2.py INPUT OUTPUT --outcome approved|rejected`。`outcome` 必须由人根据原审批记录明确提供，脚本不会从 `selected_option` 或 `rationale` 推断。迁移后同时保留原文件，以便审计和回退；Codex 与 DSH 消费者在切换前都必须通过旧 fixture、迁移输出和新 fixture 的契约回归。

弃用期覆盖 Phase 6 内部验证阶段；正式发布前不得删除 1.0 Schema 分支与 fixture。若新消费者出现兼容问题，回退消费者版本并继续保存 1.0 原件，不得把 2.0 对象静默降级或丢弃 `outcome`。
