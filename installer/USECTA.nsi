Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"

!ifndef BUILDROOT
  !define BUILDROOT ".."
!endif
!define VERSION "1.0.4"
!define APPNAME "USECTA Document Generator"
!define EXENAME "USECTA-Document-Generator.exe"
!define UNINSTALLKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\USECTA-Document-Generator"

Name "${APPNAME}"
OutFile "${BUILDROOT}\release\USECTA-Document-Generator-Setup-${VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\USECTA Document Generator"
InstallDirRegKey HKCU "Software\USECTA\DocumentGenerator" "InstallDir"
RequestExecutionLevel user
; Favor quick builds/extraction over the smallest possible pendrive download.
SetCompressor /SOLID zlib
BrandingText "USECTA (Pvt) Ltd — offline edition"
VIProductVersion "1.0.4.0"
VIAddVersionKey "ProductName" "${APPNAME}"
VIAddVersionKey "CompanyName" "USECTA (Pvt) Ltd"
VIAddVersionKey "FileDescription" "Offline Windows installer"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "USECTA (Pvt) Ltd"

!define MUI_ABORTWARNING
!define MUI_ICON "${BUILDROOT}\assets\usecta-icon.ico"
!define MUI_UNICON "${BUILDROOT}\assets\usecta-icon.ico"
!define MUI_WELCOMEPAGE_TEXT "Install USECTA Document Generator on this computer.$\r$\n$\r$\nPython, templates and the PDF converter are included. Installation and use do not require internet access.$\r$\n$\r$\nExisting local records are preserved."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXENAME}"
!define MUI_FINISHPAGE_RUN_TEXT "Open USECTA Document Generator"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function CheckRunning
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "USECTA-Document-Generator") p .r0'
  ${If} $0 != 0
    System::Call 'kernel32::CloseHandle(p r0)'
    MessageBox MB_ICONEXCLAMATION "USECTA is running. Click Exit application in its sidebar before installing or updating." /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
FunctionEnd

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "A 64-bit Windows computer is required." /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "Windows 10 or newer is required." /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
  SetShellVarContext current
  Call CheckRunning
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${BUILDROOT}\dist\USECTA-Document-Generator\*"
  File "${BUILDROOT}\OFFLINE_USER_GUIDE.md"
  File "${BUILDROOT}\THIRD_PARTY_NOTICES.md"
  ${If} ${Errors}
    MessageBox MB_ICONSTOP "Installation could not finish. Check free disk space and folder permissions, then run setup again." /SD IDOK
    SetErrorLevel 1
    Abort
  ${EndIf}
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\USECTA Document Generator"
  CreateShortcut "$SMPROGRAMS\USECTA Document Generator\USECTA Document Generator.lnk" "$INSTDIR\${EXENAME}"
  CreateShortcut "$DESKTOP\USECTA Document Generator.lnk" "$INSTDIR\${EXENAME}"
  WriteRegStr HKCU "Software\USECTA\DocumentGenerator" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALLKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "${UNINSTALLKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTALLKEY}" "Publisher" "USECTA (Pvt) Ltd"
  WriteRegStr HKCU "${UNINSTALLKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALLKEY}" "DisplayIcon" "$INSTDIR\${EXENAME}"
  WriteRegStr HKCU "${UNINSTALLKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINSTALLKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALLKEY}" "NoRepair" 1
SectionEnd

Function un.onInit
  SetShellVarContext current
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "USECTA-Document-Generator") p .r0'
  ${If} $0 != 0
    System::Call 'kernel32::CloseHandle(p r0)'
    MessageBox MB_ICONEXCLAMATION "Close USECTA using Exit application before uninstalling." /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
FunctionEnd

Section "Uninstall"
  ; Only package-owned paths are removed. The separate user workspace is retained.
  Delete "$INSTDIR\${EXENAME}"
  Delete "$INSTDIR\OFFLINE_USER_GUIDE.md"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\USECTA Document Generator.lnk"
  Delete "$SMPROGRAMS\USECTA Document Generator\USECTA Document Generator.lnk"
  RMDir "$SMPROGRAMS\USECTA Document Generator"
  DeleteRegKey HKCU "${UNINSTALLKEY}"
  DeleteRegKey HKCU "Software\USECTA\DocumentGenerator"
SectionEnd
