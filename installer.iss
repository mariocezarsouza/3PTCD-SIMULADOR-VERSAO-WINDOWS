; Instalador do Simulador Inteligente de Armazenagem - UCE II (desktop)
; Gere antes o programa com GERAR_INSTALADOR.bat (ou build_windows.py).

#define AppName "Simulador Inteligente de Armazenagem - UCE II"
#define AppVersion "4.6.0"
#define AppExe "Simulador_Armazenagem_UCE_II.exe"

[Setup]
; Mesmo AppId das versões 4.x: o Setup atualiza a instalação anterior.
AppId={{92DA47C4-48DA-4FC1-9971-4239C7F24D2D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Faculdade SENAI Contagem - Projeto UCE II
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\Simulador Armazenagem UCE II Desktop
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=Setup_Simulador_Armazenagem_UCE_II_Desktop_v{#AppVersion}
SetupIconFile=simulador.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} {#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; Flags: unchecked

[InstallDelete]
; Restos do formato antigo (--onefile) que não são mais usados
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\Simulador_Armazenagem_UCE_II\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LEIA-ME.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Pasta de dados e documentos"; Filename: "{localappdata}\SimuladorArmazenagemUCEII"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Dirs]
Name: "{localappdata}\SimuladorArmazenagemUCEII\relatorios"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o simulador"; Flags: nowait postinstall skipifsilent

; Os dados do usuário (documentos, banco e último cenário) ficam em
; %LOCALAPPDATA%\SimuladorArmazenagemUCEII e NÃO são apagados ao desinstalar.
