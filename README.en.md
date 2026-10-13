<a id="skill-workbench--visual-ai-skill-creation"></a>

# SkillTangram｜技能七巧板

**Compose AI Skills on an infinite canvas.**

SkillTangram turns reusable modules into pieces you can compose. Understand existing Skills, remix modules from different sources on an infinite canvas, and hand the complete design to your agent for validation and implementation.

[**Try in your browser — no install →**](https://jiangzl1986-gif.github.io/skill-workbench/?lang=en) · [**Download Windows installer**](https://github.com/jiangzl1986-gif/skill-workbench/releases/download/v0.1.0-beta.2/skill-workbench-0.1.0-beta.2-windows-x64-setup.exe) · [**Discussions**](https://github.com/jiangzl1986-gif/skill-workbench/discussions)

Formerly Skill Workbench. Repository and demo URLs, saved drafts and existing downloads remain compatible. [Name and compatibility](docs/BRANDING.md).

[中文 / Bilingual overview](README.md) · [All downloads](https://github.com/jiangzl1986-gif/skill-workbench/releases) · [User guide (Chinese)](docs/USER_GUIDE.md)

[![Actual UI walkthrough: open a parent module, add evidence checking from another Skill, connect, cut, inspect source and export.](docs/images/live-walkthrough.gif)](https://jiangzl1986-gif.github.io/skill-workbench/?lang=en)

**Try a real edit before installing anything.** [Open the interactive canvas](https://jiangzl1986-gif.github.io/skill-workbench/?lang=en), go inside “Outline design”, bring in “Evidence check” from another Skill, connect or cut links, and export the design with its complete source files. The animation is a step-by-step replay of actual browser screenshots.

Chinese / English interface · No account · Two public example Skills · Drafts stay in your browser. The example export is for agent review, not desktop import. To import your own Skills, get the full desktop app.

[Browser example guide](docs/ONLINE_DEMO.md#english) · [Desktop walkthrough](docs/TRY_IT.md#english)

Windows x64 · Chinese UI · MIT · Local-first · **No separate Python / Node.js installation**

If it helps you create Skills, **Star** the repository to find it again. Share public use cases in [Discussions](https://github.com/jiangzl1986-gif/skill-workbench/discussions), or report reproducible bugs through [Issues](https://github.com/jiangzl1986-gif/skill-workbench/issues/new/choose).

<a id="english"></a>
## Why a visual workspace for AI Skills?

Text conversations with an agent are useful for building a Skill. As its rules and files grow, it becomes harder to see which modules exist, where a rule belongs, how two modules should hand off their work, or where a submodule from another Skill should fit.

SkillTangram gives that process a visible, editable workspace. **Sketch your ideas, inspect the structure, and show exactly where a change belongs.** Use text to explain goals and integration requirements, and the canvas to express module placement, composition and connections.

## What you can create and organize

### 1. Visualize existing Skills before changing them

Import a Skill and explore its knowledge map from the whole Skill down to modules, submodules, files, rules and references. Open a node to read its original content, source and line numbers. Search brings you back to the relevant location.

Inspect an unfamiliar Skill, locate your own rules, or point your agent to the exact module and position you want to change. The structure becomes visible beyond folders and conversation history.

### 2. Design new Skills with modular composition on an infinite canvas

Start with a blank design or load an imported Skill's complete structure. Add modules, zoom and pan, arrange the layout, and draw connections to describe intended handoffs.

Work inside a parent module too: add, replace or remove submodules at specific positions, then connect them internally. Cut an incorrect link while keeping both modules. Plan the structure of a future Skill first, then develop its goals, handoff conditions and integration requirements.

### 3. Reuse modules across Skills in one shared library

Import your existing Skills or external Skills you are permitted to study and reuse, **without first installing them into an agent**. The workbench extracts inspectable structure from files, headings and references, then brings those module candidates into a shared assembly library.

Search across sources and filter by Skill or module level. Each module retains its source Skill, version, file and original content range. Put a module from A into a draft based on B, or combine several sources into a new design, then give your agent the complete design for integration.

### 4. Organize installed Skills, work in progress and future ideas

Import installed Skill directories to inspect their structure. Import development folders to review modules and maintain revision drafts. For a Skill you have not built yet, create a blank design and plan the capabilities and modules it needs.

When a source directory changes, inspect the differences and explicitly adopt a new version. Earlier snapshots and drafts retain their original versions, so both source updates and design dependencies remain traceable.

## From an idea to an integration handoff

```mermaid
flowchart LR
  A[Import existing Skills] --> B[Inspect maps and original content]
  B --> C[Choose modules across sources]
  C --> D[Design outer and nested composition]
  N[Blank design for a new Skill] --> D
  D --> E[Save and export a complete design]
  E --> F[Agent or developer validates and integrates]
  F --> G[Adopt the confirmed version in the workbench]
```

For example, add evidence review to a notes-to-outline Skill. Import both Skills, load the outline Skill's structure, enter its outline-design module, and place an evidence-check submodule from the other source at the intended position. Connect it, describe the handoff and save. Give the exported JSON to your agent so it can inspect original rules, versions and placement, resolve interfaces, and implement the confirmed design. Both original Skills remain available.

## Features and practical uses

| Feature | What you can do |
| --- | --- |
| **Knowledge maps** | Explore Skills, modules, files, rules and references; read original content and line numbers, search and locate details. |
| **Infinite-canvas interaction** | Start from a blank design or a complete imported structure; drag modules, zoom and pan to organize a composition. |
| **Nested assembly** | Add, replace or remove submodules at specific parent positions, preserving hierarchy and placement in saved designs. |
| **Connections and scissors** | Drag between ports or click ports in sequence; record handoff intent and cut one link without deleting either module. |
| **Shared module library** | Search every imported source together; filter by Skill and module level, with source, version, file and content-range labels. |
| **Local import and discovery** | Select a directory, choose or drag a complete folder, upload a ZIP, or discover Skills within a directory you specify; preview before adoption. |
| **Version checks and synchronization** | Inspect source changes and explicitly adopt a new version while retaining old snapshots, versions and drafts. |
| **Saved drafts** | Save, reopen and continue editing outer structures or internal submodules. |
| **Complete design exports** | Export original file content, versions, byte checksums, parent positions, connections and integration requirements for an agent or developer. |
| **Maintenance handoffs** | Record change requests, export analysis tasks and generate read-only analysis instructions for an exact registered version. |
| **Release and usage states** | Separate workbench registration, formal release evidence, local installation and actual usage; missing evidence stays unknown. |

Canvas connections express your design. **An executable Skill still requires interface integration, rule checks and independent validation by an agent or developer.** You pass the exported design to your chosen conversation; copying an instruction does not send it or prove usage. Automatically extracted file hierarchies and references are not treated as validated execution flows.

## Getting started — Windows

For your first session, follow the [public-example walkthrough](docs/TRY_IT.md#english). You do not need your own Skill or a model account to try the workbench.

1. Download the [Windows installer](https://github.com/jiangzl1986-gif/skill-workbench/releases), choosing **windows-x64-setup.exe**.
2. Double-click it and choose **Install**. Open **Skill Workbench** (the name in existing installers) when finished; your browser opens automatically. Desktop and Start menu shortcuts are available for later use.
3. Import your Skill through “导入与同步”, or try the two public examples in the installed `examples` folder.

**No separate Python, Node.js, setup command or online dependency installation is needed.** The package targets Windows x64; the workbench UI is Chinese and the installer wizard is English. Keep the launcher open and click **退出工作台** to stop the service.

For a portable option, download **windows-x64-portable.zip**, extract the complete archive and double-click **启动工作台.exe**. Keep `_internal` beside the EXE. The installer and app are currently unsigned.

Data defaults to the local `%LOCALAPPDATA%\skill-workbench`, separate from the program and original Skill directories. [Portable instructions](docs/WINDOWS_PORTABLE.md) · [Detailed user guide (Chinese)](docs/USER_GUIDE.md)

**Source developers**: the original source installation remains available. Install Python 3.11 and Node.js 22 LTS, run `setup.cmd`, then `start.cmd`. See the user guide for startup parameters and development details.

## Data, licenses and current boundaries

- Imported content stays local and source directories are read-only. The application does not execute imported scripts, automatically install Skills or call model or production APIs.
- Imports and canvas changes retain original content and provenance. Removing a design position does not delete source files or waive original rules, templates or quality requirements.
- The service binds only to `127.0.0.1`, with local-session, cross-site and request checks. It is not currently a public or multi-user server.
- Each source allows up to 5000 files / 32 MiB. Individual files, ZIPs, API requests, complete drafts and final design packages are capped at 2 MiB; outer drafts allow 60 module instances / 120 links, with coordinates within ±20000. Infinite canvas describes zoom, pan and free arrangement; capacity remains bounded. Oversized inputs are rejected without truncation. [Full contract (Chinese)](docs/WORKBENCH_CONTRACT.md)
- [MIT](LICENSE) covers this program. Imported content keeps its original license and reuse permissions. Dependencies retain their licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).

## Validation and future work

Import, source fidelity, outer and nested assembly, saving and export, explicit version adoption and invalid-input rejection were checked in isolated environments on the same Windows computer using public examples; 32 regression checks passed. A second fresh physical computer, other operating systems, arbitrary Skills' business semantics and actual execution have not been validated. [Validation scope (Chinese)](docs/RELEASE_VALIDATION.md)

The internal program identifier `0.1.0-beta.2` supports downloads, updates and traceability. Unified knowledge / experience / evidence libraries, interface-conflict guidance, automatic distribution and actual usage receipts, more platforms and installation improvements remain on the [roadmap (Chinese)](docs/ROADMAP.md); they are not advertised as implemented features.

Share creation scenarios and issues through [GitHub Issues](https://github.com/jiangzl1986-gif/skill-workbench/issues), or submit a Pull Request using the [contribution guide](CONTRIBUTING.md). Use a minimal public example and keep private Skills, accounts, credentials and project materials out of reports.
