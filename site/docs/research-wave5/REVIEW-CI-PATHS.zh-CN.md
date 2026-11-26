# Wave 5 Windows CI 路径修复：独立有限审阅

审阅时间：2026-11-26 17:07 JST（08:07 UTC）。

## 结论

**未发现本次差异中可行动的 P1／P2。** Standards 与需求范围两项均无阻断发现。本结论限于下面列出的 4 个文件及所述路径／清理行为，不代表全项目安全证明，也没有把 Windows 测试绿灯当作源码审阅结论。

## 精确基线与冻结范围

基线为 `<review-workspace>/wave5-prepublish/RDC-Operator-Kit-0.1.0a5.zip`，不是工作目录的旧 git a4 基线。ZIP SHA-256：

`6dd0d3bcdde796f6d50056f307def2a6ecf6f240764aba37af803bd6bf736b36`

从 ZIP 中逐文件比较现有字节，确认仅以下 4 个源文件改变。ZIP 的生成文件 `SOURCE-MANIFEST.json` 没有工作树对应项，未将它算作源文件删除。

| 文件 | 当前 SHA-256 |
|---|---|
| `rdc_operator/mcp_server.py` | `5e74935f63012c24b7ff6ce5ef65a2941154e376b9343a2f4a6497e379240cbe` |
| `tests/test_mcp_contract.py` | `b773f8f956677a1d25c37eb8926c55306da595cb993070ed504fd656c09a366c` |
| `tests/test_frames.py` | `11629081f2ea3947502e655daa7a97b4936df04975fcedbb642fb431a683c21c` |
| `tests/test_windows_smoke_runner.py` | `90a91a03adf6a0229c27ec62200d4c09953be3373a7808e94a2908c937b70d24` |

读取了实际 `test_mcp_contract.py`，包含提供的 `ci-fix.diff` 之后新增的 `finally` owned-fd 关闭循环；未仅依据旧 diff 判断清理完整性。

## 具体审查结果

### 1. 长路径兼容没有移除 HANDLE 路径校验

`_long_windows_path` 通过 `GetLongPathNameW` 展开短名称；Python 调用链没有使用 `Path.resolve()`／`realpath()` 将指定路径直接采纳为重定向目标。期望名称在 `os.open` **之前**固定，打开后仍通过 `GetFinalPathNameByHandleW` 获取该 HANDLE 的实际路径并比较，且比较后保留二次 `_unlinked` 检查。没有把“当前路径已经恢复为普通目录”当成已打开 HANDLE 安全的证明。

两个 WinAPI 输出使用同一 `_normalized_windows_path`，保留原有的扩展 DOS／UNC 前缀规范化与 `normcase`／`normpath` 规则。新增缓冲区为 32768 个宽字符；返回 0 或所需长度不小于容量时不采用缓冲内容。0 返回时，错误 2／3 映射为 `FileNotFoundError`，其他错误保持 `unsafe_state`，没有遇错继续读取的分支。

这里的原生 API 语义并非由 Linux stub 证明；本审阅检查的是源码顺序、拒绝条件与新增 Windows 反例设计。主控另有本次 Windows 实机证据，未将其计入本审阅的执行数量。

### 2. missing-file 语义与句柄生命周期

长名称查询发生在 `os.open` 之前，查询失败时尚未取得文件 fd。文件／父目录不存在时仍通过既有 `_read_saved_record` 转为内部类型对应的 `receipt_not_found` 或 `intent_not_found`，status 的缺失记录处理没有被改为虚构成功记录。访问拒绝和无法验证路径不会被当成普通缺失。

取得 fd 后，最终路径查询、路径不一致、二次链接检查乃至 `BaseException` 的异常分支均由同一 `except BaseException` 关闭该 fd；成功路径将 fd 交给既有读取上下文。新增 WinAPI 查询只使用 Python 管理的 Unicode buffer，没有新增需要显式关闭的 Windows HANDLE。

### 3. 两条 Windows regression 提供了具体反例

- **8.3 用例**取得真实 `GetShortPathNameW` 结果；不存在不同别名时明确 skip。传给 `ReadOnlyOperator` 的仍是短路径，而构造器仅 `abspath`，不会提前 `resolve` 掉需要覆盖的情况。断言覆盖 receipt 内容、intent／receipt 配对状态、原记录字节不变及 missing ID 的 `no_records_observed`。
- **瞬时 junction 用例**在第一次真实 `_unlinked` 通过后把请求目录替换为指向自有外部 fixture 的 junction。打开外部文件后，在把 fd 交回生产调用方前恢复普通目录。它要求 `unsafe_state` 且消息来自 `outside the fixed path`，同时要求 `fdopen` 从未调用；解析失败或其他拒绝不能冒充这个路径保护通过。生产拒绝关闭 fd 另通过 `os.fstat` 必须失败验证。
- **失败清理**：实际 `finally` 遍历已登记的 fd，覆盖打开成功但测试钩子恢复目录失败、fd 尚未返回生产方的情况。所有目录、外部 sentinel、parked 目录、probe junction 均在该测试自己的 `TemporaryDirectory` 中；使用 `rmdir` 移除 junction 后恢复原目录，没有递归删除 junction 目标的显式代码。

### 4. 两个测试期望的 resolve 没有削弱生产断言

`tests/test_frames.py` 仅把 fixture 根目录规范化，使模拟 WinApp 报告匹配生产适配器传出的规范化 `--output` 路径。错误输出路径、目标身份、尺寸、复合截图、目标替换及 replay 等断言保留；生产 `verify_capture` 的路径相等检查未改。

`tests/test_windows_smoke_runner.py` 仅将 `child_summary` 的预期值改为 `report.resolve(strict=True)`，与未修改的 `child_report` 返回值一致。失败状态、非零退出码、子报告失败状态以及报告可用性断言均保留。

## 独立有限核验

执行了 **19／19 通过** 的本地 synthetic 分支检查，原始结构化结果为：

`<review-workspace>/wave5-evidence/ci-path-independent-synthetic.json`

覆盖 3 个路径规范化样例、7 个长名称查询成功／错误／缓冲边界场景、7 个 open 前后顺序与关闭场景，以及 2 个 missing-record 错误映射。使用 Linux 上 stubbed Windows API／fd，不访问真实 Windows、RDC、浏览器、OMP、HMC 或网络，不证明 WinAPI 在实际文件系统上的行为。

另有独立子审仅阅读新增测试的反例构造、自有清理范围、实际 `finally` 以及另外两个测试改动，亦未发现 P1／P2。主审亲自核对关键源码与字节差异；未以子审一致意见代替证据。

未运行完整套件，未修改生产代码或测试，未执行发布。主控报告的 Windows 全套及 MCP 实机会话未在本报告中重新计数、拼接或表述为本代理独立执行。

## 主线实机与 GitHub 闭环补记

以下由主线根据独立运行回执补充，不属于上述 reviewer 的 19 个合成检查。

- Windows 11 / Python 3.14.7：修后源码 core **184 run／173 pass／11 skip**，7.673 秒，0 failure/error。两个新增 Windows 回归都实际执行通过。独立 SDK 2.3.0 的 modern／legacy 会话各 36 checks 通过，保存记录不变。
- 本地 Linux / Python 3.12.14：**184 run／181 pass／3 Windows-only skip**，2.677 秒，0 failure/error。不是 HMC。
- 原始公开提交 `5952a45f03549de17cdc3d92ff6d7a1f91b3e0ad` 的 [首次 CI 失败](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45777836079) 保留。
- 修复提交 `a880144d07d8599c6e5232a34bcef1e1cac54bc1` 的 [后续 CI](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45780615916) 六 jobs 全部 success。四个 core jobs 各运行 184 项：Windows Python 3.10／3.13 各 177 pass／7 skip；Ubuntu Python 3.10／3.13 各 179 pass／5 skip。CI 不安装可选 Pydantic，因此 skip 与本机不同。
- CI 的 Windows／Ubuntu MCP jobs 都记录 modern `2026-07-28`、legacy `2025-11-25` passed 与记录未变；CI 日志没有逐项输出 72 checks，不将本机数字移植为线上检查计数。

这些检查证明此具体路径兼容修复及所列流程，不能解释为 Windows UAC、任意网页或所有桌面程序都已获得控制许可。

实现参考：[Microsoft GetLongPathNameW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getlongpathnamew)、[GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)。
