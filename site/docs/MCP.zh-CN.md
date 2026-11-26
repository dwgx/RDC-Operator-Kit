# 可选的只读 MCP stdio 入口

本入口供**能启动本机子进程的 MCP host** 使用。它只描述配置、读取已有 Kit 回执及摘要保存记录，不调用 `doctor`，不执行终端、桌面、浏览器或模型动作。云端 ChatGPT 继续使用已连接的 RDC；一个本地 stdio 命令不会变成云端可达的 HTTPS endpoint。

## 安装与启动

从项目源码目录创建**新的独立 `.venv-mcp` 环境**，只在这个环境安装 MCP extra。主安装器的 `.venv` 继续服务 SmartCLI：固定 SmartCLI `0.3.5` 要求 `mcp>=1.0,<2`，本入口要求 `mcp==2.3.0`，两者不能装在同一环境，也不要安装 `.[terminal,mcp]`。下面的命令遇到已有 `.venv-mcp` 会拒绝，不删除或覆盖旧环境；需要另一个环境时，由操作者选择一个新的目录名。[SmartCLI 固定依赖声明](https://github.com/dwgx/SmartCLI/blob/24da9834686e4df7625a0096cb281567c4824042/pyproject.toml)

Windows PowerShell，Python 3.10+：

```powershell
& {
    $ErrorActionPreference = 'Stop'
    if ($null -ne (Get-Item -LiteralPath '.venv-mcp' -Force -ErrorAction SilentlyContinue)) {
        throw '.venv-mcp already exists; select a new environment directory.'
    }
    py -3 -m venv .venv-mcp
    if ($LASTEXITCODE -ne 0) { throw 'MCP environment creation failed.' }
    & .\.venv-mcp\Scripts\python.exe -m pip install ".[mcp]"
    if ($LASTEXITCODE -ne 0) { throw 'MCP dependency installation failed.' }
}
```

Linux，Python 3.10+：

```bash
bash <<'SH'
set -eu
if [ -e .venv-mcp ] || [ -L .venv-mcp ]; then
    printf '%s\n' '.venv-mcp already exists; select a new environment directory.' >&2
    exit 1
fi
python3 -m venv .venv-mcp
.venv-mcp/bin/python -m pip install '.[mcp]'
SH
```

MCP host 应启动专用环境中的解释器，并连接它的 stdin/stdout。等价的启动命令是：

```powershell
.\.venv-mcp\Scripts\python.exe -m rdc_operator.mcp_server --config config.local.json --state .rdc-state
```

Linux 对应解释器为 `.venv-mcp/bin/python`。在普通终端手动启动后等待协议输入属于正常行为。宿主配置使用解释器的绝对路径，参数分别传入 `-m`、`rdc_operator.mcp_server`、`--config`、配置绝对路径、`--state`、state 绝对路径，不把整条命令拼成一个 shell 字符串。不同宿主的配置文件格式由各自文档决定。主 CLI 与只读 MCP 可以由操作者明确指向同一份配置和 state；它们不共享 Python 依赖环境。

依赖严格要求官方 **`mcp==2.3.0`**；缺失或版本不符时，只向 stderr 输出明确错误并以 2 退出。入口不升级全局环境。顶层 SDK 版本固定不等于所有传递依赖都已锁定；实测 summary 记录当次依赖版本。固定 SDK 的 Python 要求是 `>=3.10`，Windows 依赖包含 `pywin32>=311`。[固定上游 pyproject](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/pyproject.toml)

配置和 state 是操作者提供的可信启动参数。工具请求不能替换它们；入口没有 HTTP transport 选项，也不会建立网络 listener。

## 三个只读工具

| 工具 | 参数 | 返回与限制 |
|---|---|---|
| `operator_capabilities` | `{}` | Kit/SDK 版本、三个工具的名称、terminal/desktop/OMP preview 是否具有相应配置形状；不检查文件存在、不启动程序、不探测可用性 |
| `operator_receipt` | `{"request_id":"example-001"}` | 固定 state 的 `requests/<ID>.receipt.json`；保留原始 receipt 与 status，不重放任何动作、不刷新时间、不核验当前桌面 |
| `operator_request_status` | `{"request_id":"example-001"}` | 摘要该 ID 的 intent/receipt 保存记录；不返回原参数、命令、路径、动作名称或内容，不查询进程、取消或重试动作 |

`operator_capabilities` 不返回 argv、可执行文件位置、allowed roots、wrapper 路径或配置中其他值。`operator_receipt` 则会返回请求对应的已存原始回执，其中可能包含原任务的本地路径或输出；它是授权范围内的私有证据读取，不是自动脱敏导出。

工具结果成功表示“这次读取或配置描述成功”。例如读取一份 `status: outcome_unknown` 的回执，MCP 读取调用可以成功，而原操作仍保持未知。返回同时明确 `live_verification_performed: false`、`receipt_authenticity_verified: false`；它不是签名验证，也不证明原业务成功。找不到、格式错误或越界输入会以 SDK `CallToolResult` 的 `isError` 返回简短错误，不附带任意文件内容。

### 机器可读输出契约

三个工具都在 `tools/list` 公布 object 根的 `outputSchema`，包括必填字段、状态枚举与固定的 false 标志。顶层不接受未声明字段；`operator_receipt.receipt` 公开最低限度的 schema/version/request ID/status 形状，并允许原始回执中的其他字段，保持既有回执读取内容不变。JSON 文本与 `structuredContent` 同时返回，兼容需要文本内容的客户端。[MCP Tools 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

实现使用固定 SDK 支持的 `Annotated[CallToolResult, OutputModel]`，实际验证成功结果；没有仅向工具目录手工写入 schema。SDK 与 Pydantic 仍在构建 MCP server 时懒加载，不增加基础 CLI 的安装依赖。错误结果保留 `isError: true` 与稳定的 `error.code`，不套成功结果的 schema。[官方结构化输出说明](https://py.sdk.modelcontextprotocol.io/v2/servers/structured-output/) · [固定 SDK 的验证分支](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/mcpserver/utilities/func_metadata.py)

这些 schema 有助于客户端验证结构；工具 annotations、schema 和记录内容都不能授予操作权限或证明来源可信。`operator_receipt` 仍可能包含私有原始内容；需要最小摘要时用状态工具。

### 保存记录状态

`operator_request_status` 对同一个 ID 做两轮有界读取，比较打开文件的身份、尺寸、时间与字节摘要。跨 intent/receipt 的观察不是原子快照，所以始终返回 `snapshot_atomic: false`。

| `record_state` | 本次观察到的记录 | 含义与限制 |
|---|---|---|
| `no_records_observed` | 两轮都没有读到 intent/receipt | 仅描述指定 state 的观察，不证明外部动作从未发生 |
| `intent_without_receipt` | 两轮均为合法 prepared intent、没有 receipt | 动作可能未开始、已经发生或被中断；不声称 running，也不许可换 ID 重试 |
| `receipt_recorded` | 两轮均为 ID 相符、digest 一致的 intent/receipt | `saved_receipt_status` 保留 observed/completed/failed/outcome_unknown；不是独立业务验收 |
| `inconclusive` | 记录变化、receipt 缺少 intent、摘要不一致或 receipt 缺少合法摘要 | `saved_receipt_status: null`；按 `reason` 核对原证据，不执行恢复动作 |

`reason` 是固定枚举：`no_records_observed`、`receipt_not_observed`、`matching_saved_records`、`records_changed_during_observation`、`receipt_without_intent`、`record_digest_mismatch`。未知状态不会被转换为 `running`、`cancelled`、`retryable` 或成功许可。状态工具不列举其他 request ID。

合法 intent 至少需要整数 `schema_version: 1`、相同 request ID、`state: prepared` 与 64 位小写十六进制 digest。不可读/变化中的单个文件、链接、超限文件、非法 JSON 或错误身份会返回简短 `isError`，例如 `invalid_intent`、`intent_changed`、`receipt_unreadable`；不会把错误内容反射成结果。只有 `*_not_found` 被状态工具当作本轮未读到该记录。

状态结果还固定 `live_verification_performed: false`、`record_authenticity_verified: false`、`actions_exposed: false`。即使两轮内容相同，观察后文件仍可能变化；文件指纹并非签名、全局锁或实时进程见证。

### 两种 request ID

**JSON-RPC envelope 的 `id`** 由 MCP client/SDK 用于关联一次协议请求与响应；**receipt/status 工具参数里的 `request_id`** 是 Kit 业务请求的持久标识，用来选择固定 state 下的记录。它们不是同一个字段，也不要求值相等。例如两个不同 JSON-RPC 请求可以重复读取 `{"request_id":"inspect-001"}`；两次读取仍指向同一 Kit 业务请求，不会创建新请求或重放动作。MCP 消息的 envelope 与协议 ID 处理交给官方 SDK；本入口只校验 Kit ID 的文件选择契约。

## 路径与数据边界

请求 ID 沿用 Kit 的 ASCII 字母、数字、下划线和短横线格式，最长 64 字符，拒绝 Windows 保留设备名。没有文件路径参数；多余参数也会被拒绝。固定 SDK 2.3.0 的普通函数参数模型默认忽略额外字段，因此这里通过其 middleware 明确执行精确字段契约，并在 `tools/list` 标注 `additionalProperties: false`。[固定 SDK middleware 契约](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/context.py)

读取拒绝 symlink、Windows reparse point 和多重 hard link；POSIX 按 directory descriptor 逐级打开且不跟随链接，Windows 在读取前核对已打开 HANDLE 的最终路径。intent 和 receipt 均只接受普通文件、每个最多 8 MiB；检查读取期间的文件身份/尺寸/修改时间/ctime 变化，并拒绝非法 JSON、重复键、非有限数及错误的 request ID/status。状态工具最多读取两轮、每轮两个固定记录；不无限重试竞态。读取不会创建 state、锁文件或回执。

这些措施限定本入口可读取的路径和内容类型；它不把同一用户下的文件系统变成安全沙箱，也不阻止其他程序更改可信配置或源代码。状态文件采用原子替换时，一次打开的文件可能是替换前的完整旧回执；本接口只称其为已存快照，不保证它是外部业务的最新状态。

## 真实 stdio 验证方法

无需 MCP SDK 的业务契约测试；若环境已有 Pydantic 2，还会运行两个真实输出模型测试，只有 SDK 注册器为 stub，不能当作真实协议测试：

```bash
python -m unittest discover -s tests -p test_mcp_contract.py -v
```

安装精确 SDK 的环境中运行真实进程 smoke；输出目录必须尚不存在：

```powershell
.\.venv-mcp\Scripts\python.exe scripts\smoke_mcp.py --output-dir evidence\mcp-live-unique
```

Linux 对应 `.venv-mcp/bin/python scripts/smoke_mcp.py --output-dir evidence/mcp-live-unique`。

脚本会创建专属的 `fixture 中文 space` 路径、无效可执行文件哨兵配置和合成 intent/receipt。使用官方 `StdioServerParameters`、`stdio_client`、`ClientSession` 开独占子进程；默认分别以 `discover()` 与 `initialize()` 建两个会话。报告记录**实际协商版本**，不能从两个通过结果推断所有 MCP 版本都已通过。

验收覆盖：工具列表恰好三个、只读 annotations、精确输入与成功输出 schema、JSON 文本/结构化内容一致、配置脱敏、不运行探测、读取内容一致、未知状态保留、路径型 ID 拒绝、state 覆盖参数拒绝、缺失回执、无记录/只有 intent/匹配 receipt/孤立 receipt/摘要不符的状态摘要及原记录字节不变。intent 和不被原文读取的 receipt 放入私有内容哨兵，检查摘要不会透出它们。

专属 fixture launcher 只对 `fixture-schema-invalid` 这一合成状态查询注入一次错误成功结果：把必须为 JSON `false` 的 `snapshot_atomic` 改成数字 `0`。真实 SDK 必须返回 `isError`；如果 schema 只出现在列表、没有执行服务端输出校验，此反例会使 smoke 失败。注入逻辑只存在于本次创建的测试 launcher，生产入口没有这个分支。summary 明确记录该故障注入，不把它当成真实请求记录。

测试保持真实 `sys.executable` venv 启动路线；每个会话使用新的 nonce，fixture launcher 在进入服务前写 ready 见证，服务正常返回后再写 return 见证。

进程身份验证分为以下两种路线：

| 平台与路线 | 协议活跃时 | stdin 关闭后 |
|---|---|---|
| 非 Windows 直接子进程 | ready 的 nonce、PID、PPID 分别绑定本次启动、SDK 持有 PID、当前测试进程 PID | SDK 持有 process 退出 0；return 的 nonce/PID/PPID 与已核验 ready 一致，并明确服务正常返回 0 |
| Windows，直接进程或 venv redirector | 对 SDK 持有进程和实际 worker 用只读 OS 查询取得 PPID、执行文件和创建时间；若是两层，worker 的 OS parent 必须等于 SDK 持有 PID；worker image 必须等于当前解释器的 `sys._base_executable` | SDK 持有 process 退出 0；return 见证与已核验 worker/nonce 一致；协议活跃时保存的 worker HANDLE 已 signaled，且该同一内核对象退出 0 |

Windows 只申请 `PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE`；Toolhelp snapshot 只取匹配 PID 的父进程字段并立即关闭。执行文件与创建时间来自同一个已打开 HANDLE，进程存活查询包围身份读取，创建时间必须落在本次启动的 FILETIME 区间内，且 worker 不早于启动器。FILETIME 是系统墙钟，发生不符合区间的时钟变化时验证失败，不声称它是单调时间。代码不会依据 witness 中的 PID 终止进程，也没有为这些额外查询句柄申请终止权限；失败清理由官方 SDK 管理它自己启动的进程。[PROCESSENTRY32W](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-processentry32w)、[OpenProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess)、[GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes)

smoke 的两个观察 hook 绑定固定 SDK 的真实创建函数和解析器，不替代传输/进程执行。报告里的 stdout 证据是**SDK parser 实际消费的行**，不包含 SDK 在关闭时可能丢弃的 drain 字节。服务自身的运行日志/错误走 stderr；业务协议交给 SDK 编码。[固定 stdio 实现](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/client/stdio.py)

此 smoke 明确把当前项目源码目录加入模块搜索路径，验收的是 **source tree**。summary 分别记录 `kit_source_version`、`kit_module_file`、源文件 SHA-256 和 `kit_distribution_version`；后者来自已安装或当前目录可发现的 distribution 元数据，旧 egg-info 可能与执行中的源码版本不同。`installed_package_validation: false` 明确说明这不是安装包版本验收；安装后应另行核对安装环境和包版本。

## Wave 05 契约与真实协议验证

2026-11-26（Asia/Tokyo）。初次定向测试 31 项通过；独立 review 随后发现 smoke 使用 Python 字典等值会混淆 `false` 与 `0`，且没有对全部成功结果核对文本通道。当前服务端从同一 payload 生成两个通道，本次未发现生产泄露；这是验收机制的假阳性缺口。

修复后增加类型敏感 JSON 比较、严格解析与唯一 TextContent 检查，capabilities、receipt 及五个状态结果全部比对两通道。receipt 还与原 fixture 按类型比较。新增四条具体反例，定向测试 **35 项通过**。独立合成 transport 的 12 个场景得到预期 verdict：两个正常控制通过、十个错误变异失败。这些不是 wire 测试。

在已有 Windows 11 / Python 3.14.7 / SDK 2.3.0 环境执行修复后的真实 stdio：modern `discover` 协商 `2026-07-28`、legacy `initialize` 协商 `2025-11-25`，**每会话 36 项检查通过，共 72 项**。包含三工具、严格输入、可发现输出 schema、SDK 拒绝故意注入的错误成功输出、跨通道匹配、状态脱敏与记录字节不变。SDK 持有进程及预先持有的 worker HANDLE 正常退出 0。

这份报告执行 `source_tree`，source version 为 a5，运行时安装 distribution 仍为 a4，`installed_package_validation: false`。它不冒充安装包验收，也不证明所有第三方 host 或云端 ChatGPT endpoint 可用。后续安装、CI 与发布记录见 [第五轮报告](REVIEW-WAVE5.zh-CN.md)。初次两会话各 30 项的原记录保留，不把两轮检查数相加成新测试数。

容器全局 MCP 仍为 1.29.0，未被替换；本地 core/模型测试与 Windows 真实 SDK 证据分别记录。[独立 MCP review](research-wave5/REVIEW-MCP.zh-CN.md) 保留原反例及修复闭环，[研究范围](research-wave5/RESEARCH-MCP.zh-CN.md) 说明官方规范、固定源码、Firecrawl 与 Scite 的实际阅读范围。

## a2 历史执行记录

2026-11-26，Linux / Python 3.12.14，独立测试环境安装官方 SDK 2.3.0，未修改全局既有 SDK。

| 验证 | 结果 |
|---|---|
| 无 SDK 依赖的契约与身份测试 | 20 项通过；其中 13 项覆盖读取、脱敏、参数越界、链接、非普通文件和缺失依赖，7 项覆盖进程身份、nonce、父链、执行文件、创建时间和正常返回的拒绝条件；Windows 身份单测使用合成 OS 记录，不等于 Win32 live 验收 |
| 第一次真实 stdio | 两个协议均完成协商和工具列举，但“输入 schema 禁止额外字段”检查失败；保留 `evidence/mcp-linux-20261126-01/summary.json` |
| 修复 | live SDK middleware 返回字典；同时处理字典与 typed result，使 schema 标注和参数拒绝一致 |
| schema 修复后真实 stdio | `2026-07-28` 与 `2025-11-25` 两个独立会话各 15 项检查通过，原 receipt 未变；两个直接子进程均正常返回并退出 0。保留 `evidence/mcp-linux-20261126-03/summary.json` |
| 主线首次 Windows stdio | 主线回报两个协议的工具契约均通过、SDK 持有 process 均退出 0；旧 smoke 的 return witness PID 等于 SDK PID 假设被 venv redirector 反例推翻。原失败证据保留于 Windows `evidence/wave2-20261126/mcp-windows-01`；这次失败不能改写成通过 |
| 进程身份修复后的 Linux stdio | 真实 venv 解释器、官方 SDK 2.3.0；`2026-07-28` 与 `2025-11-25` 两个独立会话各 18 项检查通过，含新的 ready/nonce/direct-child 身份验证；原 receipt 未变，两个 SDK 直接子进程正常返回并退出 0。见 `evidence/mcp-linux-20261126-04/summary.json` |
| Windows 修复后 stdio | 主线在 Windows 11 / Python 3.14.7 的独立 MCP 2.3.0 venv 真实执行；两协议各 19 项检查通过，分别 1,170.971 / 1,146.513 ms。OS 查询确认两次均为 venv redirector 父子链；SDK parent exit 0、预先持有的 worker HANDLE signaled/exit 0、同 nonce 正常 return 与原 receipt 未变全部通过。证据为 Windows `evidence/wave2-20261126/mcp-windows-02/summary.json`；主线读取副本 `evidence/wave2-20261126/mcp-windows-fixed.json` |
| Windows 最终安装环境 | 新建项目 `.venv-mcp`，安装 `.[mcp]` 后再验两协议，各 19 项通过，分别 1,226.498 / 1,212.332 ms。另用隔离导入 `-I` 核对实际 site-packages 的版本为 0.1.0a2，10 个模块摘要全部与源码一致，pip check 无冲突；主 `.venv` 仍为 SmartCLI 0.3.5 / MCP 1.30.0。协议 smoke 保持源码入口，安装包字节核对是单独证据，见 `evidence/wave2-20261126/release-validation.json` |
| 其他 host | 尚未对具体第三方桌面 host 或 ChatGPT 云端远程 endpoint 验收；上述测试是官方 SDK 的本地 stdio client/server |

早期协议研究快照在 [MCP-SKILL](research-wave2/MCP-SKILL.zh-CN.md)；本文记录该研究之后落地的有限只读切片。本入口没有实现 Tasks 扩展、图像订阅、远程 endpoint、动作工具、跨机器配对或凭据管理。需要动作时仍走已有 RDC/CLI 路由和原请求回执契约。
