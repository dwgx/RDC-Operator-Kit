# RDC Operator Kit · Wave 04

日期：2026-11-26（Asia/Tokyo）。源码版本：`0.1.0a4`，本地 Alpha 候选，未公开发布。本文区分代码回归、原生 Windows 实测、官方 Edge 操作、模型调度与发行准备；同一版本号下的两次 Windows run 另以 runner 指纹区分。

## 1. 本轮结论

**普通 Windows fixture 的真实鼠标点击和官方 Edge 自有页面的语义/CUA 点击均已有成功证据；Windows 全套验收仍为失败，不能宣称“绝对可控”或“全部功能通过”。**

Windows run 001 的桌面 case 完成了显式聚焦、一次点击与独立计数见证，但观察窗口的外层清理存在退出竞态。修复后，run 002 的观察与两个窗口清理通过；桌面 case 又在聚焦后发现 foreground 已不属于目标，保留 `focus_unverified` 并停止后续点击。两个 run 都是 **8/9 顶层 case passed、整体 exit 1**，失败原因不同，不能合并为一轮 9/9。

| 范围 | 已取得的结果 | 适用范围 |
|---|---|---|
| Linux 最终核心回归 | **158 运行、158 通过、0 跳过、0 失败/错误** | CPython 3.12.14；包含合成和 mock，不等于 Windows GUI 通过 |
| Windows run 001 | 157 运行、149 通过、8 跳过；桌面 **14 项检查通过**；总 suite failed | 首个 a4 runner；24.032 秒；清理竞态尚未修复 |
| Windows run 002 | **158 运行、150 通过、8 跳过、0 失败/错误**；顶层 **8/9 passed，exit 1** | r2 runner；22.914 秒；桌面 focus 后验未通过 |
| Windows 终端 | 自有 REPL 和 TUI 均 PASS | SmartCLI 0.3.5；业务见证与持有的进程句柄核对退出 |
| Windows 存活性 | 9 个合成场景结果符合预期 | 普通 pipe transport；不是任意 CLI/TUI 兼容性证明 |
| Windows MCP | modern/legacy 两个真实 stdio session 均通过，各 19 项检查 | SDK 2.3.0、合成只读 state；不操作桌面或模型 |
| Windows 只读 preflight | 实际返回 `observed`，无 native query 错误 | 一次普通自有窗口采样；没有提权或 UAC 输入 |
| Windows 有限观察 | run 002 的 **22 项检查通过**；3 帧、3 个不同哈希，采样 2.281 秒 | 一个自有窗口及明确打开的 owned dialog；真实像素渲染时间仍未知 |
| 官方 Edge localhost Lab | 语义点击 0→1、延迟效果 1→2、截图定位鼠标点击 2→3；reset/reload 核对 | 真实浏览器交互；原始采集错误与后续协调分别保留 |
| 官方 Edge a4 首页 | 四条能力路线、三种安装方式、键盘、主题、筛选、折叠说明与复制取得回读 | Markdown 指南被 Edge 阻断，随后 origin 自动审批拒绝；整体 BLOCKED，响应式与最终截图未执行 |
| `omp.preview` | 两个 Windows run 均核对 `DRY_RUN` | 未调用真实模型 |
| 单独真实 OMP 任务 | 单次 GLM max，约 599 秒后 `BLOCKED / upstream_abort / Deadline exceeded`，无 final | 真实调用失败，不是成功的独立模型审查 |
| 原生 Skill | 三个文件更新、canonical 验证、三个 fresh-context 模拟任务通过；主控已确认同步 | 操作说明验收，不增加机器或浏览器权限 |
| Windows 安装升级 | 两个自有环境均从 a2 升级到 a4；隔离导入定位及 11 个模块指纹核对通过 | 单独安装验收；不改写此前两个 source-tree run 的范围 |

Windows 的 8 项 skipped 由主控进一步核对为：5 项 symlink 权限不可用、1 项 POSIX FIFO、2 项 Linux installer。它们不算通过，也不表示相应 Windows 行为已经得到替代验证。两个 Windows run 都保留 `source_execution: true`、`installed_package_validation: false`、`config_unchanged: true`。

## 2. 新增接口与实现选择

### 2.1 `windows-preflight`：观察输入条件

新增 [`windows.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/windows.py) 和 CLI 入口，读取 collector/target 的 PID、创建时间、session、token integrity/elevation/UIAccess，以及 window station、thread/input desktop、前后 foreground 和各项错误。CLI 在 config/state 处理之前返回；探针没有输入、聚焦、切换 desktop、提权或策略修改。

`assessment.status` 为 `observed`、`blocked`、`unknown` 或 `unsupported`。只有 observed 返回 exit 0，其他三态返回 1，非法参数为 2。普通桌面不指定目标通常是 `unknown / target_not_provided`；已观察到的 blocked 风险优先。所有状态都保留 `permission_granted: false` 和 `uac_state: not_determined`。非原子采样、会话连接状态未核验及后续状态变化都保持为明确限制。

run 001 的真实 preflight 返回 `supported: true`、`assessment.status: observed`、空 errors/risks，耗时 0.459 ms。这证明该次原生查询与判断成功，不证明之后一直占据前台，不证明全体 ctypes 平台/位宽或 UAC 场景已经覆盖。使用方法见 [Windows 操控指南](WINDOWS-CONTROL.zh-CN.md)。

### 2.2 `desktop.focus`：单独请求正常激活

新增 action 只接受 fresh `observation_id`，沿用完整 request/config 身份、state lock、先写 intent 和 `--apply`。上游调用前检查精确 HWND/进程身份，并要求 `GA_ROOT(HWND) == HWND`；不会收养重挂后的父窗口，也不接收 `force` 或自由坐标。

调用一次正常 `winapp ui focus -w` 后，Kit 验证 window-only ACK，重新观察，并独立读取 foreground 和 kernel identity。只有这些证据同时成立才记录 `focus_effect_verified: true`；`application_effect_verified` 仍为 false。点击必须使用返回的新观察和真实 selector，且保留 click 自身的前台保护。

正常 focus 可能先恢复最小化窗口再失败，因此调用后的非零退出或无法确认的后验都保留 `outcome_unknown`。同一请求取回原回执，不会再次聚焦。检查与执行之间的竞态仍存在；本版没有加入抢焦点循环或其他强制输入策略。

### 2.3 串行 Windows runner

新增 [`smoke_windows.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/scripts/smoke_windows.py)，固定顺序为 core、doctor、liveness、terminal、MCP、browser offline、OMP preview、desktop、observation。总报告在阶段开始、子进程启动、结束与清理后持续原子写入，失败子报告和 stdout/stderr 引用不会被后续成功覆盖。

runner 分别使用真实基础 Python、SmartCLI Python、独立 MCP Python 和实际绝对路径的 PowerShell 7 `pwsh.exe`。GUI readiness 必须同时满足持有的 Popen PID、新 witness、HWND/kernel identity、可执行文件和 fixture 标题/初态；不接管 redirector 的另一 PID。输出目录必须新建，旧证据保持原样。

本轮两个 run 均使用 600 秒预算。deadline 约束命令等待并为清理预留时间，原生 OS 调用和磁盘写入不是硬实时保证。顶层 case 全部 passed 才 exit 0；失败或不确定清理为 1；只有跳过/未执行等覆盖不完整则为 2。真实 Browser 和真实模型任务始终另行记录。

## 3. Windows 两个 run 的完整判定

### 3.1 版本与时间

| 标识 | JST 时间 | runner SHA-256 | 总结果 |
|---|---|---|---|
| run 001 | 14:47:57–14:48:21 | `7c668506dad4bdb929c41c61d145f002171c01d095e75fcf637d213d9dee7a73` | failed，exit 1 |
| run 002 / r2 | 14:52:44–14:53:07 | `73fa5f555e17ba51f6971f51d7978a80480be78eab3b13e200a705b7dd698f92` | failed，exit 1 |

环境记录为 Windows 11 `10.0.26300`、Python 3.14.7；终端使用 SmartCLI 0.3.5，桌面使用已配置的 winapp 0.8.0。MCP 使用独立 SDK 2.3.0 环境。两次测试运行 a4 源码，不把原环境中 a2 distribution 的存在解释为已完成升级。

| 顶层 case | run 001 | run 002 |
|---|---|---|
| core | passed；149/157，8 skipped | passed；150/158，8 skipped |
| doctor | passed：可执行文件发现 | passed：可执行文件发现 |
| liveness | passed | passed |
| terminal | passed | passed |
| mcp | passed | passed |
| browser_offline | passed，六个预期 verdict | passed，六个预期 verdict |
| omp_preview | passed，DRY_RUN | passed，DRY_RUN |
| desktop | **passed，14 项检查；cleanup verified** | **failed，focus_unverified；cleanup verified** |
| observation | **子报告 passed，外层 cleanup failed** | **passed，22 项检查；cleanup verified** |
| 总 suite | **8/9，failed，exit 1** | **8/9，failed，exit 1** |

### 3.2 run 001：真实点击成功，外层收尾失败

桌面 fixture 的 14 项检查包括：观察与目标归属、真实 selector、Unicode value readback、Invoke ACK、独立文件见证、窗口截图、显式 focus、前台回读、selector mouse click、点击文件见证、同 request 重取无第二次点击、点击后截图，以及未观察目标的拒绝。

这次实际计数从 0 到 1，同一请求重新读取时仍为 1。focus、click、独立 witness、replay 与截图分别提供证据，不用一个工具 exit 0 代替全部判断。该 desktop fixture 正常关闭，退出码 0，witness 为 closed，没有强制终止。

观察子脚本自身完成 22 项检查，报告 passed，命令 exit 0，也已关闭它的窗口并更新 closed witness。但是 HWND 销毁早于 PowerShell 进程完全退出；外层 runner 查询窗口时得到 `window_not_found`，旧路径未先等待原来持有的进程正常退出，直接强制终止。外层因此记录 `forced: true`、`possible_descendants: unknown`、`verified: false`，整个 observation case 和 suite 正确保持失败。

这属于 runner 的收尾竞态，不能把子脚本 passed 用来覆盖。原 run 001 的 summary、失败清理记录和截图均保留。

### 3.3 r2 修复与 run 002：清理恢复正常，聚焦后验停止点击

r2 将“是否能向原 HWND 发 WM_CLOSE”和“等待原持有进程退出”分开。窗口已经消失时记录 `window_already_closed`；仍只对原 Popen 等待最多 `min(2 秒, 剩余预算)`，不能获得另一个 PID 来代替。超时或中断仍保守失败，正常退出仍要求 exit 0、closed witness、没有强杀/中断。相关回归及独立的八个反例检查见 [harness review](research-wave4/review-release-harness.md)。

run 002 的 observation case 及两个 GUI fixture 的 cleanup 均 verified。观察窗口仍走过 `window_already_closed` 路径，但原进程在有界等待中正常退出，没有强杀，证明这次实际触发条件得到正确处理。

同一 run 的 desktop focus 则呈现另一种真实结果。已直接核对的原始 receipt 内容为：

```json
{
  "status": "outcome_unknown",
  "result_code": "focus_unverified",
  "backend_exit_code": 0,
  "action_acknowledged": true,
  "post_observation_status": "observed",
  "window_identity_checked_after_action": true,
  "foreground_matches_target": false,
  "focus_effect_verified": false,
  "application_effect_verified": false
}
```

上面的 `foreground_matches_target` 是对原始两个 HWND 值的去标识比较结果，其余项摘取自对应回执字段。上游成功 ACK 与后验前台不符同时存在；当前证据无法确定是其他软件、用户输入还是 Windows 焦点规则造成，也没有据此确诊 UAC。后续 click 没有派发，原未知回执没有改写，没有通过换 request ID 或备用输入路线再点。这个保护行为成立，但桌面功能 case 仍为 failed。

### 3.4 终端、观察与 MCP 的具体证据

REPL 先观察提示符，再输入；独立 witness 得到计算结果 42，并确认 Unicode 与引号内容准确。TUI 已观察 alternate screen、选择 Beta 再 Enter，独立 witness 为对应 choice/index。两个自有程序都通过持有的 Windows process handle 确认 exit 0。通用 `terminal.close` 仍返回 `outcome_unknown / close_receipt_not_exposed`；额外的 fixture 退出见证没有改变通用接口的这个限制。

9 个 liveness 场景包括 silent、silent-input、waiting-input、flood、timeout、exit-no-marker、ready-only、marker-no-witness、wrong-token。PASS 表示分类与预期相符，例如输出洪泛应得到 output-limit、纯 marker 无 witness 不能判业务完成；不是说九个被测程序都正常完成业务。这里使用普通 pipe，没有测试任意已有终端的完整 PTY 兼容性。

run 002 的观察 fixture 检查一次 action 的独立变化、action/frame replay、单窗来源、有限采样、动画进展和 composite 拒绝。3 个样本均不同字节哈希，采样区间为 2281.208 ms；这些事实不等于高帧率视频或已知渲染时刻。原报告 `pictures_visually_reviewed: false` 保持未改。主控随后另行读图确认了三张图片：run 001 的点击后画面显示 count 1 和 Unicode 输入；run 002 同一 fixture 的前后图分别显示蓝色 action 0/frame 0 与橙色 action 1/frame 1。这项人工视觉核对单列，不倒填原始自动报告，也不增加实时性保证。

MCP 的 modern `2026-07-28` 与 legacy `2025-11-25` 协议 session 各 19 项检查通过，包含两个只读工具、闭合 schema、去标识 capabilities、原样 receipt、无 scope override、无非协议 stdout，以及已持有进程退出。原始 receipt 未改变。报告同时记录 `kit_source_version: 0.1.0a4` 和 `kit_distribution_version: 0.1.0a2`，明确运行来源是 source tree；这是区分“源码已测”与“包已安装”的直接证据。

## 4. 官方 Edge 的真实交互与采集纠错

本轮使用已连接的官方 Edge 能力，在自有 localhost Lab 完成以下序列。它与 Windows runner 的六个离线 JSON 样例不是同一次测试，也没有借用 OMP Relay、RDC 或 CDP 访问被拒绝的目标。

| 顺序 | 实际操作与观察 | 判定 |
|---|---|---|
| 1 | 填写新 request 标记与中文 token；语义点击一次；同一 fixture/document 的 counter 0→1，完成记录匹配 | 效果已发生；首次采集器断言错误，见下文 |
| 2 | 依据原始返回字段进行协调，不再点击 | `semantic_click_once_reconciled: true` |
| 3 | ACK/echo 按钮产生操作反馈，但业务 witness 与 counter 1 保持不变 | ACK 不能当业务效果 |
| 4 | 延迟按钮一次；先观察 pending，后读取 pending 清空、counter 1→2、标记匹配 | 延迟效果核对通过 |
| 5 | 根据新截图定位鼠标点击一次；counter 2→3、标记匹配 | 真实 CUA 鼠标点击效果核对通过 |
| 6 | Reset epoch | counter 回到 0，document epoch 改变 |
| 7 | Reload document | 新 fixture nonce 与新 document epoch，counter 为 0 |

首次采集器错误地读取 `last_completed.request_token`，而页面实际 schema 为 `last_completed.token`，因此原 trace 中的 `semantic_click_once.passed` 为 false。主控读取已有前后 witness 后追加 reconciliation，确认值与请求一致；没有重新点击来制造绿色结果，也没有把原 false 改成 true。归档 trace 保留 7 条记录，其中 1 条原始失败和 6 条 true；这不是“原始检查从头到尾全部通过”。

有完成时间的动作集中在 JST 14:14–14:15。图片与 DOM witness 支持该页当次变化，不等于任何网站都可操作。历史 ChatGPT origin 的宿主拒绝仍保留，当前没有再次尝试；Edge 扩展的“Allowed on all sites”也不解除宿主限制。上一轮 Linux `file://` 的 `ERR_BLOCKED_BY_ADMINISTRATOR` 没有重新尝试或改 transport 规避。

## 5. 独立审查、反例与已修复问题

实现与复核分轮进行：恢复 a3 基线后先独立找具体问题；作者修复；另一个 reviewer 用原反例复验；新增 Windows 实测暴露的竞态再进行修复与复核。审查人数、测试数量与无剩余 finding 都不替代运行证据。

| 问题或修复路径 | 修复与独立核对 | 当前判断 |
|---|---|---|
| a3 允许树内的已知私有运行文件可能进入 ZIP/TAR，基线 reviewer 判 P1 | 在读取/遍历前按名称及大小写变体排除；合法示例和研究 JSON 保留 | 已修复；不声称历史候选发生泄密 |
| 独立 HTML 预览仍能重新读取已排除的私有文档，复核判 P2 | build 与 standalone preview 都读同一批准字节快照；私有/越界引用在写产物前拒绝 | 原反例私有打开次数 0；正常文档仍能构建 |
| 网站 smoke 的启动、初始化、截图或清理异常可能丢 summary，基线 reviewer 判 P2 | 生命周期归档、已返回 handle 的清理、拒绝后停止、无法归档时非零失败 | 17 项回归及 reviewer 的 25 个独立故障场景通过；不是浏览器实测 |
| focus 后同进程 reparent 可能先激活未观察父窗，reviewer 判 P2 | 上游调用前要求 exact target 仍为自身 GA_ROOT；独立反例 effects 为空 | 7 项 focus 回归及独立对账通过 |
| GUI cleanup wait 收到 KeyboardInterrupt 时可能丢收尾，reviewer 判 P2 | 保留中断，继续处理原持有进程，记录不确定并停止后续 case | 原反例及回归通过，未扩展 PID/进程名清理范围 |
| run 001 实测发现窗口销毁早于 PowerShell 退出 | r2 增加对原持有进程的有界退出等待；自然退出仍核对 closed witness | 12 项 runner 回归、8 个独立场景及 run 002 清理结果支持修复 |

前两行是同一发布隐私要求在不同输出路径上的缺口，不把审查轴或后续复验重复相加为“更多独立漏洞”。发行规则只覆盖已知私有名称和路径边界，不是通用秘密扫描器或抵御同权限恶意文件替换的完整沙箱。

最终 Linux `python3 -m unittest discover -s tests -v` 为 158/158，耗时 1.922 秒。较早 157 项的运行恰好覆盖了发布修复的红阶段，产生 16 个预期反例失败；原日志保留，修复后的全套与最终 r2 全套分别记录，没有删除失败历史。所有 Linux 数字均不能覆盖真实 UAC、锁屏、跨 session、多显示器或任意应用。

独立报告：[a3 基线](research-wave4/review-a3-independent.md)、[preflight/focus](research-wave4/review-focus-preflight.md)、[release/site/Windows harness](research-wave4/review-release-harness.md)。各报告清楚注明自己的读取与执行范围；作者之后被授权写补丁的记录与最初只读结论分开。

## 6. 真实 OMP 调度：有回执的失败

本轮使用现有 origin-dispatch 发送一个只读冻结 packet 的审查任务，明确 `lunaroute/glm-5.3-flash`、effort max、max attempts 1、attempt/total budget 各 600 秒。没有自动换模型、增加重试或把任务改走 Relay。

| 原生回执字段 | 实际值 |
|---|---|
| JST 起止 | 14:40:56–14:50:55 |
| `status` | `BLOCKED` |
| `model_resolved` / `effort_effective` | `lunaroute/glm-5.3-flash` / `max` |
| attempts | 1，`simulated: false` |
| wall / attempt seconds | 599.0 / 599.166 |
| attempt exit / classification | 1 / `upstream_abort` |
| signature / stop_reason | `Deadline exceeded` / `aborted` |
| `timed_out` | false：wrapper 记录的是上游主动中止，不是它的外层 timeout 标志 |
| `transport_ok` / `final` | false / null |
| 最终 Markdown 字节 | 0 |

回执中记录了 JSON 输出流，但没有最终审查文本，不能拿“进程启动”“有日志”或“JSON 可解析”代替审查完成。该次 OMP 不能计为成功的独立 code review；本轮采用的具体修复来自已有可复核的原生子代理报告、代码反例及实测。

usage 与 cost 字段均为 0 只是该回执呈现的数值，不能据此证明 provider 实际没有计费，也不能解释为任务完全没有运行。原生回执与模型最终回答是不同层证据，成功调度的 `DONE` 本身也只说明 worker 返回，不自动代表其成果通过验收。

## 7. Scite、Firecrawl 与仓库研究的读取范围

本轮对 Windows 输入边界和 agent harness 做定向研究，形成 [Windows/UAC 技术研究](research-wave4/research-windows-uac.md)、[harness 仓库研究](research-wave4/research-harness-repos.md) 与 [来源账目](research-wave4/research-harness-source-ledger.json)。没有宣称遍历完整互联网、审计整个上游仓库，或运行 OSWorld/WAA 完整 benchmark。

### 7.1 论文访问层级

| 论文 | Scite 已取得 | 正文与额外阅读 |
|---|---|---|
| [OSWorld](https://doi.org/10.48550/arxiv.2404.07972) | 元数据与身份核验 verified | Scite `contentDenied: true`、`returnedChars: 0`；Firecrawl 取得作者公开摘要，另读官方实现相关方法 |
| [Windows Agent Arena](https://doi.org/10.48550/arxiv.2409.08264) | 元数据与身份核验 verified | Scite 正文同样无内容；Firecrawl 取得公开 HTML，实际选读 §3.1.3 与 task/evaluator 上下文 |
| [Agent S2](https://doi.org/10.48550/arxiv.2504.00906) | 元数据与身份核验 verified | 未请求 Scite 全文；技术行为来自固定提交 S2/S2.5 的相关代码/说明 |

Scite 共 3/3 条目 verified，不能解释为三篇论文全文已读、实验已复现或三篇均经过同行评审。其返回没有 editorial/contrasting 标记，也不能证明没有反例。OSWorld 的 [作者摘要](https://arxiv.org/abs/2404.07972) 和 WAA 的 [公开 HTML](https://arxiv.org/html/2409.08264v1) 是另行取得的一手来源。

### 7.2 实际采用与保留为研究的内容

| 固定上游 / 读取位置 | 对本轮工作的影响 |
|---|---|
| [winapp v0.8.0](https://github.com/microsoft/winappCli/blob/v0.8.0/src/winapp-CLI/WinApp.Cli/Commands/UiFocusCommand.cs) | 核对 root-window focus、restore/activation 与 ACK 结构，保留现有后端并补精确对象绑定 |
| [Playwright MCP `2337aff`](https://github.com/microsoft/playwright-mcp/blob/2337aff0213d28db41d3e3daf48cee19b3d0bd82/tests/click.spec.ts) | 学习可访问性定位、前后快照与自有点击 fixture；未将 MCP origin 配置当作完整安全沙箱 |
| [OSWorld `0ad41be`](https://github.com/xlang-ai/OSWorld/blob/0ad41bee56565efe7bb3c3a5ebc67590a1b8276f/desktop_env/desktop_env.py) | 保持动作循环与独立 evaluator 分离，使用 witness 验收效果 |
| [WAA `eb220c4`](https://github.com/microsoft/WindowsAgentArena/blob/eb220c4dcf64babefc1bfc287edda91ab04132ed/src/win-arena-container/client/desktop_env/envs/desktop_env.py) | 借鉴 Windows task/evaluator；没有把基准 VM 的 close-all/reset 搬到日常电脑 |
| [browser-use `94784c1`](https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/browser_use/agent/service.py) | 借鉴单一运行归属、取消和阶段预算；模型的 success verdict 仍需独立证据 |
| [Agent S2 `0fff0e6`](https://github.com/simular-ai/Agent-S/blob/0fff0e634869dab72027435b4586e62300185d41/gui_agents/s2/cli_app.py) | 研究 grounding 尺寸与观察循环；没有复制任意 Python 执行层来扩大控制面 |
| FlaUI、pywinauto、Windows-MCP | 比较控件覆盖、输入副作用和接管状态；没有新增安装这些完整运行栈 |

本轮以已配置的 SmartCLI/winapp 作为运行时复用对象，其余仓库为设计与反例来源，未把第三方大块源码或模型栈直接并入项目。许可与实际读取范围见研究报告；若后续复制代码，仍需固定取用版本并保留原版权、许可和适用 NOTICE。

## 8. UAC 与控制权限的裁决

Microsoft 文档规定 [`SendInput`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) 和 [`PostMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew) 均受 UIPI 约束；输入事件被接受也不是业务成功。正常前台请求受 [`SetForegroundWindow`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow) 的规则约束，不能用一次 ACK 承诺持续占据前台。

普通交互桌面、已提升应用与 UAC 安全桌面分别需要判断。[UAC](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/how-it-works) 默认使用安全桌面；[UIAccess](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview) 另有签名、可信安装位置等要求，普通脚本或新增 Skill 不会自动取得这些权限。本版没有自动 UAC 点击、特权 broker、跨用户桌面或锁屏控制的验收。

遇到确实需要提升的任务，先展示具体程序、动作及原因，由用户完成正常系统确认，返回后再建立新的目标与输入上下文。没有通过关闭安全桌面、修改 UAC、换接口或改 OMP/Browser 路由来获取“全通过”。历史被宿主拒绝的 origin 保持停止；这与本轮已获准 localhost 页面成功是两项并存事实。

## 9. 原生 Skill、安装与网页的整合状态

### 9.1 原生 Skill

`rdc-operator-kit` 的 `SKILL.md`、`references/requests.md` 和 `references/installation.md` 已更新，内容覆盖新接口、UAC 正常用户接力、600 秒 runner、三个 Python 路径与真实 pwsh、fresh observation、未知结果协调，以及 source/installed、OMP preview/live、browser offline/live 的区别。

canonical quick validation 与 diff 检查通过。全新上下文的 reviewer 只阅读 Skill，完成三个模拟任务：旧 a2 安装不能因新说明而直接获得 focus；未知点击与已有计数变化不能换 ID/Relay 重试；缺 MCP 环境和已有输出目录必须保留 incomplete 与新目录要求。三个任务没有确认会导致错误执行的指令缺陷；详见 [forward acceptance](research-wave4/review-skill-forward.md)。主控已确认原生 Skill 同步成功，并重新读取确认相应路径无未保存变化。

这证明说明在上述任务中的可用性，不证明远端安装已升级，也不授予模型访问任意设备或网页的能力。

### 9.2 Windows 安装升级——已单独验证

两个 source-tree run 结束后，主控完成了独立的本机安装升级核验。升级前将 108 个候选文件逐一与既有交付归属记录及目标现状核对，结果为 0 冲突；原源码与原 Kit 安装文件已备份。原用户配置的 SHA-256 前后一致。

使用的 pure-Python wheel SHA-256 为 `d845a324d1a902bbfc91949aedc43174faac802b677d84e19d39f12d0b91e488`，安装采用 `--no-index --no-deps --force-reinstall`，没有在这一步联网解析或升级依赖。两个已确认归属的环境均从 Kit a2 升级到 a4：SmartCLI 环境继续保留 SmartCLI 0.3.5 与 MCP 1.30.0；独立 MCP 环境继续保留 SDK 2.3.0。

主控随后分别以 Python `-I` 排除当前源码目录影响，核对实际 `site-packages` 的版本与 import 来源，并逐一确认 11 个模块的 SHA-256 与实测源码一致。因此可以报告“a4 已安装且模块字节与已测源码一致”，但这不是在安装包上重新运行整套 GUI suite 的证明。

历史 MCP 报告中的 `kit_distribution_version: 0.1.0a2` 和两个 suite 的 `installed_package_validation: false` 均保持原样。后续安装完成不能改写此前运行的环境或使其总体失败变成成功。

### 9.3 a4 网页交互验收——部分完成，整体 BLOCKED

JST 15:24–15:31，主控使用官方 Edge，在已更新的自有 localhost 首页完成真实交互。标题明确为 `RDC Operator Kit 0.1.0a4`，DOM 显示本轮 158/158、150/158 与 8/9 的区别。对应源码归档 SHA-256 为 `576a9341f800305aafd72c5d73b57a4a8c443746ba2cd6362cb6765e855b28e1`。此前 34 个源码/文档变更已按既有归属、hash 与备份进行本机同步，完整 124 文件清单一致，配置未变。

| 首页检查 | 实际结果 |
|---|---|
| 四个能力标签 | 选中状态、唯一选中项和对应可见 panel 已读回；两项采集条件纠错见下文 |
| 三个安装标签 | Agent、Linux、Windows 的显示内容和选中状态正确 |
| 键盘 | 能力组 Home/End 与安装组 ArrowLeft/ArrowRight 环回通过 |
| 三个复制按钮 | Linux 与 Windows 文本已读回一致；Agent 首次空读回保留失败，单独再次复制后 242 字符一致；未执行复制的命令 |
| 主题 | 切换浅色并恢复原深色，DOM 主题属性均匹配 |
| 四个证据筛选 | 公开来源 2、实现与实测 3、阻断 3、全部 8；hidden 与 aria-pressed 一致 |
| 四条故障说明 | 各自展开并关闭，读到相应内容；浏览器路线跳转选中目标 tab |
| 初始宽度 | DOM clientWidth 与 scrollWidth 均为 1305；仅证明该次默认宽度没有页面水平溢出 |
| Markdown 指南链接 | 单次点击后 Edge 显示 `ERR_BLOCKED_BY_CLIENT`，未通过 |
| 后续 responsive / 最终截图 | 未执行：在继续返回同一 localhost 时，自动审批拒绝该 origin 的访问权限 |

采集 trace 共 30 条记录，25 条 true、5 条原始 false，不能将它当作 30 个独立功能的通过率。两个 false 来自不匹配当前页面文案的大小写敏感 English sentinel；原记录中选中/可见状态已为真，主控只用已有 panel 文本追加 reconciliation，没有重放点击。Windows copy 的另一个 false 来自同时命中安装代码和行内 `-InstallRoot` 的多义 locator；之后只读回同一次已完成复制的内容。Agent copy 的首次空读回与单独 follow-up 成功同时保留，当前证据没有证明第一次空值的具体原因。

指南链接的拒绝属于实际浏览器结果。随后自动审批明确拒绝继续获得 `http://127.0.0.1:18764` 的 origin authority，理由是刚出现 Edge 拒绝后的继续访问可能扩大或越过访问边界；不是用户手动拒绝。主控停止所有该 origin 的浏览器验收，没有换为 RDC、OMP Relay、CDP 或另一种浏览器 transport。自有 tab 的关闭请求返回它已不属于该 browser session，未再重新 claim，关闭是否完成保持未确认。

页面与报告之后仅补记这些结果、明确 OMP 新旧证据；最终交付的 JavaScript/CSS 与上述检查相同。后续文案字节尚未获得新的 live 浏览器确认，最终首页截图和窄屏布局仍未验收。源码中的 Markdown 文件可随项目交付，但其存在不能把被拒绝的浏览器链接标为通过。此前 Lab 的实际鼠标截图只证明那个独立 fixture；可选 Playwright 的 17 项 lifecycle 与 reviewer 的 25 个故障探针仍仅为本地控制流验证。

### 9.4 公开发布

没有公开创建 GitHub repository、发布 Release 或部署 GitHub Pages；预备 workflow 与安装说明不等于 CI/Pages 已运行。后续发布应以最终归档、版本、来源指纹和准确验收边界作为审阅对象。

## 10. 复现入口与证据定位

Linux 最终回归命令：

```bash
python3 -m unittest discover -s tests -v
```

两个 Windows run 使用的参数结构如下，真实设备路径已去标识。各变量必须来自实际确认的源码、配置和环境，`$newOutput` 每次为新的允许目录：

```powershell
& $basePython "$sourceCheckout/scripts/smoke_windows.py" `
  --config $allowedConfig --output $newOutput `
  --python $basePython --terminal-python $terminalPython `
  --mcp-python $mcpPython --powershell $pwshExe `
  --deadline-seconds 600
```

私有运行证据不打入公开源代码包。下面是本报告核对副本的文件名与 SHA-256；runner 自身记录的子报告 hash 也继续保留，不以重新排版的摘要替换原始回执。文件指纹证明本次所读字节，不能单独证明实际执行或业务效果。

| 核对副本 | SHA-256 |
|---|---|
| `linux-core-a4-final.log` | `28e78a3451616ece5cb778d4f7246042794078e00109c446b9c77302fa737d6d` |
| `windows-smoke-001.json` | `02caa2d8c0009cbdf2910caf586bee4fa28927af4b2534fe92aa11163b50e3de` |
| `windows-smoke-002.json` | `2f3e75e9b1e65f6bccae0906d4a1450788dc922e482900e97985a2c5d0d93942` |
| `desktop-success.json` | `aade3acfa402f3712bd7b249ba6acec9594d2c7a28ccf4d35f7c4fe68632aad7` |
| `desktop-preflight.json` | `e41d7a2958272ee1ce5aaf1fa0dbd80beff576a788658f02419afe427fa59119` |
| `desktop-focus-stopped.receipt.json` | `0285873de96c73c1781e18be89b6f07b4892c11b4929c7cd26e89552d67ca2ef` |
| `observation-success.json` | `9a641dfcc8779fb8a6a6ce8dc0e721892c35fc159c0cc01743d293ea1333ee1d` |
| `windows-terminal.json` | `c006331bb9e3dbe54f8ec69392c1fb699e01403628394232cc810bf41d8e1d01` |
| `windows-mcp.json` | `e5587da95e3a15319e6f565b53709f403ad0c229a7d81a962e28d71dc90d76a9` |
| `windows-liveness.json` | `c3404eac279678676cd1c67d2f61feb9af75806a201a0c8d72c3ebbe2ef51aca` |
| `edge-live-fixture.json` | `31666cfae5735e39b4553dd3738498e2720f15815922f32ee6c95c8cc456a00f` |
| `edge-homepage-a4.json` | `ebc7f9ec9a7516468788d069ee9e958bb8186a7354e77d55233152a6921fc3f7` |
| `windows-installed-a4.json` | `8bc652aea48fca4584a1fa40d913091cf670146b20846016fb0bbbdaa60e908e` |
| `windows-source-update-001.json` | `43516ffc4b30bd172318a0e98515a2dcbb789b3f278302c8ba30795f33e48628` |
| `omp-native-receipt.json` | `d661953d0953bb3635c528debd30cd87e7b227c499cccaf8cbbaeee8e98810d1` |

## 11. 当前验收边界

可以据此确认：a4 增加了只读 Windows 诊断、独立正常 focus、受目标与前台约束的点击流程、有截止的总验收、持续保留失败报告、发布出口一致的私有文件排除，以及经过前向检查的操作 Skill。普通桌面点击有一次实际成功，后续不满足前台条件时也有实际停止证据。

仍不能据此确认：一次完整 Windows suite 全通过、任意应用持续可控、任意 TUI 兼容、UAC/锁屏/跨 session 操控、多屏和所有 DPI 组合、真实连续视频、OMP 本轮审查完成、被拒绝的 ChatGPT 网页可用，或任何公开部署。a4 首页取得部分真实交互证据，整体仍因浏览器与自动审批拒绝为 BLOCKED；本报告不让后续成功覆盖前述原始失败与未知。
