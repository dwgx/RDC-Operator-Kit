# Wave 05：现代界面、只读 MCP 与 Linux 可靠性

日期：2026-11-26（Asia/Tokyo）。目标版本：`0.1.0a5`。基线为本地 a4 提交 `d9ab1b38fff68e77c88841c050b8c038f52dcdb5`。

**当前结论：a5 初次 Windows 源码快照九个顶层 case 全部 passed；MCP smoke 判定缺口已修复，后续真实两会话 72 项通过。本地与 Windows core 的后续复验、安装与公开发布按下方时间线记录。** 本文只把有实际记录的检查写成通过，保留原始执行范围与后续发现。公开 GitHub 仓库、Release 和 Pages 发布已获所有者明确授权，目标为 `dwgx/RDC-Operator-Kit`；授权与发布完成是两个状态。

这次更新围绕可使用的接口、保守的失败语义与能复核的证据展开。没有声称“全网已研究完”“任意应用绝对可控”或已经比拟全部本地 Agent 能力。历史记录保留在 [Wave 04](REVIEW-WAVE4.zh-CN.md)、[Wave 03](REVIEW-WAVE3.zh-CN.md) 和 [Wave 02](research-wave2/REPORT.zh-CN.md)，各自只证明当时版本与环境。

## 1. 本版实际改动

| 范围 | 改动 | 实际价值与边界 |
|---|---|---|
| 静态首页 | 新浅色／深色视觉、层级与排版；证据搜索与分类组合；空结果重置；复制并发与异常反馈 | 更容易检索公开能力、安装与证据说明；不连接电脑、不调用模型、不执行命令 |
| Browser Evidence Lab | 视觉与首页协调，改进间距、主题、焦点和 reduced-motion 样式 | 原 counter、延迟动作及 witness 脚本逐字节保持 a4；新布局未经过浏览器验收 |
| MCP 输出 | 三个只读工具具有可发现的 object 输出 schema，并绑定固定 SDK 的实际输出模型 | 客户端可验证结构；schema 不是权限、真实性或业务成功证明 |
| MCP 记录摘要 | 新增 `operator_request_status(request_id)` | 无需返回原 args、command、path、action 或 digest 即可查看保存记录组合；不推断实时运行状态 |
| Linux 安装器 | 解释器执行前拒绝 `.venv/bin` 目录 symlink | 修复已复现的外部 fixture interpreter 执行路径；保留正常 venv 的 `bin/python` symlink |
| liveness 诊断 | 开始、每项前后与最终状态持续原子 checkpoint | 中途失败保留已返回结果并停止后续 case；持续存储故障仍需结合本次返回判断 |
| GitHub workflows | Actions 使用固定 commit SHA | 减少浮动 action revision；不等于 workflow 已运行或依赖完全锁定 |

实现位置：[静态首页](../site/index.html)、[交互脚本](../site/app.js)、[Lab](../site/lab.html)、[MCP server](../rdc_operator/mcp_server.py)、[Linux installer](../scripts/install.sh)、[liveness probe](../scripts/probe_terminal_liveness.py)。当前操作契约见 [能力表](CAPABILITIES.zh-CN.md) 与 [架构](ARCHITECTURE.zh-CN.md)。

## 2. 只读 MCP：接口与验证分层

MCP 继续使用本地 stdio 与官方 `mcp==2.3.0`，启动时固定 config/state，没有公开监听器。SmartCLI 0.3.5 的 MCP 1.x 依赖留在独立环境；本轮没有合并两者。SDK/Pydantic 懒加载，基础 CLI 仍可仅依赖标准库。安装命令与完整 schema 语义见 [MCP 指南](MCP.zh-CN.md)。

| 工具 | 返回 | 不代表什么 |
|---|---|---|
| `operator_capabilities` | 版本、工具名与静态配置形状 | 不代表程序存在、设备可用或动作已验证 |
| `operator_receipt` | 一个 ID 的原始保存回执；保留未知/失败状态及可能存在的私有内容 | 不代表自动脱敏导出、来源真实性或当前业务结果 |
| `operator_request_status` | 固定记录状态、理由与保存的 receipt status | 不代表 live running、取消、可重试或独立业务成功 |

状态工具最多对 intent/receipt 各读取两轮，比较文件身份与内容。结果为 `no_records_observed`、`intent_without_receipt`、`receipt_recorded` 或 `inconclusive`，始终保留 `snapshot_atomic: false`。孤立 receipt、摘要不符和两轮间变化不会被当成可恢复执行的许可。非法身份、不安全文件或读取中变化返回简短错误，原 intent 内容不进入摘要。

实现通过 `Annotated[CallToolResult, OutputModel]` 给手工结果绑定实际验证模型，保留 JSON 文本与结构化内容。固定 false 字段拒绝数字 `0`，schema version 的整数 `1` 拒绝布尔 `true`。这解决的是 JSON 类型契约；原始 receipt 仍是待解释的数据，不能把它当作新的工具指令。[MCP Tools 规范](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [SDK 结构化输出文档](https://py.sdk.modelcontextprotocol.io/v2/servers/structured-output/) · [固定 SDK 验证源码](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/mcpserver/utilities/func_metadata.py)

### 已执行的本地 MCP 检查

环境：Linux 6.18.57 x86_64、CPython 3.12.14、Pydantic 2.13.4；全局 MCP 是 1.29.0，没有在本轮替换它。

| 检查 | 实际结果 | 可证明范围 |
|---|---|---|
| `python -m unittest discover -s tests -p test_mcp_contract.py -v` | 31 项通过，0 failures/errors/skips | 22 项业务读取、隐私与竞态契约；2 项真实 Pydantic + 假 SDK 注册；7 项进程身份合成反例 |
| `python -S -m unittest discover -s tests -p test_mcp_contract.py -v` | 31 项运行，29 通过，2 项 Pydantic 模型检查明确 skip，0 failures/errors | 当前 Python 3.12 不加载 site-packages 时，业务测试仍能运行；不是 Python 3.10/3.13 CI 结果 |
| 四个受影响文件 `git diff --check` | exit 0 | 空白检查；不证明真实 SDK wire 行为 |
| a5 固定 SDK 2.3.0 的首次真实 Windows stdio | 两个独立会话各 30 项检查为 true，summary passed | 是本版实际执行；下文另列独立 review 发现的 smoke 判定缺口，不能据此声称验收逻辑无缺陷 |

对应源码测试为 [`test_mcp_contract.py`](../tests/test_mcp_contract.py)。实现者的两个模型测试只替换 SDK 注册器，不是完整协议验收；该区别保留在报告中。

[`smoke_mcp.py`](../scripts/smoke_mcp.py) 的首次真实执行使用 Windows 11 / Python 3.14.7 / SDK 2.3.0，modern `discover` 实际协商 `2026-07-28`，legacy `initialize` 实际协商 `2025-11-25`，两个独立会话各 30 项检查为 true。检查包括三个工具、输入与输出 schema、隐私哨兵、孤立 receipt、digest 不符及合成记录字节不变。专属 fixture launcher 把一个合成 ID 的 `snapshot_atomic` 改为数字 `0`，真实 SDK 返回错误；两会话的 SDK 持有进程及预先持有的 worker HANDLE 均确认 exit 0。

该次 summary 明确记录 `smoke_execution: source_tree`、`kit_source_version: 0.1.0a5`、`kit_distribution_version: 0.1.0a4` 和 `installed_package_validation: false`。它没有证明 a5 已安装。记录中的原 receipt 与全部合成 request records 前后字节均未改变。

### 独立 review 追加：smoke 的 JSON 判定需加强

后续独立 reviewer 构造坏 SDK 响应时发现一项 P2：Python 容器相等比较会把 `false` 和数字 `0` 当成相等，状态工具检查又没有全面比较文本内容与 `structuredContent`。这使某些错误或两通道不一致的合成响应可能被 smoke 误判通过；没有据此认定生产 `as_result` 已实际泄露内容。

主线将增加类型敏感的 JSON 等值检查，并对全部成功响应核对 JSON 文本与结构化内容。**该修复和受影响的 Windows MCP 定点复验结果待补入。** 上述 60 项是原冻结快照的实际结果，不改写原回执，也不将它扩展为 review 后的最终验收。没有为此重复计数整个九项 Windows suite。

## 3. Linux：两个有反例的修复

### 安装目录归属

a4 在拥有 `.venv` 的前提下，没有拒绝 `.venv/bin` 目录链接。原始隔离反例让该目录指向另一自有 fixture，并观察到其中的 stub interpreter 确实运行。a5 在解释器执行前拒绝该目录链接，没有改动正常 `bin/python` 文件 symlink 的语义。

实现者运行 `test_install.py`：**6/6，0 skip，exit 0**。其中四项是既有 WinApp 合成归档检查，两项是 Linux installer 回归；不能宣传成六次 Linux 真机安装。

独立 reviewer 使用相同类型的相对目录链接对照 a4 与 a5：a4 的外部合成 sentinel 出现，a5 拒绝且 marker 字节不变；dangling `bin` link 也被拒绝。另实际创建普通无 pip venv，确认 `bin/python` symlink 保留且 `sys.prefix` 指向该自有环境。安装器正常运行到缺少 pip 才停止；没有下载或安装第三方包。范围不包括同权限恶意并发替换或所有 Linux 发行版。

### liveness 的部分结果与归档错误

a4 的列表推导会等全部 case 返回后才写 summary。独立反例保留第一项实际完成的自有 pipe fixture，再让第二项启动抛出异常，结果是首项已完成但没有任何 summary。

a5 在首项前、每项前后与结束时写 checkpoint，保存 planned cases、active case、已返回结果、错误及中断标志。未返回的 case 使用未知 cleanup 状态，不从异常倒推已清理。启动异常、checkpoint 失败或中断后不会继续启动后续 case。

实现者运行 `test_liveness.py`：**18/18，0 skip，exit 0**；包括既有十二项和六项有实际行为意义的回归。独立 reviewer 另构造七种归档／中断故障，并实跑一次 `waiting-input` child 后注入 checkpoint 失败，确认已返回业务与 cleanup 结果保留、下一项未启动、最终为 FAIL。独立补测没有重复计入实现者的 18 项。

| 本次结果 | 退出码 | 读取报告时要核对 |
|---|---|---|
| 全部期望满足且归档成功 | 0 | stdout PASS 与 `summary_current: true` |
| 功能或启动失败 | 1 | 已完成项与失败／未返回项分别保留 |
| KeyboardInterrupt | 130 | 中断标志、active case 和 cleanup 不确定性 |
| 非中断的归档失败 | 3 | stdout FAIL，且最后文件可能不是当前报告 |

**已验证的存储限制：** 最终 PASS 已 replace 到磁盘后，若后续发生异常，且唯一一次保守 FAIL 写回也持续失败，旧文件可能仍显示 PASS。程序此时返回 FAIL、非零退出与 `summary_current: false`。消费者不能只读旧文件的 `status` 判定本次成功。本次独立审查未在上述四文件范围确认新的 P1/P2；不把这项限定结论扩展成仓库全面无缺陷。

## 4. 网页现代化与独立 review

首页保留 7 个 tabs、4 种证据分类、4 组恢复说明与 3 个复制入口，新增本地搜索。查询先 NFKC 规范化并转为小写，再按空白分词做 AND 匹配；搜索与分类共同生效。空结果可以重置，清空查询保留分类。查询只处理公开页面文本，不联网、不写入持久化查询记录。

复制按钮在 Promise pending 时拒绝同按钮重复写入，结束后恢复 busy 状态；clipboard 不可用时尝试选择已有文本，选择也失败则明确提示。每个按钮只保留一个反馈重置 timer。浅色／深色主题和 keyboard tabs 保留，Lab 同步视觉，但业务脚本与 a4 完全相同。

### 已执行检查的范围

| 检查 | 已记录结果 | 限制 |
|---|---|---|
| 实现者静态 inventory | 初始交接快照 38 个唯一 ID、7 tabs/7 panels、16 个本地引用，无远程 script/iframe | 后续主线标签或链接修改需再核对最终快照 |
| 实现者 Node VM | 15 组检查通过 | 合成 DOM、事件与 clipboard；不是浏览器 |
| 独立搜索与分类反例 | 4 分类 × 8 查询，32 组合符合预期 | 只证明对应算法和事件路径 |
| 独立 tabs 边界 | 7 tabs × Left/Right/Home/End，28 组合符合预期 | 不是屏幕阅读器或真实键盘验收 |
| 独立复制异常 | pending 重入、延迟拒绝、五种 selection/Range 失败及 timer 收尾符合预期 | 不证明真实 clipboard permission 流程 |
| Lab 业务脚本 | 与 a4 逐字节相同；SHA-256 `f8028b0cc3768dbc300685aac89d8001e4034237afdccf6d5390a611e98ede70` | 不证明新版布局或旧坐标仍可用 |
| 颜色对检查 | 16 组静态前景／背景配对，最小比值约 4.63:1 | 不是完整 WCAG、实际渲染或辅助技术审计 |

### 独立发现：输入法组合期间的 Escape

reviewer 在实际 `app.js` 的独立 Node VM 中派发 `key="Escape"`、`isComposing=true`、`keyCode=229`，观察到已有 `MCP 终` 查询被清空并触发 `preventDefault`。这是一个确定的 handler 反例，列为 P2；没有冒充 Windows 真 IME 复现。

主线已在 handler 开始加入 `event.isComposing || event.keyCode === 229` 守卫。reviewer 读取新源码后独立复验三个分支：`isComposing=true` 保留查询，legacy `keyCode=229` 保留查询，普通 Escape 清空查询；三者均保留当前分类，只有普通 Escape 调用 `preventDefault`。**定点 3/3 通过，Node exit 0，F1 在这三个事件分支中已修复。** 没有因此宣称真实 Windows IME 或浏览器验收；初始失败和评审快照保持原样。

### 实际浏览器验证为何停止

a4 的官方 Edge Lab 曾完成语义与截图定位点击、延迟效果、reset 与 reload。这是旧版自有 fixture 的有限证据。随后 a4 首页 Markdown 导航返回 `ERR_BLOCKED_BY_CLIENT`；返回同一 localhost origin 的操作又被自动审批拒绝。该目标的浏览器验证已经停止，没有通过桌面、OMP、CDP、shell 或其他渲染器绕过。

历史 ChatGPT origin 的 `BLOCKED_BY_POLICY` 与本地 `file://` 渲染拒绝仍分别保留。扩展的“Allowed on all sites”不能取消宿主拒绝。a5 的现代 UI 因此没有实时浏览器、响应式视口、真实剪贴板或辅助技术通过结论。仓库／Pages 发布状态也不能充当这些交互测试的替代证据。

## 5. HMC 与两个真实 OMP 任务

### HMC

RDC 设备列表当时可见 HMC 设备，但首个只读环境 probe 即收到月度额度暂停，指示不要重试或重连。该调用没有返回 PID、OS、Python、cwd 或执行结果。之后未再调用该设备、未换账户或传输路线，也未在其上建立目录、安装依赖或启动服务。

因此本报告没有 HMC Linux 通过项。当前 Linux 事实属于本地工作区；不能从设备在线推导其 OS 或工具版本，也不能用本地 fixture 替代 HMC 实机。

### OMP

主线真实使用既有 `origin-dispatch`，每项冻结只读 brief、固定模型与 `max` effort，限定一次 attempt 和 180 秒总预算。没有新 broker、全局凭据变更或静默模型替换。

| 任务 | 模型 | 实际返回 | 可以采用的 review 结论 |
|---|---|---|---|
| CI／Pages 只读审阅 | `lunaroute/glm-5.3-flash` | 约 179 秒；`BLOCKED`、`upstream_abort`、`Deadline exceeded`；final 为空 | 无，不能声称 GLM 已完成 code review |
| MCP 设计只读审阅 | `deepseek/deepseek-flash` | 约 1.6 秒；`BLOCKED`、`provider_error`、`402 Insufficient Balance`；final 为空 | 无，不能声称 DeepSeek 已完成 code review |

这些是实际调度失败，保留原生回执，不转换成 `DONE`。后续 native subagent 的审查是独立工作，不能记在 OMP 模型名下。回执中的 usage 为零也不能据此推断服务免费或用户没有其他费用。

## 6. 研究来源与阅读范围

本轮研究代理使用 Firecrawl 与 Scite，并以官方规范及固定源码作实现依据。以下是实际读取范围，不是全网覆盖声明。

| 来源 | 实际读取 | 没有声称完成 |
|---|---|---|
| [MCP Tools 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) | Firecrawl 返回 HTTP 200；工具定义、结构化输出、output schema、错误与安全相关主体段落 | 没有逐字阅读响应附带的全部 hydration 数据 |
| [官方 Python SDK structured output](https://py.sdk.modelcontextprotocol.io/v2/servers/structured-output/) | Firecrawl 返回 HTTP 200；主体文档 | 不是整个 SDK 文档站审计 |
| [固定 SDK `func_metadata.py`](https://github.com/modelcontextprotocol/python-sdk/blob/2118f14f8a19bc158d8a1cf90af58d85d187f849/src/mcp/server/mcpserver/utilities/func_metadata.py) | 初始化、结果转换与注解推断分支 | 不是整个上游仓库逐行 review |
| Firecrawl 文档发现／检索 | 一次 Alexandria 发现为空；另取得官方迁移、测试及 issue 的检索片段 | issue 报告没有自动成为本项目已复现事实 |
| Scite | 5 条搜索元数据、1 个 DOI 核对、3 段相关摘录与 1 条 APA 元数据 | 未阅读全文、未完成系统综述，不推导论文已同行评审 |

Scite 项目为 Birhan 等人的 *COPEX: Benchmarking LLM Robustness to Adversarial Context Across Model Context Protocol (MCP) Layers*，DOI：[10.48550/arxiv.2610.04378](https://doi.org/10.48550/arxiv.2610.04378)。官方 arXiv abstract 的另一次打开返回访问不可用，未把它记作成功阅读全文，也没有转路绕过。本文没有采用该论文的数值指标作为本项目效果证明。

本轮工程推断是：输出 schema 能改善结构与互操作性，但不能证明内容可信、授予操作权限或替代行为验收。因此读取保存记录的 MCP 保持只读、最小摘要与明确的未验证标志。真正的功能结果仍需源代码、具体反例及对应环境的运行证据支持。

## 7. 首次集成验收记录（后续闭环见第 9 节）

### 已完成的本地与 Windows 源码验收

Linux 当前工作区实际执行 `python -m unittest discover -s tests -v`，**177 项通过、0 skip、0 failures/errors**，耗时 2.774 秒。它覆盖本地解释器可运行的 core 与合成反例，不是 HMC、实际 Linux PTY 或 GUI 结果。

Windows 验证快照于 **2026-11-26 16:19 JST** 执行一次有界 `smoke_windows.py`。runner 报告耗时 **24.179 秒**、exit 0，九个顶层 case 全部 `passed`；core 明确为 **177 项运行，166 通过，11 skip，0 failures/errors**。原配置字节前后相同。运行来自隔离的 a5 source tree，没有把旧 installed distribution 当作当前源码版本。

| 顶层 case | 本次状态 | 范围 |
|---|---|---|
| core | passed | 177 run／166 pass／11 skip；跳过不计为通过 |
| doctor | passed | 配置组件的发现与诊断，不等于各组件所有功能 |
| liveness | passed | 自有合成 pipe fixture；不代表任意进程或 TUI |
| terminal | passed | 自有 REPL／TUI 与独立见证 |
| mcp | passed | 上文首次两个真实 stdio 会话；后续 smoke 判定修复仍需定点复验 |
| browser_offline | passed | 离线 JSON 证据一致性，没有实时浏览器执行 |
| omp_preview | passed | 既有 wrapper 的 dry-run，没有真实模型回答 |
| desktop | passed | 自有 Windows fixture 与正常清理；不是任意应用或 UAC |
| observation | passed | 自有窗口有限采样与正常退出；不证明视频或任意像素语义 |

desktop 清理核对身份后正常关闭，进程 exit 0、witness closed、verified，未强制终止。observation 的窗口先正常关闭，后续 HWND 查询报告不存在；runner 按 held process 与 closed witness 确认 exit 0，cleanup verified，同样未强制终止。报告仍保留该观察顺序，没有隐藏 `Target HWND no longer exists` 来制造一致。

这次通过不会覆盖 a4 的焦点失败，也不证明改进后的 smoke 或尚未冻结的最终发行字节已经重新运行。真实 browser 与真实模型调用均不在这九项的全部通过含义中。

### 首次记录时的交付状态（历史）

以下表格是本报告写入时的状态。主线应以实际回执补充后续版本、命令、退出码、计数与指纹；没有结果的项目保持待验证，不填预计数字。

| 验收或交付 | 当前状态 | 尚需的实际证据 |
|---|---|---|
| a5 完整本地 core suite | 初次 177/177，0 skip，通过 | MCP smoke 修复涉及新增回归时补充其必要检查 |
| a5 Windows SDK 2.3.0 stdio | 初次两会话各 30 项通过；review 后修复与定点复验待完成 | 类型敏感等值和全部成功结果双通道检查的最终回执 |
| a5 Windows 有界集成 suite | 单次 9/9 passed、exit 0；core 166 pass／11 skip | 保留该 source snapshot，不拼接不同 run 或扩展为已安装包 |
| a5 Windows wheel 安装与隔离导入 | 待主线运行 | wheel/hash、模块指纹、实际安装版本、配置与依赖保留 |
| 本轮 MCP 独立 review | 已发现 smoke 判定 P2，修复中 | 最终 findings 报告、裁决与受影响的定点复验 |
| UI IME 修复 | 已修复，独立定点 3/3 通过 | 真输入法／浏览器仍未验收，不增加无依据的通过范围 |
| a5 Skill 更新与验收 | 待主线完成 | 对应实际接口、安装说明与同步结果 |
| GitHub public repository | 已授权，尚未记录创建成功 | 实际仓库 URL、可见性、提交 SHA |
| GitHub CI | workflows 已准备并固定 Actions revision，尚未记录运行成功 | 实际 run URL、job 结果及明确 skips |
| Release 与校验文件 | 待本版冻结、构建与发布 | tag、资产、SHA-256 与源码 manifest 对应关系 |
| GitHub Pages | workflow 已准备，尚未记录部署成功 | 实际 deployment 结果与公开 URL |

a4 的 Linux 全套 **158/158**、Windows 最终 core **158 项运行／150 通过／8 skip**、顶层 suite **8/9，exit 1** 均保留为 a4 历史。最终 run 的 `focus_unverified / outcome_unknown` 阻止了后续 click；另一个 run 的成功点击不能覆盖这次失败。已安装 a4 包的核对也不自动升级成 a5 已安装。

## 8. 交付与证据使用原则

公开源码只包含可分发的程序、夹具、Skill、静态网站与去标识说明。运行配置、state、原始终端／UI 内容、设备与账户标识、凭据及私有证据不进入 GitHub 或公开发行包。原始 OMP、RDC 与验收回执由操作者保留，公开文档只提取必要的失败类别和范围。

发布时应从同一冻结字节快照生成源码归档、manifest、校验和与独立预览；已安装包另做隔离导入核对。每条最终结论都绑定版本与范围：schema 检查不等于 wire 通过，源码通过不等于安装包通过，静态网页检查不等于浏览器通过，部署成功也不等于全部功能通过。

本版当前没有实现自动处理 UAC secure desktop、被拒 origin 的替代操控、任意现有进程接管、Linux/macOS 全 GUI 或云端 ChatGPT 自动连接本地 stdio。相应限制按 [能力表](CAPABILITIES.zh-CN.md) 保留；新增能力必须有具体接口、执行证据与独立结果才能写成已完成。

## 9. 后续 review 闭环与发布前定点复验

本节追加后续实际结果，保留前面的首次运行记录，不将不同快照拼成同一 run。

- **MCP smoke P2 已关闭。** 主线加入严格 JSON 类型比较与单一文本通道检查；独立原 12 场景复验符合预期（两个控制通过、十个错误变异被拒绝）。生产 `mcp_server.py` 的摘要保持不变。
- **修后 Windows MCP：72/72。** 两个真实 SDK 2.3.0 stdio 会话各 36 项通过，modern/legacy 协议分别为 `2026-07-28` / `2025-11-25`，记录字节未变。仍是 source tree，运行时 distribution 为 a4，不计作 a5 安装包验收。
- **修后 Linux core：181/181，0 skip。** 命令 `python -m unittest discover -s tests -v`，2.674 秒，0 failure/error。
- **修后 Windows core：181 run／170 pass／11 skip。** 同一命令在隔离修后源码执行，5.672 秒，0 failure/error。没有重新运行无关的整个九项 GUI/终端 suite。
- **已安装 Skill 已更新。** canonical 与随包七文件一致；新增按需 a5 MCP 查询说明，a4 桌面最低版本保持不变。quick validation、精确 diff 与全新读者三个场景通过，私有 git 同步后远端字节核对一致。
- **公开仓库已创建。** [dwgx/RDC-Operator-Kit](https://github.com/dwgx/RDC-Operator-Kit) 已由 GitHub 回读确认 public、默认分支 main。代码 push、CI、Release 与 Pages 的结果按后续真实回执追加。

独立评审公开副本：[MCP](research-wave5/REVIEW-MCP.zh-CN.md)、[Linux 安装与诊断](research-wave5/REVIEW-LINUX.zh-CN.md)、[UI 与 IME](research-wave5/REVIEW-UI.zh-CN.md)。研究阅读范围见 [MCP 研究](research-wave5/RESEARCH-MCP.zh-CN.md)。

### Windows 安装目录的最后一项修复

由 Linux `bin` 反例追查同类具体风险，确认 Windows 安装器此前没有检查 `.venv\Scripts` 目录 reparse。补丁仅将该目录纳入原 guard；真实 Windows 空目录 junction fixture **1/1 通过，0.740 秒，无 skip**，没有 pip 或外部解释器执行。详见 [Windows 安装器 review](research-wave5/REVIEW-WINDOWS-INSTALLER.zh-CN.md)。

新增 Windows 专用测试后，本地 Linux 最终全套为 **182 run／181 pass／1 skip，2.719 秒**；这一项 skip 明确要求 Windows。Windows 的已执行记录仍为先前 **181 run／170 pass／11 skip** 加单独的 junction 回归，不合并成一次全套报告。GitHub CI 的实际矩阵结果随后另列。
