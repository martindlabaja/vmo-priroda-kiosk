#!/usr/bin/env python3
"""
Finalize Migration Script
=========================
This script completes the database migration by:
1. Generating individual gallery JSON files from raw extracted data
2. Building the by_url index for menu.json
3. Verifying all referenced images exist
4. Creating a comprehensive audit report
"""

import json
import os
from pathlib import Path
from collections import defaultdict

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
CONTENT_DIR = DATA_DIR / 'content'
GALLERIES_DIR = DATA_DIR / 'galleries'
PAGES_CZ_DIR = CONTENT_DIR / 'pages' / 'cz'
PAGES_EN_DIR = CONTENT_DIR / 'pages' / 'en'

# Image directories (from extracted data)
EXTRACTED_DATA_DIR = BASE_DIR.parent / 'extracted-data' / 'wamp' / 'www' / 'data-fotogalerie'
MENU_IMAGES_DIR = EXTRACTED_DATA_DIR / 'menu'
TILE_IMAGES_DIR = EXTRACTED_DATA_DIR / 'menu' / 'dlazdice'

# Audit results
audit = {
    'galleries': {'total': 0, 'generated': 0, 'errors': []},
    'images': {'total': 0, 'found': 0, 'missing': []},
    'menu': {'total': 0, 'indexed': 0},
    'pages': {'cz': 0, 'en': 0, 'with_content': 0, 'with_gallery': 0},
    'tiles': {'total': 0, 'found': 0, 'missing': []}
}


def load_json(filepath):
    """Load JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath, data):
    """Save JSON file with proper formatting."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_gallery_files():
    """Generate individual gallery JSON files from raw data."""
    print("\n=== Generating Gallery Files ===")

    galleries_file = CONTENT_DIR / 'galleries.json'
    images_file = CONTENT_DIR / 'gallery_images.json'

    if not galleries_file.exists():
        print("ERROR: galleries.json not found!")
        return

    if not images_file.exists():
        print("ERROR: gallery_images.json not found!")
        return

    galleries = load_json(galleries_file)
    images = load_json(images_file)

    audit['galleries']['total'] = len(galleries)
    audit['images']['total'] = len(images)

    # Index images by gallery ID (clanekid)
    images_by_gallery = defaultdict(list)
    for img in images:
        gallery_id = img.get('clanekid')
        if gallery_id:
            images_by_gallery[gallery_id].append(img)

    # Sort images by 'poradi' (order) within each gallery
    for gallery_id in images_by_gallery:
        images_by_gallery[gallery_id].sort(key=lambda x: x.get('poradi', 0))

    # Create galleries directory
    GALLERIES_DIR.mkdir(parents=True, exist_ok=True)

    # Generate individual gallery files
    for gallery in galleries:
        gallery_id = gallery.get('id')
        if not gallery_id:
            continue

        rewrite = gallery.get('rewrite', f'{gallery_id}-')
        gallery_images = images_by_gallery.get(gallery_id, [])

        # Build gallery JSON
        gallery_data = {
            'id': gallery_id,
            'name': gallery.get('nazev', ''),
            'menu_id': gallery.get('id_menu'),
            'description': gallery.get('text', ''),
            'images': []
        }

        for img in gallery_images:
            filename = img.get('soubor', '')
            if not filename:
                continue

            # Image path is just the filename (images are stored flat, not in subdirectories)
            image_path = filename

            image_data = {
                'id': img.get('id'),
                'filename': filename,
                'path': image_path,
                'caption': img.get('popis', ''),
                'author': img.get('autor', ''),
                'order': img.get('poradi', 0)
            }
            gallery_data['images'].append(image_data)

            # Check if image file exists
            full_path = EXTRACTED_DATA_DIR / image_path
            if full_path.exists():
                audit['images']['found'] += 1
            else:
                audit['images']['missing'].append(str(image_path))

        # Save gallery file
        gallery_file = GALLERIES_DIR / f"{gallery_id}.json"
        try:
            save_json(gallery_file, gallery_data)
            audit['galleries']['generated'] += 1
        except Exception as e:
            audit['galleries']['errors'].append(f"Gallery {gallery_id}: {e}")

    print(f"Generated {audit['galleries']['generated']} gallery files")
    print(f"Images found: {audit['images']['found']}/{audit['images']['total']}")
    if audit['images']['missing']:
        print(f"Missing images: {len(audit['images']['missing'])} (first 10: {audit['images']['missing'][:10]})")


def build_menu_index():
    """Build by_url index for menu.json."""
    print("\n=== Building Menu Index ===")

    menu_file = CONTENT_DIR / 'menu.json'
    if not menu_file.exists():
        print("ERROR: menu.json not found!")
        return

    menu = load_json(menu_file)
    root = menu.get('root', [])

    by_url = {}
    by_id = {}

    def index_item(item, parent_url=''):
        """Recursively index menu items."""
        item_id = item.get('id')
        item_url = item.get('url', '')

        if item_url:
            by_url[item_url] = item
        if item_id:
            by_id[item_id] = item

        # Process children
        for child in item.get('children', []):
            index_item(child, item_url)

    for item in root:
        index_item(item)

    audit['menu']['total'] = len(by_url) + len([i for i in root if not i.get('url')])
    audit['menu']['indexed'] = len(by_url)

    # Update menu.json with indexes
    menu['by_url'] = by_url
    menu['by_id'] = by_id

    save_json(menu_file, menu)
    print(f"Indexed {len(by_url)} URLs, {len(by_id)} IDs")


def verify_tile_images():
    """Verify tile images exist for menu items."""
    print("\n=== Verifying Tile Images ===")

    menu_file = CONTENT_DIR / 'menu.json'
    if not menu_file.exists():
        return

    menu = load_json(menu_file)

    def check_tiles(items):
        for item in items:
            item_id = item.get('id')
            if item_id:
                audit['tiles']['total'] += 1
                tile_path = TILE_IMAGES_DIR / f"{item_id}.jpg"
                if tile_path.exists():
                    audit['tiles']['found'] += 1
                else:
                    audit['tiles']['missing'].append(item_id)

            check_tiles(item.get('children', []))

    check_tiles(menu.get('root', []))

    print(f"Tile images found: {audit['tiles']['found']}/{audit['tiles']['total']}")
    if audit['tiles']['missing']:
        print(f"Missing tile images: {len(audit['tiles']['missing'])}")


def audit_pages():
    """Audit page content files."""
    print("\n=== Auditing Page Content ===")

    # Count CZ pages
    if PAGES_CZ_DIR.exists():
        cz_pages = list(PAGES_CZ_DIR.glob('*.json'))
        audit['pages']['cz'] = len(cz_pages)

        for page_file in cz_pages:
            try:
                page = load_json(page_file)
                if page.get('content'):
                    audit['pages']['with_content'] += 1
                if page.get('gallery_id'):
                    audit['pages']['with_gallery'] += 1
            except:
                pass

    # Count EN pages
    if PAGES_EN_DIR.exists():
        audit['pages']['en'] = len(list(PAGES_EN_DIR.glob('*.json')))

    print(f"CZ pages: {audit['pages']['cz']}")
    print(f"EN pages: {audit['pages']['en']}")
    print(f"Pages with content: {audit['pages']['with_content']}")
    print(f"Pages with gallery: {audit['pages']['with_gallery']}")


def link_galleries_to_pages():
    """Ensure pages reference the correct galleries."""
    print("\n=== Linking Galleries to Pages ===")

    # Load page data to find gallery references
    menu_file = CONTENT_DIR / 'menu.json'
    if not menu_file.exists():
        return

    menu = load_json(menu_file)
    galleries = load_json(CONTENT_DIR / 'galleries.json')

    # Build gallery lookup by menu_id
    gallery_by_menu = {}
    for gallery in galleries:
        menu_id = gallery.get('id_menu')
        if menu_id:
            gallery_by_menu[menu_id] = gallery['id']

    linked = 0

    # Update pages with gallery_id based on menu link
    for page_file in PAGES_CZ_DIR.glob('*.json'):
        try:
            page = load_json(page_file)
            menu_id = page.get('menu_id')

            # If page has menu_id and no gallery_id, try to link
            if menu_id and not page.get('gallery_id'):
                gallery_id = gallery_by_menu.get(menu_id)
                if gallery_id:
                    page['gallery_id'] = gallery_id
                    save_json(page_file, page)
                    linked += 1
        except Exception as e:
            pass

    print(f"Linked {linked} galleries to pages")


def generate_audit_report():
    """Generate a comprehensive audit report."""
    print("\n=== MIGRATION AUDIT REPORT ===")
    print("=" * 50)

    print(f"\nGalleries:")
    print(f"  Total in database: {audit['galleries']['total']}")
    print(f"  Files generated: {audit['galleries']['generated']}")
    if audit['galleries']['errors']:
        print(f"  Errors: {len(audit['galleries']['errors'])}")

    print(f"\nGallery Images:")
    print(f"  Total in database: {audit['images']['total']}")
    print(f"  Files found: {audit['images']['found']}")
    print(f"  Files missing: {len(audit['images']['missing'])}")

    print(f"\nMenu Structure:")
    print(f"  Items indexed: {audit['menu']['indexed']}")

    print(f"\nTile Images:")
    print(f"  Expected: {audit['tiles']['total']}")
    print(f"  Found: {audit['tiles']['found']}")
    print(f"  Missing: {len(audit['tiles']['missing'])}")

    print(f"\nPage Content:")
    print(f"  Czech pages: {audit['pages']['cz']}")
    print(f"  English pages: {audit['pages']['en']}")
    print(f"  With content: {audit['pages']['with_content']}")
    print(f"  With gallery: {audit['pages']['with_gallery']}")

    # Save detailed report
    report_file = DATA_DIR / 'migration_audit.json'
    save_json(report_file, audit)
    print(f"\nDetailed report saved to: {report_file}")

    # Summary
    print("\n" + "=" * 50)
    total_issues = (
        len(audit['galleries']['errors']) +
        len(audit['images']['missing']) +
        len(audit['tiles']['missing'])
    )
    if total_issues == 0:
        print("SUCCESS: Migration complete with no issues!")
    else:
        print(f"WARNING: {total_issues} issues found - check report for details")


def main():
    print("=" * 50)
    print("PRIRODA KIOSK - Migration Finalization")
    print("=" * 50)

    # Step 1: Generate gallery files
    generate_gallery_files()

    # Step 2: Build menu index
    build_menu_index()

    # Step 3: Verify tile images
    verify_tile_images()

    # Step 4: Audit pages
    audit_pages()

    # Step 5: Link galleries to pages
    link_galleries_to_pages()

    # Step 6: Generate report
    generate_audit_report()


if __name__ == '__main__':
    main()
