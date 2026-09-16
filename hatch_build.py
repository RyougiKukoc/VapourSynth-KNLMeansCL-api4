from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging import tags


ROOT = Path(__file__).resolve().parent
PLUGIN_NAME = "knlmeanscl"
DEFAULT_REPOSITORY = "RyougiKukoc/VapourSynth-KNLMeansCL-api4"
WINDOWS_PREBUILT_ASSET = "knlmeanscl-msys2-ucrt64.zip"
LINUX_PREBUILT_ASSET = "knlmeanscl-linux-x86_64.zip"


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() not in {"", "0", "false", "no", "off"})


def _project_version() -> str:
    override = os.environ.get("KNLMEANSCL_PREBUILT_VERSION")
    if override:
        return override
    with (ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError("project.version missing from pyproject.toml")
    return version


def _default_prebuilt_asset() -> str:
    if sys.platform == "linux" and platform.machine().lower() in {"amd64", "x86_64"}:
        return LINUX_PREBUILT_ASSET
    return WINDOWS_PREBUILT_ASSET


def _default_prebuilt_url(version: str) -> str:
    repository = os.environ.get("KNLMEANSCL_PREBUILT_REPOSITORY") or os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPOSITORY
    tag = os.environ.get("KNLMEANSCL_PREBUILT_TAG") or f"v{version}"
    asset = os.environ.get("KNLMEANSCL_PREBUILT_ASSET_NAME") or _default_prebuilt_asset()
    return f"https://github.com/{repository}/releases/download/{tag}/{asset}"


def _prebuilt_source(version: str) -> tuple[str, bool]:
    explicit = os.environ.get("KNLMEANSCL_PREBUILT_URL")
    if explicit:
        return explicit, True
    return _default_prebuilt_url(version), False


def _supports_prebuilt() -> bool:
    return sys.platform in {"win32", "linux"} and platform.machine().lower() in {"amd64", "x86_64"}


def _plugin_filename() -> str:
    if sys.platform == "win32":
        return f"{PLUGIN_NAME}.dll"
    if sys.platform == "darwin":
        return f"{PLUGIN_NAME}.dylib"
    return f"{PLUGIN_NAME}.so"


def _fetch_prebuilt_archive(source: str, destination: Path) -> None:
    candidate = Path(source)
    if candidate.exists():
        shutil.copy2(candidate, destination)
        return

    request = urllib.request.Request(source, headers={"User-Agent": "vapoursynth-knlm-build-hook"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _write_manifest(target_dir: Path) -> None:
    (target_dir / "manifest.vs").write_text(
        "[VapourSynth Manifest V1]\n"
        f"{PLUGIN_NAME}\n",
        encoding="ascii",
        newline="\n",
    )


def _stage_prebuilt_plugin(version: str, target_dir: Path) -> bool:
    if _truthy(os.environ.get("KNLMEANSCL_FORCE_BUILD")):
        print("KNLMeansCL wheel build: skipping prebuilt asset because KNLMEANSCL_FORCE_BUILD is set")
        return False
    if not _supports_prebuilt():
        print("KNLMeansCL wheel build: no matching release asset for this platform; falling back to a native Meson build")
        return False

    source, explicit = _prebuilt_source(version)
    asset_name = Path(source).name or _default_prebuilt_asset()
    try:
        with tempfile.TemporaryDirectory(prefix="knlmeanscl-prebuilt-") as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            archive_path = temp_dir / asset_name
            _fetch_prebuilt_archive(source, archive_path)
            with zipfile.ZipFile(archive_path) as zf:
                package_members = [
                    name
                    for name in zf.namelist()
                    if name.replace("\\", "/").startswith(f"{PLUGIN_NAME}/") and not name.endswith("/")
                ]
                if not package_members:
                    raise FileNotFoundError(f"prebuilt archive does not contain a {PLUGIN_NAME}/ package directory")
                for member in package_members:
                    normalized = member.replace("\\", "/")
                    relative = normalized.split("/", 1)[1]
                    out_path = target_dir / relative
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, out_path.open("wb") as dst:
                        shutil.copyfileobj(src, dst)

            plugin = target_dir / _plugin_filename()
            if not plugin.exists():
                raise FileNotFoundError(f"prebuilt archive did not provide {_plugin_filename()}")
            if not (target_dir / "manifest.vs").exists():
                _write_manifest(target_dir)
    except Exception as exc:
        if explicit:
            raise RuntimeError(f"failed to use explicit KNLMeansCL prebuilt asset {source!r}") from exc
        print(f"KNLMeansCL wheel build: prebuilt asset unavailable at {source}; falling back to local build ({exc})")
        return False

    print(f"KNLMeansCL wheel build: using prebuilt release asset {source}")
    return True


def _prepend_path_entries(env: dict[str, str], entries: list[Path]) -> None:
    parts = [str(entry) for entry in entries if entry.exists()]
    if not parts:
        return
    existing = env.get("PATH")
    env["PATH"] = os.pathsep.join(parts + ([existing] if existing else []))


def _candidate_msys2_prefixes(env: dict[str, str]) -> list[Path]:
    prefixes: list[Path] = []
    msystem_prefix = env.get("MSYSTEM_PREFIX")
    if msystem_prefix:
        prefixes.append(Path(msystem_prefix))
    prefixes.extend(
        [
            ROOT.parents[2] / "msys2" / "ucrt64",
            Path(r"C:\msys64\ucrt64"),
            Path(r"C:\msys64\mingw64"),
        ]
    )
    seen: set[str] = set()
    result: list[Path] = []
    for prefix in prefixes:
        key = str(prefix).lower()
        if key not in seen:
            seen.add(key)
            result.append(prefix)
    return result


def _find_command(*candidates: str) -> str | None:
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _meson_command() -> list[str]:
    meson = _find_command("meson")
    if meson:
        return [meson]
    for module_name in ("mesonbuild", "mesonbuild.mesonmain"):
        module_runner = [sys.executable, "-m", module_name]
        probe = subprocess.run(module_runner + ["--version"], cwd=ROOT, capture_output=True, text=True)
        if probe.returncode == 0:
            return module_runner
    raise FileNotFoundError("meson executable not found and python -m mesonbuild is unavailable")


def _configure_windows_build_env(env: dict[str, str]) -> dict[str, str]:
    prefixes = _candidate_msys2_prefixes(env)
    path_entries = [Path(sys.executable).resolve().parent / "Scripts"]
    for prefix in prefixes:
        path_entries.extend([prefix / "bin", prefix.parent / "usr" / "bin"])
    _prepend_path_entries(env, path_entries)

    if "PKG_CONFIG" not in env:
        for prefix in prefixes:
            for candidate in (
                prefix.parent / "usr" / "bin" / "pkg-config.exe",
                prefix.parent / "usr" / "bin" / "pkgconf.exe",
                prefix / "bin" / "pkg-config.exe",
                prefix / "bin" / "pkgconf.exe",
            ):
                if candidate.exists():
                    env["PKG_CONFIG"] = str(candidate)
                    break
            if "PKG_CONFIG" in env:
                break

    pc_paths = [
        ROOT / "_ci" / "pkgconfig",
        *(prefix / "lib" / "pkgconfig" for prefix in prefixes),
        *(prefix / "share" / "pkgconfig" for prefix in prefixes),
    ]
    existing_pc = env.get("PKG_CONFIG_PATH")
    if existing_pc:
        pc_paths.extend(Path(part) for part in existing_pc.split(os.pathsep) if part)
    env["PKG_CONFIG_PATH"] = os.pathsep.join(str(path) for path in pc_paths if path.exists() or path.name == "pkgconfig")

    if "CC" not in env or "CXX" not in env:
        for prefix in prefixes:
            gcc = prefix / "bin" / "gcc.exe"
            gxx = prefix / "bin" / "g++.exe"
            if gcc.exists() and "CC" not in env:
                env["CC"] = str(gcc)
            if gxx.exists() and "CXX" not in env:
                env["CXX"] = str(gxx)
            if "CC" in env and "CXX" in env:
                break

    env.setdefault("MSYSTEM", "UCRT64")
    for prefix in prefixes:
        if prefix.exists():
            env.setdefault("MSYSTEM_PREFIX", str(prefix))
            break
    return env


def _configure_non_windows_build_env(env: dict[str, str], build_root: Path) -> dict[str, str]:
    # The VapourSynth wheel owns the API4 headers, library, and pkg-config
    # metadata. Prepend it while preserving a caller-provided search path.
    wheel_root = env.get("KNLMEANSCL_VAPOURSYNTH_ROOT")
    if wheel_root:
        vapoursynth_dir = Path(wheel_root).resolve()
    else:
        try:
            import vapoursynth
        except ImportError as exc:
            raise RuntimeError(
                "native KNLMeansCL builds require VapourSynth in the PEP 517 build environment "
                "or KNLMEANSCL_VAPOURSYNTH_ROOT must point at an extracted wheel's vapoursynth directory"
            ) from exc
        vapoursynth_dir = Path(vapoursynth.__file__).resolve().parent
    pkgconfig_dir = vapoursynth_dir / "pkgconfig"
    include_dir = vapoursynth_dir / "include"
    if not pkgconfig_dir.is_dir() or not include_dir.is_dir():
        raise RuntimeError(f"VapourSynth pkg-config metadata is missing: {pkgconfig_dir}")

    # The R79 wheel ships libvapoursynth.so.4 without the unversioned linker
    # name required by `-lvapoursynth`. Build a private SDK shim instead of
    # mutating site-packages.
    native_libraries = sorted(vapoursynth_dir.glob("libvapoursynth.so.*"))
    if sys.platform == "darwin":
        native_libraries = sorted(vapoursynth_dir.glob("libvapoursynth*.dylib"))
    if not native_libraries:
        raise RuntimeError(f"VapourSynth native library is missing under {vapoursynth_dir}")
    shim_root = build_root / "vapoursynth-sdk"
    shim_lib = shim_root / "lib"
    shim_pc = shim_root / "pkgconfig"
    shim_lib.mkdir(parents=True, exist_ok=True)
    shim_pc.mkdir(parents=True, exist_ok=True)
    native_library = native_libraries[0]
    copied_library = shim_lib / native_library.name
    shutil.copy2(native_library, copied_library)
    if sys.platform == "linux":
        link_name = shim_lib / "libvapoursynth.so"
        try:
            link_name.symlink_to(copied_library.name)
        except OSError:
            shutil.copy2(copied_library, link_name)
    (shim_pc / "vapoursynth.pc").write_text(
        "Name: VapourSynth\n"
        "Description: API4 SDK shim created from the installed VapourSynth wheel\n"
        "Version: 79\n"
        f"Libs: -L{shim_lib} -lvapoursynth\n"
        f"Cflags: -I{include_dir}\n",
        encoding="utf-8",
    )
    existing = env.get("PKG_CONFIG_PATH")
    env["PKG_CONFIG_PATH"] = os.pathsep.join(
        [str(shim_pc), str(pkgconfig_dir)] + ([existing] if existing else [])
    )
    return env


def _run(cmd: list[str], *, env: dict[str, str]) -> None:
    print("+ " + subprocess.list2cmdline(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def _find_built_plugin(build_dir: Path) -> Path:
    suffixes = [".dll"] if sys.platform == "win32" else ([".dylib"] if sys.platform == "darwin" else [".so"])
    for suffix in suffixes:
        for stem in (PLUGIN_NAME, f"lib{PLUGIN_NAME}"):
            candidate = build_dir / f"{stem}{suffix}"
            if candidate.exists():
                return candidate
    matches = [candidate for suffix in suffixes for candidate in build_dir.rglob(f"*{PLUGIN_NAME}*{suffix}")]
    if matches:
        return matches[0]
    raise FileNotFoundError(f"missing built KNLMeansCL plugin under {build_dir}")


def _local_build(target_dir: Path, build_root: Path) -> None:
    env = os.environ.copy()
    if sys.platform == "win32":
        env = _configure_windows_build_env(env)
        _run([sys.executable, "tools/ci_prepare_vapoursynth_pc.py"], env=env)
        env = _configure_windows_build_env(env)
    else:
        env = _configure_non_windows_build_env(env, build_root)

    meson = _meson_command()
    build_dir = build_root / "build"
    _run(
        meson + ["setup", str(build_dir), str(ROOT), "--backend", "ninja", "--buildtype", "release"],
        env=env,
    )
    _run(meson + ["compile", "-C", str(build_dir), "--verbose"], env=env)

    if sys.platform == "win32":
        prefixes = _candidate_msys2_prefixes(env)
        package_dist = build_root / "dist"
        package_cmd = [
            sys.executable,
            "tools/ci_package_msys2.py",
            "--build-dir",
            str(build_dir),
            "--dist-dir",
            str(package_dist),
            "--clean",
        ]
        for prefix in prefixes:
            for search_dir in (prefix / "bin", prefix.parent / "usr" / "bin"):
                if search_dir.exists():
                    package_cmd.extend(["--search-dir", str(search_dir)])
        objdump = next((prefix / "bin" / "objdump.exe" for prefix in prefixes if (prefix / "bin" / "objdump.exe").exists()), None)
        if objdump is not None:
            package_cmd.extend(["--objdump", str(objdump)])
        _run(package_cmd, env=env)
        built_package = package_dist / PLUGIN_NAME
        if not built_package.is_dir():
            raise FileNotFoundError(f"missing built package directory: {built_package}")
        for path in sorted(built_package.rglob("*")):
            if path.is_file():
                output = target_dir / path.relative_to(built_package)
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, output)
    else:
        shutil.copy2(_find_built_plugin(build_dir), target_dir / _plugin_filename())
        if sys.platform == "linux":
            _run([sys.executable, "tools/ci_package_linux.py", "--plugin", str(target_dir / _plugin_filename())], env=env)

    _write_manifest(target_dir)


class CustomHook(BuildHookInterface[Any]):
    build_root = ROOT / "build-wheel"
    dist_dir = ROOT / "vapoursynth" / "plugins" / PLUGIN_NAME

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        del version
        build_data["pure_python"] = False
        project_version = _project_version()

        shutil.rmtree(self.build_root, ignore_errors=True)
        shutil.rmtree(self.dist_dir.parent.parent, ignore_errors=True)
        self.build_root.mkdir(parents=True, exist_ok=True)
        self.dist_dir.mkdir(parents=True, exist_ok=True)

        used_prebuilt = _stage_prebuilt_plugin(project_version, self.dist_dir)
        if not used_prebuilt:
            _local_build(self.dist_dir, self.build_root)

        platform_tag = os.environ.get("KNLMEANSCL_PLATFORM_TAG")
        if not platform_tag and used_prebuilt and sys.platform == "linux":
            platform_tag = "manylinux_2_27_x86_64"
        build_data["tag"] = f"py3-none-{platform_tag or next(tags.platform_tags())}"

    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        del version, build_data, artifact_path
        shutil.rmtree(self.build_root, ignore_errors=True)
        shutil.rmtree(self.dist_dir.parent.parent, ignore_errors=True)
