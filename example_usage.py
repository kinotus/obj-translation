"""
Example usage of the OBJ editor script.
Run from command line:

1. Process all OBJ files in a folder (with default header):
   python obj_editor.py ./data/tiles

2. Process multiple folders:
   python obj_editor.py ./data/tiles ./data/models

3. Search recursively in subfolders:
   python obj_editor.py ./data --recursive

4. With custom header:
   python obj_editor.py ./data/tiles --header "# Custom header line"

5. With custom origin values (in any Gauss Krüger zone):
   python obj_editor.py ./data/tiles --x-origo 25000000 --y-origo 6500000

6. Manually specify number of workers:
   python obj_editor.py ./data/tiles --workers 4

Each output file will have two comment lines at the beginning:
  - First line: The specified header (default: Helsinki model info)
  - Second line: # x-origo: XXXXX, y-origo: XXXXX
"""

from pathlib import Path
from obj_editor import process_files_parallel

# Example: Process all OBJ files in the current folder with custom header
if __name__ == '__main__':
    data_folder = Path('.')
    
    if data_folder.exists():
        obj_files = list(data_folder.glob('*.obj'))
        
        if obj_files:
            process_files_parallel(
                obj_files,
                x_origo=25490000,
                y_origo=6668000,
                header="# My custom header"
            )
        else:
            print(f"No OBJ files found in {data_folder}")
    else:
        print(f"Folder not found: {data_folder}")
