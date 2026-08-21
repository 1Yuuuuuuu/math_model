# 论文与文献能力矩阵

> 状态警告：`cumcm-orchestrator` 是未来 CUMCM 默认入口，`literature-researcher` 是未来按需子 Skill；二者目前均为规划能力，尚未安装或实现。本文也不把 CLI、`cumcm_*` 运行时工具或 DSH 插件描述为当前可用。

## 统一路由政策

工作台以 Codex 为主要入口，未来由 `cumcm-orchestrator` 编排模块化 CUMCM 流程，并只在背景事实、方法来源、对比基线、数据来源或明确引用要求需要外部证据时调用 `literature-researcher`。检索结果先进入候选文献表；只有经人工确认、登记 `literature-source`，并以 `citation-link` 绑定到具体主张和定位后，才能进入 BibTeX、LaTeX 与正文引用。

正式引用清单随论文提纲在人工门 3 批准，不增加第五个全局人工门。没有可用后端时，只能给出检索计划或继续不依赖文献的工作，不得伪造 DOI、作者、年份、来源或结论。

## 能力与阶段归属

以下“当前观察”是 2026-08-21 在受检 Codex 会话中的静态事实，不是持续探测结果：三个个人 Skill 文件夹均存在；`paper-search` CLI 当前不可用；`cumcm_*` 运行时工具不可用或未确认。Task 1 的可复用盘点工具按用户指示未建设，因此本矩阵不依赖盘点脚本或盘点命令。

| 能力 | 触发条件 | 范围 | 所需工具 | 当前观察状态 | 失败或备选角色 | 迁移来源 | 目标阶段 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `cumcm-orchestrator` | CUMCM 全流程或恢复请求 | 判断阶段、编排子 Skill、维护四个人工门 | 稳定契约、工作流状态与各阶段工具 | 规划中，未实现、未安装 | 明示 `cumcm-paper` 或 `math-modeling-paper`，不得静默切换 | 新建 Codex 适配，消费 `shared/` | Phase 6；Phase 7 提供 DSH 对应入口 |
| `literature-researcher` | 主张需要外部证据或用户只要求文献研究 | 检索计划、候选归一化、筛选、来源记录；不写正文、不批准引用 | 获准的搜索/读取后端或用户文件 | 规划中，未实现、未安装 | 无后端时只输出检索计划并停止引用路径 | 参考个人 `paper-search` Skill 的工作流，经复核后重建 | Phase 3；Phase 7 提供 DSH 同名 Skill |
| `cumcm-paper` | 用户显式选择 CUMCM legacy 单 Skill 流程 | CUMCM 写作资料与 LaTeX 辅助 | 其声明的 `cumcm_*` 工具或人工替代步骤 | 个人 Skill 文件夹存在；`cumcm_*` 工具在受检会话中不可用或未确认 | CUMCM 模块化流程尚未完成时的兼容入口；必须暴露工具缺口 | 模板和写作资料仅作为迁移候选 | Phase 4 分批复核资料；仍保留 legacy 入口 |
| `math-modeling-paper` | 用户显式选择 MCM/ICM、其他竞赛或单 Skill 快速流程 | 通用数学建模论文流程 | 用户数据、计算与排版环境 | 个人 Skill 文件夹存在；不含已确认联网检索后端 | MCM/ICM 默认 legacy 选项，也可作为模块化流程不可用时的明示备选 | 通用写作资料仅作为迁移候选 | Phase 4 按需复核；不成为 CUMCM 共享核心开发源 |
| `paper-search` | 已获准后端且需要搜索或读取论文 | 检索、读取或下载并返回待归一化结果 | `paper-search` CLI 及其网络/数据源配置 | 个人 Skill 文件夹存在，但 CLI 当前不可用 | 改用获准的运行时检索工具、用户提供 PDF/DOI/BibTeX，或只生成检索计划 | 后端选择与查询策略的迁移参考 | Phase 7 的确定性搜索/读取 Tool；安装须另行授权 |

## 请求路由

| 请求类型 | 未来默认路线 | 当前或失败时路线 | 控制点 |
| --- | --- | --- | --- |
| CUMCM 完整流程 | `cumcm-orchestrator` → 按需 `literature-researcher` → 论文生产 | 默认入口尚未实现；向用户展示 legacy 选项 | 候选文献在人工门 3 随提纲确认 |
| CUMCM legacy 流程 | 不自动选择 | 用户显式选择 `cumcm-paper` | 声明缺失的 `cumcm_*` 工具，不伪造替代结果 |
| MCM/ICM 或其他建模竞赛 | 未来通用模块路线；不冒充 CUMCM 总控 | 用户显式选择 `math-modeling-paper` | 仍遵守真实数据、真实运行与引用证据要求 |
| 仅文献研究 | `literature-researcher` → 候选表 → 人工确认 → 来源记录 | 当前可基于用户提供材料做检索规划和离线阅读 | 不把候选直接写成参考文献 |
| 无后端任务 | 生成检索式与待提供材料清单 | 继续不依赖文献的部分或停止引用流程 | 失败关闭，不用模型记忆补全来源 |

## 迁移与双端发布规则

个人 Skill 只作为迁移输入，不是仓库或 DSH 的隐式依赖。资源只有在完成文件级哈希清单、来源与许可审查、内容差异审查、去重和针对性测试后，才可归一化迁入 `shared/`；`cumcm-paper`、`math-modeling-paper` 与 `paper-search` 的内容不直接复制到共享核心。冲突内容必须依据当前契约、年度规则和人工决定处理，不能以更新时间自动覆盖。

`shared/` 是 Codex 与 DeepSeek Harness 的唯一开发源。Codex Skill 和 DSH Skill/Tool 由各自阶段的打包过程消费相同契约与资产，并校验哈希和语义一致性；Windows 环境不依赖符号链接。Phase 7 的 DSH 检索 Tool 必须使用确定性搜索/读取接口，并显式声明网络、允许域和凭据权限。

## 后续阶段所有权

- Phase 2：交付共享的文献检索知识、去重规则和来源评价规则及其合成知识测试；不实现运行时 Skill。
- Phase 3：实现 Codex `literature-researcher` 运行时 Skill 及触发、非触发、路由和无后端测试。
- Phase 4：实现引用证据 linker、BibTeX/LaTeX 集成和 `citation-check`。
- Phase 6：为 `cumcm-orchestrator` 增加可选文献分支，并在人工门 3 批准引用清单。
- Phase 7：实现 DSH 同名 Skill、确定性搜索/读取 Tool 与显式网络权限。
- Phase 8：对历史案例执行引用相关性、支持边界和来源 provenance 回归。
