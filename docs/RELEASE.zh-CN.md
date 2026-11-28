# a6 安装与发布检查点

状态日期：2026-11-28（Asia/Tokyo）。`0.1.0a6` 是当前 candidate；已安装包验证已完成，公开 CI、Release 与 Pages 仍为 **pending**。完整结果见[第六轮报告](REVIEW-WAVE6.zh-CN.md)。下面的 a5 章节保留真实已发布 tag、资产、校验和及历史命令，不能直接替换版本字符串便声称 a6 已发布。

| a6 交付层 | 当前结果 | 后续记录要求 |
|---|---|---|
| 冻结源码 | 已从公开 main `54131f00c3b942797809a1b90424e845ef56fe13` 逐 SHA-256 对齐 139 个基线文件；最终运行时本地检查点 `06e0e21` | 本地 commit 不充当公开 tag；最终源码／文档同步另记 |
| 源码验证 | Linux core 225／221 pass／4 skip；Windows 225／212 pass／13 skip；两系统恢复 smoke 各 17/17 | 保留平台、Python、原失败和 skip；不是一次九项 GUI 集成 suite |
| 候选 wheel | 51,757 字节；SHA-256 `f84ae08e8e6625a14ca84fe2b4a154a58ee4829c5a3866dc9bb23656b2f2770e` | 此哈希核对本轮实际安装字节；公开资产仍需上传后下载回读 |
| Windows 安装 | 两个已有环境 offline／no-deps 从 a5 升 a6；旧包备份，各 12 模块匹配 wheel，非 Kit 依赖及 config 哈希不变 | 实际 `-I` site-packages 导入；两个 `rdc-kit.exe` 版本 a6；源码主副本同步单独记录 |
| 已安装恢复 | Windows 两环境各 17/17，Linux 新隔离 venv 同一 wheel 17/17 | Windows 每次六个 guarded resume、零副作用；不是 RDC 重登实验 |
| 已安装现代 MCP | SDK 2.3.0，真正 stdio 协议 `2026-07-28`，17 checks passed | 三工具、双通道、unknown、正常退出与记录未变；与恢复 17 项分开 |
| 公开源码／CI | pending | 实际 commit／run、每个 job 的测试数、skip、失败与最终结果 |
| a6 tag／Release | pending | 精确固定 tag、时间、资产名／大小／SHA-256 与下载回读 |
| a6 Pages | pending | 精确 commit／run、build/deploy 与 page URL；不增加 live UI 验收 |

本轮新增的恢复材料过滤会剪除 `checkpoints` 目录，并排除 `.recovery-marker.json`、`recovery-checkpoint.local.json`、`recovery-context.local.json`、`recovery-handoff.local.md`。公开 example JSON 保留，归档和独立 HTML 使用同一过滤快照；七项定向隐私测试通过。这是命名与引用防护，不是通用秘密扫描；不得将原始账号、设备路由、token、state 或聊天／UI 内容加入发行快照。

当前源码的复验入口：

```bash
python -B -m unittest discover -s tests -v
python -I scripts/smoke_recovery.py --output-dir evidence/recovery-source-new
```

恢复 smoke 会创建自有合成子进程与证据；它不修改账号或连接。`resume` 的命令行只读示例使用 `python -B`，避免导入缓存写入。a5 安装不会因为读取新文档而具备 checkpoint／resume；旧版本继续人工核对，升级须按实际任务授权处理。可操作步骤见[Agent 指南](AGENT-GUIDE.zh-CN.md)和[恢复规格](RESUME-SPEC.zh-CN.md)。

# 历史：a5 发布、安装与 GitHub Pages

版本：`0.1.0a5`，已发布的 alpha。状态日期：2026-11-26（Asia/Tokyo）。

**[下载 v0.1.0a5 Release](https://github.com/dwgx/RDC-Operator-Kit/releases/tag/v0.1.0a5) · [项目网站](https://dwgx.github.io/RDC-Operator-Kit/) · [公开源码仓库](https://github.com/dwgx/RDC-Operator-Kit)**

Release 已于 **2026-11-26 17:31:53 JST（08:31:53 UTC）** 发布，tag `v0.1.0a5` 固定到 `27d367a9698c381d90986c8640d506b24d84ddd9`；九项上传资产均已实际下载回读，SHA-256 一致。发行提交的 [CI run 45782996129](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45782996129) 六个 job 全部成功，[Pages run 45783289213](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45783289213) build／deploy 也在同一提交成功。完整资产清单与历史 checkpoint 见 [第五轮报告第 12 节](REVIEW-WAVE5.zh-CN.md#12-实际公开发行与-pages-部署)。直接安装请从第 4 节开始；前面三节保留维护者的冻结、构建与发行流程。

## 1. 冻结可以公开的源码

本版归档与 tag 固定在 `27d367a`。随后 `main` 只同步文档／页面中的发布回执，不移动 tag 或替换资产；需要检查发行源码时使用 `v0.1.0a5`，不要把后续 main 文档字节视为原归档内容。随附报告保留冻结时的发布前 checkpoint，当前回执在第五轮报告第 12 节追加。

仅从审阅过的源码快照建立发布 checkout。不要把正在使用的 Windows 项目目录整体 `git add`：其中可能含配置、环境、工具与私有证据。公开树包括程序、安装脚本、文档、Skill、合成夹具、测试与静态网站；排除 `config.local.json`、`.venv/`、`.venv-mcp/`、`.rdc-state/`、`tools/`、`evidence/`、设备／账户标识、令牌、原始终端和 UI 内容。

冻结前完成以下具体核对：

1. Python 包版本、当前 README、网站当前标签、安装说明和 release tag 对应 `0.1.0a5`；历史章节保留自己的 a1–a4 标签。
2. `site/docs/` 与仓库 `docs/` 的发布文档同步，链接与锚点可解析；不是仅复制根目录的部分 Markdown。
3. 源码、打包过滤与报告中的证据范围一致。原失败回执不改写；测试数保留平台、skip 和具体快照。
4. 审阅 staged 文件清单及内容，确认只有本项目批准公开的文件。私有运行目录不因被 `.gitignore` 忽略就获得完整秘密扫描保证。

本轮初始 Linux core 177/177、一次 Windows 九顶层 case 全部 passed 保留为历史 checkpoint。MCP smoke 判定缺口和随后 CI 暴露的 Windows 路径问题均已修复。最新本地 core 为 184 run／181 pass／3 skip，自有 Windows core 为 184 run／173 pass／11 skip，真实 MCP 为 72/72；GitHub CI 的独立分平台结果见第 5 节。这些结果不能互相拼接为一次完整安装包验收。

## 2. 本地验收与构建

在冻结源码目录执行核心回归：

```bash
python -m unittest discover -s tests -v
```

具有独立 SDK 2.3.0 环境时，用新的输出目录执行受影响的 MCP gate；Windows 示例：

```powershell
& .\.venv-mcp\Scripts\python.exe scripts\smoke_mcp.py --mode both --output-dir evidence\mcp-release-a5-unique
```

Linux 对应解释器是 `.venv-mcp/bin/python`。不能把 SmartCLI 的 MCP 1.x 环境当成此入口的 SDK 2.3.0。真实 Windows 桌面／终端验收按 [Windows 操控指南](WINDOWS-CONTROL.zh-CN.md) 使用自己拥有的夹具；不要为了重复绿灯重新执行不受本次改动影响的任务。

选择一个**尚不存在**的输出目录，然后构建：

```bash
python scripts/build_release.py --output dist/a5-candidate-001
```

构建器从同一经过过滤的源码字节快照生成：

| 产物 | 作用 |
|---|---|
| `RDC-Operator-Kit-0.1.0a5.zip` | Windows 优先的完整源码包 |
| `RDC-Operator-Kit-0.1.0a5.tar.gz` | 同一源码的 TAR 归档 |
| `RDC-Operator-Kit-preview.html` | 独立项目说明预览；不是远程电脑控制台 |
| `SOURCE-MANIFEST.json` | 本次源码文件、字节数与 SHA-256 |
| `SHA256SUMS.txt` | 上述生成产物的实际校验和 |

以构建脚本的实际输出为准，不能沿用 a4 文件数或摘要。脚本允许写入已有输出目录，因此维护者必须选择新的候选目录，保留上一次失败或交付的字节。解包后逐文件比较 manifest，并核对 ZIP 与 TAR 中的源码内容一致。

构建器使用排序后的相对 POSIX 路径、固定归档时间与模式；同一源码 manifest 应一致，但不同 Python/zlib 实现不保证压缩字节相同。a2 曾有两种压缩实现生成不同归档却拥有相同源码的历史，这不能改写成当前版本已跨运行时重复构建。

### 可选 wheel

源码构建器**不会生成 wheel**。在已准备好 `setuptools>=68` 和所需构建工具的专用环境中，可另外构建：

```bash
python -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir dist/a5-candidate-001 .
```

该命令缺少构建条件时应失败，不会联网补装构建依赖。实际 wheel 应为 `rdc_operator_kit-0.1.0a5-py3-none-any.whl`。核对 wheel 内包版本和运行模块字节与冻结源码相符；在归属明确的已有环境中离线安装后，另外用隔离导入核对真实 `site-packages` 和版本。源码 smoke 与 installed-package 核对分别报告。

两个自有 Windows 环境先前从 a4 升至 a5 的记录保留为 **CI 修复前 checkpoint**。随后已安装包含修复的最终 wheel：44,645 字节，SHA-256 为 `24633b51a6cb3e72a4896fb9accf3d3125f4f9f87a2aba659ca482aa5ebcbc8b`。本次 a5→a5 仅更新 Kit；每个环境通过 `-I` 隔离导入核对 11 个实际 site-packages 模块与修后源码完全一致，其他 distribution 版本和配置哈希未变，备份保留。

实际 installed smoke 也已完成：两个 `rdc-kit.exe --version` 均返回 a5／exit 0；一个 `-I` 启动的 installed 现代 MCP 会话协商 `2026-07-28`，保存 unknown、双通道、记录未变与正常 worker 返回均核对，17 条断言全部 true。这一有限安装后验证独立于源码 72 项和 CI，不声称 legacy 或 GUI 重跑。具体回执见第五轮报告第 11 节。

如果额外附 wheel、单独报告或静态 audit JSON，维护者须把它们的实际 SHA-256 加入本批校验清单并再次核对唯一文件名；源构建器原始 checksum 不自动覆盖这些后来附加的文件。wheel 只安装 Kit，不更新 SmartCLI、SDK、winapp、Skill、测试夹具或源码目录。[离线升级与校验步骤](README.zh-CN.md#已有-windows-环境的离线-wheel-升级)

## 3. 推送、CI 与预发布

目标仓库已存在，`main` 已收到首次源码、CI 修复与发行提交，`v0.1.0a5` 已公开。后续交付从隔离发布 checkout 正常 push；检查 `origin` 精确指向 `https://github.com/dwgx/RDC-Operator-Kit.git`，并确认提交内容属于批准公开的范围。不使用 force、不上传运行目录、不输出令牌。

CI 随 push／pull request／手动触发。本版发行提交 `27d367a` 的六个 job 已通过，tag、源码快照与资产的对应关系已核验。若之后发布其他版本，应确认其实际目标 commit 与最终发行快照、校验文件一致，不能沿用另一 commit 的绿灯。已存在 tag 应先检查身份，不删除或重写它来覆盖历史。

以下命令保留本版创建预发布草稿的流程示例；**`v0.1.0a5` 已发布，不应对它重新执行 create 或覆盖上传**。维护后续版本时改用新的版本与候选目录，先核验报告和固定 tag，再上传明确列出的资产：

```powershell
gh release create v0.1.0a5 `
  --repo dwgx/RDC-Operator-Kit `
  --verify-tag --prerelease --draft `
  --title 'RDC Operator Kit 0.1.0a5' `
  --notes-file docs/REVIEW-WAVE5.zh-CN.md `
  dist/a5-candidate-001/RDC-Operator-Kit-0.1.0a5.zip `
  dist/a5-candidate-001/RDC-Operator-Kit-0.1.0a5.tar.gz `
  dist/a5-candidate-001/RDC-Operator-Kit-preview.html `
  dist/a5-candidate-001/SOURCE-MANIFEST.json `
  dist/a5-candidate-001/SHA256SUMS.txt
```

只有实际构建并校验的 wheel 才作为额外资产上传。发布草稿前检查目标 tag、资产名、大小、下载字节及校验和。本版从草稿转为公开 Release 的命令记录如下，当前无需重复执行：

```powershell
gh release edit v0.1.0a5 --repo dwgx/RDC-Operator-Kit --draft=false
```

这是已有发布授权下的执行流程，不是再次请求所有者确认。若实际工具或服务拒绝操作，则保留具体错误与未完成状态。已发布版本出现问题时保留原 tag／资产证据，发布更正版本；不要以覆盖下载文件的方式让旧 checksum 失去对应关系。[GitHub CLI Release create](https://cli.github.com/manual/gh_release_create)

## 4. 从 GitHub 安装

**`v0.1.0a5` tag 与 Release 已实际发布，以下固定版本 clone 命令可用。** 该 tag 对应提交 `27d367a9698c381d90986c8640d506b24d84ddd9`；安装前核对 Python、目标目录与已有配置，保留现有工作。

Windows PowerShell，在一个尚未含同名目录的位置：

```powershell
git clone --branch v0.1.0a5 --single-branch https://github.com/dwgx/RDC-Operator-Kit.git RDC-Operator-Kit
if ($LASTEXITCODE -ne 0) { throw 'Source download failed; do not continue installation.' }
Set-Location RDC-Operator-Kit
.\scripts\install.ps1 -WithTerminal -WithDesktop
if ($LASTEXITCODE -ne 0) { throw 'Installation failed; inspect the preserved output.' }
& .\.venv\Scripts\python.exe -m rdc_operator --config config.local.json doctor
```

Linux：

```bash
git clone --branch v0.1.0a5 --single-branch https://github.com/dwgx/RDC-Operator-Kit.git RDC-Operator-Kit && cd RDC-Operator-Kit && bash scripts/install.sh --with-terminal
```

随后运行 `.venv/bin/python -m rdc_operator --config config.local.json doctor`。Linux 支持核心与终端路线，Windows UIA 不适用；HMC 当前没有真机验收结果。完整前提、配置与诊断见 [中文指南](README.zh-CN.md)。

也可以下载 [源码 ZIP](https://github.com/dwgx/RDC-Operator-Kit/releases/download/v0.1.0a5/RDC-Operator-Kit-0.1.0a5.zip) 和 [SHA256SUMS.txt](https://github.com/dwgx/RDC-Operator-Kit/releases/download/v0.1.0a5/SHA256SUMS.txt)，确认文件摘要匹配再解压，在解压后的源码目录执行相同安装脚本。SHA-256 证明下载字节与该清单一致，不代替来源与 tag 核验。当前没有远程 `curl | sh`／`iex` 入口，没有自动升级 daemon。

给本地 Agent 使用时，提供上述真实仓库、固定 tag 与 README，让它先核对本机 Python、目标目录和原有配置，再按安装步骤执行。给 ChatGPT 使用仍需要宿主可用的 RDC／Browser 工具与设备连接；导入仓库中的 Skill 不会自动配对电脑或建立远程 MCP endpoint。

## 5. GitHub CI 的实际范围

[`ci.yml`](../.github/workflows/ci.yml) 使用 Ubuntu／Windows × Python 3.10／3.13 的四个核心 jobs，不安装可选依赖；依赖 Pydantic 的检查在未安装对应版本时明确 skip。另有 Ubuntu／Windows × Python 3.13 的两个独立 MCP jobs，创建 `.venv-mcp`、安装 `.[mcp]`、运行 modern／legacy 真实 stdio。它们不安装 SmartCLI，不连接个人设备，不运行桌面 GUI或真实模型。

核心 jobs 的 timeout 为 15 分钟，MCP jobs 为 10 分钟；矩阵 `fail-fast: false`。权限为 `contents: read`，checkout 不保留 credentials。实际 job 数、测试数、skip、失败与运行 URL 从该 commit 的 GitHub 回执读取；工作流存在不代表执行通过。

历史 checkpoint：[首轮 run 45777836079](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45777836079) 两个 Windows core job 均以 182 run／11 failures／10 errors／7 skip 失败，其他四个 job 通过；修复提交 `a880144` 的 [run 45780615916](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45780615916) 六个 job 全部 success。后者 Windows core 两组各 184 run／177 pass／7 skip，Ubuntu core 两组各 184 run／179 pass／5 skip；可选 Pydantic 模型检查在 core 中明确 skip。两个独立 MCP job 的 modern／legacy 协议均 passed、保存记录未变。原始失败与后续成功分别保留。

最终发行提交 `27d367a` 又完成 [run 45782996129](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45782996129)，六个 job 均 success：Windows 两组各 184 run／177 pass／7 skip，Ubuntu 两组各 184 run／179 pass／5 skip；两个独立 MCP job 均通过 modern `2026-07-28` 与 legacy `2025-11-25`，保存记录未变。CI 日志未输出逐项 check 数，不采用自有 Windows 的 72 项作为 CI 计数。

Actions 的固定 revision 已通过官方仓库 git-ref lookup 核对，当前 workflow 使用下面的完整 SHA，表中 tag 仅说明核对来源：

| Action | 来源 tag | 当前固定 commit |
|---|---|---|
| `actions/checkout` | `v6` | `d23441a48e516b6c34aea4fa41551a30e30af803` |
| `actions/setup-python` | `v6` | `ece7cb06caefa5fff74198d8649806c4678c61a1` |
| `actions/configure-pages` | `v5` | `983d7736d9b0ae728b81ab479565c72886d7745b` |
| `actions/upload-pages-artifact` | `v4` | `7b1f4a764d45c48632c6b24a0339c27f5614fb0b` |
| `actions/deploy-pages` | `v4` | `d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e` |

固定 Actions 不等于 Python 传递依赖或托管 runner 镜像完全锁定；重现说明应保留实际 Python、SDK 和依赖版本。

## 6. GitHub Pages

`site/` 是无后台接口的静态页面，不含本机控制凭据。发布前同步当前版本、真实仓库／Release 链接和 `site/docs/`；历史失败与策略拒绝仍保留。页面部署与真实浏览器验收分开，不能用另一个 URL 或浏览器表面补做已经被拒绝的交互验证。

目标仓库 Pages 使用 **GitHub Actions**（`build_type: workflow`）。[run 45783289213](https://github.com/dwgx/RDC-Operator-Kit/actions/runs/45783289213) 的 build／deploy 均成功，head 为发行提交 `27d367a9698c381d90986c8640d506b24d84ddd9`；实际网站为 [https://dwgx.github.io/RDC-Operator-Kit/](https://dwgx.github.io/RDC-Operator-Kit/)。后续 main 文档／页面回执同步后，可以针对新提交手动运行部署 workflow，并单独记录该次结果：

```powershell
gh workflow run pages.yml --repo dwgx/RDC-Operator-Kit --ref main
```

[`pages.yml`](../.github/workflows/pages.yml) 只接受手动触发，build 限定默认分支；上传范围仅为 `site/`。deploy 依赖 build，使用 `github-pages` environment；workflow 权限为 `contents: read`、`pages: write`、`id-token: write`，并设置独立并发组防止同时部署。此流程不会创建 MCP 服务或开放远程设备端口。[GitHub Pages 官方工作流说明](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

每次部署后检查准确 run／commit、两个 job 的完成状态，以及 `deploy-pages` 实际返回的 `page_url`。本版已取得发行提交的成功部署回执；这不增加新版 UI、剪贴板或响应式交互的 live browser 通过项，也不改动固定 tag 或 Release 资产。

如需撤回网站，可在 Pages 设置中取消发布；这不删除已公开 git 历史和下载副本。源码、Release 与 Pages 是三个分别记录的发布结果，任何一个完成都不能替代其他两项的真实证据。
