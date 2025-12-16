"""
Priroda Kiosk - Museum Touch Screen Application
Flask application entry point (Czech only)
"""
from flask import Flask, render_template, request, send_from_directory
from pathlib import Path
import json

app = Flask(__name__)

# Configuration
app.config['CONTENT_DIR'] = Path(__file__).parent.parent / 'data'
app.config['INACTIVITY_TIMEOUT'] = 180000  # 3 minutes in milliseconds
app.config['ITEMS_PER_PAGE'] = 8  # Tiles per page


def load_json(filepath):
    """Load JSON file and return data."""
    path = app.config['CONTENT_DIR'] / filepath
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def get_menu():
    """Load menu structure."""
    return load_json('content/menu.json') or {}


def get_page(url):
    """Load page content by URL."""
    url = url.strip('/')
    url_safe = url.replace('/', '_')
    return load_json(f'content/pages/cz/{url_safe}.json')


def get_gallery(gallery_id):
    """Load gallery metadata by ID."""
    return load_json(f'galleries/{gallery_id}.json')


def build_breadcrumb(url):
    """Build breadcrumb trail from URL."""
    if not url or url == '/':
        return []

    parts = url.strip('/').split('/')
    breadcrumbs = []
    current_path = ''
    menu = get_menu()

    for part in parts:
        current_path = f"{current_path}/{part}" if current_path else part
        item = find_menu_item(menu.get('root', []), current_path)
        if item:
            breadcrumbs.append({
                'name': item.get('name', part),
                'url': current_path if current_path != url else None
            })
        else:
            breadcrumbs.append({
                'name': part.replace('-', ' ').title(),
                'url': current_path if current_path != url else None
            })

    return breadcrumbs


def find_menu_item(items, url):
    """Recursively find menu item by URL."""
    for item in items:
        if item.get('url') == url:
            return item
        children = item.get('children', [])
        if children:
            found = find_menu_item(children, url)
            if found:
                return found
    return None


@app.context_processor
def inject_globals():
    """Inject common variables into all templates."""
    return {
        'inactivity_timeout': app.config['INACTIVITY_TIMEOUT'],
        'is_htmx': request.headers.get('HX-Request') == 'true'
    }


def render_htmx(template, breadcrumbs=None, **context):
    """Render template with OOB breadcrumb update for HTMX requests."""
    content = render_template(template, breadcrumbs=breadcrumbs, **context)
    if breadcrumbs is not None:
        breadcrumb_html = render_template('partials/breadcrumb.html', breadcrumbs=breadcrumbs)
        oob = f'<div id="breadcrumb-container" hx-swap-oob="innerHTML">{breadcrumb_html}</div>'
        return content + oob
    return content


# =============================================================================
# Main Routes
# =============================================================================

@app.route('/')
def home():
    """Homepage with main navigation tiles."""
    menu = get_menu()

    if request.headers.get('HX-Request'):
        return render_htmx('partials/home-content.html', breadcrumbs=[], menu=menu)

    return render_template('home.html', menu=menu)


@app.route('/mapa')
def map_view():
    """Map view of Olomouc region."""
    breadcrumbs = [{'name': 'Mapa', 'url': None}]
    if request.headers.get('HX-Request'):
        return render_htmx('partials/czech-map.html', breadcrumbs=breadcrumbs)
    return render_template('map.html', breadcrumbs=breadcrumbs)


@app.route('/<path:page_url>')
def page(page_url):
    """Dynamic page rendering."""
    content = get_page(page_url)
    menu = get_menu()
    menu_item = find_menu_item(menu.get('root', []), page_url)

    if not content:
        # Try to find as a section/category page from menu
        if menu_item:
            children = menu_item.get('children', [])
            page_type = 'tile-section' if children else menu_item.get('type', 'section')
            content = {
                'id': menu_item.get('id'),
                'title': menu_item.get('name'),
                'url': page_url,
                'type': page_type,
                'children': children
            }
        else:
            return render_template('404.html'), 404
    else:
        # Page content exists - merge children from menu if available
        if menu_item:
            children = menu_item.get('children', [])
            if children:
                content['children'] = children
                # If page has children, it's a category page with content
                if not content.get('type'):
                    content['type'] = 'tile-section'

    breadcrumbs = build_breadcrumb(page_url)
    page_type = content.get('type', 'text-page')

    # For HTMX requests, return appropriate partial with OOB breadcrumb
    if request.headers.get('HX-Request'):
        if page_type == 'tile-section':
            return render_htmx('partials/tile-section.html',
                             breadcrumbs=breadcrumbs, content=content)
        elif page_type == 'gallery':
            gallery = get_gallery(content.get('gallery_id'))
            return render_htmx('partials/gallery-page.html',
                             breadcrumbs=breadcrumbs, content=content, gallery=gallery)
        else:
            gallery = None
            if content.get('gallery_id'):
                gallery = get_gallery(content.get('gallery_id'))
            return render_htmx('partials/page-content.html',
                             breadcrumbs=breadcrumbs, content=content, gallery=gallery)

    # Full page render
    gallery = None
    if content.get('gallery_id'):
        gallery = get_gallery(content.get('gallery_id'))

    return render_template('page.html',
                         content=content, gallery=gallery,
                         breadcrumbs=breadcrumbs)


# =============================================================================
# HTMX Partial Routes
# =============================================================================

@app.route('/partials/breadcrumb')
def partial_breadcrumb():
    """Return breadcrumb partial."""
    url = request.args.get('url', '/')
    breadcrumbs = build_breadcrumb(url)
    return render_template('partials/breadcrumb.html', breadcrumbs=breadcrumbs)


@app.route('/partials/tiles')
def partial_tiles():
    """Return tile grid partial with pagination."""
    parent_url = request.args.get('parent', '')
    page_num = request.args.get('page', 1, type=int)
    per_page = app.config['ITEMS_PER_PAGE']

    menu = get_menu()

    if parent_url:
        parent_item = menu.get('by_url', {}).get(parent_url)
        if not parent_item:
            parent_item = find_menu_item(menu.get('root', []), parent_url)
    else:
        parent_item = None

    if parent_item:
        children = parent_item.get('children', [])
    else:
        children = menu.get('root', [])

    # Pagination
    total_items = len(children)
    total_pages = (total_items + per_page - 1) // per_page
    start_idx = (page_num - 1) * per_page
    end_idx = start_idx + per_page
    items = children[start_idx:end_idx]

    return render_template('partials/tile-grid.html',
                         items=items,
                         page=page_num,
                         total_pages=total_pages,
                         parent_url=parent_url,
                         has_more=page_num < total_pages,
                         has_prev=page_num > 1)


@app.route('/partials/gallery')
def partial_gallery():
    """Return gallery viewer partial."""
    gallery_id = request.args.get('id')
    current_idx = request.args.get('index', 0, type=int)

    gallery = get_gallery(gallery_id)
    if not gallery:
        return '<div class="gallery-error">Galerie nenalezena</div>', 404

    images = gallery.get('images', [])
    total = len(images)

    current_idx = max(0, min(current_idx, total - 1))
    current_image = images[current_idx] if images else None

    return render_template('partials/gallery-viewer.html',
                         gallery=gallery,
                         current_image=current_image,
                         current_index=current_idx,
                         total=total,
                         has_prev=current_idx > 0,
                         has_next=current_idx < total - 1)


@app.route('/partials/menu-sidebar')
def partial_menu_sidebar():
    """Return sidebar menu partial."""
    current_url = request.args.get('url', '')
    menu = get_menu()
    current_item = find_menu_item(menu.get('root', []), current_url)

    return render_template('partials/menu-sidebar.html',
                         menu=menu,
                         current_url=current_url,
                         current_item=current_item)


# =============================================================================
# Static File Routes
# =============================================================================

STATIC_IMAGES_DIR = Path(__file__).parent.parent / 'static' / 'images'

@app.route('/data/images/<path:filename>')
def serve_image(filename):
    """Serve images from data directory."""
    images_dir = app.config['CONTENT_DIR'] / 'images'
    return send_from_directory(images_dir, filename)


@app.route('/images/menu/<filename>')
def serve_menu_image(filename):
    """Serve menu header images from static folder."""
    return send_from_directory(STATIC_IMAGES_DIR / 'menu', filename)


@app.route('/images/tiles/<filename>')
def serve_tile_image(filename):
    """Serve tile images - use menu images for better quality."""
    # Try menu images first (919x409), fall back to tiles (141x141)
    menu_path = STATIC_IMAGES_DIR / 'menu' / filename
    if menu_path.exists():
        return send_from_directory(STATIC_IMAGES_DIR / 'menu', filename)
    return send_from_directory(STATIC_IMAGES_DIR / 'tiles', filename)


@app.route('/images/gallery/<filename>')
def serve_gallery_image(filename):
    """Serve gallery images from static folder."""
    return send_from_directory(STATIC_IMAGES_DIR / 'gallery', filename)


@app.route('/images/thumbs/<filename>')
def serve_thumb_image(filename):
    """Serve thumbnail images from static folder."""
    return send_from_directory(STATIC_IMAGES_DIR / 'thumbs', filename)


# =============================================================================
# Error Handlers
# =============================================================================

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    if request.headers.get('HX-Request'):
        return render_template('partials/error.html',
                             error='Stránka nenalezena'), 404
    return render_template('404.html'), 404


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
