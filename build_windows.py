"""Gera o programa (pasta dist) e o instalador (installer_output) do Simulador UCE II."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "Simulador_Armazenagem_UCE_II"
VENV = Path(os.environ.get("TEMP", str(ROOT))) / "uce2_build_venv"   # caminho curto: evita erro de DLL


def run(cmd, **kw):
    print("\n>", " ".join(map(str, cmd)))
    subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def find_iscc():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                 str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs")):
        if base and (Path(base) / "Inno Setup 6" / "ISCC.exe").exists():
            return Path(base) / "Inno Setup 6" / "ISCC.exe"
    return None


def main():
    if os.name != "nt":
        raise SystemExit("Execute este arquivo no Windows.")
    if not (3, 10) <= sys.version_info[:2] <= (3, 13):
        raise SystemExit(f"Use Python 3.10 a 3.13 (encontrado {sys.version.split()[0]}).")

    # 1. Ambiente isolado com as versões testadas
    py = VENV / "Scripts" / "python.exe"
    if not py.exists():
        run([sys.executable, "-m", "venv", str(VENV)])
    run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(ROOT / "requirements.txt")])

    # 2. Programa em pasta (--onedir): abre rápido e é menos barrado por antivírus que --onefile
    for folder in ("build", "dist"):
        if (ROOT / folder).exists():
            shutil.rmtree(ROOT / folder)
    run([str(py), "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
         "--name", NAME, "--icon", str(ROOT / "simulador.ico"),
         "--add-data", f"{ROOT / 'simulador.ico'};.",
         "--add-data", f"{ROOT / 'logo_72.png'};.",
         "--add-data", f"{ROOT / 'logo_simulador.jpg'};.",
         "--exclude-module", "PyQt5", "--exclude-module", "PySide6",
         str(ROOT / "simulador_desktop.py")])
    exe = ROOT / "dist" / NAME / (NAME + ".exe")

    # 3. Autoteste do programa gerado (relatórios, PDF, documentos)
    teste = ROOT / "build" / "autoteste"
    run([str(exe), "--selftest", str(teste)])
    print((teste / "selftest.txt").read_text(encoding="utf-8"))

    # 4. Instalador
    iscc = find_iscc()
    if iscc:
        run([str(iscc), "/Q", str(ROOT / "installer.iss")])
        print("\nINSTALADOR:", next((ROOT / "installer_output").glob("Setup_*.exe")))
    else:
        print("\nInno Setup 6 não encontrado: instale em https://jrsoftware.org/isdl.php e rode de novo para gerar o instalador.")
    print("PROGRAMA:", exe)


if __name__ == "__main__":
    main()
