# Windows 安装与免安装 / Windows installer and portable app

## 直接双击安装（推荐）

下载 **windows-x64-setup.exe**，双击并点击 **Install**。安装结束后打开 **Skill Workbench**；以后从桌面或开始菜单启动。所需运行时已包含，不需要安装 Python/Node.js 或联网下载依赖。安装向导为英文，工作台界面为中文。

仅为当前用户安装，默认在 `%LOCALAPPDATA%\Programs\Skill Workbench`；无需管理员，不修改系统 PATH、文件关联或防火墙。用户资料另存于 `%LOCALAPPDATA%\skill-workbench`，卸载不删除该目录。更新前正常退出正在使用的工作台。

Download **windows-x64-setup.exe**, double-click it and choose **Install**. Open **Skill Workbench** after installation; desktop and Start menu shortcuts are available. The installer is offline and per-user, without administrator, PATH or firewall changes. User data is stored separately and retained on uninstall. The wizard is English; the workbench UI is Chinese.

## 免安装方式 / Portable option

1. 从发布页下载 **windows-x64-portable.zip**。
2. 完整解压，打开 **Skill Workbench** 文件夹。
3. 双击 **启动工作台.exe**，浏览器会自动打开工作台。
4. 使用时保留启动窗口；点 **退出工作台** 正常停止本次服务。

无需另外安装 Python、Node.js，无需运行 setup，无需联网下载依赖。当前提供 Windows x64 包；界面为中文。原源码安装方式继续保留，供开发者使用。

请保留 EXE 旁的 `_internal` 文件夹，不能仅复制 EXE。资料默认存放于本机 `%LOCALAPPDATA%\skill-workbench`，更换程序目录不会自动删除资料。导入原来源只读；导出的 JSON 是设计，仍需 Agent 或开发者完成实际接入。

若提示端口已占用，先检查是否已经启动一个工作台；程序不会关闭其他服务。启动失败时窗口会显示原因，本机日志保存在运行资料目录的 `launcher.log`。

当前 EXE 尚未取得 Windows 数字签名；尚未在第二台用户实体电脑验证。

## 开发者复建 / Rebuilding for developers

在 Windows x64、Python 3.11.9 和 Node.js 22 下，先运行 `setup.cmd` 构建公开页面，再使用项目虚拟环境安装 `requirements-build.lock.txt`。运行 `tools/build_windows.py --output <新的本地空目录>` 生成 ZIP 和 SHA256SUMS.txt。构建工具拒绝覆盖已有构建目录；不会打包个人运行资料或导入的 Skill。

使用 `tools/check_windows_bundle.py --bundle <构建目录>/dist/启动工作台 --work <另一空目录>` 对成品 EXE 做独立检查；检查时移除 Python 和 Node 的环境路径，验证迁移目录、原文保真、内部组装、保存、导出与重启恢复。Node.js 仅在构建阶段使用，成品用户不需要安装。

For developers: build on Windows x64 with Python 3.11.9 and Node.js 22. Run `setup.cmd`, install `requirements-build.lock.txt` in the project environment, then run `tools/build_windows.py --output <new empty local directory>`. The builder never deletes existing builds. Run `tools/check_windows_bundle.py` against the produced directory with a separate empty acceptance directory. Node.js is a build-time tool, not a user runtime requirement.

如需安装 EXE，再准备官方 Inno Setup 6.7.3 编译器，运行 `tools/build_windows_installer.py --build <便携包构建目录> --compiler <ISCC.exe> --output <新空目录>`。此步骤先核对全部成品文件哈希，再编译 `packaging/windows.iss`；使用已验收程序，不改变业务规则。安装工具的来源、固定摘要及 CI 过程可在 Windows workflow 中检查。

## English

Download **windows-x64-portable.zip**, extract the complete archive, then double-click **启动工作台.exe** inside the **Skill Workbench** folder. Your browser opens automatically. Keep the launcher open; click **退出工作台** to stop the service.

No separate Python, Node.js, setup command or online dependency installation is required. This package targets Windows x64; the UI is Chinese. Keep the `_internal` folder next to the EXE. User data defaults to `%LOCALAPPDATA%\skill-workbench`, outside the application directory. Original Skill sources stay read-only. Exported designs still require agent or developer integration.

The EXE is currently unsigned. A second physical user computer has not yet been validated.
