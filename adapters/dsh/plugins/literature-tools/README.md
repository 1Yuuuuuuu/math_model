# literature-tools

CUMCM（全国大学生数学建模竞赛）文献侧工作流的 DeepSeek Harness **薄适配器插件**。

本插件注册 3 个 `literature_*` 工具，提供**确定性读取/解析/路由**：

| 工具 | 定位 | 规则位置 |
| --- | --- | --- |
| `literature_read_source` | 离线确定性解析 PDF/JSON/纯文本 → candidate 候选对象 | TypeScript（纯转发解析，零规则） |
| `literature_route_candidate` | 候选数组归一化分组 + 组内冲突标记 → `{groups, conflicts}` | **Python**（`toolkit/src/cumcm_toolkit/literature/rules.py`） |
| `literature_search` | 搜索门禁（backend + allowedDomains）→ 授权占位 | TypeScript（配置门禁，无真实后端） |

**规则引擎只在 Python**：去重规则（DOI → 规范化标题 → 规范化 URL 分组、组内冲突标记）
收敛在 `toolkit/src/cumcm_toolkit/literature/rules.py`，与参考实现
`tests/knowledge/test_literature_knowledge.py` 完全一致（测试代码即规则契约）。
`literature_route_candidate` 只做参数转发：spawn `python -m cumcm_toolkit.literature.rules
--group <json>` 并包装 stdout JSON。**TS 侧零规则实现**（"不复制开发源"在文献规则上的落实）。

**候选 ≠ 引用（Phase 0A 政策）**：本插件的所有输出都是 candidate，未经人工核验不得成为正式引用。

## 安装

```sh
dsh plugin --profile <name> add <此包路径或 git/npm 引用>
```

`dsh plugin` 会把包安装进 profile 并把它对账进 `dsh.profile.bundles` 层。

## 配置

`cordis.patch.yml` 提供默认配置，可在 profile 层覆盖（整段替换，需重述所有键）：

```yaml
- insert:
    - id: literature-tools
      name: literature-tools
      config:
        sourceRoot: 'C:\path\to\cumcm-workbench'   # REQUIRED — 仓库根（含 toolkit/src/cumcm_toolkit）
        backend: ''                                 # 搜索后端标识；空 = 无后端
        allowedDomains: []                          # 网络允许域白名单（fail-closed）
```

- `sourceRoot`（**必填**，缺省或为空 → **插件启动失败**，schema required + `apply()` 拒绝运行，
  绝不静默降级）：cumcm-workbench 仓库根目录。子进程以其为 cwd，并注入
  `PYTHONPATH=<sourceRoot>/toolkit/src;<sourceRoot>`，因此
  `python -m cumcm_toolkit.literature.rules` 可解析。
- `backend`（可选，默认空）：搜索后端标识（如 `paper-search`/`runtime-search`）。空 = 无后端 →
  `literature_search` blocked（"no literature backend configured"）。
- `allowedDomains`（可选，默认空）：网络允许域白名单。**本版本无真实后端转发**，门禁采用
  fail-closed：`allowedDomains` 必须显式包含 backend 标识才放行（域令牌语义）；否则
  `literature_search` blocked（"domain not allowed"）。接入真实后端后应改为校验其实际域名。
- 凭据：经 DSH 凭据机制引用，**不写死、不硬编码**。本版本无真实后端，无需凭据。

### python 解析顺序（`literature_route_candidate` 子进程）

1. 环境变量 `LITERATURE_TOOLS_PYTHON` 非空 → 直接使用（运维/测试钩子）；
2. `sourceRoot/.venv/Scripts/python.exe`（Windows）或 `.venv/bin/python` 存在 → 使用；
3. 否则使用 PATH 上的 `python`；
4. 解释器不可用/子进程失败 → 工具 **failed**（fail-closed，附明确 error）。

## 工具

### `literature_read_source` — 离线确定性解析

- 参数：`path`（必填，PDF 或 JSON 文件绝对路径）。
- **仅支持单对象 `.json` 文件**；`.jsonl`（JSON Lines）不支持，传入即 failed（fail-closed，
  不会把多行 JSONL 当整段 JSON 误解析、也不会静默按纯文本读取）。
- PDF → 提取文本：**纯文本兜底**（仅恢复未压缩 Tj 文本流的 `(...) Tj` 内容；压缩/扫描 PDF
  可能提取为空），质量在 `extraction_note` 如实标注，**绝不伪造**。
- JSON → 解析为记录：只复制输入中实际存在的字段；`doi` 扁平字段映射到 `identifiers.doi`、
  `url` 映射到 `canonical_url` 属于字段映射而非补造。
- 输出：与 `literature-source` 契约 candidate 状态兼容的候选对象：
  `verification_status: "candidate"`；缺项保留 `null`/空并在 `metadata_gaps` 列出；
  `content_sha256` 为所读文件字节的真实 sha256。
- **不补造 DOI/作者/年份/检索时间**（缺项留空并标记）。
- 失败（文件不可读 / JSON 非法）→ failed。

### `literature_route_candidate` — 归一化 + 分组 + 冲突标记（规则在 Python）

- 参数：`candidate`（必填，JSON 字符串，候选记录数组；每条至少含 `id` 与 `doi`/`title`/`url` 之一）。
- **容量（分批）**：候选数组经单个 argv 传给子进程，受 Windows 命令行长度上限（约 32,767 字符）约束。
  **建议分批处理（≤~500 条/次）**；序列化后超过约 20000 字符时工具直接 failed 并提示分批
  （"candidate payload too large"），不会触发底层系统错误。
- 行为：把 candidate 数组原样交给 Python 规则引擎
  `python -m cumcm_toolkit.literature.rules --group <json>`，只做参数转发与结果包装。
- 输出：`{groups, conflicts}`：
  - `groups`：分组键（`doi:` / `title:` / `url:` 前缀，按 DOI → 规范化标题 → 规范化 URL 取
    第一个可用字段）→ 记录 id 列表；
  - `conflicts`：分组键 → 冲突标记列表（仅列出有冲突的组）：
    `authors_mismatch` / `year_mismatch` / `venue_mismatch` / `same_doi_diff_metadata`。
- 冲突语义（铁律）：**只标记，不合并、不挑选、不补全**——组内元数据冲突的记录保持候选状态，
  须由**人工核验**后裁决。
- 失败（python 不可用 / 非 0 退出 / stdout 非 JSON）→ failed。

### `literature_search` — 门禁 + 授权占位（无真实后端）

- 参数：`query`（必填）、`limit`（可选）。
- `config.backend` 为空 → blocked：`no literature backend configured`。
- `backend` 非空但不在 `allowedDomains` → blocked：`domain not allowed`。
- 通过门禁 → 返回授权占位（fail-closed）：
  `{"backend": <name>, "query": ..., "limit": ..., "status": "requires-user-authorization", "candidates": []}`。
- **网络后端转发未实现**：本工具仅做配置门禁 + 授权占位，等待用户授权真实后端后再转发；
  **绝不伪造检索结果**（candidates 恒为空）。

## 失败语义（全部 fail-closed）

- 子进程非 0 退出、stdout 无 JSON / JSON 解析失败、契约不符 → 工具 **failed**，附明确 error；
  **绝不把空输出当成功**（argparse 层失败 `SystemExit(2)` + 空 stdout 同样归 failed，不崩溃）。
- 超时（120s）→ kill 子进程 → failed；调用方取消 → kill 子进程 → failed。
- 缺必需配置（`sourceRoot`）→ **插件启动失败**；无后端 → 工具 blocked；均不静默降级。

## 开发

```sh
pnpm typecheck   # tsc --noEmit
pnpm build       # tsc -> lib/
pnpm test        # node tests/smoke.mjs（真实注册 3 工具 + 启动失败 + search 门禁 + read_source + 真跑 rules CLI）
```

冒烟测试的 `literature_route_candidate` 真跑 Python 规则 CLI，需要本机 python
（`sourceRoot/.venv` 或 `LITERATURE_TOOLS_PYTHON`）；不可用时该段打印 SKIP，
注册 / 启动失败 / 门禁 / read_source 断言仍强制通过。

## 与 cumcm-tools 的关系

`cumcm-tools` 提供 15 个通用确定性工具（数据/模型/证据/LaTeX/PDF/工作区）；
`literature-tools` 提供文献侧三工具。两者同构：薄适配器 + 子进程调 Python CLI + fail-closed，
规则/逻辑一律在 Python toolkit（`toolkit/src/cumcm_toolkit/`）。
