# RDC Operator Kit 0.1.0a3 独立只读 Review

日期：2026-11-26。审阅基线：`4930cd026f29ac61da88992712f002fc4b6943a4`（`baseline-0.1.0a3`）。

审阅源码位于 `<project>`。这是对恢复后的 a3 快照的审阅，不声称构造了相对更早版本的差异。开始时工作树干净。已完整阅读 `AGENTS.md`、`README.md`、`docs/ARCHITECTURE.zh-CN.md`、`docs/REVIEW-WAVE3.zh-CN.md` 及相关源码和测试。

独立 review 阶段没有修改项目文件，没有访问 Windows 远端、浏览器或网络。以下复现仅使用 Linux / Python 3.12.14、隔离的 `TemporaryDirectory` 和显式标记的假 Playwright 对象；它们验证实现分支，不构成真实 GUI/Browser 验收。没有重复运行已由主执行者负责的完整核心套件。

## 结果

确认 2 个具体缺陷：1 个发行包隐私排除缺口、1 个网页 smoke 失败归档与资源收尾缺口。没有发现足够证据支持修改现有 `foreground_not_target` 安全 guard 或放宽浏览器证据的来源限制。

## F1 — P1：允许目录内的本地配置和交付运行文件会进入源码发行包

**位置：** `scripts/build_release.py:24-28,45-54`（a3 基线行号）。

**触发条件：** 开发者在 `docs/`、`site/`、`scripts/` 等允许树中留下已知私有运行文件，例如 `docs/config.local.json`。这些名字在项目 `.gitignore` 中已明确排除，但发行构建器不使用 Git 跟踪清单，也没有对文件名应用对应排除。

`source_files()` 只剪枝 `EXCLUDED_PARTS` 中的名字和 `.egg-info`，随后按 `.json`、`.py` 等扩展名收集文件。结果是 `.gitignore` 忽略的 `config.local.json`、`.rdc-install.json`、`.rdc-delivery.json`、`delivery-payload.json`、`receive-source.py` 仍可能被打包，只要位于一个允许目录下。

**已执行的最小复现：**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from scripts import build_release

with TemporaryDirectory() as tmp:
    root = Path(tmp)
    for relative in (
        "docs/config.local.json",
        "site/.rdc-install.json",
        "site/delivery-payload.json",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"private":"SYNTHETIC_ONLY"}')
    with patch.object(build_release, "ROOT", root):
        print([name for name, _ in build_release.source_files()])
```

实际输出：

```text
['docs/config.local.json', 'site/.rdc-install.json', 'site/delivery-payload.json']
```

**影响：** 构建 ZIP/TAR 会将这些文件的字节及其 manifest 项收入发行产物。后续人工分享或发布时可能带出本地配置、设备标识或交付记录。本轮没有在恢复的 99 文件源包中发现此类私有文件，也没有发生公开发布；复现内容全部是合成标记，不能据此声称已有数据泄漏。

**最小修复：** 为已知运行文件名建立显式的全树排除规则，在对条目做 `lstat` 或递归之前应用；至少覆盖项目 `.gitignore` 中这些明确的私有/交付文件名。保持允许的示例配置（如 `examples/config.example.json`）正常入包。加一个使用隔离 `ROOT` 的回归检查，同时覆盖顶层和允许子目录里的这些文件，并检查 `SOURCE-MANIFEST.json` 中没有对应路径。该修复不必声称能发现任意文件内容中的秘密。

**Standards 依据：** `AGENTS.md` 的 Local scope and publication 明确要求 `config.local.json`、运行状态、设备/账号 ID、凭据和原始私有内容不进入 commit 或 release bundle；`.gitignore` 给出可直接落实的文件名证据。

**Spec 关系：** 这是交付边界缺陷，与鼠标操作能力本身无直接关系；应在再次生成可分享发行包前解决。

## F2 — P2：网页 smoke 的启动、初始化或截图收尾失败会丢失 summary

**位置：** `scripts/smoke_site.py:12-24,63-66`（a3 基线行号）。

**触发条件：** 以下任一真实环境故障即可进入没有归档的路径：

- `pw.chromium.launch()` 抛出异常，例如浏览器缺失或启动失败；
- `browser.new_context()`、`ctx.route()`、`ctx.new_page()` 等 case 初始化抛出异常；这些语句位于 case 的 `try` 之外；
- 最后两个用于保存截图的 context、导航或 `page.screenshot()` 失败；这一段完全不经过 `case()`；
- `ctx.close()` 或 `browser.close()` 抛出异常。

`summary.json` 只在这些操作全部返回后写一次。即使前面已经积累了 pass/fail 检查，后续截图失败也会使整轮没有机器可读总结。遇到初始化或尾部截图异常时，显式 `context.close()` / `browser.close()` 也不会全部执行。

**本地合成复现结果：** 将 `playwright.sync_api` 替换为没有浏览器/网络能力的 Python stub，直接调用未修改的 `scripts/smoke_site.py.main()`，输出目录每次独立：

| 注入的故障位置 | `summary.json` | 已创建 / 显式关闭 contexts | 显式调用 `browser.close()` | Playwright 管理器 `__exit__` |
|---|---|---:|---|---|
| `chromium.launch` | 不存在 | 0 / 0 | 否 | 是 |
| 第一次 `ctx.route` | 不存在 | 1 / 0 | 否 | 是 |
| 每个 case 导航先失败，随后最终截图导航也失败 | 不存在 | 14 / 13 | 否 | 是 |

第三个场景的 13 次 case 失败本来已经被 `checks` 收集，但第 14 次导航发生在最终截图段，异常逸出后未将它们归档。实际 Playwright 驱动是否在连接关闭时最终回收进程，不在 stub 能证明的范围内；这里不据此断言真实浏览器一定泄漏。

**最小自包含复现（context 初始化失败路径）：**

```python
import importlib.util
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

events = []

class Context:
    def route(self, *args):
        raise RuntimeError("SYNTHETIC route setup failure")
    def close(self):
        events.append("context.close")

class Browser:
    version = "SYNTHETIC"
    def new_context(self, **kwargs):
        return Context()
    def close(self):
        events.append("browser.close")

class Manager:
    def __enter__(self):
        return SimpleNamespace(
            chromium=SimpleNamespace(launch=lambda **kwargs: Browser()))
    def __exit__(self, *args):
        events.append("playwright.exit")

fake = ModuleType("playwright.sync_api")
fake.sync_playwright = Manager
fake.expect = lambda value: None
spec = importlib.util.spec_from_file_location("review_smoke", "scripts/smoke_site.py")
module = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"playwright.sync_api": fake}):
    spec.loader.exec_module(module)

with TemporaryDirectory() as tmp:
    output = Path(tmp) / "out"
    with patch.object(sys, "argv", ["smoke_site.py", "--output", str(output)]):
        try:
            module.main()
        except RuntimeError as error:
            print(error)
    print("summary", (output / "summary.json").exists())
    print("cleanup", events)
```

实际结果为 `summary False`、`cleanup ['playwright.exit']`。

**影响：** 全面 smoke 在最需要诊断的失败环境中留下不完整产物，失去此前已执行检查、失败阶段及清理状态，主执行者无法可靠区分“未启动”“部分完成”“最后截图失败”。下次也不能把目录存在误当成验收完成。

**最小修复：** 让浏览器生命周期有外层 `try/finally`；让 context 的创建后配置、case 和截图都在受控的异常/清理边界内。将 startup/case/screenshot/cleanup 的错误写成结构化项，保留已完成的 checks；无论启动和运行成功与否，都通过最终归档路径写 summary。清理异常应追加记录，不应遮蔽原始失败。保留管理员拒绝的停止语义和 `not_run_after_refusal`，不得为了补截图而继续导航。必要时浏览器版本允许 `null`，明确未启动。对本报告的三个故障注入场景添加小范围回归检查。

**Standards 依据：** `AGENTS.md` 要求验证报告区分实际命令、passes、failures、skips 与限制，并且仅清理本次确立归属的资源；现有最终单点归档路径无法在上述故障时履行可追溯的验证报告要求。

**Spec 依据：** Setukou 当前要求可靠 harness 与全面 smoke；前面已经执行的检查不应因为附加截图失败全部失去报告。

## Standards 轴

2 个需修复项：F1 为明确的私有运行数据排除缺口；F2 为失败验证记录与显式收尾路径缺口。最高严重性为 F1 / P1。没有把命名、格式、压行或主观 code smell 当成额外缺陷。

## Spec 轴

1 个可复现的当前需求缺陷：F2 阻碍可靠 harness 和失败 smoke 诊断。F1 属于交付边界，另列 Standards，不虚构鼠标功能需求。

目前桌面 selector click、官方 Browser click 的真实验收应由主执行者记录；这个独立分支没有执行也不冒领这些结果。离线 `verified_fixture` 仍不等于真实浏览器成功。

## 已检查但未据此提出修复的范围

- `common.py` 的重复 key、非有限数字/溢出浮点、普通文件类型及大小边界：已审阅源码和 a3 回归用例，没有找到本轮足够证据支持的新缺陷。明确不把同权限恶意替换文件或所有 TOCTOU 问题包装成 a3 已承诺的保护范围。
- `browser_evidence.py`：审阅完整 schema、请求摘要、页面身份、顺序、witness 和结果状态路径；纯合成声明即使自洽也不认证来源，这是文档明确的设计范围，不是待“修复”的 false positive。检查了 `dispatched=False` 等组合不会得到 `verified_fixture`。
- `adapters.py`：审阅前后台错误映射、目标身份、canonical selector、点击 ack 和动作后状态核对。主执行者已亲自读取 a2 的 `increment-once.receipt`，报告其 `foreground_not_target` 位于 `stderr_json.error.code`，符合当前 `_failed()` 读取路径；我没有亲自读取该远端原件，故将其标为主执行者提供的证据，不为未观察到的 stdout 错误通道提出泛化修改。
- 必须继续保留前台 guard、独立 business witness、请求不确定结果不自动重放、官方 Browser 拒绝不得借 RDC/CDP 绕过等现有约束。

缺陷总数为 2；Standards 2，Spec 1，两个轴有重叠，不相加计数。

## 后续授权修复记录（与上述独立基线结论分开）

主执行者在报告完成后另行授权本分支独占修改 `scripts/build_release.py` 和新增 `tests/test_release_privacy.py`。已完成 F1 的最小修复：全树排除五个已知私有/交付文件名，将 `.pytest_cache` 加入目录剪枝，所有私有名字及 `.egg-info` 判断均用 `casefold()`，并在 `lstat`、递归、读取内容之前排除。未修改 F2、桌面适配器、权限或网络路线。

新增的 2 个测试在修复前均失败，分别实际触发私有文件读取守卫和私有目录遍历守卫；修复后均通过。合法 `examples/config.example.json`、合成 Browser 示例以及研究来源 JSON 的内容保持收入清单。已有 a3 边界回归 5/5 通过，`git diff --check` 通过。

执行命令：

```bash
python -m unittest discover -s tests -p test_release_privacy.py -v
python -m unittest discover -s tests -p test_wave3_review.py -v
git diff --check
```

环境仍为 Linux / Python 3.12.14；新增测试 2 通过、0 失败、0 跳过，既有相关测试 5 通过、0 失败、0 跳过。这是定向本地回归，不冒充 Windows 或真实 Browser 验收。修复后的独立复核由主执行者安排，当前报告不是作者对自己补丁的独立批准。
