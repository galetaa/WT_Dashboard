"""Build a native executable and portable release archive on the target OS."""
import argparse
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def target_name():
    system = {"win32":"windows", "darwin":"macos"}.get(sys.platform,"linux")
    machine = platform.machine().lower()
    arch = {"amd64":"x86_64", "aarch64":"arm64"}.get(machine,machine)
    return f"wt-dashboard-{system}-{arch}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary-only",action="store_true")
    args = parser.parse_args()
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--clean","--onefile",
                    "--name","wt-dashboard","--paths","backend","--add-data",
                    "frontend"+(';' if sys.platform=='win32' else ':')+"frontend",
                    "--collect-submodules","uvicorn","backend/main.py"],cwd=ROOT,check=True)
    if args.binary_only:
        return
    name = target_name()
    folder = ROOT / "build/release" / name
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    binary = "wt-dashboard.exe" if sys.platform == "win32" else "wt-dashboard"
    shutil.copy2(ROOT / "dist" / binary,folder / binary)
    shutil.copy2(ROOT / "README.md",folder / "README.md")
    shutil.copy2(ROOT / "docs/PLATFORMS.md",folder / "PLATFORMS.md")
    if sys.platform == "win32":
        archive = ROOT / "dist" / (name+".zip")
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as stream:
            for path in sorted(folder.rglob("*")):
                stream.write(path,path.relative_to(folder.parent))
    else:
        archive = ROOT / "dist" / (name+".tar.gz")
        with tarfile.open(archive,"w:gz") as stream:
            stream.add(folder,arcname=name)
    print(f"Release archive: {archive}")


if __name__ == "__main__":
    main()
