from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD_DIR = ROOT / "builddir"
DEFAULT_DIST_DIR = ROOT / "dist" / "msys2-ucrt64"
PACKAGE_NAME = "knlmeanscl"
PLUGIN_DLL = "knlmeanscl.dll"

SYSTEM_DLLS = {
    "advapi32.dll",
    "cfgmgr32.dll",
    "comdlg32.dll",
    "gdi32.dll",
    "kernel32.dll",
    "oleaut32.dll",
    "shell32.dll",
    "user32.dll",
    "version.dll",
    "winspool.drv",
    "ws2_32.dll",
    "bcrypt.dll",
    "msvcrt.dll",
    "ntdll.dll",
    "ole32.dll",
}


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def split_path(value: str) -> list[Path]:
    return [Path(p) for p in value.split(os.pathsep) if p]


def default_search_dirs() -> list[Path]:
    dirs = split_path(os.environ.get("PATH", ""))
    runner_temp = os.environ.get("RUNNER_TEMP")
    if runner_temp:
        runner_msys2 = Path(runner_temp) / "msys64"
        dirs.extend([runner_msys2 / "ucrt64" / "bin", runner_msys2 / "usr" / "bin"])
    for candidate in [
        Path(r"C:\msys64\ucrt64\bin"),
        Path(r"C:\msys64\usr\bin"),
        ROOT.parents[2] / "msys2" / "ucrt64" / "bin",
        ROOT.parents[2] / "msys2" / "usr" / "bin",
    ]:
        if candidate.exists():
            dirs.append(candidate)
    return unique_paths(dirs)


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.resolve() if path.exists() else path).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def find_tool(name: str, search_dirs: list[Path]) -> Path:
    found = shutil.which(name)
    if found:
        return Path(found)
    for directory in search_dirs:
        candidate = directory / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(name)


def find_file(name: str, search_dirs: list[Path]) -> Path:
    for directory in search_dirs:
        candidate = directory / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(name)


def find_plugin(build_dir: Path) -> Path:
    for name in ["knlmeanscl.dll", "libknlmeanscl.dll"]:
        candidate = build_dir / name
        if candidate.exists():
            return candidate
    matches = sorted(build_dir.rglob("*knlmeanscl*.dll"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"KNLMeansCL DLL under {build_dir}")


def dll_dependencies(objdump: Path, dll: Path) -> list[str]:
    completed = run([str(objdump), "-p", str(dll)])
    deps: list[str] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line.startswith("DLL Name: "):
            deps.append(line.removeprefix("DLL Name: "))
    return deps


def collect_runtime_dlls(pkg_dir: Path, search_dirs: list[Path], objdump: Path) -> None:
    queue = sorted(pkg_dir.glob("*.dll"))
    seen: set[str] = set()
    while queue:
        dll = queue.pop(0)
        key = dll.name.lower()
        if key in seen:
            continue
        seen.add(key)
        for dep in dll_dependencies(objdump, dll):
            dep_key = dep.lower()
            if dep_key in SYSTEM_DLLS or dep_key.startswith("api-ms-win-"):
                continue
            dst = pkg_dir / dep
            if dst.exists():
                if dep_key not in seen:
                    queue.append(dst)
                continue
            try:
                src = find_file(dep, search_dirs)
            except FileNotFoundError:
                print(f"warning: dependency not found in search dirs: {dep}", file=sys.stderr)
                continue
            shutil.copy2(src, dst)
            queue.append(dst)


def write_manifest(pkg_dir: Path) -> None:
    (pkg_dir / "manifest.vs").write_text(
        "[VapourSynth Manifest V1]\nknlmeanscl\n",
        encoding="ascii",
        newline="\n",
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Package KNLMeansCL MSYS2/UCRT64 build output.")
    parser.add_argument("--build-dir", default=str(DEFAULT_BUILD_DIR))
    parser.add_argument("--dist-dir", default=str(DEFAULT_DIST_DIR))
    parser.add_argument("--search-dir", action="append", default=[])
    parser.add_argument("--objdump")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)

    build_dir = Path(args.build_dir).resolve()
    dist_dir = Path(args.dist_dir).resolve()
    pkg_dir = dist_dir / PACKAGE_NAME
    search_dirs = unique_paths([Path(p).resolve() for p in args.search_dir] + default_search_dirs())
    objdump = Path(args.objdump).resolve() if args.objdump else find_tool("objdump.exe", search_dirs)

    if args.clean and dist_dir.exists():
        shutil.rmtree(dist_dir)
    pkg_dir.mkdir(parents=True, exist_ok=True)

    plugin = find_plugin(build_dir)
    opencl = find_file("OpenCL.dll", search_dirs)

    shutil.copy2(plugin, pkg_dir / PLUGIN_DLL)
    shutil.copy2(opencl, pkg_dir / "OpenCL.dll")
    write_manifest(pkg_dir)
    collect_runtime_dlls(pkg_dir, search_dirs, objdump)

    print(f"package_dir={pkg_dir}")
    for path in sorted(pkg_dir.iterdir()):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
