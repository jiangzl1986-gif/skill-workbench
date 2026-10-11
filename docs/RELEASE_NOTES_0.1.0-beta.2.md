# Skill Workbench · 可视化 Skill 创作工作台

**让 Skill 可视化，让创作过程看得见。**

**An infinite canvas for visual AI Skill creation.**

把已有 Skill 看清楚，把不同来源的模块重新搭配，把新 Skill 的结构画出来，再将完整设计交给自己的 Agent 或开发者完成接入。

[项目介绍 / Project overview](https://github.com/jiangzl1986-gif/skill-workbench#readme) · [详细使用指南 / User guide](https://github.com/jiangzl1986-gif/skill-workbench/blob/main/docs/USER_GUIDE.md)

## 下载后，三步开始

1. 在本页 **Assets** 中下载 **skill-workbench-0.1.0-beta.2-windows-x64-setup.exe**。
2. **双击**安装程序，点击 **Install**。
3. 完成后打开 **Skill Workbench**，浏览器自动显示工作台；以后可从桌面或开始菜单打开。

**无需自行安装 Python、Node.js，无需运行 setup，也无需联网安装依赖。** 请下载上面的安装包；GitHub 自动提供的 Source code 是开发源码。

当前提供 **Windows x64** 包，工作台界面为中文，安装向导为英文。使用时保留启动窗口，点 **退出工作台** 正常停止服务。资料默认保存在本机 `%LOCALAPPDATA%\skill-workbench`，与程序目录分开，卸载程序时保留。

如果不想安装，可下载 **windows-x64-portable.zip**，完整解压后双击 **启动工作台.exe**；保留 EXE 旁的 `_internal` 文件夹。

打开“导入与同步”，导入自己的 Skill，或先选择包内 `examples` 中的两个公开示例体验跨来源组装。

## 你可以用它做什么

- **让 Skill 可视化。** 在知识地图中查看整个 Skill、大模块、小模块、文件、规则和引用，定位来源原文与行号。讨论修改时，可以直接指出具体模块及内部位置。
- **用无限画布创作 Skill。** 从空白方案开始，或载入已有 Skill 的完整结构；拖拽、缩放、平移、连接模块。进入大模块内部加入、替换、移除和连接小模块；连错时单独剪断连接，保存后继续编辑。
- **跨 Skill 组合可复用模块。** 导入自己的 Skill，或有权研究和复用的外部 Skill，无需先安装到 Agent。共享模块库集中显示所有来源，支持搜索与筛选，并标明来源、版本、文件和原文范围。
- **整理已有、研发中和未来计划的 Skill。** 梳理已安装目录，维护开发草稿，为未来的 Skill 规划结构。来源更新后核对变化、预览并明确采用新版，旧快照与旧草稿继续保留。

导入 → 知识地图 → 共享模块库 → 整体与内部组装 → 保存并导出完整 JSON → 交给 Agent 或开发者核验并实施 → 确认新版后同步。

导出包保留完整来源文件、版本、字节校验、父子位置、内部连线和接入要求。画布连线表达设计意图；实际可执行 Skill 仍需完成接口接入、规则核验和独立验证。

## 本次更新与验证边界

新增包含 Python 运行时和已构建页面的 Windows 启动程序，保留源码使用方式和既有功能、规则、容量及授权边界。原 Skill 来源只读，导入的脚本不执行；程序不自动安装 Skill、不调用付费模型 API。

32 项原回归检查通过。成品 EXE 在不含 Python/Node 的环境路径、中文及空格目录下通过独立进程检查：导入、跨来源内部组装、保存、原文件字节与导出哈希、重启恢复、端口占用拒绝及请求边界。启动窗口回调和实际浏览器内部组装、保存与下载另行检查。详情见 [验证记录](https://github.com/jiangzl1986-gif/skill-workbench/blob/main/docs/RELEASE_VALIDATION.md)。

尚未在第二台用户实体电脑验证；EXE 暂未取得 Windows 数字签名。其他系统和任意第三方 Skill 的业务执行质量未验证。统一知识、经验、证据库及自动分发仍在后续计划中。

MIT 许可覆盖本程序；导入内容及依赖各自保留原许可。旧版本继续保留。内部版本 `0.1.0-beta.2` 用于下载、更新与追溯。

## English

See how existing AI Skills are built, compose new designs on an infinite canvas, and combine modules from different sources. Export the complete design to your agent or developer for integration.

### Download and double-click

1. In **Assets**, download **skill-workbench-0.1.0-beta.2-windows-x64-setup.exe**.
2. **Double-click** it and choose **Install**.
3. Open **Skill Workbench** when finished. Your browser opens automatically; desktop and Start menu shortcuts are available for later use.

**No separate Python, Node.js, setup command or online dependency installation is required.** The automatically generated Source code archives are for developers. This package targets **Windows x64**; the workbench UI is Chinese and the wizard is English. Keep the launcher open while working. Click **退出工作台** to stop the local service. Data defaults to `%LOCALAPPDATA%\skill-workbench`, outside the application directory, and is retained on uninstall.

For the portable option, download **windows-x64-portable.zip**, extract the entire archive and double-click **启动工作台.exe**. Keep `_internal` beside the EXE.

Import your own Skill through “导入与同步”, or try the two public examples in the bundled `examples` folder.

### Create and organize Skills visually

- **Visualize existing Skills.** Explore Skills, parent modules, submodules, files, rules and references. Locate original text and line ranges and point to precise changes when working with your agent.
- **Create on an infinite canvas.** Start with a blank design or load an existing structure. Drag, pan, zoom and connect modules; enter a parent module to add, replace, remove and connect submodules. Cut an incorrect connection without deleting its modules.
- **Combine modules across sources.** Import your Skills or external Skills you have permission to study and reuse, without installing them in your agent. Search a shared library with source, version, file and original-range attribution.
- **Organize installed, developing and planned Skills.** Inspect installed directories, maintain development drafts and plan future structures. Preview source changes and explicitly adopt updates while preserving old snapshots and drafts.

Import → knowledge map → shared module library → outer and nested composition → save and export JSON → agent/developer review and integration → confirm and synchronize the new version.

Exports include complete original files, versions, byte checksums, parent/child positions, nested connections and integration requirements. Connections express design intent; executable Skill integration and independent validation are still required.

### What changed and what was checked

This update bundles the Python runtime and prebuilt interface in a Windows app. Existing source setup, features, rules, limits and authority boundaries remain. Imported sources stay read-only, imported scripts are not executed, and the app does not automatically install Skills or call paid model APIs.

All 32 existing regression checks passed. Independent checks ran the relocated EXE with Python and Node removed from PATH: import, cross-source nested composition, save/export byte fidelity, restart persistence, occupied-port rejection and request boundaries. Launcher callbacks and real-browser nested editing, save and download were checked separately. A second physical user computer, other operating systems and arbitrary Skill execution remain unvalidated. The EXE is currently unsigned. Unified knowledge/experience/evidence libraries and automatic distribution remain future work.

MIT covers the program; imported content and dependencies retain their own licenses. Previous releases remain available. Internal version `0.1.0-beta.2` is retained for downloads, updates and traceability.
