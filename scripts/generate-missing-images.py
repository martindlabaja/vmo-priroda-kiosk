#!/usr/bin/env python3
"""
Generate Missing Images Script
Creates tile and header images for category pages using images from their galleries.
"""

import json
from pathlib import Path
from PIL import Image
import shutil

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
EXTRACTED_DIR = BASE_DIR.parent / 'extracted-data' / 'wamp' / 'www' / 'data-fotogalerie'

# Image directories
TILES_DIR = EXTRACTED_DIR / 'menu' / 'dlazdice'
MENU_DIR = EXTRACTED_DIR / 'menu'
GALLERIES_DIR = DATA_DIR / 'galleries'

# Image sizes
TILE_SIZE = (141, 141)
HEADER_SIZE = (919, 409)


def load_json(filepath):
    """Load JSON file."""
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def collect_menu_items(items, collected=None):
    """Recursively collect all menu items with their children."""
    if collected is None:
        collected = []

    for item in items:
        collected.append(item)
        if item.get('children'):
            collect_menu_items(item['children'], collected)

    return collected


def find_gallery_image_for_item(item, pages_dir, galleries_dir):
    """Find a suitable gallery image for a menu item."""
    # First, check if item has a page with gallery_id
    url = item.get('url', '')
    url_safe = url.replace('/', '_')
    page_path = pages_dir / f"{url_safe}.json"

    if page_path.exists():
        page = load_json(page_path)
        if page and page.get('gallery_id'):
            gallery = load_json(galleries_dir / f"{page['gallery_id']}.json")
            if gallery and gallery.get('images'):
                img_path = gallery['images'][0].get('path')
                if img_path:
                    full_path = EXTRACTED_DIR / img_path
                    if full_path.exists():
                        return full_path

    # Check children recursively for gallery images
    for child in item.get('children', []):
        img = find_gallery_image_for_item(child, pages_dir, galleries_dir)
        if img:
            return img

    return None


def create_tile_image(source_path, dest_path, size=TILE_SIZE):
    """Create a tile image by center-cropping and resizing."""
    try:
        with Image.open(source_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # Calculate crop box for center square
            width, height = img.size
            min_dim = min(width, height)
            left = (width - min_dim) // 2
            top = (height - min_dim) // 2
            right = left + min_dim
            bottom = top + min_dim

            # Crop to square and resize
            img_cropped = img.crop((left, top, right, bottom))
            img_resized = img_cropped.resize(size, Image.Resampling.LANCZOS)

            # Save
            img_resized.save(dest_path, 'JPEG', quality=85)
            return True
    except Exception as e:
        print(f"  Error creating tile: {e}")
        return False


def create_header_image(source_path, dest_path, size=HEADER_SIZE):
    """Create a header image by cropping to aspect ratio and resizing."""
    try:
        with Image.open(source_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            width, height = img.size
            target_ratio = size[0] / size[1]
            current_ratio = width / height

            if current_ratio > target_ratio:
                # Image is wider - crop sides
                new_width = int(height * target_ratio)
                left = (width - new_width) // 2
                img_cropped = img.crop((left, 0, left + new_width, height))
            else:
                # Image is taller - crop top/bottom
                new_height = int(width / target_ratio)
                top = (height - new_height) // 2
                img_cropped = img.crop((0, top, width, top + new_height))

            # Resize
            img_resized = img_cropped.resize(size, Image.Resampling.LANCZOS)

            # Save
            img_resized.save(dest_path, 'JPEG', quality=85)
            return True
    except Exception as e:
        print(f"  Error creating header: {e}")
        return False


def main():
    print("=" * 70)
    print("GENERATE MISSING IMAGES")
    print("=" * 70)

    # Load menu
    menu = load_json(DATA_DIR / 'content' / 'menu.json')
    if not menu:
        print("ERROR: Could not load menu.json")
        return

    pages_dir = DATA_DIR / 'content' / 'pages' / 'cz'

    # Collect all menu items
    all_items = collect_menu_items(menu.get('root', []))

    tiles_created = 0
    headers_created = 0
    tiles_failed = 0
    headers_failed = 0

    print(f"\nProcessing {len(all_items)} menu items...\n")

    for item in all_items:
        item_id = item.get('id')
        name = item.get('name', 'Unknown')

        if not item_id:
            continue

        tile_path = TILES_DIR / f"{item_id}.jpg"
        header_path = MENU_DIR / f"{item_id}.jpg"

        needs_tile = not tile_path.exists()
        needs_header = not header_path.exists() and item.get('children')  # Only categories need headers

        if not needs_tile and not needs_header:
            continue

        # Find a source image
        source_img = find_gallery_image_for_item(item, pages_dir, GALLERIES_DIR)

        if not source_img:
            if needs_tile:
                print(f"  ID {item_id}: {name} - No source image found for tile")
                tiles_failed += 1
            if needs_header:
                print(f"  ID {item_id}: {name} - No source image found for header")
                headers_failed += 1
            continue

        # Create tile
        if needs_tile:
            if create_tile_image(source_img, tile_path):
                print(f"  ✓ Created tile for ID {item_id}: {name}")
                tiles_created += 1
            else:
                tiles_failed += 1

        # Create header
        if needs_header:
            if create_header_image(source_img, header_path):
                print(f"  ✓ Created header for ID {item_id}: {name}")
                headers_created += 1
            else:
                headers_failed += 1

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Tiles created: {tiles_created}")
    print(f"Tiles failed (no source): {tiles_failed}")
    print(f"Headers created: {headers_created}")
    print(f"Headers failed (no source): {headers_failed}")

    if tiles_created + headers_created > 0:
        print(f"\n✓ Generated {tiles_created + headers_created} images!")

    if tiles_failed + headers_failed > 0:
        print(f"\n⚠ {tiles_failed + headers_failed} items still need images (no gallery source found)")


if __name__ == '__main__':
    main()
