# RDC Operator Kit：浏览器与桌面 harness 的上游研究

研究日期：2026-11-26（Asia/Tokyo）
范围：只读研究；没有安装第三方运行时、调用模型、操作用户浏览器、改变 Windows 设置或执行上游仓库代码。本文是实现输入，不是对本机功能的验收报告。

## 结论

本轮最值得采用的不是再接一条能点击的通道，而是让每条获准通道遵守同一套可检查的执行契约：观察当前目标、记录动作意图、只发送一次、独立读取效果、按实际证据结束。OSWorld 与 Windows Agent Arena 提供独立状态评估的实现；Playwright MCP 提供语义目标与新快照的交互模式；browser-use 提供运行生命周期和版本迁移的具体反例；Agent S 的示例则说明“模型说 done”不能直接充当验收。

RDC Operator Kit 已有 request/config digest、先写 intent、共享锁、outcome_unknown 和 browser fixture 证据绑定；这些不是本轮新功能。应保持它们，并补齐聚合报告、前置能力检查、单步 deadline 和可恢复证据等缺口。代码搜索已确认现有 `core.py` 与 `browser_evidence.py` 的这些约束。是否补齐及运行结果由本轮实现、独立 review 和实际 smoke 决定。

## 1. Scite 实际读取范围

本轮真实调用了 Scite `search_literature`、`read_fulltext` 与 `verify_papers`。

| 论文 | DOI | Scite 检索 | Scite 正文读取 | 本轮额外一手阅读 |
|---|---|---|---|---|
| OSWorld | 10.48550/arxiv.2404.07972 | 标题、作者、年份、引用分类统计、开放 PDF 链接；未返回摘要正文 | contentDenied=true，returnedChars=0，text 为空；no_full_text | 通过 Firecrawl 读取 arXiv 作者摘要页面；另读官方 DesktopEnv 实现的相关方法 |
| Windows Agent Arena | 10.48550/arxiv.2409.08264 | 同上 | contentDenied=true，returnedChars=0，text 为空；no_full_text | 通过 Firecrawl 取得 arXiv HTML，实际阅读 §3.1.3 和相关 task/evaluator 内容；不是逐字读完整论文 |
| Agent S2 | 10.48550/arxiv.2504.00906 | 元数据与开放 PDF 链接 | 本轮未请求全文 | 读取 Agent S2 固定提交中的 CLI 示例与 S2.5 README 的相关段落；不把当前 Agent S3 的行为等同于 S2 论文 |

`verify_papers` 返回 3/3 verified，0 editorial notices、0 contrasting evidence。这里只能说该次 Scite 检索没有返回这些标记；不能据此证明论文结论没有反例，也不能把引用次数用作工程可靠性证明。引用条目均为 arXiv 版本，不把 Scite 的“verified”解释为已通过同行评审。

Scite 的开放获取链接与“该工具能读到正文”是两件事。上一波若把这些 Scite 结果描述为“已读全文”，应纠正为元数据核验。OSWorld 摘要与 WAA §3.1.3 的公开内容在本轮已有真实返回。

一手论文链接：

- OSWorld 作者摘要：https://arxiv.org/abs/2404.07972
- WAA 正文选读：https://arxiv.org/html/2409.08264v1
- Agent S2 DOI：https://doi.org/10.48550/arxiv.2504.00906

## 2. 仓库、许可与维护快照

下表来自本轮 GitHub 公共 API 返回和固定提交 LICENSE 文件。时间为 GitHub `pushed_at` 转换到 JST，表示仓库 push 活动，不等于特定功能发布日期、不等于持续维护承诺。五个仓库当时均 `archived=false`。

| 上游 | 本次 main SHA | 许可 | 最近 push（JST） | 本轮用途 |
|---|---|---|---|---|
| microsoft/playwright-mcp | 2337aff0213d28db41d3e3daf48cee19b3d0bd82 | Apache-2.0 | 2026-11-19 03:50:37 | 语义目标、执行后快照、点击 fixture、动作/导航 timeout |
| xlang-ai/OSWorld | 0ad41bee56565efe7bb3c3a5ebc67590a1b8276f | Apache-2.0 | 2026-11-23 10:33:08 | setup / step / evaluate 分离，独立结果 getter |
| microsoft/WindowsAgentArena | eb220c4dcf64babefc1bfc287edda91ab04132ed | MIT | 2026-10-27 03:14:01 | Windows task/evaluator、UIA 观察、基准环境局限 |
| simular-ai/Agent-S | dd11eec8708ea113d130c496fdaa24923807a2fd | Apache-2.0 | 2026-11-26 14:07:24 | S2/S2.5 固定版本示例：grounding 坐标契约与受限循环 |
| browser-use/browser-use | 94784c1f7ecb6b0a5f565b7f9fba59e395b7e048 | MIT | 2026-11-26 13:46:06 | 单一运行所有权、取消/关闭、当前 1.0 API 与旧 API 分歧 |

OSWorld、WAA 和 browser-use 的 main 源码正文已与上表对应固定 SHA 的同一文件再次读取比较，正文一致。Agent S 研究示例使用另一固定提交 `0fff0e634869dab72027435b4586e62300185d41` 中的 S2/S2.5 子目录；不能把它冒充当前 S3 路径。

本轮没有把上游大块代码复制进项目。若后续直接复制或修改源码，必须固定实际取用的提交，保存该提交的许可、原始版权与修改说明；Apache 仓库如包含相关 NOTICE，还应一并核查。模型权重、测试数据集和依赖各自的许可不能由根仓库 LICENSE 自动覆盖。

维护数据端点：

- https://api.github.com/repos/microsoft/playwright-mcp
- https://api.github.com/repos/xlang-ai/OSWorld
- https://api.github.com/repos/microsoft/WindowsAgentArena
- https://api.github.com/repos/simular-ai/Agent-S
- https://api.github.com/repos/browser-use/browser-use

## 3. 实际读到的技术机制与适用边界

### 3.1 OSWorld：动作结束与任务完成分离

在 `desktop_env/desktop_env.py` 中，`step()` 记录 action history，执行动作后重新调用 `_get_obs()`；`evaluate()` 则通过 task 配置选择的 result getter 与 metric 评估环境结果。一次 `DONE` 只结束交互，不替代结果 evaluator。任务 reset、setup、postconfig 属于基准环境管理，不应搬到用户日常桌面执行。

对 Kit 的可移植点是独立 witness 和结构化判定，而不是导入整个 VM、OCR、模型栈。已存在的计数器 witness 应推广成各 adapter 的明确效果条件；无法独立读取的任务应返回“仅观察到 UI 变化”或 unknown。

固定源码：https://github.com/xlang-ai/OSWorld/blob/0ad41bee56565efe7bb3c3a5ebc67590a1b8276f/desktop_env/desktop_env.py

### 3.2 Windows Agent Arena：测试基准的 reset 不能当作个人电脑恢复

该版本 `DesktopEnv` 读取截图、可选 UIA tree 和当前窗口信息，并把任务 evaluator 与执行分开。实际源码也暴露了不适合直接复用的地方：`remote_vm` 的 snapshot revert 未实现，reset 分支调用 close-all setup；远程 VM 的 stop/save snapshot 也有未实现标记。把这种 reset 用在用户主机上会破坏不属于任务的窗口状态。

因此应该借用 task JSON / result getter / fixture 配置方式，在 Kit 自己创建的窗口和目录内实施测试；清理始终依赖 fixture nonce、PID、creation time、HWND、命令行等所有权证据。

固定源码：https://github.com/microsoft/WindowsAgentArena/blob/eb220c4dcf64babefc1bfc287edda91ab04132ed/src/win-arena-container/client/desktop_env/envs/desktop_env.py
论文依据：Bonatti et al. (2024), §3.1.3，https://doi.org/10.48550/arxiv.2409.08264 。

### 3.3 Playwright MCP：语义定位与观察循环

官方点击测试使用本地自有按钮 fixture，先导航并得到可访问性 ref，再调用 click，最后检查新 snapshot 中按钮的状态。官方 snapshot 文档明确 ref 的生命周期依赖当前页面状态，导航或页面变化后需要重新观察。

README 分开提供 action、navigation、settle timeout，也明确 allowed-origins / blocked-origins 不构成完整安全边界，不覆盖重定向。此处应学习语义定位、可检查的前后状态和有界等待；不能宣称“装一个 MCP 就得到整个浏览器的安全沙箱”，也不能把 README 中的广泛能力当作本会话宿主允许的能力。

固定点击测试：https://github.com/microsoft/playwright-mcp/blob/2337aff0213d28db41d3e3daf48cee19b3d0bd82/tests/click.spec.ts
README：https://github.com/microsoft/playwright-mcp/blob/2337aff0213d28db41d3e3daf48cee19b3d0bd82/README.md
Snapshot 文档：https://playwright.dev/mcp/snapshots

### 3.4 Microsoft 的歧义失败指导：点击超时以后先核对效果

官方远程 MCP 故障处理文档要求 observe–act–verify。它专门指出：打开 dialog 的动作可能已改变页面，不能因为 dialog 返回就重放；超时和连接断开不能证明动作没有发生，重试非幂等操作前必须先检查页面状态。

这直接支持 Kit 保留 `outcome_unknown`，以及把“响应丢失但 witness 已改变”纳入 smoke。文档描述的是 Microsoft 托管 MCP 产品，不能据此推断当前 ChatGPT Browser 的 API 形状完全相同。

一手文档：https://learn.microsoft.com/en-us/azure/app-testing/playwright-cloud-browsers/troubleshoot-remote-mcp-server

### 3.5 browser-use：当前版本和旧教程存在实质差异

本次固定版本的 `Agent.run(max_steps, timeout)` 拒绝同一 Agent 重入，也拒绝两个同时运行的 Agent 共享同一 Browser；取消使用 asyncio task cancellation。代码明示该 timeout 限制 agent loop，浏览器启动和关闭不计入。因此外层 harness 仍需总体 deadline，并为 cleanup 预留预算。

同一源码含 0.x→1.0 迁移映射；旧的 pause/resume/stop、max_failures 和旧状态字段不能直接照旧教程接入。它还将 `result.success` 描述为 agent 自己的 verdict。故该字段可以记录，但仍不能当作独立业务验收。

固定源码：https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/browser_use/agent/service.py

### 3.6 Agent S：grounding 输出必须绑定真实图像尺寸

S2.5 README 要求配置 grounding 的输出宽高，并说明示例面向单屏。S2 CLI 逐步截图再预测，说明图像、尺度和动作要构成一轮观察；但该示例使用 `exec(code)`，且以字符串中出现 done/fail 来分支。这是研究示例的动作接口，不适合作为 Kit 的可信请求验证器。

Kit 可以研究专用 grounding 在不提供 UIA 的自有 canvas fixture 上的作用，但当前优先补齐已安装 winapp 的可靠点击。不要为了增加功能数量再引入完整模型栈，也不要把 OCR/坐标后备变成绕过浏览器限制的通道。

固定示例：https://github.com/simular-ai/Agent-S/blob/0fff0e634869dab72027435b4586e62300185d41/gui_agents/s2/cli_app.py
固定说明：https://github.com/simular-ai/Agent-S/blob/0fff0e634869dab72027435b4586e62300185d41/gui_agents/s2_5/README.md

## 4. 八项可移植改进及验收方式

以下是架构建议。标记“保留”表示 Kit 已有部分实现，不能把建议重复计为本轮新增代码。

| 优先级 | 改进 | 对现有 Kit 的最小增量 | 具体验收 |
|---|---|---|---|
| P0 | 保留 ACK / observation / effect 分离 | 保持 core receipt 契约；为 smoke aggregate 增加明确 case outcome 与 evidence references | 工具 exit=0、但按钮无变化时不能 PASS；模型 DONE、但 witness 缺失时不能 PASS |
| P0 | 歧义结果不自动重放 | 复用既有 request ID、intent 和 reconcile，补齐 response-lost / dialog-opened 的测试分支 | 点击已发生、响应丢失；第二次相同请求不再点击；changed payload 同 ID 仍冲突 |
| P0 | 最终报告始终落地 | smoke runner 顶层 try/finally，截图失败也写 partial summary；各 case 明确 passed / failed / blocked / skipped / not_run | 中途截图抛异常、工具拒绝、cleanup 异常，都留下总报告；overall 不因外层 Python exit=0 变绿 |
| P0 | 前置能力报告区分能力与权限 | read-only capability probe 返回 backend/version、available/unavailable/unknown/blocked、当前可用动作 | 扩展“all sites”只记作浏览器扩展设置；没有实际 tool action receipt 时不写 verified；UAC/secure desktop 另列 handoff |
| P1 | 新观察绑定与失效条件 | 保留 HWND/PID/creation time、page identity；增加文档 generation/页面导航或布局变化后的失效说明与案例 | 重建同名按钮、导航、新 tab、目标窗口替换后旧 observation 被拒绝；拒绝后不自动新 ID 重试点击 |
| P1 | 整体 deadline 与阶段预算 | monotonic 总预算 + launch / act / observe / cleanup 子预算；只清理已确认自有进程和 tab | 故意让启动卡住、动作卡住、关闭卡住，各自有终止状态和残留所有权记录；不阻塞整个会话 |
| P1 | fixture 分层矩阵 | 在现有 native fixture 与 browser lab 内增加有代表性的异步/遮挡/失焦案例 | UIA invoke 与实际鼠标点击分开记录；disabled/overlay/delayed-effect/foreground-stolen各有预期；安全拒绝不算点击成功 |
| P1 | 固定依赖与可追溯复用 | 基于现有 source manifest 增加 upstream reference ledger；每个 adapter 文档写实际探测版本、兼容范围和 smoke 源码版本 | build 包排除所有 venv/证据/配置；源码 hash 可核；Linux mocked pass 不替代 Windows live；browser-use 旧 API 不静默接入新版 |

### 建议的证据结构

不要以新结构破坏已有 v1 receipt。新增 harness summary 可引用现有 request/receipt 文件，保持原证据不变：

```json
{
  "suite_schema": 1,
  "source_version": "candidate",
  "environment": {"os": "Windows", "adapter_version": "observed-version"},
  "cases": [{
    "name": "owned_button_click",
    "status": "blocked",
    "stage": "pre_action",
    "reason": "foreground_not_target",
    "effect": "not_dispatched",
    "receipt_ref": "relative/path/to/original-receipt.json",
    "cleanup": {"status": "verified"}
  }],
  "overall": "blocked"
}
```

`effect=not_dispatched` 只能由发起层确认尚未调用输入时使用；下游超时不能填这个值，应使用 unknown。不同 case 的 blocked/failed 是否使 suite 退出非零，应在 suite contract 中规定；不能把 “所有已执行 case 通过” 宣称成 “全部功能已通过”。

### 值得实现的少量反例

1. **按钮 overlay 遮挡**：定位存在，但 click 不应误点后面的页面。
2. **失焦与窗口替换**：UIA invoke 可成功，并不证明物理鼠标点击已正确发生。
3. **响应丢失**：counter 已加一，response timeout；核对 witness 后记录一次效果，禁止重放。
4. **stale screenshot**：文件名和 frame ID 更新，但像素/源时间未证实新鲜；不得证明实时画面。
5. **清理失败**：测试效果成立但自有进程残留，summary 单列 cleanup_failed。
6. **策略拒绝**：该目标停止；不使用另一个 adapter 把同一拒绝目标重新送进去。
7. **部分证据损坏**：原始 receipt 留存，validator 返回 unverified；不修原始证据凑通过。
8. **纯 echo 终端**：提示符回显输入不算计算结果，必须独立输出或文件见证。

这些测试的价值是验证不同失败机制；不建议机械增加大量与实现分支一一对应的测试。

## 5. 本轮研究没有建立的事实

- 没有证明 UAC 安全桌面可以自动点击；这需要 Windows 权限、桌面/会话与受支持提升流程的独立研究和受控验收。
- 没有证明当前 Edge 扩展允许本会话操作任何域名。扩展站点权限、宿主策略、设备连接和当前工具能力分别存在。
- 没有证明 OMP Relay 能访问被官方 Browser 拒绝的目标，也不建议尝试这种替代。
- 没有执行 OSWorld/WAA 完整 benchmark；其历史成功率不属于 RDC Operator Kit 的测试结果。
- 没有复制或运行 browser-use / Agent S 的任意 Python 执行层，也没有新建 browser broker。
- “仓库未 archived、近期 push”不能证明无漏洞、稳定或适合在日常机器上无隔离运行。
- 本文只读研究范围内没有创建 Scite Collection、购买全文、发外部消息或更改账号设置。引用决定可由主代理在整体验收报告中统一记录。

## 6. 参考文献与源码账目

### Papers

Xie, T., Zhang, D., Chen, J., et al. (2024). *OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments*. arXiv. https://doi.org/10.48550/arxiv.2404.07972

Bonatti, R., Zhao, D., Bonacci, F., et al. (2024). *Windows Agent Arena: Evaluating Multi-Modal OS Agents at Scale*. arXiv. https://doi.org/10.48550/arxiv.2409.08264

Agashe, S., Wong, K., Tu, V., et al. (2025). *Agent S2: A Compositional Generalist-Specialist Framework for Computer Use Agents*. arXiv. https://doi.org/10.48550/arxiv.2504.00906
本轮用途仅为相关论文身份核验；具体 CLI 结论来自所列固定提交源码，不假称由该论文全文得出。

### LICENSE 实际读取

- https://raw.githubusercontent.com/microsoft/playwright-mcp/2337aff0213d28db41d3e3daf48cee19b3d0bd82/LICENSE
- https://raw.githubusercontent.com/xlang-ai/OSWorld/0ad41bee56565efe7bb3c3a5ebc67590a1b8276f/LICENSE
- https://raw.githubusercontent.com/microsoft/WindowsAgentArena/eb220c4dcf64babefc1bfc287edda91ab04132ed/LICENSE
- https://raw.githubusercontent.com/simular-ai/Agent-S/dd11eec8708ea113d130c496fdaa24923807a2fd/LICENSE
- https://raw.githubusercontent.com/browser-use/browser-use/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/LICENSE

附属 `research-harness-source-ledger.json` 记录本轮来源 URL、HTTP 状态、取回字符数和 Scite 实际结果摘要，便于主代理复核。没有把完整第三方论文或 README 作为交付物复制。
