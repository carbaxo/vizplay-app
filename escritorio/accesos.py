r"""
Crea (o rehace) los accesos directos «VizPlay» en el escritorio y en el menú
Inicio, con el icono de la app.

    .venv\Scripts\python -m escritorio.accesos

Apuntan a pythonw.exe del entorno y no al .bat: así no parpadea una consola al
abrir. Si el entorno se borra, vuelve a pasar por arrancar-escritorio.bat (que
lo recrea) y después ejecuta esto otra vez.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent


def main() -> int:
    pythonw = RAIZ / ".venv" / "Scripts" / "pythonw.exe"
    icono = AQUI / "icono.ico"
    if not pythonw.exists():
        print("No está el entorno (.venv). Arranca antes arrancar-escritorio.bat.")
        return 1
    if not icono.exists():
        from .icono import main as genera_icono
        genera_icono()
    # WScript.Shell desde PowerShell: viene con Windows y no hace falta pywin32.
    # Las carpetas se piden al sistema (el escritorio puede estar en OneDrive).
    ps = rf"""
$sh = New-Object -ComObject WScript.Shell
$destinos = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))
foreach ($d in $destinos) {{
  $lnk = Join-Path $d 'VizPlay.lnk'
  $s = $sh.CreateShortcut($lnk)
  $s.TargetPath = '{pythonw}'
  $s.Arguments = '-m escritorio'
  $s.WorkingDirectory = '{RAIZ}'
  $s.IconLocation = '{icono},0'
  $s.Description = 'VizPlay: películas y series por streaming con Real-Debrid'
  $s.Save()
  Write-Output $lnk
}}
"""
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip() or "No se pudieron crear los accesos directos.")
        return 1
    for linea in r.stdout.split("\n"):
        if linea.strip():
            print("creado:", linea.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
