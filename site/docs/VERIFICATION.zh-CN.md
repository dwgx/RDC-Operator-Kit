# 当前检查点：0.1.0a6 candidate

2026-11-28（Asia/Tokyo）。本轮新增任务 checkpoint／CAS／原 state 绑定和只读 resume；它不是所有操作的全局执行拦截器。完整缺陷、修复与证据边界见[第六轮报告](REVIEW-WAVE6.zh-CN.md)，使用步骤见[Agent 指南](AGENT-GUIDE.zh-CN.md)与[恢复规格](RESUME-SPEC.zh-CN.md)。下面保留 a5 及更早历史，旧 CI／Release／Pages 不自动成为 a6 的验收。

| a6 项目 | 当前结果 | 范围与限制 |
|---|---|---|
| 基线 | 公开 main `54131f00c3b942797809a1b90424e845ef56fe13` 的 139 个文件逐 SHA-256 对齐 | 本地运行时冻结 `06e0e21` 不是公开提交 |
| Linux 最终 core | 225 run／221 pass／4 Windows-only skip；exit 0、3.529 秒 | Python 3.12.14；较早 223／219／4 是中间检查点 |
| Windows 最终 core | 225 run／212 pass／13 skip；exit 0 | Windows 11 build 26300、Python 3.14.7；运行前 149 个源码文件逐哈希核对 |
| Source 恢复 smoke | Linux、Windows 各 17/17 passed | 真实自有子进程在 effect 后、receipt 前退出；合成 operation，不是真实 RDC 重登 |
| 运行时独立反例 | 三项修后 3/3 passed | JSON null、NUL state、提交后回读不确定性；原失败保留 |
| CLI 只读边界 | fresh-copy `python -B` 正向通过；去掉 `-B` 的反向控制按预期失败 | 后者实际产生一个缓存目录和七个 pyc；不声称 atime／宿主日志不变 |
| Smoke 判定修复 | 副作用 guard、owned-worker 清理、请求与 typed-handle 明细反向控制均核对 | Python audit／mock 范围，不是 OS 沙箱 |
| 发行隐私 | 七个方法修后全部通过；修前 26 个失败条目保留 | 含 subtest，不是 26 个测试；合成 ZIP/TAR/HTML，非通用秘密扫描 |
| Windows 已安装 a6 | 两环境 offline／no-deps 升级，各 12 个实际模块与 wheel 一致，备份保留 | `-I` site-packages 导入，非 Kit 依赖及 config 哈希不变；两个 CLI entry point 均返回 a6 |
| Installed 恢复 smoke | Windows 两环境各 17/17，Linux 新隔离环境同一 wheel 17/17 | Windows 每次六个 guarded resume、零 effect；与 source smoke 分开 |
| Installed 现代 MCP | SDK 2.3.0 真正 stdio，17 checks passed | 协议 `2026-07-28`；三工具与严格双通道、unknown、记录未变、worker 正常退出；不是恢复 smoke 的 17 项 |
| Skill／前向推演 | canonical 八资源保存并回读；四种 Agent 场景回答完成 | 未在推演中操作 Browser、账号或未知进程；不是所有 Agent 的行为保证 |
| 当前路由／历史上下文 | 用户手动登录后重新发现现有连接；既往会话只取得相关检索片段 | 不公开私有标识，不声称读取完整聊天 |
| a6 GitHub CI／Release／Pages | **pending** | 尚无本轮最终公开回执；不沿用 a5 绿灯或资产 |

本轮 wheel 为 51,757 字节，SHA-256 为 `f84ae08e8e6625a14ca84fe2b4a154a58ee4829c5a3866dc9bb23656b2f2770e`。已安装模块验证不等于源码主副本已经最终同步。Browser 的既有策略拒绝／localhost 自动审批拒绝、HMC 额度阻断、OMP 无 final 等历史结论全部保留，本轮未重新测试或绕过。

# 历史结果：0.1.0a5

2026-11-26（Asia/Tokyo）：[v0.1.0a5 Release](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a5) 已发布，[项目网站](https://dwgx.github.io/RDC-Operator-Kit/) 已部署。最新接口、独立 review、具体环境与执行范围见 [第五轮报告](REVIEW-WAVE5.zh-CN.md)。以下总览区分初始 a5 快照、review 后修复和实际发布状态。没有将未执行、跳过或被阻断的项目计为通过。

| 本轮项目 | 已有结果 | 适用范围与当前待完成项 |
|---|---|---|
| CI 修复后本地 Linux core | 184 run／181 pass／3 Windows-only skip | Linux / Python 3.12.14；2.677 秒、0 failure/error；不是 HMC。三个 skip 为 Windows 安装器、8.3 路径和 junction/HANDLE 回归。 |
| 初始 a5 Windows 源码集成 | 同一次九个顶层 case 全部 passed，exit 0 | core 177 run／166 pass／11 skip；源码执行，非 installed-package 全套验收。 |
| 首次 Windows MCP 2.3.0 | modern `2026-07-28` 与 legacy `2025-11-25`，各 30 checks 为 true | 原合成记录未变、held worker exit 0；source a5、当时 installed distribution a4。 |
| MCP smoke 修复与 CI 修复后真实复验 | 12 个独立 verdict 符合预期；最新 Windows 两会话各 36 checks，通过 | 合成回归为两个控制通过、十个错误变异失败；真实 SDK 合计 72 项。最新执行为 source tree，distribution 虽为 a5，仍不证明 CI 修复已进入安装包。 |
| CI 修复后 Windows core | 184 run／173 pass／11 skip | Windows 11 / Python 3.14.7；7.673 秒、0 failure/error。新增短名称和瞬时 junction 回归均通过；不等于重跑整个九项集成 suite。 |
| Linux 安装／liveness | 定向 6/6 与 18/18；独立反例确认修复 | 分别含合成归档、真实自有 pipe fixture 与故障注入；不等于完整 Linux PTY 或 HMC 验收。 |
| 现代首页／Lab | 静态结构、Node 合成事件与独立交互反例检查；IME 修复定点 3/3 | 新 UI 没有 live browser／响应式／真实剪贴板通过结论；Lab 业务脚本保留 a4 字节。 |
| HMC | 首个环境 probe quota-blocked | 没有 OS、Python、安装或执行结果；没有重连、换账户或其他传输重试。 |
| 两次真实 OMP review | GLM deadline；DeepSeek provider 402；均无 final | 原生回执保留；不能称模型已完成 review。 |
| 最终 a5 安装包／Skill | 包含 CI 修复的 wheel 已在两个自有 Windows 环境完成 a5→a5 更新，各 11 个 site-packages 模块与修后源码完全一致；Skill 已更新并同步 | 仅更新 Kit，全部其他 distribution 版本与配置哈希不变，备份保留，使用 `-I` 隔离导入。pre-CI 安装结果仍保留为历史 checkpoint。 |
| 实际 installed CLI／MCP | 两个 `rdc-kit.exe --version` 均为 a5、exit 0；一个 installed 现代 MCP 会话的 17 条断言全部 true | `-I` 启动，实际模块位于 site-packages；协议 `2026-07-28`，保存 unknown、双通道与原记录均核对，worker 正常返回 0。不是 GUI／legacy 重跑，不并入 source 72 或 CI 计数。 |
| GitHub 源码 | [首次公开提交 `5952a45`](https://github.com/dwgx/RDC-Operator-Kit/commit/5952a45f03549de17cdc3d92ff6d7a1f91b3e0ad) 已 push 并回读一致 | public 仓库的 `main` 已有源码，不能继续描述为空仓库。 |
| 首轮 GitHub CI（历史 checkpoint） | [实际 run](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45777836079)：两个 Windows core job 失败，其他四个 job 通过 | 两个失败 job 均为 182 run／11 failures／10 errors／7 skip；原日志保留，不被新 run 覆盖。 |
| 修复提交 GitHub CI | [`a880144` 的 run 45780615916](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45780615916)：六个 job 全部 success | Windows Python 3.10/3.13 core 各 184 run／177 pass／7 skip；Ubuntu core 各 184 run／179 pass／5 skip。CI core 没有可选 Pydantic 2，相关两项明确 skip；新 Windows 路径回归均 ok。 |
| CI 的两个独立 MCP job | Ubuntu／Windows 的 modern、legacy 会话均 passed，原记录未变 | 日志未给出完整逐项 check 数；不把自有 Windows 的 72 项套到 CI。 |
| GitHub Release | [`v0.1.0a5`](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a5) 已于 17:31:53 JST 发布，固定提交 `27d367a9698c381d90986c8640d506b24d84ddd9` | 九项上传资产均已实际下载回读并核对 SHA-256 一致；完整清单见第五轮报告第 12 节。 |
| 发行提交 CI | [run 45782996129](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45782996129) 六个 job 全部 success | 每组 core 184：Windows 177 pass／7 skip，Ubuntu 179 pass／5 skip；两个独立 MCP job 的 modern／legacy 协议均 passed。 |
| GitHub Pages | [run 45783289213](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45783289213) build／deploy 均成功，head 与发行提交相同；[实际网站](https://dwgx.github.io/RDC-Operator-Kit/) | 这是部署验收，不增加新版 UI 的 live browser、剪贴板或响应式交互通过项。 |

MCP smoke 的 review 问题针对判定机制：Python 的普通容器相等会混淆 `false` 与 `0`，而旧状态检查遗漏文本通道的额外内容。生产 `as_result()` 本次没有被证实实际泄露；修复已加入类型敏感 JSON 比较和全部成功响应的双通道核对。真实协议复验与合成反例分别记录，不把修复前 60 checks 当作修复后通过。

首次公开 CI 另揭示 Windows 8.3 短名称与已打开 HANDLE 长名称的比较问题。生产修复在打开前固定展开后的预期名称，保留 HANDLE 路径和 reparse 校验；截图 fixture 与子报告测试则对齐既有 canonical path 契约。首 push 前的 Linux 182 run／181 pass／1 skip，以及 Windows 181 run／170 pass／11 skip 加单独 junction 1/1，保留为较早 checkpoint；不与最新 184 项运行拼接。完整时间线见 [第五轮报告](REVIEW-WAVE5.zh-CN.md)。

最终安装 wheel 为 44,645 字节，SHA-256 为 `24633b51a6cb3e72a4896fb9accf3d3125f4f9f87a2aba659ca482aa5ebcbc8b`。`installed-a5-final.json` 与 `installed-a5-final-smoke.json` 分别记录安装字节核对和实际 installed 入口执行；这次证据补足了旧 pre-CI 安装不能证明新修复已安装的缺口。

Release 归档和随附报告固定在发行提交 `27d367a`；随后 main 只同步文档／页面中的发布回执，不移动 tag、不替换资产。归档内较早的发布前状态保留为该冻结快照，当前结果以本页和第五轮第 12 节的后续记录区分。

历史 a4 的 Linux 158/158、Windows 最终 core 150 pass／8 skip／158，以及顶层 suite 8/9／exit 1 保持原结论；后一次 a5 通过不会删除其 `focus_unverified` 失败。a4 实机与浏览器记录见 [第四轮报告](REVIEW-WAVE4.zh-CN.md)。

## 阅读历史记录

下面从“RDC Operator Kit 验证记录”起，完整保留 **a1 第一轮历史**。其中“尚未发布”、当时测试数和安装版本只描述那个阶段，不是本轮当前状态。[第二轮](research-wave2/REPORT.zh-CN.md)、[第三轮](REVIEW-WAVE3.zh-CN.md)、[第四轮](REVIEW-WAVE4.zh-CN.md) 与 [第五轮](REVIEW-WAVE5.zh-CN.md) 各自保留版本与环境，不能跨轮拼接为一次全部通过。

# RDC Operator Kit 验证记录

日期：2026-11-26（Asia/Tokyo）。版本：`0.1.0a1`。这是有限范围的本地 alpha 验证，不是所有电脑、应用、网页或断电情形的保证。公开包不包含个人配置、设备路由、原始终端输出、账号文件或模型会话日志。

本文保留第一轮历史结论。`0.1.0a2` 的截图修复、有限采样、管道诊断、Browser Evidence、OMP 与 MCP 新结果见 [第二轮报告](research-wave2/REPORT.zh-CN.md)；新成功不抹去这里的失败，也不把旧测试改称新一轮执行。

## 实际环境与方法

Windows 实机使用 Python 3.14.7、Node 24.19.0、RDC agent 0.3.4、项目私有 SmartCLI 0.3.5 和 Microsoft winapp 0.8.0；保留原有全局 SmartCLI 0.3.2。Linux 核心测试与安装使用 Python 3.12.14。真实 UI 验证只操作项目自己创建的 WinForms 窗口；真实终端验证只创建专用 REPL/TUI 会话。

研究阶段核对了当前工具 schema、固定 GitHub 提交和上游许可证。独立审阅者检查请求恢复、目标绑定、安装完整性与错误语义；其结论经主执行者复核后才改代码。存在于上游仓库的测试不计作本项目执行过的测试。

## 结果概览

| 验证项 | 结果 | 证据与适用范围 |
|---|---|---|
| 核心/适配器离线测试 | 46 项 Linux 通过；Windows 43 通过、3 跳过 | 最终源码门禁；Windows 跳过 2 项 Linux 安装器测试与 1 项当前用户无权限建立的 symlink 测试 |
| Windows 真实 REPL | 通过 | 等到提示符，计算得到独立 `42` 行，Unicode 与特殊字符写入文件并逐字核对 |
| Windows 真实 TUI | 通过 | ConPTY/屏幕快照；Down → Beta → Enter；独立文件记录 index=1/choice=Beta |
| 终端退出 | 独立见证通过；通用 close 仍为 unknown | 持有对应进程句柄，两个 fixture 都退出 0；14 个请求中两个 close 保留不确定状态 |
| Windows 桌面完整 smoke02 | 11 项通过 | 观察、绑定、Unicode 赋值、invoke、文件见证、截图、selector click、重放不重复点击、未观察目标拒绝 |
| 桌面重复验证 smoke03/04 | 回读不一致，停止 | 动作确认成功但值为空或变化；适配器正确返回 `outcome_unknown`，没有把确认当成效果成功；之后两次上游独立写入通过，来源未明的额外变化仍保留 |
| Windows 中文/空格目录安装 | 安装与 rerun 通过 | 从 fresh owned 源开始发现故障，修复 PowerShell 5.1 参数和哈希兼容性后续跑成功；完整 rerun 配置哈希不变。不是一次不间断 clean PASS |
| Windows 带引号绝对路径子命令 | 发现上游限制 | PyWinPTY 保留 exe token 引号导致查找失败；现在在 daemon 启动前拒绝；推荐的 cwd 相对命令 REPL/TUI 实测通过 |
| Linux 核心安装 | 通过 | 全新目录建立私有 venv、安装本包、运行 doctor；没有据此声称 Linux TUI/GUI 已验收 |
| OMP preview | 通过 | 真实 Kit CLI 与原 wrapper 返回 `DRY_RUN`，attempts 为空，没有启动模型 |
| OMP 真实独立审查 | 未通过 | 一次 run 和一次有界 resume 均 `Deadline exceeded`；最终 BLOCKED，无 review.md |
| Edge 本地项目页 | 通过有限页面验收 | 本地页面可访问，能力/安装标签与证据筛选有效；首页截图已实际查看，当前页面未记录 console error |
| Edge 的 ChatGPT 网站 | `BLOCKED_BY_POLICY` | host restrictions gate 拒绝导航；没有换用桌面、CDP 或隐蔽网络通道 |
| Skill | 已验证并同步 | 新会话验收覆盖中断恢复、Browser 拒绝、running PID 和 close unknown；不等于工具权限自动安装 |
| GitHub CI / Pages | 已准备，尚未线上运行 | Windows/Linux CI 矩阵与手动 Pages workflow 已解析；仓库/Release/网站未公开发布 |

## 已发现并修复的问题

1. **回执不能覆盖未知效果。** 在写最终 receipt 失败、适配器中断、已有 intent 无结果、历史结果损坏的情形，不再次执行。请求摘要同时绑定完整有效配置。
2. **安装时只检查下载包还不够。** 校验已解压目录中每个文件的 SHA-256，拒绝额外 DLL、修改后的二进制、路径穿越与链接。原有异常内容保留，未执行。
3. **WinApp 的两个 selector 表示不同。** `inspect` 可返回 AutomationId，动作回执返回 canonical elementId。先做只读绑定，再用 canonical ID 执行与验证；不放松 HWND、类型和进程身份约束。
4. **动作后的观察也要核对身份。** 最终 post-observation 不属于原进程时，撤销效果已核验标记，返回 unknown。
5. **Windows PowerShell 5.1 会改变嵌套引号。** Python 版本探针改用不包含嵌套字符串的表达式；散列函数使用 .NET API，不依赖此机器缺失的 `Get-FileHash` 模块发现。
6. **SmartCLI 的启动字符串不是 argv。** 对 Windows 首 token 加引号的命令提前拒绝，避免已知 PyWinPTY 失败进入 daemon 启动与不确定状态。
7. **测试程序也可能有错。** 最初 WinForms witness 使用 PowerShell 自动变量 `$input` 导致见证字段错误，改为明确的 `$fixtureInputBox`；终端 smoke 最初错误地把结构化 screen line 转成 Python dict 文本，改为读 `line.text`。原失败记录保留，未计作通过。

## Windows 终端的真实证据

成功终端运行发生于 2026-11-26 08:37 JST 附近。脚本在 own state 中创建 REPL 和 raw-key TUI：REPL 对 `print(6*7)` 返回单独结果行；合成文件精确保留中文、日文、引号、字面 `$HOME`、反引号和反斜线。TUI 在独立屏幕模型中从 Alpha 移到 Beta，Enter 后的文件记录与屏幕一致。

Windows 进程 HANDLE 在 fixture 仍存活时建立，最终等待两个目标进程退出且 exit code 为 0。这个证据适用于这两个进程。SmartCLI close CLI 丢弃下层关闭细节，所以 Kit 的通用接口仍然返回 `outcome_unknown`，不会把这次额外验证推广成所有 session 的退出保证。

私有原始记录为 `evidence/terminal-state-20261125T233704Z-d884ed5c/summary.json`。它包含每条请求、原生屏幕、见证路径和源码哈希；公开包只保留脚本与本说明。

## Windows 桌面证据与不确定性

smoke02 的测试文本是 `RDC 测试 · 日本語 | 'quotes' & $()`。赋值后的控件读取、Apply 后的独立 JSON witness 和窗口截图一致。Increment 的第一次请求将 count 从 0 变成 1；相同请求再次提交返回保存回执，count 仍为 1。截图通过 RDC 图像通道返回并由主执行者实际查看，范围仅为项目测试窗口。

后续 smoke03 返回动作 ack，但即时 get-value 为 `""`，随后 inspect 与 witness 为 `"i"`；smoke04 使用全新 fixture，最终 witness 为另一个非预期值。两次的 HWND、PID 和创建时间均未改变。固定上游源码的 setter 使用 UIA/COM 模式，未发现键盘 fill fallback；现有证据不能把原因归为用户输入、其他 Agent 或整个 Windows UIA 不可用。

失败回执保留，未自动重发相同动作。随后进行了仅两次直接 WinApp setter 对照：ASCII 和 Unicode 都被 Python UIA、原生窗口文本、独立 witness、WinApp get-value 一致确认。两次之间又出现不属于测试输入的额外前缀，来源仍未知；不能证明它与 smoke03/04 具有同一原因，也不能撤销前面的失败。未执行计划中的另外两次直接 Python UIA 写入。保持 Alpha 定位，不声称广泛稳定支持。最后经核对目标身份后正常 invoke CloseFixtureButton，witness 为 closed 且 IsWindow=false。

## OMP 的两个不同结论

`omp.preview` 于 2026-11-26 08:50 JST 实际执行；Kit exit 0、native status `DRY_RUN`、`attempts=[]`、`real_model_call=false`。这说明已连接现有 wrapper 并生成合法预览，不是成功运行了模型。

真实 review 在 08:31–08:43 JST 期间运行两个 attempt：第一次原生 180.307 秒，第二次原生 360.199 秒，加一次 30 秒退避。两次均 exit 1、classification `upstream_abort`、signature `Deadline exceeded`，最终 `status=BLOCKED`、`transport_ok=false`、`final=null`。没有 `review.md`，没有第三次调用。

请求与会话记录的模型为 `lunaroute/glm-5.3-flash-background`、effort `max`。该字段不独立证明提供方底层实际模型。中止记录的零 usage 也不能作为零消费证明。冻结的十个公开输入文件 SHA-256 不变；第一轮只读这些文件和 manifest，第二轮额外读取了 wrapper 自动追加的同 job `last.md`，未发现 shell、浏览器、产品写入或新模型派发。

失败验证支持“真实启动、路由参数传递、截止和错误证据保留”，不支持“OMP 已完成审查”。核心代码的独立 review 来自本轮其他原生子代理和主执行者的证据复核，不能让 OMP 的失败回执借用它们的成功。

## 安装与最终空间路径验证

Windows 安装的完整轨迹是 fresh owned 源 → Python 探针错误（尚无 venv）→ 修探针并创建私有 venv/依赖 → 缺少 Get-FileHash → 改为 .NET SHA256 → 从 owned 部分安装续跑 → 完整 rerun。最后两次均 exit 0，均核对官方归档 SHA 与十个已解压文件；config 前后 SHA-256 相同。复用了先前已下载的官方包，所以本次安装测试没有再次测试网络下载分支。

原带引号绝对 exe 的 REPL/TUI 失败记录保留。确诊为安装的 PyWinPTY 3.1.2 在 `shlex.split(posix=False)` 后把外层引号留在 exe token，再由 `shutil.which` 查找这个带引号的名字。项目只提前拒绝该已知不支持的形式，没有宣称修复了任意 argv quoting。

推荐 smoke 现在把本项目内的 exe/bootstrap 转换成相对工作目录路径。2026-11-26 08:59 JST，在同一中文/空格安装目录、同一独立 registry、已有私有 venv 中仅执行一次：REPL 与 TUI 均 PASS，两个进程 HANDLE 均确认 exit 0，close unknown 仍保留。对应 `recommended-smoke-final-summary.json` 逐项核对了 cloud、主源码、测试副本的 adapter/test/smoke 三份文件 SHA-256。

## 源码包与页面验证

独立 reviewer 在同一 Python/zlib 环境、相同冻结输入上只构建两次；ZIP、tar.gz、HTML、manifest 和 checksum 文件逐字节一致。解包后逐文件核对 manifest；ZIP/TGZ 源字节一致；在九种 runtime/private 位置放置的合成哨兵均未入包。它证明所检查打包规则，不是通用秘密扫描或跨压缩库版本的相同字节保证。最终归档的具体哈希以随包 `SHA256SUMS.txt` 为准，不能使用 reviewer 较早冻结快照的包摘要。

Edge 通过官方 Browser 连接访问项目的 loopback 静态站。能力标签切换、Linux 安装面板和证据筛选均实际交互并读取结果；首页图像也实际查看。独立单页 HTML 嵌入 CSS、JS、图标和文档，无外部加载资源，另经结构与 JS 语法检查；没有声称移动端、所有浏览器或剪贴板权限情形均已测试。

## 未验证或明确不提供

任意 TUI、任意 Windows 应用、锁屏或 UAC secure desktop、跨用户桌面、Linux/macOS GUI、所有 ChatGPT 网页功能、现有 Codex TUI 的接管、无用户配对的自动登录、系统级恶意进程隔离、所有子孙进程的强制回收，以及永久后台学习均不在本轮验收范围。没有创建持续调度任务。

来源、固定版本和许可依据见 [RESEARCH](RESEARCH.zh-CN.md) 与 [UPSTREAMS](UPSTREAMS.md)。操作方式见 [使用指南](README.zh-CN.md)，公开发布前检查见 [RELEASE](RELEASE.zh-CN.md)。
