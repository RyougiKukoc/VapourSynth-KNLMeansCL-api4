#!/usr/bin/env python3
"""Explicitly load a KNLMeansCL package and report an OpenCL frame request."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


PACKAGE_NAME = "knlmeanscl"


def plugin_suffix() -> str:
    if sys.platform == "win32":
        return ".dll"
    if sys.platform == "darwin":
        return ".dylib"
    return ".so"


def required_runtime(package_dir: Path) -> Path | None:
    if sys.platform == "win32":
        return package_dir / "OpenCL.dll"
    if sys.platform == "linux":
        return package_dir / "libOpenCL.so.1"
    return None


def frame_hash(frame: Any) -> str:
    digest = hashlib.sha256()
    for plane in range(frame.format.num_planes):
        digest.update(bytes(frame[plane]))
    return digest.hexdigest()


def no_opencl_device(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "no device",
            "no opencl",
            "cl_device_not_found",
            "device not found",
            "cl_platform_not_found",
            "ocl_utils_unknown_error",
            "oclutilsgetplaformdeviceids",
            "oclutilsgetplatformdeviceids",
        )
    )


class IsolatedEnvironmentPolicy:
    """Create a core with plugin autoloading disabled."""

    def __init__(self, flags: int) -> None:
        self._api: Any = None
        self._environment: Any = None
        self._flags = flags

    def on_policy_registered(self, api: Any) -> None:
        self._api = api
        self._environment = api.create_environment(self._flags)

    def on_policy_cleared(self) -> None:
        self._api = None
        self._environment = None

    def get_current_environment(self) -> Any:
        return self._environment

    def set_environment(self, environment: Any) -> Any:
        previous = self._environment
        if environment is not None:
            self._environment = environment
        return previous

    def is_alive(self, environment: Any) -> bool:
        return environment is self._environment

    def close(self) -> None:
        if self._api is not None and self._environment is not None:
            self._api.destroy_environment(self._environment)
            self._environment = None


def install_isolated_policy(vs_module: Any) -> IsolatedEnvironmentPolicy | None:
    if not hasattr(vs_module, "register_policy") or vs_module.has_policy():
        return None
    policy = IsolatedEnvironmentPolicy(int(vs_module.DISABLE_AUTO_LOADING))
    vs_module.register_policy(policy)
    return policy


def resolve_artifact(artifact_dir_arg: str | None, artifact_zip_arg: str | None) -> tuple[Path, Path | None]:
    if artifact_zip_arg:
        archive = Path(artifact_zip_arg).resolve()
        if not archive.exists():
            raise FileNotFoundError(archive)
        temp_dir = Path(tempfile.mkdtemp(prefix="knlmeanscl-package-"))
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(temp_dir)
        package_dirs = [path for path in temp_dir.iterdir() if path.is_dir()]
        if len(package_dirs) != 1 or package_dirs[0].name != PACKAGE_NAME:
            raise RuntimeError(f"expected one top-level {PACKAGE_NAME}/ directory in {archive}")
        return package_dirs[0], temp_dir
    if artifact_dir_arg is None:
        raise ValueError("--artifact-dir or --artifact-zip is required")
    artifact_dir = Path(artifact_dir_arg).resolve()
    candidates = [artifact_dir, artifact_dir / PACKAGE_NAME, artifact_dir / "vapoursynth" / "plugins" / PACKAGE_NAME]
    for candidate in candidates:
        if (candidate / f"{PACKAGE_NAME}{plugin_suffix()}").is_file():
            return candidate, None
    raise FileNotFoundError(f"{PACKAGE_NAME}{plugin_suffix()} under {artifact_dir}")


def render_case(core: Any, vs: Any) -> tuple[dict[int, str], dict[str, Any]]:
    src = core.std.BlankClip(width=64, height=48, format=vs.YUV420P8, length=5, color=[96, 128, 128])
    out = core.knlm.KNLMeansCL(src, d=1, a=1, s=1, h=1.2, device_type="gpu")
    frames = {number: out.get_frame(number) for number in (0, 2, 4)}
    stats = dict(core.std.PlaneStats(out).get_frame(2).props)
    return (
        {number: frame_hash(frame) for number, frame in frames.items()},
        {
            "width": frames[2].width,
            "height": frames[2].height,
            "format": frames[2].format.name,
            "frames": out.num_frames,
            "plane_stats_average": float(stats["PlaneStatsAverage"]),
            "plane_stats_min": float(stats["PlaneStatsMin"]),
            "plane_stats_max": float(stats["PlaneStatsMax"]),
        },
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Explicitly smoke-test a packaged KNLMeansCL artifact.")
    parser.add_argument("--artifact-dir")
    parser.add_argument("--artifact-zip")
    parser.add_argument("--require-opencl", action="store_true", help="Fail unless the GPU OpenCL frame request succeeds.")
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    args = parser.parse_args(argv)

    package_dir, temp_dir = resolve_artifact(args.artifact_dir, args.artifact_zip)
    plugin = package_dir / f"{PACKAGE_NAME}{plugin_suffix()}"
    manifest = package_dir / "manifest.vs"
    if not plugin.is_file() or not manifest.is_file():
        raise FileNotFoundError(f"missing plugin or manifest under {package_dir}")
    runtime = required_runtime(package_dir)
    if runtime is not None and not runtime.is_file():
        raise FileNotFoundError(f"missing required runtime: {runtime}")

    dll_handle = None
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        dll_handle = os.add_dll_directory(str(package_dir))

    try:
        import vapoursynth as vs  # pylint: disable=import-outside-toplevel

        policy = install_isolated_policy(vs)
        core = vs.core
        core.std.LoadPlugin(str(plugin))
        if not hasattr(core, "knlm") or not hasattr(core.knlm, "KNLMeansCL"):
            raise RuntimeError("core.knlm.KNLMeansCL missing after explicit LoadPlugin")

        invalid_rejected = False
        try:
            core.knlm.KNLMeansCL(core.std.BlankClip(width=64, height=48, format=vs.YUV420P8), h=0)
        except vs.Error:
            invalid_rejected = True
        if not invalid_rejected:
            raise RuntimeError("KNLMeansCL accepted invalid h=0")

        result: dict[str, Any] = {
            "plugin": str(plugin),
            "manifest": str(manifest),
            "runtime": str(runtime) if runtime is not None else None,
            "namespace_loaded": True,
            "invalid_h_zero_rejected": True,
            "opencl_frame_executed": False,
        }
        try:
            hashes, frame_result = render_case(core, vs)
        except vs.Error as exc:
            if not no_opencl_device(str(exc)):
                raise
            result["opencl_unavailable_reason"] = str(exc)
            if args.require_opencl:
                raise RuntimeError(f"OpenCL GPU frame request did not execute: {exc}") from exc
        else:
            result.update(frame_result)
            result["frame_hashes"] = hashes
            result["opencl_frame_executed"] = True

        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            for key, value in result.items():
                print(f"{key}={value}")
        return 0
    finally:
        if dll_handle is not None:
            dll_handle.close()
        if "policy" in locals() and policy is not None:
            policy.close()
        if temp_dir is not None:
            # Keep the extracted paths alive through all VapourSynth calls, then clean them.
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
