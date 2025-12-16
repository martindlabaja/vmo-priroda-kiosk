#!/usr/bin/env python3
"""
Export MySQL data to JSON files for the kiosk application.
Connects to the recovered MySQL 5.5 database and exports menu, pages, and galleries.
"""

import json
import mysql.connector
from pathlib import Path
from collections import defaultdict

# Configuration
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3307
MYSQL_USER = 'root'
MYSQL_PASSWORD = ''
MYSQL_DATABASE = 'olomouc'

# Output directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
CONTENT_DIR = DATA_DIR / 'content'
PAGES_CZ_DIR = CONTENT_DIR / 'pages' / 'cz'
GALLERIES_DIR = DATA_DIR / 'galleries'


def connect_db():
    """Connect to MySQL database."""
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset='utf8'
    )


def export_menu(cursor):
    """Export menu table and build hierarchy."""
    print("Exporting menu...")

    # Get all CZ menu items for section 'hlavni'
    cursor.execute("""
        SELECT id, nazev, nazev2, url, nadrazene_menu, poradi, typ
        FROM menu
        WHERE jazyk = 'CZ' AND sekce = 'hlavni'
        ORDER BY nadrazene_menu, poradi
    """)

    rows = cursor.fetchall()
    print(f"  Found {len(rows)} menu items")

    # Build items dict
    items_by_id = {}
    root_items = []

    for row in rows:
        item = {
            'id': row[0],
            'name': row[1] or row[2] or '',
            'name_en': None,
            'url': row[3] or '',
            'parent_id': row[4],
            'order': row[5] or 0,
            'type': row[6],
            'children': []
        }
        items_by_id[item['id']] = item

        if not item['parent_id'] or item['parent_id'] == 0:
            root_items.append(item)

    # Build hierarchy
    for item in items_by_id.values():
        if item['parent_id'] and item['parent_id'] in items_by_id:
            items_by_id[item['parent_id']]['children'].append(item)

    # Sort children by order
    def sort_children(items):
        items.sort(key=lambda x: x['order'])
        for item in items:
            if item['children']:
                sort_children(item['children'])

    sort_children(root_items)

    # Clean up items (remove internal fields and strip hlavni-menu/ from URLs)
    def clean_url(url):
        """Strip hlavni-menu/ prefix from URL."""
        if url and url.startswith('hlavni-menu/'):
            return url[len('hlavni-menu/'):]
        if url == 'hlavni-menu':
            return ''
        return url or ''

    def clean_item(item):
        cleaned = {
            'id': item['id'],
            'name': item['name'],
            'name_en': item['name_en'],
            'url': clean_url(item['url']),
        }
        if item['parent_id']:
            cleaned['parent_id'] = item['parent_id']
        if item['children']:
            cleaned['children'] = [clean_item(c) for c in item['children']]
        else:
            cleaned['children'] = []
        return cleaned

    # Find the "Hlavní menu" root item (id=1) and use its children as actual root
    actual_root_items = root_items
    for item in root_items:
        if item['id'] == 1 and item['children']:
            actual_root_items = item['children']
            break

    menu_data = {
        'root': [clean_item(item) for item in actual_root_items]
    }

    # Save menu.json
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONTENT_DIR / 'menu.json', 'w', encoding='utf-8') as f:
        json.dump(menu_data, f, ensure_ascii=False, indent=2)

    print(f"  Saved menu.json with {len(actual_root_items)} root items")
    return items_by_id


def export_pages(cursor, menu_items):
    """Export stranky (pages) table with URLs from menu."""
    print("Exporting pages...")

    # Get all CZ pages with menu URLs
    cursor.execute("""
        SELECT s.id, s.nadpis, s.text, s.id_menu, s.id_galerie, m.url
        FROM stranky s
        LEFT JOIN menu m ON s.id_menu = m.id
        WHERE s.jazyk = 'CZ' AND m.url IS NOT NULL
    """)

    rows = cursor.fetchall()
    print(f"  Found {len(rows)} pages with menu links")

    PAGES_CZ_DIR.mkdir(parents=True, exist_ok=True)

    pages_exported = 0
    for row in rows:
        page_id, title, content, menu_id, gallery_id, menu_url = row

        if not menu_url:
            continue

        # Clean up URL - remove 'hlavni-menu/' prefix
        url = menu_url.replace('hlavni-menu/', '') if menu_url else ''

        if not url:
            continue

        page = {
            'id': page_id,
            'title': title or '',
            'content': content or '',
            'url': url,
            'menu_id': menu_id,
            'gallery_id': gallery_id
        }

        # Save page file
        safe_url = url.replace('/', '_')
        with open(PAGES_CZ_DIR / f'{safe_url}.json', 'w', encoding='utf-8') as f:
            json.dump(page, f, ensure_ascii=False, indent=2)

        pages_exported += 1

    print(f"  Exported {pages_exported} page files")


def export_galleries(cursor):
    """Export fotogalerie and fotogalerie_obrazky tables."""
    print("Exporting galleries...")

    # Get galleries (no url column in this table)
    cursor.execute("""
        SELECT id, nazev, id_menu
        FROM fotogalerie
    """)
    galleries = cursor.fetchall()
    print(f"  Found {len(galleries)} galleries")

    # Get images
    cursor.execute("""
        SELECT id, clanekid, soubor, popis, autor, poradi
        FROM fotogalerie_obrazky
        ORDER BY clanekid, poradi
    """)
    images = cursor.fetchall()
    print(f"  Found {len(images)} images")

    # Group images by gallery
    images_by_gallery = defaultdict(list)
    for img in images:
        img_id, gallery_id, filename, caption, author, order = img
        images_by_gallery[gallery_id].append({
            'id': img_id,
            'filename': filename or '',
            'path': filename or '',
            'caption': caption,
            'author': author or '',
            'order': order or 0
        })

    GALLERIES_DIR.mkdir(parents=True, exist_ok=True)

    galleries_exported = 0
    for gal in galleries:
        gal_id, name, menu_id = gal

        gallery = {
            'id': gal_id,
            'name': name or '',
            'menu_id': menu_id,
            'description': None,
            'images': sorted(images_by_gallery.get(gal_id, []), key=lambda x: x['order'])
        }

        with open(GALLERIES_DIR / f'{gal_id}.json', 'w', encoding='utf-8') as f:
            json.dump(gallery, f, ensure_ascii=False, indent=2)

        galleries_exported += 1

    print(f"  Exported {galleries_exported} gallery files")


def main():
    print("=" * 60)
    print("MYSQL DATA EXPORT")
    print("=" * 60)

    try:
        conn = connect_db()
        cursor = conn.cursor()

        menu_items = export_menu(cursor)
        export_pages(cursor, menu_items)
        export_galleries(cursor)

        cursor.close()
        conn.close()

        print("\n" + "=" * 60)
        print("EXPORT COMPLETE")
        print("=" * 60)

    except mysql.connector.Error as e:
        print(f"MySQL Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
