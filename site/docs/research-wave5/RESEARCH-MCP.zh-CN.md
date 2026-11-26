> 公开去标识副本。原始评审结论与失败记录保留；私有工作区路径已替换为占位符。

# Wave 05：只读 MCP 的输出契约与保存记录状态

研究日期：2026-11-26（Asia/Tokyo）。本轮先保存设计依据，再实施父代理批准的两个有限切片。本文不是“全网已读完”的声明；实际来源和阅读范围见末节。源代码检查基于本工作区的 a4 源文件，后续版本与真实机器验收由主代理合并记录。

## 决定

接受两项改进，均保持 stdio、启动时固定 state/config、无执行权限、无公开监听器：

1. 为现有只读工具提供可发现并由固定 SDK 验证的输出 schema，保持原有 `structured_content` 和 JSON 文本内容。
2. 新增 `operator_request_status(request_id)`，只摘要本地保存的 intent/receipt 记录。它不查询活进程，不启动动作，不取消、不重放，也不把缺少 receipt 解释成仍在运行。

这两项让有本地 stdio 客户端能力的 Agent 更可靠地理解证据。它们不会让云端 ChatGPT 自动连接用户电脑，不改变 Browser origin 拒绝，也不等同于完整本地 Agent 或任意 GUI 权限。

## 已检查的现有接口

完整阅读 `rdc_operator/mcp_server.py`、`tests/test_mcp_contract.py`、`docs/MCP.zh-CN.md`、`skills/rdc-operator-kit/SKILL.md`、`AGENTS.md`、`README.md`、`docs/ARCHITECTURE.zh-CN.md` 和 `pyproject.toml`；阅读 `core.py` 中 intent/receipt 恢复流程及 `scripts/smoke_mcp.py` 的主要会话与 fixture 流程。不是整个仓库逐行审计。

现有 MCP 暴露 `operator_capabilities` 和 `operator_receipt`。capabilities 仅判断配置 argv 是否存在，明确 `runtime_probes_performed: false`；receipt 按严格 request ID 定位固定目录，拒绝链接、非普通文件、多硬链接、超限、重复 JSON key、非有限数字、读取中变化和错误身份，并返回原 receipt。现有 `receipt_authenticity_verified: false` / `live_verification_performed: false` 是必要边界，继续保留。

两个工具手工返回 `CallToolResult`，已有 JSON 文本与 `structured_content`，但 `structured_output=False` 且没有返回类型模型，因此工具目录没有可供客户端发现的 output schema。MCP 的 output schema 是可选项，所以这是互操作性改进，不应描述为原接口违反协议。

core 先保存 intent 再执行，最后保存 receipt。同 ID 的未知状态不会自动重放；intent 表示已准备意图，不能证明动作尚未发生。`completed` 是保存回执的一个字段，不能单独证明业务效果已经独立验证。MCP 状态工具必须延续这些语义。

## 切片一：SDK 验证的输出 schema

### 一手依据

[MCP Tools 2026-07-28 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) 规定 output schema 可选；提供后，服务器必须返回符合它的结构化结果，客户端应验证；兼容旧客户端时应同时提供 JSON 序列化文本。工具 annotations 是提示，不是授权机制。

[官方 Python SDK 结构化输出文档](https://py.sdk.modelcontextprotocol.io/v2/servers/structured-output/) 说明返回类型参与生成 schema，且 `structured_output=False` 会关闭自动生成。为避免当前 scalar/list 包装规则影响既有接口，本轮所有成功结果保持 object 根。

进一步阅读固定 SDK 2.3.0 的 [func_metadata.py 源码（commit 2118f14）](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/mcpserver/utilities/func_metadata.py)：

- `Annotated[CallToolResult, ReturnType]` 可提供手工结果的验证模型。
- 成功的 `CallToolResult.structured_content` 由对应输出模型验证；`is_error` 的业务错误不套成功模型。
- 仅手工填 `output_schema` 而没有 `output_model` 会公布 schema，但不会在这条 SDK 路径执行验证。
- `structured_output=False` 提前退出类型推断。
- 返回注解由 `inspect.signature(..., eval_str=True)` 求值；本项目有 future annotations 且 SDK 懒加载，不能把只存在于 `build_server` 局部作用域的类型名留成未解析字符串。

### 实施切片

在 `build_server` 内部懒加载 SDK/Pydantic 模型，给手工 CallToolResult 注册真实已求值的 `Annotated` 返回注解，再调用 SDK 注册。保留原 `as_result` 的双份内容与 `is_error` 错误语义。模型对已承诺的顶层字段采用 literal/严格类型，对原 receipt 对象保持可扩展以保留原内容。避免 alias、计算字段和可能重新包装 payload 的返回值类型。核心 CLI 在未安装 MCP extra 时仍可导入。

### 风险及验证

主要风险是 schema 只出现在目录却没有验证、误把 error 套进成功模型、局部注解不能求值，以及 schema 生成改变 receipt 内容。测试应包括：所有工具列出 object 输出 schema；success 内容与既有业务对象完全相等；错误保留 `is_error` 和稳定 code；故意注入错误形状的成功结果必须被 SDK 拒绝。注解与 fake SDK 检查只能证明本地注册意图，真实 SDK 行为必须由固定 2.3.0 的 stdio smoke 验证。

## 切片二：保守的保存记录摘要

### 收益与边界

Agent 丢失响应后可以用已知 request ID 查询“没有可读记录”“观察到 intent 而没有 receipt”“观察到已存 receipt”。无需把原 intent 内容、路径、命令或动作参数回送给模型。所有状态都只描述文件观察，不是 live task 状态。返回明确的未做 live verification、未验证真实性、未执行动作等标志。

不引入 MCP Tasks、取消、队列枚举、客户端任意路径、后台轮询或重试许可。缺少记录不能证明外部动作未发生；有 intent 无 receipt 不能证明动作还在运行；receipt 中的 `completed` 不能被改写成操作已验证成功。孤立 receipt、身份/摘要不一致、不可读记录及观察竞态应返回保守的无法判定类别或安全错误。

### 实施切片

固定三个工具名；状态工具只接受一个严格验证的 request ID，沿用 `additionalProperties: false` 和 exact-key 运行时检查。安全读取 helper 复用已有打开句柄、文件类型/硬链接、大小、JSON、读取前后 fingerprint 校验；不新增路径入口。receipt 工具维持既有错误 code 和原文透传契约。

状态摘要只输出固定枚举与布尔值，不反射文件内部的 action、command、path、args、digest、异常内容或其他未知字段。有限次观察区分文件是否被替换/创建/删除；跨文件快照永远明确不是原子快照。无法稳定解释的组合保持 unknown/inconclusive，而非自动重试建议。

### 具体反例

| 反例 | 必须得到的边界 |
|---|---|
| intent 已持久化，输入发生后进程崩溃 | 仅报告 intent/无 receipt，不能声称 running 或 safe-to-retry |
| receipt 存在但 intent 缺失 | 不能把孤立 receipt 当成完整请求状态 |
| intent 与 receipt 的 request ID / digest 不一致 | 无法判定，不返回外来字段 |
| 先读 intent 为空，随后新请求保存了两份文件 | 竞态保守处理，不能宣称从未执行 |
| intent 中塞入秘密命令/路径/提示注入内容 | 状态摘要与错误不包含这些内容 |
| request ID 指向符号链接、硬链接、FIFO 或过大文件 | 拒绝，不跟随、不阻塞、不读出私有内容 |
| SDK schema 声明 boolean，而实现返回字符串 | 真 SDK 验证失败，不能只依赖目录外观 |

## Scite 的用途和限制

按 `"Model Context Protocol" AND (benchmark OR evaluation)` 搜索，返回 5 条元数据；只选择与本接口上下文风险直接相关的一项继续核对。Scite verify 返回 DOI 找到且没有其工具所列的 editorial notices，但这不等于论文已获同行评审，也不证明其全部结论可靠。

Birhan, N., Rostamzadeh, M., Narula, S., Nazzal, M., GhasemiGol, M., & Takabi, D. (2026). *COPEX: Benchmarking LLM Robustness to Adversarial Context Across Model Context Protocol (MCP) Layers*. https://doi.org/10.48550/arxiv.2610.04378

实际阅读 Scite 返回的摘要、三段相关摘录和 APA 元数据；没有读全文。摘录涉及工具 schema、工具输出与传输层上的对抗上下文，以及仅扫描模型可见内容的边界。本轮据此作出的工程推断是：输出 schema 可以改善类型和互操作性，不能成为内容可信、授权或整个 Agent 安全的证明；保存 receipt 仍是待解释的数据，不是新指令。没有引述该论文的数值指标，也没有把它当作本项目实测。

## 真正读取范围与访问记录

| 来源 / 工具 | 实际取得并阅读 | 没有取得或没有主张 |
|---|---|---|
| Firecrawl Alexandria | 一次开发者文档发现查询返回空 | 不声称其索引已覆盖 MCP |
| Firecrawl / MCP Tools 2026-07-28 | HTTP 200；主页面工具定义、structured content、output schema、error handling、security 相关段落；scrape `01a21698-620a-71fa-a014-8dfecbc03abc` | 227,627 字符响应包含页面 hydration；没有逐字读完这些杂项 |
| Firecrawl / SDK structured-output | HTTP 200；主体文档；scrape `01a21698-61b6-748d-9027-c4f9ab8702c6` | 不是整个 SDK 文档站审计 |
| Firecrawl / 固定 SDK 源码 | HTTP 200；FuncMetadata 初始化、convert_result、func_metadata 注解分支；scrape `01a2169a-e0d0-75f5-8c8b-f39b9262d225` | 不是整个 python-sdk 仓库 review |
| Firecrawl developer search | 官方迁移文档、结构化输出文档、SDK 测试及 issue 的检索片段 | issue 报告不算本轮已复现事实 |
| Scite | 5 条搜索元数据；1 DOI 核对；3 摘录；1 APA 条目 | 未阅读全文、未作系统综述 |
| 官方 arXiv abs 尝试 | web open 返回 DisabledError | 不把该页列为已成功阅读，也未换路线绕过访问拒绝 |

## 验收安排

本 Linux 容器已观察到全局 `mcp==1.29.0`，不是本项目要求的 2.3.0。此轮不安装环境、不修改全局依赖。先做受影响的 stdlib 合成业务测试与协议契约 mock，保留全部旧反例；再将精确文件交主代理在已有 Windows `.venv-mcp` 的 2.3.0 执行现代 discover 与 legacy initialize smoke。真实 SDK 没有运行前，不把新 schema 验证称为 live pass。

实施与验证结果将在本文件后续补充。本文写入时仅完成研究与设计裁决，尚未修改源代码。

## 实施后补充：本地已验证，等待真实 SDK

已按主代理后续授权完成且仅修改四个独占文件：`rdc_operator/mcp_server.py`、`tests/test_mcp_contract.py`、`scripts/smoke_mcp.py`、`docs/MCP.zh-CN.md`。其他版本文件由主代理管理，本 agent 没有改动。工具目录现在有三个只读工具。

输出模型使用懒加载 Pydantic 2 和真实已求值的 `Annotated[CallToolResult, Model]`。schema 根采用 closed object，原 receipt 的最小身份/status 字段可发现，额外回执内容仍允许并保持原文。特别加入严格 false / 整数 1 验证，避免 Python 中 `False == 0`、`True == 1` 使手工结果悄悄满足 Pydantic literal 却不满足 JSON schema。

状态返回只包含固定字段与 enum。两轮中任何文件内容或身份变化都成为 inconclusive；单文件读取中变化、非法身份和不安全文件直接安全失败。只保留内部比较所需的 fingerprint/digest/status，原 intent args/command/path 不进入摘要。没有执行或取消代码，没有新增依赖环境。

本轮执行命令：

```bash
python -m unittest discover -s tests -p test_mcp_contract.py -v
git diff --check -- rdc_operator/mcp_server.py tests/test_mcp_contract.py scripts/smoke_mcp.py docs/MCP.zh-CN.md
```

结果：31 项通过、0 failures、0 errors、0 skips；diff whitespace 检查退出 0。环境为 Linux 6.18.57 x86_64 / Python 3.12.14 / Pydantic 2.13.4 / MCP 1.29.0。31 项中 22 项是业务契约与读取反例，2 项使用真实 Pydantic 和假 SDK 注册器，7 项是进程身份合成记录。日志 `<review-workspace>/mcp-wave5-unit.log`。没有执行新 SDK 2.3.0 协议会话。

已为主代理准备的 Windows 验证：

```powershell
& '<kit-root>/.venv-mcp/Scripts/python.exe' '<kit-root>/scripts/smoke_mcp.py' --mode both --output-dir '<kit-root>/evidence/wave5-mcp-live-unique'
```

输出目录必须尚不存在。预期独立会话数为 2：modern discover 协商 2026-07-28，legacy initialize 协商 2025-11-25；每会话恰好 3 工具。Windows 走额外 held worker HANDLE 验证时每会话预期 30 个检查，非 Windows 29 个。应读取真实 summary 而非用预计数量代替结果。

真实协议反例仅存在于本次新建的 fixture launcher：对合成 request ID `fixture-schema-invalid` 返回 `snapshot_atomic: 0`；真实 SDK 必须回 `isError`。这同时核查了 server-side output model 实际执行，不能由“目录包含 outputSchema”替代。另以私有命令/路径哨兵验证状态结果的隐私边界，并比较全部合成记录的前后字节摘要。

剩余验证范围：固定 SDK 2.3.0 的模型/schema 生成、异常转换、两版 wire 协议、Windows 最终路径与 worker HANDLE 需要主代理在现成环境重跑；新旧版本安装包一致性由主线另测。本轮不声称网页 host 接入、Linux HMC、桌面/终端动作或真实模型调用通过。

主代理追加的 core CI gate 已作有限核验：`python -S -m unittest discover -s tests -p test_mcp_contract.py -v` 禁用 site 初始化后，31 项运行、29 项通过、两个 Pydantic 模型测试明确 skipped，0 failure/error。代码顶层不导入 SDK/Pydantic，状态与原 receipt 业务测试仍可运行。日志为 `<review-workspace>/mcp-wave5-stdlib-only.log`；这只验证本解释器无 site-packages 的边界，不替代尚未执行的 Python 3.10/3.13 CI jobs。四个项目文件保持前述冻结版本，没有因这次检查改动。
