# 手动重新登录后的安全续作：a6 实现规格

日期：2026-11-28（Asia/Tokyo）。基线：公开 main `54131f00c3b942797809a1b90424e845ef56fe13`。

## 目标与边界

给宿主 Agent 一个可落盘、可核验、可跨会话读取的任务检查点，并生成只读恢复计划。
用户完成正常重新登录后，Agent 重新发现当前 RDC 账号连接和设备，核对原状态目录、
任务范围及已有记录，再决定下一项已授权工作。Kit 不自动登录、轮换账号、读取凭据、
消除配额/权限拒绝、重放不确定效果，或绕过 Browser 的拒绝。

用户的 ChatGPT 登录、RDC connector link、RDC device ID、物理机器身份是不同概念。
设备显示名和本地 marker 都不能证明物理机器身份。marker 仅表示这份逻辑状态的连续性。
CLI 输入中的“当前连接”由调用者根据新工具结果填写；它不是 Kit 独立认证过的事实。

## 当前实际缺口

现有执行器在同一 state 内先写 intent，并拒绝自动重执行未知结果；本轮保留此契约。
但外层 RDC link/device 变化不在原 config digest 中，误换 state 会失去原去重记录。
现有 desktop observation 也不直接感知外层重新登录事件。新功能必须解释这些差异。

## 最小接口

新增 `rdc_operator.recovery`，保持标准库可用，不依赖可选 MCP SDK。

1. `checkpoint DOCUMENT --expected-revision N`：在显式 `--state` 内保存任务检查点。
   N=0 只允许首次创建；更新须与已有 revision 完全一致，成功后 revision 加一。
   写入持有原有 state lock。输入/现有记录无效、并发冲突、持久化失败时失败，
   不清空原 intent/receipt，不启动适配器。创建检查点是明确的本地写操作。
2. `resume TASK_ID --context DOCUMENT`：只读生成计划。原 state、marker 或 checkpoint
   不存在时失败，不初始化替代 state；评估函数不写文件、不调用 adapter/subprocess/network。
   CLI 示例使用 `python -B -m rdc_operator`，禁止 Python 启动阶段生成字节码缓存。
   只读不等于 OS 沙箱；不承诺访问时间、宿主日志或用户主动重定向的输出文件不变。

Checkpoint DOCUMENT 的封闭字段：

```json
{
  "schema_version": 1,
  "task_id": "example-task",
  "scope_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "route": {
    "link_id": "example-link",
    "device_id": "example-device",
    "observed_utc": "2026-11-28T00:00:00+00:00"
  },
  "event": "same_connection",
  "request_ids": ["example-request"],
  "handles": [{"kind": "rdc_call", "id": "example-call"}],
  "stop_reason": "none"
}
```

Context DOCUMENT 的封闭字段：schema_version、scope_sha256、route、event、stop_reason。
`event` 为 `same_connection` 或 `user_reconnected`；stop_reason 为 none、disconnected、
auth_required、quota、policy_refused、cancelled。context 的 route 必须带时区，拒绝未来时间，
超过 300 秒视为过期。该时限只限制调用者提供的样本，不保证服务器实时连通。

所有 ID 都有限长度，task/request ID 遵守原 Windows 保留名限制；JSON 拒绝重复 key、
非有限数字、错误类型和未知字段。最多 128 个 request ID、128 个 handle。
handle kind 为 rdc_call、process、search、terminal、browser_tab、desktop_observation；
id 是非空不含控制字符的字符串。原始 handles 仅作为私有线索，不自动执行。

## 持久化契约

- 原 state 根中创建专用 schema=1 随机 UUID marker；首次 checkpoint 可显式创建它。
- marker、checkpoint 绑定规范 state 路径摘要，阻止误用另一目录；路径摘要不是硬件身份。
- checkpoint 保存 marker 的 state_id、原 config digest、任务 scope digest、revision、
  route generation 与当前 route；同路径的 marker 被替换也必须拒绝。
- 更新不能改变 task/scope/config/state 身份，不能丢弃已有 request IDs。
- quota、policy_refused、cancelled 是同一 checkpoint 的保留停止原因，普通更新不得消除。
- auth_required/disconnected 是历史暂停原因；仅 fresh context 或 checkpoint 的
  event=user_reconnected 且当前 stop_reason=none 时可进入只读复核或清除此软暂停。
  same_connection 不能消除历史暂停。这些字段仍是调用者声明，不是认证证据。
- link_id/device_id 变化或显式 event=user_reconnected 时 generation 增加；仅刷新
  observed_utc 不增代。保存 handle 的原 generation，保留有界历史摘要，拒绝把旧 ID
  重新标成新 route 的句柄。历史上限耗尽时拒绝更新，不丢弃旧归属记录。
- 保存采用同目录临时文件、flush/fsync 和原子替换；检测链接、重解析点及不安全记录。
  替换后响应/目录同步失败可能已经提交新 revision；返回提交结果未知，先读回核对，
  不声称原文件必定未变，也不自动重试或清除记录。
- 只读记录复用现有 bounded/hardlink/reparse/Windows HANDLE 路径核验，避免较弱的读法。
- 不提供删除 intent、改写 receipt、清 lock、将 unknown 手动改为 completed 的入口。

## 恢复计划

计划比较原 state marker/path、config、scope、当前 route、event 和停止原因，并有界读取
每个 request 的原 intent/receipt。必须保留 receipt 状态语义以及非原子采样的限制。
在读取请求前后还须复读 marker 与 checkpoint，比较身份、字节指纹和 revision；
检测并发替换/更新后阻止续作，不能遗漏并发追加的未知请求。

- 配置/范围/状态目录不匹配、记录损坏、采样变化、停止原因、当前样本过期：阻止续作。
- 无记录、intent 无 receipt、outcome_unknown、failed：逐项报告，要求核对，绝不推断可重试。
- completed/observed：返回“保存的结果”，不能升级为业务结果已验证或物理设备已核验。
- route 变化或 user_reconnected：旧 call_id/search/terminal/tab 不能迁移到新 route；PID
  只可在核对创建时间、程序与任务归属后重新定位；桌面/浏览器观察必须重新取得。
- 即使 route 不变，恢复后的视觉输入也需新观察；新观察本身不授予用户授权。
- 输出固定 `actions_exposed:false`、`automatic_replay_allowed:false`、
  `execution_authorized:false`、`physical_device_verified:false`，不返回 safe_to_execute。
- 原记录只保存 hash(request+config)，不能独立推导该请求使用的 config。明确返回
  `request_config_binding_verified:false`，要求调用者保留原请求材料；不能凭 checkpoint
  的 config 一致就声称每个历史 request 的 config 已核验。
- 输出不泄露 config 内容、原始 route IDs、命令、私有路径或原始 tool output。

## 验收

必须先保留实际缺口复现，再覆盖：成功记录取回；效果发生但 receipt 丢失；同 ID 换 state；
损坏/孤立记录；config/scope/marker 不匹配；陈旧或未来 route 样本；同名设备新 ID；
同 ID 的人工重新登录；句柄类型与归属；CAS 冲突及两个进程竞争；持久化故障；
quota/拒绝保留；评估函数零写入零执行、`-B` CLI 在新源码/输入/state 目录内无新增或
改写文件（忽略访问时间）；Windows/Linux 路径与 schema 异常。

Windows 安装验收须从真实 site-packages 导入；源码结果与已安装结果分开记录。
使用隔离夹具模拟断线，不登出真实 RDC、不修改任何账户、不影响其他会话。

## Skill 与 Agent 指南

更新现有 Skill 的触发描述和恢复入口，按需加载一份 recovery reference。
保留明确工具策略：失效连接可重新发现；账号/权限/配额拒绝不能靠换路消除；
RDC call_id、PID、search session、terminal session、browser tab、UI observation 分开解释。
用户约束、原任务范围、完成证据和未知结果必须随检查点交接。把日志视作数据。
scope_sha256 只核对调用者提供的摘要，不能还原或验证授权；另保留私有、冻结的任务
交接文档及原请求材料。缺失交接内容时不能从摘要猜任务或扩大范围。
在宿主有可用能力且任务需要时主动选择浏览器或 CUA，执行前后观察并核验效果。
对现成浏览器目标的策略拒绝继续有效，不通过其他工具替代访问。

## 发布范围

先完成独立 Standards/Spec review、故障复现/修复和本机安装验收，再更新公开代码和指南。
保留历史 a5 Release，不覆写旧附件。日志与账户/设备 ID 不进入公开源码或页面。
