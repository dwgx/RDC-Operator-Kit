# RDC Operator Kit 使用指南

当前源码：`0.1.0a6` candidate，状态日期 2026-11-28（Asia/Tokyo）。Windows／Linux 已安装包及恢复验证已完成；a6 GitHub CI、Release、Pages 仍待最终回执，见[第六轮报告](REVIEW-WAVE6.zh-CN.md)与[安装发布状态](RELEASE.zh-CN.md)。

**[Agent 使用与交接](AGENT-GUIDE.zh-CN.md) · [恢复规格](RESUME-SPEC.zh-CN.md) · [当前能力](CAPABILITIES.zh-CN.md) · [各轮验证记录](VERIFICATION.zh-CN.md)**

已公开的固定版本仍为 [v0.1.0a5 Release](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a5)。它的 tag 固定在 `27d367a9698c381d90986c8640d506b24d84ddd9`，六个 CI job、Pages 与九项资产下载哈希已核对，历史回执见[第五轮报告](REVIEW-WAVE5.zh-CN.md)。下面标有 a5 的下载／wheel 命令安装该历史版本，不会提供 a6 的恢复命令；不移动旧 tag 或替换资产。

Windows 操作步骤见 [Windows 操控指南](WINDOWS-CONTROL.zh-CN.md)。[第四轮验收报告](REVIEW-WAVE4.zh-CN.md)与 [a2 第二轮报告](research-wave2/REPORT.zh-CN.md)保留原版本证据；a4 最终 Windows 顶层 suite 8/9 passed、exit 1 不会被后续通过覆盖。

RDC Operator Kit 为已获授权的电脑操作提供一条可核对的路径：读取当前状态，绑定目标，执行一次，再检查结果。它通过已有 RDC 传输调用本地 CLI，用 SmartCLI 控制终端，用 Microsoft winapp 控制 Windows 原生界面。网页交互使用宿主提供的官方 Browser 插件。

a5 新增三个只读 MCP 工具的输出 schema，以及不暴露原始任务参数的保存记录摘要；修复 Linux 安装目录链接与 liveness 中断丢失报告问题；更新静态首页和 Browser Evidence Lab 的浅色／深色布局与证据检索。新版视觉目前只经过源码和合成事件检查，不能把 a4 的网页操作结果当作 a5 浏览器验收。

## a6：用户手动重连后继续原任务

先确定任务是否需要设备操作。网页 UI 使用当前宿主的官方 Browser Skill；只读已保存记录直接读记录，两者都不要求额外 RDC discovery 或 doctor。确需 RDC 时重新发现当前连接和设备，保留旧任务授权与停止原因，并按新工具 schema 操作。用户手动登录完成，不代表旧 PID、call ID、tab 或截图仍可使用。

已经确认使用 a6 时，保留原 config、原 state、原 request 文件和私有任务正文。按照[完整 Agent 指南](AGENT-GUIDE.zh-CN.md)准备文档，再执行：

```text
python -B -m rdc_operator --config config.local.json --state .rdc-state checkpoint recovery-checkpoint.local.json --expected-revision 0
python -B -m rdc_operator --config config.local.json --state .rdc-state resume TASK_ID --context recovery-context.local.json
```

`TASK_ID` 替换为原检查点任务；只有首次创建用 revision 0，后续必须使用读到的当前 revision。两个命令都要求显式原 `--state`，不能新建目录来消除未知效果。checkpoint 写入本地检查点；resume 只生成 `blocked` 或 `review_required` 计划，exit 0 不授予执行许可，也不自动重试。`-B` 防止导入生成 Python 缓存；不承诺 OS 访问时间或宿主日志不变。

相同 ID 的 `user_reconnected` 也建立新连接代次；未知结果先查独立业务证据，再重新观察目标。`quota`、`policy_refused`、`cancelled` 保留，不能通过新账号、凭据、state 或任务 ID 清除。本机制不是所有 `call`／RDC 操作的全局拦截器，Agent 必须继续落实原授权和停止边界。a5 只做人工对账；不因为需要新命令便自动升级或改账号。

当前源码 core：Linux 225 run／221 pass／4 skip，Windows 225／212／13；两系统 source recovery smoke 各 17/17。Windows 两个已安装环境各 12 模块匹配 wheel，installed recovery 各 17/17，Linux 新隔离安装环境也为 17/17；另有真实 installed 现代 MCP 17 项。环境与反例见[第六轮报告](REVIEW-WAVE6.zh-CN.md)，这些分项不合并为一次任意应用验收。

## 安装

以下固定下载示例保留 a5 已公开版本。a6 的候选安装结果与待发布状态见[发布检查点](RELEASE.zh-CN.md)，不要猜测尚未公布的资产链接。

### Windows

准备 Python 3.10 或更新版本，从已发布的 [Release](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a5) 下载并核验源码 ZIP，或按[固定 tag clone 步骤](RELEASE.zh-CN.md)取得完整源码，放入专用目录。在该目录打开 PowerShell，运行：

```powershell
.\scripts\install.ps1 -WithTerminal -WithDesktop
.\.venv\Scripts\python.exe -m rdc_operator --config config.local.json doctor
```

仅安装 CLI 核心时运行 `.\scripts\install.ps1`。`-WithTerminal` 安装固定版本 `smartcli-toolkit==0.3.5`；`-WithDesktop` 下载并校验 Microsoft winapp `0.8.0` 的 x64 或 ARM64 归档。首次安装需要访问 Python 包源；桌面组件还需要访问 GitHub Releases。核心运行代码只依赖 Python 标准库，安装时的构建工具仍可能由 pip 下载。

安装器在源码目录建立 `.venv`，不修改全局 PATH、不安装系统服务、不创建定时任务。它拒绝采用未拥有的 `.venv`，拒绝相关安装路径的链接，并在执行 WinApp 前比较归档及安装内容。SmartCLI 的直接版本固定，传递依赖仍由 pip 解析，当前没有完整的可复现依赖锁。

重复安装保留 `config.local.json`。如果首次只安装核心，后来增加可选组件，需要把新组件路径明确加入已有配置。安装器不会代替你配对 RDC，也不会读取或复制 RDC 的登录令牌；RDC 应按其[官方说明](https://desktopcommander.app/)安装、登录和连接。

### 已有 Windows 环境的离线 wheel 升级

如果已有归属明确、依赖就绪的 `.venv` 或 `.venv-mcp`，可从 [v0.1.0a5 Release](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a5) 取得 `rdc_operator_kit-0.1.0a5-py3-none-any.whl` 和同批 `SHA256SUMS.txt`，核验后仅升级 Kit。a5 最终 wheel 已在两个自有 Windows 环境安装并逐一核对 11 个模块；实际 installed CLI 与现代 MCP 的有限验证见第五轮报告第 11 节。先保留当前源码、已安装 Kit、配置和状态的备份，核对本地修改；下例在已有项目根目录运行，假定这两个发行文件已放在该目录。

先检查同名校验条目与实际文件一致；缺少条目、重复条目或摘要不符均停止：

```powershell
$wheelName = 'rdc_operator_kit-0.1.0a5-py3-none-any.whl'
$checksumRows = @(Get-Content -LiteralPath .\SHA256SUMS.txt | Where-Object {
  $_ -match ('^[0-9a-fA-F]{64}\s+\*?' + [regex]::Escape($wheelName) + '$')
})
if ($checksumRows.Count -ne 1) { throw 'Missing or duplicate wheel checksum' }
$expectedWheelHash = ($checksumRows[0] -split '\s+', 2)[0]
$actualWheelHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path '.' $wheelName)).Hash
if ($actualWheelHash -ne $expectedWheelHash) { throw 'Wheel SHA-256 mismatch' }
```

核验通过后，对原有主环境执行：

```powershell
& .\.venv\Scripts\python.exe -m pip install --no-index --no-deps --force-reinstall .\rdc_operator_kit-0.1.0a5-py3-none-any.whl
```

若另外配置了独立 MCP 环境，在同一已核验文件上单独执行：

```powershell
& .\.venv-mcp\Scripts\python.exe -m pip install --no-index --no-deps --force-reinstall .\rdc_operator_kit-0.1.0a5-py3-none-any.whl
```

wheel 只安装 Kit 的 Python 包，不安装或升级 SmartCLI、MCP SDK、winapp、Skill、测试夹具或网页，也不会同步源码目录。保留终端与 MCP 的分离环境；新机器或依赖尚未准备好的机器继续使用上面的完整源码安装流程。校验和用于核对交付字节，不能代替来源核验。a4 的 a2→a4 升级记录仍见 [第四轮报告](REVIEW-WAVE4.zh-CN.md)，a5 的独立安装证据另见第五轮；两者不混算，source-tree smoke 也不等于 installed-package 全套通过。

### Linux

```bash
bash scripts/install.sh --with-terminal
.venv/bin/python -m rdc_operator --config config.local.json doctor
```

Linux 支持 CLI 核心和 SmartCLI 路线。Windows UIA 操作返回 `unsupported_platform`。本项目的真实终端 smoke 脚本使用 Windows 进程句柄确认退出，不能把它的结果冒用为 Linux 实测；Linux 的具体覆盖见验证记录。

a5 在解释器执行前拒绝 `.venv/bin` 目录为 symlink 的路径，仍允许普通 venv 的 `bin/python` 指向基础解释器。该修复经过本地 Linux 隔离夹具和独立反例核对，不表示完成所有 Linux 安装或真实 PTY 验收。HMC 的首个环境探测因 RDC 月度额度而被阻断，没有取得其 OS、Python 或工具版本；本地结果不会替代 HMC 真机结果。

## 配置与诊断

以下是配置形状，路径须替换为自己的绝对路径：

```json
{
  "schema_version": 1,
  "allowed_roots": ["D:/Tools/RDC-Operator-Kit"],
  "smartcli": ["D:/Tools/RDC-Operator-Kit/.venv/Scripts/smartcli-tui.exe"],
  "winapp": ["D:/Tools/RDC-Operator-Kit/tools/winapp-0.8.0/winapp.exe"],
  "observation_ttl_seconds": 120
}
```

只配置实际使用的适配器。`doctor` 区分未配置、探测失败和可执行程序可用；它不证明终端输入、GUI 操作或模型调用已经成功，也不会探测浏览器登录状态。

从 a4 起，可先运行独立的只读 Windows 输入上下文诊断；它不是 `call` action，不需要配置或 state，也不发送输入或请求提升：

```powershell
.\.venv\Scripts\python.exe -m rdc_operator windows-preflight
# $targetHwnd 必须来自本轮实际观察；需要检查目标时才加入 --window。
.\.venv\Scripts\python.exe -m rdc_operator windows-preflight --window $targetHwnd
```

`assessment.status` 分为 `observed`、`blocked`、`unknown`、`unsupported`。普通桌面不指定目标通常为 `unknown / target_not_provided`；已观察到明确冲突时 `blocked` 优先。只有 observed 返回 exit 0，其余三态为 1，非法参数为 2；任何结果都不授予操作权限，也不证明 UAC 可控。普通桌面、已提升应用和 secure desktop 的区别及正常用户确认流程见 [Windows 操控指南](WINDOWS-CONTROL.zh-CN.md)。

`allowed_roots` 约束 Kit 自己处理的 cwd、brief 和截图输出路径；终端启动的程序仍拥有当前 OS 用户权限。配置中的可执行程序路径属于可信操作员配置，不是请求可以任意改写的工具路由。

## 请求与回执

请求必须是 UTF-8 JSON，且只含 `request_id`、`action` 和 `args`。ID 使用 1–64 个 ASCII 字母、数字、下划线或连字符，首字符为字母或数字，避免 Windows 保留设备名。

```json
{
  "request_id": "terminal-start-001",
  "action": "terminal.start",
  "args": {
    "session": "demo-shell-001",
    "command": "powershell.exe -NoLogo -NoProfile",
    "cwd": "D:/Tools/RDC-Operator-Kit",
    "cols": 100,
    "rows": 30
  }
}
```

把路径改为允许的工作目录，保存为 `request.json`，再执行已授权的动作：

```powershell
.\.venv\Scripts\python.exe -m rdc_operator --config config.local.json --state .rdc-state call request.json --apply
```

`--config`、`--state` 放在子命令前；`--apply` 放在 `call` 子命令后。`--apply` 是执行开关，不能代替用户对具体任务的授权。读取保存结果：

```powershell
.\.venv\Scripts\python.exe -m rdc_operator --config config.local.json --state .rdc-state receipt terminal-start-001
```

同一 ID、同一请求和同一配置再次 `call`，返回原回执并标记 `replayed: true`，不会再执行。它不是“刷新状态”：要获取新的观察，使用新的请求 ID。同 ID 改动请求或配置会冲突。若只有 intent、没有最终回执，结果可能已经发生；保留记录、观察目标和独立产物，不能删记录或换 ID 盲目重跑。

退出码 `0` 表示返回观察或完成结果；`1` 表示回执为 `failed` 或 `outcome_unknown`；`2` 表示请求被拒绝或发生接口/存储错误。详细状态与业务验证信息在 JSON 中。

## 终端操作

| action | 主要参数 | 含义 |
|---|---|---|
| `terminal.start` | `session`, `command`, `cwd`, 可选 `cols` / `rows` | 新建 Kit 拥有的 SmartCLI 会话 |
| `terminal.snapshot` | `session` | 读取当前终端表示与存活信号 |
| `terminal.wait` | `session`, 可选 `pattern` / `timeout_ms` | 等待指定文本或受支持的稳定条件 |
| `terminal.send_text` | `session`, `text`, 可选 `newline` | 输入文本；`newline: true` 另发一次 Enter |
| `terminal.send_key` | `session`, `key` | 发送明确支持的键，如 `Down`、`Enter`、`C-c` |
| `terminal.close` | `session` | 请求关闭，保留会话归属及不确定信息 |

start、send 和 close 需要 `--apply`。会话名不能复用；Kit 只接管它记录拥有的会话。`command` 是 SmartCLI 定义的命令字符串，不能把它当作跨平台 argv 数组或受限脚本语言。

当前 Windows/PyWinPTY 路线不支持以引号包住可执行文件的首 token，Kit 会提前返回 `unsupported_command_quoting`。把 `cwd` 设为项目目录，可使用 `.venv\Scripts\python.exe -i` 这样的相对命令；不要把含空格的绝对 Python 路径放到引号里当成已支持。中文与空格工作目录的这种相对命令形式已在真实 TUI 上验证。

输入例子：

```json
{
  "request_id": "terminal-input-001",
  "action": "terminal.send_text",
  "args": {"session": "demo-shell-001", "text": "'RDC Operator Kit READY'", "newline": true}
}
```

输入文本不能以 CR/LF 结尾，使用 `newline` 表达 Enter。正则等待的 pattern 不能以 `-` 开头；如需匹配该字符，可使用 `(?:-example)`。不要把屏幕中的命令回显当成计算结果；文件内容、独立程序状态或精确的结果行更适合作为验收证据。

SmartCLI `0.3.5` 的 CLI 没有暴露完整的 daemon 关闭回执，所以 Kit 的 close 保守返回 `outcome_unknown`。这不等于关闭必定失败，也不证明所有子进程退出。正常退出程序后，通过独立证据确认，不要按名字批量杀死进程。

## Windows 桌面操作

先取得当前窗口句柄：

```powershell
.\tools\winapp-0.8.0\winapp.exe ui list-windows --json
```

从当次输出选择目标 HWND。创建 `desktop.observe` 请求，`args` 为 `{"window": 实际数字}`，使用 `call` 读取。返回的 `result.observation_id`、UI 树和 selector 是后续操作的依据，不能复制文档里的示例数字作为真实目标。

| action | 参数 | 验证内容 |
|---|---|---|
| `desktop.observe` | `window` | HWND、PID、进程创建时间、UI 树 |
| `desktop.focus` | `observation_id` | 显式聚焦已观察的精确顶层 HWND，核对身份、foreground 与新观察 |
| `desktop.set_value` | `observation_id`, `selector`, `value` | 绑定实际元素，设置值后读取核对 |
| `desktop.invoke` | `observation_id`, `selector` | 明确使用 InvokePattern，核对动作确认和新状态 |
| `desktop.click` | `observation_id`, `selector` | 对已观察元素点击，核对目标和新状态 |
| `desktop.screenshot` | `window`, `output`；可选 `observation_id` | 核对单窗来源；新 `.png` 路径必须位于 allowed_roots；已有观察时传入其 ID |

除 observe 外均需要 `--apply`。观察默认 120 秒过期，允许配置的上限为 300 秒。操作前会在指定窗口内重新绑定实际元素、检查可见与可用状态，并复核进程身份。普通 UIA 和真实鼠标输入的条件不同；点击、焦点操作及某些截图需要可交互桌面。

`desktop.focus` 不接收新目标或 `force`；它在调用上游前拒绝已经重挂、不再是同一顶层窗口的目标。成功后，后续 click 使用 `result.observation.observation_id` 和新观察中的 selector。上游 ACK 为 0 但 foreground 不匹配仍会留下 `outcome_unknown / focus_unverified`；此时停止后续点击，核对回执与当前状态，不能自动重试。同 ID 重放也不会再次聚焦。具体请求顺序见 [Windows 操控指南](WINDOWS-CONTROL.zh-CN.md)。

窗口消失、元素不唯一、目标失效或结果无法确认时，保留回执并重新观察。`invoke` 或 `click` 的成功确认不等于你的业务目标达成，仍需读取结果。浏览器目标使用官方 Browser 插件；Browser 拒绝操作时不能改用此桌面接口绕过。

## 在专用夹具上验证

a4 提供有截止时间的 `scripts/smoke_windows.py`，串行执行 core、doctor、liveness、terminal、mcp、browser_offline、omp_preview、desktop、observation 九项 case。完整命令见 [Windows 操控指南](WINDOWS-CONTROL.zh-CN.md)：分别指定真实基础解释器 `--python`、已有 SmartCLI 环境 `--terminal-python`、独立 MCP 环境 `--mcp-python`，以及实际 `pwsh.exe`、新输出目录与 `--deadline-seconds 600`。它仅清理本次确认归属的夹具，输出保留失败、跳过与 unknown；从源码运行不等于已安装包验证。浏览器项为离线证据校验，OMP 项为 dry-run；真实 Edge 与模型调用另行报告。

核心及离线反例测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Windows 真实终端测试只新建自己的 REPL/TUI 会话，生成独立文件见证并检查退出：

```powershell
.\.venv\Scripts\python.exe scripts\smoke_terminal.py --config config.local.json
```

桌面测试先在一个 PowerShell 窗口启动专用测试程序：

```powershell
.\examples\desktop-fixture.ps1
```

保持该测试窗口开启，在另一个终端运行：

```powershell
.\.venv\Scripts\python.exe scripts\smoke_desktop.py --config config.local.json --witness evidence\gui-fixture.json --output evidence\desktop-smoke-001.json
```

重跑时选择新的 output 文件名；截图不会覆盖既有文件。测试会设置合成文本、调用按钮、检查独立文件、捕获专用窗口，并验证相同请求不会点击第二次。结束后关闭测试窗口。`evidence/` 是私有运行产物，不应加入公开提交。

## 有限画面采样与终端诊断

自 `0.1.0a2` 起，Kit 为每个验收通过的截图提供 frame ID、文件 SHA-256、目标身份和捕获命令起止时间。真实渲染帧时间没有由 winapp 暴露，因此 `captured_at=null`、`pixel_freshness=unproven`；新文件和新 frame ID 都不等于新渲染帧。多窗口 composite、路径/PID/HWND/尺寸不一致会保留 unknown，不成为单窗证据。PNG 只校验头部，不声称完整解码或已看图。

在已授权的原生窗口上，使用与其他操作相同的 state，采集有限数量图片：

```powershell
# $targetHwnd 必须来自本轮对授权窗口的实际发现；输出目录必须是新目录。
.\.venv\Scripts\python.exe scripts\sample_desktop.py --config config.local.json --state .rdc-state --window $targetHwnd --output (Join-Path (Get-Location) 'evidence/sample-001') --frames 3 --interval-ms 500 --start-deadline-seconds 30 --apply
```

每帧先写入 manifest 再输出一行 JSON，RDC 返回运行中的 PID 后继续读取该进程。上限为 12 帧，开始下一帧的截止上限为 60 秒；已经开始的一次 capture 仍受自己的 30 秒调用超时约束。截图可能恢复或置前窗口。这是有限采样，不是视频直播。采样器绑定同一短效 observation，过期或换目标即停止；不会自动刷新原观察继续操作。

固定的终端存活性探针可在 Windows 和 Linux 运行：

```text
python scripts/probe_terminal_liveness.py
```

它仅新建自己的合成进程，不接管任意 PID。静默运行、无提示等待输入、输出洪泛、超时、只有提示符、只有完成 marker 等都有反例。Windows 使用当前 CPython 的实体 base interpreter，避免 venv redirector 的 PID 与真正执行者不同。详细状态与清理边界见 [终端研究](research-wave2/TERMINAL-LIVENESS.zh-CN.md)。

a5 在首个 case 前、每项前后和收尾持续原子保存报告，启动异常、中断或写入失败时保留已返回的结果并停止后续 case。正常通过为 exit 0，功能／启动失败为 1，中断为 130，非中断的归档失败为 3。读取 stdout 的 `summary_current` 并结合退出码判断归档是否代表本次结果；若最终 PASS 已落盘但后续写入持续失败，旧文件可能仍写着 PASS，此时返回 `FAIL`、非零退出及 `summary_current: false`。不要只凭一个旧 summary 判断成功。

`scripts/verify_browser_evidence.py` 与 `site/lab.html` 提供离线浏览器证据校验和无账号测试页；离线正例只证明输入内部自洽。它不控制浏览器、认证来源或授予网站访问。用法见 [Browser Evidence](research-wave2/BROWSER-EVIDENCE-USAGE.zh-CN.md)。

## OMP、Codex、MCP 和 Skills

`omp.preview` 复用已经安装的 `origin-dispatch`，只执行 `--dry-run`。在配置中加入 `omp.python` 与 `omp.wrapper` 的绝对路径，请求提供 `job`、`brief`、`cwd`、`model` 和 `effort`。它不会新建模型路由或运行真实模型任务。真实 dispatch 仍须按既有 wrapper 和该项目的授权执行。

Codex、OMP 或其他本地 Agent 可调用同一 CLI。RDC 使用者先确认实际 device/account，再把这些命令传给该设备；异步调用要读取原来的 PID 或 call ID，不能因尚未返回而重复启动。

可分发的路由 Skill 在 [`skills/rdc-operator-kit/`](https://github.com/dwgx/RDC-Operator-Kit/tree/v0.1.0a6/skills/rdc-operator-kit)。按宿主的 Skill 导入方式使用；上传文件不等于安装了 RDC、连接了浏览器或授予了电脑权限。ChatGPT 的浏览器工具与设备可用性取决于当前环境，不能由这个仓库保证。

可选 stdio MCP 配套见 [MCP 安装及使用](MCP.zh-CN.md)。a5 提供以下三个只读工具；第五轮首次 Windows SDK 2.3.0 的两个协议会话已实际运行，后续独立 review 又发现 smoke 判定缺口。修复与最终复验进展以第五轮报告为准，不能继承旧版两工具的通过结论。

| 工具 | 用途与返回边界 |
|---|---|
| `operator_capabilities` | 描述静态配置形状；不探测程序是否可用，不返回配置路径 |
| `operator_receipt` | 读取一个原始保存回执；其中可能包含原任务私有路径或输出，不是自动脱敏导出 |
| `operator_request_status` | 读取同一 ID 的 intent/receipt 两轮，只返回固定记录状态、理由与已保存 status；不返回原 args、command、path、action 或 digest |

三个工具公开并绑定输出模型，仍同时返回 JSON 文本与结构化内容。状态摘要不是实时任务状态：没有 receipt 不代表仍在运行，没有记录不证明动作从未发生，已有 `completed` 也不替代业务效果验收。`snapshot_atomic: false` 保留跨文件读取的竞态边界，接口不执行、取消或重试动作。它面向能够启动本地进程的 Agent；本地 stdio 并不会自动成为云端 ChatGPT 可达的 HTTPS 服务。

## 停用、更新与排错

停用时先正常退出本次拥有的程序，核对终端与窗口状态，再归档需要保留的配置和回执。本项目没有一键卸载器；确认没有使用该目录的活跃任务后，可移走这个专用源码目录及其本地 `.venv` / `tools`。不要删除其他 RDC、SmartCLI 或 Agent 的全局服务。升级时保留状态，审查配置差异，并使用新请求 ID 开始新的操作。

| 结果 | 下一步 |
|---|---|
| `dependency_unconfigured` / `probe_failed` | 检查当前配置中的实际可执行文件及版本 |
| `busy` | 读取当前拥有者的结果，等待其释放；不删除锁文件 |
| `request_conflict` | 保留原 ID 的含义，核对请求与配置变更 |
| `outcome_unknown` | 检查当前目标和独立见证，停止自动重试 |
| `checkpoint_conflict` | 回读原检查点 revision，保留较新 writer 的记录 |
| `checkpoint_commit_unconfirmed` | 提交可能已落盘；先只读核对，不重发保存或业务动作 |
| `stale_observation` / `target_changed` | 新建 observe，重新选择目标 |
| `browser_surface_required` | 转回宿主官方 Browser 插件，遵守其能力和策略 |

架构约束见 [ARCHITECTURE](ARCHITECTURE.zh-CN.md)，准备公开发布的步骤见 [RELEASE](RELEASE.zh-CN.md)。
