> 公开去标识副本。原始评审结论与失败记录保留；私有工作区路径已替换为占位符。

# Wave 05：Linux 安装与 liveness 独立审查

日期：2026-11-26。项目：RDC Operator Kit。

## 结论

**本次指定范围内，未确认新的 P1/P2。**

Linux 安装器增加的 `.venv/bin` 链接拒绝确实阻止了原先可复现的外部解释器执行路径；正常 venv 的 `bin/python` 符号链接仍能使用，解释器的 `sys.prefix` 保持在该自有环境。

liveness 的中途归档失败、case 中断和最终归档异常均未通过 stdout／退出码伪报 PASS。已完成的 case 可以保留；未返回结果的 case 不会被推断为 cleanup 成功；中途失败后没有再启动后续 case。

存在一项已实际验证的存储故障限制：若最终 PASS 已完成文件替换，随后归档报错，而唯一一次保守重写又持续失败，磁盘可能留下旧 PASS 文件。程序同时返回 `FAIL`、非零退出码和 `summary_current: false`，明确不承诺该文件代表最新完整结果。不能脱离这些返回字段，仅凭文件存在或旧 `status` 判定成功。这是本次可见且保守报告的失败边界，没有据此认定新的 P1/P2。

## 范围与来源

固定基线为已提交 a4：

```text
d9ab1b38fff68e77c88841c050b8c038f52dcdb5
```

实现与测试的审查范围仅为：

- `scripts/install.sh`
- `scripts/probe_terminal_liveness.py`
- `tests/test_install.py`
- `tests/test_liveness.py`

已读取当前四个文件及其相对基线的完整 diff，以仓库 `AGENTS.md` 的安装归属、保留失败证据和区分模拟／实测等要求作为规范依据。没有审查本轮 MCP、网站、CI 或发布实现的其他变更。

实现者提供的定向 install 6/6、liveness 18/18 是输入背景。本 reviewer 没有将这些数字冒充自己的复跑，也没有重跑整个测试套件；下文记录的是另行构造的独立反例和一次真实本地合成子进程检查。

本次只读取实现，在临时隔离目录中运行本地 fixture。未联网、安装第三方包、访问 HMC、操作 Windows／浏览器或调用模型；未修改 implementation。报告不包含设备、账号、任务运行 PID、真实 token 或私有路径标识。

## 受审源码指纹

| 文件 | SHA-256 |
|---|---|
| `scripts/install.sh` | `eed394f2ba145e81aaba7005353170106295ba3950e2662ecc388d4c3997c47c` |
| `scripts/probe_terminal_liveness.py` | `97ac77a176e0e1baa06a3733d7d061c5d0ef396268a210514a595fc77439cb40` |
| `tests/test_install.py` | `708df0213b246385f0f0aaf0d23581690864d036211cf3d5c31356b693b66dca` |
| `tests/test_liveness.py` | `30c8fb6b2aac971423a35e2ebc6cbb0909e887f0def15fa468f2aa5a10e5d408` |

执行环境：Linux 6.18.57 x86_64、glibc 2.41、CPython 3.12.14。

## Standards：规范轴

没有发现本次变更违反已记录规范的具体 P1/P2。

安装器在执行 `.venv/bin/python` 之前检查容器目录是否为 symlink，且不错误拒绝 venv 正常的解释器链接。拒绝路径不会修改既有 ownership marker，也不会运行隔离环境以外的 fixture interpreter。这里验证的是本轮修复的路径边界，不是对所有 venv 内部路径或同权限恶意并发替换的完整隔离证明。

liveness 在启动 case 之前保存运行意图，case 返回后立即保存结果。归档异常使流程停止，最终输出区分执行失败、归档失败和中断。未返回的 case 使用 `result_returned: false` 与 `cleanup_verified: null`，没有根据异常倒推子进程已完成清理。修改没有新增任意 PID 接管或进程名清理路线。

新增测试检查了真实会影响结果的行为：阻止外部解释器执行、保留合法 interpreter symlink、保存完成 case、停止后续工作，以及纠正最终替换后可能出现的 PASS。未将断言数量作为质量证据，也没有发现需要单独报告的代码异味。

## Spec：需求轴

### 安装器修复已独立验证

在独立临时源码树中复制安装脚本，写入匹配该 fixture 的 ownership marker。`.venv/bin` 使用相对 symlink 指向另一个同属本次临时实验的目录；该目录中的 `python` 是一个只写入合成 sentinel、随后退出 79 的 shell stub。所有输出均留在临时 fixture 中，不接触真实环境。

| 独立场景 | 实际结果 |
|---|---|
| a4 基线脚本，relative `bin` symlink | 外部 fixture stub 被执行，返回 79，sentinel 出现，复现原缺口 |
| 当前脚本，相同 relative `bin` symlink | 返回 1，报 `Linked installation path refused: bin`；sentinel 未出现，marker 字节不变 |
| 当前脚本，dangling `bin` symlink | 在执行前按链接拒绝，没有新建配置 |
| 真实 `venv --without-pip --symlinks` | `bin` 为实际目录、`bin/python` 为正常链接；`sys.prefix` 等于自有 venv 且不同于 `base_prefix`；安装器未拒绝该链接，正常运行到缺少本地 pip 后停止 |

最后一项只证明合法解释器链接与环境定位保留，不证明完整 package installation 成功。实验设置 `PIP_NO_INDEX=1` 并移除继承的 `PYTHONPATH`／`PYTHONHOME`；没有发生包下载或真实 pip 安装。

执行方式是独立 `python -B` 临时夹具驱动，通过 `subprocess.run(["bash", fixture_install_script])` 调用脚本。基线脚本通过以下只读命令取得：

```bash
git show d9ab1b38fff68e77c88841c050b8c038f52dcdb5:scripts/install.sh
```

正常 venv 的创建命令结构为：

```bash
python -I -m venv --without-pip --symlinks <isolated-source>/.venv
```

### liveness 修复已独立验证

独立探针直接调用真实 `main(argv)`，没有使用新增测试类的 helper。七个故障场景只在 `run_case` 边界提供合成结果、在 `atomic_json` 边界注入故障，生产 `expectations()`、状态转换、最终 JSON 输出和返回码均保持实际实现。

| 故障位置 | 后续 case | 返回／stdout | 落盘结果 |
|---|---|---|---|
| 第一个 case 已返回，`case_complete` checkpoint 抛 OSError | 不启动第二项 | exit 3，FAIL，`summary_current=true` | FAIL；完整保留首个 result |
| 第二项的 `case_running` checkpoint 抛 KeyboardInterrupt | 第二项尚未执行，第三项不启动 | exit 130，FAIL，current=true | FAIL；active case 不伪报结果或 cleanup |
| 第二项 `run_case` 抛 KeyboardInterrupt | 第三项不启动 | exit 130，FAIL，current=true | FAIL；保留第一项，第二项 cleanup 为 unknown |
| 最终 PASS 替换后抛 OSError，保守重写成功 | 已完成全部合成项 | exit 3，FAIL，current=true | PASS 被保守 FAIL 替换 |
| 最终 PASS 替换后抛 KeyboardInterrupt，保守重写成功 | 已完成全部合成项 | exit 130，FAIL，current=true | FAIL，保留 interrupted 标志 |
| 最终 PASS 替换后抛 OSError，保守重写继续 PermissionError | 已完成全部合成项 | exit 3，FAIL，current=false | 旧 PASS 可能残留，未被声明为最新有效归档 |
| 最终 PASS 替换后抛 KeyboardInterrupt，保守重写继续 PermissionError | 已完成全部合成项 | exit 130，FAIL，current=false | 同样保留旧文件的不确定性，不返回成功 |

七个场景均得到上述预期结果。故障注入只构造合成证据，不意味着相应真实子进程已经运行或清理。

另外进行一次真实本地 `waiting-input` fixture 验证：让现有 `run_case()` 实际启动并完成合成 child，在其返回后的 `case_complete` checkpoint 注入 OSError。观察到 `business_completed`、`semantic_verified=true`、`direct_child_exit_confirmed=true`、`readers_joined=true` 均完整保留；下一项没有启动，最终归档为 FAIL，exit 3，`summary_current=true`。这项补测验证了真实结果与新失败归档路径的结合，仍不是任意终端或 Windows 验收。

故障注入的核心条件可复现为：

```python
failed_once = []

def failing_checkpoint(path, report):
    if report["phase"] == "case_complete" and not failed_once:
        failed_once.append(True)
        raise OSError("synthetic archive failure after owned child returned")
    original_atomic_json(path, report)
```

实际探针以闭包保存 `failed_once`，并在 `main()` 返回后读取 stdout 与 summary，比对退出码、状态、完成 case 和未执行 case。最终替换故障探针先调用原 `atomic_json()`，再抛出指定异常；持续故障变体则让随后的 FAIL 重写在写入前再次报错。

## 新增测试的覆盖判断

`tests/test_install.py` 的两个新增用例是有用的回归：外部 sentinel 证明被拒绝路径没有执行解释器；真实无 pip venv 证明修复没有把正常 `bin/python` symlink 一并禁止。它们没有声称完成真实联网安装。

`tests/test_liveness.py` 的六个新增用例验证了失败启动／中断前已完成的真实 fixture、初始归档失败无启动、最终替换后错误与中断的保守重写，以及正常单 fixture 的 PASS 契约。独立补测进一步覆盖中途 checkpoint 失败和保守重写仍失败的情况。

本次没有因“缺少某个测试”单独建立 finding：在已实际构造的补充反例中，未观察到当前实现返回错误的成功结果。永久写入失败下不能只依靠磁盘 summary 的限制，应在使用或汇总证据时继续尊重。

## 其他检查与边界

以下 scoped diff 检查返回 0，无输出：

```bash
git diff --check d9ab1b38fff68e77c88841c050b8c038f52dcdb5 -- \
  scripts/install.sh scripts/probe_terminal_liveness.py \
  tests/test_install.py tests/test_liveness.py
```

没有重新执行 full core suite，没有把实现者的已有 6/6、18/18 计为本 reviewer 的执行结果，也没有给出全体 a5 功能或公开部署已通过的结论。

规范轴：0 个已确认 P1/P2。需求轴：0 个已确认 P1/P2。两项修复在上述独立反例范围内成立；最终持续存储故障的保守返回与旧文件限制已明确记录。
