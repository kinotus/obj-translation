"""
Fast parallel OBJ file editor for coordinate transformation.
Processes vertex lines (starting with 'v') by offsetting
X and Y by preset origin values. Original coordinate precision
is preserved.
"""

import argparse
import sys
from pathlib import Path
from multiprocessing import Pool, cpu_count
from typing import Tuple


def process_obj_file(
    input_path: Path,
    x_origo: float = 25490000,
    y_origo: float = 6668000,
    header: str = "# Helsinki city photogrammetric model 2024, License CC-BY-40."
) -> Tuple[Path, int, int]:
    """
    Process a single OBJ file and write to a new file with '_local' suffix.
    
    Args:
        input_path: Path to input .obj file
        x_origo: X origin offset (subtracted from x-coordinates)
        y_origo: Y origin offset (subtracted from y-coordinates)
        header: Header comment to include at the beginning of the file
        
    Returns:
        Tuple of (output_path, lines_processed, lines_modified)
    """
    output_path = input_path.parent / f"{input_path.stem}_local{input_path.suffix}"
    lines_processed = 0
    lines_modified = 0
    
    try:
        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(output_path, 'w', encoding='utf-8') as outfile:
            
            # Write header lines
            if header:
                outfile.write(f"{header}\n")
            outfile.write(f"# Local coordinate system origo in EPSG:3879 GK25 X-origo: {x_origo}, Y-origo: {y_origo}\n")
            
            for line in infile:
                lines_processed += 1
                
                # Check if line starts with 'v' (vertex line)
                if line.startswith('v ') and not line.startswith('vn ') and not line.startswith('vt '):
                    try:
                        parts = line.split()
                        if len(parts) >= 4:  # 'v' + x + y + z
                            prefix = parts[0]  # 'v'
                            x = float(parts[1])
                            y = float(parts[2])
                            
                            # Apply offset, keeping the same number of
                            # decimal places as the input coordinate
                            x_dec = len(parts[1].split('.')[1]) if '.' in parts[1] else 0
                            y_dec = len(parts[2].split('.')[1]) if '.' in parts[2] else 0
                            x_local = x - x_origo
                            y_local = y - y_origo
                            
                            # Format the output line; Z is preserved as-is
                            new_line = f"{prefix} {x_local:.{x_dec}f} {y_local:.{y_dec}f} {parts[3]}\n"
                            
                            # Preserve any additional data after the coordinates (like colors, etc.)
                            if len(parts) > 4:
                                new_line = new_line.rstrip('\n') + ' ' + ' '.join(parts[4:]) + '\n'
                            
                            outfile.write(new_line)
                            lines_modified += 1
                        else:
                            outfile.write(line)
                    except (ValueError, IndexError):
                        # If parsing fails, write line unchanged
                        outfile.write(line)
                else:
                    # Write non-vertex lines unchanged
                    outfile.write(line)
        
        return output_path, lines_processed, lines_modified
        
    except Exception as e:
        print(f"Error processing {input_path}: {e}", file=sys.stderr)
        raise


def process_files_parallel(
    file_paths: list,
    x_origo: float = 25490000,
    y_origo: float = 6668000,
    header: str = "# Helsinki city photogrammetric model 2024, License CC-BY-40.",
    num_workers: int = None
) -> None:
    """
    Process multiple OBJ files in parallel.
    
    Args:
        file_paths: List of Path objects to .obj files
        x_origo: X origin offset
        y_origo: Y origin offset
        header: Header comment to include at the beginning of each file
        num_workers: Number of parallel workers (defaults to CPU count)
    """
    if num_workers is None:
        num_workers = cpu_count()
    
    # Create partial function with fixed parameters
    from functools import partial
    process_func = partial(
        process_obj_file,
        x_origo=x_origo,
        y_origo=y_origo,
        header=header
    )
    
    print(f"Processing {len(file_paths)} file(s) with {num_workers} worker(s)...\n")
    
    with Pool(num_workers) as pool:
        results = pool.map(process_func, file_paths)
    
    # Print results
    total_processed = 0
    total_modified = 0
    for output_path, lines_processed, lines_modified in results:
        total_processed += lines_processed
        total_modified += lines_modified
        print(f"✓ {output_path.name}")
        print(f"  Lines processed: {lines_processed}, Modified: {lines_modified}")
    
    print(f"\nSummary:")
    print(f"Total lines processed: {total_processed}")
    print(f"Total lines modified: {total_modified}")


def main():
    parser = argparse.ArgumentParser(
        description="Fast parallel OBJ file editor for coordinate transformation"
    )
    parser.add_argument(
        'folders',
        nargs='+',
        type=Path,
        help='Folder(s) containing OBJ files to process'
    )
    parser.add_argument(
        '--x-origo',
        type=float,
        default=25490000,
        help='X origin offset (default: 25490000)'
    )
    parser.add_argument(
        '--y-origo',
        type=float,
        default=6668000,
        help='Y origin offset (default: 6668000)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help=f'Number of parallel workers (default: CPU count)'
    )
    parser.add_argument(
        '--recursive',
        action='store_true',
        help='Search folders recursively for OBJ files'
    )
    parser.add_argument(
        '--header',
        type=str,
        default="# Helsinki city photogrammetric model 2024, License CC-BY-40.",
        help='Header comment to add to each output file (default: Helsinki model info)'
    )
    
    args = parser.parse_args()
    
    # Discover OBJ files in folders
    valid_files = []
    for folder_path in args.folders:
        if not folder_path.exists():
            print(f"Warning: Folder not found: {folder_path}", file=sys.stderr)
            continue
        
        if not folder_path.is_dir():
            print(f"Warning: Not a directory: {folder_path}", file=sys.stderr)
            continue
        
        # Search for OBJ files
        if args.recursive:
            pattern = '**/*.obj'
        else:
            pattern = '*.obj'
        
        obj_files = list(folder_path.glob(pattern))
        if not obj_files:
            print(f"Warning: No OBJ files found in {folder_path}", file=sys.stderr)
        else:
            valid_files.extend(obj_files)
    
    if not valid_files:
        print("Error: No OBJ files to process", file=sys.stderr)
        sys.exit(1)
    
    # Sort files for consistent processing order
    valid_files.sort()
    
    try:
        process_files_parallel(
            valid_files,
            x_origo=args.x_origo,
            y_origo=args.y_origo,
            header=args.header,
            num_workers=args.workers
        )
        print("\nDone!")
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
