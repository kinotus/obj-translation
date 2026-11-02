"""
Blender bridge: imports OBJ files from a folder, packs textures, and saves a .blend file.
Exporting to GLB is handled by blender_export.py.

This file is used in two ways:
  1. Automatically – obj_folder_to_glb.py reads this file and passes it to
     Blender via --python.  Do not rename or move this file.
  2. Manually – run directly inside Blender for interactive debugging
     (see instructions below).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO RUN MANUALLY IN BLENDER'S SCRIPT EDITOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1 – Edit the MANUAL_DEBUG block near the bottom of this file.
         Set INPUT_FOLDER, OUTPUT_BLEND and RECURSIVE to match your test case.

Step 2 – Open Blender.  Switch any panel to the "Scripting" workspace
         (top menu → Scripting).

Step 3 – In the text editor, click "Open" and load this file.

Step 4 – Click "Run Script" (▶ button) or press Alt+P.

Step 5 – Watch the System Console for output.
         On Windows: Blender top bar → Window → Toggle System Console.

         Key output lines to look for:
           TEXTURE_SCAN|N image files found under …
             → N=0 means the input_folder path is wrong or has no images.
           TEXTURE_PACKED|name
             → Texture found at its original stored path and packed.
           TEXTURE_FOUND_PACKED|name|path
             → Texture had a wrong stored path but was found by filename search.
           TEXTURE_MISSING|name|stored_path
             → Texture could not be found anywhere under input_folder.
               The stored_path is what Blender recorded from the MTL file.
           TEXTURE_LOAD_ERROR|name|error
             → Texture was found on disk but bpy.data.images.load() failed.
           IMPORT_COMPLETE|path|n_objects
             → Import and packing finished; .blend saved to path.

Step 6 – After the script finishes, inspect the scene:
         • Outliner (set to "Blender File" mode) → expand "Images" to verify
           each image has the packed-file box icon (■) next to its name.
         • Shader Editor → check material nodes still reference the right textures.
         • Run blender_export.py next to test the GLB export step in isolation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO RUN FROM THE COMMAND LINE (same as the pipeline)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  blender --background --factory-startup --python blender_bridge.py -- ^
      C:\\local-3  C:\\output\\combined.blend  0

  Arguments after the --:
    1. input_folder   absolute path to the folder containing OBJ files
    2. output_blend   absolute path for the output .blend file
    3. recursive      0 = top-level only, 1 = search sub-folders too
"""

import sys
from pathlib import Path

import bpy


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(collection):
            if datablock.users == 0:
                collection.remove(datablock)


def collect_obj_files(folder: Path, recursive: bool) -> list[Path]:
    pattern = "**/*.obj" if recursive else "*.obj"
    return sorted([p for p in folder.glob(pattern) if p.is_file()])


def parse_args(argv: list[str]) -> tuple[Path, Path, bool]:
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    if len(argv) < 3:
        raise ValueError(
            "Expected args: <input_folder> <output_blend> <recursive:0|1>"
        )
    input_folder = Path(argv[0])
    output_blend = Path(argv[1])
    recursive = argv[2] == '1'
    return input_folder, output_blend, recursive


def build_texture_lookup(input_folder: Path) -> dict[str, Path]:
    image_exts = {'.jpg', '.jpeg', '.png', '.tga', '.bmp', '.tiff', '.tif', '.exr', '.hdr'}
    result: dict[str, Path] = {}
    for f in input_folder.rglob('*'):
        if f.is_file() and f.suffix.lower() in image_exts:
            result[f.name.lower()] = f
    return result


def ensure_textures_packed(input_folder: Path) -> None:
    texture_map = build_texture_lookup(input_folder)
    print(f"TEXTURE_SCAN|{len(texture_map)} image files found under {input_folder}")

    for image in list(bpy.data.images):
        if image.packed_file:
            continue

        abs_path = Path(bpy.path.abspath(image.filepath)) if image.filepath else None

        if abs_path and abs_path.exists():
            try:
                image.pack()
                print(f"TEXTURE_PACKED|{image.name}")
            except Exception as exc:
                print(f"TEXTURE_PACK_ERROR|{image.name}|{exc}")
            continue

        tex_key = (abs_path.name if abs_path else image.name).lower()
        if tex_key not in texture_map:
            print(f"TEXTURE_MISSING|{image.name}|{image.filepath}")
            continue

        found_path = texture_map[tex_key]
        try:
            new_img = bpy.data.images.load(str(found_path), check_existing=True)
            for mat in bpy.data.materials:
                if mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type == 'TEX_IMAGE' and node.image == image:
                            node.image = new_img
            bpy.data.images.remove(image)
            new_img.pack()
            print(f"TEXTURE_FOUND_PACKED|{new_img.name}|{found_path}")
        except Exception as exc:
            print(f"TEXTURE_LOAD_ERROR|{image.name}|{exc}")


def main() -> None:
    input_folder, output_blend, recursive = parse_args(sys.argv)

    if not input_folder.exists() or not input_folder.is_dir():
        raise ValueError(f"Input folder is not a valid directory: {input_folder}")

    obj_files = collect_obj_files(input_folder, recursive=recursive)
    if not obj_files:
        raise ValueError(f"No OBJ files found in: {input_folder}")

    clear_scene()

    imported = 0
    for obj_file in obj_files:
        before_set = set(bpy.context.scene.objects)
        try:
            bpy.ops.wm.obj_import(filepath=str(obj_file), forward_axis='Y', up_axis='Z')
            new_objects = set(bpy.context.scene.objects) - before_set
            for obj in new_objects:
                obj.display_type = 'BOUNDS'
            imported += len(new_objects)
            print(f"OBJ_IMPORTED|{obj_file}|{len(new_objects)}")
        except Exception as exc:
            print(f"OBJ_IMPORT_ERROR|{obj_file}|{exc}")

    if imported == 0:
        raise RuntimeError("No objects were imported successfully from OBJ files.")

    bpy.ops.object.select_all(action='SELECT')
    if bpy.context.screen:
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        with bpy.context.temp_override(area=area, region=region):
                            bpy.ops.view3d.view_selected()
                        break
                break

    output_blend.parent.mkdir(parents=True, exist_ok=True)

    ensure_textures_packed(input_folder)

    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    print(f"IMPORT_COMPLETE|{output_blend}|{imported}")


if __name__ == '__main__':
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # MANUAL_DEBUG – edit these paths, then run the script in Blender.
    # Ignored when Blender runs this file via --python (real args are present).
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _cli_args_present = '--' in sys.argv and len(sys.argv) > sys.argv.index('--') + 3

    if not _cli_args_present:
        INPUT_FOLDER  = r'C:\temp\local'
        OUTPUT_BLEND  = r'C:\temp\local-blend\combined.blend'
        RECURSIVE     = False

        sys.argv = [
            __file__, '--',
            INPUT_FOLDER,
            OUTPUT_BLEND,
            '1' if RECURSIVE else '0',
        ]

    main()
