/**
 * Priroda Kiosk - Touch Swipe Handler
 * Handles swipe gestures for gallery navigation and tile pagination
 */

class SwipeHandler {
    constructor(options = {}) {
        this.threshold = options.threshold || 50;      // Minimum swipe distance
        this.restraint = options.restraint || 100;     // Max perpendicular distance
        this.allowedTime = options.allowedTime || 500; // Max swipe duration

        this.startX = 0;
        this.startY = 0;
        this.startTime = 0;
        this.isSwiping = false;

        this.init();
    }

    init() {
        // Bind touch events
        document.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: true });
        document.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        document.addEventListener('touchend', this.handleTouchEnd.bind(this), { passive: true });

        console.log('Swipe Handler initialized');
    }

    handleTouchStart(e) {
        const touch = e.changedTouches[0];
        this.startX = touch.pageX;
        this.startY = touch.pageY;
        this.startTime = Date.now();
        this.isSwiping = true;
    }

    handleTouchMove(e) {
        if (!this.isSwiping) return;

        // Check if we're in a scrollable container
        const target = e.target;
        const scrollableParent = this.findScrollableParent(target);

        // If in gallery viewer, prevent default to enable swipe
        if (target.closest('.gallery-viewer') || target.closest('.gallery-main')) {
            // Allow horizontal swipe, prevent vertical scroll
            const touch = e.changedTouches[0];
            const distX = Math.abs(touch.pageX - this.startX);
            const distY = Math.abs(touch.pageY - this.startY);

            if (distX > distY && distX > 10) {
                e.preventDefault();
            }
        }
    }

    handleTouchEnd(e) {
        if (!this.isSwiping) return;
        this.isSwiping = false;

        const touch = e.changedTouches[0];
        const distX = touch.pageX - this.startX;
        const distY = touch.pageY - this.startY;
        const elapsedTime = Date.now() - this.startTime;

        // Check if this qualifies as a swipe
        if (elapsedTime <= this.allowedTime) {
            if (Math.abs(distX) >= this.threshold && Math.abs(distY) <= this.restraint) {
                const direction = distX > 0 ? 'right' : 'left';
                this.handleSwipe(direction, e.target);
            }
        }
    }

    findScrollableParent(element) {
        while (element && element !== document.body) {
            const style = window.getComputedStyle(element);
            const overflowY = style.getPropertyValue('overflow-y');

            if (overflowY === 'auto' || overflowY === 'scroll') {
                return element;
            }

            element = element.parentElement;
        }
        return null;
    }

    handleSwipe(direction, target) {
        console.log('Swipe detected:', direction);

        // Check for gallery viewer
        const gallery = target.closest('.gallery-viewer');
        if (gallery) {
            this.handleGallerySwipe(gallery, direction);
            return;
        }

        // Check for tile grid pagination
        const tileGrid = target.closest('.tile-grid');
        if (tileGrid) {
            this.handleTileSwipe(tileGrid, direction);
            return;
        }

        // Check for any swipeable container
        const swipeable = target.closest('[data-swipeable]');
        if (swipeable) {
            this.handleCustomSwipe(swipeable, direction);
            return;
        }
    }

    handleGallerySwipe(gallery, direction) {
        // Find the appropriate navigation button
        const navButton = gallery.querySelector(
            direction === 'left' ? '.gallery-nav.next, .gallery-next' : '.gallery-nav.prev, .gallery-prev'
        );

        if (navButton && !navButton.disabled) {
            // Show swipe indicator
            this.showSwipeIndicator(gallery, direction);

            // Trigger HTMX click
            if (typeof htmx !== 'undefined') {
                htmx.trigger(navButton, 'click');
            } else {
                navButton.click();
            }
        }
    }

    handleTileSwipe(tileGrid, direction) {
        // Find pagination container
        const pagination = tileGrid.querySelector('.tile-pagination') ||
                          tileGrid.parentElement.querySelector('.tile-pagination');

        if (pagination) {
            const navButton = pagination.querySelector(
                direction === 'left' ? '.nav-btn.next, .nav-next' : '.nav-btn.prev, .nav-prev'
            );

            if (navButton && !navButton.disabled) {
                if (typeof htmx !== 'undefined') {
                    htmx.trigger(navButton, 'click');
                } else {
                    navButton.click();
                }
            }
        }
    }

    handleCustomSwipe(element, direction) {
        // Dispatch custom event for other components
        const event = new CustomEvent('swipe', {
            detail: { direction },
            bubbles: true
        });
        element.dispatchEvent(event);
    }

    showSwipeIndicator(container, direction) {
        // Create or find indicator
        let indicator = container.querySelector('.swipe-hint.' + direction);

        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = `swipe-hint ${direction}`;
            indicator.innerHTML = direction === 'left' ? '&rarr;' : '&larr;';
            container.appendChild(indicator);
        }

        // Show briefly
        indicator.classList.add('visible');
        setTimeout(() => {
            indicator.classList.remove('visible');
        }, 300);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.swipeHandler = new SwipeHandler();
});

// Re-initialize for dynamically loaded content
document.body.addEventListener('htmx:afterSwap', () => {
    // Swipe handler uses event delegation, so no re-init needed
    // But we can add any necessary setup for new content here
});
