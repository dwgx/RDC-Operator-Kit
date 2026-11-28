# 能力与边界

日期：2026-11-28（Asia/Tokyo）。当前版本为已发布的 `0.1.0a6` alpha；已安装包、公开 CI、Release 资产下载回读与 Pages 部署均已核验，见[第六轮报告](REVIEW-WAVE6.zh-CN.md)。本文定义源码接口及条件，不能凭接口存在推定当前宿主已经提供、许可或安装该能力。

a5 是已经[公开发布](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a5)的历史 alpha，固定 tag 提交为 `27d367a9698c381d90986c8640d506b24d84ddd9`，[网站](https://dwgx.github.io/RDC-Operator-Kit/)也有成功部署回执；详见[第五轮报告](REVIEW-WAVE5.zh-CN.md)。[验证记录](VERIFICATION.zh-CN.md)、[第二轮](research-wave2/REPORT.zh-CN.md)、[第三轮](REVIEW-WAVE3.zh-CN.md)和[第四轮](REVIEW-WAVE4.zh-CN.md)保留原环境与失败，不自动成为 a6 的 live 验收。

## 从任务选择路线

| 你要做的事 | 路线 | 需要的条件 |
|---|---|---|
| 读写项目文件、搜索、运行脚本 | Remote Desktop Commander | 明确的账号与设备；RDC agent 在线 |
| 驱动交互终端、读取 TUI 当前屏幕 | Kit → SmartCLI | SmartCLI 可用；会话由 Kit 创建和记录 |
| 操作 Windows 应用控件 | Kit → winapp UIA | 明确的 HWND、当前观察记录、目标进程一致 |
| 诊断 Windows 输入条件 | `windows-preflight` 只读 CLI | 可选 exact HWND；读取事实，不申请权限或发送输入 |
| 请求已观察窗口获得前台 | `desktop.focus` → winapp | 未过期 observation、同一顶层 HWND、明确执行与前台回读 |
| 查看指定应用窗口截图 | Kit → winapp screenshot → RDC 图像读取 | 明确窗口、可用桌面、允许的输出目录 |
| 操作明确指定的网页 UI | 当前宿主官方 Browser 插件与 `control-browser` Skill | 尊重用户选定浏览器及当前 Chat／Work 模式；目标 origin 获得策略许可，不另用 CDP 绕过 |
| 派发已有本地 OMP 工作 | 已安装的 `origin-dispatch` wrapper | 现行路由、冻结 brief、独占写入范围、真实回执 |
| 使用本机 Codex | 其正式 CLI 或经过验证的终端路线 | 先核实已安装版本、参数、账号与当前授权 |
| 有限地连续观察原生窗口 | `scripts/sample_desktop.py` | 同一 observation、同一 state；每帧保存 manifest；最多 12 帧 |
| 诊断静默、洪泛、等待输入和超时的区别 | `scripts/probe_terminal_liveness.py` | 只新建自有合成 fixture；不能据此接管任意 PID |
| 校验已有浏览器证据包 | `scripts/verify_browser_evidence.py` | 离线检查内部一致性；不授予 origin 访问、不执行浏览器动作 |
| 由本地 MCP host 读取 Kit 回执或最小记录摘要 | 独立 `.venv-mcp` 的三个只读 stdio 工具 | 官方 SDK 2.3.0；与 SmartCLI 的 MCP 1.x 环境分开；保存记录不是实时状态 |
| 保存已授权任务的恢复检查点 | a6 `checkpoint` CLI | 原 config/state，明确 expected revision，私有任务正文与来源材料 |
| 手动重连后核对原任务 | a6 `resume` CLI；a5 人工对账 | fresh route、原 state/marker；只读计划，不执行或重放 |
| 检索公开能力与证据说明 | `site/` 静态页面的本地搜索与分类筛选 | 不传出查询，不连接或控制设备；新版视觉尚未浏览器验收 |
| 串行运行 Windows 自有 fixture | `scripts/smoke_windows.py` | 完整源码、新证据目录、实际基础 Python 和 PowerShell；依赖环境分别指定 |

网页 UI 与保存记录任务不为使用本 Skill 而额外发现 RDC 或运行 doctor。网页信息检索按任务选择可用的语义工具；实际浏览器操作遵守当前宿主 Skill，不把 URL 本身当作任意自动化许可。完整路由和交接步骤见[Agent 指南](AGENT-GUIDE.zh-CN.md)。

### 浏览器：历史结果与继续保留的拒绝

第四轮已通过官方 **Edge** 能力在自有 localhost Lab 执行文字填写、语义按钮点击、延迟效果、按截图定位的鼠标点击，以及 epoch reset 和 document reload。动作后的页面 witness 单独读取，ACK 回显与计数效果分开核对。该证据只覆盖已执行的自有页面操作；完整序列、采集器错误与协调记录见第四轮报告。

历史测试导航到 `https://chatgpt.com` 时，Browser 返回 `host restrictions gate did not grant access for https://chatgpt.com`，状态为 **`BLOCKED_BY_POLICY`**。第四轮没有重新尝试该目标。扩展显示“Allowed on all sites”不取消这项宿主拒绝；不得改用桌面坐标、OMP Relay、CDP 或 shell 绕过。ChatGPT 网页开新聊天、切模型及“所有功能”仍不属于已验收范围。

后续 a4 首页检查中的 Markdown 导航返回 `ERR_BLOCKED_BY_CLIENT`，返回同一 localhost origin 的操作又遭自动审批拒绝。该 origin 的浏览器验证已停止，没有经其他传输或渲染器继续。a5 对首页与 Lab 的视觉更新只有静态／合成事件检查；旧截图、旧点击坐标和旧版本的交互通过均不证明新版布局已验收。

## a6 检查点与只读恢复

[`recovery.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/recovery.py) 提供 `save_checkpoint(document, config, state, expected_revision=...)` 和 `assess_resume(task_id, context, config, state)`；对应 CLI 为 `checkpoint DOCUMENT --expected-revision N`、`resume TASK_ID --context DOCUMENT`，都要求显式 `--state`。推荐 `python -B -m rdc_operator` 避免导入缓存写入。完整封闭 schema 和错误语义见[恢复规格](RESUME-SPEC.zh-CN.md)。

- checkpoint 在原 state 锁内执行 CAS，绑定精确 marker UUID 与规范路径，冻结 scope/config 指纹；request ID 只追加，旧 revision 不能覆盖新 writer。
- `user_reconnected` 即使 link/device 相同也推进 generation；仅刷新 route 时间不推进。旧 typed handles 保留来源，不能重新标成新连接有效线索。
- disconnected/auth_required 可在明确用户手动恢复和 fresh context 后复核；quota/policy_refused/cancelled 不被新路由清除。
- resume 只读原检查点和请求，返回前复核 marker/checkpoint 身份、字节、revision；不创建新 state 或自动修复记录。`snapshot_atomic: false`，返回后的变化仍可能发生。
- 计划固定 `execution_authorized`、`automatic_replay_allowed`、`actions_exposed`、`physical_device_verified`、`request_config_binding_verified` 为 false；`route_source: caller_attested`。当前 config 与历史 request 的关联不能由复合 digest 反推；scope hash 也不能恢复任务正文或证明授权。

`review_required` 的 exit 0 只表示报告生成成功；`blocked` 为 1，输入或文件错误为 2。已有 completed/observed 仍需独立业务核验；未知效果不能换 request ID 重跑。提交后回读失败返回不确定提交，先检查已保存 revision。此模块**不是所有 call／RDC 操作的全局执行拦截器**，Agent 继续承担路由、授权、停止和当前目标核对。

运行时本体只读不等于系统级沙箱；`-B` CLI 已有 fresh-copy 正向及去掉 `-B` 的反向控制，不承诺 atime、宿主日志或显式 stdout 重定向不变。源码与安装包的有限验证范围见[第六轮报告](REVIEW-WAVE6.zh-CN.md)。

## 只读 MCP 的三个接口

[`mcp_server.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/mcp_server.py) 仅使用 stdio，启动时固定 config/state；工具调用不能提供替代路径。三个工具都有可发现的 object 输出 schema 和实际输出模型，保持 JSON 文本与 `structuredContent`，成功读取与原动作成功是两件事。完整安装、schema 与错误契约见 [MCP 指南](MCP.zh-CN.md)。

| 工具 | 数据范围 | 没有执行的工作 |
|---|---|---|
| `operator_capabilities` | 版本、工具名与静态配置形状，不回传 argv 或路径 | 不运行 doctor，不探测可执行程序、设备或模型 |
| `operator_receipt` | 一个 ID 的原始保存回执，保留其中可能存在的私有内容 | 不刷新观察、不验签、不重放动作 |
| `operator_request_status` | 两轮固定记录观察的 `record_state`、固定 `reason` 与 `saved_receipt_status`；不回传原任务内容 | 不查询 live PID、执行、取消、重试或列举全部任务 |

记录状态为 `no_records_observed`、`intent_without_receipt`、`receipt_recorded` 或 `inconclusive`。它们都不等于实时运行状态；始终保留 `snapshot_atomic: false`、未做 live verification、未验证真实性和不暴露动作接口的标志。输出 schema 改善结构验证，不授予权限，也不使原 receipt 自动可信。SDK 与 Pydantic 懒加载，基础 CLI 仍不依赖 MCP extra。

## Linux 与终端诊断：沿用 a5 的范围

Linux 安装器在执行解释器前拒绝 `.venv/bin` **目录** symlink，保留正常 venv 的 `bin/python` 文件 symlink。独立隔离反例确认 a4 会运行链接目录中的外部 fixture stub，而 a5 在运行前拒绝；正常无 pip venv 能保持正确的 `sys.prefix`。这不等于联网安装或同权限恶意并发替换防护已经全面验收。

固定 liveness 探针增加每项前后的原子 checkpoint，中断、启动异常和归档失败保留已返回的结果并停止后续 case。消费报告时同时核对 exit code、stdout 状态与 `summary_current`；持续写入失败可能留下旧 PASS 文件，不能把该旧文件单独作为本次成功证据。

HMC 连接仅在设备列表可见；首个环境探测已因 RDC 月度额度停止，没有实际 OS/Python/安装或执行结果。本地 Linux 核验不代替 HMC，真实 Linux PTY 与 Linux GUI 也未因此成为已验证能力。

## Windows 输入条件诊断

`windows-preflight` 是独立只读命令，不是 `call` action，不需要配置文件、state 或 `--apply`。可用 `python -m rdc_operator windows-preflight` 读取自身上下文，再以 `--window` 指定实际观察到的 HWND。实现见 [`windows.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/windows.py) 与 [`cli.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/cli.py)。

它采集自身与目标的 PID、创建时间、session、token integrity/elevation/UIAccess，以及 window station、thread/input desktop 和 foreground。输出明确保留 `read_only: true`、`input_performed: false`、`permission_granted: false`、`uac_state: not_determined`。

| `assessment.status` | 本次采集的含义 | CLI 退出码 |
|---|---|---|
| `observed` | 列出的检查没有发现冲突 | 0 |
| `blocked` | 已观察到具体不匹配，例如不同 session、较高目标 integrity 或目标未占前台 | 1 |
| `unknown` | 必要事实缺失、采样不稳定，或未指定目标 | 1 |
| `unsupported` | 非 Windows 平台 | 1 |

普通 Windows 桌面上无目标调用通常返回 `unknown` / `target_not_provided`；若同时观察到明确的 desktop 冲突，`blocked` 优先。非法 HWND 参数走 usage / KitError，退出码 2。探针不是原子快照，不核验 RDP 连接状态，也不把空 foreground 或 access denied 单独解释为 UAC。退出 0 既不授予权限，也不保证下一步输入有效。具体调用与恢复方法见 [Windows 操控指南](WINDOWS-CONTROL.zh-CN.md)。

## Kit 动作接口

公共入口：

```text
python -m rdc_operator --config config.local.json --state .rdc-state doctor
python -m rdc_operator --config config.local.json --state .rdc-state call request.json
python -m rdc_operator --config config.local.json --state .rdc-state call request.json --apply
```

请求包含 `request_id`、`action`、`args`。下表是当前实现契约，不代表每一个平台和应用均已通过实测。

| Action | 作用 | `--apply` | 关键前提 |
|---|---|---|---|
| `terminal.start` | 创建 SmartCLI 终端会话 | 必需 | session 尚未由其他任务占用；cwd 在允许目录中 |
| `terminal.snapshot` | 读取会话当前画面 | 不需要 | Kit 已记录该会话的所有权 |
| `terminal.wait` | 等待画面条件或超时 | 不需要 | 同上；有等待上限 |
| `terminal.send_text` | 发送文本，可选择换行 | 必需 | 已有 owned session；记录准确请求 |
| `terminal.send_key` | 发送上游支持的键 | 必需 | 已有 owned session；键在支持集合中 |
| `terminal.close` | 关闭 Kit 拥有的会话 | 必需 | 关闭未确认时保留证据，不伪称结束 |
| `desktop.observe` | 读取指定窗口和控件 | 不需要 | 正整数 HWND；保存窗口、进程、selector 与时间 |
| `desktop.focus` | 正常请求已观察的顶层窗口获得前台 | 必需 | 只接收 fresh `observation_id`；精确身份和 `GA_ROOT` 复核；独立读取前台 |
| `desktop.invoke` | 通过 UIA 激活控件 | 必需 | 未过期 observation；selector 来自该观察；身份复核 |
| `desktop.set_value` | 通过 UIA 设置控件值 | 必需 | 同上；不能把命令已执行等同于应用业务完成 |
| `desktop.click` | 点击已观察到的控件 | 必需 | 同上；不用自由坐标；需要输入条件成立 |
| `desktop.screenshot` | 截取指定窗口 | 必需 | 输出在允许目录内；可能改变窗口状态 |
| `omp.preview` | 生成现有 wrapper 的 dry-run 回执 | 必需 | 明确 brief/cwd/model/effort；不启动模型 |

`--apply` 是明确执行入口，不创造新的授权。请求文件、网页内容、上游说明都不能替用户授权额外动作。

`desktop.focus` 不接收任意窗口、selector、坐标或 `force`。若已观察 HWND 被重新挂到父窗口，`GA_ROOT(HWND) != HWND` 会在调用上游前被拒绝，Kit 不接管未观察的父窗口。正常 focus 可能恢复最小化窗口，因此上游失败或动作后身份/前台无法核实均保留 `outcome_unknown`。同一请求读取已有回执，不重复聚焦。

聚焦成功后，下一次获准点击使用返回的 `result.observation.observation_id` 和该观察中的真实 selector。`focus_effect_verified: true` 只证明本次聚焦核验成立；按钮或应用的业务效果仍需单独见证。`desktop.click` 保留上游 foreground 保护，不在内部强制聚焦或自动重发。

## Windows 权限与 UAC 范围

| 场景 | 当前处理范围（沿用 a4） | 不能由普通 fixture 推导的结论 |
|---|---|---|
| 普通交互桌面中的应用 | 读取输入条件，绑定目标，正常聚焦，操作后读取独立结果 | 不保证任意控件、DPI、显示器或同时有人操作时都成功 |
| 已提升的应用 | 读取实际 token/session；目标 integrity 高于 collector 时诊断为 `blocked`；按具体任务走正常 Windows 授权流程 | 不是管理员组成员就必定可以操控；换一种输入接口也不是通用跨权限方案 |
| UAC 安全桌面 | 说明具体程序、动作与提升原因，由用户处理系统确认；返回后重新观察 | 本版没有实现自动点击 UAC、安全桌面键鼠、跨用户桌面或特权后台服务 |

Microsoft 的 [`SendInput`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) 与 [`PostMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew) 文档都说明 UIPI 约束。UAC 默认的安全桌面与普通应用窗口分离；UIAccess 另有签名、可信安装位置等要求，并非无限提权。参见 [UAC 工作原理](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/how-it-works) 和 [辅助技术安全说明](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)。本项目保留正常用户确认，不修改 UAC 策略来制造通过结果。

## 有截止时间的 Windows 验收

[`smoke_windows.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/scripts/smoke_windows.py) 在完整源码目录中串行运行九个顶层 case，并持续保存 `summary.json`、子报告引用和清理结果。下表定义测试类型，不预填实机通过结果。

| Case | 验证范围 |
|---|---|
| `core` | 核心回归；保留运行、通过、失败、错误与跳过的实际数量 |
| `doctor` | 可执行文件发现，不等同于功能准备就绪 |
| `liveness` | 自有合成管道子进程的存活、输入等待、输出与截止 |
| `terminal` | 自有 REPL/TUI 的实际交互与独立见证 |
| `mcp` | 独立 SDK 环境中的 stdio 协议与合成 state |
| `browser_offline` | 六个离线 JSON 证据样例；没有实际浏览器执行 |
| `omp_preview` | 已有 dispatcher 的 `DRY_RUN`；没有真实模型调用 |
| `desktop` | 自有 Windows fixture 的 UIA、显式聚焦、鼠标操作与结果读取 |
| `observation` | 自有 Windows fixture 的有限采样与证据检查 |

`--python` 指定实际基础解释器，`--terminal-python` 指定安装了 SmartCLI 的环境，`--mcp-python` 指定独立 MCP SDK 环境，`--powershell` 指定实际绝对路径的 `pwsh.exe`。没有 MCP 环境时省略对应参数，case 明确为 `skipped`，不能记作全通过；不要为了跑通而合并有冲突的依赖环境。输出必须是 `allowed_roots` 内的新目录，不能覆盖旧证据。可直接采用 [600 秒示例](WINDOWS-CONTROL.zh-CN.md#4-一次有界-windows-验收)。

退出码 0 要求九个顶层 case 全部为 `passed`；失败或不确定清理为 1；跳过、未执行等覆盖不完整为 2。核心测试自身的跳过数量仍须单独报告。总体 deadline 给等待和清理预留预算，原生 OS 调用与磁盘写入不是硬实时保证。runner 标记 `source_execution: true`、`installed_package_validation: false`，不能把源码验收当作当前已安装包的版本证明。真实 Edge 操作与真实 OMP 模型任务也必须另留证据。

## 回执与恢复

- 同一个 `request_id`、相同 payload 与有效配置的已完成调用返回原回执；不同 payload 或配置拒绝。
- 效果执行前保存 intent；发现未完成 intent 时停止自动重放，返回不确定状态。
- `observed` 表示得到观察；`completed` 表示本动作完成；`failed` 表示已知失败；`outcome_unknown` 表示效果无法判定。
- 一份 state 使用一个 OS lock；这协调 Kit 的调用者，无法阻止用户或其他程序同时改变桌面。
- Shell/terminal 子进程仍拥有本机用户权限。`allowed_roots` 约束 Kit 管理的路径，不是 OS 沙箱。

## RDC 工具历史快照：第二轮记录的 30 项

以下保留第二轮实际 tool metadata 的 30 项盘点，属于历史接口快照，不是第四轮逐项功能实测，也不保证下一会话仍暴露相同集合。调用前应核对当前 schema、账号和设备。完整公开研究见 [研究说明](RESEARCH.zh-CN.md)。

| 工具 | 用途 | 使用时要保留的边界 |
|---|---|---|
| `read_file` | 文本、图片、Excel、PDF、DOCX 内容 | 文本/页/行的分页语义随格式不同；图片返回后还要实际查看 |
| `read_multiple_files` | 一次读取多个文件 | 每个结果分别检查，不能用总体成功覆盖单文件错误 |
| `list_directory` | 目录列表与递归层级 | 嵌套目录有展示上限；省略不代表不存在 |
| `get_file_info` | 类型、大小、时间、行数、sheet 信息 | 元数据不是文件正文 |
| `write_file` | 写入、追加文本与支持的文档格式 | 改写已有内容前确认目标；长写入可以分块 |
| `write_pdf` | 新建 PDF、插页或删页 | 修改 PDF 使用不同输出路径，保留原件 |
| `edit_block` | 文本精确替换、Excel 范围与 DOCX XML 修改 | 唯一匹配与 expected replacement count 必须成立 |
| `create_directory` | 创建目录 | 路径必须对应已选设备 |
| `move_file` | 移动或重命名 | 覆盖风险与写入所有权需事先确认 |
| `start_search` | 启动文件名或内容搜索 | 正则/字面匹配应明确，返回搜索 session |
| `get_more_search_results` | 分页读取搜索结果 | 按 session 和 offset 续读，不重复启动同一搜索 |
| `stop_search` | 停止搜索 | 保留已经收到的结果 |
| `list_searches` | 查询搜索 session | session 存在不代表检索完整 |
| `start_process` | 启动命令或 REPL | 使用设备对应 shell；远端等待结束不一定是进程结束 |
| `interact_with_process` | 向已有进程发送 stdin | 原生 RDC 是文本管道，不能当成完整 PTY |
| `read_process_output` | 读取进程输出 | `offset=0` 是新输出；多消费者不能抢同一个游标 |
| `list_sessions` | 查看 RDC 管理的进程会话 | 不等于所有桌面终端 |
| `list_processes` | 查看系统进程 | 只查看必要字段，不能据名称推定所有权 |
| `force_terminate` | 停止已知 RDC 进程会话 | 仅停止已确认属于本任务的会话 |
| `kill_process` | 按 PID 停止进程 | PID 必须再次核实，不能批量清理未知程序 |
| `list_devices` | 列出账号下的设备 | 记录准确 link/device；不能随意换机器 |
| `who_am_i` | 账号信息和用量百分比 | 不把账号信息写进公开包 |
| `shutdown` | 停止目标 RDC device agent | 不是停止任务；不是关机；会切断远端访问 |
| `get_config` | 读取配置和平台信息 | 不应把整份环境与历史无选择地公开 |
| `set_config_value` | 修改 RDC 配置 | 不用于放宽已遭拒绝的权限；空目录数组代表全盘范围 |
| `get_usage_stats` | 使用/失败/性能统计 | 使用量不是任务质量或验收 |
| `get_recent_tool_calls` | 有限本地工具历史 | 大输出有省略、旧历史会修剪，不是完整审计账本 |
| `list_remote_tool_calls` | 查询后台 remote 调用 | 和 PID/搜索 session 区分 |
| `get_tool_result` | 取回 `call_id` 结果 | pending/executing 时不能重发原有副作用请求 |
| `review_device_call` | 展示准确调用供用户审阅 | 本身不执行；不是连接错误或普通超时的通用重试 |

### 文件格式

该快照的接口描述包括文本、PNG/JPEG/GIF/WebP、Excel、PDF 和 DOCX。格式支持是一项工具承诺，逐格式实测需另留回执。DOCX `offset=0` 返回概览，非零 offset 才返回 XML；PDF 的 offset/length 按页；Excel 支持 sheet/range。不要把所有格式都按文本行数处理。

## 本版尚未覆盖的范围

任意网页所有功能、被策略拒绝的 origin、锁屏/UAC secure desktop 的键鼠输入、跨用户桌面、任意 TUI 兼容、自动接管用户已有任意进程、无人确认的账号配对，以及 Linux/macOS 完整 GUI 支持。

Windows 是首要实测平台。a6 的源码、安装包、公开发布与未重跑范围见[第六轮报告](REVIEW-WAVE6.zh-CN.md)；a5 结果继续见[第五轮报告](REVIEW-WAVE5.zh-CN.md)，历史结果保持原版本。Linux 的安装器与核心/终端路线可以单独验收；`winapp` 桌面适配器仅适用于 Windows。旧上游测试、作者声称或设备可连都不能替代本项目在指定版本上的实测。
