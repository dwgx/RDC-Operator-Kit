# 浏览器、MCP 与 Relay：第二轮研究及实现裁决

研究日期：2026-11-26 UTC。范围：RDC Operator Kit `0.1.0a1` 之后的下一步设计。本文是公开文档、固定源码和上游测试的研究记录；**本子任务没有安装服务、打开浏览器、访问登录会话或执行上游测试**。完整的 10 个候选、固定引用和 54 条来源记录见 [sources-browser.json](sources-browser.json)。

## 裁决

**本轮最小有价值切片：做一个离线的浏览器证据验证器，配合无账号的合成网页 fixture；先统一观察身份、截图时效、动作回执和失败状态，再对接已存在的 OMP。**

现有 Kit 已有 intent / receipt、unknown 不自动重放和独立见证原则。浏览器研究最值得补进来的内容，是这些原则怎样跨越 tab、context、worker 和截图。新增第二套 Relay 服务、完整 browser-use Agent 或新的浏览器产品，会同时带入会话、权限、生命周期和更新路径；目前没有证据说明这些新增层能解决现有的具体失败。

本机已经发现 OMP `19.2.1` 是主执行者提供的只读线索；本子任务随后独立核对了该版本上游源码。**OMP Browser Relay 是直接适配候选；AgentWorkforce/relay 是另一个项目。** 二者的名称相似，不代表共享实现或兼容契约。

所有候选都只适用于获得授权的独立测试站点。当前宿主已经拒绝的目标不能转交 OMP、RDC、CDP、其他 MCP、另一模型或桌面输入访问。这里的技术比较不改变 [AGENTS.md](../../AGENTS.md) 和 [现有架构](../ARCHITECTURE.zh-CN.md) 中的宿主策略边界。

## 证据分级与检索覆盖

| 级别 | 本文含义 | 不能推出什么 |
|---|---|---|
| 工具能力 | 当前连接器 schema 实际暴露的功能 | 开源项目有某 API，不代表本 ChatGPT 会话已经具有该 API |
| 文档 claim | 第一方 README、官方文档或发布说明写明的行为 | 不能据此说在 Setukou 的 Windows 已成功 |
| 源码检查 | 固定 commit 的选定实现片段已读取 | 不能据此排除未读路径的错误或所有竞态 |
| committed test | 固定版本中存在测试，已检查选定用例/断言 | 不等于运行过，不等于默认 CI 会执行 |
| 实测 | 本任务真正执行，并有对应输出和见证 | 本子任务这一栏为 0；上一轮实测仍以 [VERIFICATION](../VERIFICATION.zh-CN.md) 为准 |

检索使用 Exa Search 和 Firecrawl 的开发者研究流程：5 次 Exa 搜索请求了 31 个结果槽位；5 次 Firecrawl developer search 请求了 23 个结果槽位。这些是检索额度与候选命中规模，**不是“读完 54 个网站”**。Exa 的 2 次批量正文获取请求了 7 个 URL，6 个成功；旧 Browserbase URL 返回 `CRAWL_NOT_FOUND`，随后通过搜索找到当前文档路径。Firecrawl 对 BrowserOS 的一次 live scrape 返回了正文及多余的 Mintlify 编译数据，已提交 partial-quality 反馈，没有把噪声当作新的产品事实。

GitHub 连接器补充了固定 commit、LICENSE、package manifest 以及关键实现和测试。正文内容按问题选择读取，不声称穷尽这些仓库或全网。搜索中的第三方目录页、同名项目及旧版本片段没有自动进入结论。

## 优先级与固定版本

下面的版本是读取到的 manifest 或发布 tag。固定 `main` 的 package version 不是“已证明 npm / PyPI 发布、安装且跑过”的缩写。各链接都指向本轮读取的固定来源。

| 候选 | 固定引用 / 版本 | 许可 | 对本轮的决定 |
|---|---|---|---|
| OMP Browser Relay | [`b55cd1bb664d`](https://github.com/can1357/oh-my-pi/tree/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac)，`v19.2.1` | [MIT](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/LICENSE) | 最高优先，核对既有安装与契约；本轮先接证据格式 |
| Playwright MCP | [`2337aff0213d`](https://github.com/microsoft/playwright-mcp/tree/2337aff0213d28db41d3e3daf48cee19b3d0bd82)，manifest `0.0.86` | [Apache-2.0](https://github.com/microsoft/playwright-mcp/blob/2337aff0213d28db41d3e3daf48cee19b3d0bd82/LICENSE) | 最有用的隔离和生命周期参考；不新增绕行通道 |
| browser-use | [`94784c1f7ecb`](https://github.com/browser-use/browser-use/tree/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048)，manifest `1.0.8` | [MIT](https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/LICENSE) | 参考结果语义与迁移，不引入第二个 Agent 主循环 |
| Stagehand | [`97ff3e1189d3`](https://github.com/browserbase/stagehand/tree/97ff3e1189d3205bee10127fdde992f3313ef228)，manifest `4.0.0` | [MIT](https://github.com/browserbase/stagehand/blob/97ff3e1189d3205bee10127fdde992f3313ef228/LICENSE) | 参考 observe / act / extract 分层，后续可选依赖 |
| Browserbase | [当前 keep-alive 文档](https://docs.browserbase.com/platform/browser/long-sessions/keep-alive)，读取于研究日 | 托管服务条款；不由 Stagehand 的 MIT 覆盖 | 可选的远端 fixture，当前不新增账号或服务 |
| BrowserOS neo | [`62cb1ba80037`](https://github.com/browseros-ai/BrowserOS/tree/62cb1ba800373775964782be6d79cc63a2b1799a) | [AGPL-3.0](https://github.com/browseros-ai/BrowserOS/blob/62cb1ba800373775964782be6d79cc63a2b1799a/LICENSE) | 研究审计与故障案例，不把其源码直接装入 MIT 包 |
| Skyvern | [`b2f722af4f0f`](https://github.com/Skyvern-AI/skyvern/tree/b2f722af4f0fc383de64eb12b31d4f6dad958dfa) | [AGPL-3.0](https://github.com/Skyvern-AI/skyvern/blob/b2f722af4f0fc383de64eb12b31d4f6dad958dfa/LICENSE) | 参考 session 到期和错误分类，不引入完整工作流服务 |
| Chrome DevTools MCP | [`8c43179464d3`](https://github.com/ChromeDevTools/chrome-devtools-mcp/tree/8c43179464d368a6a3c7f8ce2ee024e1e736b795)，manifest `1.14.0` | [Apache-2.0](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/8c43179464d368a6a3c7f8ce2ee024e1e736b795/LICENSE) | 后续诊断候选，非当前 Edge 全兼容保证 |
| Browser MCP | [`a51ddc4ee221`](https://github.com/BrowserMCP/mcp/tree/a51ddc4ee2210b102468a52b114e6f00e5bd206e) | [Apache-2.0](https://github.com/BrowserMCP/mcp/blob/a51ddc4ee2210b102468a52b114e6f00e5bd206e/LICENSE) | 复用多浏览器身份和重连测试思路，不再装一套 daemon |
| Agent Relay | [`95b8afdac620`](https://github.com/AgentWorkforce/relay/tree/95b8afdac620feff75132d63a5c48e1eed9408d6)，manifest `18.16.1` | [Apache-2.0](https://github.com/AgentWorkforce/relay/blob/95b8afdac620feff75132d63a5c48e1eed9408d6/LICENSE) | 参考交付回执；既有 origin-dispatch 继续拥有执行 |

## 一、OMP Browser Relay：直接相关，但必须按版本裁决

### 已核到的接口和生命周期

`v19.2.1` tag 解析为完整 commit `b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac`，commit 时间为 2026-11-25 15:17:40 UTC；[Release](https://github.com/can1357/oh-my-pi/releases/tag/v19.2.1) 发布时间为同日 17:10:03 UTC。relay 子包 manifest 为 `0.1.0`，扩展 manifest 为 `0.2.0`；这三个数字描述不同组件，不能互相替代。

该版本的浏览器 facade 属于 Eval prelude，而不是单独的 AgentTool。官方文档列出结构化观察、accessibility snapshot、截图、截图差分、值读取和输入等 API；每个 named tab 一次只有一个 active run。超时后的 worker 恢复会让原有 element IDs、run globals 等失效，必须重新观察。被借用的 relay tab 与 OMP 自己创建的 tab 有不同关闭语义；重新附着也不会自动重放可能已经发生的输入。这些是适配器应继承的契约，而不是包一层 `try/retry` 就可抹掉的错误。[浏览器文档](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/docs/tools/browser.md)

当前推荐形式是字符串 `app: "relay"`。固定源码里的 `withStringApp` 仍兼容旧的对象式 `app`，把 `legacy.relay === true` 转换为上述字符串，并把旧 target / args 放到顶层。因此，“旧 app.relay 全面失效”不成立；新输出可以使用规范形式，兼容性诊断应先读取版本。[browser.ts](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/coding-agent/src/tools/browser.ts)

普通子 Agent 默认跳过用户 relay 配置，但 sidebar 产生的 relay-only session 是例外。不能把“子 Agent 默认隔离”写成对所有入口都成立的保证。[kind.ts](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/coding-agent/src/tools/browser/relay/kind.ts)

### 两处文档矛盾

| 问题 | 读取到的矛盾 | 本轮裁决 |
|---|---|---|
| 扩展 ID | browser 文档仍提从旧 unpinned 扩展迁到 pinned ID；relay README 的 Updates 段写 manifest 不含 key | 固定 [manifest](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/browser-relay/extension/manifest.json) 确实无 key；[native-host-manifest.ts](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/coding-agent/src/tools/browser/relay/native-host-manifest.ts) 按安装路径派生的 extension IDs 写 allowed_origins。不能继续套用旧版 pinned-ID 操作说明 |
| 首次安装 | relay README 的 Setup 称安装会写 Chrome profile 并可能重启 Chrome；同文 Updates 又说首次加载必须手动 | 将安装状态、真实 help 与代码分开核对；本轮未执行 install / sync，不把它当作无副作用诊断 |

这两处都是同一固定版本的公开材料内部冲突，不能用搜索排名决定谁对。源码检查也只支持已读路径，不等于本机安装版本的所有打包细节都一致。[relay README](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/browser-relay/README.md)

### 已检查的上游测试

- [busy-tab](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/coding-agent/test/tools/browser-busy-tab.test.ts)：构造竞争调用，区分同一 Agent 未 await 和另一 Agent 正在操作。
- [open-lease](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/coding-agent/test/tools/browser-open-lease.test.ts)：取消一个 acquisition 时保留另一个调用的租约；有 mock，不能称为实机浏览器测试。
- [tab-isolation](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/coding-agent/test/tools/browser-relay-tab-isolation.test.ts)：own / borrowed / persist tab 的生命周期；受 Chromium 可用性门控。
- [native-host](https://github.com/can1357/oh-my-pi/blob/b55cd1bb664d8ab46ddc77f2a34eb47555dbf1ac/packages/coding-agent/test/tools/browser-relay-native-host.test.ts)：动态端口发布与断开后的撤销、chat 子进程与 terminal relay 的区别。

这些用例适合借鉴测试意图。全部是 **committed tests inspected，executed = false**。本轮不复制其浏览器入口，也不把 localhost、域名参数或另一模型当作宿主授权边界。

## 二、Playwright MCP：最成熟的隔离参考，版本映射不能偷换

[固定 README](https://github.com/microsoft/playwright-mcp/blob/2337aff0213d28db41d3e3daf48cee19b3d0bd82/README.md) 清楚区分 persistent profile、isolated context 和 extension 接入。一个持久 profile 同时被多个实例使用会冲突；并行客户端应采用隔离 context 或独立目录。共享 context 这个选项本身就意味着共享状态，不能当成并发输入互斥器。

本轮还读取了 Playwright 核心 repo 的 `049226728d2da8054db18b04782a9848b755855e`：

| 固定文件 | 能支持的结论 |
|---|---|
| [program.ts](https://github.com/microsoft/playwright/blob/049226728d2da8054db18b04782a9848b755855e/packages/playwright-core/src/tools/mcp/program.ts) | isolated client 有独立 context / idle timer；dispose 处理各 client 与最后一个连接的差别 |
| [http.spec.ts](https://github.com/microsoft/playwright/blob/049226728d2da8054db18b04782a9848b755855e/tests/mcp/http.spec.ts) | committed 用例覆盖多个 isolated client、共享 context 的 close 拒绝、浏览器崩溃后的重新建立 |
| [idle-timeout.spec.ts](https://github.com/microsoft/playwright/blob/049226728d2da8054db18b04782a9848b755855e/tests/mcp/idle-timeout.spec.ts) | 启动归己的浏览器 idle close，与借用连接 idle disconnect 分开测试 |

**关键版本限制：** MCP `0.0.86` 的 [package.json](https://github.com/microsoft/playwright-mcp/blob/2337aff0213d28db41d3e3daf48cee19b3d0bd82/package.json) 依赖 `1.66.0-alpha-2026-11-18`；上述核心源码 commit 日期是 2026-11-21。没有完成 release 映射，不能说这些新测试覆盖的所有修复已进入这个 MCP package。这里的价值是清楚的回归模型，不是下载某个 latest 后保证成功。

## 三、browser-use 与 Stagehand：新版本改变了集成方式

### browser-use 1.0.8

当前 [README](https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/README.md) 描述的是 Python persistent REPL、browser-harness 和 raw CDP。网上常见的 DOMWatchdog、旧 BrowserSession 和逐 action history 教程属于旧架构，不能直接拼到新版本。

[迁移文档](https://github.com/browser-use/browser-use/blob/94784c1f7ecb6b0a5f565b7f9fba59e395b7e048/MIGRATING.md) 明确说明默认 `Browser()` 已改为云端；`is_done()` 只反映运行结束，`is_successful()` 仍是 Agent 的判断，不能代替独立见证。错误也可能通过返回值 `status="error"` 表达。Kit 可借鉴这套清楚的结果分类，但再套一个完整 autonomous Agent 会重复现有 OMP 的规划、模型、工具和生命周期。本轮没有核验其并发控制实现或运行测试。

### Stagehand 4.0.0

[v4 文档](https://docs.stagehand.dev/v4/reference/stagehand) 的 browser handle 归调用者所有，一个 handle 只能配一个 Stagehand 实例。`observe`、`act`、`extract` 的职责适合借鉴；v3 的 constructor / env 示例不能不经迁移混用。

[act 文档](https://docs.stagehand.dev/v4/basics/act) 说明，传入已经观察到的 Action 会直接使用其 selector；[cache 说明](https://www.browserbase.com/blog/stagehand-caching) 讨论的是复用定位结果减少模型调用。**cache hit 仍会执行动作，不能作为 request_id 去重。** Kit 的 durable intent / receipt 是另一层问题。后续若加入 Stagehand，应只解决确实需要模型定位的页面；它不应为了“自愈”重放结果未知的点击。此项目本轮主要是文档级验证，没有声称执行或审阅了它的完整测试套件。

## 四、Browserbase、BrowserOS 和 Skyvern：可观察性与服务范围

### Browserbase：远端 session，并非本机浏览器

[keep-alive](https://docs.browserbase.com/platform/browser/long-sessions/keep-alive) 保留断线后的 session，但仍有超时且需明确释放；付费计划前提由该页说明。多个连接能接到同一 session，不代表它们的写入有业务互斥。

[Session Replay](https://docs.browserbase.com/features/session-replay) 描述每 tab 的 HLS 历史视频。历史 replay、当前 screenshot、实时交互状态是三个对象。未来报告中应分别带 session ID、page ID、capture 时间和接收时间，不能拿昨天的录制充当当前观察。本轮不创建云端 session；Stagehand 的 MIT 许可证也不授权复制 Browserbase 托管服务。

### BrowserOS neo：tab group 不等于安全隔离，DOM replay 不等于视频全貌

[tabs-and-isolation](https://docs.browseros.com/neo/tabs-and-isolation) 将 Agent 创建的 tabs 分组，与用户 tabs 分开管理。该分组是操作归属和可见性机制，不能推出 cookies、站点登录态或所有写入都隔离。

[audit-and-replay](https://docs.browseros.com/neo/audit-and-replay) 描述本地截图与 DOM 变更回放，同时明确 canvas 和鼠标移动不在录制中。这是“实时看图”设计中的反例：DOM 回放可能很清楚，却仍缺少页面视觉内容。该页还声称无 telemetry，而更具体的 [privacy](https://docs.browseros.com/neo/privacy) 页说明匿名产品事件默认开启、可以关闭；报告采用后者的细分披露，不使用“完全零遥测”标签。

已读取的 [OOPIF recovery test](https://github.com/browseros-ai/BrowserOS/blob/62cb1ba800373775964782be6d79cc63a2b1799a/packages/browseros-agent/crates/browseros-mcp/tests/oopif_snapshot_live.rs) 显式标记 `#[ignore]`，需要真实 browser 和 fixture。它模拟 detach 事件丢失后的 dead session，允许首次只读失败并要求后续恢复。这个测试存在，不代表普通 `cargo test` 已运行它。

### Skyvern：将“到期”与“还能重试”分开

[浏览器文档](https://www.skyvern.com/docs/browsers) 要求同一 session 的前后任务顺序执行，给 expired / closed / startup-timeout 明确错误类别。修改超时时长的操作可能在重复调用时再次增加时长，因此也不能通用自动重试。

固定 [timeout tests](https://github.com/Skyvern-AI/skyvern/blob/b2f722af4f0fc383de64eb12b31d4f6dad958dfa/tests/unit/test_browser_session_timeouts.py) 包含很有用的反例：供应商给 session 固定生命周期时，本地观察到新的活动不能凭空延长它。Kit 应把上游硬截止与本地 soft timeout 分开记录。Skyvern 的完整服务、数据库与 Agent 工作流超出当前薄 CLI 的需要；本轮只参考契约和测试意图。

## 五、另外两个浏览器 MCP 与公共 Agent Relay

### Chrome DevTools MCP

[固定 README](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/8c43179464d368a6a3c7f8ce2ee024e1e736b795/README.md) 的强项是 network / console / performance / screenshot 诊断，正式支持范围是 Chrome 与 Chrome for Testing，不能直接外推成 Edge 全兼容。它默认有使用统计，CrUX 的 trace URL 传输又是另一个设置。

[配置](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/8c43179464d368a6a3c7f8ce2ee024e1e736b795/docs/configuration.md) 提供 pageId routing 和 idle close / disconnect 区分。pageId routing 有助于避免选错页面，仍不能阻止两个调用同时修改同一页。本轮未审阅它的关键执行源码或测试，不把文档中的“可靠自动等待”当作本机结果。

### Browser MCP

当前 [架构 README](https://github.com/BrowserMCP/mcp/blob/a51ddc4ee2210b102468a52b114e6f00e5bd206e/packages/mcp/README.md) 是 extension + per-user daemon + 每个 profile 独立 slot。文档把后台 tab 可见性、重连等待、多个浏览器 ID 冲突和恢复拆得很细，也明确其文件操作沿用当前用户权限。

[backend tests](https://github.com/BrowserMCP/mcp/blob/a51ddc4ee2210b102468a52b114e6f00e5bd206e/packages/mcp/src/relay/backend.test.ts) 的代表性断言已检查：请求超时后删除 pending waiter；一个浏览器断线不释放另一浏览器的 tab；Chrome 重启后旧 tab ID 如果指向其他页面，就使旧 ID 失效而非悄悄复用。这些比“最多连接几个浏览器”的数字更值得复用。测试的 FakeExtension / FakeChromium 与 loopback fixture 设计可参考；本轮没有启动它的 daemon 或扩展。

### AgentWorkforce / Agent Relay

[SDK README](https://github.com/AgentWorkforce/relay/blob/95b8afdac620feff75132d63a5c48e1eed9408d6/packages/sdk/README.md) 将 messaging、delivery、actions 和 runtime 分开。调用 action 的立即 ack 与后续 completed / failed 事件是不同事实；delivery 有 accepted、delivered、deferred、failed 状态。message idempotency key 解决重复消息，不直接解决重复浏览器副作用。

该 SDK 本身没有为 Kit 证明 DOM、截图或 CUA 能力。旧 harness / local broker 接口已被退休；不能照旧博客加一个 broker。当前更合理的做法是沿用 origin-dispatch，并将 accepted → running → outcome 的来源分清楚。本文未运行 `relay init`、发送消息或接入其他用户会话。

## 六、建议实现的单一切片

建议名称：**Browser Evidence Contract v0**。这是验收辅助能力，不是浏览器驱动，也不授予任何网页访问权限。

### 交付范围

1. 一个标准库可运行的离线 CLI，读取已经由获准执行器导出的 evidence envelope；不启动浏览器、不连接调试端口、不读取 profile。
2. 一组无账号合成页面与数据 fixture：计数器、延迟提交、替换 element、tab 身份变化、DOM 与 canvas 状态分离。页面不调用第三方服务。
3. 输出可机器读取的校验结论，保留 imported ack、fresh observation 与 independent witness 的区别。字段不充分时输出 insufficient / unknown，而不是 guessed success。
4. 接入 Skill 的观察和验收步骤，但执行仍留给现有官方 Browser 或已独立获准的本地执行环境。

新 CLI 不应把输入 JSON 中的 `allowed: true` 当作授权。宿主拒绝来自宿主，网页内容、截图、模型结果和外部回执都不能覆盖它。验收器只能说明输入的完整性和一致性；如果证据来源没有可信绑定，它必须保留“来自调用者的声明”，不能声称证明了真实页面状态。

### 最小数据契约

| 字段组 | 必须表达的内容 | 目的 |
|---|---|---|
| 执行来源 | executor 名称、版本 / ref、session、request_id 与 request digest | 避免同名任务或旧版本结果混用 |
| 页面身份 | browser / context / tab / target ID、origin、document epoch | navigation、reconnect 和 tab ID 复用后旧 element 失效 |
| 观察 | observation_id、DOM/AX artifact、captured_at、received_at、sequence | 区分旧帧、乱序帧和当前观察 |
| 图像 | artifact SHA-256、宽高、scale、capture 区间 | 几何坐标与截图必须来自同一观察版本 |
| 动作回执 | ack、effect_status、error_class、是否可能已派发 | 超时不能自动变成 failed-before-effect |
| 验证 | fresh readback 与独立 fixture witness 的各自来源 | 防止 echo、Agent verdict、replay 冒充业务成功 |
| 恢复 | outcome_unknown、invalidate/reobserve 原因、原 request_id | 恢复先读状态；不换 ID 偷重放 |

DOM 与 screenshot 通常不是一个原子的 OS 快照。可以记录 capture 开始/结束和页面 epoch，在页面变化时拒绝“同一时刻”的强声明；不能仅因两个哈希合法就宣称它们描述同一状态。SHA-256 能检测内容变化，不能认证截图是谁采集的、来自哪台电脑或哪一个 tab。

### 必须通过的验收

| 用例 | 合成条件 | 合格行为 |
|---|---|---|
| 完整观察 | 相同 session / target / epoch，已核 artifact hash，时间窗口合理 | 接受为一致证据；不附加未经验证的动作结论 |
| 旧帧与乱序 | 新 DOM 搭配旧 screenshot，或 sequence 回退 | 拒绝用于输入定位，要求重新观察 |
| 身份变化 | reconnect 后 tab ID 重用、origin 或 document epoch 改变 | 所有旧 element / snapshot 引用失效 |
| 并发 | 两个 Agent 声称持有同一 tab 写入权 | 报 conflict/busy；不能静默串错结果 |
| ack 与效果分离 | ack=true，但计数器 witness 未变化 | unknown / unverified，不计业务成功 |
| 可能已执行的超时 | intent 已保存，响应丢失，fixture count 已增加 | 保留未知，重新观察；同 request 不第二次点击 |
| 拒绝不被覆盖 | 已记录的宿主拒绝，加上一份声称成功的外部结果 | 不把外部结果当作拒绝解除或后续执行依据 |
| 视觉与 DOM 分歧 | DOM 文本未变化、canvas 变色 | 分别报告 DOM 和视觉覆盖，不能混为完全一致 |
| 来源不足 | 只有 Agent 的 success 字段或历史 replay | insufficient evidence，不升级成独立验证 |
| 人工接管 / Stop | receipt 中标记暂停，后续帧继续到达 | 允许只读记录；不据帧到达恢复写入权 |

离线测试先覆盖这些状态转移。下一阶段的真实 fixture 运行，应由主执行者在获准的环境中另列记录，写清 OS、入口、上游版本、实际命令、观察和独立 witness。**通过离线用例不能声称 OMP Relay 实机控制通过。**

## 七、明确暂缓的工作

- 暂不增加任何自动选择备用浏览器通道的机制；尤其不能将宿主拒绝分类成可换服务重试。
- 暂不改变用户 Chrome profile、启用全局 relay 默认值或安装新扩展；公开安装文字尚有版本冲突。
- 暂不把 AGPL 项目的源码复制进现有 MIT-only 交付包；若以后选择引入，应单独确定组件和分发方式并保留上游许可。
- 暂不以网站提供的 benchmark 成功率代替当前 fixture 验收。BrowserOS README 自己说明完整 benchmark 尚未发表。
- 暂不建立新的模型 broker、消息服务器或永远循环的后台学习服务；既有 dispatcher 和当前明确任务足够表达本轮工作。

## 后续应优先消除的未知

首要未知不是“还能不能再找到一个浏览器库”，而是 **Windows 已有 OMP 安装究竟与哪个打包状态对应**：可执行版本、扩展版本、native host 注册、既有 dispatcher 契约与源码是否一致。主执行者的只读设备核对应成为下一步依据。然后才是在独立获准 fixture 上验证 fresh observation → 单次动作 → 独立 witness → 正常释放的完整链。

若这个切片通过，下一轮可分别讨论低帧率图像流、OMP receipt 导入与 terminal/TUI 会话监督。每一项都应有有限验收范围，而不是以不断新增 subagent 数量代替完成证据。

