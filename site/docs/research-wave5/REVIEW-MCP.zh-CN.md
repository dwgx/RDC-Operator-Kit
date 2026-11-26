> 公开去标识副本。原始评审结论与失败记录保留；私有工作区路径已替换为占位符。

# Wave 05 MCP 独立只读审查

## 结论

在指定四个文件相对 a4 `d9ab1b38fff68e77c88841c050b8c038f52dcdb5` 的变更中，初次确认 **1 项 P2：smoke 的成功判定能漏过 JSON 类型变化和状态文本通道的私有内容**。主线已修复；原独立反例原样复验后 **P2 已关闭，指定范围没有未解决的 P1/P2**。下文保留修复前反例和修复后证据。这项 finding 针对验收机制；当前生产 `as_result()` 从同一个 payload 生成文本与结构化内容，本次未发现其实际泄露或改变 receipt 类型。

生产读取/输出模型未发现新的 P1/P2：真实 Pydantic 模型严格拒绝 false/0 与 1/true 混淆；状态摘要在读取变化时降为 `inconclusive`，不会将保存状态解释为 live 进度、重试许可或业务成功。

## 范围与证据限制

- 审阅：`rdc_operator/mcp_server.py`、`tests/test_mcp_contract.py`、`scripts/smoke_mcp.py`、`docs/MCP.zh-CN.md`；并查阅原记录生成位置以核对 intent/receipt 字段。
- 环境：Linux 6.18.57 x86_64 / glibc 2.41，Python 3.12.14，Pydantic 2.13.4；当前全局 MCP 1.29.0，不符合生产入口要求的 2.3.0。
- 本次只使用隔离临时文件、真实 Pydantic 模型，以及合成的 SDK 注册器/客户端/transport；没有运行远端、网络、Windows、HMC、浏览器、OMP 或发布动作，没有修改实现。
- 没有把实现者已有的 31 项契约测试重跑后计为独立验证。以下是另外构造的变异和故障场景；合成 transport 的通过不等于协议或进程通过。
- 主线另行完成 Windows SDK 2.3.0 wire gate。已只读核对其 summary：modern/legacy 各 30 项均 true、总状态 passed、保存记录未变，且有错误成功输出被 SDK 拒绝的检查。该报告明确为 source tree，`installed_package_validation: false`。这 60 项是主线执行证据，不是本审查的独立测试数。

## 已关闭 P2 — smoke 可以在结果内容不满足契约时报告 passed

**位置：** 审查时 `scripts/smoke_mcp.py` 的 `structured-output-keeps-json-text`、`exact-saved-receipt` 和状态摘要检查（原第 314–319、341–352 行）。

**原因：**

1. 文本与结构化结果、receipt 与 fixture 使用 Python 字典 `==`。该比较认为 `False == 0`、`1 == True`，因此无法证明 JSON 类型未改变。
2. 跨文本/结构化通道的一致性检查仅用于 capabilities；状态工具的脱敏检查只查看 `structured_content`。状态的 JSON 文本可以包含额外 intent/private 内容而不触发已有检查。

**独立复现：** 原样调用实际 `one_session()`，替换 SDK/transport 为本地合成对象，并从真实 `ReadOnlyOperator` 获取基本结果；只改变返回内容，不执行任何子进程。下列结果在 modern 和 legacy 两个分支完全相同：

| 场景 | 预期判定 | 修复前实际判定 | 含义 |
|---|---|---|---|
| 正常合成响应 | passed | passed，29 项通过 | 控制场景可达正常完成 |
| 注入 `snapshot_atomic: 0` 且不进行输出校验 | failed | failed，具名错误成功输出检查失败 | 既有负例确实能发现缺失校验 |
| 状态结构化 `actions_exposed: 0` | failed | failed，具名 false 标志检查失败 | 既有 `is False` 检查正确 |
| receipt 原本 `semantic_verified: false`，返回改为数字 `0` | failed | **passed，29 项通过** | `exact-saved-receipt` 不够精确 |
| capabilities JSON 文本标志为 `0`，结构化标志仍为 `false` | failed | **passed，29 项通过** | 文本/结构化一致性出现假阳性 |
| 状态文本追加含哨兵的 `intent`，结构化结果保持脱敏 | failed | **passed，29 项通过** | 状态文本的隐私回归未被发现 |

上述是 6 类场景 × 2 个协商分支的 **12 个合成 verdict 场景**。其中 6 个场景暴露假阳性，不能称为“12 项通过”。这里的 29 项只是非 Windows 分支执行的内部 check 数，不能与真实 Windows 30 项混为一谈。

**规范轴：** 测试应验证对外可见的失败语义；不得把 Python 等值当作 JSON 类型保留，也不能用一个通道的脱敏代表客户端可读取的全部返回。

**需求轴：** 文档机器可读输出契约与 smoke 验收说明承诺原 receipt 保留、JSON 文本/结构化内容一致、状态摘要不透露 intent 原内容。现有 smoke 对这些承诺可产生错误的 passed。

**最小修正建议：** 使用 JSON 类型敏感等值 helper，并让所有成功工具响应执行文本/结构化一致性检查；receipt 与原 fixture 也使用同一等值规则。当前入口只生成一项 JSON TextContent，可要求 content 恰好一项且类型为 text，避免遗漏额外块。解析/比较失败由 helper 返回 False，再交给既有 `check(name, condition)` 追加具名失败项并走现有失败报告路径；不要用不带 check 名称的裸断言绕过记录。只需本地变异机制回归和受影响 MCP wire gate，无须重跑无关 Windows suite。

**复现文件：** 原始私有验收记录中的 `review-wave5-mcp-repro.py`。公开回归位于 `tests/test_mcp_contract.py`；以下命令仅适用于持有原验收记录的维护者：

```bash
python -B <review-workspace>/review-wave5-mcp-repro.py
```

脚本默认从相邻 `RDC-Operator-Kit` 导入实际 smoke，输出每种变异的预期/实际状态与具名失败检查。修复前 exit 1 表示有假阳性；所有控制/变异均符合预期后 exit 0。脚本不读取私有 state、不启动程序、不连接真实 SDK 会话。

### 主线修复后的独立复验

主线新增 `_same_json()` 类型严格递归比较，以及 `_matching_result_channels()`：必须是明确 `is_error=False`、唯一 TextContent、object 结构化结果；文本通过现有 `strict_json()` 拒绝重复键、非有限数和非法 JSON，然后进行类型敏感比较。capabilities、receipt 和五个正常状态查询都经过通道一致性检查；原 receipt 也与 fixture 作类型敏感比较。解析失败返回 False，由 `check()` 记录具名失败。

使用上面的独立脚本原样复跑，**exit 0，12/12 场景的 verdict 符合预期**。这表示两个正常控制 passed、10 个错误变异 failed，不表示错误变异被接受，也不等于 12 项真实 SDK 协议测试。

| 原变异 | 修复后 modern / legacy 判定 | 保留的具名失败检查 |
|---|---|---|
| 正常控制 | 两者 passed，各 35 个内部 check 通过 | 无 |
| 缺失输出校验 | 两者 failed | `sdk-rejects-injected-invalid-success-output` |
| 状态结构化标志改为数字 0 | 两者 failed | `status-summary-never-claims-live-or-atomic-verification` |
| receipt 的 false 改为数字 0 | 两者 failed | `exact-saved-receipt` |
| capabilities 文本 false 改为数字 0 | 两者 failed | `structured-output-keeps-json-text` |
| 状态文本额外包含私有 intent | 两者 failed | `status-json-text-matches-fixture-receipt` |

独立复验没有扩大测试范围，没有重跑主线的 35 项单元测试或无关 Windows suite。只读检查主线新增四个单元测试后，确认覆盖此次类型比较、capabilities 通道差异、状态额外字段/额外文本块及非法 JSON 的具体反例。生产 `mcp_server.py` 摘要未变。修复后真实 SDK 的新增通道检查仍由主线执行受影响的两会话 gate，本报告不会把修复前 60 个 wire check 当作修复后的结果。

## 已确认的正确行为

### 真实输出模型

通过独立的纯注册器 stub 捕获实际函数返回注解，使用 `get_type_hints(..., include_extras=True)` 解析，并直接调用真实 Pydantic 2 模型的 `model_validate_json()`。三种返回注解均确实含有模型，注册均设置 `structured_output=True`，模型根为关闭的 object。

三个模型合计检验 49 个类型变异输入：各 false 字段替换为 `0`、`0.0`、`true`、`"false"` 或 null，以及 schema version 替换为 `true`、`1.0` 或 `"1"`，全部被拒绝。该数字是输入变异数量，不是 49 项 SDK 测试。receipt 的不透明额外内容中，false、整数 0、浮点数 0.0 各自保持原类型。

这支持 `Annotated` 的模型确实严格，而非纯文档 schema；本地 stub 不证明 SDK 如何执行注解，后者由主线 2.3.0 wire 的错误输出拒绝证据补足。

### 状态一致性与隐私

独立场景使用真实文件读取与 JSON 解析，仅在两轮间调度变化：

- receipt 私有内容原地变更，同时模拟文件元数据指纹恒定：字节 SHA 指纹仍发现变化，返回 `inconclusive / records_changed_during_observation`，保存状态为 null，无私有内容。
- 第一轮读到 receipt，第二轮前删除该文件：返回同样的保守状态，不保留此前 completed 状态。
- 带私有哨兵的截断 JSON、重复键及 `schema_version: 1.0`：分别返回 `intent_unreadable` / `invalid_intent` 等固定错误，错误消息不反射私有内容或路径。

两轮读取仍不是跨文件原子快照，也不能保证返回后文件不变化。实现固定 `snapshot_atomic: false`，文档明确说明这项边界，未发现过度宣称。

### 新增测试与文档

源码中的新增契约测试实际调用业务路径，覆盖私有字段、两轮间创建/替换、读取中变化、孤立 receipt、digest 不符；真实 Pydantic 模型测试与 SDK 注册器 stub 的边界写明。现有 SDK 1.29.0、待重跑 2.3.0、source tree 与安装验证区别也写明。没有把过去“两工具”结果直接当作当前“三工具 + 输出模型”通过。

`git diff --check` 对四个指定文件通过。

## 修复前审查文件摘要

| 文件 | SHA-256 |
|---|---|
| `rdc_operator/mcp_server.py` | `7dfc66353870e110d7f1b5080a73f4bd4aab3c608143856644f27c28882fc8c1` |
| `tests/test_mcp_contract.py` | `5188ab020f0086ec0104a93ee4f6680d86f785c641b251ba681f74f41963ac46` |
| `scripts/smoke_mcp.py` | `4de3bc90d5b8d2d10a2a6dd9c4ae09f9b2944eec2276e123cb63f26a3fe238d7` |
| `docs/MCP.zh-CN.md` | `e6e954778cb7a62d5d9b46e999f4868e22c25d3f6fa933b74791677e7bbcc92b` |

## 修复后独立复验文件摘要

| 文件 | SHA-256 |
|---|---|
| `rdc_operator/mcp_server.py` | `7dfc66353870e110d7f1b5080a73f4bd4aab3c608143856644f27c28882fc8c1` |
| `tests/test_mcp_contract.py` | `fcecce3010b41f7ee6e8906135918b0d4caeb22a47d656230bab0fa4de1590fe` |
| `scripts/smoke_mcp.py` | `d0f05d8e994fda990bdb89984f28f9fcf6c4f891d3b2329fd3aa4f4736d1a466` |
| `docs/MCP.zh-CN.md` | `e6e954778cb7a62d5d9b46e999f4868e22c25d3f6fa933b74791677e7bbcc92b` |

本报告不含设备、账号或业务私有标识；所有测试 request ID、哨兵和记录都由隔离 fixture 人工生成。
