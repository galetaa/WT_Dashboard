"""Discover native/Steam War Thunder installs, including secondary libraries."""
import os
import re
import sys
from pathlib import Path

_observed_game_dirs = set()


def game_processes():
    import psutil
    return [p for p in psutil.process_iter(["name", "exe", "cwd"])
            if (p.info.get("name") or "").casefold() in {"aces", "aces.exe"}]


def registry_value(hive, key, name):
    import winreg
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(getattr(winreg, hive), key, 0, winreg.KEY_READ | view) as handle:
                return winreg.QueryValueEx(handle, name)[0]
        except OSError:
            continue
    return None


def vdf_values(text, key):
    # Steam paths use quoted VDF strings, escaping backslashes and quotes.
    pattern = r'"' + re.escape(key) + r'"\s+"((?:\\.|[^"\\])*)"'
    return [re.sub(r'\\([\\"])', r'\1', value) for value in re.findall(pattern, text)]


def steam_game_directories(steam):
    libraries = [steam]
    try:
        text = (steam / "steamapps/libraryfolders.vdf").read_text(encoding="utf-8")
        libraries.extend(Path(p) for p in vdf_values(text, "path"))
    except OSError:
        pass
    result = []
    for library in libraries:
        manifest = library / "steamapps/appmanifest_236390.acf"
        try:
            names = vdf_values(manifest.read_text(encoding="utf-8"), "installdir")
        except OSError:
            names = []
        for name in names:
            # Install names are local directory names, never absolute paths.
            if name and not any(c in name for c in '/\\:') and name not in {'.', '..'}:
                result.append(library / "steamapps/common" / name)
        result.append(library / "steamapps/common/War Thunder")
    return result


def game_directories():
    result = list(_observed_game_dirs)
    if os.environ.get("WT_GAME_DIR"):
        result.append(Path(os.environ["WT_GAME_DIR"]).expanduser())
    for process in game_processes():
        executable = process.info.get("exe")
        if executable:
            folder = Path(executable).parent
            result.append(folder.parent if folder.name.casefold() in {"win32", "win64", "linux64", "macosx", "macosx64"} else folder)
        if process.info.get("cwd"):
            result.append(Path(process.info["cwd"]))
    _observed_game_dirs.update(result)
    roots = []
    if sys.platform == "win32":
        for hive in ("HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"):
            installed = registry_value(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 236390", "InstallLocation")
            if installed:
                result.append(Path(installed))
        steam = registry_value("HKEY_CURRENT_USER", r"SOFTWARE\Valve\Steam", "SteamPath")
        if steam:
            roots.append(Path(steam))
        for variable in ("ProgramFiles(x86)", "ProgramFiles"):
            if os.environ.get(variable):
                roots.append(Path(os.environ[variable]) / "Steam")
    elif sys.platform == "darwin":
        roots.append(Path.home() / "Library/Application Support/Steam")
        result.extend([Path("/Applications/WarThunderLauncher.app/Contents/WarThunder"),
                       Path.home() / "Applications/WarThunderLauncher.app/Contents/WarThunder"])
    else:
        roots.extend([Path.home() / ".steam/steam", Path.home() / ".local/share/Steam",
                      Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam"])
    # A macOS client executable lives inside the game's .app bundle.
    for folder in list(result):
        if folder.name == "MacOS" and folder.parent.name == "Contents":
            result.append(folder.parent.parent.parent)
    for root in dict.fromkeys(roots):
        result.extend(steam_game_directories(root))
    if sys.platform == "darwin":
        for folder in list(result):
            for suffix in ("WarThunderLauncher.app/Contents/WarThunder.app/Contents/Resources/game",
                           "WarThunderLauncher/Contents/WarThunder/Contents/Resources/game",
                           "Contents/Resources/game"):
                nested = folder / suffix
                if nested.is_dir():
                    result.append(nested)
    return list(dict.fromkeys(result))
