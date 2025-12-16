#!/usr/bin/env python3
"""
Generate Placeholder Tiles
Creates text-based placeholder tiles for items without any gallery images.
"""

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
EXTRACTED_DIR = BASE_DIR.parent / 'extracted-data' / 'wamp' / 'www' / 'data-fotogalerie'

# Image directories
TILES_DIR = EXTRACTED_DIR / 'menu' / 'dlazdice'
MENU_DIR = EXTRACTED_DIR / 'menu'

# Image sizes
TILE_SIZE = (141, 141)
HEADER_SIZE = (919, 409)

# Colors (museum theme)
BG_COLOR = (204, 20, 28)  # Museum red #cc141c
TEXT_COLOR = (255, 255, 255)  # White


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


def create_text_tile(name, dest_path, size=TILE_SIZE):
    """Create a tile with text on colored background."""
    try:
        img = Image.new('RGB', size, BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Try to use a nice font, fall back to default
        font_size = 14 if size == TILE_SIZE else 36
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()

        # Wrap text
        max_chars = 12 if size == TILE_SIZE else 30
        lines = textwrap.wrap(name, width=max_chars)

        # Calculate text position
        line_height = font_size + 4
        total_height = len(lines) * line_height
        y = (size[1] - total_height) // 2

        # Draw text
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (size[0] - text_width) // 2
            draw.text((x, y), line, font=font, fill=TEXT_COLOR)
            y += line_height

        img.save(dest_path, 'JPEG', quality=85)
        return True
    except Exception as e:
        print(f"  Error creating placeholder: {e}")
        return False


def main():
    print("=" * 70)
    print("GENERATE PLACEHOLDER TILES")
    print("=" * 70)

    # Load menu
    menu = load_json(DATA_DIR / 'content' / 'menu.json')
    if not menu:
        print("ERROR: Could not load menu.json")
        return

    # Collect all menu items
    all_items = collect_menu_items(menu.get('root', []))

    tiles_created = 0
    headers_created = 0

    print(f"\nChecking {len(all_items)} menu items for missing images...\n")

    for item in all_items:
        item_id = item.get('id')
        name = item.get('name', 'Unknown')

        if not item_id:
            continue

        tile_path = TILES_DIR / f"{item_id}.jpg"
        header_path = MENU_DIR / f"{item_id}.jpg"

        # Create tile if missing
        if not tile_path.exists():
            if create_text_tile(name, tile_path, TILE_SIZE):
                print(f"  ✓ Created placeholder tile for ID {item_id}: {name}")
                tiles_created += 1

        # Create header if missing and item has children
        if not header_path.exists() and item.get('children'):
            if create_text_tile(name, header_path, HEADER_SIZE):
                print(f"  ✓ Created placeholder header for ID {item_id}: {name}")
                headers_created += 1

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Placeholder tiles created: {tiles_created}")
    print(f"Placeholder headers created: {headers_created}")

    if tiles_created + headers_created > 0:
        print(f"\n✓ Generated {tiles_created + headers_created} placeholder images!")
    else:
        print("\n✓ All images already exist!")


if __name__ == '__main__':
    main()
