# Phase 0 验收关卡

> **通过条件。** 本阶段只能在全部契约测试、验证器检查与未完成标记扫描均成功后交付。离线、只读、零写入的承诺仅限于 `scripts/validate_contracts.py` 对仓库与契约数据的验证：它不得联网，也不得修改被校验的契约或样例文件。

## 运行完整关卡

在工作区根目录依次运行以下命令。两个 `uv` 命令必须保持原样，便于 Codex 与 DeepSeek Harness 使用同一套检查。

这些是常规验收命令，而不是严格沙盒的零写入声明：uv 可能同步环境或访问依赖源，pytest 可能生成缓存。若要严格复核验证器的零写入行为，应使用已锁定的本地环境并禁用 pytest cache，再比较运行前后的文件清单；不要把 uv 的环境管理行为误写成离线保证。

```powershell
uv run pytest tests/contracts -v
uv run python scripts/validate_contracts.py
$unfinishedMarkers = @('TO' + 'DO', 'T' + 'BD', '待' + '定', 'FIX' + 'ME')
Select-String -Path shared/contracts/*.json,docs/architecture/contracts.md,docs/quality/acceptance-gates.md,docs/operations/change-policy.md -Pattern $unfinishedMarkers -CaseSensitive:$false
```

## 判定结果

| 检查项 | 通过标准 | 失败时的处理 |
| --- | --- | --- |
| 契约测试 | `uv run pytest tests/contracts -v` 的 exit 0 | 修正 Schema、样例或文档后重新执行全部测试。 |
| 验证器 | `uv run python scripts/validate_contracts.py` 的 exit 0，且 JSON 显示 `status = ok`、`contracts = 9`、`errors = []` | 不发布；按验证器返回的对象与路径修正，再从第一条命令重跑。 |
| 目录与 JSON 边界 | `catalog_version` 必须是字符串 `1.0`；目录、Schema 和 fixtures 必须是严格 JSON，不含 `NaN`、`Infinity` 或 `-Infinity`；全部目录路径符合可移植工作区路径规则。 | 验证器 exit 1，输出稳定失败 JSON 且不得出现 traceback；未知目录版本按关闭失败处理。 |
| 无效样例 | 每个无效样例必须仅因其命名原因失败。 | 若无效样例通过、或同时违反多项规则，拆分并修正样例或 Schema。 |
| 未完成标记 | “未完成标记”扫描无输出。 | 删除标记并补齐相应内容，然后重新扫描。 |
| 工作区状态 | `git status --short` 仅出现本次有意提交的文件。 | 排除临时产物，确认不会把缓存、字节码或未审计文件带入提交。 |

## 为什么要同时运行两类检查

测试会检查具体边界，例如时区、路径、关卡顺序和格式校验；验证器则从 [契约目录](../../shared/contracts/catalog.json) 逐个加载九个登记对象，验证全部有效和无效样例。两者相互补足，而不是互相替代。

例如，若把 `error-missing-code.json` 意外改成了完整错误对象，验证器会返回失败，因为一个应当失败的样例通过了。此时即使其他八个对象正常，整个关卡仍不得放行。

## 验证器的离线与只读边界

`scripts/validate_contracts.py` 使用本地 [catalog.json](../../shared/contracts/catalog.json) 和本地 Schema，不解析远程引用，也不下载规则或依赖。运行结束后，应比较文件清单或执行 `git status --short`，确认没有新增字节码、缓存或被改写的样例。年度规则的网络核验是更新规则时的独立人工步骤，不属于这里的离线验证。

验证器作为命令行程序运行时会在导入本地模块前禁用 Python 字节码写入；作为库导入时不会修改调用进程的全局字节码策略。
