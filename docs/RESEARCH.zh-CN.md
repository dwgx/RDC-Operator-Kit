# RDC Operator Kit：能力、边界与复用研究

研究日期：2026-11-26（Asia/Tokyo）  
范围：公开一手资料、GitHub 固定提交源码、当前 ChatGPT 会话暴露的工具定义。**本备忘记录来源研究，不作为设备验收结果；实机运行另见验证报告。上游测试未在本轮执行。**

本研究支撑 `RDC Operator Kit` 的首版设计。具体动作、当前浏览器限制与平台范围见 [能力说明](CAPABILITIES.zh-CN.md)，固定上游身份见 [版本与许可记录](UPSTREAMS.md)。本研究文档与主代理完成的本机测试报告分开维护，不能互相替代。

### 项目采用的组合

核心使用 Python 3.10+ 标准库，以薄 CLI 协调请求、intent、回执和状态锁；终端接 SmartCLI，Windows 控件接 Microsoft winapp UIA，网页继续使用官方 Browser 插件，OMP 沿用用户现有 `origin-dispatch`。新增能力通过 RDC 已有命令通道调用，不新增公网控制端点。

本轮 Browser 已确认选择 Edge，但对 `https://chatgpt.com` 的导航被 host restrictions gate 拒绝，记录为 `BLOCKED_BY_POLICY`。因此“自动开 ChatGPT 会话或点击其所有功能”不是本轮已验证能力，也不改用桌面或 CDP 绕行。

## 1. 裁决

RDC 足以承担可靠的设备路由、文件工作、命令与 REPL 通道。它不是现成的桌面鼠标/键盘 CUA，也不是完整终端仿真器。新项目最有价值的切片是：保留 RDC 官方连接与身份管理，为它补充可检查的本地 GUI 适配器、结构化执行回执、明确的终端能力探针和任务流程 Skills。

不要重做 RDC 的 OAuth/远端托管服务，不要再起一个和用户已有 OMP dispatcher 竞争的队列，不要声称任何 shell 都等于 TUI 控制。RDC 能启动本机脚本，因此这些扩展在工程上可行；具体 Windows GUI 实用性仍需本机见证。

## 2. 已锁定的一手版本

| 组件 | 本轮读取版本 | 许可证及用途 |
|---|---|---|
| DesktopCommanderMCP 本地 MCP 与 remote device agent | `9a101b17e44577f0baefa4c7120f087881c5cc56`；package `0.3.4`；提交日期 2026-11-18 | MIT，可按许可复用代码与测试；保留版权与许可 |
| remote-desktop-commander 托管服务公开目录 | `71d6444c59c36f2cba2f13e8f72785383a8528b5`；2026-11-25 | 仅文档、manifests、品牌素材，版权保留；托管服务源码不在仓库，不能把它按 MIT 整包复制 |
| Remote-Commander-Tray | `70ec27403dfa909534ecc58c67d554855d57c1e2`；2026-11-25 | MIT；适合研究单进程监督、Windows Job Object、托盘状态与日志边界；本轮未运行 |

主源：

- [本地 package.json](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/package.json)
- [本地 MIT LICENSE](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/LICENSE)
- [remote 仓库 LICENSE](https://github.com/desktop-commander/remote-desktop-commander/blob/71d6444c59c36f2cba2f13e8f72785383a8528b5/LICENSE)
- [Tray README](https://github.com/PeterShanxin/Remote-Commander-Tray/blob/70ec27403dfa909534ecc58c67d554855d57c1e2/README.md)
- [Tray LICENSE](https://github.com/PeterShanxin/Remote-Commander-Tray/blob/70ec27403dfa909534ecc58c67d554855d57c1e2/LICENSE)

## 3. Remote 与 Local 是两层

本地 DesktopCommanderMCP 使用 stdio，供本机支持 MCP 的客户端使用。Remote device agent 连接官方托管中继，再把工具请求交给本地 MCP 子进程。用户已连接的 ChatGPT 插件走这一条远端路径；安装本机 stdio server 本身不会让网页 ChatGPT 自动发现它。

官方 remote endpoint 是 `https://mcp.desktopcommander.app/mcp`，客户端用 OAuth，设备配对另有 device authorization flow。官方说明支持 Windows、macOS、Linux。机器必须运行 device agent 才可达；停进程、注销设备和移除 ChatGPT connector 是不同动作。

来源：[Remote README](https://github.com/desktop-commander/remote-desktop-commander/blob/71d6444c59c36f2cba2f13e8f72785383a8528b5/README.md)、[remote device 文档](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/src/remote-device/README.md)、[本地子进程集成源码](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/src/remote-device/desktop-commander-integration.ts)。

### 不能混淆的状态

- 工具目录出现：表示本会话有这个接口，不表示某台设备在线。
- 设备在线：不表示当前本地 Python、GUI 会话或浏览器扩展可用。
- MCP 子进程握手：不代表某个实际工具请求已成功。上游当前实现也用实际服务请求检验 readiness。
- `DONE` 或退出码 0：不是产物通过验收的同义词。
- 图像工具返回成功：不代表模型已查看画面，更不代表点击目标仍未变。

最后三点中关于项目验收的要求是本次工程判断；不是 RDC 提供的额外保证。

## 4. 当前会话的完整工具清单：30 个

以下以 **2026-11-26 本会话工具 schema** 为准，和官网市场文案分开。公开 README 还列出 ping、提示库与反馈等功能，但本会话未暴露对应可调用工具，不能硬写进可运行 Skill。

| 组 | 已暴露工具 | 实际用途/边界 |
|---|---|---|
| 文件读取 4 | `read_file`、`read_multiple_files`、`list_directory`、`get_file_info` | 内容、分页、目录与元数据；绝对路径最稳妥 |
| 文件修改 5 | `write_file`、`write_pdf`、`edit_block`、`create_directory`、`move_file` | 创建、改写、追加、精确替换、移动；没有单独的删除工具 |
| 搜索 4 | `start_search`、`get_more_search_results`、`stop_search`、`list_searches` | 文件名/内容搜索，返回搜索 session，分页拉取 |
| 终端与进程 7 | `start_process`、`interact_with_process`、`read_process_output`、`list_sessions`、`list_processes`、`force_terminate`、`kill_process` | 新建管道子进程、stdin 交互、输出读取、进程观察与停止 |
| 设备/账号 3 | `list_devices`、`who_am_i`、`shutdown` | 选机器、账号用量、停止 device agent；`shutdown` 不是停止一条任务，也不是关机 |
| 配置 2 | `get_config`、`set_config_value` | shell、目录范围、命令拦截、输出限制、遥测等 |
| 观察 2 | `get_usage_stats`、`get_recent_tool_calls` | 使用统计、有限本地历史 |
| 远端异步 2 | `list_remote_tool_calls`、`get_tool_result` | 查 remote `call_id` 状态及最终结果 |
| 调用审阅 1 | `review_device_call` | 展示准确调用供用户复核，本身不执行；不能当成普通超时重试 |

当前工具清单里没有 `screenshot`、`click`、`type`、`drag`、UIA tree、OCR、浏览器 tab/CDP 方法。桌面与浏览器能力必须由另外的受支持适配器提供。

公开工具对照：[本地 README 工具表](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/README.md)。当前会话清单来自真实 tool metadata，不冒称 upstream GitHub 保证。

### 文件格式细节

当前 `read_file` schema 宣称支持文本分页；Excel sheet/range；PNG/JPEG/GIF/WebP 图像内容；PDF 文本和嵌入图；DOCX 概览或原始 XML。DOCX `offset=0` 是概览；非零 offset 才进入 XML 分页，直接沿用普通文本分页假设会读错。

当前 `write_file` 可写文本、Excel 的 JSON 二维数组、创建 DOCX；PDF 走 `write_pdf`；DOCX 原内容精确编辑走 `edit_block` 的 XML 模式。该格式能力是接口承诺，本轮尚未逐格式本机验收。

本地截图脚本可以先生成 PNG，再通过 `read_file` 返回图像，因此不需要为看图专门暴露公网图床。但截图生成、传输、模型查看三步都必须各自验收；不能只拿 PNG 路径说已经看见屏幕。

`list_directory` 默认深度 2，嵌套目录最多展示 100 项并有省略提示。目录输出不是完整资产清单；精确盘点应使用可分页搜索或本地结构化脚本。

## 5. CLI 与 TUI：源码证明的分界

在 `src/terminal-manager.ts` 中：

- `executeCommand` 使用 `child_process.spawn` 的普通 pipes；Windows 设置 `windowsHide: true`。
- `sendInputToProcess` 给不以换行结尾的输入追加 `\n`。
- 会话和已结束会话保存在进程内的 Map 中，输出有缓存上限与旧行淘汰。

因此原生 RDC 的持久 session 是管道 REPL session，不是 Windows 已有控制台的附着控制。它没有在这个接口提供 ConPTY、raw key、resize、VT 当前屏幕模型。全屏终端工具可能退化、关闭彩色界面、在 `isatty` 判定时退出，或者只返回无法正确解释的 escape sequence。这是从实现导出的兼容性判断，不是本轮实际运行任何特定 TUI 的失败结论。

主源：[terminal-manager.ts](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/src/terminal-manager.ts)、[improved-process-tools.ts](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/src/tools/improved-process-tools.ts)。

### 建议路由

| 任务 | 首选 |
|---|---|
| 编译、测试、脚本、批处理 | RDC process + 结构化结果文件 |
| Python/Node REPL | RDC 持久 process；保留 PID 与准确 shell |
| OMP bounded worker | 用户现有 `origin-dispatch`；读 brief/receipt/产物，不新造队列 |
| Codex 非交互任务 | 本机已安装版本支持的正式非交互接口，先读 `--help` |
| Full-screen TUI | 经本机验证的 SmartCLI/ConPTY 适配器，或明确 unsupported |
| 现有 Windows 应用 | UIA 优先；必要时限定窗口的 screenshot/input |
| ChatGPT 已登录网页 | 用户指定 Edge 插件，按它自己的文档与连接状态走 |

## 6. 三种异步句柄不能混用

1. **`call_id`**：RDC 远端中继尚未交出工具结果。用 `get_tool_result`，不能重新发同一个有副作用的命令。
2. **`pid`**：命令已经启动，继续读输出或写 stdin。读输出超时通常只是本次等待结束。
3. **搜索 `sessionId`**：搜索器的结果分页与生命周期，走 search 工具。

当前 remote tool 描述把等待上限写为 3000 ms；本地 `src/config.ts` v0.3.4 的 `MAX_PROCESS_WAIT_MS` 为 50000 ms。两者所属层级不同，适配器应尊重当前 connector 的 schema，不能从本地源码硬编码远端等待行为。

`read_process_output(offset=0)` 表示新输出，和 `read_file(offset=0)` 的从首行读取不同。正 offset 是绝对位置，负 offset 是尾部。并发消费者共享同一“新输出”游标会发生争抢；项目应该为一个过程指定唯一输出收集者，再把持久记录供其他 reviewer 读。

上游已有已提交测试包括 process pagination、完成后读取、进程树终止、remote pending recovery 与等待上限。可以借鉴它们的验收行为，但**未运行这些测试，因此只标 COMMITTED-TEST**。

主源：[config.ts](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/src/config.ts)、[分页测试](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/test/test-process-pagination.js)、[pending recovery 测试](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/test/test-remote-pending-recovery.js)。

## 7. 安装脚本必须解决的一处文档冲突

Remote README 和 device README 仍写 Node >=18，当前 v0.3.4 `package.json` 已要求 **Node >=22.12.0**。官方 MIT 仓库的 Windows launcher 也按 >=22.12 判断，并在缺少 Node 时提供 Node 24 安装流程。因此新安装器应以锁定包版本的 engines 为准。

建议自己的项目安装器先检查 Node/Python/系统会话/适配器版本，再安装自身私有目录；RDC 若已可用则复用，不改用户的启动方式。不要把 `npx @latest remote` 与已运行的 RDC 同时另起一个 supervisor。跨平台文案区分“核心命令可运行”“桌面 GUI 已验收”；Linux 不应因为 Python 能 import 就写成全功能支持。

官方 launcher 已有 checksum 校验、错误返回、旧 Node 检测、调用者 PATH/错误偏好恢复以及可读取的 PowerShell 测试，可作为 MIT 复用候选。固定版本后再复用并保留 attribution，不直接复制 remote 文档仓库的受限安装材料。

主源：[Windows launcher](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/scripts/remote/remote-windows.ps1)、[Windows launcher 测试](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/test/remote-launcher-windows.test.ps1)。

## 8. 控制与审计边界

RDC 以用户权限执行。上游明确把目录/命令配置定义为防误操作机制，不能当成恶意客户端的安全沙箱；`allowedDirectories` 只限制直接文件工具，shell 不因此受同等限制；空数组是全部文件范围。项目自己的 allowlist 同样不能在下层仍有任意 shell 时承诺 OS 隔离。

因此面向日常工作的控制层应承诺可观察、避免误操作、可停止、所有权检查，不要承诺完全隔离。GUI 至少检查指定窗口、PID、可见性、当前 foreground、截图时间；执行键鼠后重读状态。并发多个 reviewer 可行，但同一桌面只能有一个动作执行者。

官方表示中继使用 HTTPS/TLS，不能据此写端到端加密。公开 device 文档说明远端调用行会短期保存用于路由，完成后进入清理窗口，不能宣传零临时存储。自身项目不读取或打包 RDC 的 `device.json`、MQTT private key、浏览器 cookies。公开包使用合成 fixture 回执。

主源：[Remote security model](https://github.com/desktop-commander/remote-desktop-commander/blob/71d6444c59c36f2cba2f13e8f72785383a8528b5/SECURITY.md)、[本地 security](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/SECURITY.md)、[Remote device storage/retention](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/9a101b17e44577f0baefa4c7120f087881c5cc56/src/remote-device/README.md)。

### 为什么还需要自己的回执

RDC `get_recent_tool_calls` 有限历史会截断超过 4 KiB 的输出，并修剪旧记录；process output 也不是跨重启持久账本。项目可保存每次 owned 操作的 request ID、目标身份、预条件、结果、退出码、版本、产物路径与摘要校验，不默认记录私人屏幕内容或任意 shell stdout。这样聊天中断后可核实已有结果，而不重复执行未知结果的写操作。

## 9. 首轮最小功能与决定性反例

以下是建议验收，不是已通过的测试：

| 功能 | 正控 | 必须失败/正确拒绝的反例 |
|---|---|---|
| doctor | 返回平台、依赖、版本、适配器清单 | 无 GUI 或缺依赖时明确 unsupported，不能写 ready |
| 文件/命令 smoke | 合成目录写入、读取、校验、带非零退出的脚本 | 命令 exit 7 不得被 transport_ok 覆盖成成功 |
| 长命令 | 返回 pid 后读到唯一完成标记 | 同时/重复请求不能执行两次；等待超时不重发 |
| 图片通路 | 生成合成 PNG，RDC 返回并实际查看 | 只有本地路径无图像时不能标 screenshot_seen |
| Windows UIA | 自己的测试窗口枚举、读取、填写与按钮回执 | 错 PID、窗口关闭、过期 observation 时拒绝动作 |
| 键鼠 fallback | 新截图、限定窗口坐标、执行后新截图 | foreground 已变或分辨率变时拒绝旧坐标 |
| CLI/TUI capability | `isatty`/resize/raw input fixture | pipe backend 明确 tty=false，不宣称支持完整 TUI |
| 进程取消 | 只取消本项目启动的已核 PID/进程组 | 拒绝未知 PID、RDC 本体、用户现有 OMP/终端 |
| 安装/卸载 | 私有目标目录，可重复安装与准确恢复 | 目标已有非本项目数据时拒绝覆盖；卸载不删 RDC |

## 10. 推荐复用与暂缓

**立即保留**：官方 RDC 连接；已有 OMP dispatch；明确的本地 CLI 输出；Browser 插件；MIT 上游的测试思想、版本检查与进程生命周期处理。

**独立开发**：小型本地适配器，按 schema 做 `doctor`、`windows`、`observe`、受限 input 和 receipts；以进程 stdio/文件结果先落地，避免为初版额外暴露网络监听。

**后续可选**：Remote Commander Tray 的托盘监督与 Windows Job Object 设计；它已有 Windows x64/ARM64 和 Linux Beta 相关代码。当前 README 明确 Linux 状态是 service running，不等于 connected；不要照搬搜索摘要里旧的“无 Linux”。

**暂缓承诺**：所有 ChatGPT 网页功能、任意 TUI、锁屏/UAC secure desktop、跨用户桌面、macOS/Linux GUI、无需人工配对的完整一键登录。每个都需要独立见证，不能从 shell 成功推出来。

## 公开引用入口与取证方法

除了上面的固定提交链接，以下入口适合后续复核上游现行文档：

- https://github.com/desktop-commander/remote-desktop-commander
- https://github.com/desktop-commander/remote-desktop-commander/blob/main/LICENSE
- https://github.com/desktop-commander/remote-desktop-commander/blob/main/SECURITY.md
- https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/package.json
- https://github.com/PeterShanxin/Remote-Commander-Tray
- https://desktopcommander.app/help/getting-started/what-is-desktop-commander

部分固定 SHA 的 GitHub 页面在 web open 返回 DisabledError；同样地址已通过 GitHub connector 成功取回正文。本备忘的版本锁定来自 GitHub REST commit 和固定 ref file fetch，而不是搜索摘要。
