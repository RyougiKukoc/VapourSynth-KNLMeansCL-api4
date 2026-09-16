#!/usr/bin/env python3
"""Stage the Linux runtime closure required by a KNLMeansCL plugin payload."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


SYSTEM_LIBRARIES = (
    "linux-vdso",
    "ld-linux",
    "libc.so",
    "libm.so",
    "libpthread.so",
    "librt.so",
    "libdl.so",
    "libutil.so",
    "libresolv.so",
    "libvapoursynth.so",
)
RUNTIME_LIBRARIES = (
    "libOpenCL.so",
    "libboost_",
    "libstdc++.so",
    "libgcc_s.so",
)


def ldd_dependencies(binary: Path) -> list[tuple[str, Path]]:
    completed = subprocess.run(["ldd", str(binary)], check=True, capture_output=True, text=True)
    dependencies: list[tuple[str, Path]] = []
    for line in completed.stdout.splitlines():
        missing = re.match(r"\s*([^\s]+)\s+=>\s+not found", line)
        if missing:
            name = missing.group(1)
            if name.startswith("libvapoursynth.so"):
                # Supplied by the installed VapourSynth wheel at runtime.
                continue
            raise FileNotFoundError(f"unresolved dynamic dependency for {binary}: {line.strip()}")
        match = re.match(r"\s*([^\s]+)\s+=>\s+([^\s]+)\s+", line)
        if not match:
            continue
        name, location = match.groups()
        path = Path(location)
        if not path.exists():
            raise FileNotFoundError(f"unresolved dynamic dependency for {binary}: {line.strip()}")
        dependencies.append((name, path))
    return dependencies


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Package Linux runtime libraries for KNLMeansCL.")
    parser.add_argument("--plugin", required=True, help="Staged knlmeanscl.so path.")
    args = parser.parse_args(argv)

    plugin = Path(args.plugin).resolve()
    if sys.platform != "linux":
        raise RuntimeError("ci_package_linux.py must run on Linux")
    if not plugin.is_file():
        raise FileNotFoundError(plugin)

    package_dir = plugin.parent
    pending = [plugin]
    seen: set[Path] = set()
    copied: list[Path] = []
    while pending:
        binary = pending.pop()
        if binary in seen:
            continue
        seen.add(binary)
        for name, source in ldd_dependencies(binary):
            if name.startswith(SYSTEM_LIBRARIES):
                continue
            if not name.startswith(RUNTIME_LIBRARIES):
                raise RuntimeError(f"unclassified dynamic dependency for {binary.name}: {name} ({source})")
            destination = package_dir / name
            if not destination.exists():
                shutil.copy2(source, destination)
                copied.append(destination)
            pending.append(destination)

    loader = package_dir / "libOpenCL.so.1"
    if not loader.exists():
        raise FileNotFoundError(f"Linux payload did not stage required OpenCL loader: {loader}")
    print(f"plugin={plugin}")
    for path in copied:
        print(f"runtime={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
