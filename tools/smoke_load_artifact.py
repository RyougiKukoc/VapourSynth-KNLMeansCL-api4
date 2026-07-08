from __future__ import annotations

import argparse
import shutil
import os
import site
import sys
import sysconfig
import tempfile
import zipfile
from pathlib import Path


PACKAGE_NAME = "knlmeanscl"
PLUGIN_DLL = "knlmeanscl.dll"


def resolve_artifact(artifact_dir_arg: str | None, artifact_zip_arg: str | None) -> tuple[Path, Path | None]:
    if artifact_zip_arg:
        archive = Path(artifact_zip_arg).resolve()
        if not archive.exists():
            raise FileNotFoundError(archive)
        temp_dir = Path(tempfile.mkdtemp(prefix="knlmeanscl-package-"))
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(temp_dir)
        return temp_dir, temp_dir
    if artifact_dir_arg is None:
        raise ValueError("--artifact-dir or --artifact-zip is required")
    return Path(artifact_dir_arg).resolve(), None


def find_package_dir(artifact_dir: Path) -> Path:
    candidates = [
        artifact_dir,
        artifact_dir / PACKAGE_NAME,
        artifact_dir / "vapoursynth" / "plugins" / PACKAGE_NAME,
    ]
    for candidate in candidates:
        if (candidate / PLUGIN_DLL).exists():
            return candidate
    raise FileNotFoundError(f"{PLUGIN_DLL} under {artifact_dir}")


def add_dll_dir(path: Path) -> None:
    if path.exists():
        os.add_dll_directory(str(path))


def no_opencl_device(message: str) -> bool:
    lowered = message.lower()
    markers = [
        "no device",
        "no opencl",
        "cl_device_not_found",
        "device not found",
        "cl_platform_not_found",
    ]
    return any(marker in lowered for marker in markers)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Smoke-load a packaged KNLMeansCL artifact.")
    parser.add_argument("--vapoursynth-root", help="VapourSynth portable root or extracted wheel root.")
    parser.add_argument("--artifact-dir")
    parser.add_argument("--artifact-zip")
    parser.add_argument("--autoload", action="store_true", help="Load through VAPOURSYNTH_EXTRA_PLUGIN_PATH.")
    parser.add_argument("--exercise-filter", action="store_true", help="Render one generated frame if OpenCL is available.")
    args = parser.parse_args(argv)

    artifact_root, temp_dir = resolve_artifact(args.artifact_dir, args.artifact_zip)
    package_dir = find_package_dir(artifact_root)
    plugin = package_dir / PLUGIN_DLL
    required = [
        plugin,
        package_dir / "manifest.vs",
        package_dir / "OpenCL.dll",
    ]
    for path in required:
        if not path.exists():
            print(f"missing required path: {path}", file=sys.stderr)
            return 1

    vs_root = Path(args.vapoursynth_root).resolve() if args.vapoursynth_root else None
    dll_dirs = [
        package_dir,
        Path(sys.executable).resolve().parent,
        Path(sysconfig.get_paths().get("platlib", "")),
        Path(sysconfig.get_paths().get("purelib", "")),
        *(Path(p) for p in site.getsitepackages()),
    ]
    if vs_root is not None:
        dll_dirs.extend(
            [
                vs_root,
                vs_root / "Lib" / "site-packages",
                vs_root / "Lib" / "site-packages" / "vapoursynth",
                vs_root / "vapoursynth",
            ]
        )
        for python_path in [
            vs_root,
            vs_root / "Lib" / "site-packages",
        ]:
            if python_path.exists():
                sys.path.insert(0, str(python_path))
    for path in dll_dirs:
        add_dll_dir(path)

    if args.autoload:
        if (artifact_root / PACKAGE_NAME).exists():
            plugin_root = artifact_root
        elif (artifact_root / "vapoursynth" / "plugins").exists():
            plugin_root = artifact_root / "vapoursynth" / "plugins"
        else:
            plugin_root = package_dir.parent
        os.environ["VAPOURSYNTH_EXTRA_PLUGIN_PATH"] = str(plugin_root)

    try:
        import vapoursynth as vs

        if args.autoload:
            try:
                env = vs.create_environment()
                core = env.get_core()
            except AttributeError:
                core = vs.core
        else:
            try:
                env = vs.create_environment(flags=vs.DISABLE_AUTO_LOADING)
                core = env.get_core()
            except AttributeError:
                core = vs.core
            core.std.LoadPlugin(str(plugin))

        if not hasattr(core, "knlm") or not hasattr(core.knlm, "KNLMeansCL"):
            print("core.knlm.KNLMeansCL missing after load", file=sys.stderr)
            return 1
        print(core.knlm.KNLMeansCL)

        if args.exercise_filter:
            try:
                src = core.std.BlankClip(width=64, height=48, format=vs.YUV420P8, length=5, color=[96, 128, 128])
                out = core.knlm.KNLMeansCL(src, d=1, a=1, s=1, h=1.2)
                frame = out.get_frame(2)
                stats = core.std.PlaneStats(out).get_frame(2).props
            except Exception as exc:
                if no_opencl_device(str(exc)):
                    print(f"skipping filter exercise: {exc}", file=sys.stderr)
                    return 0
                print(f"filter exercise failed: {exc}", file=sys.stderr)
                return 1
            if frame.width != 64 or frame.height != 48:
                print(f"unexpected frame size: {frame.width}x{frame.height}", file=sys.stderr)
                return 1
            print(f"PlaneStatsAverage={stats.get('PlaneStatsAverage')}")
        return 0
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
