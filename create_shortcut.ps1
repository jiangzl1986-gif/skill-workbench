$ErrorActionPreference='Stop'
$taskDesktop=[Environment]::GetFolderPath('Desktop')
$taskShell=New-Object -ComObject WScript.Shell
$taskShortcut=$taskShell.CreateShortcut((Join-Path $taskDesktop 'Skill Workbench.lnk'))
$taskShortcut.TargetPath=Join-Path $PSScriptRoot 'start.cmd'
$taskShortcut.WorkingDirectory=$PSScriptRoot
$taskShortcut.Description='用画布创作、整理与组装 Skill'
$taskShortcut.Save()
Write-Host '桌面入口已建立；项目目录移动后请重新创建入口。'
