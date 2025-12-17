#!/usr/bin/env python3
"""Find orphan content folders not referenced in menu.yaml."""

from pathlib import Path
import yaml

CONTENT_DIR = Path(__file__).parent.parent / 'content'

# Load menu.yaml sections
menu_path = CONTENT_DIR / 'menu.yaml'
with open(menu_path) as f:
    menu = yaml.safe_load(f)

valid_sections = {s['id'] for s in menu.get('sections', [])}
print(f"Valid sections from menu.yaml: {sorted(valid_sections)}")
print()

# Find top-level directories in content/
top_level_dirs = [d.name for d in CONTENT_DIR.iterdir() if d.is_dir()]
print(f"Top-level directories in content/: {sorted(top_level_dirs)}")
print()

# Find orphans
orphans = set(top_level_dirs) - valid_sections
if orphans:
    print(f"ORPHAN directories (not in menu.yaml):")
    for orphan in sorted(orphans):
        orphan_path = CONTENT_DIR / orphan
        # Count files
        files = list(orphan_path.rglob('*'))
        file_count = len([f for f in files if f.is_file()])
        print(f"  - {orphan}/ ({file_count} files)")
else:
    print("No orphan directories found.")
