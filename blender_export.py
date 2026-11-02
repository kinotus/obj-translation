"""
Blender export: opens a .blend file produced by blender_bridge.py and exports it as GLB.

This file is used in two ways:
  1. Automatically – obj_folder_to_glb.py reads this file and passes it to
     Blender via --python.  Do not rename or move this file.
  2. Manually – run directly inside Blender for interactive debugging
     (see instructions below).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO RUN MANUALLY IN BLENDER'S SCRIPT EDITOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1 – Run blender_bridge.py first to produce the intermediate .blend file.

Step 2 – Edit the MANUAL_DEBUG block near the bottom of this file.
         Set INPUT_BLEND to the .blend produced in step 1, and OUTPUT_GLB
         to wherever you want the final file written.

Step 3 – Open Blender.  Switch any panel to the "Scripting" workspace.

Step 4 – Click "Open" and load this file, then click "Run Script" (▶ / Alt+P).

Step 5 – Watch the System Console (Window → Toggle System Console).

         Key output lines:
           EXPORT_COMPLETE|path
             → GLB written successfully to path.

Step 6 – Open the GLB in a viewer (e.g. https://gltf-viewer.donmccurdy.com or
         Windows 3D Viewer) to verify textures are embedded and look correct.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO RUN FROM THE COMMAND LINE (same as the pipeline)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  blender --background --factory-startup --python blender_export.py -- ^
      C:\\output\\combined.blend  C:\\output\\combined.glb

  Arguments after the --:
    1. input_blend   absolute path to the .blend file to open
    2. output_glb    absolute path for the output .glb file
"""

import sys
from pathlib import Path

import bpy


def parse_args(argv: list[str]) -> tuple[Path, Path]:
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    if len(argv) < 2:
        raise ValueError("Expected args: <input_blend> <output_glb>")
    input_blend = Path(argv[0])
    output_glb = Path(argv[1])
    return input_blend, output_glb


def main() -> None:
    input_blend, output_glb = parse_args(sys.argv)

    if not input_blend.exists() or not input_blend.is_file():
        raise ValueError(f"Input .blend file not found: {input_blend}")

    bpy.ops.wm.open_mainfile(filepath=str(input_blend))

    output_glb.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.export_scene.gltf(
        filepath=str(output_glb),
        export_format='GLB',
        export_yup=True,
    )
    print(f"EXPORT_COMPLETE|{output_glb}")


if __name__ == '__main__':
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # MANUAL_DEBUG – edit these paths, then run the script in Blender.
    # Ignored when Blender runs this file via --python (real args are present).
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _cli_args_present = '--' in sys.argv and len(sys.argv) > sys.argv.index('--') + 2

    if not _cli_args_present:
        INPUT_BLEND = r'C:\local-3\debug_output\combined.blend'
        OUTPUT_GLB  = r'C:\local-3\debug_output\combined.glb'

        sys.argv = [
            __file__, '--',
            INPUT_BLEND,
            OUTPUT_GLB,
        ]

    main()
