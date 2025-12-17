#!/usr/bin/env python3
"""
Migrate orphan galleries (galleries not linked to any page) to content/_galleries/

These galleries existed in the original system but had no associated page.
They are stored here so pages can be created for them later.
"""

import json
import shutil
from pathlib import Path
import re

from slugify import slugify
from markdownify import markdownify as md

BASE_DIR = Path(__file__).parent.parent
GALLERIES_JSON_DIR = BASE_DIR / 'data' / 'galleries'
STATIC_GALLERY_DIR = BASE_DIR / 'static' / 'images' / 'gallery'
STATIC_THUMBS_DIR = BASE_DIR / 'static' / 'images' / 'thumbs'
CONTENT_DIR = BASE_DIR / 'content'
OUTPUT_DIR = CONTENT_DIR / '_galleries'


def get_migrated_gallery_ids():
    """Find gallery IDs that were already migrated (have gallery/ folders in content)."""
    migrated = set()
    for gallery_dir in CONTENT_DIR.rglob('gallery'):
        if gallery_dir.is_dir() and gallery_dir.name == 'gallery':
            # Check if it has images
            if any(gallery_dir.glob('*.jpg')):
                # Get the page's menu_id from its markdown
                page_dir = gallery_dir.parent
                for md_name in ['page.md', '_index.md']:
                    md_file = page_dir / md_name
                    if md_file.exists():
                        with open(md_file) as f:
                            content = f.read()
                        for line in content.split('\n'):
                            if line.startswith('menu_id:'):
                                menu_id = line.split(':')[1].strip()
                                # Find gallery_id from original page JSON
                                # Actually, we need to check data/content/pages
                                break

    # Simpler approach: check which gallery JSONs have their images in content/
    for gallery_json in GALLERIES_JSON_DIR.glob('*.json'):
        gallery_id = gallery_json.stem
        # Check if any images from this gallery exist in content/
        with open(gallery_json) as f:
            data = json.load(f)
        images = data.get('images', [])
        if images:
            first_img = images[0].get('filename', '')
            # Search for this image in content/
            found = list(CONTENT_DIR.rglob(f'*/{first_img}'))
            if found:
                migrated.add(gallery_id)

    return migrated


def clean_html(html):
    """Convert HTML to plain text for captions."""
    if not html:
        return ""
    text = md(html, strip=['a', 'img'])
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()


def generate_slug(text, max_length=50):
    """Generate URL-safe slug."""
    if not text:
        return "untitled"
    return slugify(text, max_length=max_length, word_boundary=True) or "untitled"


def migrate_orphan_gallery(gallery_json_path):
    """Migrate a single orphan gallery."""
    with open(gallery_json_path) as f:
        data = json.load(f)

    gallery_id = data.get('id', gallery_json_path.stem)
    gallery_name = data.get('name', f'Gallery {gallery_id}')
    images = data.get('images', [])

    if not images:
        return None

    # Create folder: _galleries/{id}-{slug}/
    folder_slug = f"{gallery_id}-{generate_slug(gallery_name)}"
    gallery_folder = OUTPUT_DIR / folder_slug
    gallery_folder.mkdir(parents=True, exist_ok=True)

    # Sort images by order
    sorted_images = sorted(images, key=lambda x: (x.get('order', 999), x.get('id', 0)))

    copied = 0
    for idx, img in enumerate(sorted_images, start=1):
        original_filename = img.get('filename', img.get('path', ''))
        caption = img.get('caption', '')
        author = img.get('author', '')

        if not original_filename:
            continue

        # Generate descriptive filename
        caption_text = re.sub(r'<[^>]+>', '', caption)
        caption_slug = generate_slug(caption_text[:40]) if caption_text else f"image-{img.get('id', idx)}"
        base_name = f"{idx:02d}-{caption_slug}"

        # Copy main image
        src_img = STATIC_GALLERY_DIR / original_filename
        if src_img.exists():
            shutil.copy2(src_img, gallery_folder / f"{base_name}.jpg")
            copied += 1

        # Copy thumbnail
        src_thumb = STATIC_THUMBS_DIR / original_filename
        if src_thumb.exists():
            shutil.copy2(src_thumb, gallery_folder / f"{base_name}.thumb.jpg")

        # Create sidecar .md
        clean_caption = clean_html(caption)
        sidecar_path = gallery_folder / f"{base_name}.md"

        with open(sidecar_path, 'w', encoding='utf-8') as f:
            if author:
                f.write(f"---\nauthor: {author}\n---\n\n")
            else:
                f.write("---\n---\n\n")
            f.write(clean_caption)

    # Create a placeholder _index.md for the gallery
    index_path = gallery_folder / '_index.md'
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(f"""---
title: {gallery_name}
gallery_id: {gallery_id}
status: orphan
---

Tato galerie zatím nemá přiřazenou stránku.
""")

    return copied


def main():
    print("=" * 60)
    print("ORPHAN GALLERY MIGRATION")
    print("=" * 60)

    # Find already migrated galleries
    print("\nScanning for already migrated galleries...")

    # Get all gallery IDs
    all_gallery_ids = set()
    for gj in GALLERIES_JSON_DIR.glob('*.json'):
        all_gallery_ids.add(gj.stem)

    print(f"Total gallery JSONs: {len(all_gallery_ids)}")

    # Find which ones are already in content/ (by checking if their images exist)
    migrated_ids = set()
    for gallery_json in GALLERIES_JSON_DIR.glob('*.json'):
        gallery_id = gallery_json.stem
        with open(gallery_json) as f:
            data = json.load(f)
        images = data.get('images', [])
        if not images:
            continue

        # Check first image filename
        first_img = images[0].get('filename', '')
        if first_img:
            # Search in content (excluding _galleries)
            for found in CONTENT_DIR.rglob(f'gallery/{first_img}'):
                if '_galleries' not in str(found):
                    migrated_ids.add(gallery_id)
                    break

    print(f"Already migrated: {len(migrated_ids)}")

    orphan_ids = all_gallery_ids - migrated_ids
    print(f"Orphan galleries to migrate: {len(orphan_ids)}")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Migrate each orphan
    print("\nMigrating orphan galleries...")
    total_images = 0
    migrated_count = 0

    for gallery_id in sorted(orphan_ids):
        gallery_json = GALLERIES_JSON_DIR / f"{gallery_id}.json"
        if gallery_json.exists():
            result = migrate_orphan_gallery(gallery_json)
            if result:
                migrated_count += 1
                total_images += result
                if migrated_count % 50 == 0:
                    print(f"  Migrated {migrated_count} galleries...")

    print(f"\nMigrated {migrated_count} orphan galleries ({total_images} images)")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
