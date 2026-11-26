> 公开去标识副本。原始评审结论与失败记录保留；私有工作区路径已替换为占位符。

# Wave 05 UI 独立只读 Review

日期：2026-11-26。

基线：`d9ab1b38fff68e77c88841c050b8c038f52dcdb5`（a4）。比较命令为 `git diff d9ab1b38fff68e77c88841c050b8c038f52dcdb5 -- site/index.html site/styles.css site/app.js site/lab.html`，包含当前工作树 UI 改动。

审阅范围：`site/index.html`、`site/styles.css`、`site/app.js`；另核对 `site/lab.html` 的业务脚本是否保持 a4 字节。已读当前 AGENTS、README、架构约束与相关 UI 源码。未修改 UI、业务脚本或作者测试。

## 结果

发现 **1 个 P2 事件边界问题**：新搜索框的 Escape 处理未区分正在进行的 IME composition，会在收到组合期间的 Escape 事件时清空整个查询。

没有发现其他可在本次允许范围内复现的实质交互错误。独立 Node 检查确认了查询与四种筛选组合、两个 tablist 的键盘边界、复制操作的延迟拒绝及 Range 异常收尾。这里的通过只针对明确列出的源码/合成事件检查，不是浏览器、实际剪贴板、Windows IME、响应式布局或辅助技术验收。

## F1 — P2：组合输入期间的 Escape 会清掉已有搜索

**位置：** `site/app.js:134-139`，新加入的 `search` keydown handler。

```javascript
search.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.preventDefault();
    search.value = "";
    applyEvidenceFilter();
  }
});
```

**触发条件：** 搜索框已有查询，输入法仍处于 composition，浏览器送达的键盘事件为 `key="Escape"` 且 `isComposing=true`。这时 handler 不区分输入法的组合输入事件与应用自己的“清空搜索”快捷键。

**独立复现：** 从当前 HTML 读取真实元素信息及卡片文本，在独立编写的 Node VM DOM/event 模型中执行完整、未经修改的 `site/app.js`。输入 `MCP 终`，派发 `key="Escape", isComposing=true, keyCode=229`：

```json
{
  "before": "MCP 终",
  "after": "",
  "preventDefault": true,
  "isComposing": true,
  "keyCode": 229
}
```

**影响：** 一旦收到上述事件，应用会移除已有查询、改变筛选结果，并阻止该键的默认处理。对于中文页面的搜索框，应把正在组合的输入交给输入法处理，再在普通 Escape 时提供清空功能。

**最小修复建议：** 在清空逻辑之前忽略 `event.isComposing`；如需兼容以 composition keyCode 表达的事件，同时保留 `event.keyCode === 229` 的防护。正常、非 composition 的 Escape 仍清空查询并保留当前证据分类。

```javascript
if (event.isComposing || event.keyCode === 229) return;
```

加一条含已有查询的组合事件回归，并保留正常 Escape 用例即可。无需引入输入法状态库或更改搜索算法。

**复现限制：** 这证明当前 handler 对上述事件的确定行为。没有启动真实浏览器或 Windows 输入法；不能据此声称所有 IME 都会产生同样的键盘事件顺序。当前有效的 origin/file transport 拒绝保持有效，本审阅未尝试其他渲染入口。

下面是可独立执行的缩短反例，直接使用源码中的原 handler：

```javascript
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("site/app.js", "utf8");
const begin = source.indexOf('search.addEventListener("keydown"');
const end = source.indexOf('clearSearch.addEventListener', begin);
let listener;
const search = {
  value: "MCP 终",
  addEventListener(type, fn) { listener = fn; }
};
vm.runInNewContext(source.slice(begin, end), {
  search,
  applyEvidenceFilter() {}
});
let prevented = false;
listener({
  key: "Escape", isComposing: true, keyCode: 229,
  preventDefault() { prevented = true; }
});
console.log({ value: search.value, prevented });
```

## 独立检查结果

不是重跑或复述作者的 `wave5-ui-logic-check.cjs`。本审阅另外从当前 HTML 提取实际卡片、tab 分组、ID 和复制目标，构建独立 Node VM 对象，使用人工列出的预期卡片索引及事件序列执行原 `app.js`。

| 检查 | 结果与边界 |
|---|---|
| 4 种分类 × 8 种查询 | 32 组全部符合预期；覆盖空串、MCP、全角 `ＭＣＰ　ＳＤＫ`、反向词序 `SDK MCP`、中文“终端”、OMP、纯空白及 HTML 样式字符串。分类与多词查询共同生效。 |
| 清空和重置 | 清空保留分类并把焦点交回输入框；空结果重置恢复全部 8 张卡片并交回焦点。 |
| Tabs 键盘边界 | 两组共 7 个 tabs，对每个起点分别执行 Left、Right、Home、End，共 28 组；`aria-selected`、`tabIndex`、对应 panel 的 `hidden` 与目标焦点一致，另一 tablist 不受影响。 |
| 复制的延迟拒绝 | Promise pending 时同按钮不二次写入；延迟拒绝后走选择回退，`disabled` 和 `aria-busy` 均恢复。 |
| 选择回退的异常 | `getSelection=null`、创建 Range 失败、选择节点失败、清除 ranges 失败及加入 range 失败，均显示复制失败并恢复 busy 状态。 |
| 复制定时器 | 下一次复制 pending 时旧 reset 已移除；新操作结束后只保留一个 reset，旧 timer 不会覆盖当前反馈。 |
| JavaScript 语法 | `node --check site/app.js` 退出 0。 |
| HTML ID | 独立 HTMLParser inventory 未发现重复 ID。 |
| Lab 业务脚本 | 当前 `<script>` 内容与 a4 完全逐字节相同，SHA-256 为 `f8028b0cc3768dbc300685aac89d8001e4034237afdccf6d5390a611e98ede70`。这不证明视觉修改已经在浏览器验收。 |

未把上述子案例数当成独立用户流程或完整测试套件数量。Node 检查脚本退出 0，F1 作为明确记录的反例输出，而不是被包装成通过项。

## Standards 轴

未发现新增远程脚本、后台网络请求或设备控制入口；代码仍使用 `textContent` 展示计数/反馈，搜索字符串没有进入 HTML 执行位置。既有宿主拒绝、历史失败和当前证据范围的说明仍在。

源码中的 `[hidden]{display:none!important}` 与无 JavaScript 的面板展开规则有明确的优先级；新搜索工具条和筛选控件属于 `.enhancement-only`。静态检查没有发现筛选隐藏被新卡片布局覆盖、两个 tablist 相互串联、或引用目标缺失的问题。这里没有宣称完成屏幕阅读器或 WCAG 全面审计。

没有把压行、命名或个人视觉偏好列为缺陷；没有额外的明确仓库规范违反项。

## Spec 轴

新增本地搜索与四分类组合、清空/重置、复制异常反馈和现代化布局的源码改动已经存在；F1 是与中文输入使用场景相关、建议修复的交互边界。

页面明确标出流程示意、a4 实测、历史证据和 BLOCKED，没有将本轮静态/Node 检查冒充 a5 浏览器成功。当前版本标签与发布 URL 仍由主执行者按实际发布结果更新，这是已经说明的后续工作，本报告不重复列作 UI 作者缺陷。

## 审阅快照与验证限度

运行环境：Linux，Python 3.12.14，Node v24.22.3。

| 文件 | 审阅时 SHA-256 |
|---|---|
| `site/index.html` | `170466ca0f06e97094fbe5241f105acdda1739192ef81371eee8b7c21bf5bf0d` |
| `site/styles.css` | `89dcb35596935c4823c5839ea07d6d3b08c68ea43685d57ac394dc7f9203800a` |
| `site/app.js` | `31a5e9e7d67b397161e29b90b8497268438667b815d81c8e3929212dfb8982a9` |
| `site/lab.html` | `8c36ffdd578176c19cb710e8da8b7f08cfc54931f1910c44655322aad239cc49` |

没有使用浏览器、Playwright、截图、联网、Windows、HMC 或模型调用，也没有寻找替代渲染路线。未安装依赖。当前环境没有完整 CSS parser，本审阅对 CSS 采取源码规则检查；未证明断点实际布局、字体度量、视觉效果、真实剪贴板许可对话框、辅助技术播报或浏览器间一致性。

主执行者后续更新标签/链接或修复 F1 后，需要按实际修改核对；本报告仅针对以上快照。

## F1 修复后的定点独立复验（追加，2026-11-26）

主执行者在原 Escape handler 最前加入 composition guard：

```javascript
// Escape belongs to the IME while a composition is in progress.
if (event.isComposing || event.keyCode === 229) return;
```

本审阅者重新读取修改后的 `site/app.js`，仅抽取原 `applyEvidenceFilter()` 与搜索框 keydown handler，在独立 Node VM 中执行以下三个指定事件分支。每个案例使用新建的状态，初始查询均为 `MCP 终`，证据分类均为 `contract`；同时核对分类按钮的 `aria-pressed` 和 source/contract 两张合成卡片的 `hidden`。

| 事件 | 查询结果 | `preventDefault()` | 分类与卡片状态 | 判定 |
|---|---|---|---|---|
| `key="Escape", isComposing=true, keyCode=27` | 保留 `MCP 终` | 未调用 | 保留 `contract`；source 隐藏、contract 显示 | 通过 |
| `key="Escape", isComposing=false, keyCode=229` | 保留 `MCP 终` | 未调用 | 保留 `contract`；source 隐藏、contract 显示 | 通过 |
| `key="Escape", isComposing=false, keyCode=27` | 清空为 `""` | 已调用 | 保留 `contract`；source 隐藏、contract 显示 | 通过 |

**定点结果：3/3 通过，Node 进程退出 0。F1 在这三个源码事件分支中的缺陷已修复。** 没有重新运行整轮 UI 检查，没有修改 UI，也没有执行真实浏览器、输入法、剪贴板或渲染测试；原报告中的验证限制继续有效。

复验环境：Linux / Node v24.22.3。修复后的 `site/app.js` SHA-256：

```text
ee3f0eacdaae8338b84858d51e93b4748b333a82141298e485db1665bc25b651
```

原失败事件、原建议及上文四个审阅快照哈希全部保留，没有用修复后结果改写历史证据。此追加记录可作为主执行者冻结当前 JS 的定点独立复验依据；不扩大为真实浏览器验收或其他文件的重新审核。
