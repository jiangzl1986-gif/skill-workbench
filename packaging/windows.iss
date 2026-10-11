; Program files only; user data and imported Skill sources are never installer targets.
#ifndef BundleDir
  #error Supply BundleDir from the verified public portable build
#endif
#ifndef OutputDir
  #error Supply a new independent OutputDir
#endif

[Setup]
AppId={{D3F1782B-F98A-473B-8AB2-17DB9370F33B}
AppName=Skill Workbench
AppVersion=0.1.0-beta.2
AppPublisher=Skill Workbench contributors
AppPublisherURL=https://github.com/jiangzl1986-gif/skill-workbench
AppSupportURL=https://github.com/jiangzl1986-gif/skill-workbench/issues
DefaultDirName={localappdata}\Programs\Skill Workbench
DefaultGroupName=Skill Workbench
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
OutputDir={#OutputDir}
OutputBaseFilename=skill-workbench-0.1.0-beta.2-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
DisableDirPage=yes
AllowNoIcons=yes
UninstallDisplayIcon={app}\启动工作台.exe
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut / 创建桌面快捷方式"; GroupDescription: "Start Skill Workbench / 启动工作台"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Skill Workbench"; Filename: "{app}\启动工作台.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Skill Workbench"; Filename: "{app}\启动工作台.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\启动工作台.exe"; Description: "Open Skill Workbench / 打开工作台"; Flags: nowait postinstall skipifsilent

; No registry edits beyond Inno Setup's normal current-user uninstall registration.
; No UninstallDelete section: user data outside {app} is retained.
