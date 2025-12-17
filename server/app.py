"""
Priroda Kiosk - Museum Touch Screen Application
Flask application entry point (Czech only)

Uses filesystem-based markdown content from content/ folder.
"""
from flask import Flask, render_template, request, send_from_directory, abort
from pathlib import Path

# Import content loading functions
from server.content import (
    build_menu_tree,
    get_page_content,
    get_gallery,
    get_content_image_path,
    get_gallery_image_path,
    CONTENT_DIR
)

app = Flask(__name__)

# Configuration
app.config['INACTIVITY_TIMEOUT'] = 180000  # 3 minutes in milliseconds
app.config['ITEMS_PER_PAGE'] = 8  # Tiles per page

# Menu cache (rebuilt in debug mode)
_menu_cache = None


def get_menu():
    """Load menu structure from filesystem."""
    global _menu_cache
    if _menu_cache is None or app.debug:
        _menu_cache = build_menu_tree()
    return _menu_cache


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
        item = menu.get('by_url', {}).get(current_path)
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
    """Dynamic page rendering from markdown content."""
    content = get_page_content(page_url)
    menu = get_menu()

    if not content:
        # Check if URL exists in menu (directory without markdown)
        menu_item = menu.get('by_url', {}).get(page_url)
        if menu_item:
            content = {
                'id': menu_item.get('id'),
                'title': menu_item.get('name'),
                'url': page_url,
                'type': 'tile-section' if menu_item.get('children') else None,
                'children': menu_item.get('children', []),
                'content': ''
            }
        else:
            return render_template('404.html'), 404

    breadcrumbs = build_breadcrumb(page_url)
    page_type = content.get('type', 'text-page')

    # Load gallery if page has one
    gallery = None
    if content.get('gallery'):
        gallery = get_gallery(page_url)

    # For HTMX requests, return appropriate partial with OOB breadcrumb
    if request.headers.get('HX-Request'):
        if page_type == 'tile-section':
            return render_htmx('partials/tile-section.html',
                             breadcrumbs=breadcrumbs, content=content)
        elif page_type == 'gallery':
            return render_htmx('partials/gallery-page.html',
                             breadcrumbs=breadcrumbs, content=content, gallery=gallery)
        else:
            return render_htmx('partials/page-content.html',
                             breadcrumbs=breadcrumbs, content=content, gallery=gallery)

    # Full page render
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
    gallery_id = request.args.get('id')  # Now a URL path
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
    current_item = menu.get('by_url', {}).get(current_url)

    return render_template('partials/menu-sidebar.html',
                         menu=menu,
                         current_url=current_url,
                         current_item=current_item)


# =============================================================================
# Content Image Routes (new filesystem structure)
# =============================================================================

@app.route('/content/<path:url>/header.jpg')
def serve_header_image(url):
    """Serve header image - redirects to tile.jpg (consolidated)."""
    # Header images consolidated into tile.jpg
    img_path = get_content_image_path(url, 'tile')
    if img_path:
        return send_from_directory(img_path.parent, img_path.name)
    abort(404)


@app.route('/content/<path:url>/tile.jpg')
def serve_tile_image(url):
    """Serve tile image from content directory."""
    img_path = get_content_image_path(url, 'tile')
    if img_path:
        return send_from_directory(img_path.parent, img_path.name)
    abort(404)


@app.route('/content/<path:url>/gallery/<filename>')
def serve_gallery_image(url, filename):
    """Serve gallery images from content directory."""
    img_path = get_gallery_image_path(url, filename)
    if img_path:
        return send_from_directory(img_path.parent, img_path.name)
    abort(404)


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
