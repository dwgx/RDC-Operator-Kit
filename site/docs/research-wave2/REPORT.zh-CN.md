# RDC Operator Kit 0.1.0a2：第二轮研究、实现与实测报告

日期：2026-11-26（Asia/Tokyo）。原始进程、工具回执保留 UTC 时间。本报告对应 Windows 优先的本地 Alpha 候选，延续 0.1.0a1；旧版失败与限制仍保留在 [第一轮验证记录](../VERIFICATION.zh-CN.md)。

## 交付结论

这轮把“更多能力”推进成了四个可运行切片：**有限窗口画面采样、命令存活性诊断、浏览器证据实验页与校验器、可选的只读 MCP stdio 入口**。现有 RDC、SmartCLI、winapp 和 OMP 继续分别承担设备连接、终端、Windows 控件和模型任务。

项目已在授权的 Windows 专用目录工作；研究、实现、反例测试、独立 review、Skill 接手测试和实际 OMP 派发分批进行。公开 GitHub 仓库、Release 与 Pages 尚未发布。这里的研究覆盖有明确主题、固定版本和来源清单，不声称穷尽全网；通过项也只覆盖实际执行的平台、版本与夹具。

最终候选已经完成以下验收。核心测试与真实桌面、终端、模型或协议实验分别记录：

| 验证 | 实际结果 | 范围 |
|---|---|---|
| Linux 核心与合成回归 | 100 项通过，1.714 秒 | Python 3.12.14；标准 unittest 模块入口 |
| Windows 核心与合成回归 | 100 项运行，93 项通过、7 项跳过，3.944 秒 | Python 3.14.7；4 项 symlink 权限、1 项 POSIX FIFO、2 项 Linux installer 被跳过 |
| Windows 主安装更新 | 0.1.0a2 安装成功，配置 SHA-256 前后相同 | SmartCLI 0.3.5 / MCP 1.30.0；pip check 无依赖错误 |
| Windows 独立 MCP 安装 | 新 .venv-mcp 安装 0.1.0a2 / MCP 2.3.0 | 不含 SmartCLI；pip check 无依赖错误 |
| 两个实际安装包核对 | 各 10 个 Python 模块与候选源码 SHA-256 全部一致 | 使用 -I 从 site-packages 导入，避免 cwd 源码遮盖安装包 |
| 最终 MCP 环境 | 两协议各 19 项检查通过，1,226.498 / 1,212.332 ms | 实际 .venv-mcp，父子进程身份、正常退出与回执不变均通过 |
| 新版页面 | Edge 打开并实际查看首页及 Relay 面板 | 本地预览保留；公开 Pages 未部署 |

另一次主线汇总尝试通过标准输入启动 unittest runner，导致 multiprocessing spawn 无法重新打开名为 <stdin> 的主模块；那次为 99/100，原日志保留。改用项目文档中的 python -m unittest 标准入口后得到上表的 100/100。这是测试启动方式的修正，没有改动锁测试或放宽断言。

发行构建另在 Windows 与 Linux 各执行了一次：95 个源码文件的大小与 SHA-256 全部一致。实际构建发现 pathlib 默认排序在两平台不同，构建器已改为相对 POSIX 路径排序以统一 manifest。压缩运行时分别为 Linux zlib 1.3.2 与 Windows 1.3.1.zlib-ng，因此不承诺重新压缩的 ZIP/tar.gz 逐字节相同；每份实际发行归档都有自己的 SHA256SUMS。核心与安装包没有因这个打包排序修复改变。

## 本轮新增的实际内容

| 内容 | 已实现的行为 | 实际适用范围 |
|---|---|---|
| 截图来源核对 | 核对 winapp 的 PID、HWND、输出路径、尺寸及单窗声明；核对 PNG 头部和文件 SHA-256 | Windows 原生窗口；不声称完整图像解码 |
| 有限画面采样 | 绑定一个 observation，保存逐帧 manifest；相同图片哈希不伪装为新渲染帧 | 最多 12 帧；开始下一帧的截止最多 60 秒；不是直播服务 |
| 命令存活性诊断 | 同时消费 stdout/stderr；有界保留；区分静默、明确等输入、输出洪泛、截止与完成见证 | Windows/Linux 的自建 subprocess fixture，不接管任意 PID |
| 浏览器实验页 | 无账号的本地页面，独立 DOM witness、nonce、document epoch、计数和请求 token | localhost 合成实验；点击故意不具备去重能力 |
| 浏览器证据校验器 | 校验导入证据的一致性、动作与见证关系、旧画面和失联状态 | 离线，不控制浏览器、不认证来源、不授予 origin 权限 |
| 只读 MCP | operator_capabilities 和 operator_receipt 两个工具，官方 SDK 2.3.0，stdio | 能启动本机子进程的 MCP host；独立环境；不暴露动作 |
| Skill 更新 | 明确画面采样、图片实际查看、进程等待、未知结果恢复及允许的独立 Relay fixture | 路由和操作说明，不创造电脑连接或额外授权 |

核心原有 12 个 action 保留。新增的诊断与证据工具没有变成一个接受任意命令的常驻服务，也没有在本机安装第二套 RDC 管家。完整接口见 [能力表](../CAPABILITIES.zh-CN.md) 与 [使用指南](../README.zh-CN.md)。

## 一、浏览器与 Relay：已经确认什么

### 研究覆盖与选择

浏览器支线比较了 10 个候选，并留下 54 条可定位的来源记录。Exa、Firecrawl 和 GitHub 连接器用于检索与读取；主线又核对了直接影响实现的 OMP Relay、winapp 和 MCP 原始材料。检索结果槽位、正文获取成功数、固定源码和已执行测试分别记录，没有把搜索命中数量写成“读完的网站数量”。

| 候选 | 本轮用途 | 当前决定 |
|---|---|---|
| OMP Browser Relay 19.2.1 | 复用用户已经运行的本地浏览器桥接 | 对允许的 localhost fixture 做真实派发和回执核验 |
| Playwright MCP 0.0.86 | context 隔离、profile 冲突、生命周期参考 | 保留作后续专属测试浏览器适配候选 |
| browser-use 1.0.8 | 运行结束与任务成功语义、架构迁移参考 | 当前不引入另一个完整 Agent 主循环 |
| Stagehand 4.0.0 | observe / act / extract 分工及 browser handle 归属 | 可选集成方向，尚未安装验证 |
| Browserbase | 托管 session 与 keep-alive 生命周期 | 未新增账号或云服务 |
| BrowserOS neo | 审计、回放与故障分析参考 | 未把 AGPL 实现复制进本项目 |
| Skyvern | session 到期和工作流错误分类 | 未引入完整服务 |
| Chrome DevTools MCP 1.14.0 | 诊断协议参考 | 不据此承诺当前 Edge 完全兼容 |
| Browser MCP | 多浏览器身份与重连用例 | 借鉴测试意图，未另装 daemon |
| AgentWorkforce/relay 18.16.1 | Agent 消息投递回执 | 与 OMP Browser Relay 是不同项目，不能混为一谈 |

固定 commit、许可、已读实现与上游测试的明细在 [浏览器研究](BROWSER-MCP.zh-CN.md) 和 [来源清单](sources-browser.json)。其中“检查了上游测试”不等于执行了那些测试。

OMP 19.2.1 的 Browser Relay 使用既有扩展/native host 及动态 loopback 连接，当前文档形式为 app: "relay"。own tab、borrowed tab、persist 与断开后的生命周期不同；worker 恢复后旧 element ID 与运行上下文可能失效。单独的域名参数并不是宿主授权。固定版本的 README 在首次安装与扩展 ID 上还存在内部表述差异，本轮没有为了诊断执行 install 或 sync。[固定 Relay README](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/browser-relay/README.md)、[浏览器接口](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/docs/tools/browser.md)

### 本机真实 Relay 结果：部分成功，完整验收失败

本轮通过已有 origin-dispatch，向实际安装的 OMP 19.2.1 派发一个冻结的 fixture brief。只访问本项目的 localhost 页面，使用独占命名 tab，禁止第二次点击；Retry-Safe 为 none，只有一次 attempt。

从真实工具日志和保存图片中核对到：

1. 打开本地 Browser Evidence Lab，读取 DOM、nonce、document epoch、request ID 和 token，初始计数为 0。
2. 保存操作前 PNG，116,393 字节。主代理实际查看了图片，并核对 SHA-256 为 7815d264e8a660f09cf751e0b523e77ba10017964bc5e198e31c4b07ed902ab9。
3. 发出一次 Increment click。工具返回后，另一次 DOM 读取显示 counter=1、business_revision=1、pending_request=null；last_completed 的请求 ID/token 与点击前读取值匹配。
4. 接着，worker 的验收代码引用未定义的 out.requestAtClick，发生 TypeError。没有保存操作后截图，也没有生成完整验收 JSON。
5. finally 日志记录专属 tab release 成功、managedTabsAfter=[]。这是 Relay 工具返回的清理证据；主代理没有另开用户页面证明所有浏览器内部资源状态。
6. worker 在 600 秒模型期限结束时被上游中止，wrapper 最终为 BLOCKED / upstream_abort / Deadline exceeded，final=null。

因此，结论是 **“本地 Relay 的打开、观察、一次操作与 DOM 回读有成功证据；整套 smoke 未通过”**。不能把部分结果改成 DONE，也不能因为缺少 after 图片再执行同一个点击。此操作实际已发生，后续若研究采集器，应先修确定性采集逻辑，并在新的独立 fixture 上开展新任务。

worker 曾进行 managed tabs 的只读枚举，返回空列表；这超出了 brief 中不枚举其他 tab 的严格要求。没有证据显示读取了其他用户 tab 内容，但不把这次执行称为完全符合 brief。截图接口返回文件路径时，worker 又探查了返回对象并使用底层 page.screenshot 取字节，暴露出应预先核对接口返回契约的问题。这些都进入验收记录，而不由模型的自述掩盖。

### ChatGPT origin 的边界仍然存在

第一轮官方 Browser 已确认 Edge 连接，访问 chatgpt.com 时收到 host restrictions gate 拒绝。本轮没有把该目标转交 OMP、RDC、CDP、另一模型或桌面输入。localhost Relay 的结果只支持该独立测试页，不能推出“已经能操控 ChatGPT 所有网页功能”。这个具体边界与浏览器技术能力应分开理解。[第一轮实测](../VERIFICATION.zh-CN.md)

### 离线证据校验器带来了什么

新增校验器把以下信息分开：浏览器/context/tab/target 身份、document epoch、fixture nonce、请求摘要、图片字节与尺寸、观察次序、动作 ACK、动作后的独立见证。ACK 只说明请求被接收；它不能代替 counter/token 的业务结果。

失联后即使导入材料声称计数已变化，也保留 outcome_unknown；旧图片、复用 tab、时间倒退、篡改摘要和只有 Agent 自评的结果不会获得完整 fixture 结论。外部 stop 或 host-refused 先于证据包内容生效。其正例只证明输入内部自洽，返回中明确 authenticity/live execution/authorization 未验证。[使用文档](BROWSER-EVIDENCE-USAGE.zh-CN.md)

该模块 10 项测试通过；独立 review 另外检查了 27 种 ACK/状态组合及 11 项页面行为。后者使用 Node 合成 DOM，不是浏览器运行结果。真实 Relay 的部分证据也没有伪装成校验器的完整正例。

## 二、看图与 CUA：从文件存在推进到来源可核对

### 为什么新截图文件仍不足够

固定 winapp 0.8.0 的截图 JSON 可以同时返回多个 owned window 的 composite。它还可以使用不同的画面获取路径，而 JSON 没有统一暴露真正的渲染帧时间。命令结束时间不是源像素的时间；文件新建、尺寸正确或哈希改变，也不能单独证明这是所需对象的最新画面。[截图命令源码](https://github.com/microsoft/winappCli/blob/696222f72e80c669671845bd6c7b0286eefab987/src/winapp-CLI/WinApp.Cli/Commands/UiScreenshotCommand.cs)、[JSON 数据结构](https://github.com/microsoft/winappCli/blob/696222f72e80c669671845bd6c7b0286eefab987/src/winapp-CLI/WinApp.Cli/Helpers/UiJsonContext.cs)

因此现在会核对 PID/HWND/路径/尺寸与当前内核身份一致，拒绝 composite、元素截图、坐标裁剪和远程执行目标冒充本地单窗；读取文件时保留大小与身份检查。每帧记录 frame_id、artifact SHA-256、命令起止与耗时。captured_at 仍为 null，pixel_freshness 明确为 unproven；PNG 只验证头部，不声称完整解码。

独立 review 找到采样器外层身份检查与真正 capture 之间的目标替换窗口。修复把同一个短效 observation 传入适配器，在执行捕获前再次核对；确定性反例从“对替换对象捕获一次再停止”变为“捕获零次并停止”。普通 UIA 仍无法消除所有操作系统时序竞态，不把这一修复称为原子桌面事务。

### Windows 实测

本轮创建专用 WinForms fixture，使用随机 nonce、独立 JSON witness 和只属于该任务的窗口：

| 检查 | 实际结果 |
|---|---|
| 操作前后窗口图 | 主代理实际查看；从蓝色、action_count=0 / frame_seq=0 变为橙色、1 / 1 |
| 一次 UIA Next Frame | 独立 witness 为 action_count=1 |
| 相同动作 request ID 重放 | 没有第二次增加 |
| 相同截图 request ID 重放 | frame ID 与原时间保持不变，没有伪装成新捕获 |
| 动画中的有限采样 | 3 帧，3 个不同 SHA-256；采样约 2,414.984 ms；fixture frame_seq 从 2 到 13 |
| 打开自己的附属对话框后截图 | winapp 返回两窗口 composite；Kit 保留 outcome_unknown / composite_capture_rejected |
| 关闭 | 正常关闭本任务窗口；IsWindow=false，独立 witness 记 closed；外层 fixture 进程 exit 0 |

原始 smoke summary 的 pictures_visually_reviewed=false 是脚本当时的事实，保持不变。主代理的后续图片审阅单独记录，未改写原始测试回执。主代理查看了 before、after 和拒绝的 composite；并没有声称逐一视觉检查所有三帧动画图。

相关代码是 frames.py、sample_desktop.py、smoke_observation.py、observation-fixture.ps1。截图模块 6 项测试、采样器 6 项测试以及独立的目标替换反例共同覆盖新增行为；真机结果与反例测试分别留档。

### “实时”当前到哪里

现在是**有限采样 + 明确目标 + 逐帧 manifest + RDC 图片读取**。每帧先持久化后输出，ChatGPT 需要真正读取返回的图片才能说已看图。最多 12 帧，开始下一帧的截止最多 60 秒；已开始的一次 capture 仍可能使用其 30 秒命令超时和清理时间。它不是固定 FPS 的视频流，也不保证后台、最小化、锁屏、受保护内容或 UAC 桌面。

更低延迟的视频需要专门的采集、帧时间、背压、断开与访问生命周期。Windows Graphics Capture 的源帧时间不能由 shell 调用时间代替；研究记录了 OSWorld、Windows Agent Arena、Agent S、ScreenSpot-Pro 等基准的启发，但本项目没有复跑这些 benchmark。[画面观察研究](OBSERVATION.zh-CN.md)、[原始来源](OBSERVATION.sources.json)

## 三、命令窗口为什么会像“卡死”

这轮做了两个外部观测完全相同的程序：一个静默 sleep，一个无提示地等待 stdin。两者都是进程 alive、输出 0 字节，所以只能报告 running_silent。不能仅凭没有新字判断哪个在等输入，更不能盲目再发 Enter。

诊断脚本对 stdout/stderr 分别持续 drain，控制线程读取有界计数和当前状态；每路只保留前 4 KiB。它不在控制线程等整条流的 EOF，也不把画面稳定、READY 提示符或 exit 0 等同于业务完成。唯一完成正例要求本次 token 的完成 marker、独立 witness 与正常退出一致。

Windows 首轮 9 项测试中有 1 项失败：venv redirector 的父 PID 与真正 Python fixture PID 不同。主线在真实机器分别启动 venv 与 base interpreter，确认差异后，仅对这个标准库 fixture 选择当前 CPython 的真实 base interpreter；并保留严格 PID 核对，绝不从 witness 认领一个任意 PID 作为可终止对象。[CPython venv 说明](https://docs.python.org/3/library/venv.html)、[固定 Windows launcher 源码](https://github.com/python/cpython/blob/v3.14.7/PC/venvlauncher.c)

修复后 **Windows 12 项针对性测试通过，9 个诊断场景均符合预期**。waiting-input 正例约 48.869 ms；1200 ms 截止场景实际约 1204.572 ms，所有直接子进程退出与 reader join 都得到确认。这里的 9 场景 PASS 表示正确分类和回收；8 个业务未完成的反例仍保持 semantic_verified=false。

该 probe 是普通 subprocess 管道测试。第一轮 SmartCLI 的真实 REPL/TUI 与中文、空格路径证据另行保留；本轮不借用管道结果证明 ConPTY 在所有应用都不会阻塞。原来的 SmartCLI close CLI 未暴露完整退出事实，通用 close 仍可以是 unknown。

还有一个容易误判的点：Kit 在一次适配器调用期间持有 state 锁，另一次调用可能得到 busy。这表示同一 state 正在处理请求，不自动等于终端卡死。使用较短的显式 wait，再观察当前结果；不能新建 state 绕过同一动作的协调。[终端研究及源码链接](TERMINAL-LIVENESS.zh-CN.md)

## 四、MCP 和 Skill：实际配套，而不是权限的另一名字

MCP 入口只提供：

- operator_capabilities：描述配置形状与版本，不执行 doctor、不启动程序，不输出 argv 或配置路径。
- operator_receipt：从启动时固定的 state 读取一个合法 Kit request ID 的已有 receipt，不执行、重放或刷新原动作。

入口使用官方 mcp==2.3.0，仅 stdio。路径型 ID、额外字段、symlink/reparse point、多个 hard link、非普通文件、超过 8 MiB 的文件、重复 JSON key、非有限数及身份不符都被拒绝。POSIX 按目录 descriptor 打开；Windows 核对已打开 HANDLE 的最终路径。回执保留 outcome_unknown，读取成功不代表原业务完成。[实现与安装](../MCP.zh-CN.md)

主线核对了 2026-07-28 协议变更与固定 SDK：现代 discover 与旧 initialize 并不相同；JSON-RPC transport ID 与 Kit request ID 也不是同一层。重新连接或更换 transport ID 不能授权重复未知动作。[规范变更](https://modelcontextprotocol.io/specification/2026-07-28/changelog)、[固定 SDK](https://github.com/modelcontextprotocol/python-sdk/tree/2118f14f8a19bc158d8a1cf90af58d85d187f849)

Linux 的真实 SDK 会话分别协商 2026-07-28 和 2025-11-25。初次发现 SDK middleware 的 live 返回是字典，导致 schema 标注未生效；同时处理字典与 typed result 后，两个会话各 15 项检查通过。Windows 第一轮通信、schema、参数拒绝、回执读取、held process exit 0 均通过，正常 EOF 的 PID 检查因 venv redirector 失败。修复保留真实 venv 路线，在会话活跃时通过只读 OS 查询核对父链、执行文件、创建时间并持有 worker HANDLE；EOF 后核对同一对象退出。**Windows 修复后两协议各 19 项检查通过，耗时 1,170.971 / 1,146.513 ms；SDK parent 与 worker 均 exit 0，原回执未变。Linux 新候选两协议各 18 项通过。** 两类初次失败的原始记录均保留，Windows 多出的一项是同一 worker HANDLE 的退出核对。

安装中发现的依赖冲突已明确：SmartCLI 0.3.5 要求 mcp>=1.0,<2，新入口固定 mcp==2.3.0。两者必须使用不同的虚拟环境，不应执行 .[terminal,mcp]。MCP 入口接收主项目已有配置/state 的绝对路径，只读共享回执；它不需要修改主终端环境。可选 extra 固定顶层 SDK，但没有完整传递依赖锁。

本地 stdio 命令只能由支持本机子进程的 host 启动，不会自动变成 ChatGPT 云端可访问的 HTTPS connector。当前 ChatGPT 到 Windows 仍走已连接的 RDC。Skill 负责告诉 Agent 何时用哪条路线、如何观察和验收；导入 Skill 不代表安装了二进制、连接了浏览器或获得了额外权限。

更新后的 Skill 已通过验证，并由无历史上下文的新子代理进行接手测试。它实际读取新文档、图片与回执，正确判断旧 fixture 已关闭、动画图不是直播、pipe 不等于 PTY、unknown 不可重放。该测试不是对真实用户桌面重新执行任务。

## 五、真实 OMP 派发与裁决

本机 catalog 当前可解析 lunaroute/glm-5.3-flash 与 deepseek/deepseek-flash，后者显示 DeepSeek-V4.1-Flash。它们是本次已安装路由的名称，不代表研究者独立认证了供应商后端模型。实际 wrapper 源文件 SHA-256 为 35f59f6af1e61b51624773cf1440bad273b16770f0afeecabf655bc0ade9e378。

| 任务 | 回执 | 实际产物 / 裁决 |
|---|---|---|
| GLM 5.3 flash 截图契约 review | DONE，约 485 秒，exit 0 | 6,069 字节最终审阅文本；没有工具调用。主线逐项裁决，没有把模型建议当作事实 |
| DeepSeek V4.1 flash 终端状态 review | BLOCKED，约 1.946 秒，exit 1 | provider 返回 402 Insufficient Balance；没有模型最终答案；未充值或换账号 |
| GLM 5.3 flash localhost Relay smoke | BLOCKED，上游约 600 秒 deadline，exit 1 | 开页、观察、before 图、一次点击与 DOM 变化可核对；验收代码错误，缺少 after 图/完整结果 |

GLM 的五项建议中，PID/HWND 与 composite 来源核对支持主线修复方向；“已有输出路径可覆盖”的担忧在完整 Kit 中已有拒绝，不作为新缺陷；建议接受多个窗口全部通过与本项目单窗契约不符，未采纳。其样例 HWND 字符串也不符合实际整数契约。24 字节 PNG 头不是完整解码这一点已明确保留，不把加一个 checksum 宣称为视觉验收。有关焦点的建议没有足够的完整源码依据，未据此宣称发现新故障。

之前 background 路由的两次审阅超时保留为历史失败；这次普通 GLM 路由成功不重写旧记录。DeepSeek 的余额错误与 Relay 的验收错误属于不同问题，不能统称“OMP 不可用”，也不能反过来用一个 DONE 宣称全链可靠。Codex 没有在本轮进行真实模型派发，不列入已验收能力。

## 六、独立 review 与缺陷闭环

| 问题 | 发现与处理 | 当前证据 |
|---|---|---|
| 多窗口截图可能冒充单窗 | 核对上游 JSON，拒绝 composite | 真机开 owned dialog 后得到预期拒绝 |
| 采样器外层检查后的目标替换 | 独立 reviewer 构造确定性交错，增加 observation 内层绑定 | 修复后对替换目标 capture=0 |
| Windows 标准库 fixture PID 不一致 | 真机复现并对照 base interpreter | 12 项针对性测试及 9 场景重验通过 |
| SDK live middleware 字典结果 | 首次真实协议测试暴露 | 两种协议重跑 schema 与额外参数拒绝通过 |
| MCP Windows venv 的两层身份 | 首次真机保留失败 | 见最终 MCP 验收节 |
| SmartCLI 与新 SDK major 冲突 | 主线核对既有依赖台账 | 安装说明要求两个独立环境 |
| Relay worker 验收代码变量错误 | 从真实工具结果读出 TypeError | 保留 partial/BLOCKED，不重放已发生点击 |

浏览器离线实现有独立 review；MCP 路径和数据边界另有 5 项确定性交错检查，覆盖末端/父目录链接替换、读取期间原子替换、配置对象后续变化和错误信息。review 结论受源码版本和测试范围约束，不以参与 Agent 数量代替证据。

本轮没有宣称修复第一轮桌面文本回读偶发不一致，也没有宣称解决通用 SmartCLI close 的退出可见性。两项继续作为已知边界。

## 七、如何安装与复用

### Windows 主路线

取得完整源包后，在希望保留项目的目录解压，打开该目录的 PowerShell：

~~~powershell
.\scripts\install.ps1 -WithTerminal -WithDesktop
.\.venv\Scripts\python.exe -m rdc_operator --config config.local.json --state .rdc-state doctor
~~~

这使用项目私有 .venv、固定 SmartCLI 0.3.5 和有内容校验的 winapp 0.8.0。重复安装保留已有配置，首次后来新增组件时需要按说明补路径。完整中文/空格目录的真实终端安装证据在第一轮记录；本轮安装更新另有最终候选核对。

可选 MCP 请按 [独立环境安装步骤](../MCP.zh-CN.md) 创建新的 .venv-mcp。不要将 MCP 2.3.0 装进现有 SmartCLI 环境。云端 ChatGPT 仍通过 RDC 调用本地命令。

有限画面采样：

~~~powershell
# $targetHwnd 必须来自当次已授权窗口的实际发现；输出目录必须尚不存在。
.\.venv\Scripts\python.exe scripts\sample_desktop.py --config config.local.json --state .rdc-state --window $targetHwnd --output (Join-Path (Get-Location) 'evidence/sample-new') --frames 3 --interval-ms 500 --start-deadline-seconds 30 --apply
~~~

诊断与离线检查：

~~~text
python scripts/probe_terminal_liveness.py
python scripts/verify_browser_evidence.py --help
python -m unittest discover -s tests -v
~~~

### Linux

~~~bash
bash scripts/install.sh --with-terminal
.venv/bin/python -m rdc_operator --config config.local.json --state .rdc-state doctor
~~~

Linux 有核心、终端和可选独立 MCP 路线；Windows winapp 桌面不在 Linux 支持范围。本轮 Linux 测试主要是核心、合成 subprocess 与 MCP stdio，不能扩张为所有桌面和所有发行版支持。

### 交给 ChatGPT 或本地 Agent 的接手说明

~~~text
读取 RDC Operator Kit 的 README、Skill、能力表与最新实测报告。
确认当前设备、授权目标、已有安装和 state；不要从旧回执沿用 PID/HWND。
按已安装路线调用工具：文件/进程用 RDC，TUI 用 SmartCLI，原生窗口用 winapp。
图片要实际打开查看；新观察使用新的请求 ID，重放回执不是刷新画面。
OMP 工作使用已有 origin-dispatch，冻结 brief，限定一个写入者。
只读 MCP 使用独立 .venv-mcp；不要升级 SmartCLI 环境的 MCP major。
动作后检查独立产物；unknown 或失联先核对发生了什么，不自动再执行。
在本轮授权范围内完成工作，交付实际结果和失败证据。
~~~

项目保留源码、Skill、安装器、GitHub Actions 与 Pages 准备文件；公开发布所需 owner/repository 设置见 [发布说明](../RELEASE.zh-CN.md)。当前没有可宣称已上线的公开安装 URL，也没有已运行成功的 GitHub Actions 记录。

## 八、下一轮有证据支持的目标

这一阶段在候选验收后交付，不把无限派发作为质量指标。下一轮最值得继续的是以下具体问题：

1. 把 Relay 的浏览器证据采集做成确定性步骤，先在新 fixture 校验前后截图、动作见证和关闭，再考虑其他获准站点。一次 UI 操作和完整任务验收分开。
2. 为有限采样评估真正的源帧时间、低延迟传输与背压。先给出延迟与内存预算，再决定是否需要视频服务。
3. 针对 SmartCLI 自有 ConPTY 会话，测试无人轮询时输出、长 wait 期间观察和退出见证。普通 pipe 的成功不能替代这些实验。
4. 在明确的实际 MCP host 上验证安装与接入；当前只读切片稳定后，才讨论动作工具、图片资源或远端 transport。
5. 建立可复现的依赖锁和发布 CI 执行记录，保留 Windows 与 Linux 的差异；在公开发布授权后运行仓库与 Pages 流程。

原始日志、机器路径、账户配置和测试图片保留在私有 evidence，源码发行包按 allowlist 构建。公开文档包含可复核结论与来源，不附带登录资料或浏览器 profile。

