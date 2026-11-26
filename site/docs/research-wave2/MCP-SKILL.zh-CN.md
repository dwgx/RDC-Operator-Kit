# MCP 与 Skill：接入兼容性研究

研究日期：2026-11-26（Asia/Tokyo）。范围：RDC Operator Kit 第二轮研究。本文为**源码与规范研究，尚未实现或验收 Kit 的 MCP transport**。已有 CLI、RDC 路由和 Skill 的历史测试继续以项目的 [VERIFICATION](../VERIFICATION.zh-CN.md) 为准；不能把本文建议当作执行记录。

## 结论与实现选择

当前最小配套应继续使用已有的 **RDC → Kit CLI → 原生适配器**，并提供同一份可移植 Skill。给本地 Agent 增加 MCP 时，采用固定版本官方 SDK 的可选 stdio 入口，先暴露能力描述和已有回执读取，再单独验收会产生动作的入口。云端调用继续复用已经连接的 RDC，不再建立桌面 HTTP broker 或凭据仓库。这是根据本项目现有状态机与下述传输差异作出的架构判断。

本轮最重要的新事实是：**MCP 已发生协议代际变化**。正式 `2026-07-28` 版本取消旧的连接初始化握手与协议级 session；Tasks 已从 `2025-11-25` 的实验性核心功能迁移为官方扩展。基于旧教程手写一个只处理 `initialize`、`tools/list`、`tools/call` 的服务，会遗漏当前协议契约。[官方变更记录](https://modelcontextprotocol.io/specification/2026-07-28/changelog)

本地 stdio 服务也不能直接作为云端 ChatGPT 的远程 HTTPS endpoint。stdio 的客户端在同一执行环境中启动子进程并连接其标准流；远程 HTTP 则要求一个可达服务。复制 `SKILL.md`、提供 `python server.py` 或写出 `http://127.0.0.1:...`，都没有建立云端到用户电脑的可达链路。这是由传输拓扑推导出的结论；本项目现有 RDC 连接承担了这条链路。[stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) · [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)

## 一、证据等级与覆盖

| 等级 | 本文实际证据 | 不能据此声称 |
|---|---|---|
| 规范原文 | 已读正式 MCP 的 changelog、stdio、HTTP 相关段落、取消、tools、授权相关段落；Tasks 扩展规范与状态表 | 任意 MCP host 都已支持这些特性 |
| 固定源码 | 官方 Python SDK `v2.3.0`，提交 `2118f14f8a19bc158d8a1cf90af58d85d187f849`；OMP `v19.2.1` 的 Skills 文档 | SDK 在这台 Windows 上已安装或测试通过 |
| 当前本地材料 | 已读 Kit 的 AGENTS、README、架构、Skill、pyproject；核对核心与 CLI 文件身份 | 本支线运行过桌面、模型或浏览器动作 |
| 设计推断 | 传输接入方案、回执映射、最小实现切片 | 已经存在可调用的新 MCP server |

检索使用 Exa，五个有区别的查询共请求 25 个结果槽位；随后读取规范和固定文件。结果槽位数不是“完整读过 25 个来源”。核心来源属于五个一手来源家族：MCP core、MCP Tasks、官方 Python SDK、Agent Skills、OMP。具体 URL、读取范围、版本冲突和文件摘要记录在 [MCP-SKILL.sources.json](MCP-SKILL.sources.json)。没有把搜索摘要当成本机执行证明。

## 二、当前 MCP 协议需要怎样处理

### 版本与连接

| 主题 | `2025-11-25` 及更早的相关模式 | 正式 `2026-07-28` | Kit 的处理选择 |
|---|---|---|---|
| 初始化 | `initialize` / `notifications/initialized` | 每请求携带版本、client capabilities；提供 `server/discover` | 交给官方 SDK 做版本兼容 |
| HTTP session | 可使用 `Mcp-Session-Id` | 移除协议级 session | 不把终端 session 寄托于 HTTP 连接身份 |
| 长期通知 | GET stream、原 resource subscription 方式 | `subscriptions/listen` | 首切片不启用订阅 |
| 结果类型 | 旧结果通常没有 discriminator | 结果带 `resultType` | 不自行删减 SDK 结果 envelope |
| 断线恢复 | 旧 HTTP 存在 SSE 恢复机制 | 不再通过 SSE event ID 重投递 | 传输重试与 Kit 动作重试必须分开 |

这张表只列当前实现相关差异，完整协议包含更多改动。stdio 的兼容探测会先尝试 `server/discover`，再按其结果决定是否进入旧握手；不能只对单一错误码写 fallback。[变更记录](https://modelcontextprotocol.io/specification/2026-07-28/changelog) · [stdio 的 Backward Compatibility](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)

### stdout、错误与身份

stdio 的 stdout 必须只包含逐行 JSON-RPC 消息；日志走 stderr。CLI 现在打印供人查看的 JSON，不能直接把这一输出伪装为 MCP transport。MCP 层应调用已存在的业务函数或受控 CLI，并把协议编码、并发和生命周期交给 SDK。[stdio 消息规则](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)

MCP 的协议错误与工具执行错误是两个通道。Kit 的 `failed` 或 `outcome_unknown` 应保留完整业务状态，并通过工具结果的错误语义传递；不能把它改写成正常成功，也不该用协议异常吞掉可恢复的原始回执。工具 annotations 是供客户端判断的提示，不能替代授权、校验或状态锁。[Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

本项目必须保留两个 ID：

| ID | 谁管理 | 含义与恢复规则 |
|---|---|---|
| JSON-RPC request `id` | MCP 客户端/SDK | 一次传输请求的关联标识；新的网络请求可能换 ID |
| Kit `request_id` | 获授权任务调用者 | 同一持久动作意图；绑定相同 payload 与有效 config，恢复时保持原值 |

例如客户端失去一次点击的响应，随后以新的 JSON-RPC ID 重发 `tools/call`，工具参数中的 Kit `request_id` 仍应是原值。现有 `execute_request` 才能返回已存回执或保留未知结果。自动生成一个新的 Kit ID 会绕开已有去重契约，可能再点一次。这是基于本地 `core.py` 的实现分析，不是 MCP 自动保证的 exactly-once。

### 取消不等于动作回滚

在当前 stdio 中，取消用 `notifications/cancelled` 引用在途 request ID；在当前 Streamable HTTP 中，关闭该请求的 SSE 响应流就是取消信号。规范明确存在完成与取消竞争，部分请求无法取消；进度通知也不能无限延长总 deadline。[Cancellation](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/cancellation)

因此，取消 MCP 等待只能表示“不再等待这个调用”，不能证明键盘输入没发生、SmartCLI daemon 已关闭、窗口没有变化，或所有子孙进程退出。Kit 现有意图与回执应继续保存；超时后先核对原请求、原进程和实际产物。未来实现不得为了满足 SDK cancellation 而取消整个用户桌面、RDC 或全局终端服务。

## 三、Tasks 已是稳定扩展，但仍不提供业务验收

官方 `ext-tasks` 仓库将 `2026-07-28` schema 标为 **Stable**，`draft` 标为 **Development**；旧 `2025-11-25` Tasks 文档明确标为 experimental。当前实现应准确称为“正式版本的可选 Tasks 扩展”，不能继续把旧实验性 API 与新 API 混用。[ext-tasks 状态表](https://github.com/modelcontextprotocol/ext-tasks) · [旧实验性版本](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks)

扩展名是 `io.modelcontextprotocol/tasks`。客户端与服务器都要声明支持；服务器才可以将工具调用转成持久任务。当前流程使用 `tasks/get`、`tasks/update`、`tasks/cancel`，不再使用旧的 `tasks/result` 或 `tasks/list`。任务 handle 发出前，服务器必须使该任务可以查询；客户端需要保存 task ID，并尊重 `pollIntervalMs`。[正式 Tasks 规范](https://tasks.extensions.modelcontextprotocol.io/specification/2026-07-28/tasks)

两个容易误读的语义会直接影响 RDC/OMP 包装：

| 返回 | 规范允许的情况 | 对 Kit / OMP 的要求 |
|---|---|---|
| Task `completed` | 最终工具结果仍可 `isError: true` | 继续检查 Kit status、verification 和独立产物；不能按单词 completed 验收 |
| `tasks/cancel` ack | 状态可能暂时仍 working，最终也可能 completed；服务器不保证停止工作 | 保存“取消已请求”和实际终止证据两个事实；不得报告已杀死进程 |

任务 TTL 还允许服务丢弃过期状态。它不是永久审计归档。本项目已有持久 request receipt，以及 OMP 既有 wrapper 的 job/attempt/receipt；未来若映射 Tasks，应适配这些既有身份与证据，不再建一个平行队列。本轮不实现 Tasks，因为尚未核验本次客户端支持，也没有验收 Kit server 在进程重启后的任务存活和取消范围。[Tasks lifecycle](https://tasks.extensions.modelcontextprotocol.io/specification/2026-07-28/tasks) · [官方概述](https://modelcontextprotocol.io/extensions/tasks/overview)

## 四、官方 Python SDK 的固定版本裁决

建议候选依赖为 **`mcp==2.3.0`**，作为可选额外依赖，不加入 Kit 的默认 stdlib 核心。`v2.3.0` 标签直接指向提交 `2118f14f8a19bc158d8a1cf90af58d85d187f849`。[tag 元数据](https://api.github.com/repos/modelcontextprotocol/python-sdk/git/ref/tags/v2.3.0)

| 项目 | 固定版本核验结果 | 限制 |
|---|---|---|
| License | MIT | 复用时保留上游许可；本轮未复制 SDK 实现 |
| Python | 固定 pyproject 与 README 均为 `>=3.10` | 当前滚动文档/默认分支写 `3.11+`，不能拿它改写固定 tag 的要求 |
| Windows | `pywin32>=311` 仅 Windows 安装；CI 配置含 Windows 和 Ubuntu、Python 3.10–3.14 | 读取 CI 配置不等于查到其某次成功运行，更不等于这台机器已通过 |
| 协议代际 | v2 官方说明支持新协议并兼容早期客户端 | Kit 仍须测试实际目标 host 的协商结果 |
| 依赖 | 包含 anyio、httpx2、pydantic、mcp-types、HTTP 与 OAuth 相关依赖 | 装 plain `mcp` 也不等于只安装极小 stdio 组件 |

固定 `pyproject.toml` 还针对 Python 3.14 提高了 anyio 与 starlette 的最低版本；`mcp-types` 与 SDK 同版本。仅钉住顶层 `mcp==2.3.0` 仍不构成所有传递依赖的 lock。发布前应为 Windows 目标 Python 版本保存解析后的依赖与 wheel 校验信息，再在 Linux 复核可移植部分。[固定 pyproject](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/pyproject.toml) · [固定 README](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/README.md) · [固定 CI matrix](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/.github/workflows/shared.yml) · [LICENSE](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/LICENSE)

SDK v2 的示例入口为 `from mcp.server import MCPServer`。旧文档常见的 v1 API 不应未经迁移检查就粘贴进新包；这里没有提供一个未执行却标为可用的完整 server 示例。[官方 v2 说明](https://py.sdk.modelcontextprotocol.io/whats-new/)

## 五、Skill 的可移植部分与宿主差异

Agent Skills 的核心是含 YAML frontmatter 的 `SKILL.md`，`name` 与 `description` 为必需项，可带 scripts、references、assets。`compatibility` 适合写清 Windows/Python/已有 RDC 等前置条件；`allowed-tools` 本身仍为实验性字段，宿主支持不一致。它不能被用来推断某个工具已安装、已连接或已获当前任务授权。[Agent Skills 规范](https://agentskills.io/specification)

OMP `v19.2.1` 的加载器也不是“把任何目录递归扫描就生效”。其常规 providers 与 custom directories 查找一层 `skills/<name>/SKILL.md`；部分 provider 更宽松，标准 Agent Plugins 校验更严格；同名覆盖、来源优先级和 user-level foreign provider 开关都会影响最终发现结果。因此安装流程应报告实际发现的文件路径、版本和名称，不能只凭复制成功给出功能通过。[固定 OMP Skills 文档](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/docs/skills.md)

| 宿主 | 可以复用的包内容 | 接通执行仍需要 |
|---|---|---|
| 当前 ChatGPT 会话 | 已安装的路由 Skill、项目 README 与 request 格式 | 当前宿主真实提供的 RDC/Browser 等工具及已连接设备 |
| Windows 本地 OMP | 同一份 Skill 的标准字段、CLI 调用与证据步骤 | OMP 实际发现 Skill；已有本机权限、解释器与依赖 |
| 其他本地 Agent / MCP host | 标准 Skill 内容；未来可选 stdio server | 该 host 自身的加载与 MCP 配置、版本兼容测试 |
| 远程 MCP 客户端 | 协议 schema 与业务回执设计 | 经过单独部署和授权审查的可达 HTTP 服务 |

ChatGPT 一行所述来源于当前环境可见能力与本地 Skill 契约，没有额外探测账号配置，也没有访问被当前宿主拒绝的 OpenAI 网页。Skill 的路由不会解除 Browser 拒绝；本项目不把 Relay、CDP 或 shell 作为绕过路径。发布说明应把“本地安装”“Skill 被发现”“RDC 可连”“一次具体 workflow 已验收”分成四个可独立核验的事实。

## 六、最小后续实现切片与验收

### 切片 A：当前即可保留的交付

现有 CLI、平台安装器、路由 Skill 与回执格式继续作为主要使用路径。Skill 保留一份可移植正文，详细平台差异放 references；安装器输出绝对解释器路径和配置位置，不自动改全局模型或启动网络服务。新的截图与终端证据工具接入这条已有路线即可，无须先引入 MCP。

### 切片 B：可选的本地 stdio 小入口

建议先实现两个窄工具，名称为设计建议、当前尚不存在：

| 工具 | 输入 | 行为 |
|---|---|---|
| `operator_capabilities` | 空对象 | 返回 Kit/SDK 版本与已配置能力；明确没有进行端到端探测 |
| `operator_receipt` | 校验后的 Kit request ID | 仅从启动参数固定的 state 中读取已有 receipt；不接受任意路径 |

由 `mcp==2.3.0` 处理 framing、版本协商与协议 schema。server 启动时固定本项目 config/state，stderr 写诊断，stdout 只走 SDK；MCP 输入不能覆盖可执行文件前缀或 state 根。能力说明与回执读取不应触发终端启动、桌面截图或模型调用。

决定性验收为：在专用目录启动真实 stdio server；以官方客户端分别请求新协议与受支持旧协议；读一份预先创建的合成 receipt；尝试路径穿越 ID 和非法结构；关闭 stdin 并核对进程退出；让客户端在请求中断后重新连接，确认同一 receipt 没有被改写。检查 stdout 每行都是有效协议消息，退出时不遗留子进程。Windows 路径含空格与 Unicode，Linux 跑同一契约。**这份文档没有执行这些步骤。**

### 切片 C：动作入口，待 B 验收后实施

之后才把明确 allowlist 中的 Kit actions 映射到工具：继续调用 `execute_request`，沿用 request digest、同 state 锁和原始回执；分别声明观察与动作语义。新测试要覆盖“动作已发生但响应丢失”后重连、重复 RPC 但同一 Kit ID、配置变更冲突、取消与结果提交竞争。不能使用 `asyncio.to_thread` 后就声称取消了正在运行的 native action；线程等待结束与外部动作停止是两个问题。

长任务优先引用已有 RDC PID / call ID 或 OMP job receipt。只有目标 host 的 Tasks 扩展支持和现有 job 的持久查询经过实测，才添加 Tasks 映射。不要为此再引入一个队列、daemon、模型 router 或 credentials store。

### HTTP 是独立部署项

Streamable HTTP 需要校验 Origin，本地监听应限定 loopback，并处理实际连接认证。HTTP 授权规范还涉及资源元数据、每请求 token、audience 与发行方绑定；stdio 入口不会自动提供这一层。若以后要公开 endpoint，另做部署、权限和恢复验收；当前 GitHub Pages 是静态文档站，不应承载命令执行入口。[HTTP endpoint 规则](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) · [HTTP Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)

## 尚未验证

本支线未安装 MCP SDK、未写/启动 server、未执行 SDK tests、未连接真实 MCP host、未调用浏览器或桌面、未注册远程 endpoint。上游 CI 只检查了定义，没有把 workflow 文件的存在称为运行成功。未读取或更改账号、token、浏览器 profile 和全局模型配置。后续验证应针对上述具体未决风险，不重复已经成立的基础事实。
