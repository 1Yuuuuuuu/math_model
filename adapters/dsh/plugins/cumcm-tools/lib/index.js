/**
 * cumcm-tools — CUMCM workbench thin adapter plugin for DeepSeek Harness.
 *
 * Registers 15 deterministic `cumcm_*` tools on `ctx.tools`. Every tool is a
 * pure adapter: it assembles model arguments into CLI argv, spawns
 * `python -m cumcm_toolkit.<module> <args>` through {@link runPythonTool}, and
 * parses the stdout JSON with fail-closed semantics. The TypeScript side
 * carries zero toolkit logic — all deterministic behavior lives in the
 * cumcm-workbench Python CLI (`toolkit/src/cumcm_toolkit/`).
 *
 * Host-only plugin: no `dsh.client`, single tsconfig program.
 */
import z from '@deepseek-ai/schemastery';
import { defineTool, } from '@deepseek-ai/dsh-tools';
import { runPythonTool } from './bridge.js';
export const name = 'cumcm-tools';
export const inject = ['tools'];
export const Config = z.object({
    cumcmRoot: z.string().default(''),
    pythonBin: z.string().default(''),
    toolTimeoutMs: z.number().default(120000),
});
/** Open object: any JSON object passes (unknown keys allowed). */
const openObject = { type: 'object', additionalProperties: true };
/** Integer or JSON null (CLI emits `null` for unset optional ints). */
const nullableInt = { oneOf: [{ type: 'integer' }, { type: 'null' }] };
const PREREQ_NOTE = '前置条件：插件已配置 cumcmRoot（cumcm-workbench 仓库根，含 .venv 与 toolkit/src）或 pythonBin 指向可用 python；' +
    '子进程以 cumcmRoot 为 cwd、注入 PYTHONPATH=<cumcmRoot>/toolkit/src;<cumcmRoot> 执行 `python -m cumcm_toolkit.*`。';
const FAIL_CLOSED_NOTE = '失败语义：Python CLI 子进程非 0 退出、stdout 非 JSON 或参数契约不符时，工具返回 failed 并附明确 error，绝不返回伪造结果。';
/**
 * Run one CLI module and fail closed on bridge failure. The returned value is
 * `any` because its concrete type is declared by each tool's `output.schema`
 * and enforced by the tool registry (ToolOutputError) at dispatch time — the
 * adapter itself never fabricates a type.
 */
async function bridgeOk(config, toolName, moduleName, argv, signal) {
    const result = await runPythonTool(config, moduleName, argv, { signal });
    if (!result.ok) {
        throw new Error(`${toolName}: ${result.error}`);
    }
    return result.data;
}
/** Stable compact renderer: the full JSON value as one text block. */
function renderJson(_args, value) {
    return [{ type: 'text', text: JSON.stringify(value) }];
}
/** The 15 tool definitions, one per cumcm_toolkit CLI module. */
function buildTools(config) {
    return [
        defineTool({
            name: 'cumcm_data_profile',
            description: '对 CSV 数据文件做画像分析，返回结构化 profile 报告（行/列数、每列 dtype/缺失/唯一值、数值列 min/max/mean/std、重复行、key 列唯一性、警告列表）。' +
                PREREQ_NOTE +
                '输入契约：path 为 CSV 文件路径；key_columns 为逗号分隔的关键列名（可选）。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                path: { type: 'string', required: true, description: 'CSV 文件路径' },
                key_columns: { type: 'string', description: '逗号分隔的关键列名（可选）' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        column_count: { type: 'integer' },
                        row_count: { type: 'integer' },
                        duplicate_rows: { type: 'integer' },
                        warnings: { type: 'array', items: { type: 'string' } },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                const argv = ['--path', args.path];
                if (args.key_columns !== undefined)
                    argv.push('--key-columns', args.key_columns);
                return bridgeOk(config, 'cumcm_data_profile', 'data.profile', argv, exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_data_transform',
            description: '按 JSON steps 对 CSV 应用数据变换（drop_columns/drop_missing/fill_missing/normalize/to_datetime/cast），写出到 output，返回 {steps_applied, warnings}。' +
                PREREQ_NOTE +
                '输入契约：input 为输入 CSV 路径；steps 为 JSON 字符串（变换步骤对象数组，如 [{"op":"fill_missing","columns":["a"],"value":0}]）；output 为输出 CSV 路径。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                input: { type: 'string', required: true, description: '输入 CSV 文件路径' },
                steps: { type: 'string', required: true, description: 'JSON 字符串：变换步骤对象数组' },
                output: { type: 'string', required: true, description: '输出 CSV 文件路径' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        steps_applied: { type: 'integer' },
                        warnings: { type: 'array', items: { type: 'string' } },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                return bridgeOk(config, 'cumcm_data_transform', 'data.transform', ['--input', args.input, '--steps', args.steps, '--output', args.output], exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_model_run',
            description: '拟合注册的机器学习模型并返回 {status, model, params, seed, fitted}。' +
                PREREQ_NOTE +
                '输入契约：name 为注册模型名；X 为 JSON 字符串（特征矩阵行数组，如 [[1,2],[3,4]]）；y 为 JSON 字符串（目标值数组，如 [0,1]）；seed 为可选整数随机种子；params 为可选 JSON 字符串（模型参数字典）。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                name: { type: 'string', required: true, description: '注册模型名' },
                X: { type: 'string', required: true, description: 'JSON 字符串：特征矩阵行数组' },
                y: { type: 'string', required: true, description: 'JSON 字符串：目标值数组' },
                seed: { type: 'integer', description: '随机种子（可选）' },
                params: { type: 'string', description: 'JSON 字符串：模型参数字典（可选）' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        status: { type: 'string' },
                        model: { type: 'string' },
                        fitted: { type: 'boolean' },
                        seed: nullableInt,
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                const argv = ['--name', args.name, '--X', args.X, '--y', args.y];
                if (args.seed !== undefined)
                    argv.push('--seed', String(args.seed));
                if (args.params !== undefined)
                    argv.push('--params', args.params);
                return bridgeOk(config, 'cumcm_model_run', 'models.runner', argv, exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_metrics',
            description: '计算回归或分类指标并返回 {metrics}。' +
                PREREQ_NOTE +
                '输入契约：kind 为 regression 或 classification；y_true/y_pred 为 JSON 字符串（真值/预测值数组）；classification 时可给 positive_label（JSON 标量，缺省自动推断）。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                kind: {
                    type: 'string',
                    required: true,
                    enum: ['regression', 'classification'],
                    description: 'regression 或 classification',
                },
                y_true: { type: 'string', required: true, description: 'JSON 字符串：真值数组' },
                y_pred: { type: 'string', required: true, description: 'JSON 字符串：预测值数组' },
                positive_label: { type: 'string', description: 'JSON 字符串：分类正类标量（可选）' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        metrics: { type: 'object', additionalProperties: true },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                const argv = ['--kind', args.kind, '--y-true', args.y_true, '--y-pred', args.y_pred];
                if (args.positive_label !== undefined)
                    argv.push('--positive-label', args.positive_label);
                return bridgeOk(config, 'cumcm_metrics', 'evaluation.metrics', argv, exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_sensitivity',
            description: '校验灵敏度报告输入契约（base_params 数值对象 + perturb 数值列表对象）并返回 {status, valid}。CLI 只做契约校验、不做评估。' +
                PREREQ_NOTE +
                '输入契约：validate 为 JSON 字符串，形如 {"base_params":{"alpha":0.1},"perturb":{"alpha":[0.05,0.15]}}。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                validate: {
                    type: 'string',
                    required: true,
                    description: 'JSON 字符串：含 base_params 与 perturb 的对象',
                },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        status: { type: 'string' },
                        valid: { type: 'boolean' },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                return bridgeOk(config, 'cumcm_sensitivity', 'evaluation.sensitivity', ['--validate', args.validate], exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_evidence_link',
            description: '为一条论断创建证据链接记录（evidence-link 契约，schema_version 1.0），返回校验通过的记录对象。' +
                PREREQ_NOTE +
                '输入契约：claim 为 JSON 字符串，必含 claim_id/claim_text/artifact_id/experiment_id/locator/boundary 字段。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                claim: {
                    type: 'string',
                    required: true,
                    description: 'JSON 字符串：论断对象（含 claim_id/claim_text/artifact_id/experiment_id/locator/boundary）',
                },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        schema_version: { type: 'string' },
                        claim_id: { type: 'string' },
                        claim_text: { type: 'string' },
                        artifact_id: { type: 'string' },
                        experiment_id: { type: 'string' },
                        boundary: { type: 'string' },
                        locator: { type: 'object', additionalProperties: true },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                return bridgeOk(config, 'cumcm_evidence_link', 'evidence.linker', ['--claim', args.claim], exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_citation_link',
            description: '从已批准的文献源记录创建引用链接记录（citation-link 契约）并返回记录。源记录 verification_status 必须为 approved 且含 decision_id，否则失败关闭。' +
                PREREQ_NOTE +
                '输入契约：source 为 JSON 字符串（文献源记录）；claim_id/usage/support_boundary 为字符串；locator 为 JSON 字符串（含 kind/value）。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                source: {
                    type: 'string',
                    required: true,
                    description: 'JSON 字符串：文献源记录（须 approved + decision_id）',
                },
                claim_id: { type: 'string', required: true, description: '论断 id' },
                usage: { type: 'string', required: true, description: 'background|method|baseline|data|limitation' },
                locator: { type: 'string', required: true, description: 'JSON 字符串：含 kind 与 value 的对象' },
                support_boundary: { type: 'string', required: true, description: '支持边界描述' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        schema_version: { type: 'string' },
                        citation_id: { type: 'string' },
                        claim_id: { type: 'string' },
                        source_id: { type: 'string' },
                        usage: { type: 'string' },
                        support_boundary: { type: 'string' },
                        verified_at: { type: 'string' },
                        locator: { type: 'object', additionalProperties: true },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                return bridgeOk(config, 'cumcm_citation_link', 'evidence.citation_linker', [
                    '--source', args.source,
                    '--claim-id', args.claim_id,
                    '--usage', args.usage,
                    '--locator', args.locator,
                    '--support-boundary', args.support_boundary,
                ], exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_latex_build',
            description: '用本机 xelatex 编译论文目录（main.tex），有 bibliography.bib 时跑 bibtex，再跑 passes 次 xelatex，返回构建报告（status/errors/warnings/pages/undefined_references/failed_pass/pdf_path/log_path）。' +
                PREREQ_NOTE +
                '额外前置条件：本机 PATH 上有 xelatex（以及 bibtex，若存在 bibliography.bib）。输入契约：dir 为含 main.tex 的论文目录；passes 为可选整数（默认 2）。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                dir: { type: 'string', required: true, description: '论文目录（含 main.tex）' },
                passes: { type: 'integer', description: 'xelatex 额外遍数（默认 2，可选）' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        status: { type: 'string' },
                        passes: { type: 'integer' },
                        pages: nullableInt,
                        failed_pass: nullableInt,
                        pdf_path: { type: 'string' },
                        log_path: { type: 'string' },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                const argv = ['--dir', args.dir];
                if (args.passes !== undefined)
                    argv.push('--passes', String(args.passes));
                return bridgeOk(config, 'cumcm_latex_build', 'latex.build', argv, exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_latex_lint',
            description: '对论文目录（main.tex + bibliography.bib）做静态 lint，返回 {status, issues}（issues 为 severity/kind/line/message 数组）。' +
                PREREQ_NOTE +
                '输入契约：dir 为含 main.tex 的论文目录。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                dir: { type: 'string', required: true, description: '论文目录（含 main.tex）' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        status: { type: 'string' },
                        issues: { type: 'array', items: { type: 'object', additionalProperties: true } },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                return bridgeOk(config, 'cumcm_latex_lint', 'latex.lint', ['--dir', args.dir], exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_citation_check',
            description: '检查 LaTeX 引用与 bibliography.bib、citation-link 记录、已批准源 id 的一致性，返回报告（status/missing_bibtex/unapproved_sources/uncited_entries/unmatched_citations/orphaned_citations/errors）。' +
                PREREQ_NOTE +
                '输入契约：tex/bib 为 .tex/.bib 文件路径；citations 为 JSON 字符串（citation-link 记录数组）；approved_source_ids 为 JSON 字符串（已批准源 id 数组）。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                tex: { type: 'string', required: true, description: '.tex 文件路径' },
                bib: { type: 'string', required: true, description: '.bib 文件路径' },
                citations: { type: 'string', required: true, description: 'JSON 字符串：citation-link 记录数组' },
                approved_source_ids: { type: 'string', required: true, description: 'JSON 字符串：已批准源 id 数组' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        status: { type: 'string' },
                        missing_bibtex: { type: 'array', items: { type: 'string' } },
                        unapproved_sources: { type: 'array', items: { type: 'string' } },
                        uncited_entries: { type: 'array', items: { type: 'string' } },
                        unmatched_citations: { type: 'array', items: { type: 'string' } },
                        orphaned_citations: { type: 'array', items: { type: 'string' } },
                        errors: { type: 'array', items: { type: 'string' } },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                return bridgeOk(config, 'cumcm_citation_check', 'latex.citation_check', [
                    '--tex', args.tex,
                    '--bib', args.bib,
                    '--citations', args.citations,
                    '--approved-source-ids', args.approved_source_ids,
                ], exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_pdf_inspect',
            description: '检查 PDF 文件，返回 {status, pages, blank_pages, fonts, metadata, errors}。' +
                PREREQ_NOTE +
                '输入契约：pdf 为 PDF 文件路径。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                pdf: { type: 'string', required: true, description: 'PDF 文件路径' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        status: { type: 'string' },
                        pages: { type: 'integer' },
                        blank_pages: { type: 'array', items: { type: 'integer' } },
                        fonts: { type: 'array', items: { type: 'object', additionalProperties: true } },
                        metadata: { type: 'object', additionalProperties: true },
                        errors: { type: 'array', items: { type: 'string' } },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                return bridgeOk(config, 'cumcm_pdf_inspect', 'pdf.inspect', ['--pdf', args.pdf], exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_result_export',
            description: '把结果导出为文件（json/csv/latex 三选一），返回 {status, path, format}。' +
                PREREQ_NOTE +
                '输入契约：json（JSON 字符串，任意数据）、csv（JSON 字符串，行对象数组）与 latex（布尔）三者恰好选一；latex 模式需 rows（JSON 字符串，行对象数组）并可给 caption；out 为输出文件路径（必填）。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                json: { type: 'string', description: 'JSON 字符串：要导出为文件的数据（json 模式）' },
                csv: { type: 'string', description: 'JSON 字符串：行对象数组（csv 模式）' },
                latex: { type: 'boolean', description: 'true 时导出 rows 为 LaTeX 表格（latex 模式）' },
                rows: { type: 'string', description: 'JSON 字符串：行对象数组（latex 模式必填）' },
                caption: { type: 'string', description: 'LaTeX 表格标题（可选）' },
                out: { type: 'string', required: true, description: '输出文件路径' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        status: { type: 'string' },
                        path: { type: 'string' },
                        format: { type: 'string' },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                if (args.latex === true) {
                    const argv = ['--latex'];
                    if (args.rows !== undefined)
                        argv.push('--rows', args.rows);
                    if (args.caption !== undefined)
                        argv.push('--caption', args.caption);
                    argv.push('--out', args.out);
                    return bridgeOk(config, 'cumcm_result_export', 'results.export', argv, exec.signal);
                }
                if (args.json !== undefined) {
                    return bridgeOk(config, 'cumcm_result_export', 'results.export', ['--json', args.json, '--out', args.out], exec.signal);
                }
                if (args.csv !== undefined) {
                    return bridgeOk(config, 'cumcm_result_export', 'results.export', ['--csv', args.csv, '--out', args.out], exec.signal);
                }
                // No mode selected: pass only --out and let argparse fail closed (I-1).
                return bridgeOk(config, 'cumcm_result_export', 'results.export', ['--out', args.out], exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_workspace_scaffold',
            description: '在 target 下按标准模板创建 CUMCM 工作区 <target>/<workspace_id>，返回 {workspace_id, root, files}（files 为 path/size/sha256 列表）。' +
                PREREQ_NOTE +
                '输入契约：target 为父目录路径；workspace_id 为合法工作区 id（无路径分隔符）；overwrite 为可选布尔（true 时合并模板覆盖既有文件、不删除其他文件）。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                target: { type: 'string', required: true, description: '父目录路径' },
                workspace_id: {
                    type: 'string',
                    required: true,
                    description: '工作区 id（字母数字下划线连字符）',
                },
                overwrite: { type: 'boolean', description: 'true 时合并覆盖既有工作区（可选）' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        workspace_id: { type: 'string' },
                        root: { type: 'string' },
                        files: { type: 'array', items: { type: 'object', additionalProperties: true } },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                const argv = ['--target', args.target, '--workspace-id', args.workspace_id];
                if (args.overwrite === true)
                    argv.push('--overwrite');
                return bridgeOk(config, 'cumcm_workspace_scaffold', 'project.scaffold', argv, exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_experiment_record',
            description: '创建实验清单记录（experiment.schema 契约，schema_version 1.0，要求 Python 3.11 与 project_root/uv.lock），返回记录对象。' +
                PREREQ_NOTE +
                '输入契约：input_artifacts 为逗号分隔的 art_ 输入产物 id（必填）；code_artifact 为代码产物 id（必填）；status 为 succeeded|failed|cancelled（必填）；project_root 为含 uv.lock 的项目根（可选，默认 cumcmRoot）；parameters/metrics 为 JSON 字符串（可选）；random_seed 为可选整数；output_artifacts 为逗号分隔的 art_ 输出产物 id（可选）。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                input_artifacts: { type: 'string', required: true, description: '逗号分隔的 art_ 输入产物 id 列表' },
                code_artifact: { type: 'string', required: true, description: '代码产物 id' },
                status: {
                    type: 'string',
                    required: true,
                    enum: ['succeeded', 'failed', 'cancelled'],
                    description: '实验状态',
                },
                project_root: { type: 'string', description: '含 uv.lock 的项目根（可选，默认 cumcmRoot）' },
                parameters: { type: 'string', description: 'JSON 字符串：参数字典（可选，默认 {}）' },
                random_seed: { type: 'integer', description: '随机种子（可选）' },
                output_artifacts: { type: 'string', description: '逗号分隔的 art_ 输出产物 id 列表（可选）' },
                metrics: { type: 'string', description: 'JSON 字符串：数字指标字典（可选，默认 {}）' },
            },
            output: {
                schema: {
                    type: 'object',
                    additionalProperties: true,
                    properties: {
                        schema_version: { type: 'string' },
                        experiment_id: { type: 'string' },
                        code_artifact_id: { type: 'string' },
                        random_seed: nullableInt,
                        status: { type: 'string' },
                        started_at: { type: 'string' },
                        finished_at: { type: 'string' },
                        parameters: { type: 'object', additionalProperties: true },
                        metrics: { type: 'object', additionalProperties: true },
                    },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                const argv = [
                    '--input-artifacts', args.input_artifacts,
                    '--code-artifact', args.code_artifact,
                    '--status', args.status,
                ];
                if (args.project_root !== undefined)
                    argv.push('--project-root', args.project_root);
                if (args.parameters !== undefined)
                    argv.push('--parameters', args.parameters);
                if (args.random_seed !== undefined)
                    argv.push('--random-seed', String(args.random_seed));
                if (args.output_artifacts !== undefined)
                    argv.push('--output-artifacts', args.output_artifacts);
                if (args.metrics !== undefined)
                    argv.push('--metrics', args.metrics);
                return bridgeOk(config, 'cumcm_experiment_record', 'experiments.manifest', argv, exec.signal);
            },
        }),
        defineTool({
            name: 'cumcm_artifact_index',
            description: '索引工作区产物，返回 artifact 记录数组（每条含 schema_version/artifact_id/kind/path/sha256/created_at/source_artifact_ids）。' +
                PREREQ_NOTE +
                '输入契约：root 为工作区根目录路径。' +
                FAIL_CLOSED_NOTE,
            parameters: {
                root: { type: 'string', required: true, description: '工作区根目录路径' },
            },
            output: {
                schema: {
                    type: 'array',
                    items: { type: 'object', additionalProperties: true },
                },
                render: renderJson,
            },
            async execute(args, exec) {
                return bridgeOk(config, 'cumcm_artifact_index', 'artifacts.index', ['--root', args.root], exec.signal);
            },
        }),
    ];
}
export function apply(ctx, config) {
    const normalized = {
        cumcmRoot: config.cumcmRoot ?? '',
        pythonBin: config.pythonBin ?? '',
        toolTimeoutMs: config.toolTimeoutMs ?? 120000,
    };
    for (const tool of buildTools(normalized)) {
        ctx.tools.register(tool);
    }
}
