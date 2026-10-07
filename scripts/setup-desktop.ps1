$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Project = Split-Path $PSScriptRoot -Parent
$Runtime = Join-Path $Project 'runtime'
$PythonFolder = Join-Path $Runtime 'python'
$PythonExe = Join-Path $PythonFolder 'python.exe'
$Downloads = Join-Path $Runtime 'downloads'
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
    throw 'This desktop kit needs Windows 10/11 on an Intel/AMD 64-bit PC.'
}
New-Item -ItemType Directory -Force -Path $Runtime, $Downloads | Out-Null

function Download-File($Url, $Destination) {
    Write-Host "Downloading $([IO.Path]::GetFileName($Destination))..."
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing -TimeoutSec 600
}
function Confirm-Publisher($Path, $Publisher) {
    $Signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch $Publisher) {
        throw "Publisher verification failed for $Path. Setup stopped; do not bypass this check."
    }
}

if (-not (Test-Path $PythonExe)) {
    # The official embeddable runtime can move between PCs without a Python install.
    $PythonZip = Join-Path $Downloads 'python.zip'
    Download-File 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' $PythonZip
    Expand-Archive -LiteralPath $PythonZip -DestinationPath $PythonFolder -Force
}
Confirm-Publisher $PythonExe 'Python Software Foundation'
@('python312.zip', '.', 'Lib/site-packages', '../..', 'import site') |
    Set-Content -LiteralPath (Join-Path $PythonFolder 'python312._pth') -Encoding ASCII
$PipFile = Join-Path $PythonFolder 'Lib/site-packages/pip/__init__.py'
if (-not (Test-Path $PipFile)) {
    $GetPip = Join-Path $Downloads 'get-pip.py'
    Download-File 'https://bootstrap.pypa.io/get-pip.py' $GetPip
    & $PythonExe $GetPip --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw 'Could not set up pip in the bundled runtime.' }
}
Write-Host 'Installing the app into its own portable Python runtime...'
& $PythonExe -m pip install --only-binary=:all: --no-warn-script-location -r (Join-Path $Project 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the internet connection and retry.' }
& $PythonExe -c 'import streamlit, docxtpl, openpyxl, pyarrow, lxml'
if ($LASTEXITCODE -ne 0) { throw 'The portable Python runtime did not pass its import check.' }

$LibreFolder = Join-Path $Runtime 'libreoffice'
$Soffice = Join-Path $LibreFolder 'program/soffice.exe'
if (-not (Test-Path $Soffice)) {
    $Installed = @("$env:ProgramFiles\LibreOffice", "${env:ProgramFiles(x86)}\LibreOffice") |
        Where-Object { Test-Path (Join-Path $_ 'program/soffice.exe') } | Select-Object -First 1
    if ($Installed) {
        Write-Host 'Copying the installed LibreOffice into the portable folder...'
        Copy-Item -LiteralPath $Installed -Destination $LibreFolder -Recurse -Force
    } else {
        # Extract the official signed MSI as an administrative image; do not install it globally.
        $Msi = Join-Path $Downloads 'LibreOffice.msi'
        Download-File 'https://downloadarchive.documentfoundation.org/libreoffice/old/25.8.2.2/win/x86_64/LibreOffice_25.8.2.2_Win_x86-64.msi' $Msi
        Confirm-Publisher $Msi 'Document Foundation'
        $Extract = Join-Path $Runtime 'libreoffice-extracted'
        New-Item -ItemType Directory -Force -Path $Extract | Out-Null
        $MsiLog = Join-Path $Downloads 'libreoffice-extract.log'
        Write-Host 'Extracting LibreOffice. Windows may ask for permission for this setup step...'
        $Arguments = '/a "' + $Msi + '" /qn TARGETDIR="' + $Extract + '" /L*v "' + $MsiLog + '"'
        $Installer = Start-Process -FilePath 'msiexec.exe' -ArgumentList $Arguments -Wait -PassThru
        if ($Installer.ExitCode -notin @(0, 3010)) { throw "LibreOffice extraction failed. See $MsiLog." }
        $Found = Get-ChildItem -LiteralPath $Extract -Filter 'soffice.exe' -Recurse | Select-Object -First 1
        if (-not $Found) { throw 'The LibreOffice archive did not contain soffice.exe.' }
        $ExtractedLibre = Split-Path (Split-Path $Found.FullName -Parent) -Parent
        if (Test-Path $LibreFolder) { Remove-Item -LiteralPath $LibreFolder -Recurse -Force }
        Move-Item -LiteralPath $ExtractedLibre -Destination $LibreFolder
        if (Test-Path $Extract) { Remove-Item -LiteralPath $Extract -Recurse -Force }
    }
}
Write-Host 'Checking Word and PDF generation with sample content...'
& $PythonExe (Join-Path $PSScriptRoot 'check-desktop.py')
if ($LASTEXITCODE -ne 0) { throw 'Desktop verification failed. Check the message above before sharing the folder.' }
'USECTA portable runtime prepared; check-desktop.py passed.' |
    Set-Content -LiteralPath (Join-Path $Runtime 'ready.txt') -Encoding UTF8
& (Join-Path $PSScriptRoot 'create-desktop-shortcuts.ps1')
Write-Host ''
Write-Host 'Ready. Use the USECTA Documents shortcut on your desktop.'
Write-Host 'To prepare a pendrive folder, double-click Make USB copy.bat.'
