# Wave 05 Windows 安装器 Scripts 目录归属检查

## 结论

确认 **1 项具体 P2：已拥有 `.venv` 的 `Scripts` 目录链接未被安装器拒绝**。这是 a4 已存在的缺口，不是本轮 Linux 修复引入的回归。主线裁决后已做最小修复，两个实现/测试文件已停止编辑并冻结；本地验证完成，真实 Windows junction 回归待主线执行。

本次只检查这个目录归属问题，没有扩展到其他安装器安全审计。

## 源码可证的路径

原 `scripts/install.ps1` 的 guard 检查安装根、`.venv`、marker、配置和 tools，但没有检查 `.venv\Scripts`。当 `.venv` 是普通目录且 `.rdc-install.json` 的 project/install_root 匹配时，安装器跳过 venv 创建，随后直接调用 `.venv\Scripts\python.exe -m pip install ...`。

因此把 `Scripts` 设置为指向另一个目录的 junction 或目录 symlink，不会命中原 guard；父目录 `.venv` 的属性不会代表它的子目录是否为 reparse point。后续解释器路径经过这个未检查的目录，违背安装器自身的目录归属边界。

**证据界限：** 本地是 Linux，未发现 `pwsh` 或 `powershell`。本次确认的是源码检查遗漏及其可达调用位置，没有宣称实际在 Windows 启动过外部解释器。按照主线裁决，验证 fixture 的外部目标保持为空，不为证明问题而执行未知解释器或 pip。

## 最小修复与正常 venv

仅在现有 guard 列表加入 `(Join-Path $venv 'Scripts')`，复用既有 `ReparsePoint` 拒绝逻辑。`python.exe` 调用方式和其他安装行为未改。

拒绝的是 `Scripts` **目录**的重定向，不拒绝 `python.exe` 文件。只读检查本地 CPython 3.12.14 的 `venv.EnvBuilder.ensure_directories()` / `setup_python()` 可见：scripts 路径作为目录创建，Windows 下可在该目录放置复制或链接的解释器文件。因此该修复保留正常解释器文件链接/venv redirector 路线。这里是标准库源码核对，不是 Windows venv 实测声明。

## 单个 Windows 回归 fixture

`tests/test_install.py` 新增 `WindowsInterpreterDirectoryTests.test_linked_scripts_directory_is_refused_before_interpreter_invocation`：

- 自有临时源码目录内复制安装脚本，创建占位 pyproject、匹配 marker 和真实 `.venv` 目录。
- 另建自有空目录，以已有 `cmd.exe /d /c mklink /J` 创建 `.venv\Scripts` junction；目标中没有 `python.exe`。
- 使用已有 `pwsh -NoProfile -NonInteractive -File ... -Python sys.executable` 执行当前安装器；不使用 `ExecutionPolicy Bypass`。
- 要求非零退出且包含 `Linked installation path refused`，同时配置未创建、marker 字节未改、外部目标仍为空。旧版即使因找不到解释器而非零退出，也不能满足具名拒绝断言。
- junction 命令限时 10 秒，安装器限时 20 秒；清理时仅移除自有 junction，再由临时目录生命周期清理自有文件。
- 非 Windows 明确 skip；缺少 pwsh/cmd.exe 或无法创建 junction 时明确 skip，不把它算通过。

fixture 不安装包、不连接网络、不写系统配置。初始 `-Python` 只执行版本检查；由于 foreign 目录为空，guard 失效的旧脚本也没有 pip 可执行路线。

## 已执行验证与冻结结果

```bash
python -B -m unittest discover -s tests -p test_install.py -v
```

Linux / Python 3.12.14：**6 passed，1 Windows skip**，没有真实 Windows 通过声明。Python 测试文件 AST 解析、`git diff --check` 通过；静态对照确认 a4 guard 没有 Scripts、补丁 guard 包含 Scripts，解释器调用未改。

主线 Windows 定点命令：

```powershell
python -B -m unittest discover -s tests -p test_install.py -k linked_scripts -v
```

| 冻结文件 | SHA-256 |
|---|---|
| `scripts/install.ps1` | `ec2fbb91ae2012ea6ac9c6c8f5c7be20e12d2c331c0950f77676ea7978976433` |
| `tests/test_install.py` | `ea789ce030910fab4f641f03e996926bd13889268c26f6df69693cef63d8e72f` |

源码修复完成；真实 Windows 回归尚未执行于本审查进程，结果由主线补充。

## 主线追加：真实 Windows 定点回归

2026-11-26，主线在 Windows / Python 3.14.7 运行上述 `-k linked_scripts` 命令：**1 test，0.740 秒，OK，exit 0，未 skip**。传入的两个源码文件 SHA-256 与上表一致。空目录 junction 被具名拒绝，marker 保留、config 未生成；没有执行 pip 或创建外部解释器。这关闭了本项发布 gate，不扩大为完整安装器或任意 reparse 攻击防护保证。
