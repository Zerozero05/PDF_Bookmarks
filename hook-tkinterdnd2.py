"""Include the native TkDnD library and Tcl scripts for this Windows build."""

import platform

from PyInstaller.utils.hooks import collect_data_files


# Include both supported Tcl versions; TkinterDnD chooses the runtime variant.
# Restrict the data to the build architecture to avoid shipping other systems.
architecture = "win-arm64" if platform.machine().lower() in {"arm64", "aarch64"} else (
    "win-x64" if platform.architecture()[0] == "64bit" else "win-x86")
datas = collect_data_files("tkinterdnd2", includes=[
    f"tkdnd/{architecture}/*", f"tkdnd/{architecture}-tcl9/*",
])
