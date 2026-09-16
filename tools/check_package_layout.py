#!/usr/bin/env python3
"""Validate the release-zip shape consumed by the KNLMeansCL build hook."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import PurePosixPath


PACKAGE_NAME = "knlmeanscl"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate a KNLMeansCL release zip.")
    parser.add_argument("artifact_zip")
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--required", action="append", default=[])
    args = parser.parse_args(argv)

    archive = PurePosixPath(args.artifact_zip)
    with zipfile.ZipFile(args.artifact_zip) as zf:
        files = [PurePosixPath(name.replace("\\", "/")) for name in zf.namelist() if not name.endswith("/")]
        roots = {path.parts[0] for path in files if path.parts}
        if roots != {PACKAGE_NAME}:
            raise RuntimeError(f"expected exactly one top-level {PACKAGE_NAME}/ directory, found {sorted(roots)}")
        expected = {args.plugin, "manifest.vs", *args.required}
        names = {str(path.relative_to(PACKAGE_NAME)) for path in files}
        missing = sorted(expected - names)
        if missing:
            raise FileNotFoundError(f"release zip is missing: {', '.join(missing)}")
        manifest = zf.read(f"{PACKAGE_NAME}/manifest.vs").decode("ascii")
        if manifest != f"[VapourSynth Manifest V1]\n{PACKAGE_NAME}\n":
            raise RuntimeError("manifest.vs does not name exactly the knlmeanscl plugin")
    print(f"artifact={archive}")
    print(f"files={len(files)}")
    print("layout=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
