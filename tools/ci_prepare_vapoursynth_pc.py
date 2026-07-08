from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    import vapoursynth

    pkg = Path(vapoursynth.__file__).resolve().parent
    include = pkg / "include"
    for path in [include / "VapourSynth4.h", include / "VSHelper4.h"]:
        if not path.exists():
            raise FileNotFoundError(path)

    out = ROOT / "_ci" / "pkgconfig"
    out.mkdir(parents=True, exist_ok=True)
    pc = out / "vapoursynth.pc"
    pc.write_text(
        "\n".join(
            [
                "Name: vapoursynth",
                "Description: VapourSynth R77 API4 headers from wheel",
                "Version: 77",
                "Libs:",
                f"Cflags: -I{include.as_posix()}",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"VAPOURSYNTH_PKG={pkg}")
    print(f"PKG_CONFIG_PATH={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
