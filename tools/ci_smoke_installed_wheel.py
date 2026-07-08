#!/usr/bin/env python3
"""Smoke test an installed vapoursynth-knlm wheel."""

from __future__ import annotations

import argparse
import json
import site
import sys


NO_DEVICE_MARKERS = (
    "no device",
    "no opencl",
    "cl_device_not_found",
    "device not found",
    "cl_platform_not_found",
    "ocl_utils_unknown_error",
    "oclutilsgetplaformdeviceids",
    "oclutilsgetplatformdeviceids",
)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Smoke test an installed vapoursynth-knlm wheel.")
    parser.add_argument("--exercise-filter", action="store_true", help="Try to render one frame if OpenCL is available.")
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    args = parser.parse_args(argv)

    import vapoursynth as vs  # pylint: disable=import-outside-toplevel

    core = vs.core
    namespace = getattr(core, "knlm", None)
    if namespace is None or not hasattr(namespace, "KNLMeansCL"):
        raise RuntimeError("knlm plugin namespace was not autoloaded from the installed wheel")

    result = {
        "vapoursynth_module": vs.__file__,
        "site_packages": site.getsitepackages(),
        "namespace_loaded": True,
        "callable_loaded": True,
    }

    if args.exercise_filter:
        clip = core.std.BlankClip(format=vs.YUV420P8, width=64, height=48, length=5, color=[96, 128, 128])
        try:
            out = namespace.KNLMeansCL(clip, d=1, a=1, s=1, h=1.2)
            frame = out.get_frame(2)
            stats = dict(core.std.PlaneStats(out).get_frame(2).props)
            result.update(
                {
                    "exercise_filter": True,
                    "exercise_skipped": False,
                    "width": frame.width,
                    "height": frame.height,
                    "format": frame.format.name,
                    "plane_stats_average": float(stats["PlaneStatsAverage"]),
                    "plane_stats_min": float(stats["PlaneStatsMin"]),
                    "plane_stats_max": float(stats["PlaneStatsMax"]),
                }
            )
        except Exception as exc:
            message = str(exc)
            if any(marker in message.lower() for marker in NO_DEVICE_MARKERS):
                result.update(
                    {
                        "exercise_filter": True,
                        "exercise_skipped": True,
                        "exercise_skip_reason": message,
                    }
                )
            else:
                raise

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
