# 第二轮：窗口画面、观察时效与动作证据

研究日期：2026-11-26 UTC。研究基线：RDC Operator Kit `0.1.0a1`；Microsoft winapp `0.8.0`，固定源码提交 `696222f72e80c669671845bd6c7b0286eefab987`。本文件是源码与公开资料研究，以及下一步实现/验收建议；**没有在本研究支线执行新的 Windows 捕获或 Linux 模拟测试**。本轮其他支线或后续实现的真实结果，仍应写入项目 VERIFICATION，不能由本文件代替。

## 1. 建议先交付什么

优先把已有 `desktop.screenshot` 补成**有来源、有时间边界、有内容指纹的图像证据**，再考虑有限采样。最紧迫的问题是来源核验：固定上游的 `screenshot -w HWND` 可能把目标的 owned dialogs 合成进图片；当前基线 Kit 只检查请求窗口前后身份和 PNG 头，未检查上游实际输出的 `hwnd/processId/windows/filePath/width/height`。[L1][W1][W2]

本轮建议的可交付范围：

1. 严格核对上游 screenshot JSON，拒绝 composite、错 HWND/PID、错路径、错尺寸和未完成文件作为合格证据。
2. 返回不可变 `frame_id`、PNG SHA-256、捕获调用开始/完成时间、耗时、目标身份和明确的验证标记。
3. 精确区分“取得了新的文件”“取得新的 compositor frame”“动作产生了预期业务效果”。现有接口只能为第一项及部分来源检查提供直接证据。
4. 保留现有 UIA selector 动作，不增加根据截图猜出的坐标点击。截图本身不授予 mutation 资格。
5. 先完成一个专用 WinForms fixture 的有限验收，再决定是否增加 `max_frames/deadline` 采样脚本。

不需要为这个增量新建 daemon、HTTP server、模型 broker、视频中继或凭据系统。现有 RDC 文件/图像传输和 Kit 请求回执足以承载第一阶段。

## 2. 实际研究范围与访问状态

已完整读取本地 AGENTS、ARCHITECTURE、VERIFICATION，以及 README 的当前项目说明；阅读了 adapter 的窗口身份、UIA observation、screenshot 和 mutation 相关代码，并阅读现有 WinForms fixture 与 desktop smoke。版本/文件摘要保存在同目录 `OBSERVATION.sources.json`。[L1]

Scite 的 `search_literature` 和 `read_fulltext` 已通过工具 schema 发现。实际调用了一次 `search_literature`，针对 OSWorld、Windows Agent Arena、Agent S 查询 screenshot/observation/feedback/evaluation；返回 `INVALID_ARGUMENT`，说明 MCP 需要付费计划或有效试用。没有取得论文命中或 full-text。没有继续调用已知受限的 full-text、变更套餐或读写 collections。下文文献依据来自可访问的原始 arXiv、研究项目页和官方源码，不把 Scite 错误当研究结果。[A1]

论文阅读是**与本问题相关的摘要、章节及附录定位阅读**，不是声称通读全部论文。OSWorld 2.0 的 v1 HTML 请求出现 `DisabledError`；已读取 arXiv 摘要及作者项目页，未用不可访问的全文推导细节。[P5]

本研究没有采集全桌面、操作用户桌面、打开 ChatGPT/OpenAI 网页或启动新中继。会话已有 Browser origin policy 拒绝，换捕获后端不能改变这个约束。[L1]

## 3. 原始研究真正支持的设计判断

| 原始来源 | 相关事实 | 对本项目的含义；不应外推的部分 |
|---|---|---|
| OSWorld，2024，§2.2.3、§2.3、§5.2 | 环境同时支持截图和 accessibility tree；以任务相关的执行结果脚本验收；作者还研究了窗口位置、尺寸和无关窗口扰动。[P1] | 图像、UIA、结果文件是不同通道。窗口布局变化应触发重观察。该评测不能证明此 Windows 电脑的延迟、焦点或截图来源正确。 |
| Windows Agent Arena，2024，§3.1、§3.1.3 | 交互描述为观察—动作—新观察；任务完成根据最终系统设置、文件等后处理判断。其讨论指出 OS 中多个过程异步运行。[P2] | 最终结果检查应与动作 ack 分离。benchmark 的最终 reward 不等于每次动作都有及时、可信的反馈。 |
| Agent S，2024，§3.1.3、§3.3、附录 A | 使用截图加树结构、受限动作和 `wait`；Self-Evaluator 的经验总结不使用外部 ground truth。[P3] | 可复用“有边界的动作 + 再观察”思想。Agent 自评和 DONE 信号不能代替独立 oracle，不能直接写成实测成功记忆。 |
| ScreenSpot-Pro，2025，§1、§3、附录 D/E | 任务给定指令与静态截图，要求定位 UI 元素；数据强调高分辨率、小目标与专业软件，采用专家目标框。[P4] | 可以评估图像 grounding，不能据此验证动作发出时目标还在原位置、传输帧未过期或业务效果完成。裁剪、缩放必须保留坐标变换。 |
| OSWorld 2.0，2026，摘要与项目页 | 作者明确区分动态环境与 streaming interaction；后者含观察和动作之间视觉状态变化的情形。[P5] | “不断发截图”与能在动态界面中及时闭环是两个目标。第一阶段应公布实测采样与交付延迟，不能把有限 PNG 序列称作实时视频。 |

这里没有借用任何模型平均分证明本机能力。上表第三列是面向 Kit 的工程推论，不是论文原作者对本项目的测评。

## 4. 固定 winapp 源码里的三个重要边界

### 4.1 指定 HWND 仍可能返回 composite

`UiScreenshotCommand.cs` 395–438：无 element selector/filter 时，普通窗口截图仍会发现 owned windows；只有特定 `--capture-screen -w` 分支跳过此扩展。736–786 行显示，即使显式 `-w`，仍会查找该窗口拥有的窗口，并可包含跨进程 owned dialogs。[W1]

上游有专门的 provenance 测试：同一 system host 内被复用的 dialog HWND，不能仅凭 PID 接受，而要确认 owner 关系仍指向预期应用。这些是**上游测试源码**，并非本项目在用户电脑执行过的测试。[W3]

这意味着：

- Kit 的“原 HWND 身份没变”不能证明 PNG 只含这个 HWND。
- 上游也会在 composite 中对各窗分别捕获。即使共用一段协调锁，也不等于像素来自同一个时刻，外部人或程序仍能改界面。
- 不能用 `--capture-screen` 作为简单修补：它读取屏幕区域，可能包含覆盖在上面的其他内容，并依赖 foreground 行为。
- post-capture 拒收只是防止误用证据。图片可能已写入私有路径；这不是“绝不捕获额外窗口”的事前隔离保证。尚未实现严格捕获范围前，应把实测限制在项目自有 fixture。

### 4.2 screenshot 可能改变窗口状态

`UiAutomationService.Screenshot.cs` 的实际路径：[W4]

- 最小化窗口会调用 `ShowWindow(...SW_RESTORE)`，等待 300ms。
- 显式 focus 或 screen capture 会尝试置前。
- 支持 WGC 时优先走 Windows Graphics Capture；某些异常会转 PrintWindow。
- PrintWindow 返回 blank 时会尝试 `SetForegroundWindow`，等 200ms 再捕获。

所以“截图”不应被宣传成保证不抢焦点、纯被动、完全无副作用。元数据可注明 `upstream_may_restore_or_foreground: true`；没有观察到状态变化时，也不能写成 `foreground_unchanged_verified: true`。

### 4.3 WGC 内部有 freshness，但 screenshot JSON 没有透出

`WgcCapture.CaptureAsync` 以 2,000ms 内部 deadline 等非 blank frame，用 `Version` 区分新帧与重复读取缓存；五个不同版本 blank frame 会失败，取消会被传播。对应 freshness 测试覆盖重复缓存、deadline、五个 blank、取消，以及 opaque black 是合法图像。[W5][W6]

然而 screenshot 对外只返回 pixels/width/height，CLI JSON 没有 compositor timestamp、frame version 或实际选择的 capture backend。[W1][W2] Kit 在命令返回后加一个 `time.time()`，不能将其标成“像素渲染时间”。而 WGC 失败后的其他路径也不能继承 WGC 内部的 freshness 保证。

Microsoft 的 `Direct3D11CaptureFrame.SystemRelativeTime` 才定义为 compositor 渲染该帧时的 QPC 时间；`ContentSize` 是那一帧的内容尺寸。官方文档还要求正确处理 resize、归还 frame pool 缓冲区，避免在 UI thread 做重活。[M1][M2] PrintWindow 文档则明确其是可能阻塞的同步调用，由目标应用处理绘制。[M3]

## 5. 上游实际 JSON 契约

固定源码位置：

- 类型与序列化：`src/winapp-CLI/WinApp.Cli/Helpers/UiJsonContext.cs` 155–188。
- 发布：`src/winapp-CLI/WinApp.Cli/Commands/UiScreenshotCommand.cs` 624–670。
- JSON 使用 camelCase，null 默认省略。[W1][W2]

| 字段 | 当前源码类型/含义 | Kit 建议 |
|---|---|---|
| `filePath` | string，写入后的绝对路径 | 与请求解析后的 output 对比；只读该请求文件，别跟随上游另一个路径 |
| `width/height` | int，最终编码图片尺寸 | 与 PNG IHDR 比较，限制尺寸/文件大小；头验证不等于完整 PNG 解码 |
| `processId/hwnd` | int/long，pass target 身份 | 严格整数且匹配 kernel identity；Python bool 不作为 int 接受 |
| `windowTitle` | 可省略 string | 只作说明，不作唯一身份凭据 |
| `elementId` | 可省略 string | 本阶段请求整窗；不悄悄接受变成任意 element crop |
| `windows` | composite 的数组；单窗为 null，序列化时通常省略 | presence with array 应拒收为严格单窗证据；schema 错误同样拒收。兼容 null 的选择需写成明确规则 |
| `coordinates` | 可省略对象 | 未核验时不把它用于坐标动作 |
| `executionTarget` | 可省略对象，本机 ui screenshot 不设置 | 未配置远端 target 时，不接受不同 target incarnation |

`windows[]` 含 `hwnd/title/label/width/height/captured/error`；**没有每窗 PID**。不能从这个数组独立还原每个窗口的进程创建时间或跨进程 owner 链。[W2]

命令异常、timeout、无 JSON、截断输出、上游与磁盘不一致，都不应返回“合格单窗帧”。既有 `outcome_unknown` 语义应保留，失败文件仍保留供诊断，不伪造完成回执。

## 6. 最小 frame envelope 建议

以下是协议设计示例，字段与数值均为合成示意；不是当前产品已经支持的输出：

```json
{
  "frame_id": "frame-<uuid>",
  "request_id": "<screenshot-request-id>",
  "scope": "verified-single-window",
  "identity": {
    "window": 123,
    "pid": 456,
    "process_started": "<kernel FILETIME>",
    "executable": "<normalized local executable>"
  },
  "capture": {
    "requested_backend": "winapp-ui-screenshot",
    "actual_backend": null,
    "call_started_at": "<UTC ISO8601>",
    "call_completed_at": "<UTC ISO8601>",
    "call_elapsed_ms": 310.4,
    "captured_at": null,
    "captured_at_source": "not_exposed_by_upstream",
    "upstream_may_restore_or_foreground": true
  },
  "artifact": {
    "path": "<request-owned path>",
    "sha256": "<digest>",
    "bytes": 10000,
    "width": 680,
    "height": 360
  },
  "correlation": {
    "after_action_request_id": null,
    "action_receipt_verified": false,
    "causal_effect_verified": false
  },
  "verification": {
    "upstream_scope_checked": true,
    "window_identity_checked": true,
    "png_header_verified": true,
    "full_png_decode_verified": false,
    "pixels_visually_reviewed": false,
    "pixel_render_time_verified": false
  }
}
```

### 时效怎么定义

- 用目标机的 monotonic clock 计算 `call_elapsed_ms`。UTC 只是跨日志阅读用的标签，不把跨机时钟相减当单向网络延迟。
- `captured_at` 在实际帧时间不可得时明确为 null；或者彻底省略该字段。不要将 CLI 完成时间伪装成 pixel capture/render 时间。
- `frame_id` 识别采集事件，hash 识别文件字节。两帧 hash 相同可能只是静态界面，不能证明画面卡死；两帧 hash 不同也不证明业务操作成功。
- 相同 request ID 的回放应保留原 frame_id、时间、hash 与路径，不能因为读取旧 receipt 就“刷新”图片时间。
- UIA tree 与 PNG 是顺序取得的两个观察，不能声称原子同步。若关联 observation_id，应写出两次调用的区间，而非只有一个笼统 observed_at。
- 若文件后来被替换、丢失或 hash 不符，历史 receipt 仍描述原事件；当前交付应报 artifact mismatch/missing，不能把新文件借用旧 frame_id。

### 动作关联怎么定义

`after_action_request_id` 只能在同一 state 查到相符 identity 的真实 action receipt 后，由编排器关联；仅用户输入同一个字符串不证明顺序。它表达“该动作调用后请求了此帧”，不是“此动作造成所有可见变化”。

例如 Invoke ack 后，新的图像仍显示旧文本：可能业务仍异步进行、渲染尚未刷新或动作没有产生预期效果。应有界等待结果 oracle，而不是追加一次 Invoke。来源不明的额外变化也应保留为未知。

### 旧截图如何限制下一步

当前 Kit mutation 依赖 UIA observation_id 和 selector，截图不能成为坐标授权。明显延迟、窗口移动/resize、对话框出现、目标关闭或身份变化后先重新 observe，重新绑定 selector。任何未来坐标动作都需要单独的 freshness/geometry/DPI 契约；本增量不提供它。

“截图不陈旧”本身也是有限判断：即使有 QPC，只能证明捕获时机，无法冻结捕获后变化。取新图不是对竞态的绝对消除。

## 7. 有限 PNG 采样、近实时反馈与视频

| 形式 | 能承诺的内容 | 仍缺少的证据 |
|---|---|---|
| 单次截图 | 一个请求对应一个文件和来源检查 | 不保证动态场景连续性 |
| 有限 PNG 序列 | 固定窗口、最大帧数、采样区间、截止、逐帧来源和失败列表 | 不是连续视频；两帧之间可漏过弹窗或闪烁变化 |
| 近实时查看 | 在具体机器、具体传输路线测量 sample 到 delivery 的分布 | 没有实测不能承诺固定 FPS 或端到端延迟 |
| 连续录制/流 | 编码时序、丢帧、背压、缓冲、关闭与设备丢失处理 | 文件录制完成也不代表 ChatGPT 正在实时消费每一帧 |

最小 sampler 可以先是一条不常驻的任务：例如最多 4 帧、目标总耗时 10 秒、间隔至少 250ms、固定允许 output 根目录与总字节预算。数字是**建议初值，尚未实测**。逐帧同步采集，不让多个 CLI 争夺同一桌面；失败即停止或返回明确 partial，不跨窗口换目标凑帧。

总时限要传递给每次子调用的剩余时间。只在帧间检查 deadline、单帧仍默认 30 秒，不是真正的 10 秒上限。进程关闭与残留资源也沿用现有 Kit 的直接子进程边界，不能声称能回收任意子孙或全系统 capture session。

上游 winapp 已有 `ui record`，其 JSON 类型含 `frames/durationSec/fps/achievedFps/cadenceRatio/stopReason/frameArtifacts`，启动事件含 `framesDirectory/framesManifest/framesIndex`。[W2] 这是下一阶段优先评估的复用方向；本研究只确认源码接口存在，未运行录制、未核对完整录像实现，也未承诺能通过当前 RDC 图片通道实时交付视频。

## 8. 一项足以决定本阶段成败的 Windows 实测

**测试名称：自有窗口“动作—像素—独立结果—范围拒绝”有限闭环。**

复用现有 WinForms fixture，增加一个固定显示的 `run_nonce`、`render_seq` 和测试专用 owned-dialog 开关；这些属于后续实现，不是本支线已经改好的代码。测试控制器、PNG 消费者与 witness 读取器使用独立结果判断，不从 screenshot receipt 直接复制预期值。

一次测试只执行以下有界流程：

1. 启动隔离的自有 fixture，建立进程 HANDLE 与 kernel identity。记录随机 nonce。窗口显示 nonce、count=0；从 fixture 自己写的 witness 读取实际值。
2. 取得基线截图 A。核验 source JSON、header/尺寸/hash，再实际解码并查看图片；A 的 nonce/count 与 witness 一致。图像读取路径必须是将来给 Agent 的实际传输路线。
3. 用一次真实 selector Invoke/Click 增加 count；只允许一个 action request ID。等待 fixture witness 成为 count=1，再取得截图 B，关联该 action。在 deadline 内看到相同 nonce/count=1，且 B 的 capture 调用发生在 action 调用后。若图像迟迟不更新，测试失败，不重发动作。
4. 重放相同 action request ID，witness 必须仍是 count=1。随后由 fixture 打开自有 owned dialog，再请求截图 C。上游如报告 `windows[]`，Kit 必须拒绝它成为 `verified-single-window`；不能因为有合法 PNG 就 PASS。C 的原始文件只放私有证据。
5. 关闭测试窗并确认原 HANDLE 退出；不能把后续未知窗口或旧 A 作为当前目标。保留所有原失败回执。

**验收条件：** 一次业务变化、两张来源核验和视觉核验均一致的图像、动作重放无二次变化、composite 被拒绝、正常清理，全流程有真实调用时间与截止。输出的是这条 fixture 路径的通过/失败，不是 Windows 通用稳定性。若第 4 项未触发上游 composite，就记录未覆盖；不能用一个正常单窗正例替代这个反例。

这一个测试同时暴露错误 target、截错图、旧图回放、把 ack 当业务成功、以及 composite 标签不实。额外的 GPU/UAC/锁屏/多显示器压力测试不应成为本阶段发布前无限延长的理由；它们先列为未覆盖。

## 9. Linux 上的决定性模拟反例

**测试名称：合法 PNG + 同样 HWND 前后检查，仍然是不合格图像证据。**

给 adapter 的 mocked runner 返回 exit=0 和一个尺寸、PNG 头都正确的 fixture 文件；kernel identity stub 前后相同。但 stdout JSON 含 `windows=[{hwnd:original,...},{hwnd:other,...}]`。旧基线会将其作为 completed 截图；新契约必须拒绝 scope，不返回合格 frame envelope。

随后在同一个有限回归集合中覆盖：

| 注入的反例 | 预期 |
|---|---|
| JSON 的 hwnd/PID/path/width 与请求或 PNG 不符 | 拒绝 provenance，不继续交付为可信帧 |
| stdout 无 JSON、字段类型错误、截断 PNG、文件缺失 | unknown/failed，不以 exit=0 覆盖缺失证据 |
| 同一 request ID 重放 | 不调用上游；保留原 frame_id/hash/time |
| 本地 wall clock 回退，monotonic 仍前进 | 耗时保持有效；不产生负 latency 或“更鲜”的旧帧 |
| 等待超过剩余 deadline 或最后一帧只写一半 | partial/timeout 留证；停止下一帧，不轮询无限期 |
| PNG 字节被替换但沿用旧 manifest | hash 不符，不混淆事件身份 |
| 合法静态图片两次字节相同 | 可保留两次采集事件；不能据此判应用挂死 |

这是协议和适配器模拟，不证明 WGC、PrintWindow、Windows 进程身份或 RDC 图像展示已经实机通过。本研究支线没有运行这些测试；后续报告应给出实际命令与结果。

## 10. 如何保留第一轮证据

既有 VERIFICATION 记录：smoke02 的截图已实际通过 RDC 图像通道查看，显示自有 fixture；这条正例有效。smoke03/04 的 set_value 回读不一致也仍然有效，不能因后来读到上游源码而撤销或归因于截图。[L1]

新发现补充的是：当时通用 adapter 没有独立验证上游 JSON 的单窗 provenance，故那次成功不能证明对任意 owned-dialog 情形都严格只采一个 HWND。本文未重新读取所有私有原图和原始 JSON，也没有根据文档声称已经完成历史图像取证。可以同时成立：

- “这一张历史图实际显示了自有 fixture，已被查看。”
- “通用截图接口对 composite 的严格拒绝，在当时尚未获得验证。”

不用重写旧 receipt，不把旧测试变成新测试；让下一条反例和明确的新版本边界承担新增保证。

## 11. 建议优先级

**P0，当前增量：** screenshot JSON provenance 检查、frame ID/hash/调用区间、回放时间不刷新、合成 Linux 反例；文档保留可能恢复/置前与 post-capture 拒收边界。

**P1，有限 Windows 验收：** 第 8 节的一条专用 fixture 闭环。成功后可以描述“目标窗口截图证据路径实测通过”；失败就保留 Alpha 与具体原因。

**P2，下一轮有明确问题再做：** 审查上游 `ui record` frameArtifacts 是否可用于增量交付；调查如何从 WGC 暴露真实 frame timestamp/backend，及能否在捕获前严格约束单 HWND。没有这些证据前，不承诺连续实时控制。

## 参考与定位

以下均为公开原始材料；访问状态和本地基线摘要见 `OBSERVATION.sources.json`。

- [P1] Xie, T., et al. (2024). *OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments.* [arXiv v2](https://arxiv.org/html/2404.07972v2)。定位 §2.2.3、§2.3、§5.2。
- [P2] Bonatti, R., et al. (2024). *Windows Agent Arena: Evaluating Multi-Modal OS Agents at Scale.* [arXiv v1](https://arxiv.org/html/2409.08264v1)。定位 §3.1–3.1.3、异步环境讨论。
- [P3] Agashe, S., et al. (2024). *Agent S: An Open Agentic Framework that Uses Computers Like a Human.* [arXiv v1](https://arxiv.org/html/2410.08164v1)。定位 §3.1.3、§3.3、附录 A。
- [P4] Li, K., et al. (2025). *ScreenSpot-Pro: GUI Grounding for Professional High-Resolution Computer Use.* [arXiv v1](https://arxiv.org/html/2504.07981v1)。定位 §1、§3、附录 D/E。
- [P5] Yuan, M., et al. (2026). *OSWorld 2.0: Benchmarking Computer Use Agents on Long-Horizon Real-World Tasks.* [arXiv 摘要](https://arxiv.org/abs/2606.29537)；[作者项目页](https://osworld-v2.xlang.ai/)。
- [M1] Microsoft. [Direct3D11CaptureFrame](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.direct3d11captureframe)。
- [M2] Microsoft. [Screen capture](https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture)。
- [M3] Microsoft. [PrintWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-printwindow)。
- [W1] Microsoft winapp 固定提交：[UiScreenshotCommand.cs](https://github.com/microsoft/winappCli/blob/696222f72e80c669671845bd6c7b0286eefab987/src/winapp-CLI/WinApp.Cli/Commands/UiScreenshotCommand.cs)。
- [W2] 同提交：[UiJsonContext.cs](https://github.com/microsoft/winappCli/blob/696222f72e80c669671845bd6c7b0286eefab987/src/winapp-CLI/WinApp.Cli/Helpers/UiJsonContext.cs)。
- [W3] 同提交：[UiCommandTests.Screenshot.Provenance.cs](https://github.com/microsoft/winappCli/blob/696222f72e80c669671845bd6c7b0286eefab987/src/winapp-CLI/WinApp.Cli.Tests/UiCommandTests.Screenshot.Provenance.cs)。
- [W4] 同提交：[UiAutomationService.Screenshot.cs](https://github.com/microsoft/winappCli/blob/696222f72e80c669671845bd6c7b0286eefab987/src/winapp-CLI/WinApp.UIAutomation/Services/UiAutomationService.Screenshot.cs)。
- [W5] 同提交：[WgcCapture.cs](https://github.com/microsoft/winappCli/blob/696222f72e80c669671845bd6c7b0286eefab987/src/winapp-CLI/WinApp.UIAutomation/Capture/WgcCapture.cs)；[WgcCapture.FrameGrabber.cs](https://github.com/microsoft/winappCli/blob/696222f72e80c669671845bd6c7b0286eefab987/src/winapp-CLI/WinApp.UIAutomation/Capture/WgcCapture.FrameGrabber.cs)。
- [W6] 同提交：[WgcScreenshotFreshnessTests.cs](https://github.com/microsoft/winappCli/blob/696222f72e80c669671845bd6c7b0286eefab987/src/winapp-CLI/WinApp.UIAutomation.Tests/WgcScreenshotFreshnessTests.cs)。
- [L1] 项目基线：[ARCHITECTURE](../ARCHITECTURE.zh-CN.md)、[VERIFICATION](../VERIFICATION.zh-CN.md)、[adapters.py](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/adapters.py)、[desktop fixture](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/examples/desktop-fixture.ps1)。
- [A1] 本次 Scite tool 访问错误；无论文内容返回，不作为论文事实来源。

