from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


PACKAGE_NAME = "knlmeanscl"


def find_package_dir(input_dir: Path) -> Path:
    if (input_dir / PACKAGE_NAME / "manifest.vs").exists():
        return input_dir / PACKAGE_NAME
    if (input_dir / "manifest.vs").exists():
        return input_dir
    raise FileNotFoundError(f"could not find {PACKAGE_NAME}/manifest.vs under {input_dir}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Create a KNLMeansCL release zip with a top-level plugin directory.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir).resolve()
    output = Path(args.output).resolve()
    package_dir = find_package_dir(input_dir)
    archive_root = package_dir.name

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                zf.write(path, Path(archive_root) / path.relative_to(package_dir))

    print(f"zip={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
