# 环境与依赖

## 必需依赖

| 检查项 | 必需 | 说明 | 2026-08-22 实测 |
| --- | --- | --- | --- |
| `python` | 是 | 3.11.x（契约 `environment.python_version` 固定为 `"3.11"`） | 3.11.x（见 bootstrap 探测） |
| `uv` | 是 | 依赖锁与 `.venv` 恢复工具 | 不在 PATH；由 `scripts/bootstrap.ps1` 引导至 `.superpowers\bootstrap-uv` |
| `xelatex` | 是 | XeLaTeX 引擎（中文 PDF 主生产线） | MiKTeX 用户级安装，`%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64\xelatex.exe` |
| `latexmk` | 是 | 检查项：PATH 存在性（本机因缺 Perl 不可运行，doctor 会报 `ok=false`；最小链路用 xelatex 双遍直编） | 同 MiKTeX bin 目录 |

> 注：`latexmk` 依赖 Perl 脚本引擎。本机（2026-08-22）未安装 Perl，`latexmk` 虽在 PATH 上但不可用（MiKTeX 报 "could not find the script engine 'perl'"），doctor 的 `latexmk` 探针报 `ok=false`。最小链路不依赖 latexmk：`latex/build` 用 xelatex 双遍直编（第 1 遍生成 aux/标签，第 2 遍解析引用），引文解析由 xelatex → bibtex → xelatex → xelatex 序列完成（bibtex 是 MiKTeX 独立可执行文件，不需要 Perl）。如需 `latexmk`，请另行安装 Perl（如 Strawberry Perl）或使用自带 Perl 的 TeX Live。

## 恢复环境

```powershell
pwsh -NoProfile -File scripts\bootstrap.ps1
```

幂等：引导缺失的 uv，然后 `uv sync --frozen --dev` 恢复 `.venv`；重复运行安全。

## 检查环境

```powershell
pwsh -NoProfile -File scripts\check_environment.ps1
```

输出稳定 JSON（`doctor_version`、`status`、`checks`、`errors`）；任一必需项缺失或不可运行时 `status = "failed"` 且退出码为 1。doctor 对 `uv`/`xelatex`/`latexmk` 先解析路径、再以 `--version` 探针验证可运行性（presence ≠ runnability）：二进制在 PATH 上但探针失败（例如本机 `latexmk` 缺 Perl 脚本引擎）时 `ok = false`。`uv` 不在 PATH 时回落探测仓库引导目录 `.superpowers\bootstrap-uv\Scripts`，且 `scripts\check_environment.ps1` 会把该目录加入 PATH 供 doctor 发现。

## 失败处理

- 缺 `.venv`：先运行 `scripts\bootstrap.ps1`。
- `uv` 缺失：bootstrap 自动引导；如需手动：`python -m venv .superpowers\bootstrap-uv` 后 `pip install uv==0.12.5`。
- TeX 缺失或未在 PATH：安装 MiKTeX 并确认 `xelatex`、`latexmk` 在 PATH；本仓库依赖用户级安装（`%LOCALAPPDATA%\Programs\MiKTeX`）。
