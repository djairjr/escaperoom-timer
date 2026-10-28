; installer.iss — Inno Setup Script
; Timer-Nicolau Configurator
; Uso: gere o .exe com PyInstaller primeiro, depois compile este script

[Setup]
AppName=Timer-Nicolau Configurator
AppVersion=1.0
AppPublisher=Timer-Nicolau
DefaultDirName={autopf}\Timer-Nicolau Configurator
DefaultGroupName=Timer-Nicolau
OutputDir=installer_output
OutputBaseFilename=Timer-Nicolau-Configurator-Setup
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\Timer-Nicolau-Configurator.exe
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\Timer-Nicolau-Configurator.exe"; DestDir: "{app}"

[Icons]
Name: "{group}\Timer-Nicolau Configurator"; Filename: "{app}\Timer-Nicolau-Configurator.exe"
Name: "{commondesktop}\Timer-Nicolau Configurator"; Filename: "{app}\Timer-Nicolau-Configurator.exe"

[Run]
Filename: "{app}\Timer-Nicolau-Configurator.exe"; Description: "Executar Timer-Nicolau Configurator"; Flags: postinstall nowait skipifsilent
