"""
Merge OBJ files from a folder into one GLB using Blender CLI backend.
"""

import argparse
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

LOGGER = logging.getLogger("obj_folder_to_glb")
DEFAULT_BLENDER_PATH = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")


def setup_logging(log_file: Path) -> None:
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()
    LOGGER.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)

    LOGGER.addHandler(console_handler)
    LOGGER.addHandler(file_handler)


def collect_obj_files(folder: Path, recursive: bool) -> list[Path]:
    pattern = "**/*.obj" if recursive else "*.obj"
    return sorted([p for p in folder.glob(pattern) if p.is_file()])


def _read_script(filename: str) -> str:
    path = Path(__file__).parent / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"{filename} not found: {path}\n"
            f"{filename} must be in the same directory as obj_folder_to_glb.py"
        )
    return path.read_text(encoding="utf-8")


def _run_blender(
    blender_executable: Path,
    script_text: str,
    script_args: list[str],
    step_name: str,
) -> subprocess.CompletedProcess:
    if not blender_executable.exists() or not blender_executable.is_file():
        raise FileNotFoundError(f"Blender executable not found: {blender_executable}")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(script_text)
            temp_path = Path(tmp.name)

        process = subprocess.run(
            [
                str(blender_executable),
                "--background",
                "--factory-startup",
                "--python", str(temp_path),
                "--",
                *script_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        for line in process.stderr.splitlines():
            lowered = line.lower()
            if "error" in lowered or "traceback" in lowered:
                LOGGER.warning("Blender stderr [%s]: %s", step_name, line)

        if process.returncode != 0:
            raise RuntimeError(
                f"Blender {step_name} failed with exit code {process.returncode}. "
                "Check log.txt for details."
            )

        return process
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def run_blender_import(
    blender_executable: Path,
    input_folder: Path,
    output_blend: Path,
    recursive: bool,
) -> tuple[int, int]:
    process = _run_blender(
        blender_executable,
        _read_script("blender_bridge.py"),
        [str(input_folder), str(output_blend), "1" if recursive else "0"],
        step_name="import",
    )

    imported_files = 0
    imported_objects = 0

    for line in process.stdout.splitlines():
        if line.startswith("OBJ_IMPORTED|"):
            parts = line.split("|", 2)
            if len(parts) == 3:
                try:
                    added = int(parts[2])
                except ValueError:
                    added = 0
                imported_objects += added
                imported_files += 1
                LOGGER.info("Added %s: %d object(s)", Path(parts[1]).name, added)
        elif line.startswith("OBJ_IMPORT_ERROR|"):
            parts = line.split("|", 2)
            if len(parts) == 3:
                LOGGER.warning("Failed to import OBJ %s: %s", parts[1], parts[2])
        elif line.startswith("TEXTURE_SCAN|"):
            LOGGER.info("%s", line.split("|", 1)[1] if "|" in line else line)
        elif line.startswith("TEXTURE_PACKED|"):
            parts = line.split("|", 1)
            if len(parts) == 2:
                LOGGER.info("Texture packed: %s", parts[1])
        elif line.startswith("TEXTURE_FOUND_PACKED|"):
            parts = line.split("|", 2)
            if len(parts) == 3:
                LOGGER.info("Texture resolved and packed: %s -> %s", parts[1], parts[2])
        elif line.startswith("TEXTURE_MISSING|"):
            parts = line.split("|", 2)
            if len(parts) == 3:
                LOGGER.warning("Texture not found: %s (stored path: %s)", parts[1], parts[2])
        elif line.startswith("TEXTURE_PACK_ERROR|"):
            parts = line.split("|", 2)
            if len(parts) == 3:
                LOGGER.warning("Failed to pack texture %s: %s", parts[1], parts[2])
        elif line.startswith("TEXTURE_LOAD_ERROR|"):
            parts = line.split("|", 2)
            if len(parts) == 3:
                LOGGER.warning("Failed to load texture %s: %s", parts[1], parts[2])

    return imported_files, imported_objects


def run_blender_export(
    blender_executable: Path,
    input_blend: Path,
    output_glb: Path,
) -> None:
    process = _run_blender(
        blender_executable,
        _read_script("blender_export.py"),
        [str(input_blend), str(output_glb)],
        step_name="export",
    )

    for line in process.stdout.splitlines():
        if line.startswith("EXPORT_COMPLETE|"):
            parts = line.split("|", 1)
            if len(parts) == 2:
                LOGGER.info("GLB written: %s", parts[1])


def merge_folder_to_glb(
    input_folder: Path,
    output_glb: Path,
    recursive: bool,
    blender_executable: Path,
    keep_blend: bool,
) -> None:
    if not input_folder.exists() or not input_folder.is_dir():
        raise ValueError(f"Input folder is not a valid directory: {input_folder}")

    obj_files = collect_obj_files(input_folder, recursive=recursive)
    if not obj_files:
        raise ValueError(f"No OBJ files found in: {input_folder}")

    LOGGER.info("Found %d OBJ files in %s", len(obj_files), input_folder)
    LOGGER.info("Blender executable: %s", blender_executable)
    LOGGER.info("Keep .blend file: %s", "yes" if keep_blend else "no")

    blend_path = output_glb.with_suffix('.blend')

    imported_files, imported_objects = run_blender_import(
        blender_executable=blender_executable,
        input_folder=input_folder,
        output_blend=blend_path,
        recursive=recursive,
    )

    LOGGER.info("Import complete — %d object(s) from %d file(s)", imported_objects, imported_files)

    run_blender_export(
        blender_executable=blender_executable,
        input_blend=blend_path,
        output_glb=output_glb,
    )

    if not keep_blend:
        blend_path.unlink(missing_ok=True)

    LOGGER.info("OBJ files scanned: %d", len(obj_files))
    LOGGER.info("OBJ files imported: %d", imported_files)
    LOGGER.info("Objects imported: %d", imported_objects)
    LOGGER.info("Output GLB: %s", output_glb)
    if keep_blend:
        LOGGER.info("Output BLEND: %s", blend_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import OBJ files from a folder with Blender and export one GLB."
    )
    parser.add_argument(
        "input_folder",
        type=Path,
        help="Folder containing OBJ files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("combined.glb"),
        help="Output GLB path (default: combined.glb)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search input folder recursively for OBJ files",
    )
    parser.add_argument(
        "--blender",
        type=Path,
        default=DEFAULT_BLENDER_PATH,
        help=(
            "Path to Blender executable "
            "(default: C:/Program Files/Blender Foundation/Blender 5.0/blender.exe)"
        ),
    )
    parser.add_argument(
        "--no-keep-blend",
        action="store_true",
        help="Do not keep the intermediate .blend file (default: keep it)",
    )

    args = parser.parse_args()
    setup_logging(Path("log.txt"))

    try:
        merge_folder_to_glb(
            input_folder=args.input_folder,
            output_glb=args.output,
            recursive=args.recursive,
            blender_executable=args.blender,
            keep_blend=not args.no_keep_blend,
        )
    except Exception as exc:
        LOGGER.error("Error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
