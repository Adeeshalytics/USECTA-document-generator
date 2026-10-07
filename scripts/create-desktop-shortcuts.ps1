$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
$Pythonw = Join-Path $Project 'runtime/python/pythonw.exe'
if (-not (Test-Path $Pythonw)) {
    throw 'Run setup-desktop.bat first. Keep the whole USECTA folder together.'
}
$Desktop = [Environment]::GetFolderPath('Desktop')
New-Item -ItemType Directory -Force -Path $Desktop | Out-Null
$Shell = New-Object -ComObject WScript.Shell
foreach ($Entry in @(@('USECTA Documents', ''), @('Stop USECTA Documents', ' --stop'))) {
    $Shortcut = $Shell.CreateShortcut((Join-Path $Desktop ($Entry[0] + '.lnk')))
    $Shortcut.TargetPath = $Pythonw
    $Shortcut.Arguments = '"' + (Join-Path $Project 'desktop.py') + '"' + $Entry[1]
    $Shortcut.WorkingDirectory = $Project
    $Shortcut.Description = 'USECTA local document generator'
    $Shortcut.Save()
}
Write-Host 'Created USECTA Documents and Stop USECTA Documents desktop shortcuts.'
