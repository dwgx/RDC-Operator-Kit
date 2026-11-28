# 架构与可靠性边界

本文对应 `0.1.0a5`（2026-11-26，Asia/Tokyo）。执行入口仍是 [`core.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/core.py)、[`common.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/common.py)、[`adapters.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/adapters.py) 和 [`omp.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/omp.py)；截图文件证据在 [`frames.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/frames.py)。a4 加入 [`windows.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/windows.py) 只读诊断与 [`smoke_windows.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/scripts/smoke_windows.py) 串行验收；a5 扩展 [`mcp_server.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/mcp_server.py) 的只读记录契约，并加强 Linux 安装与 liveness 报告。本文说明当前实现，本轮实际覆盖见 [第五轮报告](REVIEW-WAVE5.zh-CN.md)，历史 Windows 证据见 [第四轮报告](REVIEW-WAVE4.zh-CN.md)。

## a6 增量：检查点与只读恢复

2026-11-28 的增量以 [恢复规格](RESUME-SPEC.zh-CN.md) 为契约；使用步骤见
[Agent 指南](AGENT-GUIDE.zh-CN.md)。以下 a5 章节保留已有执行器和 MCP 的说明，
不能把 a5 通过记录当成 a6 新功能验收。

`recovery.py` 在原 state 内保存任务 marker 与有版本号的 checkpoint。保存使用现有
state lock，更新要求 expected revision。scope/config/path/marker 保持绑定，原请求
ID 不能被新检查点静默丢弃；hard stop 不能因换 route 消除。

`resume` 不创建 state、不持有跨任务执行锁、不调用适配器；它前后核对 marker 和
checkpoint，并通过现有安全读取器观察原请求记录。双重采样仍非原子快照。
只读计划明确区分 caller-attested route、逻辑 state 连续性、未验证的物理身份与
未独立验证的 request-config 关联，不输出执行许可。

route change 与同 ID 的 user_reconnected 都使新检查点进入新代次。历史 handle
保留来源，视觉观察必须重新建立；这是一项恢复工作规程，并未给旧版 `call`
或宿主其他工具增加全局拦截器。任务的冻结原文和原请求文件仍须由 Agent 保留。

## 控制路径

| 层 | 职责 | 本项目不替代的部分 |
|---|---|---|
| 宿主 Agent / Skill | 确认任务范围、选择工具、读取证据并验收 | 用户授权、宿主工具策略 |
| RDC | 已连接设备的文件与进程传输 | RDC 配对、账号与托管服务 |
| Kit CLI | 参数检查、state 锁、intent / receipt、适配器调用 | OS 沙箱、统一 daemon 或模型 broker |
| 只读 MCP stdio | 静态配置描述、单个保存回执及最小记录摘要；可发现的输出 schema | 动作执行、实时任务状态、远程 endpoint 或宿主自动接入 |
| Windows 只读诊断 | 采集 token、session、desktop 与 foreground，保守分类 | 权限授予、UAC 确诊、动作执行保证 |
| SmartCLI | 持久终端与屏幕状态 | 任意应用的业务完成判断 |
| Microsoft winapp | Windows UIA、目标操作与窗口捕获 | 所有应用的一致可自动化程度 |
| 官方 Browser 插件 | 已连接浏览器中的受支持网页操作 | 不能通过桌面、CDP 或 shell 绕过的宿主拒绝 |
| 既有 origin-dispatch | OMP preview 的本地执行及其原始回执 | 新队列、真实模型任务的授权 |

Kit 不监听网络端口。RDC 直接启动 CLI，因此无需额外的 localhost HTTP 身份验证层或公网暴露服务。以后若引入新 transport，必须单独审查其权限和失败语义，不能把当前 CLI 测试当成网络服务验收。

## 请求身份与有效配置

请求的三个字段是 `request_id`、`action`、`args`。执行器将请求与实际传入的整个配置对象进行规范化 JSON 序列化，然后计算 SHA-256。对象 key 顺序不影响摘要；配置值、可执行文件前缀、允许路径和 TTL 的变化会改变摘要。这里的摘要绑定所用配置，不是秘密签名，也不证明当前文件系统中的二进制未被更换。

同一 state 中的请求 ID 只表达一次特定意图：

| 已有记录 | 行为 |
|---|---|
| 无 intent / receipt | 验证输入和 `--apply`，先写 intent，再调用适配器 |
| intent 与 receipt 完整，摘要一致 | 返回原 receipt，`replayed: true`，不再执行，也不刷新观察 |
| 同 ID、摘要不同 | `request_conflict` |
| intent 存在，receipt 缺失或不可读 | `outcome_unknown`，禁止自动重放 |
| receipt 孤立、损坏或与 intent 不符 | 不确定结果，保留原记录 |

一次终端输入或点击可能已经发生，但进程在写 receipt 前中断。因此本项目保证的是“对保存了意图的同一请求，不因响应丢失而盲目再执行”，没有宣称 exactly-once。不要删 intent、重写 receipt 或换一个 ID 来伪装重试。新 ID 表达新的动作，仍须先核对现状及授权。

## 状态、存储与进程

最终 receipt 的状态是 `observed`、`completed`、`failed` 或 `outcome_unknown`。`completed` 需要结合 `result.verification` 解读：输入被上游接受、目标控件值已核对和业务目标完成，是不同证据。

intent 和 receipt 使用临时文件、文件 flush/fsync 和原子替换写入；Unix 还同步父目录。Windows 没有使用同样的目录 fsync 路径。此实现处理进程中断和写入失败，不提供针对所有硬件、文件系统或断电场景的持久性证明。

每个规范化 state 目录有一个 OS 文件锁，覆盖准备、适配器执行和结果提交。竞争调用得到 `busy`。这只协调共享该 state 的 Kit 调用者；另一 state、其他软件和人的输入仍可改变桌面。

子命令通过 `shell=False` 的 argv 启动。输出使用临时文件并限制返回尺寸，超时或中断时只清理本次持有句柄的直接子进程。输出阈值按间隔观察，不能当成严格磁盘配额；直接子进程清理也不等于终止所有 daemon、后台工作或任意子孙进程。

## 终端归属与退出

逻辑 session 对应 Kit 生成的唯一 SmartCLI session ID；归属文件记录创建路线。既有他人会话不会被自动采用，标识不复用。命令字符串仍是获授权的本机程序执行，`allowed_roots` 不限制子程序能访问的所有资源。

SmartCLI 的屏幕状态和存活信号分别读取。等待超时、只有 echo 的输入、程序仍未 ready、snapshot 不完整，都不能被描述为任务完成。

固定 liveness 探针只创建自己的合成管道子进程，不采用任意 PID。a5 的编排在开始前、每 case 前后与最终状态持续调用 `atomic_json` 保存计划、当前项、已完成结果、错误和中断标志。case 未返回时，`cleanup_verified` 保持 null；启动失败、checkpoint 失败或中断后不启动下一项。它没有更改既有 `OwnedFixture` 的所有权边界。

正常通过退出 0；功能／启动失败退出 1；中断退出 130；非中断归档失败退出 3。stdout 的 `summary_current` 表示最后报告是否已成功保存。最终 PASS 替换之后若发生异常，会进行一次有界的保守 FAIL 写回；如果存储持续失败，旧 PASS 文件可能残留，但 stdout 保持 FAIL、非零退出及 `summary_current: false`。消费者必须综合本次返回与文件，不得用旧 summary 单独推导成功。这不是对强杀、永久不可写或所有存储硬件的持久性保证。

固定的 SmartCLI `0.3.5` CLI 隐藏了 daemon 的完整 close 结果。Kit 发出关闭后保留归属，并返回 `outcome_unknown` / `close_receipt_not_exposed`。真实 smoke 使用独立文件与 Windows 进程句柄核对测试程序退出，这种额外见证不会改变通用 close 接口的有限保证。

## Windows 桌面目标

observe 记录 HWND、PID、进程创建时间、可执行文件身份、UI 树、selector 与时间。mutation 必须使用短效 observation，操作前在同一窗口内重新绑定实际元素。上游 inspect 可能返回 AutomationId，而动作确认使用 canonical selector；适配器显式绑定这两者，并核对 canonical elementId、HWND 和动作字段。

`invoke` 明确请求 InvokePattern，避免上游自动选择另一操作或祖先。`set_value` 在操作后 get-value 核对内容。`click` 只接收观察到的 selector，不提供无目标坐标接口。操作后再次读取界面，失败时保留未知结果。

### 显式聚焦与目标层级

`desktop.focus` 是独立 mutation，沿用 request/config 身份、state 锁、先写 intent 与 `--apply` 契约。参数只包含 fresh `observation_id`。适配器首先核对 observation 的 winapp 路线与 kernel identity，再要求 `GetAncestor(HWND, GA_ROOT) == HWND`；不符合则在上游调用前返回 `top_level_target_required`。窗口被同进程重新挂为子窗口时，即使 HWND、PID 和创建时间没变，也不能让 winapp 改为激活未观察的父窗口。

正常路径只调用一次 `winapp ui focus -w HWND`。回执必须指向该窗口且为 window-only acknowledgement；随后重新观察、读取 foreground，并再次核对身份。只有新观察有效且精确 HWND 占据前台，才返回 `completed` / `focus_effect_verified: true`。这仍保留 `application_effect_verified: false`，因为聚焦并非应用业务动作。

上游 focus 可能先恢复最小化窗口再失败，因此调用后失败、无效 ACK 或后验无法确认均保持 `outcome_unknown`，不自动重发。同一 request ID 只读原回执；后续获准点击使用 focus 返回的新 observation 和其真实 selector。点击本身不负责强制聚焦，不绕开上游 foreground 检查。层级、身份与焦点检查之间仍存在竞态，不能宣称冻结了共享桌面。

这些检查缩小误操作窗口，不能冻结外部应用，也不能阻止其他人抢焦点。上游确认可能早于业务效果完成，模型仍须通过控件状态、文件或其他独立见证验收。

截图的 `observation_id` 可绑定已有短效目标；适配器在调用 winapp 前核对 observation、可执行路线及 kernel identity，采样器为全部帧携带同一 ID。未提供 observation 的单次捕获只能绑定调用时所观察到的 HWND；调用者仍须先确认它是本次授权窗口。

winapp 的 `screenshot -w` 可能将 owned dialog 合成为多窗图。`frames.py` 核对返回的 HWND、PID、文件路径、尺寸和单窗结构，拒收非 null 的 `windows`、element/coordinate/remote-target 结果；已经生成的原始图片不会因拒收被删除。捕获后拒收不能撤销捕获或焦点副作用。

Frame ID 标识一次被记录的文件产物；SHA-256 标识字节，调用起止与 monotonic 耗时标识命令区间。`captured_at=null`、`backend=not_reported` 和 `pixel_freshness=unproven` 保留实际缺失信息。回放旧 receipt 保留旧 frame ID、hash 和时间。这里只验证 PNG 头，不提供完整解码或像素语义证明。

有限采样器会逐帧落盘并输出 JSON。目标改变、composite 或不确定捕获会使它停止；observation TTL 过期会写 failed manifest 并退出。它没有新增常驻录像服务、任意截图目标或网络监听器。

## Windows 只读诊断与权限分层

`windows-preflight` 在 CLI 读取 config 或创建 state 之前处理。`windows.py` 将原生采集与纯逻辑 assessment 分开；原生层仅请求查询所需的 process/token/desktop 权限，按归属关闭自己打开的句柄，不关闭借用的 thread-desktop/window-station 句柄，不发送输入、不改变前台、不切换 desktop，也不申请提升。

报告记录 collector、可选 exact HWND 的目标、window station、thread/input desktop、前后 foreground、各查询错误和非原子快照标志。它不读取目标标题、页面文字或凭据。目标不存在或查询失败时不选择另一个窗口；较高目标 integrity、跨 session、desktop 冲突或非目标前台会形成具体风险。

assessment 与动作 receipt 是不同契约：`observed` 表示本次列出的检查没发现冲突；`blocked` 表示已经观察到不匹配；`unknown` 表示必要事实缺失或采样不稳定；`unsupported` 表示非 Windows。仅 `observed` 的 CLI 退出码为 0，其余为 1，非法参数为 2。普通桌面中不提供目标会加入 `target_not_provided`，通常得到 `unknown`；已有 blocked 风险优先。所有结果都保留 `input_performed: false`、`permission_granted: false` 和 `uac_state: not_determined`。

探针没有查询 session 的连接状态，也不能单凭 foreground 为零或 desktop 查询失败确定 UAC。`OpenInputDesktop` 成功同样不证明用户当前可见并可接管该会话。探针不会给适配器颁发长期可用的通行证，后续动作仍按自己的目标契约重新核对。[Microsoft API 说明](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop)

架构区分普通交互应用、已提升应用和 UAC 安全桌面。普通输入受真实 token/session/desktop 条件影响；已提升目标需要核实完整性级别及具体操作授权；安全桌面的系统确认由用户处理。本版不安装 elevated broker，不调整 UAC/desktop 策略，也不将 UIAccess 当作无限权限。需要提升时先给出具体程序、动作和原因，用户完成正常确认后再建立新观察。[UAC 原理](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/how-it-works) · [UIAccess 安全要求](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)

## 有界 Windows 验收编排

`smoke_windows.py` 的九个顶层 case 固定串行为 `core → doctor → liveness → terminal → mcp → browser_offline → omp_preview → desktop → observation`。各既有脚本保留自己的 state 与 witness，总 runner 引用子报告；它没有新增跨应用锁，也不允许另建 state 来绕开已有 `busy`。

解释器依赖分开传入：`--python` 是实际基础 CPython，`--terminal-python` 对应 SmartCLI distribution，`--mcp-python` 对应独立 SDK 环境；GUI 用调用者提供的实际绝对 `pwsh.exe`。输出目录必须新建，链接路径拒绝。MCP 未配置时记录 skipped，不静默安装或合并环境。OMP case 只核对 `DRY_RUN` 和 `real_model_call: false`；浏览器 case 只验证离线样例，保留 `live_browser_execution: false`。

runner 在 case 开始、子进程启动、结束与清理后原子保存总报告。命令日志和失败子报告引用继续保留，之后成功的 case 不覆盖较早的失败。整体使用 monotonic deadline，为收尾预留预算；到期或不确定清理后不启动后续 case。这个预算约束可等待的命令，不是原生 OS 调用或磁盘写入的硬实时上限。

GUI fixture 的 witness PID 必须等于本次持有的 `Popen.pid`，同时满足新 witness、exact HWND、kernel PID/创建时间/可执行文件、固定 fixture 标题及初始状态检查。redirector 的 PID 不一致会失败，不从 witness 中接管另一个进程。清理先重新核对同一 HWND 身份，再发正常 `WM_CLOSE`；必要时只处理本次持有的直接子进程，不按名称或事后发现的 PID 扫杀。

正常关闭的验收同时要求进程退出码 0、独立 witness 为 closed，以及没有强制终止或中断。关闭等待期间收到 `KeyboardInterrupt` 也保留 cleanup 记录并收尾，不能因中断省略已持有进程的处理。强制清理标明 `possible_descendants: unknown`，使整体失败并停止后续工作，不声称子孙进程已全部退出。

顶层全部 passed 才退出 0；失败或不确定结果退出 1；只有跳过/未执行等不完整覆盖则退出 2。核心回归自身的 skipped 数量另列，不能从顶层 case 的 passed 推导所有平台路径都运行过。总报告明确 `source_execution: true` 与 `installed_package_validation: false`；已安装包版本、真实 Edge 交互及真实模型任务分别验收。具体命令见 [Windows 操控指南](WINDOWS-CONTROL.zh-CN.md#4-一次有界-windows-验收)。

## 浏览器与 OMP

浏览器工作通过当前宿主的官方 Browser 插件完成。Kit 会拒绝已知浏览器进程作为桌面目标，但进程名列表不是完整的 OS 安全边界；调用者始终有责任遵守网页操作的授权与宿主策略。Browser 不可用或因策略拒绝时，报告具体限制，不转用 RDC、CDP 或模拟键鼠绕开。

第四轮的官方 Edge localhost 交互与 Kit 的 `browser_offline` 是两份不同证据。前者检查实际语义点击、截图定位点击、延迟效果及页面 reset/reload；后者仅检查已有证据包内部一致性。已拒绝的 ChatGPT origin 没有被重新尝试或转给 OMP Relay，扩展站点权限也不改变这项宿主边界。

a4 首页后续导航遭 `ERR_BLOCKED_BY_CLIENT` 与自动审批拒绝后，该 localhost origin 的操作已停止。a5 首页与 Lab 的视觉更新只完成静态／合成事件核对，未通过其他渲染器补做被拒绝的浏览器验证。首页搜索仅在本页公开卡片文本中工作，不发送网络请求或保存查询；Lab 业务脚本保留 a4 字节，但新布局需要自己的实际验证，不能复用旧坐标证明新页面。

OMP 适配器目前仅支持 `omp.preview`，调用已配置的 `origin-dispatch` 和 `--dry-run`，验证原生 `DRY_RUN` 回执。它不修改模型路由、不保存凭据、不证明真实模型运行质量。真实任务继续使用既有 dispatcher 契约。

## 只读 MCP 输出与记录摘要

服务使用官方 SDK 2.3.0 的 stdio transport，并在启动时固定可信 config/state。SmartCLI 0.3.5 的 MCP 1.x 依赖放在另一个环境；不通过合并可选 extra 消解冲突。SDK/Pydantic 在 `build_server` 内懒加载，基础 CLI 和不依赖模型的契约检查仍可只使用标准库。安装及精确参数见 [MCP 指南](MCP.zh-CN.md)。

`operator_capabilities` 仅描述静态配置形状；`operator_receipt` 保留原始保存回执；a5 的 `operator_request_status` 只给固定记录状态与理由。三个工具通过已求值的 `Annotated[CallToolResult, OutputModel]` 绑定 SDK 输出模型，保持手工结果的 JSON 文本与 `structuredContent`；成功结果遵守 object 根与封闭的顶层字段，receipt 子对象允许原回执的额外字段。固定 false 标志拒绝数字 0，整数 schema version 拒绝 true，避免 Python 相等性放松 JSON 类型契约。错误结果沿用 `isError` 与稳定的简短 code，不套成功 schema。[MCP Tools 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [固定 SDK 验证实现](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/mcpserver/utilities/func_metadata.py)

记录读取复用安全打开、文件身份检查与严格 JSON：固定 ID 对应固定文件、拒绝链接和多重 hard link、只读普通文件、每文件最多 8 MiB，并拒绝读取期间变化。状态工具有界读取 intent/receipt 两轮，比较内容和身份；它不获取执行器 state 锁，所以明确是非原子的保存记录观察。两轮一致也不能保证读取后的状态不变。

| 记录组合 | 摘要语义 |
|---|---|
| 两轮均未观察到记录 | `no_records_observed`，不证明动作从未发生 |
| 合法 intent、没有 receipt | `intent_without_receipt`，不推断 running 或安全重试 |
| 同 ID、digest 一致的记录 | `receipt_recorded`，保存的 receipt status 仍需按原语义解释 |
| 两轮变化、孤立 receipt、digest 不匹配 | `inconclusive`，保存 status 为 null |
| 不安全路径、非法内容或读取失败 | 简短业务错误，不反射文件内部内容 |

状态摘要不返回原 action、args、command、path、digest 或异常文件正文；没有取消、重放、执行或全任务枚举。原始 `operator_receipt` 则仍可能含私有路径与输出，不能把状态工具的最小摘要承诺扩展到原回执工具。固定的未做 live verification、未验证真实性及 `snapshot_atomic: false` 字段，使客户端能够保留证据边界；schema 是结构检查，不是授权或来源可信证明。

## Linux 安装目录归属

[`install.sh`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/scripts/install.sh) 使用源码内专用 `.venv` 和 ownership marker。a5 在执行解释器前额外拒绝 `.venv/bin` **目录** symlink，防止拥有的外层目录被用于执行链接目录里的其他解释器；正常 venv 的 `bin/python` 文件链接仍可工作。这个修复限定安装路径，不是对同一 OS 用户恶意并发修改或所有 venv 内容的完整防护。隔离 fixture 验证与实际机器安装必须分别记录。

## 证据与发布

运行配置、state、终端内容、截图和 `evidence/` 默认排除在源代码包外。公开文档只汇总必要的去标识结果；本轮覆盖由 [第五轮报告](REVIEW-WAVE5.zh-CN.md) 记录。CI 的核心测试不自动覆盖真实 Windows 桌面、RDC 连接或用户浏览器。a5 的 workflow 将 Actions 固定到 commit SHA；固定版本和存在 workflow 都不证明 GitHub jobs 或 Pages 已运行。

a4 的发行构建先取得经过目录、文件名与链接检查的源码字节快照，再从同一快照生成 ZIP、TAR、manifest 和独立 HTML 预览。预览里的文档引用也必须通过同一私有名称与相对路径规则，不能通过页面链接重新打开已排除的配置文件。非法引用在写出产物前拒绝；manifest 的哈希证明所打包字节，不证明这些字节已经在目标机器运行。
