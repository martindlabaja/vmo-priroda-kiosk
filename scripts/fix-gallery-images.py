#!/usr/bin/env python3
"""
Fix Gallery Images Script
Scans image files and populates empty gallery JSON files with their images.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
GALLERIES_DIR = DATA_DIR / 'galleries'
IMAGES_DIR = BASE_DIR.parent / 'extracted-data' / 'wamp' / 'www' / 'data-fotogalerie'


def load_json(filepath):
    """Load JSON file."""
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_json(filepath, data):
    """Save JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def scan_images():
    """Scan all images and group by gallery ID."""
    gallery_images = defaultdict(list)

    # Pattern for images: ID.jpg, ID-suffix.jpg, ID_suffix.jpg
    # Examples: 393.jpg, 393-1.jpg, 15-hornina.jpg

    for img_file in IMAGES_DIR.glob('*.jpg'):
        filename = img_file.name

        # Skip menu/tile related images
        if img_file.parent.name in ('menu', 'dlazdice'):
            continue

        # Extract gallery ID from filename
        # Try pattern: NUMBER.jpg or NUMBER-*.jpg or NUMBER_*.jpg
        match = re.match(r'^(\d+)(?:[-_].*)?\.jpg$', filename)
        if match:
            gallery_id = int(match.group(1))
            gallery_images[gallery_id].append({
                'filename': filename,
                'path': filename
            })

    return gallery_images


def main():
    print("=" * 70)
    print("FIX GALLERY IMAGES")
    print("=" * 70)

    # Scan all images
    print("\nScanning image files...")
    image_map = scan_images()
    print(f"Found images for {len(image_map)} potential galleries")

    # Process galleries with empty images
    fixed_count = 0
    already_ok = 0
    no_images = 0

    for gallery_file in sorted(GALLERIES_DIR.glob('*.json')):
        gallery = load_json(gallery_file)
        if not gallery:
            continue

        gallery_id = gallery.get('id')
        if not gallery_id:
            continue

        # Skip if gallery already has images
        if gallery.get('images'):
            already_ok += 1
            continue

        # Check if we found images for this gallery
        if gallery_id in image_map:
            images = image_map[gallery_id]

            # Sort images by filename
            images.sort(key=lambda x: x['filename'])

            # Add proper structure
            for i, img in enumerate(images):
                img['id'] = gallery_id * 100 + i  # Generate unique ID
                img['caption'] = None
                img['author'] = ''
                img['order'] = i

            gallery['images'] = images
            save_json(gallery_file, gallery)

            print(f"  ✓ Fixed gallery {gallery_id}: {gallery.get('name', 'Unknown')} - added {len(images)} images")
            fixed_count += 1
        else:
            no_images += 1

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Galleries already OK: {already_ok}")
    print(f"Galleries fixed: {fixed_count}")
    print(f"Galleries with no images found: {no_images}")

    if fixed_count > 0:
        print(f"\n✓ Fixed {fixed_count} galleries!")


if __name__ == '__main__':
    main()
