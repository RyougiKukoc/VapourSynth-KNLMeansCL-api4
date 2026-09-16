#!/usr/bin/env python3
"""Smoke-test the installed KNLMeansCL wheel through VapourSynth autoload."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Any


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


def frame_hash(frame: Any) -> str:
    digest = hashlib.sha256()
    for plane in range(frame.format.num_planes):
        digest.update(bytes(frame[plane]))
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test an installed vapoursynth-knlm wheel.")
    parser.add_argument("--require-opencl", action="store_true", help="Fail unless the GPU OpenCL frame request succeeds.")
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    args = parser.parse_args(argv)

    import vapoursynth as vs  # pylint: disable=import-outside-toplevel

    core = vs.core
    namespace = getattr(core, "knlm", None)
    if namespace is None or not hasattr(namespace, "KNLMeansCL"):
        raise RuntimeError("knlm plugin namespace was not autoloaded from the installed wheel")

    src = core.std.BlankClip(width=64, height=48, format=vs.YUV420P8, length=5, color=[96, 128, 128])
    invalid_rejected = False
    try:
        namespace.KNLMeansCL(src, h=0)
    except vs.Error:
        invalid_rejected = True
    if not invalid_rejected:
        raise RuntimeError("KNLMeansCL accepted invalid h=0")

    result: dict[str, Any] = {
        "vapoursynth_module": vs.__file__,
        "namespace_loaded": True,
        "invalid_h_zero_rejected": True,
        "opencl_frame_executed": False,
    }
    try:
        out = namespace.KNLMeansCL(src, d=1, a=1, s=1, h=1.2, device_type="gpu")
        frames = {number: out.get_frame(number) for number in (0, 2, 4)}
        stats = dict(core.std.PlaneStats(out).get_frame(2).props)
    except vs.Error as exc:
        if not no_opencl_device(str(exc)):
            raise
        result["opencl_unavailable_reason"] = str(exc)
        if args.require_opencl:
            raise RuntimeError(f"OpenCL GPU frame request did not execute: {exc}") from exc
    else:
        result.update(
            {
                "opencl_frame_executed": True,
                "width": frames[2].width,
                "height": frames[2].height,
                "format": frames[2].format.name,
                "frames": out.num_frames,
                "frame_hashes": {number: frame_hash(frame) for number, frame in frames.items()},
                "plane_stats_average": float(stats["PlaneStatsAverage"]),
                "plane_stats_min": float(stats["PlaneStatsMin"]),
                "plane_stats_max": float(stats["PlaneStatsMax"]),
            }
        )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
