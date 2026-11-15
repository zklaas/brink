; Inno Setup script: the Windows installer for Brink.
; Built by .github/workflows/release.yml from PyInstaller's dist\Brink folder:
;   iscc /DAppVersion=1.0.0 packaging\brink.iss
; Installs for the current user only (no administrator rights), adds a Start-menu
; entry and an uninstaller (Settings > Apps).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{F28F7F2E-7135-578B-A040-5076C58F666F}
AppName=Brink
AppVersion={#AppVersion}
AppPublisher=Zachary Klaas
AppPublisherURL=https://github.com/zklaas/brink
DefaultDirName={localappdata}\Programs\Brink
DefaultGroupName=Brink
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=Brink-Setup-Windows
SetupIconFile=..\icons\brink.ico
UninstallDisplayIcon={app}\Brink.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\Brink\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Brink"; Filename: "{app}\Brink.exe"
Name: "{userdesktop}\Brink"; Filename: "{app}\Brink.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\Brink.exe"; Description: "Start Brink"; Flags: nowait postinstall skipifsilent
