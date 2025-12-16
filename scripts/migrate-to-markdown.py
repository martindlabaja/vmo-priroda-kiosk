#!/usr/bin/env python3
"""
Migrate JSON-based content to filesystem-based Markdown structure.

This script converts:
- Page JSONs → Markdown files with YAML frontmatter
- Gallery JSONs → Gallery folders with images + sidecar .md files
- Tile/header images → Co-located with content

Output structure (everything in content/):
  content/
    ├── menu.yaml
    ├── geologie/
    │   ├── _index.md
    │   ├── tile.jpg
    │   ├── header.jpg
    │   └── kras-olomouckeho-kraje/
    │       └── okres-olomouc/
    │           └── javoricske-jeskyne/
    │               ├── page.md
    │               ├── tile.jpg
    │               ├── header.jpg
    │               └── gallery/
    │                   ├── 01-dom-gigantu.jpg
    │                   ├── 01-dom-gigantu.thumb.jpg
    │                   └── 01-dom-gigantu.md
"""

import json
import re
import shutil
from pathlib import Path
from typing import Optional

import yaml
from markdownify import markdownify as md
from slugify import slugify


# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
STATIC_DIR = BASE_DIR / 'static'

# Input paths
MENU_JSON = DATA_DIR / 'content' / 'menu.json'
PAGES_DIR = DATA_DIR / 'content' / 'pages' / 'cz'
GALLERIES_DIR = DATA_DIR / 'galleries'
GALLERY_IMAGES_DIR = STATIC_DIR / 'images' / 'gallery'
TILES_DIR = STATIC_DIR / 'images' / 'tiles'
MENU_IMAGES_DIR = STATIC_DIR / 'images' / 'menu'
THUMBS_DIR = STATIC_DIR / 'images' / 'thumbs'

# Output path (single folder for everything)
OUTPUT_DIR = BASE_DIR / 'content'


# =============================================================================
# Utility Functions
# =============================================================================

def clean_html_to_markdown(html: str) -> str:
    """Convert HTML content to clean Markdown."""
    if not html:
        return ""

    # Convert HTML to markdown
    markdown = md(html, heading_style="ATX", bullets="-")

    # Clean up common issues
    # Remove excessive blank lines
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)

    # Clean up HTML entities that weren't converted
    markdown = markdown.replace('&nbsp;', ' ')
    markdown = markdown.replace('&ndash;', '–')
    markdown = markdown.replace('&mdash;', '—')

    # Strip leading/trailing whitespace
    markdown = markdown.strip()

    return markdown


def generate_slug(text: str, max_length: int = 50) -> str:
    """Generate a URL-safe slug from text."""
    if not text:
        return "untitled"

    # Use python-slugify with Czech transliteration
    slug = slugify(text, max_length=max_length, word_boundary=True)

    return slug or "untitled"


def create_frontmatter(data: dict) -> str:
    """Create YAML frontmatter from dictionary."""
    # Filter out None values and empty strings
    clean_data = {k: v for k, v in data.items() if v is not None and v != ""}

    yaml_str = yaml.dump(clean_data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n\n"


def load_json(path: Path) -> Optional[dict]:
    """Load JSON file, return None if not found."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        print(f"  Warning: Invalid JSON in {path}: {e}")
        return None


# =============================================================================
# Menu Processing
# =============================================================================

def build_menu_lookup(menu_data: dict) -> dict:
    """Build a lookup table: menu_id -> menu item with URL."""
    lookup = {}

    def process_item(item, parent_url=""):
        item_id = item.get('id')
        url = item.get('url', '')

        lookup[item_id] = {
            'id': item_id,
            'name': item.get('name', ''),
            'url': url,
            'parent_url': parent_url,
            'has_children': bool(item.get('children'))
        }

        for child in item.get('children', []):
            process_item(child, url)

    for root_item in menu_data.get('root', []):
        process_item(root_item)

    return lookup


def generate_menu_yaml(menu_data: dict, output_path: Path):
    """Generate menu.yaml from menu.json."""
    sections = []

    for item in menu_data.get('root', []):
        sections.append({
            'id': item.get('url', ''),
            'title': item.get('name', ''),
            'menu_id': item.get('id')
        })

    menu_yaml = {
        'sections': sections
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(menu_yaml, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"  Created {output_path}")


# =============================================================================
# Page Conversion
# =============================================================================

def get_page_folder(url: str, is_category: bool) -> Path:
    """Get the folder path for a page."""
    if is_category:
        # Category pages: content/{url}/
        return OUTPUT_DIR / url
    else:
        # Leaf pages: content/{parent_url}/{slug}/
        url_parts = url.split('/')
        if len(url_parts) > 1:
            return OUTPUT_DIR / '/'.join(url_parts[:-1]) / url_parts[-1]
        else:
            return OUTPUT_DIR / url


def convert_page(page_path: Path, menu_lookup: dict, galleries_dir: Path) -> Optional[dict]:
    """Convert a single page JSON to Markdown. Returns page info for gallery linking."""
    page_data = load_json(page_path)
    if not page_data:
        return None

    url = page_data.get('url', '')
    title = page_data.get('title', '')
    content_html = page_data.get('content', '')
    menu_id = page_data.get('menu_id')
    gallery_id = page_data.get('gallery_id')

    if not url:
        print(f"  Skipping {page_path.name}: no URL")
        return None

    # Check if this is a category page (has children in menu)
    menu_item = menu_lookup.get(menu_id, {})
    is_category = menu_item.get('has_children', False)

    # Get page folder
    page_folder = get_page_folder(url, is_category)
    page_folder.mkdir(parents=True, exist_ok=True)

    # Determine markdown filename
    if is_category:
        md_path = page_folder / '_index.md'
    else:
        md_path = page_folder / 'page.md'

    # Build frontmatter
    frontmatter_data = {
        'title': title,
        'menu_id': menu_id,
    }

    # Add gallery reference if present (will be local ./gallery/ folder)
    if gallery_id:
        frontmatter_data['gallery'] = True

    # Convert content
    content_md = clean_html_to_markdown(content_html)

    # Write markdown file
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(create_frontmatter(frontmatter_data))
        f.write(content_md)

    return {
        'url': url,
        'menu_id': menu_id,
        'gallery_id': gallery_id,
        'folder': page_folder,
        'is_category': is_category
    }


def convert_all_pages(pages_dir: Path, menu_lookup: dict, galleries_dir: Path) -> dict:
    """Convert all page JSONs to Markdown. Returns mapping of gallery_id -> page_folder."""
    print("\nConverting pages...")

    page_files = list(pages_dir.glob('*.json'))
    converted = 0
    gallery_to_page = {}  # Maps gallery_id -> page_folder

    for page_path in page_files:
        result = convert_page(page_path, menu_lookup, galleries_dir)
        if result:
            converted += 1
            if result.get('gallery_id'):
                gallery_to_page[result['gallery_id']] = result['folder']

    print(f"  Converted {converted}/{len(page_files)} pages")
    return gallery_to_page


# =============================================================================
# Gallery Conversion (co-located with pages)
# =============================================================================

def convert_gallery_to_page_folder(gallery_path: Path, page_folder: Path,
                                    source_images_dir: Path, source_thumbs_dir: Path):
    """Convert a gallery JSON to folder structure within the page folder."""
    gallery_data = load_json(gallery_path)
    if not gallery_data:
        return None

    gallery_id = gallery_data.get('id')
    images = gallery_data.get('images', [])

    if not images:
        return None  # Skip empty galleries

    # Create gallery folder inside page folder
    gallery_folder = page_folder / 'gallery'
    gallery_folder.mkdir(parents=True, exist_ok=True)

    # Sort images by order, then by id
    sorted_images = sorted(images, key=lambda x: (x.get('order', 999), x.get('id', 0)))

    copied = 0
    for idx, img in enumerate(sorted_images, start=1):
        img_id = img.get('id')
        original_filename = img.get('filename', img.get('path', ''))
        caption = img.get('caption', '')
        author = img.get('author', '')

        # Clean caption for slug generation
        caption_text = re.sub(r'<[^>]+>', '', caption)  # Remove HTML tags
        caption_text = caption_text.split('<br')[0]  # Take first line before <br>
        caption_slug = generate_slug(caption_text[:40]) if caption_text else f"image-{img_id}"

        # Base filename (without extension)
        base_name = f"{idx:02d}-{caption_slug}"

        # Copy main image
        source_img = source_images_dir / original_filename
        if source_img.exists():
            shutil.copy2(source_img, gallery_folder / f"{base_name}.jpg")
            copied += 1

        # Copy thumbnail with .thumb.jpg suffix
        source_thumb = source_thumbs_dir / original_filename
        if source_thumb.exists():
            shutil.copy2(source_thumb, gallery_folder / f"{base_name}.thumb.jpg")

        # Create sidecar .md file
        sidecar_path = gallery_folder / f"{base_name}.md"

        # Clean caption HTML
        clean_caption = clean_html_to_markdown(caption)

        sidecar_frontmatter = {}
        if author:
            sidecar_frontmatter['author'] = author

        with open(sidecar_path, 'w', encoding='utf-8') as f:
            if sidecar_frontmatter:
                f.write(create_frontmatter(sidecar_frontmatter))
            else:
                f.write("---\n---\n\n")
            f.write(clean_caption)

    return copied


def convert_all_galleries(galleries_dir: Path, gallery_to_page: dict,
                          source_images_dir: Path, source_thumbs_dir: Path):
    """Convert all galleries that have associated pages."""
    print("\nConverting galleries (co-located with pages)...")

    converted = 0
    total_images = 0

    for gallery_id, page_folder in gallery_to_page.items():
        gallery_path = galleries_dir / f"{gallery_id}.json"
        if gallery_path.exists():
            result = convert_gallery_to_page_folder(
                gallery_path, page_folder,
                source_images_dir, source_thumbs_dir
            )
            if result:
                converted += 1
                total_images += result

    print(f"  Converted {converted} galleries ({total_images} images)")


# =============================================================================
# Page Image Organization (tile + header co-located)
# =============================================================================

def organize_page_images(menu_lookup: dict, tiles_dir: Path, menu_images_dir: Path):
    """Organize tile and header images to co-locate with page folders."""
    print("\nOrganizing page images (tile + header)...")

    copied_tiles = 0
    copied_headers = 0

    for menu_id, item in menu_lookup.items():
        url = item.get('url', '')
        if not url:
            continue

        is_category = item.get('has_children', False)
        page_folder = get_page_folder(url, is_category)

        # Check for tile image
        tile_path = tiles_dir / f"{menu_id}.jpg"
        if tile_path.exists():
            page_folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tile_path, page_folder / 'tile.jpg')
            copied_tiles += 1

        # Check for header image (in menu folder)
        header_path = menu_images_dir / f"{menu_id}.jpg"
        if header_path.exists():
            page_folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(header_path, page_folder / 'header.jpg')
            copied_headers += 1

    print(f"  Copied {copied_tiles} tile images, {copied_headers} header images")


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 60)
    print("CONTENT MIGRATION: JSON → Markdown Filesystem")
    print("=" * 60)
    print("\nOutput: Single content/ folder with co-located images")

    # Load menu and build lookup
    print("\nLoading menu structure...")
    menu_data = load_json(MENU_JSON)
    if not menu_data:
        print("Error: Could not load menu.json")
        return

    menu_lookup = build_menu_lookup(menu_data)
    print(f"  Found {len(menu_lookup)} menu items")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate menu.yaml
    print("\nGenerating menu.yaml...")
    generate_menu_yaml(menu_data, OUTPUT_DIR / 'menu.yaml')

    # Convert pages (returns mapping of gallery_id -> page_folder)
    gallery_to_page = convert_all_pages(PAGES_DIR, menu_lookup, GALLERIES_DIR)

    # Organize page images (tile + header)
    organize_page_images(menu_lookup, TILES_DIR, MENU_IMAGES_DIR)

    # Convert galleries into their associated page folders
    convert_all_galleries(
        GALLERIES_DIR,
        gallery_to_page,
        GALLERY_IMAGES_DIR,
        THUMBS_DIR
    )

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"\nOutput: {OUTPUT_DIR}")
    print("\nStructure:")
    print("  content/")
    print("    ├── menu.yaml")
    print("    └── {section}/")
    print("        ├── _index.md (or page.md)")
    print("        ├── tile.jpg")
    print("        ├── header.jpg")
    print("        └── gallery/")
    print("            ├── 01-name.jpg")
    print("            ├── 01-name.thumb.jpg")
    print("            └── 01-name.md")


if __name__ == '__main__':
    main()
