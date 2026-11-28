# 命令窗口与终端存活性：第二轮研究和可复现反例

日期：2026-11-26（Asia/Tokyo；原始回执保留 UTC）。范围：RDC Operator Kit `0.1.0a2` 新增的独立诊断脚本。Linux 第一轮通过；随后 Windows 实测出现 venv redirector 的两个 PID 问题，修复后 Windows 12 项针对性测试与 9 场景 probe 均通过。第一轮原有 REPL/TUI 证据保留；本探针不冒用其 ConPTY 覆盖。

## 结论

**“窗口没有新字”不足以判断程序卡死。** 本轮让两个自建子程序产生完全一样的观测：进程仍存活、stdout/stderr 都是 0 字节；一个在 `sleep`，另一个等待 stdin。两者都必须报告 `running_silent`。只有程序明确报告等待输入，或有独立状态证据，才能进一步判断。

同时，**进程退出 0、出现 `READY>`、甚至出现本次随机 token 对应的 `business_done`，都不能单独证明业务完成。** 本轮唯一的完成正例要求三项一致：完成 marker、独立 JSON witness 的值与本次身份匹配、进程退出 0。其余反例正确保留未完成状态。这是本项目合成协议的验收规则，不是所有软件都实现了相同协议。

实现见 [`probe_terminal_liveness.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/scripts/probe_terminal_liveness.py)、[`liveness-fixture.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/examples/liveness-fixture.py) 和 [`test_liveness.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/tests/test_liveness.py)。它们只启动固定白名单中的自建 Python fixture，不接管任意 PID、命令、终端会话或正在运行的 Agent。

## Linux 第一轮实际结果（修复前源码）

环境：Linux `6.18.57`、x86_64、glibc `2.41`、Python `3.12.14`。实际命令：

```bash
python -m unittest discover -s tests -p test_liveness.py -v
python scripts/probe_terminal_liveness.py
```

新增 **9 项测试通过，1.089 秒**。独立脚本运行 **9 个场景全部满足预期，约 1.8 秒**。这里的 PASS 表示正确识别预期状态并回收 fixture；8 个未完成业务场景的 `semantic_verified` 仍然为 false。

| 场景 | 决策时进程存活 | 分类 | 整例耗时 ms | 业务完成 |
|---|---:|---|---:|---:|
| 无输出，程序在 sleep | 是 | `running_silent` | 154.686 | 否 |
| 无输出，程序等待 stdin | 是 | `running_silent` | 154.773 | 否 |
| 明确 waiting_input → 一次输入 → witness | 输入前是；结束时否 | `business_completed` | 31.590 | 是 |
| stdout/stderr 同时洪泛 | 是 | `output_limit_reached` | 42.764 | 否 |
| 1200 ms 截止时间到达 | 是 | `deadline_exceeded` | 1201.708 | 否 |
| 正常 exit 0，但没有完成标记 | 否 | `exited_without_completion` | 31.459 | 否 |
| READY 提示符已出现，任务未完成 | 是 | `ready_without_completion` | 154.475 | 否 |
| 正确 token 的完成标记，没有独立 witness | 否 | `completion_marker_without_witness` | 31.383 | 否 |
| 旧 token 的完成标记 | 否 | `exited_without_completion` | 45.764 | 否 |

本轮所有 `observe()` 调用中，最慢 **0.375328 ms**；这测量的是读取当前进程状态和内存计数的返回延迟，不包含程序启动、Agent 网络往返或一轮业务执行。5 个仍存活的 fixture 被取消，全部确认直接子进程退出；9 个案例的两个 reader 都完成 join。另有隔离测试同时启动两个 fixture，取消第一个后第二个仍存活，随后再清理第二个。

洪泛场景实际读取 stdout **65,621 B**、stderr **65,536 B**；每路仅保留 **4,096 B**，其余计数但不积存。阈值是两路累计 131,072 B，观察到的合计 131,157 B 包含完成采样前的超出量。它是输出保护阈值，不能描述为严格的 OS 配额。

私有原始摘要：`evidence/liveness-20261126T002928Z-35c5d5bd/summary.json`。摘要包含每次场景决策、输入前状态、退出与清理结果、源文件 SHA-256；公开源包不包含 `evidence/`。上述第一轮脚本和 fixture 对应 SHA-256；它们属于历史快照，不是下方 Windows 修复后的摘要：

```text
e291c629878477965cd2b1c2c94f66fa33caabf66bb626016610c083222c220e  scripts/probe_terminal_liveness.py
22bab7dde172a6f4d382ccaa1010cf0c735c8eff734d167c2310910ab44f9b25  examples/liveness-fixture.py
```

## Windows 首轮失败与 PID 修复

主代理随后在 Windows 项目私有 Python 3.14.7 venv 中执行同一套测试，得到 **8 项通过、1 项失败**：waiting-input 已收到两个正确 marker，进程退出 0，两个 reader 均已结束，但 `semantic_verified=false`。完整 probe 的同一场景返回 `completion_marker_without_witness`，其余 8 场景符合预期。原始失败摘要为 `evidence/liveness-20261126T004156Z-900ec435/summary.json`，没有改写成 PASS。

这里并非 witness 没写出。主代理保留实际 witness 并做了两个自建进程对照：经 venv `python.exe` 启动时，保存的 `Popen.pid` 与 fixture 内 `os.getpid()` 不同；直接用该运行时的 `_base_executable` 启动同一个 fixture 时，两者相同，marker、文件和 exit 0 一致。私有诊断记录为 `evidence/wave2-20261126/liveness-pid/diagnosis.json`。该对照由主代理在 Windows 执行，本子任务没有通过远程工具另起 Windows 操作。

官方 [Python venv 文档](https://docs.python.org/3/library/venv.html) 说明 Windows venv 使用 redirector。固定 [CPython v3.14.7 的 `PC/venvlauncher.c`](https://github.com/python/cpython/blob/v3.14.7/PC/venvlauncher.c) 也明确创建真正解释器进程并等待它；因此“fixture Python 源码没有 spawn”不能推出“启动路径只有一个进程”。[同版本 multiprocessing 的 Windows 启动实现](https://github.com/python/cpython/blob/v3.14.7/Lib/multiprocessing/popen_spawn_win32.py) 对 venv 情况同样选择 base Python，这提供了可核对的实现参考。

修复仅用于本标准库 fixture：

- Windows 选择当前 CPython 提供、已存在的绝对 `sys._base_executable` 路径；没有合法路径就启动前报错，不退回可能具有另一 PID 的 redirector。
- 记录 `launch_identity`：请求的解释器路径、实际选择路径、选择依据、保存的直接进程 PID。
- 保留严格 PID 匹配，新增 `witness_verification` 分开说明文件是否存在、fixture PID、是否匹配及失败原因。不同 PID 得到 `pid_mismatch`；不会把文件里写出的任意 PID 认领为 owned，也不会对它发送信号。
- 清理范围改为“保存的 Popen 直接子进程”；不从 fixture 源码推导启动器后代退出保证。该 base 路径选择不推广给依赖第三方 venv 包的真实模型或用户命令。

Linux 增加了两 PID mock 反例、Windows base 路径选择和缺少 base 时启动前拒绝三个回归测试。**修复后共 12 项通过，1.085 秒**；另一次 waiting-input CLI 正例为 `business_completed`、31.792 ms，保存的 PID 与独立 witness PID 一致。该次摘要为 `evidence/liveness-20261126T004527Z-f701fcf0/summary.json`。这验证 Linux 回归与参数选择 mock；修复后的真实 Windows 效果须以主代理的重验为准。

修复后的代码摘要：

```text
e1759ebc02a29e156cbcf81742afec7d74643def5937ce414e3550582fb70145  scripts/probe_terminal_liveness.py
7fe9e2132b62d364f720835b3714b11ddf075687d2c1c2497a5eea576be5e4f8  examples/liveness-fixture.py
```

## 诊断脚本如何保持可返回

`observe()` 不调用等待 EOF 的读取方法。stdout 和 stderr 各有一个 reader，连续消费实际管道；控制线程只读取有界内存中的计数、事件和 `Popen.poll()`。每次循环约间隔 5 ms。每路保留前 4 KiB，协议行上限 1 KiB，已识别事件集合只有四种值；不建立无限增长的输出队列。

默认普通采样窗口为 150 ms，最长场景业务截止为 1200 ms。输入仅限已声明 `waiting_input` 的自建程序，且只发送一次 42 字节的 `continue <token>\n`。该微小写入并不能推出“任意程序、任意长度 stdin 写入都不阻塞”。

清理始终针对构造时保存的 `Popen`：先请求 terminate，最多等待 300 ms，再在必要时 kill 并等待最多 1000 ms。两个 reader 的 join 共用 500 ms 截止。结果明确记录 `direct_child_exit_confirmed`、`readers_joined` 和 `action`，没有确认就不算成功。fixture 源码不调用子进程创建 API，但启动器的实际拓扑需要单独验证；脚本不调用 `taskkill /IM`、全局 daemon shutdown 或外部 PID 搜索。

这些是应用层有界等待与本轮实测，不是硬实时保证。OS 调度、进程创建和内核调用可能超过预计时长；普通 Python 锁也没有在任意故障操作系统上的最坏延迟保证。本脚本不解决不可终止的内核等待，也不宣称任意后代进程都已回收。

## 用户看到“卡住”时可能发生了什么

| 可见现象 | 能得到的结论 | 需要补的证据 / 可恢复动作 |
|---|---|---|
| 没输出，进程 alive | 只知道还没退出 | 对照业务截止、明确输入提示、已有结果文件；不要仅因沉默自动重复输入 |
| 明确请求输入 | 程序声明正在等输入 | 核对当前会话归属与提示，发送一次匹配输入，再读取业务结果 |
| 输出增速很高，但界面很久不返回 | 可能是输出积压、渲染成本或串行 drain | 看累计字节、pending、read/fed offset；缩短等待、限制每轮处理量，保持两路消费 |
| `.wait()` 一直没结束 | 可能仍运行，也可能在等未被排空的输出 | 并行 drain 后再等退出；对交互 TUI 使用 PTY，不把普通管道等同于完整终端 |
| TUI 画面稳定 / 光标提示符出现 | 已观测到稳定画面或某个 marker | 验证本次状态变化和业务 witness，旧画面或 echo 不足以验收 |
| 退出 0，但没有目标文件或最终回答 | 进程正常结束，业务结果未验证 | 保留日志、退出码和缺失见证，报告未完成，不伪造 final |
| Kit 返回 `busy` | 同一 state 的一个请求仍持锁 | 查已有 intent/receipt；等待该请求返回，不新建 state 来绕开协调 |
| close 返回成功，但进程状态未知 | 关闭请求获得确认 | 用本次持有的进程身份 / 退出证据确认；通用结果保持 unknown |

Kit 自身也有一个容易被误认为“终端死了”的等待层：[`core.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/core.py) 会在整个适配器调用和 receipt 提交期间持有 state 锁。因此同一 state 的第二次 Kit 调用会得到 `busy`，上游 SmartCLI 的并发观察能力不能自动穿透这把锁。当前 `terminal.wait` 最长接受 30,000 ms，外层 `run_command` 为该请求另留 18 秒 transport 余量；没有改成后台任务。交互任务可使用较短的显式 wait，完成后重新观察，保留请求 ID 与效果的现有语义。这个选择是本轮建议，不是已经合入的行为变更。

当前 [`common.run_command`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/common.py) 已用临时文件承接 stdin/stdout/stderr，避免因为一条普通管道未排空而阻塞另一条；它每 50 ms 检查超时/输出保护阈值。该实现仍是批命令等待接口，不是 PTY、可交互 session 或实时视频通道。本轮没有替换它，也没有增加 daemon、broker、任务队列或新模型路由。

## 固定上游源码得到的判断

本轮通过 GitHub 连接器重新读取了下列公开源码，使用固定 SmartCLI `0.3.5` 对应提交 `ccf3472dadaae0b5081c8324e2569c25a9174115`，没有把 main 分支的状态当成已经安装的功能。

### SmartCLI 0.3.5

[`pty_backend.py`](https://github.com/dwgx/SmartCLI/blob/ccf3472dadaae0b5081c8324e2569c25a9174115/smartcli_core/pty_backend.py) 的 Windows backend 用后台 reader 消费 PyWinPTY 返回的数据，再提供预算读取与 pending 状态。POSIX backend 的 transport 不同。本项目的管道 fixture 不调用任何一个 backend，所以这里是源码核验，不是本轮 Windows 运行证明。

[`session.py`](https://github.com/dwgx/SmartCLI/blob/ccf3472dadaae0b5081c8324e2569c25a9174115/smartcli_core/session.py) 区分 `drained`、`budget_limited`、`unknown` 和 error；一次刚好吃满预算的读取不能自行宣称 drained。观察还携带 generation、read/fed offset、pending、representation、close 等事实。ConPTY 标为 `conpty_reconstructed_utf8`，上游未知队列量仍可为 unknown。Agent 应保留这些未知值，不能补成零。

[`readiness.py`](https://github.com/dwgx/SmartCLI/blob/ccf3472dadaae0b5081c8324e2569c25a9174115/smartcli_core/readiness.py) 将画面稳定、marker、进程退出和超时分开，并有 revision baseline 的支持。它为上层提供更强观察，不决定任意应用的业务成功。Kit 当前仍按自己的已实现接口核验，不能因为上游支持某项参数就宣称 Kit 已透传。

[`tui.py`](https://github.com/dwgx/SmartCLI/blob/ccf3472dadaae0b5081c8324e2569c25a9174115/skills/drive-tui/scripts/tui.py) 的 session worker 在空闲、请求之间和 wait 的轮询间隙服务 I/O；长等待不应停止消费输出。其 close CLI 最终 JSON 仍只输出 `ok/sid/closed`，不能代替底层完整关闭事实；原 Kit 的 `close_receipt_not_exposed` 边界继续保留。

### PyWinPTY 3.1.2

本轮读取了 [`v3.1.2/winpty/ptyprocess.py`](https://github.com/andfoy/pywinpty/blob/v3.1.2/winpty/ptyprocess.py)。`read()` 使用 socket recv，可能阻塞；`readline()` 等换行；`wait()` 循环等存活状态，且不会同时读取输出。把这些方法直接放在唯一控制线程上，不能获得本轮 `observe()` 的快速返回性质。

源码中的 `terminate(force=True)` 会尝试中断、取消 I/O、必要时终止，再检查是否存活；调用者仍需核对结果。`spawn(str)` 会先 `shlex.split(..., posix=False)` 再查 executable。先前已验证的带引号 exe 路径问题仍有源码依据，本轮未再次重跑路径 smoke，也没有重写 quoting。

### 官方 ConPTY 文档：关闭语义随 Windows 版本不同

Microsoft 的 [Creating a Pseudoconsole session](https://learn.microsoft.com/en-us/windows/console/creating-a-pseudoconsole-session) 说明通信通道使用同步 I/O，建议分别服务输入与输出，以免一端满而另一端同步等待；生命周期中的句柄也需要正确释放。[CreatePseudoConsole](https://learn.microsoft.com/en-us/windows/console/createpseudoconsole) 还说明启用 cursor inheritance 时需要处理光标查询与回复。这解释了某些“程序还在，但命令窗口不动”的底层机制，不证明 Setukou 当前机器恰好遇到了该问题。

当前 [ClosePseudoConsole](https://learn.microsoft.com/en-us/windows/console/closepseudoconsole) 文档明确区分：Windows 11 24H2/build 26100 起调用立即返回；更早版本可能等待伪控制台退出。关闭期间客户端仍可产生输出，未关闭或继续排空输出通道会引起旧系统的等待问题。要确认客户端断开，应继续观察输出管道结束等证据。**不能把旧版“可能长时间阻塞”和新版“立即返回”合并成一句“close 必定等到退出”。**

## Windows 修复后重验与验收范围

主代理在同一私有 venv 入口重新执行下面两条命令：**12 项针对性测试通过，1.147 秒；独立 full probe 的 9 个场景均符合预期**。waiting-input 为 `business_completed` / `semantic_verified=true`，耗时 48.869 ms；1200 ms deadline 场景实际 1204.572 ms（含清理）。全部直接子进程退出和 reader join 均确认。修复后记录为 `evidence/liveness-20261126T004618Z-7a9fc4e3/summary.json`，初次失败记录保持原样。

这三个代码文件仅依赖 Python 标准库。本次 Windows 重验命令：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_liveness.py -v
.\.venv\Scripts\python.exe scripts\probe_terminal_liveness.py
```

该重验的目标是 Windows 普通 subprocess 管道、观察延迟、合成状态、PID 身份绑定与直接子进程清理，**仍不验证 ConPTY/TUI**。真实 PTY 的既有证据仍见 [`VERIFICATION.zh-CN.md`](../VERIFICATION.zh-CN.md)。若继续增加 Windows 专门测试，应在全新 owned SmartCLI session 中分别验证无人轮询时的输出消费、长 wait 期间观察返回、ConPTY 输出洪泛及关闭退出见证；先保留原始失败和身份，不把 Linux PASS 借给 Windows。

本轮不创建真实 OMP/Codex 请求，不接管用户已有命令窗口，不测试宿主拒绝的网页，不改变服务路由。Linux 当前实测支持“本诊断脚本有界返回、正确区分所列反例”，不支持“全部 CLI/TUI 不会卡死”或“永久后台学习已经启动”。
