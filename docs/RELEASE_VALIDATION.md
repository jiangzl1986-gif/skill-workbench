# 发布验收范围 / Release validation scope

## Windows 免安装包：0.1.0-beta.2

此轮只扩展打包、冻结资源定位和启动窗口，保留原功能与完整契约。源码环境用于构建，实际成品 EXE 的检查由独立进程执行，不导入应用实现作为答案。

| 检查 | 结果与实际范围 |
| --- | --- |
| 原回归 | 32 项通过；既有规则、权限、容量与来源保真约束继续检查。 |
| 成品冷启动 | 清除 PYTHONHOME、PYTHONPATH 等外部环境，PATH 仅保留 Windows 系统目录，确认找不到 Python 和 Node。迁移到包含中文与空格的完整解压目录，EXE 启动成功，内置 Python DLL 与应用资源路径均位于解压目录。 |
| 原功能与保真 | 独立 HTTP 进程导入两个公开示例，保存跨来源内部组合并导出；以 JSON/gzip/base64/SHA-256 核对原文件实际字节与设计正文哈希，不调用索引器或组装实现。 |
| 生命周期与拒绝 | 退出后重新启动，来源与草稿保留；第二实例占用同端口时拒绝启动，原服务继续运行且没有创建冲突运行资料。无会话、错误 Host、错误 CSRF、过期草稿均按契约拒绝。 |
| 启动窗口 | 在本应用隐藏测试窗口调用实际 Tk 按钮回调，检查服务就绪后打开浏览器、重新打开和正常退出。此项检查运行源程序窗口回调，不冒充对另一电脑成品界面的人工检查。 |
| 实际浏览器 | 使用成品 EXE 提供的页面，载入完整结构，进入父模块，加入另一 Skill 的小模块、内部连线、保存并实际下载设计。另行核对下载文件的完整正文、内部来源位置及连线和原文件字节。 |
| 公开包 | 仅程序、内置运行时、已构建界面、原创公开示例、文档和依赖许可；不收录数据库、用户资料、私人 Skill 或授权信息。 |
| 安装与卸载 | 在新的中文与空格目录静默安装，逐文件核对成品清单哈希；直接启动已安装 EXE，验证无需外部 Python/Node 的环境路径、页面与空白工作空间；本次测试卸载后，目录外用户资料字节保留。测试不创建个人桌面/菜单入口，不覆盖任何既有安装。 |

源程序窗口检查在 `tools/check_windows_gui.py`，成品独立检查在 `tools/check_windows_bundle.py`，复建脚本在 `tools/build_windows.py`。相同流程加入 Windows CI；CI 成功记录见仓库 Actions。

安装程序编译与独立验收在 `tools/build_windows_installer.py`、`tools/check_windows_installer.py`。仅检查自己的新测试安装；发现已登记安装时测试停止。安装向导为英文；完整交互向导和桌面图标尚未作为另一实体电脑的人工验收。

Windows x64 以外的平台、第二台用户实体电脑、数字签名及任意 Skill 的业务执行质量尚未验证或完成。无环境路径检查证明此次成品运行不需要外部 Python/Node，不等同于全部电脑、全部安全策略已兼容。

English: all 32 existing regression checks passed. A relocated packaged EXE was tested independently with Python and Node absent from PATH, including source fidelity, nested composition, export, rejection boundaries and restart persistence. Source-program Tk callbacks and real-browser editing/download were checked separately. The checks do not establish compatibility with every computer, security policy or Skill. The Windows x64 EXE is currently unsigned; a second physical user computer and other platforms remain unvalidated.

## 历史：0.1.0-beta.1 验收范围

本页记录首个公开测试版的验证边界。程序测试、独立文件核对、真实浏览器操作和 Skill 实际业务执行分别记录。

## 已验证

| 路径 | 结果与证据方式 |
| --- | --- |
| 项目回归测试 | 32 个测试项通过。覆盖空白工作空间、原文件字节和 SHA-256、父子范围、跨来源保存和导出、内部加入/替换/移除、版本明确采纳、来源漂移、路径/ZIP/请求与设计容量拒绝。公开测试在 `tests/test_portable.py`，预期来自独立编写的公开样例与明确约束。 |
| Windows 安装与构建 | 在同一台 Windows 电脑的新项目目录、新 Python 虚拟环境和独立运行目录，实际运行 Windows PowerShell 5.1 的 `setup.ps1`，安装锁定依赖并构建页面成功。中文脚本保留 UTF-8 BOM。 |
| 页面重新构建 | 放入一份过期测试页面文件后重新构建：旧文件退出当前页面目录，并留在独立备份；发布包只收录本次完整构建。 |
| 冷启动 | 实际运行 `start.ps1`；空白数据库不携带任何个人来源，首页与构建资源正常响应。两个公开示例可预览、确认导入，整套结构没有推断出的执行连线。 |
| 保存与重启 | 跨来源草稿保存成功；关闭后重新启动，两个来源、模块位置和设计连接保留。 |
| 浏览器操作 | 实际操作空白首页、两个示例导入、共享模块库、载入完整结构、外层连接与剪断、进入父模块、加入另一来源的小模块、内部连接、保存、重新打开和下载设计包。 |
| 下载包字节核对 | 另一个独立进程使用标准 JSON/gzip/base64/SHA-256，核对浏览器下载包的规范哈希、两份来源的 5 个原文件字节、6 个外层实例和内部来源位置/连线。内部编辑以增量位置保存，未修改的原位置通过原来源结构还原。该进程不调用索引器或组装实现。 |
| 本机访问边界 | 无会话请求、错误 Host/Origin、缺失 CSRF、超限请求与路径穿越的拒绝符合约束；不同服务端口使用独立会话 Cookie。 |
| 公开内容边界 | 发布只使用程序、原创公开示例、公开文档、真实示例截图和依赖许可的白名单；不含导入快照、运行数据库、私人 Skill、个人配置、私有材料和授权凭证。 |

`setup.cmd` 和 `start.cmd` 是调用对应 PowerShell 脚本的薄入口。本次实际验证了脚本路径；没有把某台电脑上的准备成功等同于所有用户电脑都能成功。

## 尚未验证与后续门槛

- 第二台全新电脑、其他操作系统、不同代理/杀毒策略和不同 Python/Node 安装方式。
- 任意第三方 Skill 的业务语义、接口兼容、最终执行质量、真实模型/视频生产行为。标题结构不是自动推导的业务流程。
- 独立评审者的全面语义审查；项目自身的回归测试不冒充独立业务审核。
- 跨路径迁移已有运行数据库；当前推荐停服务后备份完整运行目录，并恢复到相同路径。
- 自动生成可执行 Skill、自动安装、正式晋升、跨对话框自动分发或真实调用回执。
- 知识/经验/证据库的整理与检索；它们列入路线图。

## 已知非阻断提示

测试工具会提示 Starlette 的 httpx 测试客户端适配将来需要更新。构建会提示 React Flow 的 `use client` 指令被忽略，以及单个前端文件超过建议大小。当前构建和上述操作通过；后续可在保持行为和测试边界的前提下优化依赖与按需加载。

超出容量会明确拒绝，保留来源；不会通过删字段、裁原文或跳过原规则来让测试通过。
