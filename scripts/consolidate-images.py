#!/usr/bin/env python3
"""
Consolidate tile.jpg and header.jpg into single tile.jpg.

For each folder:
- If only tile.jpg exists: keep it
- If only header.jpg exists: rename to tile.jpg
- If both exist: keep the larger one as tile.jpg, delete the other
"""

import os
from pathlib import Path

CONTENT_DIR = Path(__file__).parent.parent / 'content'

def consolidate_images():
    stats = {
        'only_tile': 0,
        'only_header': 0,
        'both_kept_tile': 0,
        'both_kept_header': 0,
        'no_images': 0
    }

    # Find all directories in content
    for root, dirs, files in os.walk(CONTENT_DIR):
        root_path = Path(root)

        # Skip gallery directories
        if root_path.name == 'gallery':
            continue

        tile_path = root_path / 'tile.jpg'
        header_path = root_path / 'header.jpg'

        has_tile = tile_path.exists()
        has_header = header_path.exists()

        if has_tile and has_header:
            tile_size = tile_path.stat().st_size
            header_size = header_path.stat().st_size

            rel_path = root_path.relative_to(CONTENT_DIR)

            if header_size > tile_size:
                # Header is larger - delete tile, rename header to tile
                tile_path.unlink()
                header_path.rename(tile_path)
                print(f"[HEADER > TILE] {rel_path}")
                print(f"    header: {header_size:,} bytes, tile: {tile_size:,} bytes")
                stats['both_kept_header'] += 1
            else:
                # Tile is larger or equal - delete header
                header_path.unlink()
                print(f"[TILE >= HEADER] {rel_path}")
                print(f"    tile: {tile_size:,} bytes, header: {header_size:,} bytes")
                stats['both_kept_tile'] += 1

        elif has_header and not has_tile:
            # Only header exists - rename to tile
            header_path.rename(tile_path)
            rel_path = root_path.relative_to(CONTENT_DIR)
            print(f"[RENAMED] {rel_path}/header.jpg -> tile.jpg")
            stats['only_header'] += 1

        elif has_tile and not has_header:
            stats['only_tile'] += 1

        else:
            # No images - check if this is a content folder (has .md file)
            if any(f.endswith('.md') for f in files):
                stats['no_images'] += 1

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Only tile.jpg (kept):           {stats['only_tile']}")
    print(f"Only header.jpg (renamed):      {stats['only_header']}")
    print(f"Both - kept tile (larger):      {stats['both_kept_tile']}")
    print(f"Both - kept header (larger):    {stats['both_kept_header']}")
    print(f"Content folders with no images: {stats['no_images']}")

    total_changes = stats['only_header'] + stats['both_kept_tile'] + stats['both_kept_header']
    print(f"\nTotal changes made: {total_changes}")

if __name__ == '__main__':
    consolidate_images()
