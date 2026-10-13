# 在线体验 · Browser example

[**打开画布，直接动手 / Open the interactive canvas**](https://jiangzl1986-gif.github.io/skill-workbench/)

不用安装、不用登录、不用模型账号。打开后切换右上角 **中文 / English**。

这次试着给「笔记转大纲」加入另一个 Skill 的「证据检查」：

1. 点击画布上的 **进入「大纲设计」内部**，看到已有子模块。
2. 在左侧找到 **证据检查**，点击 **加入**，或拖到画布上。来源标记会随模块保留。
3. 把「主张与依据」右侧的圆点拖到「证据检查」左侧的圆点。也可以在画布下方选择起点、终点，填写交接要求后点击 **连接**。
4. 想改连接，点击线上的 **剪刀**；想换模块，选中后使用右侧的 **替换这个位置**。这些操作只改示例草稿。
5. 点击 **保存草稿** 留在当前浏览器，或 **导出设计** 下载完整 JSON，交给自己的 Agent 评估。

也可以切换 **知识地图** 看来源结构，点击模块的原文按钮核对完整内容、行号与文件哈希。地图虚线表示包含关系，不代表自动推断的执行顺序。

## 这个示例与桌面版有什么区别？

| | 在线示例 | 桌面完整版 |
| --- | --- | --- |
| 如何打开 | 浏览器直接打开 | Windows 安装包或便携包 |
| 来源 | 两套项目自带公开示例，5 份文件 | 导入自己的 Skill 或有权使用的来源 |
| 体验 | 来源地图、子模块组装、拖动、连线、剪线、替换、备注、保存与导出 | 完整本机导入、来源同步及设计工作流 |
| 草稿保存 | 当前浏览器的本地存储，换设备不自动同步 | 本机工作台数据目录 |
| 导出 | 明确标识的示例交接格式，含全部原文与设计，不可直接导回桌面版 | 桌面工作台原生设计包 |

在线示例不会上传草稿或导入私人文件，也不执行、安装或发布 Skill。GitHub Pages 托管静态页面；这里没有公开运行本机服务。浏览器禁用本地存储时仍可操作与导出；清理浏览器数据会清掉已保存草稿，请先导出备份。

首页动图是本页面**真实操作截图的步骤回放**，包括进入内部、跨来源加入、连接、剪线、原文查看和导出。它不是自动生成 Skill 的效果展示。

想用自己的 Skill，下载 [Windows 完整版](https://github.com/jiangzl1986-gif/skill-workbench/releases/latest)，参考 [桌面版图文演示](TRY_IT.md)。

---

## English

[**Try it now — no installation or account**](https://jiangzl1986-gif.github.io/skill-workbench/?lang=en)

Add evidence checking to a notes-to-outline Skill:

1. Choose **Start here: open “Outline design”** to see its submodules.
2. Find **Evidence check** in the shared library and click **Add**, or drag it onto the canvas. Its source label stays with it.
3. Drag the output dot of **Claims & evidence** onto the input dot of **Evidence check**. Alternatively, choose **From module** and **To module**, add a handoff note, and click **Connect**.
4. Use the **scissors** on a line to disconnect without deleting modules. Select a module to replace it, remove it from the draft, or write an integration note.
5. **Save draft** keeps it in this browser. **Export design** downloads the complete example handoff as JSON for your agent to inspect.

Switch to **Knowledge map** to inspect the original structure. Source buttons show complete texts, line numbers and hashes. Dashed containment links are not inferred execution order. The original examples are in Chinese and are preserved verbatim; the interface supports both languages.

This static example uses only the two bundled public Skills (five files). It uploads no drafts, opens no private files and executes no Skills. Browser storage is local to this browser and origin; export before clearing it. Export still works when browser storage is unavailable.

The example export is **not the desktop import format**. It preserves all original example files, source identities, positions, parent-child relationships, connections, notes and limits. An agent must still validate interfaces, dependencies and semantics before implementation; export grants no permission to modify, execute, install or publish a Skill.

The README animation is a **step-by-step replay of actual browser screenshots**, not a mockup or a claim of automatic Skill generation.

To import your own Skills and use the complete local workflow, [download the Windows app](https://github.com/jiangzl1986-gif/skill-workbench/releases/latest) and follow the [desktop walkthrough](TRY_IT.md#english).

## Build and verify the static example

From `apps/web`, run `npm ci`, then `npm run build:demo`. Run `node tools/test_demo.mjs` from the repository root. The output is `apps/web/dist-demo`; serve it at `/skill-workbench/` (or use `npm run dev:demo` for development).

`tools/build_demo_sources.mjs` reads only an explicit five-file allowlist under `examples/`. The browser reuses the existing assembly composition and connection checks. The Pages workflow publishes only static output; the local API is never deployed. Existing desktop source semantics and installer assets are unchanged.
