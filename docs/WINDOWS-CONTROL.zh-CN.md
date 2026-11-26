# Windows 操控与恢复指南

版本：0.1.0a4；2026-11-26（Asia/Tokyo）。本文说明已实现的接口与验收方法，具体实机结果见 [第四轮报告](REVIEW-WAVE4.zh-CN.md)。

## 选择合适的入口

| 任务 | 入口 | 需要核对的结果 |
|---|---|---|
| 文件、单次命令、进程输出 | RDC | 具体设备、真实退出码、文件或输出见证 |
| 交互 CLI / TUI | SmartCLI 的 Kit adapter | 当前屏幕、提示符、独立业务结果、owned child 退出 |
| Windows 原生应用 | winapp 的 Kit adapter | HWND / PID / 创建时间、fresh observation、控件结果 |
| Windows 输入条件诊断 | `windows-preflight` | token、session、desktop、foreground；不发送输入 |
| 网页点击、填写、截图 | 当前获准的官方 Browser | 当前 tab 身份、动作后 DOM / 独立见证 |
| 已有 OMP Relay 的单独获准任务 | 既有 dispatcher / relay | frozen brief、owned tab、native receipt、实际结果 |
| 请求管理员权限 / UAC | 正常 Windows 提升与用户确认 | 具体程序与动作授权；确认后重新观察 |

普通窗口、已提升的应用与 UAC 安全桌面是三个不同问题。浏览器扩展的站点权限也不等同于宿主允许操作全部网站。已经被宿主明确拒绝的目标不能改走 Relay、RDC 或 CDP。

## 1. 先读取 Windows 上下文

此命令不需要 `config.local.json`，不建立 state，不改变前台、不移动鼠标，不请求提升。

```powershell
python -m rdc_operator windows-preflight
python -m rdc_operator windows-preflight --window 123456
```

`123456` 仅是示例，必须换成已观察的目标 HWND。无目标调用只采集当前运行上下文：普通桌面通常返回 `unknown`，包含 `target_not_provided`；如果已观察到明确桌面冲突，`blocked` 优先。这些结果都不代表已经获得操作权限。

返回信息包含自身与目标的 PID、session、创建时间、token integrity RID、elevation、UIAccess，当前 window station、thread/input desktop 与前后 foreground HWND。它不读取目标标题、页面文字或凭据。

| `assessment.status` | 含义 | CLI 退出码 |
|---|---|---|
| `observed` | 此次采集未发现列出的冲突 | 0 |
| `blocked` | 已观察到具体不匹配，例如目标不是前台或 session 不同 | 1 |
| `unknown` | 必要信息缺失、状态不稳定或没有指定目标 | 1 |
| `unsupported` | 运行平台不是 Windows | 1 |

非法参数走 CLI usage / KitError，通常为退出码 2。退出 0 不代表获得权限，也不保证下一次点击成功；用户输入、其它应用和桌面状态仍可在探测后变化。每个报告保留 `input_performed: false`、`permission_granted: false`、`uac_state: not_determined`。

本版不查询 RDP 连接状态，不把 `OpenInputDesktop` 成功等同于会话在线。`GetForegroundWindow()==0` 也不是“检测到 UAC”。这些情况保留具体 native error 和 unknown。[1][2]

## 2. 明确聚焦，再点击与验收

`desktop.focus` 是新增的独立修改动作。它需要一份当前 state 中未过期的 observation，且只能聚焦其中绑定的 HWND；不接收任意坐标、外部 PID、`force` 或其它新目标。

先观察：

```json
{"request_id":"owned-observe-001","action":"desktop.observe","args":{"window":123456}}
```

从结果取得真实 `observation_id` 后，创建新的请求文件：

```json
{"request_id":"owned-focus-001","action":"desktop.focus","args":{"observation_id":"obs-REPLACE-WITH-OBSERVED-ID"}}
```

```powershell
python -m rdc_operator --config config.local.json --state .rdc-state call focus.json --apply
```

Kit 先核对原 observation 的 HWND、PID、创建时间和可执行文件身份，再调用固定版 `winapp ui focus -w`。上游正常请求激活，可能恢复最小化窗口；Kit 随后再次观察并独立读取 foreground HWND。只有身份和前台均吻合才返回 `completed` / `focus_effect_verified: true`。[3]

点击时使用聚焦结果中的新 observation 和它实际列出的 selector。点击仍受 winapp 的前台保护，**不会在 click 内自动聚焦或重发**。之后读取控件状态或独立文件见证；focus 成功不是按钮业务动作成功。

若 focus 非零退出，窗口可能已经从最小化恢复，因此本版保留 `outcome_unknown`。不能简单当成“无副作用”。同一 request ID 读取保存回执，不再发出第二次 focus；先核实当前状态，再决定是否有新的获准动作。

## 3. 如何处理 UAC 和高权限应用

`SendInput` 受 UIPI 限制，允许向相同或更低 integrity 的应用注入输入；返回成功插入的事件数量，不是业务结果。它的错误值本身不能唯一诊断 UIPI。[4]

`PostMessage` 同样受 UIPI，不能把换接口视为普遍跨权限方案。当前某些上游说明存在与 Win32 基础 API 合同不一致的表述，本项目以 Microsoft API 文档和实际回执为依据。[5]

UAC 默认将确认放到安全桌面；Microsoft 建议保留这层保护。合法 UIAccess 应用另有签名、可信安装位置、manifest 与用户授权要求，普通 Python 脚本不能靠一个标志自动获得这些条件。[6][7]

本版提供诊断和交接流程：

1. 指明需要提升的具体程序、目标操作与原因。
2. 保留正常 Windows 提升确认，由用户核对并同意。
3. 用户返回后重新读取 HWND、token、session、desktop 与前台状态。
4. 以新的观察执行授权范围内的动作，保留独立结果见证。

本版不自动点击 UAC，不修改 secure-desktop/UAC 策略，不安装特权服务，不创建绕过确认的计划任务。已提升应用、锁屏、跨用户桌面仍需专门验收，不能从普通 fixture 通过推导它们通过。

## 4. 一次有界 Windows 验收

`scripts/smoke_windows.py` 负责串行调用现有 smoke，持续保存 `summary.json`，把每个 case、跳过、deadline 和 cleanup 分开记录。输出目录必须是新的，不能覆盖已有证据。

```powershell
python .\scripts\smoke_windows.py `
  --config .\config.local.json `
  --python 'C:\Path\To\Python\python.exe' `
  --terminal-python 'C:\Path\To\Kit\.venv\Scripts\python.exe' `
  --powershell 'C:\Program Files\PowerShell\7\pwsh.exe' `
  --mcp-python 'C:\Path\To\Kit\.venv-mcp\Scripts\python.exe' `
  --output '.\evidence\windows-run-UNIQUE' `
  --deadline-seconds 600
```

路径是示意，请使用本机确实存在的绝对路径。`--python` 选择真实基础解释器；`--terminal-python` 选择已安装 SmartCLI 的环境，既有终端 smoke 会核对该环境的 distribution metadata；`--powershell` 选择实际 PowerShell 可执行文件，避免 PATH 中同名 redirector 把 fixture 的 Popen PID 与真实 GUI PID 分开。MCP 参数可省略，此时明确记录 skipped，整体为 incomplete。

退出码 0 仅表示九个计划 case 都通过；失败或不确定清理为 1，有跳过或未执行为 2。runner 从当前源码运行，不能单靠它证明已安装的包也是同一版。总 deadline 为等待与清理预留预算，原生 OS 调用和磁盘写入不是硬实时承诺。

范围包括核心回归、doctor、9 场景 liveness、真实 REPL/TUI、可选 readonly MCP、六个浏览器离线证据样例、OMP dry-run、两个拥有的 WinForms fixture。它不发真实模型请求，也不启动浏览器自动化。官方 Edge 的交互单独执行并报告。

现有 smoke 各有自己的 owned state，runner 串行调度并引用其报告；这不是全系统桌面锁，也不能用新 state 绕开其它调用的 busy。GUI 必须同时通过 Popen PID、fresh witness 和 kernel identity 核对；只正常关闭本次确认归属的窗口，不按程序名称批量终止。

## 5. 浏览器测试与恢复

本轮官方 Edge 的 localhost Lab 已实际完成文字填写、语义点击、截图定位鼠标点击、延迟结果、ACK 无业务效果、epoch reset 与 document reload。页面自身的 DOM witness 与调用回执分开读取；实际 trace 与限界记录在第四轮报告。

独立 Playwright smoke 是可选开发工具，不属于 Kit 核心依赖。需要自行准备适合运行环境的 Playwright 与浏览器；无依赖、启动失败和环境策略拒绝都保存 summary，不算功能通过。上一轮 Linux `file://` 被管理员策略拒绝，本轮没有重新尝试或改 transport 规避该拒绝。

官方 Browser 可正常完成的页面无需经过 OMP Relay。Relay 仍是单独的、已有授权和安装要求的能力，不是遇到策略拒绝时的自动降级机制。网络断开或响应丢失时，先读现有 tab / witness / receipt；不能把 timeout 解释为点击没有发生。[8]

## 来源

1. [GetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow)
2. [OpenInputDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop)
3. [winapp v0.8.0 UiFocusCommand.cs](https://github.com/microsoft/winappCli/blob/v0.8.0/src/winapp-CLI/WinApp.Cli/Commands/UiFocusCommand.cs)
4. [SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
5. [PostMessageW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew)
6. [How User Account Control works](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/how-it-works)
7. [Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)
8. [Troubleshoot remote MCP server](https://learn.microsoft.com/en-us/azure/app-testing/playwright-cloud-browsers/troubleshoot-remote-mcp-server)
