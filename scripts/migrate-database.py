#!/usr/bin/env python3
"""
MySQL Binary Log Parser for Priroda Kiosk Database Migration

Extracts data from MySQL binary logs and generates JSON files for the kiosk application.
"""

import re
import json
import os
from pathlib import Path


# Paths
MYSQL_RECOVERY_DIR = Path('/mnt/d/Muzeum/PrirodaTouch/mysql-recovery')
OUTPUT_DIR = Path('/mnt/d/Muzeum/PrirodaTouch/priroda-kiosk/data/content')
BINLOG_FILES = [
    MYSQL_RECOVERY_DIR / 'mysql-bin.000001',
    MYSQL_RECOVERY_DIR / 'mysql-bin.000002',
]


def read_binary_log(filepath):
    """Read binary log file and return decoded text."""
    with open(filepath, 'rb') as f:
        data = f.read()
    return data.decode('latin-1', errors='replace')


def fix_encoding(text):
    """Fix UTF-8 that was mis-decoded as Latin-1."""
    if not text:
        return text
    try:
        # The text was UTF-8 but decoded as Latin-1, so we encode it back and decode as UTF-8
        return text.encode('latin-1').decode('utf-8', errors='replace')
    except:
        return text


def extract_table_data(text, table_name):
    """Extract all rows from INSERT statements for a given table."""
    rows = []

    # Find all INSERT statements for this table
    search_str = f"INSERT INTO `{table_name}`"
    start_pos = 0

    while True:
        pos = text.find(search_str, start_pos)
        if pos == -1:
            break

        # Find VALUES keyword
        values_pos = text.find("VALUES", pos)
        if values_pos == -1 or values_pos > pos + 500:  # VALUES should be within 500 chars
            start_pos = pos + 1
            continue

        # Extract all row tuples after VALUES
        data_start = values_pos + 6  # len("VALUES")

        # Find the end of this INSERT (look for semicolon or next INSERT)
        end_pos = len(text)
        next_insert = text.find("INSERT INTO", data_start)
        if next_insert > 0:
            end_pos = min(end_pos, next_insert)

        # Also look for binary garbage (null bytes indicate end of SQL)
        null_pos = text.find('\x00', data_start)
        if null_pos > 0 and null_pos < end_pos:
            end_pos = null_pos

        # Extract the values section
        values_section = text[data_start:end_pos]

        # Parse individual row tuples
        paren_depth = 0
        current_row = ""
        in_string = False
        string_char = None
        i = 0

        while i < len(values_section):
            char = values_section[i]

            if not in_string:
                if char == "'" or char == '"':
                    in_string = True
                    string_char = char
                    current_row += char
                elif char == '(':
                    paren_depth += 1
                    if paren_depth == 1:
                        current_row = ""
                    else:
                        current_row += char
                elif char == ')':
                    paren_depth -= 1
                    if paren_depth == 0:
                        rows.append(current_row)
                        current_row = ""
                    else:
                        current_row += char
                elif paren_depth > 0:
                    current_row += char
            else:
                current_row += char
                if char == string_char:
                    # Check for escaped quote
                    if i + 1 < len(values_section) and values_section[i + 1] == string_char:
                        current_row += string_char
                        i += 1
                    else:
                        in_string = False
                        string_char = None
                elif char == '\\' and i + 1 < len(values_section):
                    # Handle escaped characters
                    current_row += values_section[i + 1]
                    i += 1

            i += 1

        start_pos = end_pos

    return rows


def parse_sql_values(row_str):
    """Parse a SQL VALUES tuple into a list of Python values."""
    values = []
    current = ""
    in_string = False
    string_char = None
    string_value = None  # Stores the string value when completed
    i = 0

    while i < len(row_str):
        char = row_str[i]

        if not in_string:
            if char in ("'", '"'):
                in_string = True
                string_char = char
                string_value = ""
            elif char == ',':
                if string_value is not None:
                    # We just finished a string, use that value
                    values.append(string_value)
                    string_value = None
                else:
                    # Parse the non-string value
                    val = current.strip()
                    if val.upper() == 'NULL':
                        values.append(None)
                    elif val.lstrip('-').isdigit():
                        values.append(int(val))
                    elif val:
                        values.append(val)
                current = ""
            else:
                current += char
        else:
            if char == string_char:
                # Check for escaped quote
                if i + 1 < len(row_str) and row_str[i + 1] == string_char:
                    string_value += char
                    i += 1
                else:
                    # String ended - store the value
                    in_string = False
                    string_char = None
            elif char == '\\' and i + 1 < len(row_str):
                next_char = row_str[i + 1]
                if next_char == 'n':
                    string_value += '\n'
                elif next_char == 'r':
                    string_value += '\r'
                elif next_char == 't':
                    string_value += '\t'
                elif next_char == '\\':
                    string_value += '\\'
                elif next_char in ("'", '"'):
                    string_value += next_char
                else:
                    string_value += next_char
                i += 1
            else:
                string_value += char

        i += 1

    # Handle last value
    if string_value is not None:
        values.append(string_value)
    else:
        val = current.strip()
        if val:
            if val.upper() == 'NULL':
                values.append(None)
            elif val.lstrip('-').isdigit():
                values.append(int(val))
            else:
                values.append(val)

    return values


def parse_menu_items(rows):
    """Parse menu table rows."""
    # Menu columns: id, id_kategorie, typ, nazev, nazev2, url, nadrazene_menu, poradi, jazyk, sekce, target, razeni, otevrena_v_menu, vyhledavani
    items = []
    for row in rows:
        values = parse_sql_values(row)
        if len(values) >= 14:
            items.append({
                'id': values[0],
                'id_kategorie': values[1],
                'typ': values[2],
                'nazev': fix_encoding(values[3]) if values[3] else None,
                'nazev2': fix_encoding(values[4]) if values[4] else None,
                'url': values[5],
                'nadrazene_menu': values[6],
                'poradi': values[7],
                'jazyk': values[8],
                'sekce': values[9],
                'target': values[10],
                'razeni': values[11],
                'otevrena_v_menu': values[12],
                'vyhledavani': values[13],
            })
    return items


def parse_stranky_items(rows):
    """Parse stranky (pages) table rows."""
    # stranky columns: id, rewrite, nadpis, text, jazyk, homepage, id_menu, id_script_head, id_script_foot, id_galerie, keywords, description, needitovatelny
    items = []
    for row in rows:
        values = parse_sql_values(row)
        if len(values) >= 7:
            items.append({
                'id': values[0],
                'rewrite': values[1],
                'nadpis': fix_encoding(values[2]) if len(values) > 2 and values[2] else None,
                'text': fix_encoding(values[3]) if len(values) > 3 and values[3] else None,
                'jazyk': values[4] if len(values) > 4 else None,
                'homepage': values[5] if len(values) > 5 else None,
                'id_menu': values[6] if len(values) > 6 else None,
                'id_galerie': values[9] if len(values) > 9 else None,
            })
    return items


def parse_fotogalerie_items(rows):
    """Parse fotogalerie table rows."""
    # fotogalerie columns: id, id_menu, nazev, odstavec, text, datum, vlozil, jazyk, rewrite, aktivni
    items = []
    for row in rows:
        values = parse_sql_values(row)
        if len(values) >= 8:
            items.append({
                'id': values[0],
                'id_menu': values[1],
                'nazev': fix_encoding(values[2]) if values[2] else None,
                'odstavec': fix_encoding(values[3]) if len(values) > 3 and values[3] else None,
                'text': fix_encoding(values[4]) if len(values) > 4 and values[4] else None,
                'jazyk': values[7] if len(values) > 7 else None,
                'rewrite': values[8] if len(values) > 8 else None,
            })
    return items


def parse_fotogalerie_obrazky_items(rows):
    """Parse fotogalerie_obrazky table rows."""
    # fotogalerie_obrazky columns: id, clanekid, soubor, x, y, thumb_x, thumb_y, popis, autor, poradi
    items = []
    for row in rows:
        values = parse_sql_values(row)
        if len(values) >= 3:
            items.append({
                'id': values[0],
                'clanekid': values[1],  # gallery ID
                'soubor': values[2],    # filename
                'x': values[3] if len(values) > 3 else None,
                'y': values[4] if len(values) > 4 else None,
                'thumb_x': values[5] if len(values) > 5 else None,
                'thumb_y': values[6] if len(values) > 6 else None,
                'popis': fix_encoding(values[7]) if len(values) > 7 and values[7] else None,
                'autor': values[8] if len(values) > 8 else None,
                'poradi': values[9] if len(values) > 9 else None,
            })
    return items


def deduplicate(items, key='id'):
    """Remove duplicate items, keeping the last occurrence."""
    seen = {}
    for item in items:
        if item.get(key) is not None:
            seen[item[key]] = item
    return list(seen.values())


def generate_menu_json(menu_items):
    """Generate the menu.json structure for the kiosk app."""
    cz_items = [m for m in menu_items if m and m.get('jazyk') == 'CZ']
    en_items = [m for m in menu_items if m and m.get('jazyk') == 'EN']

    items_by_id = {m['id']: m for m in cz_items}
    en_by_url = {}
    for item in en_items:
        url = item.get('url', '').replace('homepage/', '')
        en_by_url[url] = item

    # Find root items (parent=1 for CZ which is "Hlavní menu")
    root_sections = []
    for item in cz_items:
        if item.get('nadrazene_menu') == 1:
            url = item.get('url', '').replace('hlavni-menu/', '')

            # Find English name from EN menu items
            en_item = en_by_url.get(url)
            name_en = en_item.get('nazev') if en_item else item.get('nazev2')

            section = {
                'id': item['id'],
                'name': item['nazev'],
                'name_en': name_en,
                'url': url,
                'children': []
            }

            # Find children recursively
            def add_children(parent_item, parent_node, depth=0):
                if depth > 5:  # Prevent infinite recursion
                    return
                for child in cz_items:
                    if child.get('nadrazene_menu') == parent_item['id']:
                        # Extract last URL segment
                        child_url = child.get('url', '').split('/')[-1]
                        full_url = f"{parent_node['url']}/{child_url}" if parent_node['url'] else child_url

                        # Find English name
                        en_child = en_by_url.get(full_url.replace('hlavni-menu/', ''))
                        child_name_en = en_child.get('nazev') if en_child else child.get('nazev2')

                        child_node = {
                            'id': child['id'],
                            'name': child['nazev'],
                            'name_en': child_name_en,
                            'url': full_url,
                            'parent_id': parent_item['id'],
                            'children': []
                        }

                        add_children(child, child_node, depth + 1)

                        child_node['children'].sort(key=lambda x: (x.get('poradi', 0), x.get('id', 0)))
                        parent_node['children'].append(child_node)

                parent_node['children'].sort(key=lambda x: (x.get('poradi', 0), x.get('id', 0)))

            add_children(item, section)
            root_sections.append(section)

    root_sections.sort(key=lambda x: x.get('id', 0))

    return {'root': root_sections}


def main():
    print("=" * 60)
    print("Priroda Kiosk Database Migration")
    print("=" * 60)

    # Read all binary logs
    all_text = ""
    for binlog in BINLOG_FILES:
        if binlog.exists():
            print(f"Reading {binlog.name}...")
            all_text += read_binary_log(binlog)

    print(f"Total text length: {len(all_text)} characters")

    # Extract menu data
    print("\nExtracting menu data...")
    menu_rows = extract_table_data(all_text, 'menu')
    print(f"Found {len(menu_rows)} menu rows")
    menu_items = parse_menu_items(menu_rows)
    menu_items = deduplicate(menu_items)
    print(f"Parsed {len(menu_items)} unique menu items")

    # Extract pages data
    print("\nExtracting pages data...")
    page_rows = extract_table_data(all_text, 'stranky')
    print(f"Found {len(page_rows)} page rows")
    pages = parse_stranky_items(page_rows)
    pages = deduplicate(pages)
    print(f"Parsed {len(pages)} unique pages")

    # Extract gallery data
    print("\nExtracting gallery data...")
    gallery_rows = extract_table_data(all_text, 'fotogalerie')
    print(f"Found {len(gallery_rows)} gallery rows")
    galleries = parse_fotogalerie_items(gallery_rows)
    galleries = deduplicate(galleries)
    print(f"Parsed {len(galleries)} unique galleries")

    # Extract gallery images
    print("\nExtracting gallery images...")
    image_rows = extract_table_data(all_text, 'fotogalerie_obrazky')
    print(f"Found {len(image_rows)} image rows")
    images = parse_fotogalerie_obrazky_items(image_rows)
    images = deduplicate(images)
    print(f"Parsed {len(images)} unique images")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate and write menu.json
    print("\nGenerating menu.json...")
    menu_json = generate_menu_json(menu_items)

    menu_path = OUTPUT_DIR / 'menu.json'
    with open(menu_path, 'w', encoding='utf-8') as f:
        json.dump(menu_json, f, ensure_ascii=False, indent=2)
    print(f"Wrote {menu_path}")

    # Write raw data for reference
    raw_menu_path = OUTPUT_DIR / 'menu_raw.json'
    with open(raw_menu_path, 'w', encoding='utf-8') as f:
        json.dump(menu_items, f, ensure_ascii=False, indent=2)
    print(f"Wrote {raw_menu_path}")

    # Write galleries
    galleries_path = OUTPUT_DIR / 'galleries.json'
    with open(galleries_path, 'w', encoding='utf-8') as f:
        json.dump(galleries, f, ensure_ascii=False, indent=2)
    print(f"Wrote {galleries_path}")

    # Write gallery images
    gallery_images_path = OUTPUT_DIR / 'gallery_images.json'
    with open(gallery_images_path, 'w', encoding='utf-8') as f:
        json.dump(images, f, ensure_ascii=False, indent=2)
    print(f"Wrote {gallery_images_path}")

    # Write page content files
    pages_cz_dir = OUTPUT_DIR / 'pages' / 'cz'
    pages_en_dir = OUTPUT_DIR / 'pages' / 'en'
    pages_cz_dir.mkdir(parents=True, exist_ok=True)
    pages_en_dir.mkdir(parents=True, exist_ok=True)

    menu_by_id = {m['id']: m for m in menu_items}

    page_count = 0
    for page in pages:
        if page.get('id_menu') and page.get('text'):
            menu_item = menu_by_id.get(page['id_menu'])
            if menu_item:
                url = menu_item.get('url', '').replace('hlavni-menu/', '').replace('homepage/', '')
                url_safe = url.replace('/', '_') if url else f"page_{page['id']}"

                lang = page.get('jazyk', 'CZ')
                target_dir = pages_cz_dir if lang == 'CZ' else pages_en_dir

                page_data = {
                    'id': page['id'],
                    'menu_id': page['id_menu'],
                    'title': page['nadpis'],
                    'content': page['text'],
                    'gallery_id': page.get('id_galerie'),
                    'url': url,
                }

                page_path = target_dir / f"{url_safe}.json"
                with open(page_path, 'w', encoding='utf-8') as f:
                    json.dump(page_data, f, ensure_ascii=False, indent=2)
                page_count += 1

    print(f"Wrote {page_count} page files")

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)

    # Print summary
    print(f"\nMenu structure:")
    for section in menu_json.get('root', [])[:5]:
        print(f"  - {section['name']} ({section['url']})")
        for child in section.get('children', [])[:3]:
            print(f"      - {child['name']}")
            for grandchild in child.get('children', [])[:2]:
                print(f"          - {grandchild['name']}")


if __name__ == '__main__':
    main()
