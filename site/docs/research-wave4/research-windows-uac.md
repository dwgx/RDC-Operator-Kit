# Windows 输入权限、UAC 与可靠桌面操控研究

日期：2026-11-26（Asia/Tokyo）
范围：RDC Operator Kit 下一阶段的 Windows 诊断、鼠标操作与人工接力设计。
性质：独立研究工作稿；本稿未操作用户机器、未提升权限、未修改 UAC 或安装服务。这里的设计建议不是已经实现或通过实机验收的功能。

## 1. 建议采用的产品承诺

可以建设的目标是：**对支持的 Windows 场景，确认对象身份与当前输入条件，执行一次动作，保存回执并验证实际效果；条件不满足时给出准确原因和可继续的接力步骤。** 不应写成“所有窗口、所有 UAC 提示都保证自动点击”。

Windows 普通桌面、已提升的应用和 UAC 安全桌面需要分别处理。Microsoft 的 `SendInput` 文档明确规定输入注入受 UIPI 限制，只允许指向相同或更低 integrity level 的应用；而其失败返回值不能单独证明是 UIPI。UAC 默认把确认放在 secure desktop，官方建议保留这层隔离。[M1][M2]

这一边界不降低普通桌面自动化的价值：RDC 继续承担文件与进程路由；winapp 负责已授权窗口的 UIA 操作和受约束的真实鼠标输入；网站 UI 依从被选择的浏览器能力及其独立权限。更换 OMP 模型、封装 MCP 或增加 Skill 均不会改变 Windows 的 token、session、desktop 或浏览器宿主权限。

## 2. 系统事实与直接工程后果

| 已核实事实 | 对 Kit 的直接后果 | 一手来源与读取范围 |
|---|---|---|
| `SendInput` 受 UIPI 限制；返回事件数量，不返回业务操作成功与否；UIPI 原因无法仅凭返回值或 `GetLastError` 唯一识别 | 保存事件/命令回执；另查目标状态。不能把发送成功写成保存成功、点击成功或 UAC 已允许 | [M1] 官方 API 正文 |
| `PostMessage` 也受 UIPI；低 integrity 向高 integrity 的消息可被拒绝，UIPI 拒绝时可得到 Access Denied | 不能把 `post-message` 当作普遍跨权限解决方案，更不能在拒绝后盲目更换输送接口重放输入 | [M3] 官方 API 正文 |
| `UIAccess` 有签名、可信安装位置和 manifest 要求；它不是无限提权，也不自动得到 system IL 的 UAC desktop 访问能力 | 可研究合规辅助技术产品的独立发行架构；不把普通 Python/PowerShell 脚本改一个标志就宣称支持 secure desktop | [M4] 官方安全设计正文；[M5] 官方配置正文 |
| `SetForegroundWindow` 受 Windows 焦点规则限制，即使满足列出的条件也可能被拒绝 | 焦点切换返回值和实际 foreground 必须分别记录；失败时停止输入，不用 topmost 或坐标盲点伪造成功 | [M6] 官方 API 正文 |
| `GetForegroundWindow` 可能在窗口失活转换时返回 NULL | `foreground_hwnd == 0` 只能证明这次读数为空，不能单独写成“已检测到 UAC”或“必定锁屏” | [M7] 官方 API 正文 |
| `OpenInputDesktop` 在断开的 session 也可能返回恢复连接时将使用的 desktop | handle 成功不是“用户当前可以看见并接管桌面”的充分证据；同时查 session 状态 | [M8] 官方 API 正文 |
| desktop 对象有自身访问控制，打开操作会检查所请求的权限 | `Access Denied` 应保留为观察结果，不调整 ACL、不请求切换 desktop 的权限来令探针跑绿 | [M9] 官方文档正文 |
| 服务自 Vista 起不能直接与用户交互；通常在 session 0，而用户窗口属于交互用户的 session | 后台 broker 和会话内 UI worker 应分开。不能仅把 RDC 设成 SYSTEM 服务就承诺能操控所有用户窗口 | [M10] 官方架构文档正文 |

### 2.1 发现的上游说明冲突

本次读取的 winapp `docs/ui-automation.md` / Microsoft Learn 对应说明包含两种过宽或冲突的表述：`post-message` 可跨所有 integrity，以及 `send-input` 受阻方向的描述。它们与 Win32 `PostMessage` / `SendInput` 的基础 API 合同不一致。[R2][M1][M3]

建议在 Kit 文档采用基础 API 的约束，并明确实际 token、窗口类型、输入方法及具体实测范围。不能因为某个 WinForms 控件在一次环境中收到消息，就推出所有高权限应用或 UAC 都可用。这里记录的是文档冲突；未把该冲突扩大为“整个 winapp 不可靠”，也未向上游发送 issue。

### 2.2 不把未知状态归因得过满

`OpenInputDesktop` 失败、当前 foreground 为空、UIA 目标查询失败、SendInput 零返回分别可能由多种原因产生。诊断器应输出 `unknown` 或具体已观察到的错误，再列候选解释。`requires_user_consent` 只有在任务确实请求提升或已确认正在等待用户同意时才准确；否则用 `interactive_desktop_unavailable` / `foreground_unverified` 并解释需要用户检查屏幕。

## 3. 仓库比较与复用决策

| 项目 | 本次实际读取 | 许可 | 值得借鉴的实现 | 对 Kit 的建议 |
|---|---|---|---|---|
| [microsoft/winappCli](https://github.com/microsoft/winappCli) | `v0.8.0` 的 `Input/MouseInput.cs`、`Input/ForegroundCheck.cs`、LICENSE；当前文档及测试的检索片段 | MIT，直接读取 LICENSE | 真实输入与 UIA 操作分开；foreground 检查；虚拟多屏坐标归一化；分批输入部分执行的错误语义；拖动异常时尽力释放按钮 | **保留为当前主要 Windows 后端。** 在 Kit 增加身份、诊断、效果验收与未知结果协调层，优先修复集成而不是再装一套操控栈 |
| [FlaUI/FlaUI](https://github.com/FlaUI/FlaUI) | README 检索片段、`src/FlaUI.Core/Input/Mouse.cs` 前 160 行、LICENSE.txt | MIT，直接读取 LICENSE | .NET UIA2/UIA3 接口；鼠标坐标读回、多屏移动、点击节奏的细节 | 适合将来 .NET companion 或更丰富控件测试；不是当前必须新增的 Python 依赖，不能假定它绕过 UAC |
| [pywinauto/pywinauto](https://github.com/pywinauto/pywinauto) | README、`controls/hwndwrapper.py` 的 focus 相关段、LICENSE | BSD-3-Clause，直接读取 LICENSE | Win32/UIA 双后端；窗口包装与状态等待 | 可研究其控件覆盖与等待设计。所读 `set_focus()` 会移动真实鼠标，因此不能把所有探测/聚焦方法当只读调用；不要直接复制“抢焦点”实现到 doctor |
| [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP) | README 和 manifest 检索片段、`desktop/service.py` 前 120 行、`tools/control_status.py` 与 `desktop/control.py` 的固定 commit 片段、LICENSE.md | MIT，直接读取 LICENSE | 截图尺寸/坐标映射；控制权状态；操作提示；human takeover 与长任务状态的接口设计 | 借鉴状态表达与可见接管，不立即启用其整个 PowerShell/文件/浏览器工具面。其上游也明确 hook 接管为 best-effort，而非排他控制或安全边界 |

### 3.1 winapp v0.8.0 已直接核对的代码行为

固定 tag：`v0.8.0`。读取结果带有 Git blob SHA，而不是本机安装文件校验或测试通过证明：

| 文件 | 读取结果中的 blob SHA | 观察 |
|---|---|---|
| `src/winapp-CLI/WinApp.UIAutomation/Input/MouseInput.cs` | `b5bf45c344052c9c7e33522f327b9227a6fe9a35` | 鼠标使用 `SendInput`；多屏以 virtual desktop 原点和尺寸归一化；部分事件写入抛错；拖动异常清理是 best-effort |
| `src/winapp-CLI/WinApp.UIAutomation/Input/ForegroundCheck.cs` | `65f303bc7f12256093cfeb11432d1bd65baa9092` | 区分可执行、无交互 foreground、目标未持有 foreground |
| `LICENSE` | `25ef6e9607f14dfaa543181109d05134c09a57cd` | Microsoft 与贡献者的 MIT 条款 |

这些观察支持以下设计判断：保留 `foreground_not_target`；不要用“工具非零退出”一律推断“绝无任何副作用”；部分按下/抬起事件可能已经送达，应进入 `outcome_unknown` 协调流程，不重放整个动作。[R1][R3]

`MouseInput` 是下层输入实现，不是完整 Kit 的对象绑定、桌面权限或业务成功证明。上层与下层都检查也无法让屏幕状态停止变化；实际动作前后的证据仍然必要。

### 3.2 许可与版本复用规则

如以后实际复制 MIT 或 BSD 代码，保留对应版权、许可和修改记录，并记录具体 tag/commit 与文件路径；BSD 的署名与不得暗示背书条款也要保留。本次只产生自写分析与接口建议，未向 Kit 复制上述仓库代码。检索到 `main` 或特定 commit 中的功能，不等于已安装的发行版本就提供它。使用 CLI 选项前应核实本机版本与 help/schema。[R4][R5][R6][R7]

## 4. 推荐新增：只读 Windows 操控前置诊断

推荐入口暂称 `desktop.preflight`，可以先做独立 CLI，再纳入 Kit 只读动作。它应提供事实与理由，不应自动提权、抢焦点、切桌面、创建计划任务或修改策略。

### 4.1 采集字段

| 字段 | 建议 API | 注意事项 |
|---|---|---|
| 自身与目标 PID、创建时间、执行映像路径、HWND 所属 PID | 沿用 Kit 已有身份绑定；`GetWindowThreadProcessId` 等 | 目标查询前后对照，防止 PID/HWND 重用。获取失败不可静默默认成自己 |
| 自身、目标 integrity RID 与 elevation/UIAccess | `OpenProcessToken` + `GetTokenInformation`，只申请 query 权限 | 读 `TokenIntegrityLevel`、`TokenElevation`、`TokenElevationType`、`TokenUIAccess`。不要用管理员组成员身份代替 token 是否提升。[M11][M12] |
| 自身与目标 session | `ProcessIdToSessionId` | 使用实际结果，不硬编码“console 就是 session 0”。查询失败保留错误。[M13] |
| session 连接状态 | `WTSQuerySessionInformation` 的 `WTSConnectState` | 连接状态与锁屏、当前 input desktop 是不同事实，不相互替代。[M14] |
| process window station、thread desktop、input desktop 名称与可读性 | `GetProcessWindowStation`、`GetThreadDesktop`、`OpenInputDesktop`、`GetUserObjectInformation(UOI_NAME/UOI_IO/UOI_FLAGS)` | 仅查询，释放自己打开的 handles；不调用 SwitchDesktop，不改 ACL。通过 UOI_IO 可记录对象是否接收输入。[M8][M9][M15] |
| 当前 foreground HWND、PID；是否目标或允许的、已验证 owned dialog | `GetForegroundWindow` 及窗口 owner 链查询 | 主窗口与弹窗要在 contract 中区分；有弹窗时不能把主窗截图误认成单窗口事实。[M7] |
| 平台、时间与采集能力 | UTC 时间 + collector 版本 | Linux 返回 `unsupported_platform`，不能伪造 Windows 默认值；时间戳说明采集时刻，不保证动作时仍成立 |

输出应带每一小项的 `status`、值和原生 error；局部查询失败不丢掉其它已采集字段。若目标是浏览器，则诊断仍不能据此开启原先被拒绝的网站操作。

### 4.2 建议判断状态

| 状态 | 必须满足或已观察到的条件 | 后续动作 |
|---|---|---|
| `ready_for_attempt` | 目标身份可靠；同一可用 session/desktop；目标前台；所需 token 权限条件已满足；无未协调的旧动作 | 仍需立即重查目标并执行一次，再验效果；该状态不等于 success |
| `foreground_not_target` | 有 foreground，但不是本次绑定的对象/允许弹窗 | 停止注入；可在明确已授权的拥有窗口中发起一次正常 focus 请求，然后读回；失败则由用户激活 |
| `integrity_mismatch` | 已成功读取 token，所选普通输入路径没有足够权限 | 报出 collector/target IL；准备一个有界、用户可审阅的提升操作，由用户处理系统确认 |
| `session_mismatch` | 自身与目标 session 不同 | 改用该用户 session 中已存在且受信的 worker，或人工接力；不能把 session 0 当交互桌面 |
| `interactive_desktop_unavailable` | 当前输入条件不可用，或读取明确失败 | 不注入；保留错误并请用户检查锁屏/UAC/连接。不要冒称已经确诊 UAC |
| `unknown` | 关键事实缺失或相互矛盾 | 不尝试具有副作用的鼠标动作；继续只读诊断或交接 |
| `unsupported_platform` | 非 Windows | 明确跳过 Windows 功能，保留 CLI/文档/纯逻辑验收 |

这张状态表是本稿的设计建议，并非 Microsoft 对每种组合的授权表。尤其 UIAccess 和 AppContainer 等情况需要专门实测；初版宁可返回 `unknown`，也不把复杂权限比较简化成“管理员=true 就一切可用”。

### 4.3 纯诊断可测性质

最有价值的单元测试是错误分类与控制流：查询失败不得变成 success；foreground 为零不得唯一归因 UAC；target identity 变更不得沿用旧观察；跨 session 不发送输入；IL 不可读不得假设与自身相同。测试应断言“没有执行输入/提权/策略写入”，而不是只镜像某个 if 分支。

## 5. UAC 的正规工作流

合法的标准提升机制可以由 Shell 执行 `runas`，Windows 会向用户提出同意或管理员凭据要求；取消应记录为取消而不是重试。`ShellExecuteEx` 对取消有明确的错误语义。[M16][M17]

建议产品分两阶段：

1. **初版提供诊断与人工接力。** 展示准确的待提升可执行文件、参数、工作目录、预期副作用、文件指纹和限定时长。系统确认由用户完成。未得到进程身份与结果回执前，不报告提升成功。
2. **有明确需求后设计受信 companion。** 普通 session worker 负责 GUI；受限 elevated helper 只接受固定授权操作。两者用本机身份约束的 IPC、单次 request ID、超时和结果文件通信；不提供任意 shell、任意路径或任意代码的无限权限入口。用户确认、签名与安装包验证是发行设计的一部分。

第二阶段是架构方向，不是本稿已证明安全的实现。不能靠关闭 UAC、禁用 secure desktop、修改 message filter、临时计划任务或 token 技巧来获得“全部测试通过”。对 UAC 提示自动点击本身没有在本研究中得到可支持的普遍方案，不能承诺。

## 6. 普通鼠标点击的实际验收方式

建议使用 Kit 自己创建的 WinForms/WPF fixture，绑定 nonce、进程创建时间和 HWND。窗口中放专用 `MouseClick` 计数按钮及只追加 witness。固定一次 click 的 request ID；同一 request 重取回执不再生成输入。

顺序如下：

1. 启动拥有的测试窗口，等待独立 witness 中出现真实子进程身份。不得仅假设 wrapper 的 Popen PID 是窗口 PID。
2. 读取 preflight、UIA 元素、bounding box 和相关窗口截图。
3. 若需要聚焦，使用正常的、作用于这个已验证 HWND 的 focus 行为，记录其是否获准。焦点依然不符就结束该 case；不删除上游检查。
4. 重查 exact HWND/PID/creation time、当前 foreground、元素位置与输入桌面。只对观察到的元素执行一次 click。
5. 以独立 witness 证明 click 计数从 0 到 1，同时确认变化属于同一 nonce/fixture。工具 ACK、echo、截图文件存在均不能代替这一步。
6. 对相同 request 获取历史回执，确认计数仍为 1。若首次结果未知，先读 witness，不能通过换 request ID 再点一次来解决不确定性。
7. 正常关闭拥有的 fixture；记录清理结果，不扫杀同名应用或无关窗口。

这套过程可以消除很多“看似点了、其实点错或根本没点”的假阳性。它不能消除用户在两次检查之间移动鼠标/激活窗口的所有竞态。可以向 Windows-MCP 学习可见控制状态与接管入口，但其上游也把 hook 接管明确限定为 best-effort。[R8]

## 7. 建议 smoke-test 矩阵

| 测试 | 通过标准 | 失败时的正确行为 |
|---|---|---|
| 普通桌面 exact-window click | witness 0→1、同 nonce、同进程、单次输入 | 状态与错误完整保留 |
| 非目标窗口在前台 | 返回 `foreground_not_target`；witness 保持 0 | 不向其它窗口发送点击 |
| 元素移动或窗口替换 | 拒绝旧 observation / target moved | 重新观察；不自动重放旧动作 |
| 同 request 重读 | 返回原回执；witness 仍为 1 | 对冲突 payload 返回 conflict |
| SendInput 部分执行 | 分类为 `outcome_unknown`，保留部分执行原因 | 调查独立 witness，禁止重放 |
| 已提升目标而 worker 权限不足 | 明确 IL 差异或 unknown | 用户确认流程，不能偷偷提权 |
| UAC / lock / input desktop 不可读 | 明确不可用/unknown，停止注入 | 人工接力，保留 UAC 配置 |
| session 不同或 RDP 断开 | 不宣称可点击当前桌面 | 只读报告 session 条件 |
| 多屏、负坐标、非 100% DPI | 绑定目标显示器、截图原始尺寸与坐标系；计数正确 | 不用缩略图像素直接点击屏幕 |
| UIA invoke / set_value | 相关模式有效且独立读回结果 | 不把 invoke 通过算成 mouse click 通过 |
| collector 不支持/调用异常 | 结构化失败仍可读取 | 不空报告、不吞异常转 PASS |

真正的锁屏/UAC、跨 session 与多显示器 case 应当在用户明确配合的专用测试时段执行，不为了测试负路径而随意锁定当前远程会话。纯逻辑负向测试可以先覆盖拒绝语义，但必须注明不是实机 UAC 验收。

## 8. 推荐实施顺序

**当前就做：** 保存 `desktop.preflight` 的只读结果；修正所有“管理员=可控所有窗口”“换 PostMessage=跨 UAC”的文案；对 foreground 拒绝、partial input 与未知结果给结构化恢复说明；补 Windows fixture 的真实鼠标效果验收。

**随后做：** 在网页公布按平台、后端版本、环境条件拆分的能力矩阵；显示具体失败/跳过原因；暴露明确的“等待用户激活窗口”“等待用户处理 UAC”的状态，不让 TUI 或 agent 无限卡住。

**更晚独立设计：** 签名 companion、受限 IPC 与生命周期管理、可见控制权与接管、性能采样。该阶段需要 threat model、安装/卸载、升级、鉴别与实机验收；不能仅把第三方 MCP 启动起来就称为成熟 harness。

## 9. 来源与访问层级

以下均为维护者仓库或 Microsoft 文档；仅读取声明的范围。检索与 connector 访问不等于在用户电脑验证其运行行为。

### Microsoft

- [M1] [SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)：检索返回的官方正文；读取 UIPI、返回值与输入状态相关段。
- [M2] [How User Account Control works](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/how-it-works)：官方检索正文，secure desktop 与 consent 段。
- [M3] [PostMessageW](https://learn.microsoft.com/en-us/windows/desktop/api/winuser/nf-winuser-postmessagew)：官方正文，UIPI 与错误码段。
- [M4] [Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)：官方正文，UIAccess 要求与 IL 限制段。
- [M5] [UAC settings and configuration](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/settings-and-configuration/)：官方配置说明，签名/可信位置/secure desktop 段。
- [M6] [SetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow)：直接打开官方 API 正文。
- [M7] [GetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow)：直接打开官方 API 正文。
- [M8] [OpenInputDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop)：官方正文与 disconnected session 说明。
- [M9] [Desktop Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/winstation/desktop-security-and-access-rights)：官方检索正文。
- [M10] [Interactive Services](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services)：官方正文。
- [M11] [TOKEN_INFORMATION_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class)：直接打开 user-mode API 枚举；避免采用老驱动页面的 session 简化说明。
- [M12] [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation)：直接打开官方 API 正文。
- [M13] [ProcessIdToSessionId](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-processidtosessionid)：官方正文。
- [M14] [WTS_INFO_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/ne-wtsapi32-wts_info_class)、[WTS_CONNECTSTATE_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/Wtsapi32/ne-wtsapi32-wts_connectstate_class)：官方枚举说明。
- [M15] [GetUserObjectInformation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getuserobjectinformationa)：官方正文，UOI_NAME/UOI_IO/UOI_FLAGS 段。
- [M16] [SHELLEXECUTEINFO](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ns-shellapi-shellexecuteinfoa)：官方正文，runas 语义。
- [M17] [ShellExecuteEx](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecuteexa)：官方正文，错误与取消语义。

### 上游仓库

- [R1] [winapp v0.8.0 MouseInput.cs](https://github.com/microsoft/winappCli/blob/v0.8.0/src/winapp-CLI/WinApp.UIAutomation/Input/MouseInput.cs)：GitHub connector 分两段读取全文件。`raw.githubusercontent.com` 的网页读取失败后未宣称该读取成功；实际证据来自 GitHub 文件工具。
- [R2] [winapp UI automation documentation](https://github.com/microsoft/winappCli/blob/main/docs/ui-automation.md)：网页检索与 Firecrawl developer search 返回相关段落，未声称审核整个仓库。
- [R3] [winapp v0.8.0 ForegroundCheck.cs](https://github.com/microsoft/winappCli/blob/v0.8.0/src/winapp-CLI/WinApp.UIAutomation/Input/ForegroundCheck.cs)：GitHub connector 全文；[MouseInputTests.cs](https://github.com/microsoft/winappcli/blob/e7e4587ad7a6e51c085ad6360a10ede0cee7ab6e/src/winapp-CLI/WinApp.UIAutomation.Tests/MouseInputTests.cs)：Firecrawl 固定 commit 的相关测试片段，不能等同本机执行过测试。
- [R4] [winapp v0.8.0 LICENSE](https://github.com/microsoft/winappCli/blob/v0.8.0/LICENSE)：GitHub connector 全文。
- [R5] [FlaUI README](https://github.com/FlaUI/FlaUI)、[Mouse.cs](https://github.com/FlaUI/FlaUI/blob/main/src/FlaUI.Core/Input/Mouse.cs)、[LICENSE.txt](https://github.com/FlaUI/FlaUI/blob/main/LICENSE.txt)：README 检索片段；Mouse.cs 前 160 行；许可全文。
- [R6] [pywinauto README](https://github.com/pywinauto/pywinauto)、[hwndwrapper.py](https://github.com/pywinauto/pywinauto/blob/master/pywinauto/controls/hwndwrapper.py)、[LICENSE](https://github.com/pywinauto/pywinauto/blob/master/LICENSE)：README 片段、focus 方法相关行、许可全文。
- [R7] [Windows-MCP README](https://github.com/CursorTouch/Windows-MCP)、[desktop/service.py](https://github.com/CursorTouch/Windows-MCP/blob/main/src/windows_mcp/desktop/service.py)、[LICENSE.md](https://github.com/CursorTouch/Windows-MCP/blob/main/LICENSE.md)：README 相关片段、service.py 前 120 行、许可全文。
- [R8] [Windows-MCP ControlStatus](https://github.com/cursortouch/windows-mcp/blob/42133911a57920b8e61cb0ce506f85ec2c57fa21/src/windows_mcp/tools/control_status.py)、[control.py](https://github.com/cursortouch/windows-mcp/blob/42133911a57920b8e61cb0ce506f85ec2c57fa21/src/windows_mcp/desktop/control.py)、[上游控制权变更讨论](https://github.com/CursorTouch/Windows-MCP/issues/445)：Firecrawl 开发者索引返回的指定文件/讨论片段。讨论内测试数量属于上游作者报告，未当作 Kit 的测试结果。
