<a id="skill-workbench--可视化-skill-创作工作台"></a>

# SkillTangram｜技能七巧板

**在无限画布上，拼出你的 AI 技能。**

**Compose AI Skills on an infinite canvas.**

把 Skill 从分散的文件和文字讨论带到同一个可视化工作空间：看懂已有结构，用模块搭出新方案，再把完整设计交给自己的 Agent 或开发者完成接入。

Bring AI Skills into a visual workspace: inspect existing structures, compose new designs from reusable modules, and hand the complete design to your agent or developer for integration.

[项目介绍 / Project overview](https://github.com/jiangzl1986-gif/skill-workbench#readme) · [使用指南 / User guide](https://github.com/jiangzl1986-gif/skill-workbench/blob/main/docs/USER_GUIDE.md)

## 你可以用它做什么

### 让 Skill 可视化，看清每个模块的位置

用知识地图查看整个 Skill、大模块、小模块、规则、文件与引用，定位来源原文和行号。与 Agent 讨论修改时，可以明确指出要调整哪个模块、哪个内部位置，让结构与修改意图都看得见。

### 用无限画布搭配模块，设计自己的 Skill

创建空白方案，或将已有 Skill 的完整结构载入画布。拖拽、缩放、平移、连线；深入大模块内部加入、替换、移除小模块，再连接内部内容。连错时单独剪断连接，继续调整布局。用图形表达想要的组合和交接，保存后随时继续编辑。

### 把不同 Skill 的模块汇入同一仓库，跨来源组合

导入自己的 Skill，或有权研究和复用的外部 Skill，无需先安装到 Agent。工作台提取文件与标题层级形成可检查的模块结构，集中到共享模块库。跨 Skill 搜索和选择，每个模块标明来源、版本、文件及原文范围；可以把 A 的小模块加入 B 的内部，也可以搭成全新的设计。

### 整理正在使用、正在开发和未来计划的 Skill

导入已安装目录，看清已有能力；导入开发目录，整理模块与维护草稿；为未来的 Skill 创建空白设计，先规划所需模块。来源更新后，核对变化、预览并明确采用新版，原快照和旧草稿继续保留。

## 从设计到 Agent 接入

导入 Skill → 知识地图查看 → 共享模块库选择 → 画布整体 / 内部组装 → 保存并导出 JSON → 交给 Agent 或开发者核验接口、规则并实施 → 确认新版本后同步工作台。

导出包包含完整来源文件、版本、校验信息、父子位置、内部连接和接入要求。画布提供可交接的设计；实际可执行 Skill 仍需开发接入与独立验证，复制指令不会自动发送给对话框。

## 下载与使用

下载下方的 Windows ZIP，解压后双击 `setup.cmd`，准备完成后双击 `start.cmd`。首次需要 Python 3.11、Node.js 22 LTS 和联网下载依赖；当前界面为中文，无需模型 API Key。可以先用 `examples` 中的两个公开示例体验。

下载包包含源码、预构建页面、中英文项目介绍、中文使用指南、公开示例和依赖许可。`SHA256SUMS.txt` 可核对下载；Python 和 Node 安装器不包含在包内。

## 验证、许可与发布信息

32 个回归测试项通过；已在同一台 Windows 电脑的独立目录验证安装、构建、启动、重启保留数据，以及实际浏览器的跨来源内部组装与导出。第二台全新电脑、其他系统和任意 Skill 的业务执行仍待验证。知识 / 经验 / 证据库、自动分发与实际调用回执属于后续计划。

资料留在本机，原来源只读；程序不执行导入脚本、不自动安装 Skill、不调用付费 API。程序采用 MIT，导入内容继续遵循原许可。容量和来源校验规则见 [完整契约](https://github.com/jiangzl1986-gif/skill-workbench/blob/main/docs/WORKBENCH_CONTRACT.md)。

内部版本与标签 `0.1.0-beta.1` 保留用于下载、更新及追溯。本次更新的是介绍与使用资料，程序代码和既有验证范围保持原状态；标签仍指向原发布代码，仓库首页与 Windows 包中的项目介绍已更新。

---

## English

### Visualize Skills and see where every module belongs

Explore a Skill through knowledge maps: whole Skills, modules, submodules, rules, files and references, with original content and line numbers. Show your agent exactly which module or internal position you want to change.

### Design Skills through modular composition on an infinite canvas

Start with a blank design or load an existing Skill's complete structure. Drag, zoom, pan and connect modules. Enter a parent module to add, replace, remove and connect submodules. Cut one incorrect link while keeping the modules, save your draft, and continue editing later.

### Bring modules from different Skills into one shared library

Import your own Skills or external Skills you are permitted to study and reuse, without installing them into an agent. The workbench extracts inspectable structure from files and headings and collects module candidates in a shared library. Search across sources; every module keeps its source, version, file and content range. Add a submodule from A inside B, or compose an entirely new design.

### Organize installed Skills, development work and future plans

Import installed directories to inspect current capabilities, or development folders to organize modules and maintain revision drafts. Create a blank design for a future Skill. Inspect source changes and explicitly adopt a new version while retaining earlier snapshots and drafts.

### From a design to agent integration

Import → inspect maps → choose modules → compose outer and nested structures → save and export JSON → give it to an agent or developer for interface and rule validation and implementation → adopt the confirmed version in the workbench.

Exports contain complete original files, versions, checksums, parent positions, internal connections and integration requirements. An executable Skill still requires development and independent validation; copying a handoff instruction does not automatically send it to another conversation.

### Download and run

Download the Windows ZIP below, extract it, run `setup.cmd`, then `start.cmd`. Initial setup needs Python 3.11, Node.js 22 LTS and Internet access for dependencies. The current UI is Chinese; no model API key is required. Try the two public Skills under `examples/` first.

The archive includes source code, a prebuilt UI, Chinese and English project introductions, a Chinese user guide, public examples and dependency licenses. Use `SHA256SUMS.txt` to check the download. Python and Node installers are not included.

### Validation, licenses and release details

32 regression checks passed. Installation, build, launch, restart with preserved data, browser-based cross-source nested composition and export were checked in isolated directories on the same Windows computer. A second fresh physical computer, other operating systems and arbitrary Skill execution remain unvalidated. Unified knowledge / experience / evidence libraries, automatic distribution and actual usage receipts remain future work.

Data stays local and original sources are read-only. Imported scripts are not executed, Skills are not automatically installed, and no paid APIs are called. MIT covers the program; imported content retains its own license. See the [full contract (Chinese)](https://github.com/jiangzl1986-gif/skill-workbench/blob/main/docs/WORKBENCH_CONTRACT.md) for capacity and source-check boundaries.

The internal version and tag `0.1.0-beta.1` remain for downloads, updates and traceability. This refresh changes presentation and documentation only; program code and the existing validation scope are unchanged. The tag still points to the original release code, while the repository overview and Windows archive contain the updated introductions.

Share your creation scenarios or minimal public examples in [Issues](https://github.com/jiangzl1986-gif/skill-workbench/issues).
