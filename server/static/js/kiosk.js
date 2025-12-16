/**
 * Priroda Kiosk - Kiosk Mode JavaScript
 * Handles inactivity timer, fullscreen, and kiosk-specific behaviors
 */

class KioskManager {
    constructor(options = {}) {
        this.timeout = options.timeout || 180000; // 3 minutes default
        this.homeUrl = options.homeUrl || '/';
        this.timer = null;
        this.isFullscreen = false;

        // Check for debug mode via URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        this.debugMode = urlParams.get('debug') === '1' || urlParams.get('debug') === 'true';

        this.init();
    }

    init() {
        // Get timeout from body data attribute if set
        const bodyTimeout = document.body.dataset.inactivityTimeout;
        if (bodyTimeout) {
            this.timeout = parseInt(bodyTimeout, 10);
        }

        // Detect language from URL
        if (window.location.pathname.startsWith('/en')) {
            this.homeUrl = '/en/';
        }

        // Start inactivity timer
        this.resetTimer();

        // Bind event listeners for activity detection
        this.bindActivityEvents();

        // Bind HTMX events
        this.bindHtmxEvents();

        // DISABLED: Kiosk mode features (uncomment for production)
        // this.preventBrowserBehaviors();
        // this.setupFullscreen();
        // document.body.classList.add('kiosk-mode');

        console.log('Kiosk Manager initialized (development mode)', {
            timeout: this.timeout,
            homeUrl: this.homeUrl
        });
    }

    bindActivityEvents() {
        const events = ['touchstart', 'touchend', 'touchmove', 'click', 'scroll', 'keydown'];

        events.forEach(eventType => {
            document.addEventListener(eventType, () => {
                this.resetTimer();
            }, { passive: true });
        });
    }

    bindHtmxEvents() {
        // Reset timer on HTMX requests
        document.body.addEventListener('htmx:beforeRequest', () => {
            this.resetTimer();
        });

        document.body.addEventListener('htmx:afterRequest', () => {
            this.resetTimer();
        });

        // Update home URL when language changes
        document.body.addEventListener('htmx:pushedIntoHistory', (event) => {
            if (event.detail.path.startsWith('/en')) {
                this.homeUrl = '/en/';
            } else {
                this.homeUrl = '/';
            }
        });
    }

    preventBrowserBehaviors() {
        // Prevent context menu (right-click)
        document.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            return false;
        });

        // Prevent keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Block common browser shortcuts
            const blockedKeys = [
                { key: 'F5' },                    // Refresh
                { key: 'r', ctrl: true },         // Refresh
                { key: 'F11' },                   // Fullscreen toggle
                { key: 'F12' },                   // Dev tools
                { key: 'i', ctrl: true, shift: true }, // Dev tools
                { key: 'j', ctrl: true, shift: true }, // Console
                { key: 'u', ctrl: true },         // View source
                { key: 'p', ctrl: true },         // Print
                { key: 's', ctrl: true },         // Save
                { key: 'f', ctrl: true },         // Find
            ];

            for (const blocked of blockedKeys) {
                if (e.key === blocked.key &&
                    (!blocked.ctrl || e.ctrlKey) &&
                    (!blocked.shift || e.shiftKey) &&
                    (!blocked.alt || e.altKey)) {
                    e.preventDefault();
                    return false;
                }
            }
        });

        // Prevent drag and drop
        document.addEventListener('dragstart', (e) => {
            e.preventDefault();
            return false;
        });

        // Prevent text selection on double-tap
        document.addEventListener('dblclick', (e) => {
            e.preventDefault();
        });

        // Prevent pinch zoom
        document.addEventListener('gesturestart', (e) => {
            e.preventDefault();
        });
    }

    setupFullscreen() {
        // Request fullscreen on first touch
        const requestFullscreen = () => {
            if (!this.isFullscreen) {
                this.enterFullscreen();
            }
            document.removeEventListener('touchstart', requestFullscreen);
            document.removeEventListener('click', requestFullscreen);
        };

        document.addEventListener('touchstart', requestFullscreen, { once: true });
        document.addEventListener('click', requestFullscreen, { once: true });

        // Handle fullscreen changes
        document.addEventListener('fullscreenchange', () => {
            this.isFullscreen = !!document.fullscreenElement;
        });

        // Handle visibility changes (screen wake/sleep)
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                // Go home when screen wakes up
                this.goHome();
                // Re-enter fullscreen
                this.enterFullscreen();
            }
        });
    }

    enterFullscreen() {
        const elem = document.documentElement;

        if (elem.requestFullscreen) {
            elem.requestFullscreen().catch((err) => {
                console.log('Fullscreen request failed:', err);
            });
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        } else if (elem.mozRequestFullScreen) {
            elem.mozRequestFullScreen();
        } else if (elem.msRequestFullscreen) {
            elem.msRequestFullscreen();
        }
    }

    resetTimer() {
        // Clear existing timer
        if (this.timer) {
            clearTimeout(this.timer);
        }

        // Set new timer
        this.timer = setTimeout(() => {
            this.onInactivity();
        }, this.timeout);
    }

    onInactivity() {
        console.log('Inactivity timeout reached, returning to home');
        this.goHome();
    }

    goHome() {
        const currentPath = window.location.pathname;

        // Don't navigate if already at home
        if (currentPath === this.homeUrl || currentPath === '/') {
            // Still reset the view in case user scrolled
            window.scrollTo(0, 0);
            this.resetTimer();
            return;
        }

        // Use HTMX to navigate home (smooth transition)
        const mainContent = document.getElementById('main-content');

        if (mainContent && typeof htmx !== 'undefined') {
            htmx.ajax('GET', this.homeUrl, {
                target: '#main-content',
                swap: 'innerHTML'
            }).then(() => {
                // Update browser history
                history.pushState({}, '', this.homeUrl);
                // Scroll to top
                window.scrollTo(0, 0);
            });
        } else {
            // Fallback to regular navigation
            window.location.href = this.homeUrl;
        }

        // Reset timer after navigation
        this.resetTimer();
    }

    // Public method to manually trigger home navigation
    navigateHome() {
        this.goHome();
    }

    // Public method to update timeout
    setTimeout(ms) {
        this.timeout = ms;
        this.resetTimer();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Create global instance
    window.kioskManager = new KioskManager();
});

// Also initialize if HTMX loads content dynamically
document.body.addEventListener('htmx:load', () => {
    // Reinitialize any kiosk-specific behaviors for new content
});
