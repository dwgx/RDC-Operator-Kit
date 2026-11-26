# RDC Operator Kit · Wave 03

2026-11-26 / 0.1.0a3 review candidate，未公开发布。Windows 已安装运行时为 a2。上一版 95 个源文件均按 manifest 核对。

## 本轮 Windows 基线实测（0.1.0a2）

| 能力 | 结果 |
|---|---|
| 核心 unittest | 100 项运行、93 通过、7 跳过、0 失败 |
| doctor | SmartCLI 与 winapp available；OMP wrapper_found；Browser 未探测 |
| SmartCLI | 真实 REPL 与 TUI 均 PASS |
| 存活性诊断 | 9 场景 PASS；普通 pipe，不是任意 PTY |
| MCP | 独立环境的真实 stdio smoke exit 0 |
| 原生窗口 | observe、Unicode set_value、Invoke、独立文件见证、截图均通过 |
| 鼠标点击 | foreground_not_target，未通过；后续点击重放未执行 |
| 有限采样 | 3 帧、3 个不同哈希、2.157 秒；复合窗口拒绝与关闭通过 |
| OMP | wrapper DRY_RUN 成功，未调用真实模型 |
| 浏览器证据校验器 | 6 个离线场景 verdict 与预期一致 |
| OMP Relay | 本轮未重验；上轮 partial/BLOCKED 保留 |

私有证据：evidence/wave3-20261126T045246Z-cd6856、evidence/wave3-20261126T045525Z-44f035。第一轮测试误将 PATH 的 PowerShell 转发器当实体进程，身份检查拒绝，两个残留测试窗经 PID、命令行、HWND 与见证文件核对后正常关闭。第一次重试因路径字符串转义错误未启动；改实际 pwsh 绝对路径后重验。两个新夹具均正常退出。原配置未改变。点击前台条件保留，未强抢焦点。

## 代码 Review 与修复

- JSON 文件、CLI stdin、上游 JSON 解析拒绝重复 key、非有限数字与溢出浮点；文件入口有界读取，拒绝明显链接/reparse point 及非普通文件。
- schema_version 要求真实整数 1，拒绝布尔值 True。
- 发行遍历由全树 rglob 后过滤改为仅进入显式允许目录、提前剪枝私有目录，拒绝源码目录链接。保持相对 POSIX 路径排序。未宣称抵御同权限恶意目录替换或所有 TOCTOU。
- 5 个新增回归测试方法；旧版对应反例失败，新候选通过。Linux 原版 100/100，a3 候选 105/105。候选没有安装到原 Windows 环境，不能把 a2 真机证据算为 a3 全量验收。
- 网页加入按范围区分的实际验收记录；内部文档链接在单文件预览中自动展开；响应式布局补强。

## 研究来源和采用决策

Scite Premium 账号查询和元数据检索成功。OSWorld、Windows Agent Arena、Agent S2 元数据可取，但 OSWorld 与 WAA 的全文读取无正文；采用作者公开摘要，不声称阅读全文或重跑基准。

Xie et al. (2024). OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments. https://doi.org/10.48550/arXiv.2404.07972 — 明确初态与执行结果判分，启发独立文件见证。

Bonatti et al. (2024). Windows Agent Arena: Evaluating Multi-Modal OS Agents at Scale. https://doi.org/10.48550/arXiv.2409.08264 — 真实 Windows 可复现环境；不把 Linux/mock 通过等同 Windows。

Playwright: https://playwright.dev/docs/best-practices — 独立 context、用户可见断言、自有页面。Python json: https://docs.python.org/3/library/json.html — object_pairs_hook 与 parse_constant。

仍未解决：真实 Relay 完整证据采集，实时视频流，通用 terminal.close 退出语义，桌面点击前台条件，具体第三方 MCP host 接入，公开 CI/Pages。未访问已被拒绝的站点，也不以替代工具绕过。

## 网页验收补记

新版 HTML 已生成；静态 HTML ID 唯一性、内部链接与 ARIA 引用、资源存在性、JavaScript 语法检查通过。真实 Chromium smoke 打开本地文件时收到 `ERR_BLOCKED_BY_ADMINISTRATOR`，未得到完整浏览器验收结果，不计为通过。未尝试绕过；可选 smoke 脚本保留，检测到管理员拒绝即停止该轮后续导航。当前候选未同步覆盖 Windows 已安装源码，未安装 a3，未发布网页到 GitHub Pages。
