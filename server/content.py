"""
Content loading from filesystem-based markdown structure.

This module replaces JSON-based content loading with filesystem-based
markdown content. All content is stored in the content/ folder with:
- _index.md for category pages
- page.md for leaf pages
- Co-located tile.jpg and header.jpg images
- gallery/ subfolder with images and sidecar .md files
"""

from pathlib import Path
from typing import Optional, Dict, List, Any
import yaml
import frontmatter
import markdown

# =============================================================================
# Configuration
# =============================================================================

CONTENT_DIR = Path(__file__).parent.parent / 'content'

# Markdown processor with common extensions
_md = markdown.Markdown(extensions=['tables', 'fenced_code', 'nl2br'])


# =============================================================================
# Low-level Utilities
# =============================================================================

def _load_frontmatter(md_file: Path) -> Dict[str, Any]:
    """Load frontmatter metadata from a markdown file."""
    try:
        post = frontmatter.load(md_file)
        return dict(post.metadata)
    except Exception:
        return {}


def _load_markdown_file(md_file: Path) -> Dict[str, Any]:
    """Load a markdown file and return metadata + HTML content."""
    try:
        post = frontmatter.load(md_file)
        html_content = _md.convert(post.content)
        _md.reset()
        return {
            'metadata': dict(post.metadata),
            'content': html_content
        }
    except Exception:
        return {'metadata': {}, 'content': ''}


def _get_dir_title(dir_path: Path) -> str:
    """Get title from directory's markdown file or derive from name."""
    for filename in ['_index.md', 'page.md']:
        md_file = dir_path / filename
        if md_file.exists():
            meta = _load_frontmatter(md_file)
            if meta.get('title'):
                return meta['title']
    # Derive from directory name
    return dir_path.name.replace('-', ' ').title()


# =============================================================================
# Menu Loading
# =============================================================================

def load_menu_yaml() -> Dict[str, Any]:
    """Load top-level sections from menu.yaml."""
    menu_path = CONTENT_DIR / 'menu.yaml'
    if menu_path.exists():
        with open(menu_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {'sections': []}


def _build_menu_item(dir_path: Path, url_path: str) -> Dict[str, Any]:
    """Recursively build menu item from directory."""
    title = _get_dir_title(dir_path)

    item = {
        'id': url_path.replace('/', '-'),
        'name': title,
        'url': url_path,
        'children': []
    }

    # Find child directories (exclude 'gallery')
    if dir_path.is_dir():
        for child_dir in sorted(dir_path.iterdir()):
            if child_dir.is_dir() and child_dir.name != 'gallery':
                child_url = f"{url_path}/{child_dir.name}"
                child_item = _build_menu_item(child_dir, child_url)
                item['children'].append(child_item)

    return item


def _index_menu_item(item: Dict, by_url: Dict):
    """Index menu item and its children by URL."""
    by_url[item['url']] = item
    for child in item.get('children', []):
        child['parent'] = item  # Add parent reference
        _index_menu_item(child, by_url)


def build_menu_tree() -> Dict[str, Any]:
    """
    Build complete menu structure by combining menu.yaml with filesystem.

    Returns:
        {
            'root': [
                {'id': 3, 'name': 'Geologie', 'url': 'geologie', 'children': [...]},
                ...
            ],
            'by_url': {'geologie': {...}, 'geologie/kras': {...}, ...}
        }
    """
    menu_yaml = load_menu_yaml()
    root_items = []
    by_url = {}

    for section in menu_yaml.get('sections', []):
        section_id = section.get('id', '')
        section_dir = CONTENT_DIR / section_id

        if section_dir.is_dir():
            item = _build_menu_item(section_dir, section_id)
            # Override with menu.yaml values
            item['name'] = section.get('title', item['name'])
            root_items.append(item)
            _index_menu_item(item, by_url)

    return {'root': root_items, 'by_url': by_url}


# =============================================================================
# Page Content Loading
# =============================================================================

def get_page_content(url: str) -> Optional[Dict[str, Any]]:
    """
    Load page content from markdown file.

    Args:
        url: Page URL path (e.g., 'geologie/kras-olomouckeho-kraje')

    Returns:
        {
            'id': 'url-slug',
            'title': 'Page Title',
            'content': '<p>HTML content...</p>',
            'url': 'geologie/kras-olomouckeho-kraje',
            'type': 'tile-section' or None,
            'gallery': True/False,
            'children': [...]
        }
    """
    url = url.strip('/')
    content_path = CONTENT_DIR / url

    if not content_path.is_dir():
        return None

    # Determine which markdown file to load
    page_file = content_path / 'page.md'
    index_file = content_path / '_index.md'

    if page_file.exists():
        md_file = page_file
    elif index_file.exists():
        md_file = index_file
    else:
        md_file = None

    # Load content
    if md_file:
        data = _load_markdown_file(md_file)
        meta = data['metadata']
        html_content = data['content']

        content = {
            'id': url.replace('/', '-'),
            'title': meta.get('title', content_path.name.replace('-', ' ').title()),
            'content': html_content,
            'url': url,
            'type': meta.get('type'),
            'gallery': meta.get('gallery', False)
        }
    else:
        # Directory exists but no markdown - create minimal content
        content = {
            'id': url.replace('/', '-'),
            'title': content_path.name.replace('-', ' ').title(),
            'content': '',
            'url': url,
            'type': None,
            'gallery': False
        }

    # Build children from subdirectories
    children = []
    for child_dir in sorted(content_path.iterdir()):
        if child_dir.is_dir() and child_dir.name != 'gallery':
            child_url = f"{url}/{child_dir.name}"
            child_title = _get_dir_title(child_dir)
            children.append({
                'id': child_dir.name,
                'name': child_title,
                'url': child_url
            })

    if children:
        content['children'] = children
        if not content['type']:
            content['type'] = 'tile-section'

    # Check for gallery folder
    gallery_dir = content_path / 'gallery'
    if gallery_dir.is_dir() and any(gallery_dir.glob('*.jpg')):
        content['gallery'] = True

    return content


# =============================================================================
# Gallery Loading
# =============================================================================

def get_gallery(url: str) -> Optional[Dict[str, Any]]:
    """
    Load gallery from filesystem.

    Args:
        url: Page URL that contains the gallery

    Returns:
        {
            'id': 'geologie/kras/javoricske-jeskyne',
            'name': 'Gallery Name',
            'images': [
                {
                    'path': 'geologie/.../gallery/01-image.jpg',
                    'thumb': 'geologie/.../gallery/01-image.thumb.jpg',
                    'caption': 'Image caption',
                    'author': 'Author'
                },
                ...
            ]
        }
    """
    url = url.strip('/')
    gallery_path = CONTENT_DIR / url / 'gallery'

    if not gallery_path.is_dir():
        return None

    # Get page title for gallery name
    page_content = get_page_content(url)
    gallery_name = page_content['title'] if page_content else url.split('/')[-1]

    images = []

    # Find all .jpg files (excluding .thumb.jpg)
    image_files = sorted([
        f for f in gallery_path.glob('*.jpg')
        if not f.name.endswith('.thumb.jpg')
    ])

    for img_file in image_files:
        img_stem = img_file.stem
        rel_path = f"{url}/gallery/{img_file.name}"

        # Look for sidecar .md file
        sidecar_file = gallery_path / f"{img_stem}.md"
        caption = ''
        author = ''

        if sidecar_file.exists():
            post = frontmatter.load(sidecar_file)
            # Author might be in frontmatter
            author = post.get('author', '')

            # Caption is in the body
            caption_text = post.content.strip()
            if caption_text:
                # Check if "Foto:" appears in text (author embedded in caption)
                lines = caption_text.split('\n')
                caption_parts = []
                for line in lines:
                    line = line.strip()
                    if line.lower().startswith('foto:'):
                        if not author:
                            author = line[5:].strip()
                    else:
                        caption_parts.append(line)
                caption = ' '.join(caption_parts).strip()

        # Check for thumbnail
        thumb_file = gallery_path / f"{img_stem}.thumb.jpg"
        thumb_path = f"{url}/gallery/{img_stem}.thumb.jpg" if thumb_file.exists() else rel_path

        images.append({
            'path': rel_path,
            'thumb': thumb_path,
            'caption': caption,
            'author': author
        })

    return {
        'id': url,
        'name': gallery_name,
        'images': images
    }


# =============================================================================
# Image Path Helpers
# =============================================================================

def get_content_image_path(url: str, image_type: str) -> Optional[Path]:
    """
    Get absolute path to content image.

    Args:
        url: Page URL path
        image_type: 'header', 'tile'

    Returns:
        Path object or None if not found
    """
    url = url.strip('/')
    content_path = CONTENT_DIR / url

    if image_type == 'header':
        img_path = content_path / 'header.jpg'
    elif image_type == 'tile':
        img_path = content_path / 'tile.jpg'
    else:
        return None

    return img_path if img_path.exists() else None


def get_gallery_image_path(url: str, filename: str) -> Optional[Path]:
    """
    Get absolute path to gallery image.

    Args:
        url: Page URL path
        filename: Image filename (e.g., '01-image.jpg')

    Returns:
        Path object or None if not found
    """
    url = url.strip('/')
    img_path = CONTENT_DIR / url / 'gallery' / filename
    return img_path if img_path.exists() else None
