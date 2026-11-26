# Windows preflight / focus 独立技术复核

日期：2026-11-26。审查者：独立只读 reviewer。源码：<project>。

## 结论

本轮发现 1 个真实的 P2 目标绑定问题：已经观察过的顶层窗口在同一进程内被重新设置父窗口后，原 focus 实现可能先激活未观察的父窗口，随后才因回执 HWND 不匹配返回 outcome_unknown。主代理已在审查期间修复；我重新读取修复后的源码并独立验证，当前没有尚未解决的 actionable finding。

这是代码、上游原始源码与 Linux 本地合成验证的结论，不能替代 Windows 原生 ABI 执行或真实 GUI 验收。本审查未调用远端设备、真实浏览器或真实 Windows 输入。

## 审查基线与规范来源

- 固定基线：baseline-0.1.0a3，解析为 4930cd026f29ac61da88992712f002fc4b6943a4。
- HEAD 仍是该基线；被审对象是未提交工作区变化，因此实际审查使用 git diff baseline-0.1.0a3，并单独读取未追踪的 windows.py 与新测试。没有把空的 baseline...HEAD 当成被审改动。
- 规范全文：AGENTS.md、README.md、docs/ARCHITECTURE.zh-CN.md。架构文档自标 0.1.0a2，使用其中仍适用的 contract，不把历史平台验收当成 a4 验收。
- 范围：rdc_operator/windows.py、cli.py 的 windows-preflight 分支、adapters.py 的 desktop.focus 接入、相关观察/身份/回执共用路径、test_windows_context.py、test_focus.py。
- 需求：预检仅观察，不授予权限；focus 单独授权，绑定短效观察与实际 HWND/进程；保留 click guard；不自动重试；不绕过 Browser 拒绝。
- 没有为凑数列举命名、抽象或代码气味。以下两轴中的同一 finding 不应重复计为两个独立缺陷。

## Standards

### S1 — P2，已修复：focus 的上游根窗口归一化可能扩大已观察目标

**规范依据：** AGENTS.md 要求 Windows 操作绑定 fresh observations、HWND/process identity；docs/ARCHITECTURE.zh-CN.md 的“Windows 桌面目标”要求 mutation 使用短效 observation 并绑定同一窗口。捕获/操作完成后拒绝一个不匹配回执，不能撤销已经发生的窗口激活。

**原问题位置：** 修复前 adapters.py:531–535 在 HWND/PID/TID/创建时间/executable 匹配后直接进入 focus；原 adapters.py:613 即调用上游，原 :620–625 只在效果发生后检查回执 HWND。当前相应调用和回执校验位于 :631–643。

**可复现场景：**

1. 对顶层窗口 A=123 成功执行 desktop.observe；记录 PID=7、TID=8、创建时间=111、相同 executable。
2. 应用随后把 A 重新挂到同一进程的另一窗口 B=456 之下。A 的 HWND、PID、TID、进程创建时间和 executable 均不需要改变；observation 仍在 TTL 内。
3. 发送绑定该 observation 的 desktop.focus --apply。
4. Microsoft winapp v0.8.0 的 FocusWindowAsync 先执行 GetRootWindow(uiTarget.WindowHandle)，对根窗口 B 执行必要的 restore 和 RequestForeground，最后返回 Hwnd=B。
5. 原 Kit 会在上述副作用之后返回 outcome_unknown / invalid_action_acknowledgement。它没有误报 completed，却已经操作了未观察的 HWND。

**证据校正：** 单纯给一个始终是 child 的 HWND 并不是充分反例。独立读取的 UiAutomationService.InspectAsync 通常会把 inspect 输出归到 GA_ROOT，Kit 的 _selectors 随后会拒绝与请求不符的 HWND。这里最终成立的反例是“观察完成后 reparent”，不是忽略 inspect 的静态 child 假设。

**最小修复及已验证结果：** 当前 adapters.py:421–429 新增明确 HWND/UINT/ HWND ctypes 声明的 _root_window；:624–630 在调用上游前要求 GetAncestor(A, GA_ROOT)==A，并再次核对 identity。若 root 不匹配或为零则拒绝，不采用 root 替代原目标。tests/test_focus.py:93–100 覆盖同 identity 的 reparent，断言 _winapp 未被调用。独立合成演示中，原行为记录 activated_hwnd=456 后返回 unknown；修复后 failed/top_level_target_required，effects=[]。

**残余边界：** 根窗口检查与上游真正执行之间仍存在 TOCTOU。修复消除了检查时已经存在的层级变化，不能冻结共享桌面或保证之后绝不会变化；此项不应被描述为“消除所有 race”。

## Spec

### R1 — P2，已修复：独立 focus 只能作用于 fresh observed window

上述 S1 同时违背这一需求：原实现虽然绑定短效 observation 和进程身份，但没有在执行前核对上游实际会操作的根 HWND。当前修复将这种已变化目标在效果发生前拒绝；它没有扩大授权为父窗口，也没有删除 click guard 或增加重试。

本范围未发现其他缺失需求或多余控制路径：windows-preflight 在配置和 state 读取之前分支返回；它只调用查询 API。focus 属于 MUTATING_ACTIONS，必须 --apply，参数只允许 observation_id；已知 Browser executable 仍由 _window_identity 拒绝。

两轴计数：Standards 原 1 项 P2、当前 0 项未解决；Spec 原 1 项 P2、当前 0 项未解决。两轴指向同一个已修复问题。

## 已独立核对的关键证据

| 项目 | 源码位置 | 判定与边界 |
| --- | --- | --- |
| Win32 ABI | windows.py:135–164 | HWND/HANDLE 用指针宽类型；BOOL/DWORD、FILETIME 输出指针及 OpenProcessToken 的 PHANDLE 声明与官方签名一致。USEROBJECTFLAGS 是 BOOL、BOOL、DWORD；SID_AND_ATTRIBUTES 是指针加 DWORD，保留本机对齐。仅静态核对，未在 Windows Python 进程中执行。 |
| 句柄归属 | windows.py:170–175、210–278、323–353 | OpenProcess / OpenProcessToken 获得的 owned handles 用 CloseHandle；OpenInputDesktop 用 CloseDesktop；GetThreadDesktop 与 GetProcessWindowStation 的 borrowed handles 不关闭。Close 失败被记录为查询不完整。 |
| 只读预检 | windows.py:323–375、cli.py:57–61 | OpenInputDesktop 仅请求 DESKTOP_READOBJECTS；没有 SwitchDesktop、SetThreadDesktop、SendInput、SetForegroundWindow、ShellExecute runas 或 token/policy 修改。CLI 分支不读取 config，也不创建 state。 |
| Token 解码 | windows.py:193–260 | TokenElevationType=18、TokenElevation=20、TokenIntegrityLevel=25、TokenUIAccess=26 与枚举吻合。完整性 SID 仅在返回 buffer 内做边界检查和字节读取，没有直接解引用不可信 SID 指针。 |
| UAC / UIPI 推断 | windows.py:45–115 | 零 foreground、OpenInputDesktop access denied、未知 token 均没有被推断为 UAC。uac_state 始终 not_determined；高 integrity、不同 session、desktop mismatch 保持保守阻断；UIAccess 不被当成授权。 |
| 预检未知状态 | windows.py:355–411 | target identity 前后采样；已知变化为 blocked，缺失为 unknown；前台变动会报告；返回 atomic_snapshot=false。无 target 时不能得到目标级 observed 结论。 |
| Focus 的确认格式 | adapters.py:637–643 | 独立读取 v0.8.0 UiFocusCommand.cs 确认 window-only focus 的 elementId 为空、hwnd 为实际根 HWND。Kit 要求 empty elementId、严格 int HWND、值相同且没有 error 字段；不接受错 HWND 的成功回执。 |
| 失败可能已有副作用 | adapters.py:621–636 | 上游可能先 restore 再拒绝 foreground；focus 对所有 _failed 返回统一保留 outcome_unknown，而不是套用 click 的“已知 pre-effect error”结论。没有自动再次 focus。 |
| Ack 与观察、业务效果 | adapters.py:644–662 | 成功 ack 后再观察和读 kernel foreground，且重新核 identity。只有观察有效、identity 相同、foreground==目标才 completed；application_effect_verified 始终 false。焦点状态只是采样时的证据，不代表后续业务完成。 |
| 请求身份、intent、replay | core.py:93–147 | 新 action 继续使用完整 request+config digest；state lock 覆盖准备/执行/提交；先保存 intent；已有 receipt 在 validation 前返回，既不刷新 observation 也不再次执行。未知 outcome 不自动重放。 |
| Browser / click guard | adapters.py:404–407、原 click 路径 | 新 focus 仍通过 kernel executable 检查，没有新增 browser fallback；click 的 canonical selector、目标 identity、上游错误保留等路径未被删除。Browser 名单不是完整 OS 安全边界，这一既有文档限制仍成立。 |

## 执行的验证

环境：Linux 6.18.57 x86_64、glibc 2.41、CPython 3.12.14。均为本地 synthetic/mocked adapter；没有 Windows GUI 或远端输入。

| 实际命令 / 验证 | 结果 |
| --- | --- |
| python -m unittest discover -s tests -p 'test_windows_context.py' -v | 11 passed，0 failed，0 skipped。 |
| python -m unittest discover -s tests -p 'test_focus.py' -v（修复前） | 6 passed，0 failed，0 skipped；该六项没有覆盖 reparent。 |
| python -m unittest discover -s tests -p 'test_focus.py' -v（修复后） | 7 passed，0 failed，0 skipped。 |
| 直接调用 cli.main，模拟 observed / unknown / blocked / unsupported 四态；传不存在的 config、state；--window 0x190 | 四态 exit code 分别 0/1/1/1；传入 native collector 的 HWND=400；read_json 未调用；临时目录保持空。 |
| 真实 execute_request + desktop.observe + intent/receipt，mock kernel 和 WinApp 的同进程 reparent 演示 | 原函数模型：副作用 B=456、unknown/invalid_action_acknowledgement；当前函数：failed/top_level_target_required、无副作用；两者 duplicate request 均只返回 replay。 |

最后一项对“原函数”的执行是从已经读取过的旧函数恢复其代码：从当前函数文本中仅移除这次新增的 GA_ROOT 和再次 identity 检查块，在独立 namespace 中执行，不修改源码文件。没有宣称该原行为在真实 Windows 桌面上执行过。

### reparent 合成演示的观测输出

~~~json
[
  {
    "version": "reviewed_before_fix",
    "status": "outcome_unknown",
    "code": "invalid_action_acknowledgement",
    "effects": [{"activated_hwnd": 456}],
    "replayed": true
  },
  {
    "version": "current_fixed",
    "status": "failed",
    "code": "top_level_target_required",
    "effects": [],
    "replayed": true
  }
]
~~~

## 明确未覆盖的范围

- 没有运行 Windows x86/x64/ARM64 的真实 ctypes 调用；原生 DLL 加载、真实 token buffer、真实桌面切换与 UIAccess token 的运行证据仍需由相应平台验收提供。Linux 的 mock 测试不能冒充 ABI 验证。
- 没有测试真实 UAC、锁屏、RDP disconnected session、提权边界或真实浏览器。Microsoft 明确说明 OpenInputDesktop 在 disconnected session 可以返回恢复连接后将激活的 desktop，因此该 API 本身不能证明会话当前已连接；代码的 limitations 正确保留这一未知。
- 前台 HWND 和进程 identity 是分步采样；同一进程内 HWND 复用、外部输入、窗口重建以及检查之后的 reparent 仍可能竞争。GetForegroundWindow 的一次读回只能支持当次观察，不能保证焦点保持。
- 预检采样的是运行 collector 的进程与 desktop，不是对所有未来配置 backend 的令牌、任务授权或业务效果的证明。
- 没有评审或运行发布、CI、installer、site/browser smoke 的其余变化；报告不为这些范围作通过结论。

## 复核时文件指纹

~~~text
d7853f4ab9dc50a25d089e2ffe294317d1bc7f0d5d2c6f56bb49682a55bec413  rdc_operator/windows.py
e125283d5c972c90c809dda82f94e27937c2dbfb67d4dc7a96321b77b6a81d4e  rdc_operator/adapters.py
a956964b1bd297c4e4c472c2f87a223f783bc771fdee5d0d86025d5e563ee23c  rdc_operator/cli.py
7b0219e43a4b6a3fdbb4c690e0d75c0090751184c8604ae7f518fcc687790eac  tests/test_windows_context.py
0eb5c5ee348f2283692f18534b5772289b1a2a9a14099aa8e734d9943520987c  tests/test_focus.py
~~~

## 一手资料

以下内容由 reviewer 自己读取，不依靠其他 agent 的上游摘要。GitHub 搜索仅用于定位文件，判定使用固定 v0.8.0 文件内容。

- [Microsoft winapp v0.8.0 UiFocusCommand.cs](https://github.com/microsoft/winappCli/blob/v0.8.0/src/winapp-CLI/WinApp.Cli/Commands/UiFocusCommand.cs)，blob d71695022d8d3d0eeb2cc0df6387b703be233c02：FocusWindowAsync 的根窗口选择、restore/activation 顺序和结果模型。
- [Microsoft winapp v0.8.0 UiTargetResolver.cs](https://github.com/microsoft/winappCli/blob/v0.8.0/src/winapp-CLI/WinApp.UIAutomation/Services/UiTargetResolver.cs)：ResolveByHwnd 保留显式 HWND。
- [Microsoft winapp v0.8.0 UiAutomationService.cs](https://github.com/microsoft/winappCli/blob/v0.8.0/src/winapp-CLI/WinApp.UIAutomation/Services/UiAutomationService.cs)，blob 82585cf6365d3539afc6058d5522913973cc71be：InspectAsync、GetRootElementCore、GetTopLevelWindowHandle。
- [Microsoft winapp v0.8.0 UiStatusCommand.cs](https://github.com/microsoft/winappCli/blob/v0.8.0/src/winapp-CLI/WinApp.Cli/Commands/UiStatusCommand.cs)：status 返回解析后的显式 HWND。
- [GetAncestor](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getancestor)、[SetParent](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setparent)、[IsWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-iswindow)：parent 链、重新挂接与 HWND 复用边界。
- [GetUserObjectInformationW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getuserobjectinformationw)、[USEROBJECTFLAGS](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-userobjectflags)：UOI_IO、UOI_NAME、flags 与 ABI。
- [OpenInputDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop)、[CloseDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-closedesktop)、[GetProcessWindowStation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getprocesswindowstation)、[GetThreadDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getthreaddesktop)：句柄归属和 disconnected session 限制。
- [TOKEN_INFORMATION_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class)、[TOKEN_MANDATORY_LABEL](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_mandatory_label)：token class 和结构。
- [Security Considerations for Assistive Technologies](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)、[SetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow)：UIAccess 不等于普遍高权限许可，Windows 可拒绝前台激活。
