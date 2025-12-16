#!/usr/bin/env python3
"""
MySQL to JSON Migration Script for Příroda Olomouckého Kraje Kiosk

This script converts the MySQL database from the original PHP application
to JSON files for the new Flask-based kiosk.

Usage:
    python migrate-data.py --dump /path/to/mysqldump.sql
    python migrate-data.py --host localhost --user root --db olomouc

Output structure:
    data/content/menu.json          - Menu hierarchy (both languages)
    data/content/pages/cz/*.json    - Czech page content
    data/content/pages/en/*.json    - English page content
    data/galleries/*.json           - Gallery metadata
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any


class MySQLDumpParser:
    """Parse MySQL dump file to extract data."""

    def __init__(self, dump_path: str):
        self.dump_path = dump_path
        self.tables: Dict[str, List[Dict]] = {}

    def parse(self) -> Dict[str, List[Dict]]:
        """Parse the dump file and extract table data."""
        if not os.path.exists(self.dump_path):
            raise FileNotFoundError(f"Dump file not found: {self.dump_path}")

        with open(self.dump_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        # Find all INSERT statements
        insert_pattern = r"INSERT INTO `?(\w+)`?\s+(?:\([^)]+\)\s+)?VALUES\s*(.+?);"

        for match in re.finditer(insert_pattern, content, re.DOTALL | re.IGNORECASE):
            table_name = match.group(1)
            values_str = match.group(2)

            if table_name not in self.tables:
                self.tables[table_name] = []

            # Parse values - handle multiple rows
            rows = self._parse_values(values_str)
            self.tables[table_name].extend(rows)

        return self.tables

    def _parse_values(self, values_str: str) -> List[Dict]:
        """Parse VALUES clause into list of dicts."""
        rows = []

        # Split by ),( pattern to get individual rows
        # This is a simplified parser - may need refinement for complex data
        row_pattern = r"\(([^)]+)\)"

        for match in re.finditer(row_pattern, values_str):
            row_str = match.group(1)
            values = self._parse_row(row_str)
            rows.append(values)

        return rows

    def _parse_row(self, row_str: str) -> Dict:
        """Parse a single row of values."""
        values = []
        current = ""
        in_string = False
        string_char = None
        escape_next = False

        for char in row_str:
            if escape_next:
                current += char
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                current += char
                continue

            if char in ('"', "'") and not in_string:
                in_string = True
                string_char = char
                continue
            elif char == string_char and in_string:
                in_string = False
                string_char = None
                continue

            if char == ',' and not in_string:
                values.append(current.strip())
                current = ""
                continue

            current += char

        if current:
            values.append(current.strip())

        # Convert to dict with numeric indices (we don't have column names from INSERT)
        return {str(i): v for i, v in enumerate(values)}


class DataMigrator:
    """Migrate MySQL data to JSON format."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.menu_data: Dict[str, Any] = {"cz": {}, "en": {}}
        self.pages_data: Dict[str, Dict] = {"cz": {}, "en": {}}
        self.galleries_data: Dict[str, Dict] = {}

    def migrate_from_dump(self, dump_path: str):
        """Migrate data from MySQL dump file."""
        parser = MySQLDumpParser(dump_path)
        tables = parser.parse()

        print(f"Found tables: {list(tables.keys())}")

        # Process menu table
        if 'menu' in tables:
            self._process_menu(tables['menu'])

        # Process stranky (pages) table
        if 'stranky' in tables:
            self._process_pages(tables['stranky'])

        # Process fotogalerie tables
        if 'fotogalerie' in tables:
            self._process_galleries(tables['fotogalerie'],
                                   tables.get('fotogalerie_obrazky', []))

        self._write_output()

    def migrate_from_db(self, host: str, user: str, password: str, database: str):
        """Migrate data directly from MySQL database."""
        try:
            import mysql.connector
        except ImportError:
            print("Error: mysql-connector-python not installed")
            print("Run: pip install mysql-connector-python")
            sys.exit(1)

        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            charset='utf8'
        )
        cursor = conn.cursor(dictionary=True)

        # Get menu items
        cursor.execute("SELECT * FROM menu ORDER BY nadrazene_menu, poradi")
        menu_rows = cursor.fetchall()
        self._process_menu_rows(menu_rows)

        # Get pages
        cursor.execute("SELECT * FROM stranky")
        pages_rows = cursor.fetchall()
        self._process_pages_rows(pages_rows)

        # Get galleries
        cursor.execute("SELECT * FROM fotogalerie")
        galleries_rows = cursor.fetchall()

        cursor.execute("SELECT * FROM fotogalerie_obrazky ORDER BY clanekid, poradi")
        images_rows = cursor.fetchall()
        self._process_galleries_rows(galleries_rows, images_rows)

        cursor.close()
        conn.close()

        self._write_output()

    def _process_menu_rows(self, rows: List[Dict]):
        """Process menu rows from database."""
        # Build tree structure
        items_by_id = {}
        root_items = []

        for row in rows:
            item = {
                "id": row['id'],
                "name_cz": row.get('nazev', ''),
                "name_en": row.get('nazev_en', row.get('nazev', '')),
                "url": row.get('url', ''),
                "url_en": row.get('url_en', row.get('url', '')),
                "parent_id": row.get('nadrazene_menu', 0),
                "order": row.get('poradi', 0),
                "children": []
            }
            items_by_id[item['id']] = item

            if item['parent_id'] == 0:
                root_items.append(item)

        # Build hierarchy
        for item in items_by_id.values():
            if item['parent_id'] and item['parent_id'] in items_by_id:
                items_by_id[item['parent_id']]['children'].append(item)

        # Sort by order
        for item in items_by_id.values():
            item['children'].sort(key=lambda x: x['order'])
        root_items.sort(key=lambda x: x['order'])

        self.menu_data = {
            "root": root_items,
            "by_id": items_by_id
        }

    def _process_pages_rows(self, rows: List[Dict]):
        """Process page rows from database."""
        for row in rows:
            lang = row.get('jazyk', 'CZ').lower()
            if lang not in self.pages_data:
                lang = 'cz'

            page = {
                "id": row.get('id'),
                "title": row.get('nadpis', ''),
                "content": row.get('text', ''),
                "url": row.get('rewrite', ''),
                "menu_id": row.get('id_menu'),
                "gallery_id": row.get('id_galerie')
            }

            url = page['url']
            if url:
                self.pages_data[lang][url] = page

    def _process_galleries_rows(self, galleries: List[Dict], images: List[Dict]):
        """Process gallery rows from database."""
        # Group images by gallery
        images_by_gallery = {}
        for img in images:
            gid = img.get('clanekid')
            if gid not in images_by_gallery:
                images_by_gallery[gid] = []
            images_by_gallery[gid].append({
                "id": img.get('id'),
                "filename": img.get('soubor', ''),
                "title": img.get('popisek', ''),
                "order": img.get('poradi', 0)
            })

        for gallery in galleries:
            gid = gallery.get('id')
            self.galleries_data[str(gid)] = {
                "id": gid,
                "title": gallery.get('nazev', ''),
                "menu_url": gallery.get('url', ''),
                "images": sorted(images_by_gallery.get(gid, []),
                               key=lambda x: x['order'])
            }

    def _process_menu(self, rows: List[Dict]):
        """Process menu table from dump (index-based values)."""
        # This needs column mapping - column order from original schema
        # Typical: id, nazev, url, nadrazene_menu, poradi, ...
        print(f"Processing {len(rows)} menu items...")
        # Without column names, we need to map by position
        # This is placeholder - actual mapping depends on dump format

    def _process_pages(self, rows: List[Dict]):
        """Process stranky (pages) table from dump."""
        print(f"Processing {len(rows)} pages...")

    def _process_galleries(self, galleries: List[Dict], images: List[Dict]):
        """Process gallery tables from dump."""
        print(f"Processing {len(galleries)} galleries with {len(images)} images...")

    def _write_output(self):
        """Write processed data to JSON files."""
        # Ensure directories exist
        content_dir = self.output_dir / "content"
        pages_cz_dir = content_dir / "pages" / "cz"
        pages_en_dir = content_dir / "pages" / "en"
        galleries_dir = self.output_dir / "galleries"

        for d in [content_dir, pages_cz_dir, pages_en_dir, galleries_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Write menu.json
        menu_path = content_dir / "menu.json"
        with open(menu_path, 'w', encoding='utf-8') as f:
            json.dump(self.menu_data, f, ensure_ascii=False, indent=2)
        print(f"Written: {menu_path}")

        # Write page files
        for url, page in self.pages_data['cz'].items():
            safe_url = url.replace('/', '_')
            page_path = pages_cz_dir / f"{safe_url}.json"
            with open(page_path, 'w', encoding='utf-8') as f:
                json.dump(page, f, ensure_ascii=False, indent=2)
        print(f"Written: {len(self.pages_data['cz'])} Czech pages")

        for url, page in self.pages_data['en'].items():
            safe_url = url.replace('/', '_')
            page_path = pages_en_dir / f"{safe_url}.json"
            with open(page_path, 'w', encoding='utf-8') as f:
                json.dump(page, f, ensure_ascii=False, indent=2)
        print(f"Written: {len(self.pages_data['en'])} English pages")

        # Write gallery files
        for gid, gallery in self.galleries_data.items():
            gallery_path = galleries_dir / f"{gid}.json"
            with open(gallery_path, 'w', encoding='utf-8') as f:
                json.dump(gallery, f, ensure_ascii=False, indent=2)
        print(f"Written: {len(self.galleries_data)} galleries")


def create_sample_data(output_dir: str):
    """Create sample data based on known structure for testing."""
    output_path = Path(output_dir)

    # Sample menu structure based on original application
    menu_data = {
        "root": [
            {
                "id": 103,
                "name": "Geologie a mineralogie",
                "name_en": "Geology and Mineralogy",
                "url": "geologie",
                "url_en": "geology",
                "image": True,
                "children": [
                    {"id": 105, "name": "Geologická minulost", "name_en": "Geological Past",
                     "url": "geologie/geologicka-minulost", "url_en": "geology/geological-past"},
                    {"id": 106, "name": "Minerály", "name_en": "Minerals",
                     "url": "geologie/mineraly", "url_en": "geology/minerals"},
                    {"id": 107, "name": "Horniny", "name_en": "Rocks",
                     "url": "geologie/horniny", "url_en": "geology/rocks"}
                ]
            },
            {
                "id": 104,
                "name": "Živá příroda",
                "name_en": "Living Nature",
                "url": "ziva-priroda",
                "url_en": "living-nature",
                "image": True,
                "type": "tile-section",
                "children": [
                    {
                        "id": 108, "name": "Rostliny", "name_en": "Plants",
                        "url": "ziva-priroda/rostliny", "url_en": "living-nature/plants",
                        "children": [
                            {"id": 120, "name": "Mechy", "name_en": "Mosses",
                             "url": "ziva-priroda/rostliny/mechy", "url_en": "living-nature/plants/mosses"},
                            {"id": 121, "name": "Kapradiny", "name_en": "Ferns",
                             "url": "ziva-priroda/rostliny/kapradiny", "url_en": "living-nature/plants/ferns"},
                            {"id": 122, "name": "Byliny", "name_en": "Herbs",
                             "url": "ziva-priroda/rostliny/byliny", "url_en": "living-nature/plants/herbs"}
                        ]
                    },
                    {
                        "id": 109, "name": "Houby", "name_en": "Fungi",
                        "url": "ziva-priroda/houby", "url_en": "living-nature/fungi",
                        "children": []
                    },
                    {
                        "id": 110, "name": "Živočichové", "name_en": "Animals",
                        "url": "ziva-priroda/zivocichove", "url_en": "living-nature/animals",
                        "children": [
                            {"id": 130, "name": "Hmyz", "name_en": "Insects",
                             "url": "ziva-priroda/zivocichove/hmyz", "url_en": "living-nature/animals/insects"},
                            {"id": 131, "name": "Ptáci", "name_en": "Birds",
                             "url": "ziva-priroda/zivocichove/ptaci", "url_en": "living-nature/animals/birds"},
                            {"id": 132, "name": "Savci", "name_en": "Mammals",
                             "url": "ziva-priroda/zivocichove/savci", "url_en": "living-nature/animals/mammals"}
                        ]
                    }
                ]
            },
            {
                "id": 111,
                "name": "Chráněná území",
                "name_en": "Protected Areas",
                "url": "chranena-uzemi",
                "url_en": "protected-areas",
                "image": True,
                "children": []
            },
            {
                "id": 112,
                "name": "Použitá literatura",
                "name_en": "References",
                "url": "pouzita-literatura",
                "url_en": "references",
                "image": True,
                "children": []
            },
            {
                "id": 113,
                "name": "O expozici muzea",
                "name_en": "About the Exhibition",
                "url": "o-expozici",
                "url_en": "about",
                "image": True,
                "children": []
            }
        ]
    }

    # Build by_id and by_url indexes
    def build_index(items, by_id={}, by_url={}):
        for item in items:
            by_id[item['id']] = item
            by_url[item['url']] = item
            if item.get('url_en'):
                by_url[item['url_en']] = item
            if item.get('children'):
                build_index(item['children'], by_id, by_url)
        return by_id, by_url

    by_id, by_url = build_index(menu_data['root'])
    menu_data['by_id'] = {str(k): v for k, v in by_id.items()}
    menu_data['by_url'] = by_url

    # Create directories
    content_dir = output_path / "content"
    pages_cz_dir = content_dir / "pages" / "cz"
    pages_en_dir = content_dir / "pages" / "en"
    galleries_dir = output_path / "galleries"

    for d in [content_dir, pages_cz_dir, pages_en_dir, galleries_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Write menu.json
    with open(content_dir / "menu.json", 'w', encoding='utf-8') as f:
        json.dump(menu_data, f, ensure_ascii=False, indent=2)

    # Sample pages - Czech
    sample_pages_cz = {
        "geologie": {
            "id": 103,
            "title": "Geologie a mineralogie",
            "url": "geologie",
            "description": "<p>Geologie Olomouckého kraje je velmi pestrá a zajímavá. Najdeme zde horniny všech geologických období od starohor až po čtvrtohory.</p>",
            "image": True,
            "has_gallery": True,
            "gallery_id": 1
        },
        "ziva-priroda": {
            "id": 104,
            "title": "Živá příroda",
            "url": "ziva-priroda",
            "type": "tile-section",
            "description": "<p>Živá příroda Olomouckého kraje zahrnuje pestrou škálu rostlin, hub a živočichů typických pro střední Evropu.</p>",
            "image": True
        },
        "chranena-uzemi": {
            "id": 111,
            "title": "Chráněná území",
            "url": "chranena-uzemi",
            "description": "<p>V Olomouckém kraji se nachází řada chráněných území různých kategorií.</p>",
            "image": True,
            "has_gallery": True,
            "gallery_id": 2
        },
        "pouzita-literatura": {
            "id": 112,
            "title": "Použitá literatura",
            "url": "pouzita-literatura",
            "description": "<p>Seznam použité literatury a zdrojů informací.</p>",
            "image": False
        },
        "o-expozici": {
            "id": 113,
            "title": "O expozici muzea",
            "url": "o-expozici",
            "description": "<p>Expozice Příroda Olomouckého kraje byla otevřena v roce 2012 ve Vlastivědném muzeu v Olomouci.</p>",
            "image": True
        }
    }

    # Sample pages - English
    sample_pages_en = {
        "geology": {
            "id": 103,
            "title": "Geology and Mineralogy",
            "url": "geology",
            "description": "<p>The geology of the Olomouc Region is very diverse and interesting. Here we find rocks from all geological periods from the Proterozoic to the Quaternary.</p>",
            "image": True,
            "has_gallery": True,
            "gallery_id": 1
        },
        "living-nature": {
            "id": 104,
            "title": "Living Nature",
            "url": "living-nature",
            "type": "tile-section",
            "description": "<p>The living nature of the Olomouc Region includes a diverse range of plants, fungi and animals typical of Central Europe.</p>",
            "image": True
        },
        "protected-areas": {
            "id": 111,
            "title": "Protected Areas",
            "url": "protected-areas",
            "description": "<p>The Olomouc Region contains a number of protected areas of various categories.</p>",
            "image": True,
            "has_gallery": True,
            "gallery_id": 2
        },
        "references": {
            "id": 112,
            "title": "References",
            "url": "references",
            "description": "<p>List of literature and information sources used.</p>",
            "image": False
        },
        "about": {
            "id": 113,
            "title": "About the Exhibition",
            "url": "about",
            "description": "<p>The Nature of Olomouc Region exhibition was opened in 2012 at the Regional Museum in Olomouc.</p>",
            "image": True
        }
    }

    # Write page files
    for url, page in sample_pages_cz.items():
        with open(pages_cz_dir / f"{url}.json", 'w', encoding='utf-8') as f:
            json.dump(page, f, ensure_ascii=False, indent=2)

    for url, page in sample_pages_en.items():
        with open(pages_en_dir / f"{url}.json", 'w', encoding='utf-8') as f:
            json.dump(page, f, ensure_ascii=False, indent=2)

    # Sample galleries
    sample_galleries = {
        "1": {
            "id": 1,
            "title": "Geologie",
            "menu_id": 103,
            "images": [
                {"id": 1, "filename": "1.jpg", "title": "Geologická mapa", "order": 1},
                {"id": 2, "filename": "2.jpg", "title": "Minerál křemen", "order": 2},
                {"id": 3, "filename": "3.jpg", "title": "Vzorek horniny", "order": 3}
            ]
        },
        "2": {
            "id": 2,
            "title": "Chráněná území",
            "menu_id": 111,
            "images": [
                {"id": 10, "filename": "10.jpg", "title": "CHKO Jeseníky", "order": 1},
                {"id": 11, "filename": "11.jpg", "title": "PR Velký Kosíř", "order": 2}
            ]
        }
    }

    for gid, gallery in sample_galleries.items():
        with open(galleries_dir / f"{gid}.json", 'w', encoding='utf-8') as f:
            json.dump(gallery, f, ensure_ascii=False, indent=2)

    print(f"Sample data created in {output_path}")
    print(f"  - menu.json")
    print(f"  - {len(sample_pages_cz)} Czech pages")
    print(f"  - {len(sample_pages_en)} English pages")
    print(f"  - {len(sample_galleries)} galleries")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate MySQL data to JSON for Příroda kiosk'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Dump file migration
    dump_parser = subparsers.add_parser('dump', help='Migrate from MySQL dump file')
    dump_parser.add_argument('--file', '-f', required=True, help='Path to MySQL dump file')
    dump_parser.add_argument('--output', '-o', default='../data', help='Output directory')

    # Direct DB migration
    db_parser = subparsers.add_parser('db', help='Migrate directly from MySQL database')
    db_parser.add_argument('--host', default='localhost', help='MySQL host')
    db_parser.add_argument('--user', '-u', default='root', help='MySQL user')
    db_parser.add_argument('--password', '-p', default='', help='MySQL password')
    db_parser.add_argument('--database', '-d', default='olomouc', help='Database name')
    db_parser.add_argument('--output', '-o', default='../data', help='Output directory')

    # Sample data generation
    sample_parser = subparsers.add_parser('sample', help='Create sample data for testing')
    sample_parser.add_argument('--output', '-o', default='../data', help='Output directory')

    args = parser.parse_args()

    if args.command == 'dump':
        migrator = DataMigrator(args.output)
        migrator.migrate_from_dump(args.file)
    elif args.command == 'db':
        migrator = DataMigrator(args.output)
        migrator.migrate_from_db(args.host, args.user, args.password, args.database)
    elif args.command == 'sample':
        create_sample_data(args.output)
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python migrate-data.py sample -o ../data")
        print("  python migrate-data.py dump -f /path/to/dump.sql -o ../data")
        print("  python migrate-data.py db -u root -d olomouc -o ../data")


if __name__ == '__main__':
    main()
