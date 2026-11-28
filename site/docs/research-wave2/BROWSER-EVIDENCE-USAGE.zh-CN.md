# Browser Evidence v0：离线验收与本地网页 fixture

日期：2026-11-26。此切片在 `0.1.0a1` 基础上新增独立模块和脚本，不改动原有 Kit CLI、浏览器驱动、dispatcher 或安装器。设计依据见 [第二轮浏览器研究](BROWSER-MCP.zh-CN.md)。

**它检查调用者提供的证据是否自洽，不会操作浏览器，也不认证证据来源。** 正例状态特意命名为 `verified_fixture`：只说明声明为合成测试的计数器条件、记录身份、调用顺序和图像字节符合本契约。一个完全捏造但内部一致的 bundle 也能通过；因此不能把退出 0 当作真实网页完成证明、用户授权或宿主策略许可。

## 文件与运行

| 文件 | 用途 |
|---|---|
| [`rdc_operator/browser_evidence.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/rdc_operator/browser_evidence.py) | 标准库纯函数 `validate_bundle()` 和计数器请求摘要 |
| [`scripts/verify_browser_evidence.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/scripts/verify_browser_evidence.py) | 只读一个 JSON 文件或 stdin，输出 JSON 判定 |
| [`examples/browser-evidence/`](https://github.com/dwgx/RDC-Operator-Kit/tree/v0.1.0a6/examples/browser-evidence) | 6 个明确标记为 synthetic 的正反例 |
| [`site/lab.html`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/site/lab.html) | 无账号、无外部资源的静态网页 fixture |
| [`tests/test_browser_evidence.py`](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/tests/test_browser_evidence.py) | 离线契约及 CLI 验收 |

Windows，在项目目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\verify_browser_evidence.py examples\browser-evidence\counter-success.json
.\.venv\Scripts\python.exe scripts\verify_browser_evidence.py examples\browser-evidence\lost-response.json
```

Linux：

```bash
.venv/bin/python scripts/verify_browser_evidence.py examples/browser-evidence/counter-success.json
.venv/bin/python scripts/verify_browser_evidence.py examples/browser-evidence/lost-response.json
```

系统 Python 3.10+ 也可直接运行，不需要另装依赖。脚本不会连接浏览器、读取 profile、启动服务、执行 bundle 中的命令或跟随其中的文件路径。它不输出证据文件，只把判定打印到 stdout；不会自动再试、再点击或重新调度。

## 判定与退出码

| `status` | 退出码 | `next_action` | 含义 |
|---|---:|---|---|
| `verified_fixture` | 0 | `stop` | 合成计数器条件和输入记录内部一致；本次离线分析完成 |
| `unverified` | 1 | `reobserve` 或 `reconcile` | 身份、顺序、字节、见证不足或不一致；缺少可信真实采集者的 imported 记录也在此类 |
| `outcome_unknown` | 1 | `reconcile` | 响应丢失、dispatch/ack 未知或互相矛盾；不能换 ID 偷重放 |
| `blocked` | 1 | `stop` | 调用者单独提供了宿主拒绝或人工停止事实 |
| `invalid` | 2 | `stop` | JSON、字段集合、类型、大小或格式不符合 v0 |

所有结果固定包含 `authorization_verified=false`、`authenticity_verified=false`、`live_execution_verified=false`、`automatic_replay_permitted=false`。`next_action` 是需要人工/上层处理的分类，脚本不会执行它；`reobserve` 也没有为另一个通道授予访问权限。

既有拒绝或停止应由调用者作为独立上下文传入：

```powershell
.\.venv\Scripts\python.exe scripts\verify_browser_evidence.py evidence.json --host-refused
.\.venv\Scripts\python.exe scripts\verify_browser_evidence.py evidence.json --operator-stopped
```

这两个参数只能收紧结果：存在时立即输出 `blocked/stop`，连指定文件都不需要读取。未传入意味着“此脚本没有收到停止上下文”，绝不意味着获准。bundle 不接受 `host_allowed` 等授权字段；网页、另一个模型或导入回执均不能解除宿主拒绝。此脚本没有内建跨会话策略数据库，调用者仍必须保留实际宿主决定。

## 最小数据契约

完整可运行范例是 [counter-success.json](https://github.com/dwgx/RDC-Operator-Kit/blob/v0.1.0a6/examples/browser-evidence/counter-success.json)。v0 只处理“从已观察计数值增加一次”的合成业务条件，不提供任意断言表达式或通用代码执行。

| 对象 | 关键字段与核对 |
|---|---|
| `executor` | name、version、session_id；仅记录调用者声明，未核验二进制或真实 session |
| `page` | browser_id、context_id、tab_id、target_id、document_epoch、fixture_nonce、origin |
| `request` | request_id、operation=`increment_once`、token、before_count、expected_count、digest |
| `observation` | 原页面身份、observation_id、sequence、observed_at、counter |
| `screenshot` | 相同页面身份与 observation_id、递增 sequence、调用起止、可空 captured_at、PNG base64、SHA-256、宽高 |
| `action` | 同一 request_id/digest/页面身份/observation_id；dispatched、acknowledged、response 分开记录 |
| `witness` | 动作之后的页面身份、sequence、时间、来源、counter、request_id、token；可以为 null，此时不能通过 |

计数器 `expected_count` 必须是 `before_count + 1`。request digest 是五个意图字段按 key 排序、无额外空格、UTF-8 JSON 的 SHA-256；`request_digest()` 可生成它。摘要只是校验和，不是签名。

所有 observation / screenshot / action / witness 必须与根页面身份逐字段相同。相同 tab_id 但不同 target、context、document epoch 或 fixture nonce 不能通过。Reset 或 reload 之后，之前 element/observation 的身份应失效。序号要求 `observation < screenshot < action < witness`；带时区的时间也要保持相应顺序。离线文件可以描述历史事件，脚本不把它称为“现在的浏览器”。

业务见证须为 `fixture_dom_readback`，counter、request_id、token 同时匹配。命令 echo 或 Agent 的 success 宣言不满足该条件。`response=lost` 时，即使业务见证的计数已经变化，结果仍为 `outcome_unknown`，并保留 `business_condition_consistent=true` 这个较弱的输入事实，让上层核对而不是再次点击。

## 图像证据的明确限制

6 个范例内嵌的是一张 **74 字节、2×2 彩块的合成 PNG**，不是本轮浏览器截图。脚本校验 base64、SHA-256、PNG signature / IHDR 和尺寸，`full_image_decode_verified=false`；没有逐像素解析、OCR 或图文语义一致性判断。

`captured_at=null` 时，`pixel_freshness=unproven`。若调用者提供一个落在观察区间内的像素时间，也只得到 `source_time_claimed_but_unproven`，因为时间来源仍未认证。调用起止、文件创建时间、哈希变化和真实 compositor 帧时间不是同一个事实。相同 document epoch 也不能证明 DOM 与截图是原子快照。

JSON 输入上限为 1 MiB；重复 key、NaN / Infinity、布尔值冒充计数/尺寸、未知字段和无时区时间被拒绝。不会根据任何 bundle 内容去读取另一个路径。

## 静态网页 fixture

`site/lab.html` 可由已有获准的静态站点预览入口打开。本切片没有启动服务器，也没有打开浏览器。它使用本地 DOM、随机 nonce 和短计时器，CSP 禁止网络 API 与外部资源；不使用 cookies、localStorage 或账号。

页面提供这些可观察的反例：

1. **Increment once**：ACK 日志随后产生一次 counter 变化，并更新 `last_completed` 的 request_id/token/time。
2. **Increment after 1.2 seconds**：先出现 ACK 和 pending，约 1.2 秒后才更新业务见证；在此之前不能判断完成。
3. **Echo ACK only**：只更新日志与提示，不改变 counter 或 `last_completed`。
4. **Reset epoch**：取消此页尚未完成的延迟动作，计数归零并生成新 epoch；不能继续用旧观察定位。
5. **Reload document**：生成新页面 nonce 与 epoch，旧页面的记录不能与它拼接。
6. **New request fields**：只更新输入中的 ID/token，不代表任何业务完成。

页面故意**不按 Request ID 去重**：重复点击确实会再次增加计数。这使执行器的 durable intent / receipt 重放测试有真实反例。不要为凑正例把页面改成自己吞掉重复输入。

右侧 `#witness` 是页面业务状态，`#activity-log` 是事件日志。采集者必须从实际浏览器取得 browser/context/tab/target 身份，并标注采集时间/序号；页面不能知道这些内部标识，也不会替采集者编造。网页 witness 仍是页面提供的数据，不能把它当作已认证的外部业务系统结果。

## 已执行验证

2026-11-26，Linux 6.18.57 / Python 3.12.14：

```bash
python -m unittest discover -s tests -p test_browser_evidence.py -v
```

**10 项测试通过，0.311 秒，0 skips。** 覆盖合成正例、ACK/echo/Agent 声明不等于业务效果、响应丢失仍未知、旧截图与 tab 复用、时间/序号回退、字节/尺寸/请求篡改、外部 stop 优先、非法类型、CLI 退出码与无输出文件。其中 JavaScript 检查仅通过 `node --check` 验证语法，没有执行页面交互。

没有执行真实浏览器、OMP Relay、Playwright、网络请求或 Windows GUI。没有运行整个旧测试套件。真正的浏览器 smoke 应由主执行者另记录入口、版本、页面身份、单次动作、随后读取的业务见证及释放结果；离线通过不能替代该记录。
