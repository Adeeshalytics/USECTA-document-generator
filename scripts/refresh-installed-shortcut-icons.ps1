$ErrorActionPreference = 'Stop'
$Install = Join-Path $env:LOCALAPPDATA 'Programs\USECTA Document Generator'
$Executable = Join-Path $Install 'USECTA-Document-Generator.exe'
$Icon = Join-Path $Install '_internal\assets\usecta-icon.ico'
if (-not (Test-Path -LiteralPath $Icon)) { throw 'Installed USECTA icon was not found.' }
$Shell = New-Object -ComObject WScript.Shell
$Shortcuts = @(
    (Join-Path $Shell.SpecialFolders.Item('Desktop') 'USECTA Document Generator.lnk'),
    (Join-Path $Shell.SpecialFolders.Item('Programs') 'USECTA Document Generator\USECTA Document Generator.lnk')
)
foreach ($Path in $Shortcuts) {
    if (-not (Test-Path -LiteralPath $Path)) { throw 'An installed USECTA shortcut was not found.' }
    $Shortcut = $Shell.CreateShortcut($Path)
    if ($Shortcut.TargetPath -ne $Executable) { throw 'Refusing to change an unrelated shortcut.' }
    $Shortcut.IconLocation = $Icon + ',0'
    $Shortcut.Save()
    if ($Shell.CreateShortcut($Path).IconLocation -ne ($Icon + ',0')) { throw 'Shortcut icon verification failed.' }
}
Write-Host 'Both installed USECTA shortcuts now explicitly use the supplied icon.'
