; PixelForgeAI - Inno Setup installer script
;
; Build after PyInstaller produces dist\PixelForgeAI\:
;
;   pyinstaller packaging/pixelforgeai.spec --noconfirm
;   iscc packaging\installer.iss
;
; Output: dist\installer\PixelForgeAI-Setup-1.0.0.exe

#define MyAppName        "PixelForgeAI"
#define MyAppVersion     "1.0.0"
#define MyAppPublisher   "PixelForgeAI"
#define MyAppSupportEmail "support@pixelforgeai.local"
#define MyAppURL         "https://pixelforgeai.local"
#define MyAppExeName     "PixelForgeAI.exe"

[Setup]
; Stable AppId — keep this constant across versions so upgrades replace in place.
AppId={{B1F7E2A0-9C4D-4E2B-8A1F-3D5E7F9C0A2B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppContact={#MyAppSupportEmail}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=PixelForgeAI-Setup-1.0.0
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Onedir build output. recursesubdirs pulls in themes/, models/, rembg data, etc.
Source: "..\dist\PixelForgeAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
