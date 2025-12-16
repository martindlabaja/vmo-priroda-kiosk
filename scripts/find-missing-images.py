#!/usr/bin/env python3
"""
Find Missing Images Script
Scans menu items and galleries to identify missing image files.
"""

import json
from pathlib import Path
from collections import defaultdict

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
EXTRACTED_DIR = BASE_DIR.parent / 'extracted-data' / 'wamp' / 'www' / 'data-fotogalerie'

# Image directories
TILES_DIR = EXTRACTED_DIR / 'menu' / 'dlazdice'
MENU_DIR = EXTRACTED_DIR / 'menu'
GALLERIES_DIR = DATA_DIR / 'galleries'


def load_json(filepath):
    """Load JSON file."""
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def collect_menu_items(items, collected=None):
    """Recursively collect all menu items."""
    if collected is None:
        collected = []

    for item in items:
        collected.append(item)
        if item.get('children'):
            collect_menu_items(item['children'], collected)

    return collected


def check_tile_images(menu_items):
    """Check for missing tile images."""
    missing = []
    found = []

    for item in menu_items:
        item_id = item.get('id')
        if not item_id:
            continue

        # Check for tile image (used in tile-grid)
        tile_path = TILES_DIR / f"{item_id}.jpg"
        if tile_path.exists():
            found.append((item_id, item.get('name'), str(tile_path)))
        else:
            missing.append((item_id, item.get('name'), item.get('url'), str(tile_path)))

    return missing, found


def check_menu_header_images(menu_items):
    """Check for missing menu header images (used in tile-section)."""
    missing = []
    found = []

    # Only check items that have children (category pages)
    category_items = [item for item in menu_items if item.get('children')]

    for item in category_items:
        item_id = item.get('id')
        if not item_id:
            continue

        # Check for menu header image
        menu_path = MENU_DIR / f"{item_id}.jpg"
        if menu_path.exists():
            found.append((item_id, item.get('name'), str(menu_path)))
        else:
            missing.append((item_id, item.get('name'), item.get('url'), str(menu_path)))

    return missing, found


def check_gallery_images():
    """Check for missing gallery images."""
    missing = []
    found = []
    galleries_checked = 0

    if not GALLERIES_DIR.exists():
        return missing, found, 0

    for gallery_file in GALLERIES_DIR.glob('*.json'):
        gallery = load_json(gallery_file)
        if not gallery:
            continue

        galleries_checked += 1
        gallery_id = gallery.get('id')

        for img in gallery.get('images', []):
            img_path = img.get('path')
            if not img_path:
                continue

            full_path = EXTRACTED_DIR / img_path
            if full_path.exists():
                found.append((gallery_id, img_path))
            else:
                missing.append((gallery_id, gallery.get('name', 'Unknown'), img_path, str(full_path)))

    return missing, found, galleries_checked


def main():
    print("=" * 70)
    print("MISSING IMAGES REPORT")
    print("=" * 70)

    # Load menu
    menu = load_json(DATA_DIR / 'content' / 'menu.json')
    if not menu:
        print("ERROR: Could not load menu.json")
        return

    # Collect all menu items
    all_items = collect_menu_items(menu.get('root', []))
    print(f"\nTotal menu items: {len(all_items)}")

    # Check tile images
    print("\n" + "-" * 70)
    print("TILE IMAGES (used in navigation grids)")
    print("-" * 70)

    missing_tiles, found_tiles = check_tile_images(all_items)
    print(f"Found: {len(found_tiles)}")
    print(f"Missing: {len(missing_tiles)}")

    if missing_tiles:
        print("\nMissing tile images:")
        for item_id, name, url, path in missing_tiles[:20]:  # Show first 20
            print(f"  ID {item_id}: {name}")
            print(f"    URL: {url}")
            print(f"    Expected: {path}")
        if len(missing_tiles) > 20:
            print(f"  ... and {len(missing_tiles) - 20} more")

    # Check menu header images
    print("\n" + "-" * 70)
    print("MENU HEADER IMAGES (used in category pages)")
    print("-" * 70)

    missing_headers, found_headers = check_menu_header_images(all_items)
    print(f"Found: {len(found_headers)}")
    print(f"Missing: {len(missing_headers)}")

    if missing_headers:
        print("\nMissing header images:")
        for item_id, name, url, path in missing_headers[:20]:
            print(f"  ID {item_id}: {name}")
            print(f"    URL: {url}")
            print(f"    Expected: {path}")
        if len(missing_headers) > 20:
            print(f"  ... and {len(missing_headers) - 20} more")

    # Check gallery images
    print("\n" + "-" * 70)
    print("GALLERY IMAGES")
    print("-" * 70)

    missing_gallery, found_gallery, galleries_count = check_gallery_images()
    print(f"Galleries checked: {galleries_count}")
    print(f"Images found: {len(found_gallery)}")
    print(f"Images missing: {len(missing_gallery)}")

    if missing_gallery:
        print("\nMissing gallery images:")
        # Group by gallery
        by_gallery = defaultdict(list)
        for gal_id, gal_name, img_path, full_path in missing_gallery:
            by_gallery[f"{gal_id}: {gal_name}"].append(img_path)

        for gallery_info, images in list(by_gallery.items())[:10]:
            print(f"  {gallery_info}:")
            for img in images[:3]:
                print(f"    - {img}")
            if len(images) > 3:
                print(f"    ... and {len(images) - 3} more")

        if len(by_gallery) > 10:
            print(f"  ... and {len(by_gallery) - 10} more galleries with missing images")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total_missing = len(missing_tiles) + len(missing_headers) + len(missing_gallery)
    total_found = len(found_tiles) + len(found_headers) + len(found_gallery)

    print(f"Total images found: {total_found}")
    print(f"Total images missing: {total_missing}")

    if total_missing == 0:
        print("\n✓ All images are present!")
    else:
        print(f"\n⚠ {total_missing} images need attention")

        # Save detailed report
        report_path = BASE_DIR / 'missing-images-report.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("MISSING IMAGES DETAILED REPORT\n")
            f.write("=" * 70 + "\n\n")

            f.write("MISSING TILE IMAGES\n")
            f.write("-" * 40 + "\n")
            for item_id, name, url, path in missing_tiles:
                f.write(f"ID: {item_id}\n")
                f.write(f"Name: {name}\n")
                f.write(f"URL: {url}\n")
                f.write(f"Expected path: {path}\n\n")

            f.write("\nMISSING HEADER IMAGES\n")
            f.write("-" * 40 + "\n")
            for item_id, name, url, path in missing_headers:
                f.write(f"ID: {item_id}\n")
                f.write(f"Name: {name}\n")
                f.write(f"URL: {url}\n")
                f.write(f"Expected path: {path}\n\n")

            f.write("\nMISSING GALLERY IMAGES\n")
            f.write("-" * 40 + "\n")
            for gal_id, gal_name, img_path, full_path in missing_gallery:
                f.write(f"Gallery: {gal_id} - {gal_name}\n")
                f.write(f"Image: {img_path}\n")
                f.write(f"Expected path: {full_path}\n\n")

        print(f"\nDetailed report saved to: {report_path}")


if __name__ == '__main__':
    main()
