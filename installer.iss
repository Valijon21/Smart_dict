; Inno Setup Script — Vocab Master Pro Professional Windows Installer
; Ushbu skript orqali to'liq Windows O'rnatuvchi (VocabMaster_Setup_v1.0.0.exe) yaratiladi.
; Desktop Shortcut, Start Menu, Icon va Uninstaller to'liq ta'minlanadi.

#define MyAppName "Vocab Master Pro"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SmartDict"
#define MyAppURL "https://github.com/SmartDict"
#define MyAppExeName "VocabMaster.exe"

[Setup]
; Standart o'rnatish parametrlari
AppId={{D9A834B7-8C7E-4E65-B857-8547A5A0A1C2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=README.md
OutputDir=dist
OutputBaseFilename=VocabMaster_Setup_v{#MyAppVersion}
SetupIconFile=app.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; dist\VocabMaster papkasidagi barcha fayllarni dastur papkasiga nusxalash
Source: "dist\VocabMaster\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; DIQQAT: Foydalanuvchi ma'lumotlar bazasi (vocab.db) o'rnatish paytida o'chib ketmasligi uchun:
; vocab.db fayli uninstaller tomonidan o'chirilmaydi.

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
