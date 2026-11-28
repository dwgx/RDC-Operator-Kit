# 第六轮：手动重连后的恢复、Agent 交接与证据复核

状态日期：2026-11-28（Asia/Tokyo）。版本：`0.1.0a6` 已发布 alpha。本文记录已执行的源码验证、独立反例及其修复；Windows／Linux 已安装包验证已完成；a6 GitHub CI、Release 与 Pages 均已有真实回执，见第 9 节。a5 的已发布资产和历史结论保留在[第五轮报告](REVIEW-WAVE5.zh-CN.md)，不会被本轮源码结果替代。

本轮从公开 `main` 提交 `54131f00c3b942797809a1b90424e845ef56fe13` 建立隔离副本，139 个基线文件逐一核对 SHA-256 相同。开发、独立审阅和运行时冻结使用的是本地提交；最终运行时检查点 `06e0e21` **不是公开发行提交或 tag**。Windows 源码测试前另核对了当时隔离快照的 149 个文件；这也不是最终 Release 文件数。

## 1. 当前结果

| 项目 | 已取得的结果 | 适用范围 |
|---|---|---|
| Linux 最终 core | 225 run／221 pass／4 skip，exit 0，3.529 秒 | Python 3.12.14；四项为 Windows 专属检查，不是 HMC 验收 |
| Windows 最终 core | 225 run／212 pass／13 skip，exit 0 | Windows 11 build 26300、Python 3.14.7；隔离源码执行，非已安装 wheel |
| Linux 恢复 smoke | 17/17 passed，exit 0 | 真实自有 Python 子进程与合成 effect；未调用 RDC、GUI、Browser 或真实终端适配器 |
| Windows 恢复 smoke | 17/17 passed，exit 0，summary 已逐项核对 | 自有源码夹具；不是真实重新登录实验 |
| 独立运行时反例 | 三个缺陷已修，修后定向 3/3 通过 | 保留 JSON `null`、NUL 路径、提交后回读错误的原失败 |
| 恢复 smoke 自身审查 | 三类判定／生命周期缺口已修；反向控制按预期失败 | 合成变异与 mock 清理控制分别记录；不是 OS 沙箱证明 |
| 打包隐私回归 | 7 个测试方法修后全通过；修前 26 个失败条目保留 | ZIP、TAR、manifest、独立 HTML 的合成私有哨兵；不是通用秘密扫描 |
| Skill 和交接 | canonical 八个资源已保存并逐文件远端回读核对；四种原生 Agent 场景推演完成 | 推演未执行真实浏览器、进程接管或账号切换；YAML 重排已核对语义一致 |
| 当前 RDC 路由 | 用户手动登录后，主执行者已重新发现并读取现有连接和设备 | 私有标识已脱敏；只证明当时路由发现成功，不授予额外工具权限 |
| a6 已安装包 | Windows 两个环境各 12 模块匹配 wheel；恢复 smoke 各 17/17；Linux 新隔离环境安装包 smoke 17/17 | 真实 site-packages 隔离导入；其他依赖与 Windows 配置未变 |
| installed CLI／现代 MCP | 两个 `rdc-kit.exe` 均返回 a6；真实 SDK 2.3.0 stdio 会话 17 checks passed | 与恢复 smoke 的 17 项分开记录；协议 `2026-07-28`，三工具、双通道、unknown 与记录未变均核对 |
| a6 CI、Release、Pages | 已完成，见第 9 节 | 六个 CI job、九项资产下载回读及 Pages build/deploy；不增加 live UI 结论 |

较早的 Linux 223 run／219 pass／4 skip 是修复后的中间检查点。新增命令行只读回归后最终变为 225 项；不能把这两个运行或定向子集相加成更多测试。各系统 skip 的数量保留原值，未执行项不计为通过。

## 2. 本轮新增的恢复机制

实现位于 [`recovery.py`](../rdc_operator/recovery.py) 与 [`cli.py`](../rdc_operator/cli.py)，完整契约见[恢复规格](RESUME-SPEC.zh-CN.md)，操作步骤见[Agent 使用与交接指南](AGENT-GUIDE.zh-CN.md)。a6 增加的是任务检查点与只读核对计划，**没有把所有 `call`、RDC 调用或其他控制工具接入一个全局执行拦截器**。Agent 仍须遵守原授权、停止原因与实际工具权限；核心原有的 intent／receipt 去重继续负责同一 state 内的请求语义。

| 机制 | 实际契约 | 保留的边界 |
|---|---|---|
| 持久检查点 | `checkpoint DOCUMENT --expected-revision N`，必须显式传原 `--state`；在原 state 锁内比较 revision、写入 revision + 1 | 第一次 N 为 0；旧 writer 冲突，不覆盖较新的检查点 |
| 原状态身份 | 检查点绑定随机 marker UUID 和规范 state 路径，冻结 scope／config 指纹；请求 ID 只可追加 | 同路径换 marker、复制到另一 state、改配置或改 scope 都不能冒充原任务；不证明物理设备身份 |
| 连接代次 | link/device identity 改变，或明确 `user_reconnected`，都会推进 route generation | 相同 ID 的手动重连仍推进代次；仅刷新观察时间不推进；旧 handle 不能重新标为新来源 |
| 停止原因 | `disconnected`／`auth_required` 仅在 fresh context、`user_reconnected`、当前 stop 为 `none` 时进入复核 | `quota`／`policy_refused`／`cancelled` 保留；新路由不消除旧停止原因 |
| 只读计划 | `resume TASK_ID --context DOCUMENT` 核对原 marker、检查点和保存请求；返回前再次检查 marker／检查点的身份、字节与 revision | 无执行、取消或重放入口；`snapshot_atomic: false`；返回后目标仍可能变化 |
| 来源与授权 | 输出保留 `route_source: caller_attested`、`physical_device_verified: false`、`request_config_binding_verified: false` | 当前 route 由调用者提供；checkpoint config 不等于历史 request 使用该 config 的证明；scope hash 不能恢复正文或证明授权 |
| Typed handles | RDC call、process、search、terminal、browser tab、desktop observation 分类型处理 | 旧 PID 需重新核对创建时间、可执行文件及归属；旧 tab、截图、selector 和调用句柄不能跨代盲用 |

`resume` 只有 `blocked` 或 `review_required`；后者的 exit 0 表示报告生成成功，不是执行许可。两者均固定 `execution_authorized: false`、`automatic_replay_allowed: false`、`actions_exposed: false`，并要求 fresh observation。没有记录、只有 intent、失败或未知效果都需要独立核对；已有 `completed`／`observed` 也不替代业务效果验收。

只读边界分两层：`assess_resume()` 本体不写 state、不调用适配器、不创建子进程或网络连接；命令行推荐 `python -B -m rdc_operator ... resume ...`，使导入模块也不生成 `.pyc`。这不承诺文件访问时间、宿主日志或调用者明确重定向的 stdout 文件完全不变，更不是系统级隔离。

## 3. 独立发现的三个运行时缺陷

测试源码见 [`test_recovery_review.py`](../tests/test_recovery_review.py)。以下是实际反例，不是仅凭审阅提出的假设。

| 缺陷 | 修前证据 | 修复与修后检查 |
|---|---|---|
| JSON `null` 被误当作不存在的检查点 | 已有 checkpoint 被写成合法 JSON `null` 后，首次 revision 0 保存未被拒绝，可能覆盖损坏记录 | 将“文件不存在”和“内容为 null”分开；返回 `invalid_checkpoint` 并保留损坏字节 |
| NUL state 路径泄漏原始异常 | checkpoint 和 resume 的两个 subtest 均抛出未归一化的 `ValueError: embedded null character in path` | 在路径入口形成结构化 `KitError`，不再返回裸 traceback |
| 原子提交后的回读失败错误地报告确定失败 | `os.replace` 已提交新 revision，随后 `_bundle` 归一化的 `KitError` 未进入原 OSError 分支，`uncertain` 仍为 false | 返回 `checkpoint_commit_unconfirmed` 且 `uncertain: true`；revision 2 留在磁盘，继续用 expected revision 1 会得到 `checkpoint_conflict` |

前两项修前为 2 个测试方法、1 failure、2 个 subtest error，修后 2/2 通过。第三项加入后，修前定向运行 3 项中 1 failure，修后 3/3 通过。提交后确认失败不允许回滚或盲写：先回读已保存 revision 与材料，再决定下一步。

独立规格审查还指出普通 `python -m` 会在 fresh source 导入时生成缓存。新增 [`test_recovery_cli_readonly.py`](../tests/test_recovery_cli_readonly.py) 从无缓存源码副本运行真实 `-B` CLI，比较源码、输入和 state 的目录结构、文件身份、mtime 与内容；正向通过。去掉 `-B` 的反向控制观察到一个缓存目录和七个 `.pyc`，并按预期失败。测试不比较 atime，也不把专门保存 stdout 的日志视作评估函数写入。

## 4. 恢复 smoke 的审查与修复

[`smoke_recovery.py`](../scripts/smoke_recovery.py) 创建自己拥有的子进程，由注入的合成 operation 写一次 effect 文件，然后在最终 receipt 之前 `os._exit(73)`。父进程确认真实 worker 身份、退出码、effect 和 intent 存在而 receipt 缺失；原 ID、原 payload、原 config、原 state 再次进入核心时不会执行第二次 effect。它不是实际网络断线、RDC 重新认证或 GUI 点击实验。

独立审查没有把 smoke 自报 passed 当作充分证据，加入了三个具体控制：

| 原缺口 | 反例与修复 |
|---|---|
| 只比较 state 文件字节，副作用标志硬编码 | 旧 smoke 在同字节重写、空目录创建、state 外写入及五次 fake adapter 调用下仍通过 12 项。修后用 Python audit 和适配器入口 guard 记录并拒绝这些尝试；吞掉异常的变异仍留下四类尝试并失败。正常最终运行覆盖六次 resume，零副作用尝试。 |
| Windows redirector 与捕获管道可能留下无界等待 | CPython Windows 分支的 mock 观察到原流程在杀 launcher 后进入 `communicate(None)`。修后选实际 base interpreter、使用文件 stdout/stderr、核对 worker 导入来源及 PID；45 秒有界监视和持有 `Popen` 的 finally 清理另有最多 5 秒等待。超时、中断、清理失败三个控制均得到预期结果。mock 不是 Windows 实测。 |
| 只核对顶层 status，遗漏请求和句柄证据 | 清空 requests、handles、原因列表的变异曾仍通过；修后检查具体 request reason、保存状态和 typed-handle 建议，空证据变异在指定 case 失败。旧 RDC call 要重新发现，旧 process 要重新识别，均不宣称 live verification。 |

修后 Linux source smoke 为 **17/17 passed**，`source_execution: true`、`installed_package_validation: false`、`real_rdc_reauthentication: false`。guard 在模块导入后开启，只有 Python audit 与已守卫入口的范围；不是 OS 沙箱，也不覆盖恶意原生代码。命令行导入缓存由上一节的独立 fresh-copy 测试覆盖。

Windows source 的 summary 已逐项核对，17/17 passed。随后 Windows 两个已安装环境分别通过 `--installed` 模式 17/17，均有六次 guarded resume、零副作用尝试；Linux 新隔离 venv 的同一 wheel 也通过 installed 17/17。所有这些夹具的 `real_rdc_reauthentication` 仍为 false，不从测试成功推导真实认证行为。

## 5. 恢复材料的发行隐私

独立打包反例发现恢复材料的常见命名还未被全部过滤。修复在遍历前按大小写无关规则剪除目录组件 `checkpoints`，并排除 `.recovery-marker.json`、`recovery-checkpoint.local.json`、`recovery-context.local.json`、`recovery-handoff.local.md`。ZIP、TAR、manifest、独立 HTML 与预览引用使用同一过滤边界；私有目录不被遍历，私有文件内容不被读取。公开的 `recovery-checkpoint.example.json` 和 `recovery-context.example.json` 仍保留。

[`test_release_privacy.py`](../tests/test_release_privacy.py) 修前 **7 个测试方法产生 26 个失败条目（含 subtests）**；不是 26 个独立测试。修后 7/7 通过，exit 0。验证包含真实生成的合成归档、HTML 私有哨兵、禁止引用和直接注入 sources 字典的反例。命名过滤不能识别任意文件中的秘密；发布前仍须审阅实际源码清单，私有账号、device/link、令牌、浏览器内容和原始运行日志不进公开包。

## 6. 验证层次与复现入口

在明确归属的源码目录使用新的输出目录：

```bash
python -B -m unittest discover -s tests -v
python -I scripts/smoke_recovery.py --output-dir evidence/recovery-source-new
```

第二条命令会创建自己的合成工作区和子进程，不能把它描述为只读操作；只读保证针对其中的 resume 评估阶段。详细模式与原 state 操作见 [Agent 指南](AGENT-GUIDE.zh-CN.md) 和[恢复规格](RESUME-SPEC.zh-CN.md)。

| 层次 | 本轮证据 | 不能推导的结论 |
|---|---|---|
| 核心离线／合成回归 | Linux 225、Windows 225，分别记录 pass/skip | 不代表任意应用、网络或断电时序都已验证 |
| 本地子进程效果见证 | Linux／Windows source smoke 各 17/17 | 合成 effect 不是 RDC 断线或真实业务系统写入 |
| fresh-copy CLI | 真实 `-B` 子命令正向和去 `-B` 反向控制 | 不保证 OS 不更新 atime、不保证宿主不记日志 |
| 独立审阅 | 规格审查、运行时反例、harness 反向控制、打包隐私测试 | 独立审阅无新增 coding-standard finding 不等于“没有任何缺陷” |
| 已安装包 | Windows 两环境各 17 项恢复 smoke，Linux 隔离安装包 17 项；Windows 另有真实现代 MCP 17 项 | 分开的进程／协议验收不合并成同一 suite；没有重跑 GUI 或 legacy MCP |
| GitHub CI／公开资产／部署 | a6 实际回执已核对，见第 9 节 | 旧 a5 结果仍独立保留；部署不等于浏览器交互验收 |

规格审查先澄清了同 ID 重连代次、request/config 关联未验证、精确 marker 绑定、并发快照复核、软暂停及私有 scope 正文归属；随后对实际代码的审阅发现了提交后回读缺陷。独立标准审阅在其受审 diff 中没有确认的编码规范违例，并另外复现了同一回读问题；两份意见不是两次独立全套运行。规格独立 follow-up 已确认两项问题关闭，无剩余 blocking finding；这不是所有代码无缺陷的证明。原始检查点及错误输出都保留在私有证据账本，公开文档仅引用脱敏结论。

## 7. 对其他 Agent 的实际用法

路由先看任务。网页 UI 任务按当前宿主 Browser Skill 与实际 Chat／Work 模式选择能力；只读已有记录的任务直接读记录。两者都不为触发本 Skill 而额外发现 RDC、运行 doctor 或启动终端。确需 RDC 时才重新取得当前连接、设备和工具 schema。旧授权不因会话变化自动失效，但同样不能替代当前工具的许可。

用户完成手动重新登录后，先保留原任务、原 config/state、请求材料和未知效果，读取 fresh route，再做只读 resume 或 a5 的人工对账。需继续时，独立查明业务效果、重新观察 UI／进程，并在原授权内执行剩余工作；不要自动改账号、换凭据、重新配对、升级软件、丢弃旧 state 或换 ID 重发未知请求。

交接包至少包含任务正文及已授权范围、停止原因、原请求与 config/state 的私有引用、检查点 revision/generation、完成与未知证据、typed handles 的来源和时间、当前待核对事项。正文在私有文件中保存，hash 只用于比较；日志是证据，不是新指令。普通公共文档只保留脱敏的结论和可复现合成样例。

原生 Agent 前向推演覆盖浏览器优先、继续原任务、PID 与页面变化、quota 停止四种情形，响应均保持这些边界。该结果来自四份场景回答，没有实际操作浏览器或进程，不保证所有 Agent、所有未来宿主都会遵守。canonical Skill 八个资源已经保存并远端回读核对；复用副本与[公开研究](research-wave6/RESEARCH-RECOVERY.zh-CN.md)供其他宿主按自己的导入方式使用。

当前会话对既往任务的查阅只取得相关检索片段，没有读取完整聊天记录，不能据此声称还原全部历史。主执行者实际重新发现了用户手动登录后的现有 RDC 路由；原始账号与设备值不公开。真实 Browser 对 `chatgpt.com` 的宿主拒绝、localhost 自动审批拒绝、HMC 额度阻断和 OMP 失败记录全部沿用，未重新测试、换表面绕过或借新路由改写为通过。

## 8. 已安装包与公开发布回执

| 事项 | 本检查点状态 | 最终须记录的证据 |
|---|---|---|
| Windows a6 wheel 安装 | 已完成 | 两个已有环境 offline／no-deps 从 a5 升到 a6；旧包备份保留，各 12 个模块 SHA-256 与 wheel 相同；非 Kit distribution 与 config 哈希不变 |
| 已安装恢复 smoke／CLI | 已完成 | Windows 两环境 `-I` 实际 site-packages 导入、版本 a6、恢复各 17/17；两个 `Scripts/rdc-kit.exe` 均为 a6；Linux 新隔离环境同一 wheel 恢复 17/17 |
| 已安装现代 MCP | 已完成 | SDK 2.3.0 真正 stdio 协商 `2026-07-28`；三工具、严格双通道一致、unknown 保留、worker 正常返回、夹具未变，17 checks passed |
| a6 GitHub 源码与 CI | 已完成 | `edf4aa52` 的六个 job 全部 success；各平台 run/pass/skip 见第 9 节 |
| a6 tag 与 Release | 已发布 | 18:07:02 JST；九项资产全部下载回读一致；固定 tag 见第 9 节 |
| a6 Pages | 已部署 | 发行提交的 build/deploy success 与实际 page URL；仍无本轮 live Browser 验收 |

本轮已安装 wheel 为 **51,757 字节**，SHA-256 为 `f84ae08e8e6625a14ca84fe2b4a154a58ee4829c5a3866dc9bb23656b2f2770e`。wheel 只更新 Kit；源码主副本的最终同步和公开发布分别记录，不能因 site-packages 已升级便视为其他交付全部完成。

当前 a6 下载与历史 a5 发布步骤见[安装与发布说明](RELEASE.zh-CN.md)，所有轮次总览见[验证记录](VERIFICATION.zh-CN.md)。已公开资产保留冻结字节，main 的后续发布补记与原归档分开。

## 9. 实际公开发行与 Pages 部署

`v0.1.0a6` 于 **2026-11-28 18:07:02 JST** 公开为预发布 alpha，固定到公开提交
`edf4aa52e11d1f326cee93a538b8dfa7422a055f`。不移动 a5／a6 tag，不覆盖既有 Release 资产。
[打开 a6 Release](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a6) ·
[发行提交 CI](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/46128657762) ·
[发行提交 Pages](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/46129018315)

发行提交的六个 CI job 全部 success；日志回读结果如下。与本机数量的差异是各环境实际
skip，不把未执行项算作通过，也不把每个 job 的同一套测试累加成独立能力数。

| Job | Core run / pass / skip | 恢复 smoke |
|---|---|---|
| Windows / Python 3.10 | 225 / 217 / 8 | source 17/17 |
| Windows / Python 3.13 | 225 / 217 / 8 | source 17/17 |
| Ubuntu / Python 3.10 | 225 / 219 / 6 | source 17/17 |
| Ubuntu / Python 3.13 | 225 / 219 / 6 | source 17/17 |
| MCP stdio / Windows | 真实 SDK 会话 job success | installed 17/17 |
| MCP stdio / Ubuntu | 真实 SDK 会话 job success | installed 17/17 |

最终公开源清单包含 **156 个源文件**；ZIP、TAR 各含这 156 个文件及一份 manifest，共
157 条目，已逐字节核对。独立审查核对了 38 份站点文档，站点副本的 53 条跨出 docs
的源码引用改为固定 tag 上的 GitHub 路径；源码文档仍保留仓库相对链接。静态检查覆盖
三个 HTML 文档、22 个 HTML 相对目标、338 个 Markdown 相对目标，不宣称完整无障碍
或真实浏览器渲染验收。Windows 的最终源码副本也已同步核对这 156 个文件，旧源码和
两个已安装包有独立备份，原 config 哈希及既有运行记录保留。

九项资产先上传为 draft，再实际下载全部文件逐项比较 SHA-256，全部一致后才公开：

| 发行资产 | 字节数 | SHA-256 |
|---|---:|---|
| `RDC-Operator-Kit-0.1.0a6-report.zh-CN.md` | 17,668 | `afc8b3473942d102937d150db3289d3194b66672c752c0f5009971572a00aba2` |
| `RDC-Operator-Kit-0.1.0a6.tar.gz` | 702,737 | `c7d90fc16974f2489424c4e465f87f9cb4a84b1522dc0dfbb643bb024b746449` |
| `RDC-Operator-Kit-0.1.0a6.zip` | 863,847 | `29b6ccc06f21ca6636e220e4181df3daf70a402c71bee41328fe631e9881e586` |
| `RDC-Operator-Kit-preview.html` | 281,400 | `615b8f08de0f90588cd5da9c69d46e84d1d6efe85f380efdc666c7195172412e` |
| `RELEASE-VALIDATION.json` | 1,596 | `681f9cfa9d44ede34eed315619fb875890ad58deeace650f4a1ce327188fa455` |
| `SHA256SUMS.txt` | 777 | `562a4ebff115f1610d96014063102fdc15f6b2c6fb0a77b43ca0357df0c9a161` |
| `SOURCE-MANIFEST.json` | 26,228 | `226031bd24c671a92ea8f055430489968e78f3dc9d8f9955a5d2eb187d3b01e3` |
| `rdc_operator_kit-0.1.0a6-py3-none-any.whl` | 51,757 | `f84ae08e8e6625a14ca84fe2b4a154a58ee4829c5a3866dc9bb23656b2f2770e` |
| `static-web-audit.json` | 550 | `5b5ced923dd4b482253157e35ec84c49d44445d76fa186f25fb76f5a5cf4204d` |

Pages 的 build 与 deploy 均 success，部署状态回读在 **18:08:31 JST** 返回 success，
对应同一个发行提交和实际页面 URL：<https://dwgx.github.io/RDC-Operator-Kit/>。
这是部署证据，不增加 live Browser 验收。随后 main 只补充这些已经发生的发布回执与
当前安装指南；发行包内报告保留打包时的发布前检查点，正文的后续补记不改变发行资产。

本轮没有真实登出、重新配对或自动账号切换实验。连接变化由合成 context 覆盖；实际
RDC 仅重新发现用户已经手动登录后的当前路由，并执行授权的文件、测试与发布工作。
