# 手动重登后的恢复：官方依据与工程取舍

日期：2026-11-28（UTC）。本页记录公开官方资料的阅读结果与本项目推断，未调用
RDC 或 Browser，也不证明任何目标机器已重新登录、解除配额或安装 a6。
恢复接口以[规格](../RESUME-SPEC.zh-CN.md)与[源码](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/recovery.py)为准；
操作步骤见 [Agent 指南](../AGENT-GUIDE.zh-CN.md)。

## 上游事实及适用范围

| 来源 | 阅读所得事实 | 对本项目的限制 |
|---|---|---|
| [RDC 设备离线/账户错配 Help](https://desktopcommander.app/help/troubleshooting/remote-cant-find-computer) | 设备进程未运行与 AI connector/设备处于不同 RDC 账户是不同故障；删除并重配设备通常不是首选排障 | 不能从同名设备或在线标志推导原目标/任务仍有效 |
| [多个 AI 账户 Help](https://desktopcommander.app/help/account-billing/multiple-ai-accounts) | AI 登录邮箱可与 RDC 邮箱不同；多个已授权客户端共享同一 RDC 账户的设备、usage 与 OS 用户访问能力；没有逐助手权限层 | 不按 ChatGPT 邮箱猜 RDC 身份，不假设多 Agent 具有隔离的桌面/进程访问 |
| [Pro 后仍显示额度限制 Help](https://desktopcommander.app/help/troubleshooting/usage-limit-after-upgrading) | 真正用尽 Free-plan 限额时停止重试/重连是正确处理；已付 Pro 却连接错误 RDC 账户属于另一种原因 | 账号错配的人工修复不构成自动账户轮换或绕开配额的授权 |
| [MCP Tools 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) | 工具列表可随时间与请求授权变化，也可以为空 | 新会话应发现当前工具/schema；旧工具名、annotation 或 schema 不证明当前权限与业务授权 |
| [Playwright Locators](https://playwright.dev/docs/locators) | 动作执行时重新定位当前 DOM 元素 | 可借鉴新鲜目标原则，不能推导宿主提供任意 Playwright API |
| [Playwright Navigations](https://playwright.dev/docs/navigations) | `load` 之后页面仍可变化；hydration 尚未绑定事件时，enabled 控件被点击也可能没有效果 | fresh locator、操作 ACK 与业务完成必须分开验证 |
| [RDC 数据说明](https://desktopcommander.app/help/security-privacy/data-privacy) | Remote 参数与结果经 relay；读取内容进入 AI provider 上下文；本机还保存工具日志 | 短期远端保留不等于交接自动脱敏；读取与导出都应按任务缩小范围 |

## 两个需要保留的版本差异

### RDC `--logout`：搜索缓存不能替代当前正文或安装版

搜索索引摘要仍把 logout 描述为只删除本地 credentials；本轮实际打开的
[官方 `main` Remote Device README](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/src/remote-device/README.md)
已改为服务端撤销设备与 MQTT certificates 后清理本地文件，并带有相应 backend
confirmation 的发布前条件。同次打开的
[`main/package.json`](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/package.json)
版本为 `0.3.5-alpha.0`。正文仍说明正常重启复用已保存会话，并反对将 revoke/re-pair
当作在线且普通调用正常时的通用排障。

这是阅读时浮动分支与缓存的差异，不证明用户安装版具有哪一种行为。因此 Skill 不提供
自动 logout/revoke/reset 命令，账户/配对变更由用户按其当前版本与宿主流程处理。
本项目没有从 `main` 文档推导线上服务已发布或本地已升级。

### MCP：不能把旧会话恢复写成跨版本规则

| 规范 | 读取到的语义 |
|---|---|
| [2025-11-25 Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) | 可选 `MCP-Session-Id`；失效 session 的 404 对应重新 initialize；可选 `Last-Event-ID` 流恢复；断连本身不表示取消 |
| [2026-07-28 Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) | 移除协议级 sessions 与 GET stream endpoint；不支持 `Last-Event-ID` 恢复；每请求携带 metadata；关闭请求 SSE stream 是取消信号 |
| [2026-07-28 Cancellation](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/cancellation) | 取消与完成存在竞态，已完成或不能取消的请求不保证停止 |
| [2026-07-28 Versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning) | 明确区分 modern、legacy 与 dual-era，按实际支持版本兼容 |

本次没有与 RDC 或任何宿主协商协议，不能确定其线上版本。Kit 的任务恢复由保存的
请求与独立结果证据驱动，transport 恢复交给当前宿主/SDK。流重投递、重新 initialize
或发出取消都不能单独证明业务副作用从未发生或已回滚；这项结论是工程推断，不是
上游提供了 exactly-once 保证。

## 本项目的工程取舍

先将任务范围、原 state、request IDs、route observation、typed handles 与停止原因
保存为检查点。手动重登后用新的上下文比较，保留原请求效果的不确定性。即使新旧
link/device IDs 相同，显式 `user_reconnected` 也使保存的 route generation 增加，
避免把旧句柄当成新会话观察。marker 只绑定逻辑 state；机器身份仍需调用者独立核对。

恢复计划只读，不补建 state，不执行 adapter，不建立第二个 broker，也不授予执行
许可。它在读取请求前后复查 marker/checkpoint，以发现并发变化，但继续声明采样非原子。
原 request digest 混合了请求与 config，因此计划不能仅凭 checkpoint 的 config match
声称所有历史请求的配置已经验证；保留 `request_config_binding_verified:false`。

Browser 路由按当前任务与宿主指导选择。明确页面交互/视觉验收时主动使用许可能力；
纯语义操作先查 connector/API/CLI。导航、人工接管或连接恢复后重新观察，再核对动作
结果。策略/审批拒绝保留其目标范围，不能用另一个工具绕过。a5 缺少恢复接口时继续
手工 reconciliation，不把 Skill 文本当作升级或重新登录动作。

## 阅读范围

上述官方 Help 已打开主体；Remote README 阅读登录、会话、logout 与排障段，
package.json 阅读版本与 engines；MCP 阅读工具可用性、transport/session、取消与版本
兼容部分；Playwright 阅读定位、load/navigation 与 hydration 部分。没有宣称审计完整
上游仓库或所有文档，未采用社区 issue、非官方镜像或旧搜索摘要作实现依据。
当前宿主 Browser skill 的具体方法名与登录交接规则按需读取，不复制成固定通用 API。
